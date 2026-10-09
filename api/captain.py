"""Private rules-based ride assistant; never contacts emergency services or others.

The server schedules check-ins; apps display them only while open. Captain is
not a human monitor. Run one worker with the existing SQLite deployment.
"""
from __future__ import annotations
import asyncio
from contextlib import suppress
import hashlib
import json
import logging
import time
from typing import Literal
from uuid import UUID, uuid4
from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

INTERVAL = 300
POLL_INTERVAL = 15
SCHEMA = """
CREATE TABLE IF NOT EXISTS captains(
 id TEXT PRIMARY KEY, booking_id TEXT UNIQUE NOT NULL REFERENCES bookings(id),
 rider_id TEXT NOT NULL REFERENCES users(id), created REAL NOT NULL,
 started REAL, next_checkin REAL, concern_reported INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS captain_checkins(
 id TEXT PRIMARY KEY, booking_id TEXT NOT NULL REFERENCES bookings(id),
 due_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'awaiting', answered REAL,
 UNIQUE(booking_id,due_at));
CREATE UNIQUE INDEX IF NOT EXISTS captain_one_pending ON captain_checkins(booking_id) WHERE status='awaiting';
CREATE TABLE IF NOT EXISTS captain_messages(
 seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
 booking_id TEXT NOT NULL REFERENCES bookings(id), role TEXT NOT NULL,
 text TEXT NOT NULL, created REAL NOT NULL, checkin_id TEXT);
CREATE INDEX IF NOT EXISTS captain_history ON captain_messages(booking_id,seq);
CREATE TABLE IF NOT EXISTS captain_requests(
 booking_id TEXT NOT NULL REFERENCES bookings(id), request_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL, created REAL NOT NULL,
 PRIMARY KEY(booking_id,request_id));
"""

class Message(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=1000)
    action: Literal['all_good', 'need_help', 'unsafe', 'status'] | None = None
    checkin_id: str | None = Field(default=None, min_length=1, max_length=100)
    request_id: UUID

def init(c):
    """Install additive schema from the core database initialization."""
    c.executescript(SCHEMA)

def _message(c, booking_id, role, text, now, checkin_id=None):
    c.execute('INSERT INTO captain_messages(id,booking_id,role,text,created,checkin_id) VALUES(?,?,?,?,?,?)',
              ('msg_' + uuid4().hex, booking_id, role, text, now, checkin_id))

def ensure(c, booking_id, rider_id, now):
    """Assign one persistent assistant per reservation, in its transaction."""
    assignment = c.execute('SELECT * FROM captains WHERE booking_id=?', (booking_id,)).fetchone()
    if assignment is None:
        c.execute('INSERT INTO captains(id,booking_id,rider_id,created) VALUES(?,?,?,?)',
                  ('captain_' + uuid4().hex, booking_id, rider_id, now))
        _message(c, booking_id, 'captain',
                 "I'm your automated ride Captain. I can explain this booking and check in while your trip is in progress. "
                 "This private chat is visible to you; concerns you report are recorded for manual operator review. "
                 "I am not a human monitor or emergency dispatcher. Check-ins appear when the app is open. "
                 "Use SOS to call 112 or contact someone you trust if you need urgent help.", now)
    return c.execute('SELECT * FROM captains WHERE booking_id=?', (booking_id,)).fetchone()

def _check(c, booking_id, due_at, now):
    if c.execute("SELECT 1 FROM captain_checkins WHERE booking_id=? AND status='awaiting'", (booking_id,)).fetchone():
        return
    identifier = 'check_' + uuid4().hex
    inserted = c.execute('INSERT OR IGNORE INTO captain_checkins(id,booking_id,due_at) VALUES(?,?,?)',
                         (identifier, booking_id, due_at)).rowcount
    if inserted:
        _message(c, booking_id, 'captain',
                 "How is your ride going? Choose All good, Need help, or I feel unsafe. "
                 "No response stays marked Awaiting; it does not confirm whether you are safe.", now, identifier)

def start(c, booking_id, now):
    """Start the check-in clock once, after a trip has successfully started."""
    b = c.execute('SELECT * FROM bookings WHERE id=?', (booking_id,)).fetchone()
    if b is None or b['status'] != 'in_progress':
        return
    assignment = ensure(c, booking_id, b['rider_id'], now)
    if assignment['started'] is None:
        c.execute('UPDATE captains SET started=?,next_checkin=? WHERE booking_id=?', (now, now + INTERVAL, booking_id))
        _check(c, booking_id, now, now)

def tick(service, now=None):
    """Queue due prompts durably without a backlog of unanswered prompts."""
    now = time.time() if now is None else now
    with service.db(True) as c:
        rows = c.execute("SELECT id FROM bookings WHERE status='in_progress'").fetchall()
        for row in rows:
            start(c, row['id'], now)  # Adopt trips underway when the API is upgraded.
            a = c.execute('SELECT * FROM captains WHERE booking_id=?', (row['id'],)).fetchone()
            if a['next_checkin'] is not None and a['next_checkin'] <= now:
                _check(c, row['id'], a['next_checkin'], now)

def _state(c, b, now):
    a = ensure(c, b['id'], b['rider_id'], now)
    active = b['status'] == 'in_progress'
    if active:
        start(c, b['id'], now)
        a = c.execute('SELECT * FROM captains WHERE booking_id=?', (b['id'],)).fetchone()
        if a['next_checkin'] is not None and a['next_checkin'] <= now:
            _check(c, b['id'], a['next_checkin'], now)
    checkin = c.execute('SELECT id,status,due_at FROM captain_checkins WHERE booking_id=? ORDER BY due_at DESC LIMIT 1',
                        (b['id'],)).fetchone() if active else None
    rows = c.execute('SELECT id,role,text,created FROM captain_messages WHERE booking_id=? ORDER BY seq DESC LIMIT 50',
                     (b['id'],)).fetchall()
    return {'captain': {'id': a['id'], 'name': 'Captain ' + a['id'][-6:].upper(), 'automated': True, 'booking_id': b['id']},
            'messages': [dict(row) for row in reversed(rows)], 'checkin': dict(checkin) if checkin else None,
            'next_checkin_at': a['next_checkin'] if active else None, 'delivery': 'foreground',
            'trip_status': b['status'], 'concern_reported': bool(a['concern_reported'])}

def _intent(data):
    if data.action:
        return data.action
    text = data.text.casefold()
    if any(word in text for word in ('unsafe', 'not safe', 'danger', 'threaten', 'harass', 'accident', 'attacked', 'emergency')):
        return 'unsafe'
    if any(word in text for word in ('need help', 'help me', 'unwell', 'uncomfortable')) or text == 'help':
        return 'need_help'
    if any(word in text for word in ('pay', 'fare', 'charge', 'cost', 'refund')):
        return 'payment'
    if any(word in text for word in ('carbon', 'tree', 'impact', 'heat', 'traffic', 'co2')):
        return 'impact'
    if any(word in text for word in ('driver', 'car', 'bike', 'vehicle', 'plate')):
        return 'driver'
    if any(word in text for word in ('status', 'trip', 'ride', 'where', 'pickup', 'destination', 'cancel')):
        return 'status'
    return 'fallback'

def _reply(c, b, r, intent):
    if intent in ('need_help', 'unsafe'):
        return ("Your concern has been recorded for manual operator review. No one has been automatically contacted, "
                "and this chat is not monitored in real time. If you need urgent help, open SOS to call 112 or your trusted contact. "
                "Use those options directly; do not wait here for a reply.")
    if intent == 'all_good':
        concern = c.execute('SELECT concern_reported FROM captains WHERE booking_id=?', (b['id'],)).fetchone()[0]
        return ("Thanks for the update. This check-in records that you reported All good; it is not a safety guarantee. "
                "I will check in again in about 5 minutes while the trip is in progress."
                + (" Your earlier concern remains recorded for manual review." if concern else ''))
    if intent == 'payment':
        payment = 'marked paid after server verification' if b['paid'] else 'not marked paid'
        return (f"This booking's recorded fare is ₹{b['total']}; payment is {payment}. "
                "Open the booking's payment option after the trip is completed. "
                "I cannot collect money, change the fare, or promise a refund in chat.")
    if intent == 'driver':
        d = c.execute('SELECT name FROM users WHERE id=?', (r['driver_id'],)).fetchone()
        return (f"Your booking lists {d['name']} as the driver, with {r['vehicle']} ({r['plate']}). "
                "Check the vehicle and driver before boarding. Use the booking screen for the trip PIN; do not type it in this chat.")
    if intent == 'impact':
        return ("Open Impact for recorded contributions and clearly labelled ride estimates. Carbon savings depend on distance, "
                "sharing and the travel option replaced; they are not measured emissions. "
                "Tree funding is recorded separately from fares. A city temperature reduction cannot be calculated from your trip alone.")
    if intent == 'status':
        return (f"This booking is {b['status'].replace('_', ' ')}: {r['origin']} → {r['destination']}, with {b['seats']} passenger seat(s). "
                "Use the booking screen for available trip actions and any recent shared location. "
                "I cannot confirm your safety or estimate arrival from chat.")
    return ("I can help with this booking's status, driver details, fare, and impact information. "
            "Try asking 'trip status' or choose a check-in response. For a concern, choose Need help or I feel unsafe. "
            "For urgent help, use SOS directly.")

def register(app, service):
    """Install routes and lifecycle tasks once without importing the core module."""
    if getattr(app.state, 'captain_registered', False):
        return
    app.state.captain_registered = True

    @app.get('/v1/bookings/{id}/captain')
    def conversation(id: str, u=Depends(service.current)):
        with service.db(True) as c:
            b, _ = service.owned_booking(c, id, u)
            return _state(c, b, time.time())

    @app.post('/v1/bookings/{id}/captain/messages')
    def send(id: str, data: Message, u=Depends(service.current)):
        now = time.time()
        fingerprint = hashlib.sha256(json.dumps(data.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
        with service.db(True) as c:
            b, r = service.owned_booking(c, id, u)
            _state(c, b, now)
            previous = c.execute('SELECT fingerprint FROM captain_requests WHERE booking_id=? AND request_id=?',
                                 (id, str(data.request_id))).fetchone()
            if previous:
                service.fail(previous['fingerprint'] == fingerprint, 'This request ID was already used for a different message.', 409)
                return _state(c, b, now)
            recent = c.execute('SELECT count(*) FROM captain_requests WHERE booking_id=? AND created>?', (id, now - 60)).fetchone()[0]
            service.fail(recent < 12, 'Please wait a moment before sending another Captain message.', 429)
            intent = _intent(data)
            checkin = None
            if data.checkin_id:
                checkin = c.execute("SELECT * FROM captain_checkins WHERE id=? AND booking_id=? AND status='awaiting'",
                                    (data.checkin_id, id)).fetchone()
                service.fail(checkin is not None and b['status'] == 'in_progress' and checkin['due_at'] <= now,
                             'This check-in is not awaiting a reply. Refresh the chat.', 409)
                service.fail(intent in ('all_good', 'need_help', 'unsafe'), 'Choose a check-in response for this prompt.')
            if intent == 'all_good':
                service.fail(checkin is not None, 'Choose All good on the current check-in prompt.', 409)
            c.execute('INSERT INTO captain_requests VALUES(?,?,?,?)', (id, str(data.request_id), fingerprint, now))
            _message(c, id, 'rider', data.text, now, data.checkin_id)
            if checkin:
                status = {'all_good': 'all_good', 'need_help': 'needs_help', 'unsafe': 'unsafe'}[intent]
                c.execute('UPDATE captain_checkins SET status=?,answered=? WHERE id=?', (status, now, checkin['id']))
                c.execute('UPDATE captains SET next_checkin=? WHERE booking_id=?', (now + INTERVAL, id))
            if intent in ('need_help', 'unsafe'):
                c.execute('UPDATE captains SET concern_reported=1 WHERE booking_id=?', (id,))
                c.execute('INSERT INTO incidents(id,user_id,booking_id,kind,detail,created) VALUES(?,?,?,?,?,?)',
                          ('incident_' + uuid4().hex, u['id'], id, 'safety', 'Captain report (' + intent + '): ' + data.text, now))
            _message(c, id, 'captain', _reply(c, b, r, intent), now, data.checkin_id)
            return _state(c, b, now)

    @app.get('/v1/captain/checkins')
    def pending(u=Depends(service.current)):
        now = time.time()
        with service.db(True) as c:
            for b in c.execute("SELECT * FROM bookings WHERE rider_id=? AND status='in_progress'", (u['id'],)).fetchall():
                _state(c, b, now)
            rows = c.execute("""SELECT b.id AS booking_id,a.id AS captain_id,q.id AS checkin_id,q.due_at,q.status
                FROM captain_checkins q JOIN bookings b ON b.id=q.booking_id JOIN captains a ON a.booking_id=b.id
                WHERE b.rider_id=? AND b.status='in_progress' AND q.status='awaiting' ORDER BY q.due_at LIMIT 100""", (u['id'],)).fetchall()
            return {'checkins': [dict(row) for row in rows]}

    async def scheduler():
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            try:
                await asyncio.to_thread(tick, service)
            except Exception:
                logging.getLogger(__name__).error('Captain scheduling failed; due prompts will be retried.')

    @app.on_event('startup')
    async def begin():
        with service.db() as c:
            init(c)
        await asyncio.to_thread(tick, service)
        app.state.captain_task = asyncio.create_task(scheduler())

    @app.on_event('shutdown')
    async def end():
        task = getattr(app.state, 'captain_task', None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
