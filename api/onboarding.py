"""Driver submissions, encrypted private images, and separate operator decisions."""
import base64
import binascii
import io
import os
import re
import time
import warnings
from typing import Literal
from cryptography.fernet import Fernet, InvalidToken
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
import storage

MAX_IMAGE=2*1024*1024
RETENTION=30*86400
CONSENT='vehicle-documents-v1'
SCHEMA='''
CREATE TABLE IF NOT EXISTS vehicle_applications(id TEXT PRIMARY KEY,driver_id TEXT NOT NULL REFERENCES users(id),plate TEXT NOT NULL,vehicle TEXT NOT NULL,services TEXT NOT NULL,status TEXT NOT NULL,review_note TEXT NOT NULL DEFAULT '',reference TEXT NOT NULL DEFAULT '',government_status TEXT NOT NULL DEFAULT 'not_connected',consent_version TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS vehicle_application_pending ON vehicle_applications(driver_id,plate) WHERE status='pending';
CREATE TABLE IF NOT EXISTS vehicle_documents(application_id TEXT NOT NULL REFERENCES vehicle_applications(id),kind TEXT NOT NULL,ciphertext TEXT NOT NULL,bytes INTEGER NOT NULL,expires REAL NOT NULL,PRIMARY KEY(application_id,kind));
'''

def init(c):
    storage.install(c,SCHEMA)
    purge(c)

def purge(c): c.execute('DELETE FROM vehicle_documents WHERE expires<?',(time.time(),))

def cipher():
    try:return Fernet(os.environ['DOCUMENT_ENCRYPTION_KEY'].encode())
    except (KeyError,ValueError):raise HTTPException(503,'Private document storage is not configured. Contact the operator.')

def image_bytes(encoded):
    try:
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>MAX_IMAGE:raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ('JPEG','PNG') or source.width*source.height>16000000:raise ValueError()
                source.load()
                # Decode and re-encode pixels: discard EXIF/GPS and non-image payloads.
                im=ImageOps.exif_transpose(source).convert('RGB')
                im.thumbnail((2400,2400))
                out=io.BytesIO();im.save(out,format='JPEG',quality=90)
                result=out.getvalue()
                if len(result)>MAX_IMAGE:raise ValueError()
                return result
    except (ValueError,binascii.Error,OSError,UnidentifiedImageError,Image.DecompressionBombWarning,Image.DecompressionBombError):
        raise HTTPException(400,'Use a valid JPG or PNG photo up to 2 MB and 16 megapixels.')

class Input(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Submission(Input):
    plate:str=Field(min_length=6,max_length=20)
    vehicle:str=Field(min_length=2,max_length=80)
    services:list[Literal['shared','cab','bike']]=Field(min_length=1,max_length=3)
    licence_photo:str=Field(min_length=16,max_length=2800000)
    aadhaar_photo:str=Field(min_length=16,max_length=2800000)
    consent:bool
    masked_aadhaar:bool
    @field_validator('plate')
    @classmethod
    def normalize(cls,value):
        value=re.sub(r'[ -]','',value.upper())
        if not re.fullmatch(r'[A-Z0-9]{6,16}',value):raise ValueError('Enter a valid registration plate.')
        return value
class Decision(Input):
    decision:Literal['approved','rejected']
    reference:str=Field(min_length=3,max_length=200)
    note:str=Field(min_length=3,max_length=1000)
    documents_reviewed:bool=False

def register(app,s,operator):
    def audit(c,action,id,reference):
        c.execute('INSERT INTO audit(action,target,reference,created) VALUES(?,?,?,?)',(action,id,reference,time.time()))

    @app.get('/v1/vehicle-applications')
    def mine(u=Depends(s.current)):
        with s.db(True) as c:
            purge(c)
            rows=c.execute('SELECT id,plate,vehicle,services,status,review_note,government_status,created FROM vehicle_applications WHERE driver_id=? ORDER BY created DESC LIMIT 50',(u['id'],)).fetchall()
        return {'applications':[dict(r) for r in rows],'government_verification':'not_connected'}

    @app.post('/v1/vehicle-applications',status_code=201)
    def submit(data:Submission,u=Depends(s.current)):
        s.fail(u['role']=='driver','Register or change your account to Driver before submitting a vehicle.',403)
        s.fail(data.consent and data.masked_aadhaar,'Consent and confirmation of masked Aadhaar are required.')
        s.fail(not ('bike' in data.services and len(data.services)>1),'Submit a bike separately from a car.')
        key=cipher()
        s.throttle('vehicle-submission:'+u['id'],5,3600)
        pictures={'licence':image_bytes(data.licence_photo),'aadhaar':image_bytes(data.aadhaar_photo)}
        with s.db(True) as c:
            purge(c)
            s.fail(not c.execute("SELECT 1 FROM vehicle_applications WHERE driver_id=? AND plate=? AND status='pending'",(u['id'],data.plate)).fetchone(),'This vehicle is already awaiting review. Refresh your submissions.',409)
            s.fail(c.execute("SELECT count(*) FROM vehicle_applications WHERE driver_id=? AND status='pending'",(u['id'],)).fetchone()[0]<5,'You already have five pending applications.',409)
            s.fail(c.execute('SELECT coalesce(sum(bytes),0) FROM vehicle_documents').fetchone()[0]+sum(map(len,pictures.values()))<=100*1024*1024,'Pilot document storage is full. Contact the operator.',503)
            id=s.uid('vehicle_application');now=time.time()
            c.execute('INSERT INTO vehicle_applications(id,driver_id,plate,vehicle,services,status,consent_version,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(id,u['id'],data.plate,data.vehicle,','.join(sorted(set(data.services))),'pending',CONSENT,now,now))
            for kind,raw in pictures.items():
                c.execute('INSERT INTO vehicle_documents VALUES(?,?,?,?,?)',(id,kind,key.encrypt(raw).decode(),len(raw),now+RETENTION))
            audit(c,'vehicle-submitted',id,CONSENT)
        return {'id':id,'status':'pending','government_status':'not_connected','message':'Submitted for operator review. Government verification is not connected.'}

    @app.post('/v1/vehicle-applications/{id}/withdraw')
    def withdraw(id:str,u=Depends(s.current)):
        with s.db(True) as c:
            row=c.execute('SELECT status FROM vehicle_applications WHERE id=? AND driver_id=?',(id,u['id'])).fetchone()
            s.fail(row is not None,'Application not found.',404)
            s.fail(row['status']=='pending','Only pending submissions can be withdrawn.',409)
            c.execute("UPDATE vehicle_applications SET status='withdrawn',updated=? WHERE id=?",(time.time(),id))
            c.execute('DELETE FROM vehicle_documents WHERE application_id=?',(id,))
            audit(c,'vehicle-withdrawn',id,'driver-request')
        return {'withdrawn':True}

    @app.get('/v1/operator/vehicle-applications/{id}/documents')
    def documents(id:str,authorized=Depends(operator)):
        with s.db(True) as c:
            purge(c)
            rows=c.execute('SELECT kind,ciphertext FROM vehicle_documents WHERE application_id=? AND expires>?',(id,time.time())).fetchall()
            s.fail(bool(rows),'Photos have expired or were removed. Ask the driver to submit again.',404)
            audit(c,'operator:document-view',id,'private-review')
            try: images={r['kind']:'data:image/jpeg;base64,'+base64.b64encode(cipher().decrypt(r['ciphertext'].encode())).decode() for r in rows}
            except InvalidToken:raise HTTPException(503,'Document decryption is unavailable. Contact the operator.')
        return {'images':images,'government_status':'not_connected'}

    @app.post('/v1/operator/vehicle-applications/{id}/review')
    def review(id:str,data:Decision,authorized=Depends(operator)):
        with s.db(True) as c:
            purge(c)
            a=c.execute('SELECT * FROM vehicle_applications WHERE id=?',(id,)).fetchone()
            s.fail(a is not None,'Application not found.',404)
            s.fail(a['status']=='pending','This application has already been reviewed or withdrawn.',409)
            if data.decision=='approved':
                s.fail(data.documents_reviewed,'Review the documents and record your verification reference first.')
                s.fail(c.execute('SELECT count(*) FROM vehicle_documents WHERE application_id=? AND expires>?',(id,time.time())).fetchone()[0]==2,'Documents expired or were removed. Request a new application.',409)
                u=c.execute('SELECT role,approved FROM users WHERE id=?',(a['driver_id'],)).fetchone()
                s.fail(u['role']=='driver' and u['approved'],'Approve the Driver account in Accounts first.',409)
                c.execute('INSERT INTO vehicles VALUES(?,?,?,?) ON CONFLICT(driver_id,plate) DO UPDATE SET vehicle=excluded.vehicle,services=excluded.services',(a['driver_id'],a['plate'],a['vehicle'],a['services']))
            c.execute('UPDATE vehicle_applications SET status=?,review_note=?,reference=?,updated=? WHERE id=?',(data.decision,data.note,data.reference,time.time(),id))
            audit(c,'operator:vehicle-application-'+data.decision,id,data.reference)
        return {'status':data.decision,'government_status':'not_connected'}

    @app.delete('/v1/operator/vehicle-applications/{id}/documents')
    def delete_documents(id:str,authorized=Depends(operator)):
        with s.db(True) as c:
            c.execute('DELETE FROM vehicle_documents WHERE application_id=?',(id,))
            audit(c,'operator:documents-deleted',id,'retention-cleanup')
        return {'deleted':True}
