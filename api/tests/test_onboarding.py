import base64,io,time
import pytest
from PIL import Image
from cryptography.fernet import Fernet
import app as service
from tests.test_service import ctx,headers
from tests.test_admin import operator

@pytest.fixture
def submission(monkeypatch):
    monkeypatch.setenv('DOCUMENT_ENCRYPTION_KEY',Fernet.generate_key().decode())
    out=io.BytesIO();Image.new('RGB',(20,20),'white').save(out,'PNG')
    photo=base64.b64encode(out.getvalue()).decode()
    return dict(plate='mh12 zz1234',vehicle='Test car',services=['shared','cab'],licence_photo=photo,rc_photo=photo,consent=True)

def submit(ctx,data,user='driver'):
    r=ctx.post('/v1/vehicle-applications',headers=headers(user),json=data)
    assert r.status_code==201,r.text
    return r.json()['id']

def test_private_queue_and_approval(ctx,operator,submission):
    id=submit(ctx,submission)
    assert ctx.post('/v1/vehicle-applications',headers=headers('driver'),json=submission).status_code==409
    rows=ctx.get('/v1/operator/records/applications',headers=operator).json()['records']
    assert rows[0]['id']==id and rows[0]['status']=='pending'
    assert 'ciphertext' not in str(rows)
    assert ctx.get('/v1/vehicle-applications',headers=headers()).json()['applications']==[]
    url='/v1/operator/vehicle-applications/'+id
    assert ctx.get(url+'/documents',headers=headers('driver')).status_code==401
    docs=ctx.get(url+'/documents',headers=operator)
    assert docs.status_code==200 and docs.headers['cache-control']=='no-store'
    assert set(docs.json()['images'])=={'licence','rc'}
    with service.db() as c:
        assert submission['licence_photo'] not in c.execute('SELECT ciphertext FROM vehicle_documents WHERE application_id=?',(id,)).fetchone()[0]
        assert not c.execute('SELECT 1 FROM vehicles WHERE plate=?',('MH12ZZ1234',)).fetchone()
    payload=dict(decision='approved',reference='checked-001',note='Eligibility checked',documents_reviewed=False)
    assert ctx.post(url+'/review',headers=operator,json=payload).status_code==400
    payload['documents_reviewed']=True
    assert ctx.post(url+'/review',headers=operator,json=payload).status_code==200
    assert ctx.post(url+'/review',headers=operator,json=payload).status_code==409
    with service.db() as c:assert c.execute('SELECT 1 FROM vehicles WHERE plate=?',('MH12ZZ1234',)).fetchone()
    assert ctx.get('/v1/vehicle-applications',headers=headers('driver')).json()['applications'][0]['government_status']=='not_connected'

def test_pending_driver_and_withdrawal(ctx,operator,submission):
    id=submit(ctx,submission,'pending')
    url='/v1/operator/vehicle-applications/'+id+'/review'
    p=dict(decision='approved',reference='checked-001',note='Eligibility checked',documents_reviewed=True)
    assert ctx.post(url,headers=operator,json=p).status_code==409
    assert ctx.post(url,headers=operator,json={**p,'decision':'rejected'}).status_code==200
    id=submit(ctx,submission)
    url='/v1/vehicle-applications/'+id+'/withdraw'
    assert ctx.post(url,headers=headers(),json={}).status_code==404
    assert ctx.post(url,headers=headers('driver'),json={}).status_code==200
    assert ctx.get('/v1/operator/vehicle-applications/'+id+'/documents',headers=operator).status_code==404

def test_expiry_and_validation(ctx,operator,submission,monkeypatch):
    id=submit(ctx,submission)
    with service.db(True) as c:c.execute('UPDATE vehicle_documents SET expires=?',(time.time()-1,))
    assert ctx.get('/v1/operator/vehicle-applications/'+id+'/documents',headers=operator).status_code==404
    p=dict(decision='approved',reference='checked-001',note='Eligibility checked',documents_reviewed=True)
    assert ctx.post('/v1/operator/vehicle-applications/'+id+'/review',headers=operator,json=p).status_code==409
    url='/v1/vehicle-applications'
    assert ctx.post(url,headers=headers(),json=submission).status_code==403
    for change in [dict(consent=False),dict(services=['bike','cab']),dict(licence_photo='a'*24)]:
        assert ctx.post(url,headers=headers('driver'),json={**submission,**change}).status_code==400
    monkeypatch.delenv('DOCUMENT_ENCRYPTION_KEY')
    assert ctx.post(url,headers=headers('driver'),json=submission).status_code==503
    assert ctx.post(url,headers=headers('driver'),content=b'x'*(6*1024*1024+1)).status_code==413
    assert ctx.post('/v1/auth/login',content=b'x'*17000).status_code==413


def test_old_identity_photo_does_not_count_as_vehicle_rc(ctx,operator,submission):
    id=submit(ctx,submission)
    with service.db(True) as c:c.execute("UPDATE vehicle_documents SET kind='aadhaar' WHERE application_id=? AND kind='rc'",(id,))
    url='/v1/operator/vehicle-applications/'+id
    assert set(ctx.get(url+'/documents',headers=operator).json()['images'])=={'licence'}
    p=dict(decision='approved',reference='checked-001',note='Eligibility checked',documents_reviewed=True)
    assert ctx.post(url+'/review',headers=operator,json=p).status_code==409
    old={**submission,'aadhaar_photo':submission['rc_photo'],'masked_aadhaar':True}
    old.pop('rc_photo')
    assert ctx.post('/v1/vehicle-applications',headers=headers('driver'),json=old).status_code==422
