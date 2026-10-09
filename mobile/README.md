# Planto-Ride Android and iPhone

Expo SDK 57 / React Native. The native UI connects directly to the same API as the website. No offline sample rides or local booking simulation remains. Your supplied logo is the app icon and header artwork.

```sh
npm ci
npm run typecheck
npm test
npm start
```

Set `EXPO_PUBLIC_API_URL` in your development/build environment to your API's HTTPS base URL. Never set Cashfree secrets in `EXPO_PUBLIC_*`. For local device testing use a reachable private-LAN server address with matching browser CORS if applicable; do not expose test accounts to the internet. Session tokens are in memory only.

```sh
npm run export
npm run build:android
npm run build:ios
```

EAS builds require the owner's Expo project and platform signing credentials. Apple distribution requires the appropriate Apple developer setup. Android package and iOS bundle ID are `com.plantoride.pune`; this is a new identifier for the renamed app. Signed binaries, physical-phone tests and store submission were not performed.

Shared, Car and Bike services, Ladies preference, login/registration, booking, driver offers, PIN verification, trip history, foreground location sharing, trusted contact, trip sharing and floating SOS are implemented. The displayed Car service retains the internal API value `cab` for compatibility. Cashfree opens the short-lived hosted checkout in the system browser; return to Trips and tap Check payment status. The API must be connected for all these account/ride/payment operations.

Location is requested only for user-chosen sharing and stops when the app goes to the background. No background location, automatic route-deviation detector, recording, masked calls, SMS OTP or push dispatch is claimed. SOS opens the dialler/share sheet; it does not automatically dispatch emergency services. Test permission denial, dialler availability, poor connectivity and sharing on real Android/iOS devices before release.

Each rider booking now opens a persistent automated Captain conversation from Trips. The signed-in app polls for due check-ins every 30 seconds while in the foreground, across all tabs. A banner opens the pending conversation. All good answers the current check-in; Need help and I feel unsafe record a concern for operator review. The Captain modal has its own SOS entry. Captain is not a human dispatcher, cannot verify safety and does not send emergency calls or messages. Polling stops when signed out or in the background; push notifications are not implemented.

The Impact tab shows live and completed-trip CO₂ estimates, accumulated vehicle-hours avoided, recorded tree-fund attribution as rider and car owner, and app-wide totals. Drivers declare whether a shared journey was already planned, and riders choose whether they would otherwise drive alone. Accepted foreground GPS samples include accuracy when available. Missing eligible measurement is shown as unavailable rather than fabricated savings. Vehicle-hours avoided are modelled driving avoided, not measured congestion or commuter time saved. The 0.249 kg CO₂/km factor is a US petrol-car proxy, not a vehicle-specific reading. Tree amounts come from recorded allocations; heat reduction remains unmeasured until operator study evidence exists. The dashboard distinguishes any local study result from a city-wide temperature claim.

Source repository: https://github.com/navnathpy/Planto_Ride
