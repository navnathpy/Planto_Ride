import time
import pytest
import app as service
from tests.test_service import ctx, headers, offer, reserve

@pytest.fixture
def operator(ctx,monkeypatch):
    monkeypatch.setenv('OPERATOR_EMAIL','owner@example.test')
    monkeypatch.setenv('OPERATOR_PASSWORD_HASH',service.password_hash('only-a-test-password'))
    r=ctx.post('/v1/operator/login',json={'email':'owner@example.test','password':'only-a-test-password'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_passengers_cannot_access_any_operator_controls(ctx,operator):
    for kind in ['users','vehicles','rides','bookings','incidents','audit','allocations','heat']:
        assert ctx.get('/v1/operator/records/'+kind,headers=headers()).status_code==401
    actions=[('PATCH','/users/rider',{'role':'driver','approved':True,'reference':'test-record'}),
             ('POST','/vehicles',{'driver_id':'driver','plate':'MH12TEST123','vehicle':'Car','services':['cab'],'reference':'test-record'}),
             ('POST','/rides/any/close',{'reference':'test-record'}),
             ('PATCH','/incidents/any',{'status':'resolved','note':'reviewed','reference':'test-record'}),
             ('POST','/allocations',{'booking_id':'any','rider_inr':'1','owner_inr':'0','trees':0,'evidence_url':'https://example.org/evidence','reference':'test-record'})]
    for method,path,data in actions:
        assert ctx.request(method,'/v1/operator'+path,headers=headers(),json=data).status_code==401
    for kind in ['users','vehicles','rides','bookings','incidents','audit','allocations','heat']:
        r=ctx.get('/v1/operator/records/'+kind,headers=operator)
        assert r.status_code==200,r.text
        for row in r.json()['records']:
            assert not {'password','pin','hash','request_json'} & set(row)

def test_operator_login_logout_rotation_and_expiry(ctx,operator,monkeypatch):
    assert ctx.post('/v1/operator/login',json={'email':'owner@example.test','password':'wrong'}).status_code==401
    # An operator token cannot impersonate a passenger.
    assert ctx.get('/v1/me',headers=operator).status_code==401
    monkeypatch.setenv('OPERATOR_PASSWORD_HASH',service.password_hash('rotated-test-password'))
    assert ctx.get('/v1/operator/records/users',headers=operator).status_code==401
    r=ctx.post('/v1/operator/login',json={'email':'owner@example.test','password':'rotated-test-password'})
    h={'Authorization':'Bearer '+r.json()['token']}
    assert ctx.delete('/v1/operator/session',headers=h).status_code==200
    assert ctx.get('/v1/operator/records/users',headers=h).status_code==401
    r=ctx.post('/v1/operator/login',json={'email':'owner@example.test','password':'rotated-test-password'})
    h={'Authorization':'Bearer '+r.json()['token']}
    with service.db(True) as c:c.execute('UPDATE operator_sessions SET expires=?',(time.time()-1,))
    assert ctx.get('/v1/operator/records/users',headers=h).status_code==401

def test_account_correction_vehicle_approval_and_suspension(ctx,operator):
    vehicle={'driver_id':'rider','plate':'MH12TEST123','vehicle':'Test car','services':['shared','cab'],'reference':'vehicle-checked'}
    assert ctx.post('/v1/operator/vehicles',headers=operator,json=vehicle).status_code==400
    account={'role':'driver','approved':True,'woman_verified':False,'reference':'identity-checked'}
    assert ctx.patch('/v1/operator/users/rider',headers=operator,json=account).status_code==200
    assert ctx.get('/v1/me',headers=headers()).status_code==401
    assert ctx.post('/v1/operator/vehicles',headers=operator,json=vehicle).status_code==200
    assert ctx.post('/v1/operator/vehicles/revoke',headers=operator,json=vehicle).status_code==200
    assert ctx.patch('/v1/operator/users/man',headers=operator,json={**account,'woman_verified':True}).status_code==400
    assert ctx.patch('/v1/operator/users/driver',headers=operator,json={**account,'approved':False}).status_code==200
    assert ctx.get('/v1/me',headers=headers('driver')).status_code==401
    with service.db() as c:
        assert c.execute("SELECT count(*) FROM audit WHERE action LIKE 'operator:%'").fetchone()[0]>=5

def test_close_offer_preserves_booking_and_active_role_change_rejected(ctx,operator):
    ride=offer(ctx).json()['ride']['id']
    b=reserve(ctx,ride).json()['booking']['id']
    assert ctx.patch('/v1/operator/users/driver',headers=operator,json={'role':'rider','approved':True,'reference':'role-check'}).status_code==409
    assert ctx.post('/v1/operator/rides/'+ride+'/close',headers=operator,json={'reference':'offer-check'}).status_code==200
    with service.db() as c:
        assert c.execute('SELECT status FROM bookings WHERE id=?',(b,)).fetchone()[0]=='confirmed'

def test_report_review_and_evidence_validation(ctx,operator):
    r=ctx.post('/v1/incidents',headers=headers(),json={'kind':'safety','detail':'Test concern for review'})
    id=r.json()['id']
    assert ctx.patch('/v1/operator/incidents/'+id,headers=operator,json={'status':'reviewing','note':'Owner investigating','reference':'case-001'}).status_code==200
    result=ctx.get('/v1/operator/records/incidents',headers=operator).json()['records'][0]
    assert result['review_status']=='reviewing'
    assert ctx.post('/v1/operator/allocations',headers=operator,json={'booking_id':'missing','rider_inr':'1','owner_inr':'0','trees':0,'evidence_url':'https://example.org/evidence','reference':'evidence-001'}).status_code==404
    assert ctx.post('/v1/operator/heat',headers=operator,json={'site':'Pune test','before_at':'2020-01-01T00:00:00Z','after_at':'2021-01-01T00:00:00Z','site_before':30,'site_after':29,'control_before':30,'control_after':30,'samples':3,'protocol':'Matched calibrated sensors and weather controls documented.','reference':'study-001','evidence_url':'https://example.org/evidence'}).status_code==200

def test_operator_login_rate_limit(ctx,operator):
    for _ in range(9):
        assert ctx.post('/v1/operator/login',json={'email':'owner@example.test','password':'wrong'}).status_code==401
    assert ctx.post('/v1/operator/login',json={'email':'different@example.test','password':'wrong'}).status_code==429
