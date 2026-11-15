// FlameWatch 3D habitat scene (Three.js, low-poly).
// One scene per habitat preset; it reacts to the same readings as the rest of the page.
// app.js calls window.FW3D.update(state). If WebGL isn't available, the 2D drawing stays.
import * as THREE from "./vendor/three.module.min.js";

const host = document.getElementById("scene3d");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function boot() {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch {
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 2, 0.1, 400);
  const look = new THREE.Vector3(0, 0.35, 0);

  // ---------- shared helpers ----------
  const mat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, flatShading: true, roughness: 0.85, metalness: 0.05, ...extra });
  const rng = (() => { let s = 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();

  // Soft round sprite texture for smoke and CO2.
  const puff = (() => {
    const c = document.createElement("canvas"); c.width = c.height = 64;
    const g = c.getContext("2d"); const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.5, "rgba(255,255,255,.55)"); gr.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();

  // ---------- lights ----------
  scene.add(new THREE.HemisphereLight(0xbcd0ff, 0x1a2133, 1.1));
  const sun = new THREE.DirectionalLight(0xfff3e0, 2.2);
  sun.position.set(8, 6, 5);
  scene.add(sun);

  // ---------- sky ----------
  const stars = (() => {
    const g = new THREE.BufferGeometry(), p = [];
    for (let i = 0; i < 500; i++) {
      const v = new THREE.Vector3(rng() - 0.5, rng() * 0.9 + 0.05, rng() - 0.5).normalize().multiplyScalar(150);
      if (v.z > 20) v.z *= -1;   // keep stars behind the scene
      p.push(v.x, v.y, v.z);
    }
    g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
    return new THREE.Points(g, new THREE.PointsMaterial({ color: 0xdfe8ff, size: 0.55, sizeAttenuation: true }));
  })();
  scene.add(stars);

  function planet(radius, detail, sea, land, landShare, seed) {
    const g = new THREE.IcosahedronGeometry(radius, detail);
    const col = [], pos = g.attributes.position, a = new THREE.Color(sea), b = new THREE.Color(land), w = new THREE.Color(0xf2f6ff);
    for (let i = 0; i < pos.count; i += 3) {
      const y = pos.getY(i) / radius;
      const n = Math.sin(pos.getX(i) * seed) * Math.cos(pos.getZ(i) * seed * 1.3) + Math.sin(pos.getY(i) * seed * 0.7);
      const c = Math.abs(y) > 0.94 ? w : n > 1 - landShare * 2 ? b : a;
      for (let k = 0; k < 3; k++) col.push(c.r, c.g, c.b);
    }
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    return new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 1 }));
  }

  function moonGround() {
    const g = new THREE.PlaneGeometry(90, 90, 46, 46);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position;
    const craters = [[-6, -9, 3], [9, -14, 4.5], [-15, -4, 2.5], [5, 6, 2], [16, 2, 3.5], [-4, -22, 6]];
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), z = pos.getZ(i);
      let y = (rng() - 0.5) * 0.25 + Math.sin(x * 0.15) * 0.3 + Math.cos(z * 0.12) * 0.3;
      for (const [cx, cz, r] of craters) {
        const d = Math.hypot(x - cx, z - cz) / r;
        if (d < 1) y -= (1 - d * d) * r * 0.25; else if (d < 1.4) y += (1.4 - d) * r * 0.15;
      }
      if (Math.hypot(x, z) < 4) y *= 0.2;   // flat pad under the habitat
      pos.setY(i, y - 1.55);
    }
    g.computeVertexNormals();
    return new THREE.Mesh(g, mat(0x6f7584, { roughness: 1 }));
  }

  // ---------- habitat module (cutaway cylinder) ----------
  const hullMat = mat(0xd5dceb, { side: THREE.DoubleSide, metalness: 0.25, roughness: 0.6 });
  const innerMat = mat(0x3a4c72, { side: THREE.BackSide });

  function makeModule({ len = 4.4, r = 1.1, legs = true } = {}) {
    const g = new THREE.Group();
    // Cut away the front-top of the hull so we can see inside.
    const cut = 1.9, start = 1.25;
    const hullGeo = new THREE.CylinderGeometry(r, r, len, 28, 1, true, start, Math.PI * 2 - cut);
    hullGeo.rotateZ(Math.PI / 2);
    g.add(new THREE.Mesh(hullGeo, hullMat));
    const innerGeo = new THREE.CylinderGeometry(r * 0.97, r * 0.97, len, 28, 1, true, start, Math.PI * 2 - cut);
    innerGeo.rotateZ(Math.PI / 2);
    g.add(new THREE.Mesh(innerGeo, innerMat));
    for (const x of [-len / 2, -len / 6, len / 6, len / 2]) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(r * 1.01, 0.04, 6, 32), mat(0x9aa8c2, { metalness: 0.4 }));
      ring.rotation.y = Math.PI / 2; ring.position.x = x;
      g.add(ring);
    }
    // End caps (solid domes)
    for (const s of [-1, 1]) {
      const cap = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2), hullMat);
      cap.rotation.z = -s * Math.PI / 2; cap.position.x = s * len / 2;
      cap.scale.set(1, 0.38, 1);   // local y is the dome's axis, so this flattens it along x
      g.add(cap);
    }
    // Floor
    const floor = new THREE.Mesh(new THREE.BoxGeometry(len - 0.1, 0.06, r * 1.5), mat(0x55688f));
    floor.position.y = -r * 0.62; g.add(floor);
    if (legs) {
      for (const x of [-len * 0.32, len * 0.32]) for (const z of [-0.6, 0.6]) {
        const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.08, 0.9, 6), mat(0x7a879f, { metalness: 0.5 }));
        leg.position.set(x, -r - 0.15, z); leg.rotation.z = Math.sign(x) * 0.18; g.add(leg);
        const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.22, 0.05, 10), mat(0x7a879f));
        foot.position.set(x + Math.sign(x) * 0.08, -r - 0.58, z); g.add(foot);
      }
    }
    g.userData = { len, r };
    return g;
  }

  // ---------- inside the module: racks, crew, fire, smoke, CO2 ----------
  function makeInterior(mod) {
    const { len, r } = mod.userData;
    const floorY = -r * 0.62 + 0.03;
    const parts = {};
    const rack = (x, w, color = 0x2c3e64) => {
      const b = new THREE.Mesh(new THREE.BoxGeometry(w, 1.05, 0.45), mat(color));
      b.position.set(x, floorY + 0.52, -r * 0.52); mod.add(b);
      for (let i = 1; i < 3; i++) {
        const shelf = new THREE.Mesh(new THREE.BoxGeometry(w + 0.02, 0.03, 0.47), mat(0x8fa2c6));
        shelf.position.set(x, floorY + i * 0.35, -r * 0.52 + 0.01); mod.add(shelf);
      }
      return b;
    };
    rack(-0.55, 0.7);
    rack(len * 0.33, 0.8);
    // The overheating rack: a cable bundle that glows with heat
    const fx = len * 0.06;
    rack(fx, 0.62, 0x22324f);
    parts.cables = [];
    const cableMat = mat(0xc27a12, { emissive: 0xff5a1f, emissiveIntensity: 0 });
    for (let i = 0; i < 5; i++) {
      const c = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.9, 5), cableMat);
      c.position.set(fx - 0.2 + i * 0.1, floorY + 0.52, -r * 0.27); mod.add(c);
    }
    parts.cableMat = cableMat;

    // Astronaut
    const crew = new THREE.Group();
    const white = mat(0xf3f5fa), visor = mat(0xd4a017, { metalness: 0.8, roughness: 0.25 });
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.17, 0.32, 4, 8), white); body.position.y = 0.42; crew.add(body);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.15, 12, 10), white); head.position.y = 0.82; crew.add(head);
    const vis = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 8, -0.9, 1.8, 0.9, 1.0), visor); vis.position.set(0, 0.83, 0.05); crew.add(vis);
    const pack = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.34, 0.12), mat(0xc9d1df)); pack.position.set(0, 0.5, -0.17); crew.add(pack);
    for (const s of [-1, 1]) {
      const leg = new THREE.Mesh(new THREE.CapsuleGeometry(0.06, 0.18, 3, 6), white); leg.position.set(s * 0.08, 0.1, 0); crew.add(leg);
    }
    crew.position.set(-len / 2 + 0.85, floorY, 0.05);
    crew.rotation.y = 0.5;
    mod.add(crew);
    parts.crew = crew; parts.crewHome = crew.position.x; parts.crewOut = -len / 2 - 1.3;

    // Hatch on the left end cap
    const hatch = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.08, 18), mat(0xaab8d2, { metalness: 0.5 }));
    hatch.rotation.z = Math.PI / 2;
    hatch.position.set(-len / 2 - r * 0.4, -0.05, 0);
    mod.add(hatch);
    const frame = new THREE.Mesh(new THREE.TorusGeometry(0.54, 0.05, 6, 20), mat(0x5b6b8c, { metalness: 0.4 }));
    frame.rotation.y = Math.PI / 2; frame.position.set(-len / 2 - r * 0.4, -0.05, 0); mod.add(frame);
    parts.hatch = hatch; parts.hatchY = { open: 0.95, closed: -0.05 };

    // Vent on the roof with a flap
    const vx = len * 0.33;
    const vent = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.12, 0.45), mat(0x5b6b8c)); vent.position.set(vx, r * 0.98, -0.2); mod.add(vent);
    const flapPivot = new THREE.Group(); flapPivot.position.set(vx - 0.3, r * 1.06, -0.2); mod.add(flapPivot);
    const flap = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.04, 0.45), mat(0xc6d1e5, { metalness: 0.4 })); flap.position.x = 0.3; flapPivot.add(flap);
    parts.flap = flapPivot;
    // Airflow streaks (visible while the vent is open)
    const flowMat = new THREE.MeshBasicMaterial({ color: 0x8fb6ff, transparent: true, opacity: 0.5 });
    parts.flow = [];
    for (let i = 0; i < 6; i++) {
      const s = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.18, 0.02), flowMat);
      s.userData.phase = i / 6; mod.add(s); parts.flow.push(s);
    }
    parts.flowMat = flowMat; parts.vent = { x: vx, y: r * 0.9, z: -0.2 };

    // Warning beacon on the roof
    const beaconMat = new THREE.MeshStandardMaterial({ color: 0x4cd38a, emissive: 0x4cd38a, emissiveIntensity: 1.2 });
    const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 8), beaconMat); beacon.position.set(-0.3, r * 1.06, -0.25); mod.add(beacon);
    const beaconLight = new THREE.PointLight(0x4cd38a, 0.6, 3); beaconLight.position.copy(beacon.position); mod.add(beaconLight);
    parts.beaconMat = beaconMat; parts.beaconLight = beaconLight;

    // Fire on the cable rack
    const fire = new THREE.Group();
    const outer = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.75, 7), new THREE.MeshBasicMaterial({ color: 0xff7a2f, transparent: true, opacity: 0.92 }));
    outer.position.y = 0.37;
    const inner = new THREE.Mesh(new THREE.ConeGeometry(0.11, 0.45, 6), new THREE.MeshBasicMaterial({ color: 0xffe08a }));
    inner.position.y = 0.23;
    fire.add(outer, inner);
    fire.position.set(fx, floorY + 0.2, -r * 0.18);
    fire.scale.setScalar(0.001);
    mod.add(fire);
    const fireLight = new THREE.PointLight(0xff7a2f, 0, 6, 1.5); fireLight.position.set(fx, floorY + 0.7, 0); mod.add(fireLight);
    parts.fire = fire; parts.fireLight = fireLight;

    // Smoke puffs, gathered under the ceiling
    parts.smoke = [];
    const smokeMat = new THREE.SpriteMaterial({ map: puff, color: 0x9ea7b6, transparent: true, opacity: 0, depthWrite: false });
    for (let i = 0; i < 34; i++) {
      const s = new THREE.Sprite(smokeMat);
      const base = new THREE.Vector3((rng() - 0.5) * (len - 0.6), r * 0.15 + rng() * r * 0.6, (rng() - 0.6) * r * 1.0);
      s.position.copy(base); s.scale.setScalar(0.7 + rng() * 0.6);
      s.userData = { base, phase: rng() * Math.PI * 2 };
      mod.add(s); parts.smoke.push(s);
    }
    parts.smokeMat = smokeMat;

    // CO2 spray from a ceiling nozzle
    const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.08, 0.14, 8), mat(0x7a879f)); nozzle.position.set(-len * 0.12, r * 0.9, -0.25); mod.add(nozzle);
    parts.co2 = [];
    const co2Mat = new THREE.SpriteMaterial({ map: puff, color: 0xe2f1ff, transparent: true, opacity: 0, depthWrite: false });
    for (let i = 0; i < 40; i++) {
      const s = new THREE.Sprite(co2Mat);
      s.userData = { dir: new THREE.Vector3((rng() - 0.5) * 2.2, -0.8 - rng(), (rng() - 0.5) * 1.4), phase: rng() };
      s.scale.setScalar(0.35); mod.add(s); parts.co2.push(s);
    }
    parts.co2Mat = co2Mat; parts.nozzle = nozzle.position.clone();
    return parts;
  }

  // ---------- environments ----------
  const envs = {};

  function moonEnv({ rover = false } = {}) {
    const root = new THREE.Group();
    root.add(moonGround());
    const earth = planet(4.5, 3, 0x2d6cdf, 0x4cae6e, 0.35, 0.9); earth.position.set(-38, 15, -64); root.add(earth);
    let mod;
    if (rover) {
      mod = makeModule({ len: 3.4, r: 0.95, legs: false });
      mod.position.y = 0.05;
      for (const x of [-1.15, 0, 1.15]) for (const z of [-0.95, 0.95]) {
        const w = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.3, 12), mat(0x2b3240));
        w.rotation.x = Math.PI / 2; w.position.set(x, -1.05, z); mod.add(w);
        const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.32, 8), mat(0xaab4c8, { metalness: 0.5 }));
        hub.rotation.x = Math.PI / 2; hub.position.copy(w.position); mod.add(hub);
      }
      const chassis = new THREE.Mesh(new THREE.BoxGeometry(3.3, 0.18, 1.6), mat(0x8a96ad, { metalness: 0.4 }));
      chassis.position.y = -0.92; mod.add(chassis);
      const lamp = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.12, 0.3), new THREE.MeshBasicMaterial({ color: 0xfff1c2 }));
      lamp.position.set(2.18, -0.35, 0.4); mod.add(lamp);
    } else {
      mod = makeModule();
      // a few props: a flag and a solar panel on the ground
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.6, 6), mat(0xd9dee8)); pole.position.set(-4.2, -0.75, -1.2); root.add(pole);
      const flag = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.38, 0.02), mat(0xe9eef7)); flag.position.set(-3.88, -0.13, -1.2); root.add(flag);
      const panel = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.05, 1.0), mat(0x1f3d7a, { metalness: 0.6, roughness: 0.3 }));
      panel.position.set(4.6, -0.75, -1.8); panel.rotation.set(0.5, -0.4, 0); root.add(panel);
      const stand = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.8, 6), mat(0x9aa8c2)); stand.position.set(4.6, -1.15, -1.8); root.add(stand);
    }
    root.add(mod);
    return { root, mod, parts: makeInterior(mod), cam: rover ? [4.6, 1.2, 6.6] : [5.2, 1.3, 7.4], lookY: 0.45 };
  }

  function orbitEnv() {
    const root = new THREE.Group();
    const earth = planet(46, 5, 0x2559c4, 0x46a86a, 0.4, 0.12); earth.position.set(-6, -58, -40); root.add(earth);
    const atmo = new THREE.Mesh(new THREE.SphereGeometry(47.4, 64, 40), new THREE.MeshBasicMaterial({ color: 0x8fb6ff, transparent: true, opacity: 0.12, side: THREE.BackSide }));
    atmo.position.copy(earth.position); root.add(atmo);
    const mod = makeModule({ legs: false });
    mod.position.y = 0.3;
    // Truss and solar arrays
    const truss = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.18, 6), mat(0xb8c2d6, { metalness: 0.5 })); truss.position.set(0, 0.2, -3.6); mod.add(truss);
    for (const z of [-3.2, -5.8]) {
      for (const x of [-1.1, 1.1]) {
        const wing = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.03, 2.4), mat(0x1d3f86, { metalness: 0.6, roughness: 0.3, emissive: 0x0a1a3a }));
        wing.position.set(x * 1.2, 0.2, z); wing.rotation.x = 0.35; mod.add(wing);
      }
    }
    const radiator = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.02, 0.8), mat(0xe9eef7)); radiator.position.set(0, -0.6, -2.7); mod.add(radiator);
    root.add(mod);
    return { root, mod, parts: makeInterior(mod), cam: [5.4, 1.5, 8.2], float: true, lookY: 0.2 };
  }

  function suitEnv() {
    const root = new THREE.Group();
    root.add(moonGround());
    const earth = planet(4.5, 3, 0x2d6cdf, 0x4cae6e, 0.35, 0.9); earth.position.set(-30, 13, -60); root.add(earth);
    // A big astronaut. The "module" for fire effects is the suit itself.
    const astro = new THREE.Group();
    const white = mat(0xf3f5fa), visor = mat(0xd4a017, { metalness: 0.85, roughness: 0.2 });
    const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.55, 0.7, 4, 10), white); torso.position.y = 0.55; astro.add(torso);
    const helmet = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 12), white); helmet.position.y = 1.6; astro.add(helmet);
    const vis = new THREE.Mesh(new THREE.SphereGeometry(0.4, 16, 10, -1, 2, 0.9, 1.1), visor); vis.position.set(0, 1.62, 0.16); astro.add(vis);
    const pack = new THREE.Mesh(new THREE.BoxGeometry(0.9, 1.1, 0.45), mat(0xc9d1df)); pack.position.set(0, 0.75, -0.62); astro.add(pack);
    for (const s of [-1, 1]) {
      const arm = new THREE.Mesh(new THREE.CapsuleGeometry(0.16, 0.6, 4, 8), white); arm.position.set(s * 0.72, 0.6, 0.05); arm.rotation.z = s * 0.25; astro.add(arm);
      const leg = new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 0.55, 4, 8), white); leg.position.set(s * 0.25, -0.45, 0); astro.add(leg);
      const boot = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.18, 0.45), mat(0x8a93a6)); boot.position.set(s * 0.25, -0.92, 0.06); astro.add(boot);
    }
    const panel = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.3, 0.14), mat(0x5b6b8c)); panel.position.set(0, 0.75, 0.55); astro.add(panel);
    astro.position.y = -0.5; astro.rotation.y = 1.75;
    root.add(astro);
    // Fire and smoke around the backpack's oxygen supply
    const parts = {};
    const fire = new THREE.Group();
    const outer = new THREE.Mesh(new THREE.ConeGeometry(0.28, 0.9, 7), new THREE.MeshBasicMaterial({ color: 0xff7a2f, transparent: true, opacity: 0.92 })); outer.position.y = 0.45;
    const inner = new THREE.Mesh(new THREE.ConeGeometry(0.14, 0.55, 6), new THREE.MeshBasicMaterial({ color: 0xffe08a })); inner.position.y = 0.28;
    fire.add(outer, inner); fire.position.set(0, 1.25, -0.7); fire.scale.setScalar(0.001); astro.add(fire);
    const fireLight = new THREE.PointLight(0xff7a2f, 0, 6, 1.5); fireLight.position.set(0, 1.4, -0.4); astro.add(fireLight);
    parts.fire = fire; parts.fireLight = fireLight;
    parts.smoke = [];
    const smokeMat = new THREE.SpriteMaterial({ map: puff, color: 0x9ea7b6, transparent: true, opacity: 0, depthWrite: false });
    for (let i = 0; i < 20; i++) {
      const s = new THREE.Sprite(smokeMat);
      const base = new THREE.Vector3((rng() - 0.5) * 1.4, 1.6 + rng() * 1.4, -0.8 + (rng() - 0.5));
      s.position.copy(base); s.scale.setScalar(0.7 + rng() * 0.5); s.userData = { base, phase: rng() * 6 };
      astro.add(s); parts.smoke.push(s);
    }
    parts.smokeMat = smokeMat;
    const beaconMat = new THREE.MeshStandardMaterial({ color: 0x4cd38a, emissive: 0x4cd38a, emissiveIntensity: 1.2 });
    const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 8), beaconMat); beacon.position.set(0.15, 0.85, 0.63); astro.add(beacon);
    parts.beaconMat = beaconMat;
    return { root, mod: astro, parts, cam: [3.4, 1.2, 6.2], lookY: 0.55, suit: true };
  }

  const builders = { moonbase: () => moonEnv(), moon_alt: () => moonEnv(), rover: () => moonEnv({ rover: true }), iss: orbitEnv, suit: suitEnv };
  let env = null, envKey = null;

  function setScenario(key) {
    if (!builders[key]) key = "moonbase";
    if (key === envKey) return;
    if (env) scene.remove(env.root);
    env = envs[key] || (envs[key] = builders[key]());
    envKey = key;
    scene.add(env.root);
    document.querySelector('.scene-tags')?.classList.toggle('suit', !!env.suit);
    look.set(0, env.lookY ?? 0.3, 0);
    cam.base.set(...env.cam);
  }

  // ---------- state from the page ----------
  const want = { smoke: 0, fire: 0, heat: 0, ventOpen: 1, crewIn: 1, hatchOpen: 1, co2: 0, level: "green" };
  const now = { smoke: 0, fire: 0, heat: 0, ventOpen: 1, crewIn: 1, hatchOpen: 1, co2: 0 };
  const LEVEL_COLOR = { green: 0x4cd38a, yellow: 0xf2a900, red: 0xff3b4e };

  function update(s) {
    setScenario(s.scenario);
    const box = s.box || {};
    want.smoke = Math.min(1, (s.smoke || 0) / 90);
    want.fire = s.flame ? 1 : 0;
    want.heat = s.flame || box.heat_detected ? 1 : 0;
    want.ventOpen = box.vent === "closed" ? 0 : 1;
    want.crewIn = (box.crew ?? true) ? 1 : 0;
    want.hatchOpen = box.hatch_closed ? 0 : 1;
    want.co2 = box.mode === "suppressing" ? 1 : 0;
    want.level = s.risk.level;
  }

  // ---------- camera: gentle sway + follows the pointer ----------
  const cam = { base: new THREE.Vector3(6, 2.6, 8.6), px: 0, py: 0 };
  host.addEventListener("pointermove", (e) => {
    const r = host.getBoundingClientRect();
    cam.px = ((e.clientX - r.left) / r.width - 0.5) * 2;
    cam.py = ((e.clientY - r.top) / r.height - 0.5) * 2;
  });
  host.addEventListener("pointerleave", () => { cam.px = cam.py = 0; });

  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // Narrow screens: pull back so the whole module stays in frame.
    camera.fov = w / h < 1.6 ? 44 : 34;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(host);

  let visible = true;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(host);

  const clock = new THREE.Clock();
  const ease = (k, dt) => 1 - Math.exp(-k * dt);
  function frame() {
    requestAnimationFrame(frame);
    if (!visible || !env) return;
    const dt = Math.min(0.05, clock.getDelta()), t = clock.elapsedTime;
    for (const k of ["smoke", "fire", "heat", "ventOpen", "crewIn", "hatchOpen", "co2"]) now[k] += (want[k] - now[k]) * ease(k === "crewIn" ? 1.2 : 2.5, dt);
    const p = env.parts;

    // camera
    const sway = reduceMotion ? 0 : Math.sin(t * 0.18) * 0.6;
    camera.position.set(env.cam[0] + sway + cam.px * 1.2, env.cam[1] - cam.py * 0.6, env.cam[2]);
    camera.lookAt(look);
    if (env.float && !reduceMotion) { env.mod.position.y = 0.3 + Math.sin(t * 0.6) * 0.06; env.mod.rotation.z = Math.sin(t * 0.4) * 0.015; }

    // fire
    const f = Math.max(0.001, now.fire);
    const flick = reduceMotion ? 1 : 1 + Math.sin(t * 23) * 0.08 + Math.sin(t * 37) * 0.05;
    p.fire.scale.set(f * (2 - flick), f * flick, f * (2 - flick));
    p.fireLight.intensity = now.fire * 9 * flick;
    if (p.cableMat) p.cableMat.emissiveIntensity = now.heat * 1.4;

    // smoke
    p.smokeMat.opacity = now.smoke * 0.9;
    for (const s of p.smoke) {
      const u = s.userData;
      s.position.x = u.base.x + (reduceMotion ? 0 : Math.sin(t * 0.4 + u.phase) * 0.15);
      s.position.y = u.base.y + (reduceMotion ? 0 : Math.sin(t * 0.3 + u.phase * 2) * 0.05);
    }

    // beacon
    const pulse = want.level === "red" && !reduceMotion ? 0.6 + Math.sin(t * 9) * 0.6 : 1.2;
    p.beaconMat.color.setHex(LEVEL_COLOR[want.level]); p.beaconMat.emissive.setHex(LEVEL_COLOR[want.level]);
    p.beaconMat.emissiveIntensity = Math.max(0.2, pulse);
    if (p.beaconLight) { p.beaconLight.color.setHex(LEVEL_COLOR[want.level]); p.beaconLight.intensity = Math.max(0.1, pulse) * (want.level === "green" ? 0.4 : 1.6); }

    if (p.crew) {
      // crew walks out through the hatch
      p.crew.position.x = p.crewOut + (p.crewHome - p.crewOut) * now.crewIn;
      p.crew.visible = now.crewIn > 0.04;
      p.crew.rotation.y = now.crewIn > 0.97 ? 0.5 : -Math.PI / 2;
      if (now.crewIn < 0.97 && now.crewIn > 0.04 && !reduceMotion) p.crew.position.y = -env.mod.userData.r * 0.62 + 0.03 + Math.abs(Math.sin(t * 9)) * 0.04;
      // hatch slides up when open
      p.hatch.position.y = p.hatchY.closed + (p.hatchY.open - p.hatchY.closed) * now.hatchOpen;
      // vent flap and airflow
      p.flap.rotation.z = now.ventOpen * 0.75;
      p.flowMat.opacity = now.ventOpen * 0.55;
      for (const s of p.flow) {
        const k = (t * 0.6 + s.userData.phase) % 1;
        s.position.set(p.vent.x - 0.25 + s.userData.phase * 0.5 - k * 0.6, p.vent.y - k * 1.2, p.vent.z + 0.2);
      }
      // CO2 spray
      p.co2Mat.opacity = now.co2 * 0.6;
      for (const s of p.co2) {
        const k = (t * 0.7 + s.userData.phase) % 1;
        s.position.copy(p.nozzle).addScaledVector(s.userData.dir, k * 0.9);
        s.scale.setScalar(0.2 + k * 0.7);
      }
    }
    renderer.render(scene, camera);
  }

  setScenario("moonbase");
  resize();
  frame();
  return { update, setScenario };
}

const api = host && boot();
if (api) {
  window.FW3D = api;
  document.documentElement.classList.add("has-3d");
  if (window.__fwState) api.update(window.__fwState);
}
