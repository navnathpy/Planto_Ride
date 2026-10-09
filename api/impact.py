"""Observed journey estimates and operator-evidenced environmental records.

Totals and one transient GPS anchor are kept, never a route history. Payment,
passenger input and tree counts are never converted into measured cooling.
"""
from __future__ import annotations
import argparse, json, math, sqlite3, time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from fastapi import Depends, HTTPException

CO2_KG_PER_KM = 0.249
MAX_GAP_SECONDS, MAX_ACCURACY_METRES, MAX_SPEED_KMH, MIN_SEGMENT_METRES = 120, 50, 160, 30
METHODOLOGY = {
    'version': '2026-10-08',
    'carbon_label': 'Estimated avoided tailpipe CO2',
    'co2_kg_per_km': CO2_KG_PER_KM,
    'carbon_basis': 'Illustrative US average petrol-car baseline; not an India fleet measurement.',
    'carbon_source': 'https://www.epa.gov/greenvehicles/greenhouse-gas-emissions-typical-passenger-vehicle',
    'eligibility': 'Shared rides only: the owner already planned this journey, and this booking party reports replacing one solo car.',
    'traffic_label': 'Estimated vehicle-hours avoided',
    'traffic_basis': 'Accepted tracked time replacing one solo car per booking; not measured time saved in congestion.',
    'coverage': 'Only accepted foreground GPS segments. Gaps, poor accuracy, first fixes and untracked distance are omitted.',
    'attribution': 'Rider savings and owner-enabled savings describe the same journeys. Overall totals count each booking once; never add personal totals together.',
    'trees_basis': 'Operator-recorded fund allocations with evidence; not 50% of fare and not a claim that allocated money has already been spent.',
    'heat_basis': 'Site-level before/after association adjusted by a matched control. No citywide cooling or causal attribution is inferred.',
    'heat_source': 'https://www.epa.gov/heatislands/measuring-heat-islands',
}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS impact_rides(ride_id TEXT PRIMARY KEY REFERENCES rides(id),already_planned INTEGER NOT NULL DEFAULT 0 CHECK(already_planned IN (0,1)));
CREATE TABLE IF NOT EXISTS impact_bookings(booking_id TEXT PRIMARY KEY REFERENCES bookings(id),baseline TEXT NOT NULL DEFAULT 'unknown' CHECK(baseline IN ('solo_car','other','unknown')),eligible INTEGER NOT NULL DEFAULT 0 CHECK(eligible IN (0,1)),started REAL,finished REAL,metres REAL NOT NULL DEFAULT 0,seconds REAL NOT NULL DEFAULT 0,segments INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS impact_anchors(ride_id TEXT PRIMARY KEY REFERENCES rides(id),lat REAL NOT NULL,lng REAL NOT NULL,accuracy REAL NOT NULL,observed REAL NOT NULL);
CREATE TABLE IF NOT EXISTS impact_allocations(id INTEGER PRIMARY KEY,booking_id TEXT NOT NULL REFERENCES bookings(id),rider_paise INTEGER NOT NULL CHECK(rider_paise>=0),owner_paise INTEGER NOT NULL CHECK(owner_paise>=0),trees INTEGER NOT NULL CHECK(trees>=0),reference TEXT UNIQUE NOT NULL,evidence_url TEXT NOT NULL,created REAL NOT NULL,CHECK(rider_paise+owner_paise>0));
CREATE TABLE IF NOT EXISTS impact_heat_studies(id INTEGER PRIMARY KEY,site TEXT NOT NULL,before_at TEXT NOT NULL,after_at TEXT NOT NULL,site_before REAL NOT NULL,site_after REAL NOT NULL,control_before REAL NOT NULL,control_after REAL NOT NULL,samples INTEGER NOT NULL,protocol TEXT NOT NULL,reference TEXT UNIQUE NOT NULL,evidence_url TEXT NOT NULL,created REAL NOT NULL);
'''

def require(ok, message, status=400):
    if not ok: raise HTTPException(status, message)

def init(c):
    # executescript would commit the caller's transaction.
    for statement in SCHEMA.split(';'):
        if statement.strip(): c.execute(statement)
    # Existing rides migrate as unmeasured/ineligible, never reconstructed.
    c.execute('INSERT OR IGNORE INTO impact_rides(ride_id) SELECT id FROM rides')
    c.execute('INSERT OR IGNORE INTO impact_bookings(booking_id) SELECT id FROM bookings')

def record_offer(c, ride_id, already_planned=False):
    c.execute('INSERT INTO impact_rides VALUES(?,?)', (ride_id, int(bool(already_planned))))

def record_booking(c, booking_id, baseline='unknown'):
    require(baseline in ('solo_car', 'other', 'unknown'), 'Invalid travel baseline.')
    row = c.execute('SELECT r.service,coalesce(i.already_planned,0) AS planned FROM bookings b JOIN rides r ON r.id=b.ride_id LEFT JOIN impact_rides i ON i.ride_id=r.id WHERE b.id=?', (booking_id,)).fetchone()
    require(row is not None, 'Booking not found.', 404)
    eligible = row['service'] == 'shared' and row['planned'] and baseline == 'solo_car'
    c.execute('INSERT INTO impact_bookings(booking_id,baseline,eligible) VALUES(?,?,?)', (booking_id, baseline, int(bool(eligible))))

def start_booking(c, booking_id):
    c.execute('UPDATE impact_bookings SET started=? WHERE booking_id=? AND started IS NULL AND finished IS NULL', (time.time(), booking_id))

def complete_booking(c, booking_id):
    c.execute('UPDATE impact_bookings SET finished=? WHERE booking_id=? AND finished IS NULL', (time.time(), booking_id))
    ride=c.execute('SELECT ride_id FROM bookings WHERE id=?',(booking_id,)).fetchone()
    if ride and not c.execute("SELECT 1 FROM bookings WHERE ride_id=? AND status='in_progress'",(ride['ride_id'],)).fetchone():
        stop_location(c,ride['ride_id'])

def stop_location(c, ride_id): c.execute('DELETE FROM impact_anchors WHERE ride_id=?', (ride_id,))

def haversine(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lng2-lng1)/2)**2
    return 6371008.8*2*math.atan2(math.sqrt(min(1, a)), math.sqrt(max(0, 1-a)))

def record_location(c, ride_id, lat, lng, accuracy=None):
    """Server-timed credible movement, only while on-trip; completed totals freeze."""
    now = time.time()
    if not all(isinstance(v, (int,float)) and math.isfinite(v) for v in (lat,lng,accuracy)) or not (-90<=lat<=90 and -180<=lng<=180 and 0<=accuracy<=MAX_ACCURACY_METRES):
        stop_location(c, ride_id); return
    active = c.execute("SELECT 1 FROM bookings b JOIN impact_bookings i ON i.booking_id=b.id WHERE b.ride_id=? AND b.status='in_progress' AND i.started IS NOT NULL AND i.finished IS NULL", (ride_id,)).fetchone()
    if not active: stop_location(c, ride_id); return
    previous = c.execute('SELECT * FROM impact_anchors WHERE ride_id=?', (ride_id,)).fetchone()
    # Duplicate/backward timestamps cannot move the anchor or manufacture time.
    if previous and now<=previous['observed']: return
    c.execute('INSERT OR REPLACE INTO impact_anchors VALUES(?,?,?,?,?)', (ride_id,lat,lng,accuracy,now))
    if not previous: return
    duration = now-previous['observed']
    if duration<=0 or duration>MAX_GAP_SECONDS: return
    metres = haversine(previous['lat'],previous['lng'],lat,lng)
    if metres<max(MIN_SEGMENT_METRES,accuracy+previous['accuracy']): return
    if metres/duration*3.6>MAX_SPEED_KMH:
        stop_location(c,ride_id); return
    # A rider starting after the anchor cannot receive an earlier segment.
    c.execute("UPDATE impact_bookings SET metres=metres+?,seconds=seconds+?,segments=segments+1 WHERE booking_id IN (SELECT id FROM bookings WHERE ride_id=? AND status='in_progress') AND finished IS NULL AND started<=?", (metres,duration,ride_id,previous['observed']))

def totals(c, status, user_id=None, attribution=None, empty_zero=False):
    where, params = 'b.status=?', [status]
    if user_id is not None:
        if attribution=='rider': where+=' AND b.rider_id=?'; params.append(user_id)
        elif attribution=='owner': where+=' AND r.driver_id=?'; params.append(user_id)
        else: where+=' AND (b.rider_id=? OR r.driver_id=?)'; params.extend([user_id,user_id])
    row=c.execute('SELECT count(*) AS bookings,coalesce(sum(i.metres),0) AS metres,coalesce(sum(i.eligible),0) AS eligible,coalesce(sum(CASE WHEN i.segments>0 THEN 1 ELSE 0 END),0) AS tracked,coalesce(sum(CASE WHEN i.eligible=1 AND i.segments>0 THEN 1 ELSE 0 END),0) AS measured,coalesce(sum(CASE WHEN i.eligible=1 THEN i.metres ELSE 0 END),0) AS eligible_metres,coalesce(sum(CASE WHEN i.eligible=1 THEN i.seconds ELSE 0 END),0) AS seconds FROM impact_bookings i JOIN bookings b ON b.id=i.booking_id JOIN rides r ON r.id=b.ride_id WHERE '+where,params).fetchone()
    measured=bool(row['measured'])
    return {'co2_kg':round(row['eligible_metres']/1000*CO2_KG_PER_KM,4) if measured or empty_zero else None,
            'vehicle_hours':round(row['seconds']/3600,5) if measured or empty_zero else None,
            'tracked_km':round(row['metres']/1000,3),'eligible_bookings':row['eligible'],
            'measured_eligible_bookings':row['measured'],'tracked_bookings':row['tracked'],
            'bookings':row['bookings'],'measurement_available':measured}

def personal(c,user):
    contributions=c.execute('SELECT coalesce(sum(CASE WHEN b.rider_id=? THEN a.rider_paise ELSE 0 END),0) AS rider,coalesce(sum(CASE WHEN r.driver_id=? THEN a.owner_paise ELSE 0 END),0) AS owner FROM impact_allocations a JOIN bookings b ON b.id=a.booking_id JOIN rides r ON r.id=b.ride_id',(user['id'],user['id'])).fetchone()
    created=c.execute('SELECT created FROM users WHERE id=?',(user['id'],)).fetchone()[0]
    return {'since':datetime.fromtimestamp(created,timezone.utc).isoformat(),
            'live':totals(c,'in_progress',user['id']),'lifetime':totals(c,'completed',user['id']),
            'attribution':{'rider':totals(c,'completed',user['id'],'rider'),'owner_enabled':totals(c,'completed',user['id'],'owner')},
            'contributions':{'rider_inr':contributions['rider']/100,'owner_inr':contributions['owner']/100,'total_inr':(contributions['rider']+contributions['owner'])/100},
            'methodology':METHODOLOGY}

def overall(c):
    trees=c.execute('SELECT coalesce(sum(rider_paise+owner_paise),0) AS paise,coalesce(sum(trees),0) AS trees,count(*) AS entries FROM impact_allocations').fetchone()
    study=c.execute('SELECT * FROM impact_heat_studies ORDER BY after_at DESC,id DESC LIMIT 1').fetchone()
    heat={'reduction_c':None,'scope':'Not yet measured','reference':None,'measured_at':None,'citywide_reduction_c':None}
    if study:
        heat.update({'reduction_c':round((study['site_before']-study['site_after'])-(study['control_before']-study['control_after']),3),
            'scope':'Site-level measured association at '+study['site']+'; not citywide or a causal attribution to Planto-Ride.',
            'reference':study['evidence_url'],'measured_at':study['after_at'],'before_at':study['before_at'],
            'samples_per_period':study['samples'],'protocol':study['protocol'],
            'readings_c':{k:study[k] for k in ('site_before','site_after','control_before','control_after')}})
    return {'completed':totals(c,'completed',empty_zero=True),
            'trees':{'allocated_inr':trees['paise']/100,'trees_recorded':trees['trees'],'evidence_records':trees['entries']},
            'heat':heat,'updated_at':datetime.now(timezone.utc).isoformat(),'methodology':METHODOLOGY}

def register(app,service):
    @app.get('/v1/impact/me')
    def my_impact(u=Depends(service.current)):
        with service.db() as c: return personal(c,u)
    @app.get('/v1/impact/overall')
    def all_impact():
        with service.db() as c: return overall(c)

def public_evidence(url):
    require(isinstance(url,str) and 8<=len(url)<=1000,'Use a public HTTPS evidence URL.')
    parsed=urlparse(url)
    require(parsed.scheme=='https' and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.fragment,'Use a public HTTPS evidence URL without credentials or fragments.')
    require(parsed.hostname not in ('localhost','127.0.0.1','::1') and '.' in parsed.hostname,'Use a public HTTPS evidence URL.')
    return url

def reference_text(reference):
    require(isinstance(reference,str) and 3<=len(reference.strip())<=200,'An evidence reference of 3–200 characters is required.')
    return reference.strip()

def paise(amount):
    try:
        value=Decimal(str(amount))
        require(value.is_finite() and 0<=value<=1000000 and value==value.quantize(Decimal('0.01')),'Use a nonnegative INR amount with at most two decimal places.')
        return int(value*100)
    except (InvalidOperation,ValueError,TypeError): raise HTTPException(400,'Invalid INR amount.')

def record_allocation(c,booking_id,rider_inr,owner_inr,trees,reference,evidence_url):
    """Operator-only local command; never expose as a passenger write endpoint."""
    rider,owner=paise(rider_inr),paise(owner_inr)
    require(rider+owner>0,'The allocation must be positive.')
    require(isinstance(trees,int) and not isinstance(trees,bool) and 0<=trees<=100000,'Invalid recorded tree count.')
    reference,evidence_url=reference_text(reference),public_evidence(evidence_url)
    booking=c.execute('SELECT * FROM bookings WHERE id=?',(booking_id,)).fetchone()
    require(booking is not None,'Booking not found.',404)
    require(booking['status']=='completed' and booking['paid'],'Only completed, paid bookings may receive an allocation.',409)
    allocated=c.execute('SELECT coalesce(sum(rider_paise+owner_paise),0) FROM impact_allocations WHERE booking_id=?',(booking_id,)).fetchone()[0]
    require(allocated+rider+owner<=booking['total']*100,'Recorded allocations cannot exceed the paid booking amount.',409)
    require(not c.execute('SELECT 1 FROM impact_allocations WHERE reference=?',(reference,)).fetchone(),'This evidence reference is already recorded.',409)
    c.execute('INSERT INTO impact_allocations(booking_id,rider_paise,owner_paise,trees,reference,evidence_url,created) VALUES(?,?,?,?,?,?,?)',(booking_id,rider,owner,trees,reference,evidence_url,time.time()))
    c.execute('INSERT INTO audit(action,target,reference,created) VALUES(?,?,?,?)',('record-tree-allocation',booking_id,reference,time.time()))

def parse_time(value):
    try:
        timestamp=datetime.fromisoformat(value.replace('Z','+00:00'))
        require(timestamp.tzinfo is not None,'Measurement dates must include a time zone.')
        return timestamp.astimezone(timezone.utc)
    except (ValueError,AttributeError): raise HTTPException(400,'Use an ISO measurement date with a time zone.')

def record_heat_study(c,site,before_at,after_at,site_before,site_after,control_before,control_after,samples,protocol,reference,evidence_url):
    reference,evidence_url=reference_text(reference),public_evidence(evidence_url)
    require(isinstance(site,str) and 3<=len(site.strip())<=160,'A public study site name is required.')
    require(isinstance(protocol,str) and 30<=len(protocol.strip())<=2000,'Document matching, sensor protocol, locations and weather controls.')
    require(isinstance(samples,int) and not isinstance(samples,bool) and 2<=samples<=1000000,'Record at least two matched samples per period.')
    before,after=parse_time(before_at),parse_time(after_at)
    require(before<after<=datetime.now(timezone.utc),'Before/after measurement dates must be ordered and in the past.')
    values=(site_before,site_after,control_before,control_after)
    require(all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and -60<=v<=80 for v in values),'Provide four valid measured mean air temperatures in Celsius.')
    require(not c.execute('SELECT 1 FROM impact_heat_studies WHERE reference=?',(reference,)).fetchone(),'This study reference is already recorded.',409)
    c.execute('INSERT INTO impact_heat_studies(site,before_at,after_at,site_before,site_after,control_before,control_after,samples,protocol,reference,evidence_url,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(site.strip(),before.isoformat(),after.isoformat(),*values,samples,protocol.strip(),reference,evidence_url,time.time()))
    c.execute('INSERT INTO audit(action,target,reference,created) VALUES(?,?,?,?)',('record-heat-study',site.strip(),reference,time.time()))

def main():
    parser=argparse.ArgumentParser(description='Planto-Ride evidence ledger. Restricted server-operator access only.')
    sub=parser.add_subparsers(dest='command',required=True)
    allocation=sub.add_parser('record-tree-allocation')
    for name in ('booking-id','rider-inr','owner-inr','reference','evidence-url'): allocation.add_argument('--'+name,required=True)
    allocation.add_argument('--trees',type=int,required=True)
    heat=sub.add_parser('record-heat-study')
    for name in ('site','before-at','after-at','protocol','reference','evidence-url'): heat.add_argument('--'+name,required=True)
    for name in ('site-before','site-after','control-before','control-after'): heat.add_argument('--'+name,type=float,required=True)
    heat.add_argument('--samples',type=int,required=True)
    arguments=vars(parser.parse_args()); command=arguments.pop('command')
    import app as service
    service.init()
    try:
        with service.db(True) as c:
            init(c)
            (record_allocation if command=='record-tree-allocation' else record_heat_study)(c,**arguments)
        print(json.dumps({'recorded':True,'command':command}))
    except HTTPException as error: parser.exit(1,error.detail+'\n')
    except sqlite3.IntegrityError: parser.exit(1,'Record conflicts with existing ledger evidence. No change saved.\n')

if __name__=='__main__': main()
