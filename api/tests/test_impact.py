import time
import pytest
from fastapi import HTTPException
import app as service
import impact
from tests.test_service import ctx, headers, offer


@pytest.fixture
def clock(monkeypatch):
    class Clock:
        now=time.time()
        def advance(self,seconds=60): self.now+=seconds
    timer=Clock()
    monkeypatch.setattr(impact.time,'time',lambda:timer.now)
    return timer


def create(client,baseline='solo_car',planned=True,kind='shared',seats=1):
    ride=offer(client,kind,capacity=3 if kind!='bike' else 1,already_planned=planned).json()['ride']
    response=client.post('/v1/bookings',headers=headers(),json={'ride_id':ride['id'],'seats':seats,'baseline':baseline})
    assert response.status_code==201,response.text
    booking=response.json()['booking']
    assert client.post('/v1/bookings/'+booking['id']+'/start',headers=headers('driver'),json={'pin':booking['pin']}).status_code==200
    return booking


def locate(client,booking,lat=18.5,lng=73.8,accuracy=5):
    data={'lat':lat,'lng':lng}
    if accuracy is not None: data['accuracy']=accuracy
    response=client.post('/v1/rides/'+booking['ride']['id']+'/location',headers=headers('driver'),json=data)
    assert response.status_code==200,response.text


def measured(client,booking,clock):
    clock.advance(1); locate(client,booking)
    clock.advance(60); locate(client,booking,18.505)


def finish(client,booking):
    response=client.post('/v1/bookings/'+booking['id']+'/complete',headers=headers('driver'),json={})
    assert response.status_code==200,response.text


def mine(client,user='rider'):
    response=client.get('/v1/impact/me',headers=headers(user))
    assert response.status_code==200,response.text
    return response.json()


def test_empty_impact_distinguishes_absence_from_measured_zero(ctx):
    assert ctx.get('/v1/impact/me').status_code==401
    me=mine(ctx)
    assert me['live']['co2_kg'] is None and me['lifetime']['vehicle_hours'] is None
    assert me['contributions']=={'rider_inr':0,'owner_inr':0,'total_inr':0}
    overall=ctx.get('/v1/impact/overall').json()
    assert overall['completed']['co2_kg']==0 and not overall['completed']['measurement_available']
    assert overall['heat']['reduction_c'] is None and overall['heat']['citywide_reduction_c'] is None
    assert overall['trees']['allocated_inr']==0
    assert 'phone' not in str(overall)


def test_live_then_completed_totals_do_not_multiply_seats_or_owner(ctx,clock):
    b=create(ctx,seats=3)
    measured(ctx,b,clock)
    expected=impact.haversine(18.5,73.8,18.505,73.8)/1000*impact.CO2_KG_PER_KM
    live=mine(ctx)['live']
    assert live['co2_kg']==pytest.approx(expected,abs=.0001)
    assert live['vehicle_hours']==pytest.approx(60/3600,abs=.00001)
    assert mine(ctx)['lifetime']['co2_kg'] is None
    finish(ctx,b)
    with service.db() as c:
        assert not c.execute('SELECT 1 FROM impact_anchors WHERE ride_id=?',(b['ride']['id'],)).fetchone()
    rider,owner=mine(ctx),mine(ctx,'driver')
    assert rider['live']['co2_kg'] is None
    assert rider['lifetime']['co2_kg']==owner['lifetime']['co2_kg']==live['co2_kg']
    assert owner['attribution']['owner_enabled']['co2_kg']==live['co2_kg']
    assert owner['attribution']['rider']['co2_kg'] is None
    assert ctx.get('/v1/impact/overall').json()['completed']['co2_kg']==live['co2_kg']
    # Completed aggregate is frozen even if a hook receives a later fix.
    clock.advance()
    with service.db(True) as c: impact.record_location(c,b['ride']['id'],18.51,73.8,5)
    assert mine(ctx)['lifetime']['co2_kg']==live['co2_kg']


@pytest.mark.parametrize('baseline,planned,kind',[('unknown',True,'shared'),('other',True,'shared'),('solo_car',False,'shared'),('solo_car',True,'cab'),('solo_car',True,'bike')])
def test_noneligible_journeys_never_claim_savings(ctx,clock,baseline,planned,kind):
    b=create(ctx,baseline,planned,kind)
    measured(ctx,b,clock)
    data=mine(ctx)['live']
    assert data['tracked_km']>0 and data['co2_kg'] is None
    assert data['eligible_bookings']==0
    finish(ctx,b)
    assert ctx.get('/v1/impact/overall').json()['completed']['co2_kg']==0


def test_first_fix_duplicates_backward_time_and_jitter_not_counted(ctx,clock):
    b=create(ctx); locate(ctx,b)
    assert mine(ctx)['live']['co2_kg'] is None
    locate(ctx,b,18.505) # same server time, ignore new coordinates
    clock.advance(-1); locate(ctx,b,18.51)
    clock.advance(61); locate(ctx,b,18.50001)
    assert mine(ctx)['live']['co2_kg'] is None
    clock.advance(); locate(ctx,b,18.505)
    assert mine(ctx)['live']['tracked_km']==pytest.approx(.555,abs=.003)


def test_gap_poor_accuracy_and_speed_outliers_break_continuity(ctx,clock):
    b=create(ctx); locate(ctx,b)
    clock.advance(121); locate(ctx,b,18.505)
    assert mine(ctx)['live']['co2_kg'] is None
    clock.advance(); locate(ctx,b,18.51,accuracy=80)
    clock.advance(); locate(ctx,b,18.515)
    assert mine(ctx)['live']['co2_kg'] is None
    clock.advance(1); locate(ctx,b,19.5) # implausible speed clears anchor
    clock.advance(); locate(ctx,b,18.52)
    assert mine(ctx)['live']['co2_kg'] is None
    clock.advance(); locate(ctx,b,18.525)
    assert mine(ctx)['live']['measured_eligible_bookings']==1
    assert mine(ctx)['live']['tracked_km']==pytest.approx(.556,abs=.002)


def test_missing_accuracy_and_stop_resume_do_not_bridge_unobserved_gaps(ctx,clock):
    b=create(ctx); locate(ctx,b,accuracy=None)
    clock.advance(); locate(ctx,b,18.505)
    assert mine(ctx)['live']['co2_kg'] is None
    assert ctx.delete('/v1/rides/'+b['ride']['id']+'/location',headers=headers('driver')).status_code==200
    clock.advance(); locate(ctx,b,18.51)
    assert mine(ctx)['live']['co2_kg'] is None
    clock.advance(); locate(ctx,b,18.515)
    assert mine(ctx)['live']['tracked_km']==pytest.approx(.556,abs=.002)


def test_cancellation_excluded_and_new_passenger_not_credited_earlier_segment(ctx,clock):
    b=create(ctx)
    response=ctx.post('/v1/bookings',headers=headers('other'),json={'ride_id':b['ride']['id'],'seats':1,'baseline':'solo_car'})
    # Existing offer becomes in_progress after first boarding, so create the
    # second reservation directly as pre-existing inventory for timing coverage.
    assert response.status_code==409
    with service.db(True) as c:
        c.execute("INSERT INTO bookings(id,rider_id,ride_id,seats,reserved,total,status,pin,created) VALUES('second','other',?,1,1,100,'confirmed','123456',?)",(b['ride']['id'],clock.now))
        impact.record_booking(c,'second','solo_car')
    locate(ctx,b)
    clock.advance(30)
    assert ctx.post('/v1/bookings/second/start',headers=headers('driver'),json={'pin':'123456'}).status_code==200
    clock.advance(30); locate(ctx,b,18.505)
    assert mine(ctx,'other')['live']['co2_kg'] is None
    clock.advance(); locate(ctx,b,18.51)
    assert mine(ctx,'other')['live']['co2_kg']>0
    with service.db(True) as c:
        c.execute("UPDATE bookings SET status='cancelled' WHERE id='second'")
    assert mine(ctx,'other')['live']['co2_kg'] is None
    assert mine(ctx,'other')['lifetime']['co2_kg'] is None


def test_default_fields_migration_unknown_no_retroactive_claim(ctx):
    ride=offer(ctx).json()['ride']
    b=ctx.post('/v1/bookings',headers=headers(),json={'ride_id':ride['id'],'seats':1}).json()['booking']
    with service.db(True) as c:
        impact.init(c)
        row=c.execute('SELECT * FROM impact_bookings WHERE booking_id=?',(b['id'],)).fetchone()
        assert row['baseline']=='unknown' and row['eligible']==0 and row['segments']==0


def allocation(c,b,**changes):
    values=dict(booking_id=b['id'],rider_inr='2.30',owner_inr='1.20',trees=1,reference='allocation-evidence-001',evidence_url='https://example.org/public/green-ledger-001')
    values.update(changes)
    impact.record_allocation(c,**values)


def test_tree_allocations_require_paid_completed_and_deduplicate(ctx,clock):
    b=create(ctx)
    with service.db(True) as c:
        with pytest.raises(HTTPException): allocation(c,b)
    finish(ctx,b)
    with service.db(True) as c:
        with pytest.raises(HTTPException): allocation(c,b)
        c.execute('UPDATE bookings SET paid=1 WHERE id=?',(b['id'],))
        allocation(c,b)
        with pytest.raises(HTTPException): allocation(c,b)
        with pytest.raises(HTTPException): allocation(c,b,rider_inr='99',reference='over-budget')
        with pytest.raises(HTTPException): allocation(c,b,rider_inr='0.001',reference='bad-fraction')
        assert c.execute("SELECT count(*) FROM audit WHERE action='record-tree-allocation'").fetchone()[0]==1
    assert mine(ctx)['contributions']=={'rider_inr':2.3,'owner_inr':0,'total_inr':2.3}
    assert mine(ctx,'driver')['contributions']=={'rider_inr':0,'owner_inr':1.2,'total_inr':1.2}
    public=ctx.get('/v1/impact/overall').json()
    assert public['trees']=={'allocated_inr':3.5,'trees_recorded':1,'evidence_records':1}
    assert 'allocation-evidence-001' not in str(public)
    assert ctx.post('/v1/impact/overall',headers=headers(),json={'trees':200}).status_code==405
    assert ctx.post('/v1/impact/allocations',headers=headers(),json={}).status_code==404


def study(c,**changes):
    values=dict(site='Pune test plot',before_at='2025-04-15T14:00:00+05:30',after_at='2025-05-15T14:00:00+05:30',site_before=35.,site_after=32.,control_before=34.,control_after=33.,samples=20,protocol='Matched shielded air sensors at two metres; comparable hour, season, wind and moisture conditions, with a nearby control plot.',reference='study-internal-001',evidence_url='https://example.org/public/study-001')
    values.update(changes)
    impact.record_heat_study(c,**values)


def test_heat_requires_evidence_and_does_not_claim_citywide_cooling(ctx):
    assert ctx.get('/v1/impact/overall').json()['heat']['reduction_c'] is None
    with service.db(True) as c:
        with pytest.raises(HTTPException): study(c,evidence_url='C:/private/study.pdf')
        with pytest.raises(HTTPException): study(c,after_at='2999-01-01T00:00:00Z')
        with pytest.raises(HTTPException): study(c,samples=1)
        with pytest.raises(HTTPException): study(c,site_after=float('nan'))
        study(c)
        with pytest.raises(HTTPException): study(c)
    heat=ctx.get('/v1/impact/overall').json()['heat']
    assert heat['reduction_c']==2.0 # (35-32)-(34-33), not raw 3 C
    assert heat['citywide_reduction_c'] is None
    assert 'not citywide' in heat['scope']
    assert heat['reference']=='https://example.org/public/study-001'
    assert 'study-internal-001' not in str(heat)


def test_heat_negative_result_is_not_hidden_or_clamped(ctx):
    with service.db(True) as c: study(c,site_after=36.)
    assert ctx.get('/v1/impact/overall').json()['heat']['reduction_c']==-2.0
