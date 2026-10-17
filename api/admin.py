"""Private operator controls. No public registration or passenger-role elevation."""
import hmac
import os
import secrets
import time
from typing import Literal
from fastapi import Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field
import impact
import storage
import onboarding

SCHEMA = '''
CREATE TABLE IF NOT EXISTS operator_sessions(hash TEXT PRIMARY KEY,credential_version TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS incident_reviews(incident_id TEXT PRIMARY KEY REFERENCES incidents(id),status TEXT NOT NULL,note TEXT NOT NULL,updated REAL NOT NULL);
'''

def init(c): storage.install(c, SCHEMA)

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True,allow_inf_nan=False)
class Login(Input):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=1,max_length=128)
class Evidence(Input):
    reference:str=Field(min_length=3,max_length=200)
class Account(Evidence):
    role:Literal['rider','driver']
    approved:bool
    woman_verified:bool=False
class Vehicle(Evidence):
    driver_id:str
    plate:str=Field(pattern=r'^[A-Z0-9 -]{6,16}$')
    vehicle:str=Field(min_length=2,max_length=80)
    services:list[Literal['shared','cab','bike']]=Field(min_length=1,max_length=3)
class Review(Evidence):
    status:Literal['open','reviewing','resolved']
    note:str=Field(min_length=3,max_length=2000)
class Allocation(Evidence):
    booking_id:str
    rider_inr:str=Field(max_length=20)
    owner_inr:str=Field(max_length=20)
    trees:int=Field(ge=0,le=100000,strict=True)
    evidence_url:str=Field(max_length=1000)
class Heat(Evidence):
    site:str=Field(min_length=3,max_length=160)
    before_at:str
    after_at:str
    site_before:float
    site_after:float
    control_before:float
    control_after:float
    samples:int=Field(ge=2,le=1000000,strict=True)
    protocol:str=Field(min_length=30,max_length=2000)
    evidence_url:str=Field(max_length=1000)

def register(app,s):
    def settings():
        email=os.getenv('OPERATOR_EMAIL','').strip().lower()
        encoded=os.getenv('OPERATOR_PASSWORD_HASH','')
        s.fail(bool(email and encoded),'Operator access is not configured.',503)
        return email,encoded,s.digest(email+'|'+encoded)

    def current(authorization:str=Header(default='')):
        _,_,version=settings()
        s.fail(authorization.startswith('Bearer '),'Operator sign-in required.',401)
        with s.db() as c:
            row=c.execute('SELECT credential_version FROM operator_sessions WHERE hash=? AND expires>?',(s.digest(authorization[7:]),time.time())).fetchone()
        s.fail(row is not None and hmac.compare_digest(row['credential_version'],version),'Operator session expired. Sign in again.',401)
        return True

    def audit(c,action,target,reference):
        c.execute('INSERT INTO audit(action,target,reference,created) VALUES(?,?,?,?)',('operator:'+action,target,reference,time.time()))

    onboarding.register(app,s,current)

    @app.post('/v1/operator/login')
    def login(data:Login,request:Request):
        s.throttle('operator-login',10,900)
        email,encoded,version=settings()
        try: candidate=s.password_hash(data.password,encoded.split(':')[0])
        except ValueError: s.fail(False,'Operator access is not configured.',503)
        s.fail(hmac.compare_digest(candidate,encoded) and hmac.compare_digest(data.email.lower(),email),'Email or password is incorrect.',401)
        token=secrets.token_urlsafe(32)
        with s.db(True) as c:
            c.execute('DELETE FROM operator_sessions WHERE expires<?',(time.time(),))
            c.execute('INSERT INTO operator_sessions VALUES(?,?,?)',(s.digest(token),version,time.time()+3600))
            audit(c,'login','operator','password-login')
        return {'token':token,'expires_in':3600}

    @app.delete('/v1/operator/session')
    def logout(authorized=Depends(current),authorization:str=Header()):
        with s.db(True) as c:c.execute('DELETE FROM operator_sessions WHERE hash=?',(s.digest(authorization[7:]),))
        return {'signed_out':True}

    @app.get('/v1/operator/records/{kind}')
    def records(kind:Literal['applications','users','vehicles','rides','bookings','incidents','audit','allocations','heat'],q:str='',offset:int=0,authorized=Depends(current)):
        s.fail(0<=offset<=1000000 and len(q)<=100,'Invalid search or page.')
        queries={
            'applications':"SELECT a.id,u.name,u.phone,a.driver_id,a.plate,a.vehicle,a.services,a.status,a.government_status,a.review_note,a.created FROM vehicle_applications a JOIN users u ON u.id=a.driver_id WHERE a.plate LIKE ? OR u.phone LIKE ? ORDER BY CASE WHEN a.status='pending' THEN 0 ELSE 1 END,a.created DESC,a.id",
            'users':"SELECT id,name,phone,role,gender,approved,woman_verified,created FROM users WHERE name LIKE ? OR phone LIKE ? ORDER BY created DESC,id",
            'vehicles':"SELECT v.*,u.name,u.phone FROM vehicles v JOIN users u ON u.id=v.driver_id WHERE v.plate LIKE ? OR u.phone LIKE ? ORDER BY v.driver_id,v.plate",
            'rides':"SELECT id,driver_id,origin,destination,departure,service,plate,status,capacity,available FROM rides WHERE id LIKE ? OR plate LIKE ? ORDER BY created DESC,id",
            'bookings':"SELECT id,rider_id,ride_id,total,status,paid,created FROM bookings WHERE id LIKE ? OR ride_id LIKE ? ORDER BY created DESC,id",
            'incidents':"SELECT i.*,coalesce(r.status,'open') AS review_status,coalesce(r.note,'') AS review_note FROM incidents i LEFT JOIN incident_reviews r ON r.incident_id=i.id WHERE i.id LIKE ? OR i.user_id LIKE ? ORDER BY i.created DESC,i.id",
            'audit':"SELECT * FROM audit WHERE target LIKE ? OR reference LIKE ? ORDER BY created DESC,id",
            'allocations':"SELECT * FROM impact_allocations WHERE booking_id LIKE ? OR reference LIKE ? ORDER BY created DESC,id",
            'heat':"SELECT * FROM impact_heat_studies WHERE site LIKE ? OR reference LIKE ? ORDER BY created DESC,id"}
        with s.db() as c: rows=c.execute(queries[kind]+' LIMIT 51 OFFSET ?',('%'+q+'%','%'+q+'%',offset)).fetchall()
        return {'records':[dict(r) for r in rows[:50]],'has_more':len(rows)>50}

    @app.patch('/v1/operator/users/{id}')
    def account(id:str,data:Account,authorized=Depends(current)):
        with s.db(True) as c:
            u=c.execute('SELECT * FROM users WHERE id=?',(id,)).fetchone()
            s.fail(u is not None,'Account not found.',404)
            s.fail(not data.woman_verified or (u['gender']=='woman' and data.approved),'Ladies verification requires an approved account registered as a woman.')
            if u['role']!=data.role:
                active=c.execute("SELECT 1 FROM bookings b JOIN rides r ON r.id=b.ride_id WHERE b.status IN ('confirmed','in_progress') AND (b.rider_id=? OR r.driver_id=?)",(id,id)).fetchone()
                s.fail(not active,'Finish or cancel active bookings before changing account type.',409)
                c.execute("UPDATE rides SET status='closed' WHERE driver_id=? AND status='open'",(id,))
            c.execute('UPDATE users SET role=?,approved=?,woman_verified=? WHERE id=?',(data.role,int(data.approved),int(data.woman_verified),id))
            # Revoke rider/driver sessions after every privilege change.
            c.execute('DELETE FROM sessions WHERE user_id=?',(id,))
            if not data.approved:c.execute("UPDATE rides SET status='closed' WHERE driver_id=? AND status='open'",(id,))
            audit(c,'account-'+data.role+('-approved' if data.approved else '-suspended')+('-ladies' if data.woman_verified else ''),id,data.reference)
        return {'updated':True}

    @app.post('/v1/operator/vehicles')
    def vehicle(data:Vehicle,authorized=Depends(current)):
        with s.db(True) as c:
            u=c.execute('SELECT role,approved FROM users WHERE id=?',(data.driver_id,)).fetchone()
            s.fail(u is not None and u['role']=='driver','Select a Driver account, not a Rider account.')
            s.fail(u['approved'],'Approve the driver account first.')
            s.fail(not ('bike' in data.services and len(data.services)>1),'Approve a bike separately from a car.')
            c.execute('INSERT INTO vehicles VALUES(?,?,?,?) ON CONFLICT(driver_id,plate) DO UPDATE SET vehicle=excluded.vehicle,services=excluded.services',(data.driver_id,data.plate,data.vehicle,','.join(sorted(set(data.services)))))
            audit(c,'approve-vehicle',data.driver_id+':'+data.plate,data.reference)
        return {'updated':True}

    @app.post('/v1/operator/vehicles/revoke')
    def revoke(data:Vehicle,authorized=Depends(current)):
        with s.db(True) as c:
            c.execute('DELETE FROM vehicles WHERE driver_id=? AND plate=?',(data.driver_id,data.plate))
            c.execute("UPDATE rides SET status='closed' WHERE driver_id=? AND plate=? AND status='open'",(data.driver_id,data.plate))
            audit(c,'revoke-vehicle',data.driver_id+':'+data.plate,data.reference)
        return {'updated':True}

    @app.post('/v1/operator/rides/{id}/close')
    def close(id:str,data:Evidence,authorized=Depends(current)):
        with s.db(True) as c:
            r=c.execute('SELECT status FROM rides WHERE id=?',(id,)).fetchone()
            s.fail(r is not None,'Ride not found.',404)
            s.fail(r['status']=='open','Only an open offer can be closed.',409)
            c.execute("UPDATE rides SET status='closed' WHERE id=?",(id,))
            audit(c,'close-offer',id,data.reference)
        return {'updated':True,'message':'New bookings stopped. Existing bookings remain valid.'}

    @app.patch('/v1/operator/incidents/{id}')
    def review(id:str,data:Review,authorized=Depends(current)):
        with s.db(True) as c:
            s.fail(c.execute('SELECT 1 FROM incidents WHERE id=?',(id,)).fetchone() is not None,'Report not found.',404)
            c.execute('INSERT INTO incident_reviews VALUES(?,?,?,?) ON CONFLICT(incident_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated=excluded.updated',(id,data.status,data.note,time.time()))
            audit(c,'review-'+data.status,id,data.reference)
        return {'updated':True}

    @app.post('/v1/operator/allocations')
    def allocation(data:Allocation,authorized=Depends(current)):
        with s.db(True) as c:impact.record_allocation(c,**data.model_dump())
        return {'recorded':True}

    @app.post('/v1/operator/heat')
    def heat(data:Heat,authorized=Depends(current)):
        with s.db(True) as c:impact.record_heat_study(c,**data.model_dump())
        return {'recorded':True}
