# Planto-Ride visual refresh

The existing `index.html` and `app.html?view=...` routes remain in use. The homepage adds `vision.css`, `vision.mjs` and a locally bundled Three.js scene. Booking, authentication, payments, document access and impact calculations keep their existing API contracts. This release does not migrate user or ride records or activate any new paid service.

The scene progressively loads when visible, pauses in background tabs, caps render resolution and uses a static car image for reduced motion or unavailable WebGL. The car and environmental animation are illustrative concept visuals. Live application data remains in the booking app; no illustration is presented as a real ride, tree allocation or measured cooling outcome.

Car asset: `dist/assets/planto-car-concept.webp`, 1536×1024, approximately 104 KB. Generated using the built-in image generation tool; saved in the repository and encoded as WebP for delivery. The existing user-supplied logo remains unchanged. Three.js license and provenance are in `dist/assets/vendor/three/`.

Final image prompt:

> Use case: product-mockup. Create a photorealistic premium automotive product image for the Planto-Ride website: a futuristic but credible five-seat, four-door sedan, front-left three-quarter view, nose pointing left, entire vehicle visible with generous clear margins. Pearl warm-white body, deep forest-green lower door panels, subtle lime trim, elegant realistic headlights and detailed dark alloy wheels, lightly tinted glass with believable seats. The side doors clearly read exactly 'Planto-Ride' in dark green, alongside a small green leaf-and-wheel emblem inspired by our project branding. No other text or manufacturer badges. Studio-quality soft lighting, natural contact shadow under tires. Background is a flat very pale warm sage (#eef1e5), no buildings, no people, no extra cars. Car fills 85% width, horizontally composed, polished high-end sustainable mobility campaign. This is an illustrative concept car, no fake fleet statistics. Produce landscape 1536x1024-like composition.

QA uses a separate local SQLite database outside the repository. Test accounts are never added to the hosted service. Check the homepage, Find a Ride, Drive, My Trips, Impact, Safety and Account at desktop, tablet and phone widths. Operator approval and RC upload access remain private and separate from passenger sessions.


## Background and iPhone layout correction

The former sticky car showcase is removed from document flow. Both the website and web app use one aria-hidden, pointer-transparent background layer. The low-resolution 3D scene follows overall scrolling and app tab changes, with a static image for reduced motion or unavailable WebGL. Opaque form cards and foreground gradients retain readable contrast. No data or access controls change.

Decorative arrows use bounded SVG. Inline arrows request text presentation to avoid Apple colour-emoji substitution. The closing CTA hides its decoration and stacks its buttons on narrow phones. HTML responses request cache revalidation so returning mobile browsers can obtain the updated interface.
