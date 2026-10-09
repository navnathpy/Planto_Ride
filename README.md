# Planto-Ride

Shared rides, cars and bikes — with 50% of annual net profit after tax committed to tree planting and care in Pune. Built for Navnath Sonawane, using his supplied Planto-Ride logo.

[Repository](https://github.com/navnathpy/Planto_Ride) · [Hosting setup](HOSTING.md)

## Current release

The website and native Android/iPhone screens now use the same HTTP API. There are **no seeded rides, fictional drivers, local booking fallbacks or passenger-operated trip simulations**. The database starts empty.

The owner will connect backend hosting separately. Until `PLANTO_API_URL` is configured, the public website shows booking-service unavailable and accepts no bookings or payments. Cashfree integration is implemented, but no merchant keys are included and no live transaction has been run. The native source builds successfully; signed APK/IPA and store releases are separate steps.

## Captain and impact release

Each booking receives a persistent, private **Captain** chatbot. It is a rules-based automated assistant, not a human driver or safety officer. The API schedules a check-in at trip start and five minutes after each reply during a trip, with at most one unanswered check-in. Signed-in clients poll across tabs while open. Replies are stored, and help/unsafe reports enter the existing manual incident-review queue. There are no push notifications, automatic calls or staffed response promises. Missing replies never establish that a ride is safe.

The new **Impact** tab shows live eligible shared-ride CO₂ estimates, accumulated completed-trip estimates since joining, rider/owner tree-fund allocations, overall estimated vehicle-hours avoided, and site-level heat-study results when recorded. Unknown or missing measurements stay unmeasured. See [impact methodology and operator records](api/IMPACT.md) and the website's methodology page.

Savings require an already-planned shared journey, an explicit solo-car alternative and credible foreground GPS segments. The 0.249 kg CO₂/km US petrol-car proxy is an estimate, not measured Pune emissions. Tree funding comes from evidence-backed allocation records, not an automatic percentage of each fare. No carbon-to-°C conversion is used.

## Included

- Shared-seat fares; exclusive car and bike bookings, with vehicle capacity limits.
- Password-based accounts, hashed credentials, expiring sessions, operator approval of riders/drivers and service-specific vehicles.
- Ladies journeys: operator-verified women riders and drivers, all-women-party confirmation, no mixed-ride fallback. This is an eligibility control, not a guarantee of safety.
- Driver-only PIN-verified trip starts, lockouts after incorrect attempts, cancellation before start, completion and history.
- Floating SOS on all web/mobile tabs: 112 dial action, trusted contact, opt-in current-location sharing. No automatic emergency dispatch or staffed monitoring is claimed.
- Expiring/revocable journey links, optional foreground driver location, no stale or post-trip coordinates displayed.
- Cashfree checkout after trip completion: server-created amounts, deterministic idempotency keys, authenticated status reconciliation and signed webhooks. Native checkout opens the hosted payment page.
- Safety reports recorded for manual operator review. No automatic alerts are sent.

## Run locally

Python 3.12:
```sh
cd api
python -m venv .venv
# Activate .venv using your shell, then:
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8788 --no-access-log
```

Website (Node 24 and Python): set `PLANTO_API_URL=http://127.0.0.1:8788` in your terminal environment, then:
```sh
node website/scripts/configure-api.mjs
python -m http.server 4173 --bind 127.0.0.1 --directory website/dist
```

Open `http://127.0.0.1:4173/app.html`. Register rider/driver accounts, then follow `api/README.md` for operator approval. New accounts cannot bypass verification. For mobile, set `EXPO_PUBLIC_API_URL` to the reachable API URL and run `npm ci` and `npm start` in `mobile/`.

## Deployment and boundaries

Read **[HOSTING.md](HOSTING.md)** for the persistent backend, HTTPS, Cashfree, webhook and Pages configuration. **[LAUNCH-PLAN.md](LAUNCH-PLAN.md)** lists remaining operational prerequisites. **[VERIFICATION.md](VERIFICATION.md)** records checks and their limitations.

This release supports scheduled offers matched by exact pickup/destination areas. It does not implement automatic nearby-driver dispatch, Google route-based metered pricing, SMS OTP, masked calls, background GPS, push notifications, automatic emergency response or an operating driver fleet. Google Maps city/route previews are separate from optional live coordinates.

Never put merchant passwords, Cashfree secrets, databases, identity documents or signing keys in GitHub. This version is saved in the requested **navnathpy/Planto_Ride** repository. The earlier `Plato-ride` repository and deployment are separate.

The vision website incorporates the supplied investor deck’s Pune office-commute focus, proposed corridors, Green Fund care cycle and employer roadmap. Deck projections, example impact figures and unverified regulatory claims are not presented as operating results. The private source deck is not included in the public repository.
