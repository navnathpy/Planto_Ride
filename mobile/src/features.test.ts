import test from 'node:test';
import assert from 'node:assert/strict';
import {formatMetric,formatRupees,formatDate} from './features.ts';

test('impact formatting distinguishes unavailable measurements from an observed zero',()=>{
 assert.equal(formatMetric(null,'kg'),'Not enough data');
 assert.equal(formatMetric(undefined,'kg'),'Not enough data');
 assert.equal(formatMetric(Number.NaN,'kg'),'Not enough data');
 assert.equal(formatMetric(0,'kg'),'0 kg');
 assert.equal(formatMetric(1.249,'kg'),'1.25 kg');
 assert.equal(formatMetric(-0.5,'°C'),'-0.5 °C');
});
test('tree allocations show recorded zero separately from missing funding data',()=>{
 assert.equal(formatRupees(0),'₹0');
 assert.equal(formatRupees(1250.5),'₹1,250.5');
 assert.equal(formatRupees(null),'Not available');
 assert.equal(formatRupees(Infinity),'Not available');
});
test('server second timestamps and ISO dates identify the same check-in time',()=>{
 assert.equal(formatDate(1791460800),formatDate('2026-10-08T12:00:00Z'));
 assert.equal(formatDate(null),'Not available');
 assert.equal(formatDate('not-a-date'),'Not available');
});
