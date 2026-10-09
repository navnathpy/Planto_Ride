"""Captain integration tests use isolated SQLite files; no external messages."""
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
import app as service
import captain

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(service, 'DB', str(tmp_path / 'captain.sqlite3'))
    monkeypatch.setattr(captain, 'POLL_INTERVAL', 0.02)
    service.init()
    with service.db(True) as c:
        for index, role in enumerate(('driver', 'rider', 'other')):
            c.execute('INSERT INTO users(id,name,phone,password,role,gender,approved,created) VALUES(?,?,?,?,?,?,?,?)',
                      (role, role.title(), '+91900000000' + str(index), 'not-used', 'driver' if role == 'driver' else 'rider', 'woman', 1, time.time()))
            c.execute('INSERT INTO sessions VALUES(?,?,?)', (service.digest(role + '-token'), role, time.time() + 3600))
        c.execute('INSERT INTO vehicles VALUES(?,?,?,?)', ('driver', 'MH12AB1234', 'White car', 'shared'))
    with TestClient(service.app) as c:
        yield c


def auth(user='rider'):
    return {'Authorization': 'Bearer ' + user + '-token'}


def book(client):
    offered = client.post('/v1/rides', headers=auth('driver'), json={
        'origin': 'Baner', 'destination': 'Hinjawadi', 'service': 'shared', 'capacity': 3,
        'price': 120, 'vehicle': 'White car', 'plate': 'MH12AB1234',
        'departure': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
    assert offered.status_code == 201, offered.text
    reserved = client.post('/v1/bookings', headers=auth(), json={'ride_id': offered.json()['ride']['id'], 'seats': 1})
    assert reserved.status_code == 201, reserved.text
    return reserved.json()['booking']


def chat(client, b, user='rider'):
    return client.get('/v1/bookings/' + b['id'] + '/captain', headers=auth(user))


def start(client, b):
    result = client.post('/v1/bookings/' + b['id'] + '/start', headers=auth('driver'), json={'pin': b['pin']})
    assert result.status_code == 200, result.text
    return chat(client, b).json()


def send(client, b, action=None, check=None, request=None, text='Trip status'):
    payload = {'text': text, 'request_id': request or str(uuid4())}
    if action:
        payload['action'] = action
    if check:
        payload['checkin_id'] = check
    return client.post('/v1/bookings/' + b['id'] + '/captain/messages', headers=auth(), json=payload)


def test_assignment_is_persistent_private_and_does_not_leak_trip_secrets(client):
    b = book(client)
    first = chat(client, b)
    assert first.status_code == 200
    state = first.json()
    assert state['captain']['automated'] is True and state['delivery'] == 'foreground'
    assert state['checkin'] is None and state['next_checkin_at'] is None
    assert state['captain'] == chat(client, b).json()['captain']
    for other in ('other', 'driver'):
        assert chat(client, b, other).status_code == 404
        assert client.post('/v1/bookings/' + b['id'] + '/captain/messages', headers=auth(other),
                           json={'text': 'status', 'request_id': str(uuid4())}).status_code == 404
    assert client.get('/v1/bookings/' + b['id'] + '/captain').status_code == 401
    for question in ('trip status', 'driver details', 'payment status', 'carbon impact', 'tell me a joke'):
        reply = send(client, b, text=question)
        assert reply.status_code == 200
        assert b['pin'] not in reply.text and 'rider-token' not in reply.text and '+91900000000' not in reply.text
    with service.db() as c:
        assert c.execute('SELECT count(*) FROM captains WHERE booking_id=?', (b['id'],)).fetchone()[0] == 1


def test_checkins_repeat_after_response_no_backlog_and_stop_on_completion(client, monkeypatch):
    b = book(client)
    first = start(client, b)
    first_check = first['checkin']['id']
    assert first['checkin']['status'] == 'awaiting'
    captain.tick(service, first['next_checkin_at'] + 3600)
    assert chat(client, b).json()['checkin']['id'] == first_check
    assert client.get('/v1/captain/checkins', headers=auth('driver')).json()['checkins'] == []
    assert client.get('/v1/captain/checkins', headers=auth('other')).json()['checkins'] == []
    pending = client.get('/v1/captain/checkins', headers=auth()).json()['checkins']
    assert len(pending) == 1 and pending[0]['checkin_id'] == first_check
    assert send(client, b, 'all_good', first_check, text='All good').status_code == 200
    clock = time.time() + 301
    monkeypatch.setattr(captain, 'time', SimpleNamespace(time=lambda: clock))
    captain.tick(service, clock)
    second = chat(client, b).json()
    assert second['checkin']['id'] != first_check and second['checkin']['status'] == 'awaiting'
    captain.tick(service, clock + 300)
    with service.db() as c:
        assert c.execute('SELECT count(*) FROM captain_checkins WHERE booking_id=?', (b['id'],)).fetchone()[0] == 2
    completed = client.post('/v1/bookings/' + b['id'] + '/complete', headers=auth('driver'), json={})
    assert completed.status_code == 200
    captain.tick(service, clock + 3600)
    final = chat(client, b).json()
    assert final['checkin'] is None and final['next_checkin_at'] is None
    assert client.get('/v1/captain/checkins', headers=auth()).json()['checkins'] == []
    with service.db() as c:
        assert c.execute('SELECT count(*) FROM captain_checkins WHERE booking_id=?', (b['id'],)).fetchone()[0] == 2


def test_help_is_idempotent_records_incident_without_claiming_external_dispatch(client):
    b = book(client)
    check = start(client, b)['checkin']['id']
    request_id = str(uuid4())
    first = send(client, b, 'unsafe', check, request_id, 'I feel unsafe')
    assert first.status_code == 200
    state = first.json()
    assert state['checkin']['status'] == 'unsafe' and state['concern_reported']
    assert 'No one has been automatically contacted' in state['messages'][-1]['text']
    assert 'manual operator review' in state['messages'][-1]['text']
    repeat = send(client, b, 'unsafe', check, request_id, 'I feel unsafe')
    assert repeat.status_code == 200 and len(repeat.json()['messages']) == len(state['messages'])
    assert send(client, b, 'unsafe', check, request_id, 'Different message').status_code == 409
    with service.db() as c:
        assert c.execute('SELECT count(*) FROM incidents WHERE booking_id=?', (b['id'],)).fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM captain_messages WHERE booking_id=? AND role='rider'", (b['id'],)).fetchone()[0] == 1


def test_invalid_old_or_unrelated_checkin_cannot_be_answered(client):
    b = book(client)
    assert send(client, b, 'all_good', text='All good').status_code == 409
    check = start(client, b)['checkin']['id']
    assert send(client, b, 'all_good', 'check_future', text='All good').status_code == 409
    assert send(client, b, 'status', check, text='Status').status_code == 400
    assert send(client, b, 'all_good', check, text='All good').status_code == 200
    assert send(client, b, 'all_good', check, text='All good').status_code == 409
    assert send(client, b, text='I need help').status_code == 200
    assert chat(client, b).json()['concern_reported'] is True


def test_later_all_good_does_not_erase_earlier_concern(client, monkeypatch):
    b = book(client)
    check = start(client, b)['checkin']['id']
    assert send(client, b, 'need_help', check, text='Need help').status_code == 200
    clock = time.time() + 301
    monkeypatch.setattr(captain, 'time', SimpleNamespace(time=lambda: clock))
    second = chat(client, b).json()['checkin']['id']
    result = send(client, b, 'all_good', second, text='All good').json()
    assert result['concern_reported'] is True and result['checkin']['status'] == 'all_good'
    assert 'earlier concern remains recorded' in result['messages'][-1]['text']


def test_message_limits_history_bounds_and_request_validation(client):
    b = book(client)
    assert send(client, b, text='x' * 1001).status_code == 422
    assert send(client, b, request='not-a-uuid').status_code == 422
    for _ in range(12):
        assert send(client, b, text='status').status_code == 200
    assert send(client, b, text='status').status_code == 429
    with service.db(True) as c:
        for i in range(60):
            captain._message(c, b['id'], 'captain', 'Historical message ' + str(i), time.time())
    history = chat(client, b).json()['messages']
    assert len(history) == 50 and history[-1]['text'] == 'Historical message 59'


def test_background_scheduler_persists_prompt_without_client_polling(client):
    b = book(client)
    check = start(client, b)['checkin']['id']
    assert send(client, b, 'all_good', check, text='All good').status_code == 200
    with service.db(True) as c:
        c.execute('UPDATE captains SET next_checkin=? WHERE booking_id=?', (time.time() - 1, b['id']))
    deadline = time.monotonic() + 2
    count = 0
    while time.monotonic() < deadline:
        with service.db() as c:
            count = c.execute('SELECT count(*) FROM captain_checkins WHERE booking_id=?', (b['id'],)).fetchone()[0]
        if count == 2:
            break
        time.sleep(0.025)
    assert count == 2


def test_cancelled_trip_has_no_checkins_and_new_booking_gets_own_captain(client):
    b = book(client)
    first = chat(client, b).json()['captain']['id']
    assert client.post('/v1/bookings/' + b['id'] + '/cancel', headers=auth(), json={}).status_code == 200
    captain.tick(service, time.time() + 3600)
    assert chat(client, b).json()['checkin'] is None
    second = book(client)
    assert chat(client, second).json()['captain']['id'] != first
