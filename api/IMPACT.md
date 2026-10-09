# Impact measurement and evidence ledger

Version: 8 October 2026. The application starts with no impact data. It never invents distance, emissions savings, money allocated, trees planted or temperature changes.

## Carbon and vehicle-hours

The live estimate requires all three conditions:

1. A **Shared** ride, with the owner confirming before publication that this journey was already planned.
2. The rider declaring that the booking party would otherwise use **one solo car**. Unknown and other alternatives are excluded. A booking with several seats still represents at most one avoided car.
3. Accepted foreground GPS movement while the booking is in progress after its trip PIN has been checked.

The default baseline is unknown; the owner declaration defaults to false. Existing data is migrated with these conservative defaults. Car and Bike bookings never receive an avoided-car estimate through this model.

For eligible bookings:

```
Estimated avoided tailpipe CO2 (kg) = accepted distance (km) × 0.249
Estimated vehicle-hours avoided   = accepted segment seconds ÷ 3,600
```

The illustrative factor comes from the US EPA's approximate 400 grams of tailpipe CO2 per mile for an average passenger vehicle, converted to kilometres and rounded. It is **not an Indian fleet estimate**, fuel measurement, certified carbon credit or complete carbon footprint. See the [EPA passenger-vehicle source](https://www.epa.gov/greenvehicles/greenhouse-gas-emissions-typical-passenger-vehicle). Deployment should replace the assumption with a documented local vehicle/fuel model before making verified environmental claims.

This is a **gross avoided-car baseline estimate**, conditional on truthful declarations. It does not model different solo routes, pickup detours, additional energy caused by passengers, vehicle manufacture or fuel supply. No savings are attributed to trees. Observed shared-ride segments approximate the replaced solo-car segments; route equality is not independently verified.

Vehicle-hours are an estimate of vehicle use removed from the road. They are **not measured hours saved in traffic**: measuring congestion delay requires independent travel-time baselines and network analysis. This release does not report citywide traffic-delay reductions.

### GPS coverage and privacy

Each authorized driver location request may include `accuracy` in metres. Missing accuracy does not stop normal location sharing, but that fix cannot contribute to impact totals. The impact module accepts fixes only with accuracy at most 50 metres, using server receipt timestamps. It skips the first fix, duplicate/backward timestamps, intervals longer than 120 seconds, movement below both the 30-metre floor and the combined accuracy radii, and speeds above 160 km/h. Poor accuracy and speed outliers break continuity. Pausing location sharing clears the anchor.

It stores aggregate metres, seconds and segment count per booking, plus one current GPS anchor per active ride. It does not store a raw route history. A later-boarding passenger does not receive distance before boarding. Completed totals are frozen and cancelled bookings are excluded. Gaps, slow movements below the threshold and stationary intervals are omitted, so totals can undercount substantially. GPS spoofing cannot be reliably prevented by these filters; estimates are not verification evidence.

Live values are current in-progress totals; lifetime values are completed bookings since account creation. Personal savings are `null` until at least one eligible measured segment exists. Public aggregate totals begin at zero, with `measurement_available: false` and coverage counts to distinguish an empty ledger from measured zero emissions. `tracked_km` sums tracked booking kilometres, including unmodelled bookings; it is not unique fleet kilometres.

A rider's savings and the owner's enabled savings refer to the **same booking**. The overall query counts each booking once. Do not sum personal dashboards. A person acting in both roles sees a combined personal total and separate lifetime attribution fields.

## Tree-planting contributions

The Green Fund commitment is **50% of annual net profit after tax**, not half the fare. Payment confirmation alone adds no tree allocation. A restricted server operator records funds actually allocated to the Green Fund after reconciling the relevant accounts. The backend cannot independently verify an invoice, profit calculation, planting event or tree survival.

Each allocation records a completed and paid booking, rider-attributed INR, owner-attributed INR, a tree count, a unique internal evidence reference and a public HTTPS evidence URL. INR is validated and stored as integer paise. The combined allocation must be positive; accumulated allocations cannot exceed the booking's paid amount. This ceiling is a validation guard, not a net-profit calculation. Both participants' attributed amounts must be partitions of the same recorded funds, not duplicate credits.

Tree count is an operator-recorded planting count tied to that evidence entry. Only count a physical tree once across all entries. Use zero for a fund allocation without planting evidence or when a planting count has already been recorded. Amounts shown are **allocated**, not automatically spent or donated by the passenger. Publish payment receipts, accounting allocation evidence and planting records separately through a suitable public report. Never include private rider information in the public evidence.

There is no HTTP endpoint to create allocation or study records. Server filesystem access is the operator authorization boundary. Restrict SSH, service accounts and database access; back up the database and audit table. An authenticated passenger cannot modify this ledger. Each operator command writes an audit event within the same transaction. Corrections require a reviewed database migration with an audit note; this release does not silently edit or delete prior entries.

From `api/`, using the same `DATABASE_PATH` as the running service:

```sh
python impact.py record-tree-allocation --booking-id BOOKING_ID --rider-inr 2.30 --owner-inr 1.20 --trees 0 --reference UNIQUE_ACCOUNTING_REFERENCE --evidence-url https://YOUR_PUBLIC_REPORT_URL
```

The example values are command syntax only. Do not run them without actual reconciled evidence. Keep the total recorded allocations consistent with the annual net-profit commitment; this release does not provide an accounting system or annual profit calculator.

## Urban heat in degrees Celsius

`heat.reduction_c` remains **null / Not yet measured** until an operator records an evidence-backed local study. Money, tree counts, CO2 estimates and journey counts are never multiplied by a cooling factor. `citywide_reduction_c` remains null even after a local study.

The ledger requires a named public site, dated before/after mean **air temperatures** at the project site and a matched control, at least two matched samples per period, a protocol, a unique reference and a public evidence URL. It computes:

```
Site-level cooling association (°C)
  = (site before − site after) − (control before − control after)
```

Negative results are retained: a warming association must not be hidden. The latest study by observation date is displayed with its scope, dates, protocol and source. Studies are not summed; multiple locations are not averaged into a citywide claim.

This difference-in-differences arithmetic is a reporting aid, **not proof of causation**. The operator must document site/control comparability, matched dates/hours/seasons, local weather, sensor calibration and shielding, measurement height, sample count and uncertainty in the linked study. Two samples are merely the data-entry floor, not evidence of adequate statistical power. Do not record remote surface temperature as if it were measured air temperature. A qualified measurement team should design and review the study before publication.

The [EPA heat-island measurement guidance](https://www.epa.gov/heatislands/measuring-heat-islands) distinguishes air and surface measurements and stresses representative sites, consistent monitoring and documented time and spatial scope. A few local sensors may not represent citywide conditions. Planto-Ride accordingly labels a recorded result as a **site-level measured association**, not a causal reduction of Pune's urban heat island attributable to the app.

Operator command syntax:

```sh
python impact.py record-heat-study --site "PUBLIC_SITE_NAME" --before-at "2025-04-15T14:00:00+05:30" --after-at "2025-05-15T14:00:00+05:30" --site-before 35 --site-after 32 --control-before 34 --control-after 33 --samples 20 --protocol "ACTUAL_MATCHED_MEASUREMENT_PROTOCOL" --reference UNIQUE_STUDY_REFERENCE --evidence-url https://YOUR_PUBLIC_STUDY_URL
```

Those numbers illustrate argument names, not observations. Enter actual evidence only. Date validation requires ordered observations in the past; temperature inputs must be finite and within −60 to 80°C.

## Read API and integration

- `GET /v1/impact/me` requires the user's bearer session and returns only their account's live/lifetime totals, lifetime rider/owner attribution and contribution split.
- `GET /v1/impact/overall` is public and returns aggregate completed booking estimates, recorded tree funds/counts, the latest local study and methodology. It exposes no rider, driver, route, trip PIN, raw coordinates or internal evidence reference.
- Both include a methodology version and primary source URLs. UI copy must preserve the estimate, coverage and attribution limits.
- Core service hooks run inside its existing transaction: `init(c)`, `record_offer`, `record_booking`, `start_booking`, `complete_booking`, `record_location` and `stop_location`. `register(app, service)` attaches the two read-only endpoints.

Tests cover conservative defaults and migration, eligibility, seat counts, owner attribution, accepted GPS segments, rejected fixes, start/complete boundaries, paused tracking, cancellation, private endpoint access, paid-booking allocations, exact paise, limits, evidence deduplication, and positive/negative controlled heat calculations.
