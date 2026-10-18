// Planto-Ride's decorative, progressively enhanced car scene.
// Three.js r186 is locally vendored; no models, tracking or remote runtime assets.
const canvas = document.querySelector('#ride-scene');
const stage = document.querySelector('#scene-stage');
const fallback = document.querySelector('#scene-fallback');
const caption = document.querySelector('#scene-status');
const backgroundMode = stage?.dataset.sceneMode === 'background';
const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
let controller = null;
let loading = false;
let stopped = false;
let visible = false;
let generation = 0;

function staticView() {
  if (stage) stage.dataset.scene = 'fallback';
  if (canvas) { canvas.hidden = true; canvas.style.opacity = '0'; }
  if (fallback) { fallback.hidden = false; fallback.style.opacity = '1'; }
}

async function enhance() {
  if (!canvas || !stage || loading || controller || stopped || motion.matches || !visible) return;
  loading = true;
  const thisGeneration = ++generation;
  try {
    const THREE = await import('./assets/vendor/three/three-planto-0.186.1.mjs');
    if (stopped || thisGeneration !== generation || motion.matches) return;
    controller = buildScene(THREE);
    controller.setVisible(visible && !document.hidden);
  } catch (error) {
    staticView();
    // A failed GPU enhancement must never interrupt navigation or booking.
    console.info('Planto-Ride is using its static car illustration.', error?.message || 'WebGL unavailable');
  } finally {
    loading = false;
  }
}

function buildScene(T) {
  const renderer = new T.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, backgroundMode ? 1.15 : window.innerWidth < 700 ? 1.4 : 1.7));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.35;
  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(34, 1, 0.1, 80);
  const world = new T.Group();
  scene.add(world);
  const materials = new Set();
  const geometries = new Set();
  const textures = new Set();
  const resources = (material) => { materials.add(material); return material; };
  const standard = (options) => resources(new T.MeshStandardMaterial(options));
  const physical = (options) => resources(new T.MeshPhysicalMaterial(options));
  const basic = (options) => resources(new T.MeshBasicMaterial(options));
  const geo = (geometry) => { geometries.add(geometry); return geometry; };
  const make = (geometry, material, parent = world) => { const object = new T.Mesh(geo(geometry), material); parent.add(object); return object; };
  const body = physical({ color: 0xdce6d5, metalness: 0.52, roughness: 0.24, clearcoat: 1, clearcoatRoughness: 0.16 });
  const dark = standard({ color: 0x10251e, metalness: 0.48, roughness: 0.3 });
  const trim = standard({ color: 0x4e6259, metalness: 0.9, roughness: 0.22 });
  const rubber = standard({ color: 0x111815, roughness: 0.92 });
  const rim = standard({ color: 0xc7cec8, metalness: 0.95, roughness: 0.2 });
  const glass = physical({ color: 0x1d3c35, metalness: 0.35, roughness: 0.13, clearcoat: 1, side: T.DoubleSide });
  const lime = standard({ color: 0xc9f37a, emissive: 0x8ab147, emissiveIntensity: 0.18, roughness: 0.4 });
  const whiteLight = basic({ color: 0xf1ffe4 });
  const redLight = basic({ color: 0xef6559 });

  scene.add(new T.HemisphereLight(0xe9f4dd, 0x33443a, 3.2));
  const light = new T.DirectionalLight(0xfff3dd, 4.4);
  light.position.set(1, 7, 6); scene.add(light);
  const edgeLight = new T.DirectionalLight(0xb6d9b4, 3.4);
  edgeLight.position.set(-5, 3, -4); scene.add(edgeLight);
  const frontLight = new T.DirectionalLight(0xe0f0ff, 1.7);
  frontLight.position.set(5, 2, -2); scene.add(frontLight);

  function box(parent, x, y, z, w, h, d, material, radius = 0) {
    const mesh = make(new T.BoxGeometry(w, h, d), material, parent);
    mesh.position.set(x, y, z);
    return mesh;
  }
  function extrudedProfile(points, depth, material, parent, bevel = .04) {
    const outline = new T.Shape();
    points.forEach(([x, y], index) => index ? outline.lineTo(x, y) : outline.moveTo(x, y));
    outline.closePath();
    const mesh = make(new T.ExtrudeGeometry(outline, { depth, steps: 1, bevelEnabled: bevel > 0, bevelSegments: 3, bevelSize: bevel, bevelThickness: bevel, curveSegments: 20 }), material, parent);
    mesh.position.z = -depth / 2;
    return mesh;
  }
  function panel(parent, points, material) {
    const geometry = new T.BufferGeometry();
    const vertices = [];
    for (let i = 1; i < points.length - 1; i++) vertices.push(...points[0], ...points[i], ...points[i + 1]);
    geometry.setAttribute('position', new T.Float32BufferAttribute(vertices, 3));
    geometry.computeVertexNormals();
    return make(geometry, material, parent);
  }
  function stroke(parent, points, color, opacity = 1) {
    const geometry = geo(new T.BufferGeometry().setFromPoints(points.map(p => new T.Vector3(...p))));
    const material = resources(new T.LineBasicMaterial({ color, transparent: true, opacity }));
    const line = new T.Line(geometry, material); parent.add(line); return line;
  }
  function tube(parent, points, radius, material) {
    return make(new T.TubeGeometry(new T.CatmullRomCurve3(points.map(p => new T.Vector3(...p))), 22, radius, 6, false), material, parent);
  }
  function textureFromCanvas(painter, width = 1024, height = 512) {
    const bitmap = document.createElement('canvas'); bitmap.width = width; bitmap.height = height;
    painter(bitmap.getContext('2d'), width, height);
    const texture = new T.CanvasTexture(bitmap); texture.colorSpace = T.SRGBColorSpace;
    textures.add(texture); return texture;
  }

  // Four opening doors, a two-seat front row and a three-seat rear bench form a five-seat concept sedan.
  const car = new T.Group(); world.add(car);
  const shellShape = new T.Shape();
  shellShape.moveTo(-2.31, .46); shellShape.lineTo(-2.30, .96);
  shellShape.quadraticCurveTo(-2.13, 1.16, -1.69, 1.17);
  shellShape.lineTo(.96, 1.16); shellShape.lineTo(1.91, 1.09);
  shellShape.quadraticCurveTo(2.36, 1.05, 2.39, .82);
  shellShape.lineTo(2.37, .43); shellShape.lineTo(2.02, .43);
  shellShape.absarc(1.5, .46, .52, -.058, Math.PI + .058, false);
  shellShape.lineTo(-.98, .43);
  shellShape.absarc(-1.5, .46, .52, -.058, Math.PI + .058, false);
  shellShape.lineTo(-2.31, .46);
  const shell = make(new T.ExtrudeGeometry(shellShape, { depth: 1.65, steps: 1, bevelEnabled: true, bevelSegments: 4, bevelSize: .08, bevelThickness: .08, curveSegments: 28 }), body, car);
  shell.position.z = -.825;
  // Taper the bonnet and wrap the nose around its corners instead of using a flat box front.
  const shellPositions = shell.geometry.attributes.position;
  for (let i = 0; i < shellPositions.count; i++) {
    const x = shellPositions.getX(i), y = shellPositions.getY(i), z = shellPositions.getZ(i) - .825;
    const nose = Math.max(0, Math.min(1, (x - 1.0) / 1.4));
    const corner = Math.pow(Math.abs(z) / .91, 2);
    shellPositions.setXYZ(i, x - nose * nose * corner * .24, y - nose * Math.max(0, y - .8) * .42, shellPositions.getZ(i));
  }
  shellPositions.needsUpdate = true; shell.geometry.computeVertexNormals();
  extrudedProfile([[-1.72, 1.16], [-1.02, 1.63], [-.77, 1.71], [.18, 1.70], [.45, 1.59], [1.07, 1.16]], 1.48, body, car, .06);
  // Panoramic roof with a bright edge strip and dark glass.
  box(car, -.28, 1.779, 0, 1.02, .018, 1.25, glass);
  box(car, .25, 1.761, 0, .035, .025, 1.23, trim);
  // Side glass is divided into front and rear windows by a visible B-pillar.
  [-1, 1].forEach(side => {
    // Cabin bevels reach z=±.80; glazing must sit beyond them to avoid occlusion.
    const z = side * .818;
    panel(car, [[-.19, 1.24, z], [.95, 1.24, z], [.36, 1.61, z], [-.19, 1.66, z]], glass);
    panel(car, [[-1.55, 1.24, z], [-.28, 1.24, z], [-.28, 1.66, z], [-.90, 1.64, z]], glass);
    box(car, -.235, 1.45, z + side * .004, .065, .44, .025, dark);
    tube(car, [[-1.43, 1.18, z], [-.3, 1.18, z], [.99, 1.18, z]], .017, trim);
    // Door seams, inset handles and lower sill make both doors on each side clear.
    stroke(car, [[-.24, 1.17, side * .918], [-.24, .55, side * .918]], 0x7f9386, .65);
    stroke(car, [[-1.35, 1.16, side * .918], [-1.13, .56, side * .918], [.84, .56, side * .918], [1.01, 1.16, side * .918]], 0x7f9386, .5);
    box(car, -.48, 1.08, side * .929, .24, .035, .025, dark);
    box(car, .69, 1.08, side * .929, .24, .035, .025, dark);
    box(car, -.05, .405, side * .88, 1.97, .085, .07, dark);
    box(car, -.05, .452, side * .921, 1.82, .012, .01, lime);
    const mirror = make(new T.SphereGeometry(1, 16, 12), body, car);
    mirror.scale.set(.19, .1, .11); mirror.position.set(.84, 1.30, side * 1.01);
    box(car, .78, 1.25, side * .90, .07, .055, .22, dark);
    box(car, .81, 1.32, side * 1.09, .22, .012, .018, whiteLight);
  });
  panel(car, [[.40, 1.69, -.69], [.40, 1.69, .69], [1.11, 1.23, .79], [1.11, 1.23, -.79]], glass);
  panel(car, [[-1.65, 1.25, -.78], [-1.65, 1.25, .78], [-1.04, 1.68, .69], [-1.04, 1.68, -.69]], glass);
  // Subtle reflected skylight strips keep the windows legible without an expensive environment map.
  panel(car, [[.52, 1.67, -.59], [.52, 1.67, -.48], [1.045, 1.27, -.56], [1.045, 1.27, -.67]], basic({ color: 0xb8d9cb, transparent: true, opacity: .18, side: T.DoubleSide }));
  [-.45, .45].forEach(z => { box(car, .13, 1.26, z, .33, .39, .36, dark); box(car, .13, 1.50, z, .17, .15, .27, dark); });
  [-.49, 0, .49].forEach(z => { box(car, -.88, 1.24, z, .26, .34, .30, dark); box(car, -.88, 1.45, z, .14, .14, .23, dark); });
  // Sculpted nose, a lower intake, full-width light signature and rear light bar.
  const noseX = z => 2.487 - .24 * Math.pow(Math.abs(z) / .91, 2);
  const grilleVertices = [];
  for (let z = -.65; z < .64; z += .13) {
    const x0 = noseX(z) + .018, x1 = noseX(z + .13) + .018, z1 = z + .13;
    grilleVertices.push(x0, .58, z, x0, .75, z, x1, .58, z1, x1, .58, z1, x0, .75, z, x1, .75, z1);
  }
  const grilleGeometry = new T.BufferGeometry();
  grilleGeometry.setAttribute('position', new T.Float32BufferAttribute(grilleVertices, 3));
  grilleGeometry.computeVertexNormals(); make(grilleGeometry, dark, car);
  tube(car, Array.from({ length: 19 }, (_, i) => { const z = -.73 + i * 1.46 / 18; return [noseX(z) + .009, .91 - Math.abs(z) * .03, z]; }), .018, whiteLight);
  [-.69, .69].forEach(z => { tube(car, [[noseX(z), .89, z], [noseX(z), .81, z]], .016, whiteLight); box(car, -2.40, .985, z, .02, .08, .24, redLight); });
  box(car, -2.39, .985, 0, .022, .022, 1.25, redLight);
  box(car, 2.426, .55, 0, .018, .09, .42, body);
  box(car, -2.40, .58, 0, .02, .12, 1.35, dark);
  stroke(car, [[1.08, 1.194, -.59], [1.86, 1.14, -.59], [2.12, 1.07, -.53]], 0x91a794, .5);
  stroke(car, [[1.08, 1.194, .59], [1.86, 1.14, .59], [2.12, 1.07, .53]], 0x91a794, .5);
  const wheels = [];
  [-1.5, 1.5].forEach(x => [-1, 1].forEach(side => {
    const wheel = new T.Group(); wheel.position.set(x, .46, side * .91); car.add(wheel); wheels.push(wheel);
    const tyre = make(new T.CylinderGeometry(.445, .445, .255, 36, 1), rubber, wheel); tyre.rotation.x = Math.PI / 2;
    const hub = make(new T.CylinderGeometry(.322, .322, .265, 32), dark, wheel); hub.rotation.x = Math.PI / 2;
    const outer = make(new T.TorusGeometry(.32, .013, 6, 36), rim, wheel); outer.position.z = side * .141;
    const center = make(new T.CylinderGeometry(.077, .077, .29, 20), rim, wheel); center.rotation.x = Math.PI / 2;
    for (let i = 0; i < 7; i++) {
      const spoke = box(wheel, Math.cos(i * Math.PI * 2 / 7) * .18, Math.sin(i * Math.PI * 2 / 7) * .18, side * .143, .27, .041, .018, rim);
      spoke.rotation.z = i * Math.PI * 2 / 7;
    }
    const inner = make(new T.TorusGeometry(.39, .009, 5, 36), trim, wheel); inner.position.z = side * .13;
  }));

  const doorTexture = textureFromCanvas((context, w, h) => {
    context.clearRect(0, 0, w, h);
    context.fillStyle = '#123e2b'; context.font = '700 126px Arial, sans-serif'; context.textAlign = 'center';
    context.fillText('Planto-Ride', w / 2, h / 2 + 28);
    context.fillStyle = '#4c7154'; context.font = '500 35px Arial, sans-serif'; context.letterSpacing = '5px';
    context.fillText('SHARE A RIDE. GROW A CITY.', w / 2, h / 2 + 93);
  });
  const decalMaterial = basic({ map: doorTexture, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 });
  [-1, 1].forEach(side => {
    const label = make(new T.PlaneGeometry(1.72, .86), decalMaterial, car); label.position.set(-.03, .805, side * .922); label.rotation.y = side === 1 ? 0 : Math.PI;
  });
  // The supplied emblem is drawn on the rear door and bonnet, keeping the exact brand artwork.
  const logoImage = new Image();
  let disposed = false;
  logoImage.onload = () => {
    if (disposed) return;
    const logoTexture = textureFromCanvas((context, w, h) => context.drawImage(logoImage, 180, 100, 940, 830, 0, 0, w, h), 512, 512);
    const logoMaterial = basic({ map: logoTexture, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -3 });
    [-1, 1].forEach(side => { const mark = make(new T.PlaneGeometry(.32, .32), logoMaterial, car); mark.position.set(-.95, .88, side * .924); mark.rotation.y = side === 1 ? 0 : Math.PI; });
    const badge = make(new T.PlaneGeometry(.30, .30), logoMaterial, car); badge.rotation.x = -Math.PI / 2; badge.position.set(1.43, 1.17, 0);
    renderFrame(performance.now());
  };
  logoImage.src = new URL('./assets/planto-ride-logo.png', import.meta.url).href;

  // A soft contact shadow anchors the vehicle while allowing the page background to show through.
  const shadowTexture = textureFromCanvas((context, w, h) => { const gradient = context.createRadialGradient(w / 2, h / 2, w * .03, w / 2, h / 2, w * .49); gradient.addColorStop(0, 'rgba(0,10,4,.5)'); gradient.addColorStop(1, 'rgba(0,10,4,0)'); context.fillStyle = gradient; context.fillRect(0, 0, w, h); }, 256, 256);
  const shadow = make(new T.PlaneGeometry(7, 3.7), basic({ map: shadowTexture, transparent: true, depthWrite: false }), world); shadow.rotation.x = -Math.PI / 2; shadow.position.y = .006;
  const road = new T.Group(); world.add(road);
  const roadLine = basic({ color: 0xa5c4a7, transparent: true, opacity: .18, depthWrite: false });
  for (let x = -5; x < 5; x += 1.15) [-1.8, 1.8].forEach(z => { const dash = make(new T.PlaneGeometry(.55, .024), roadLine, road); dash.rotation.x = -Math.PI / 2; dash.position.set(x, .013, z); });
  const ring = make(new T.RingGeometry(3.8, 3.81, 100), basic({ color: 0xb4db95, transparent: true, opacity: .16, side: T.DoubleSide, depthWrite: false }), world); ring.rotation.x = -Math.PI / 2; ring.position.y = -.015; ring.scale.y = .75;

  const trafficMaterial = standard({ color: 0x9bb7a6, metalness: .2, roughness: .65, transparent: true, opacity: .15, depthWrite: false });
  const ghostMaterial = standard({ color: 0x122f25, transparent: true, opacity: .16, depthWrite: false, roughness: .5 });
  const traffic = [];
  [[-2.7, -2.75], [2.6, -2.75], [-3.6, 2.9]].forEach(([x, z], index) => {
    const ghost = new T.Group(); world.add(ghost); ghost.position.set(x, .03, z); ghost.scale.setScalar(.67);
    extrudedProfile([[-2.2, .5], [-2.2, 1.0], [-1.1, 1.14], [-.7, 1.77], [.35, 1.77], [.97, 1.15], [2.2, .97], [2.2, .5]], 1.6, trafficMaterial, ghost, .09);
    [-1.4, 1.4].forEach(wheelX => [-.89, .89].forEach(wheelZ => { const wheel = make(new T.CylinderGeometry(.42, .42, .2, 16), ghostMaterial, ghost); wheel.rotation.x = Math.PI / 2; wheel.position.set(wheelX, .45, wheelZ); }));
    traffic.push({ group: ghost, x, z, direction: index === 1 ? -1 : 1 });
  });

  const foliage = standard({ color: 0x7aa35c, roughness: .88 });
  const foliageLight = standard({ color: 0xb2cc78, roughness: .86 });
  const trunk = standard({ color: 0x79634b, roughness: 1 });
  const planter = standard({ color: 0x466855, roughness: .9 });
  const trees = [];
  [[-3.3, -1.45, 1.0], [-1.55, -2.7, .78], [1.25, -3.1, .92], [3.4, -1.35, 1.05], [-3.5, 1.9, .7], [3.3, 2.5, .72]].forEach(([x, z, size], index) => {
    const tree = new T.Group(); tree.position.set(x, .035, z); world.add(tree);
    const pot = make(new T.CylinderGeometry(.30, .25, .18, 12), planter, tree); pot.position.y = .09;
    const growth = new T.Group(); tree.add(growth); growth.position.y = .13;
    const stem = make(new T.CylinderGeometry(.038, .065, 1.05, 8), trunk, growth); stem.position.y = .53;
    [[-.14, 1.2, 0, .43], [.18, 1.36, .06, .46], [0, 1.69, -.02, .43]].forEach(([cx, cy, cz, radius], n) => { const canopy = make(new T.IcosahedronGeometry(radius, 1), n % 2 ? foliageLight : foliage, growth); canopy.position.set(cx, cy, cz); canopy.scale.y = 1.2; });
    trees.push({ group: tree, growth, size, index });
  });
  const waterMaterial = basic({ color: 0x99d5e0, transparent: true, opacity: .65 });
  const droplets = [];
  trees.forEach(({ group }, i) => { for (let n = 0; n < 3; n++) { const droplet = make(new T.SphereGeometry(.028, 5, 4), waterMaterial, world); droplet.scale.y = 1.7; droplets.push({ mesh: droplet, x: group.position.x + .25, z: group.position.z + .1, phase: i * .31 + n * .34 }); } });
  const carbon = new T.Group(); world.add(carbon);
  const trails = [];
  for (let i = 0; i < 3; i++) {
    const trail = stroke(carbon, Array.from({ length: 40 }, (_, n) => { const p = n / 39; return [-2.1 - p * 2.8, .35 + Math.sin(p * 4 + i) * .11 + i * .14, -.45 + i * .45 + p * .12]; }), 0xc4ed85, .45);
    trails.push(trail);
  }

  const steps = [...document.querySelectorAll('[data-story-step]')];
  const labels = ['Shared seats. Fewer separate journeys.', 'Planting is a promise to keep caring.', 'Small journeys. A lighter footprint.', 'More canopy. A greener neighbourhood.'];
  let targetProgress = 0;
  let progress = 0;
  let inView = false;
  let previousFrame = 0;
  let label = -1;
  let started = false;
  let revealElapsed = 0;
  const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));
  const smooth = (value) => { const x = clamp(value); return x * x * (3 - 2 * x); };
  function updateScroll() {
    if (backgroundMode) {
      // The fixed backdrop follows the whole page; it never pins content or owns scrolling.
      const scrollRange = Math.max(1, document.documentElement.scrollHeight - innerHeight);
      const pageProgress = clamp(window.scrollY / scrollRange);
      const activeView = document.querySelector('.view[id^="view-"]:not([hidden])');
      const viewProgress = { 'view-ride': .1, 'view-drive': .55, 'view-trips': 1, 'view-impact': 2.5, 'view-safety': 1.5, 'view-account': 1.9 };
      targetProgress = activeView ? clamp((viewProgress[activeView.id] ?? 0) + pageProgress * .65, 0, 3) : pageProgress * 3;
      return;
    }
    if (steps.length < 2) return;
    const centers = steps.map(step => { const rect = step.getBoundingClientRect(); return rect.top + rect.height * .48; });
    const line = innerHeight * .5;
    let value = 0;
    for (let i = 0; i < centers.length - 1; i++) {
      if (line >= centers[i]) value = i + clamp((line - centers[i]) / Math.max(1, centers[i + 1] - centers[i]));
    }
    targetProgress = clamp(value, 0, 3);
  }
  function resize() {
    if (disposed) return;
    const { width, height } = stage.getBoundingClientRect();
    if (width < 1 || height < 1) return;
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix();
    updateScroll();
    if (!inView) renderFrame(performance.now());
  }
  function renderFrame(time = 0) {
    if (disposed) return;
    // Keep the ambient backdrop inexpensive, especially alongside booking controls.
    if (inView && time - previousFrame < (backgroundMode ? 56 : 31)) return;
    const delta = previousFrame ? Math.min((time - previousFrame) / 1000, .1) : .033;
    previousFrame = time;
    progress += (targetProgress - progress) * (1 - Math.exp(-delta * (backgroundMode ? 1.6 : 6)));
    if (inView) revealElapsed += delta;
    const greenery = smooth((progress - .45) / 2.4);
    const trafficFade = 1 - smooth(progress / .95);
    trafficMaterial.opacity = .16 * trafficFade; ghostMaterial.opacity = .18 * trafficFade;
    traffic.forEach(({ group, x, z, direction }) => { group.visible = trafficFade > .015; group.position.set(x + direction * (1 - trafficFade) * 1.7, .03, z * (.75 + trafficFade * .25)); });
    trees.forEach(({ growth, group, size, index }) => {
      const amount = .15 + greenery * .85;
      growth.scale.setScalar(amount * size); group.scale.setScalar(.6 + .4 * smooth(progress));
      growth.rotation.z = inView ? Math.sin(time * .0005 + index) * .015 * greenery : 0;
    });
    const watering = smooth((progress - .55) * 2.5) * (1 - smooth((progress - 1.55) * 2));
    droplets.forEach(({ mesh, x, z, phase }) => { mesh.visible = watering > .01; mesh.position.set(x, .15 + (1 - ((time * .0006 + phase) % 1)) * .65, z); mesh.scale.x = mesh.scale.z = watering; });
    const carbonAmount = smooth((progress - 1.35) * 2) * (1 - smooth((progress - 2.6) * 2));
    carbon.visible = carbonAmount > .01;
    trails.forEach((trail, i) => { trail.material.opacity = carbonAmount * (.42 - i * .07); trail.position.x = Math.sin(time * .0007 + i) * .08; });
    const drift = backgroundMode && inView ? Math.sin(time * .000075) : 0;
    const angle = .70 - smooth(progress / 3) * (backgroundMode ? .12 : .22) + drift * .015;
    const distance = backgroundMode ? (camera.aspect < .88 ? 17.3 : camera.aspect < 1.25 ? 14.7 : 12.9) : camera.aspect < .88 ? 12.7 : camera.aspect < 1.25 ? 11.6 : 10.4;
    camera.position.set(Math.sin(angle) * distance, 3.8 + greenery * (backgroundMode ? .35 : .85), Math.cos(angle) * distance);
    camera.lookAt(0, .67, 0);
    car.rotation.y = -.10 + Math.sin(progress * 1.6) * (backgroundMode ? .035 : .065) + drift * .008;
    car.position.y = inView ? Math.sin(time * .0005) * .008 : 0;
    wheels.forEach(wheel => wheel.rotation.z = -progress * .9);
    ring.material.opacity = .10 + greenery * .13;
    const active = Math.round(progress);
    if (active !== label) { label = active; if (caption) caption.textContent = labels[active]; stage.dataset.story = String(active); }
    renderer.render(scene, camera);
    // Background enhancement crossfades gently after loading, even on a short app tab.
    const reveal = backgroundMode ? smooth(revealElapsed / 1.4) : smooth((progress - .12) / .38);
    canvas.hidden = reveal <= 0; canvas.style.opacity = String(reveal);
    if (fallback) { fallback.hidden = reveal >= 1; fallback.style.opacity = String(1 - reveal); }
    if (!started) { started = true; stage.dataset.scene = 'ready'; }
  }
  function setVisible(value) {
    inView = value;
    if (disposed) return;
    renderer.setAnimationLoop(value ? renderFrame : null);
    if (value) { previousFrame = 0; updateScroll(); renderFrame(performance.now()); }
  }
  const resizer = new ResizeObserver(resize); resizer.observe(stage);
  const viewObserver = backgroundMode ? new MutationObserver(updateScroll) : null;
  if (viewObserver) document.querySelectorAll('.view[id^="view-"]').forEach(view => viewObserver.observe(view, { attributes: true, attributeFilter: ['hidden'] }));
  window.addEventListener('scroll', updateScroll, { passive: true });
  function contextLost(event) { event.preventDefault(); stopped = true; stopScene(); staticView(); }
  canvas.addEventListener('webglcontextlost', contextLost);
  resize();
  return {
    setVisible,
    dispose() {
      disposed = true; renderer.setAnimationLoop(null); resizer.disconnect(); viewObserver?.disconnect();
      window.removeEventListener('scroll', updateScroll); canvas.removeEventListener('webglcontextlost', contextLost);
      logoImage.onload = null; logoImage.src = '';
      geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose()); textures.forEach(texture => texture.dispose());
      // Keep the canvas context reusable if the visitor changes their motion preference.
      renderer.dispose();
    }
  };
}

function stopScene() { generation++; controller?.dispose(); controller = null; }
function motionChanged() { if (motion.matches) { stopScene(); staticView(); } else enhance(); }
function visibilityChanged() { controller?.setVisible(visible && !document.hidden); }
if (canvas && stage) {
  staticView();
  const observer = new IntersectionObserver(entries => {
    visible = entries.some(entry => entry.isIntersecting);
    if (visible) enhance();
    controller?.setVisible(visible && !document.hidden);
  }, { rootMargin: '160px' });
  observer.observe(stage);
  motion.addEventListener('change', motionChanged);
  document.addEventListener('visibilitychange', visibilityChanged);
  // Preserve the scene during the browser's back-forward cache; release GPU resources on a true exit.
  window.addEventListener('pagehide', event => { if (!event.persisted) { stopped = true; stopScene(); observer.disconnect(); motion.removeEventListener('change', motionChanged); document.removeEventListener('visibilitychange', visibilityChanged); } else controller?.setVisible(false); });
  window.addEventListener('pageshow', () => { if (!stopped) visibilityChanged(); });
}
