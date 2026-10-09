# Verification — Planto-Ride upgrade

Verified locally on 8–9 October 2026, including the September booking/payment regression suite:

- API: 56 tests passed in temporary databases. Coverage includes empty inventory, password/session behavior, driver and vehicle approval, three vehicle types, Ladies eligibility/no fallback, concurrent last-seat reservation, PIN ownership/lockout, role authorization, location freshness, sharing revocation/end-of-trip, last-shared-cancellation closure, payment amount ownership, durable order history, lost-response retry, active checkout reuse, terminal-order rotation, pending-payment blocking, concurrent checkout protection, historical settlement, forged/mismatched webhook rejection and incident ownership.
- Website: 16 tests passed for fare/capacity rules, missing-backend behavior, visible impact categories without invented data, authorization headers, API failures, Google Maps URLs, impact formatting, chat ownership in the UI, stale-response isolation, check-in replies and clearing private chat on logout. JavaScript syntax checked.
- Mobile: TypeScript and 6 tests passed. Android, iOS and web exports completed successfully with the new logo and location module.

Cashfree integration tests mock provider responses and sign local test webhooks. No real merchant credentials or live charges were used. API host activation, Cashfree domain/webhook acceptance, signed phone builds, physical-device testing, staffed safety operations and production load/security assessment remain unverified.

Dependency audit reports moderate transitive findings in Expo's Xcode/UUID build tooling. The suggested automated fix downgrades Expo across major versions and was not applied. Review compatible upstream fixes before signing/releasing applications. No high/critical npm finding was reported in this check.

Browser validation: account registration reached the API; a separately approved local test rider searched a locally published test offer, reserved it, received a private trip PIN and cancelled it successfully. These isolated fixtures exist only in a scratch database outside the repository. Bike capacity, Ladies selection, empty/unavailable states, tab navigation and SOS panel were checked. No emergency calls or messages were sent.

The final service choices are Shared, Car and Bike. Auto was removed from the website, mobile app and new API offers. The supplied investor deck informed the planned Pune corridors, Green Fund care cycle and workplace roadmap. Example financial/impact figures were not published as results, and the deck itself is excluded from the repository.

Captain coverage includes booking ownership and privacy, persistent assignment, background scheduler catch-up, unanswered-check-in deduplication, terminal-trip stopping, concern retention, incident/request idempotence, stale check-ins, rate limiting and bounded history. Delivery is foreground polling, not native push or staffed safety monitoring.

Impact coverage includes eligibility defaults, GPS accuracy/time/speed filtering, no seat multiplier, completed-total immutability, owner/rider attribution without platform double counting, end-of-trip GPS anchor removal, exact-money allocation bounds, evidence deduplication and controlled site-level heat records. EPA methodology links were checked on 8 October. No environmental outcomes are manufactured for the published app.

Connected browser validation used a separate local test database: Captain check-ins appeared outside the Trips tab, All good was persisted, Help recorded a concern for manual review, and the personal Impact view showed the correct joining date, zero recorded contributions and unmeasured carbon/heat when no GPS/study evidence existed. Test data is excluded from the repository and source archive.
