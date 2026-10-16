import time
from concurrent.futures import ThreadPoolExecutor
import pytest
import app as service
import storage
from tests.test_service import ctx, offer, reserve


def test_last_seat_is_not_double_booked(ctx):
    ride=offer(ctx,capacity=1).json()['ride']['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda user:reserve(ctx,ride,user),['rider','other']))
    assert sorted(r.status_code for r in results)==[201,409]
    with service.db() as c:
        assert c.execute('SELECT available FROM rides WHERE id=?',(ride,)).fetchone()[0]==0


def test_rollback_and_reinitialization_preserve_data(ctx):
    with pytest.raises(RuntimeError):
        with service.db(True) as c:
            c.execute('UPDATE users SET name=? WHERE id=?',('Changed','rider'))
            raise RuntimeError('abort transaction')
    service.init()
    with service.db() as c:
        assert c.execute('SELECT name FROM users WHERE id=?',('rider',)).fetchone()[0]=='rider'


def test_epoch_precision_and_parameter_safety(ctx):
    stamp=1792123456.123456
    name="O'Brien ? 100%"
    with service.db(True) as c:
        c.execute('UPDATE users SET created=?,name=? WHERE id=?',(stamp,name,'rider'))
    with service.db() as c:
        row=c.execute('SELECT created,name FROM users WHERE id=?',('rider',)).fetchone()
        assert abs(row[0]-stamp)<0.00001
        assert dict(row)['name']==name


def test_test_hosting_rejects_live_payments(monkeypatch):
    monkeypatch.setattr(service,'TEST_HOSTING',True)
    monkeypatch.setattr(service,'MODE','production')
    with pytest.raises(Exception,match='Test hosting requires'):
        service.startup()


def test_render_rejects_ephemeral_database(monkeypatch):
    monkeypatch.setenv('RENDER','true')
    monkeypatch.setattr(service,'DATABASE_URL','')
    with pytest.raises(Exception,match='persistent PostgreSQL'):
        service.startup()
