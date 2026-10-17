// Village / House 3D — float-above Craft Mode (outdoor) + cutaway room (indoor).
// Orbit 360°, zoom, pan. Cyan footprint grid for placement (matches in-game Customization).
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const BASE = "game/craft3d/";
const MAP_BASE = "game/map3d/";
const loader = new GLTFLoader();
const buffers = new Map();
const texCache = new Map();
let manifest = null, materials = {}, renderer = null, scene = null, cam = null, ctl = null, host = null;
let islandEnv = null;
let root = null, room = null, terrain = null, terrainMesh = null, cursor = null, gridHelper = null;
let onSelect = null, onPlace = null, onMove = null, selected = null, mode = "indoor";
let placeSize = { w: 1, d: 1 }, bounds = null, rayPlane = null, roomCell = 0.5;
let roomHalf = { x: 2.75, z: 2.75 };
let pointerDown = null, drag = null;
let terrainTool = null; // null | 'raise' | 'lower'

/**
 * UE Location (cm) → Three.js meters.
 * Outdoor Base Camp: +X east, -Z north (ruins/bridge), +Z south (ocean) — matches
 * the map-art plane after the ground texture's V-up → −Z mapping.
 * Indoor My House keeps the legacy (X, Z-up, Y→Z) path used by the cutaway remap.
 */
function ueToThree(loc, outdoor = false) {
  if (outdoor) {
    return new THREE.Vector3(loc[0] / 100, loc[2] / 100, -(loc[1] / 100));
  }
  return new THREE.Vector3(loc[0] / 100, loc[2] / 100, loc[1] / 100);
}
function threeToUeXZ(x, z, outdoor = false) {
  if (outdoor) return { x: x * 100, y: -z * 100 };
  return { x: x * 100, y: z * 100 };
}
function yawToQuat(rot, outdoor = false) {
  // Craft house/guild glTFs put the door on local +X (not +Z). After outdoor
  // Z=−Y, saveYaw 0 faces south (+Z) toward the pad — Three Y rot = −90° − saveYaw.
  // Thatched yaw 90 → west (toward guild); islander 180 → north; guild 0 → south.
  // Indoor cutaway still uses −saveYaw (furniture gets +90 at remap time).
  const yawDeg = outdoor ? -90 - (rot?.[1] || 0) : -(rot?.[1] || 0);
  const yaw = THREE.MathUtils.degToRad(yawDeg);
  return new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
}

/** Wallpaper atlas: 16 vertical slats, chevron crown at V=1, wainscot at V=0. */
const WALL_SLAT_BASE = 16;
const WALL_TARGET_SLATS = 11; // ~10–12 broad slats across the back wall in-game

function craftTex(rel, colorSpace = THREE.SRGBColorSpace, base = BASE) {
  if (!rel) return null;
  const key = `${base}|${rel}|${colorSpace}`;
  if (!texCache.has(key)) {
    const t = new THREE.TextureLoader().load(base + rel);
    t.colorSpace = colorSpace;
    t.anisotropy = 8;
    t.flipY = false;
    texCache.set(key, t);
  }
  return texCache.get(key);
}

/** Resolve craft3d material def; tolerate glTF name suffixes (mat_foo.001). */
function craftMatDef(name) {
  if (!name) return null;
  const key = String(name).toLowerCase();
  if (materials[key]?.tex) return materials[key];
  const bare = key.replace(/\.\d+$/, "");
  if (materials[bare]?.tex) return materials[bare];
  // Last resort: unique substring match on mat_cft…
  const hit = Object.keys(materials).find((k) => k.includes(bare) || bare.includes(k));
  return hit ? materials[hit] : null;
}

/** CUE4Parse glTFs name materials but leave PBR empty — bind Diff_Texture from craft3d/map3d build. */
function paintCraft(root, texBase = BASE) {
  let paintedN = 0, missed = [];
  root.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const painted = mats.map((src) => {
      if (!src) return src;
      const def = craftMatDef(src.name);
      if (!def?.tex) {
        if (src.name) missed.push(src.name);
        // Empty PBR reads as white — tint so missed binds are obvious in debug.
        return new THREE.MeshBasicMaterial({ color: 0xc4a574, name: src.name || "miss" });
      }
      const map = craftTex(def.tex, THREE.SRGBColorSpace, texBase);
      // Unlit diffuse — game craft mats are toon-baked; PBR+normals wash them to mud.
      const mat = new THREE.MeshBasicMaterial({
        map,
        name: src.name,
        transparent: /\bgrass\b|_glass/i.test(src.name || ""),
        alphaTest: /\bgrass\b/i.test(src.name || "") ? 0.35 : 0,
      });
      if (map && !map.image) {
        map.addEventListener("update", () => { mat.needsUpdate = true; });
      }
      paintedN++;
      return mat;
    });
    o.material = Array.isArray(o.material) ? painted : painted[0];
    o.castShadow = true;
    o.receiveShadow = true;
  });
  if (missed.length && typeof console !== "undefined") {
    console.warn("village3d: no Diff for", [...new Set(missed)].slice(0, 8),
      `(painted ${paintedN}, materials ${Object.keys(materials).length})`);
  }
}

async function glb(rel, base = BASE) {
  const key = `${base}|${rel}`;
  if (!buffers.has(key)) {
    buffers.set(key, fetch(base + rel).then(async (r) => {
      if (!r.ok) throw new Error(`mesh ${rel} HTTP ${r.status}`);
      return r.arrayBuffer();
    }));
  }
  const g = await loader.parseAsync((await buffers.get(key)).slice(0), base);
  const node = g.scene || g.scenes[0];
  paintCraft(node, base);
  return node;
}

/** Base Camp env chunks (Map_000100) — world-baked glTFs under game/map3d/. */
async function loadIslandEnv() {
  if (islandEnv) {
    scene.remove(islandEnv);
    clearGroup(islandEnv);
    islandEnv = null;
  }
  let raw;
  try {
    raw = await fetch(MAP_BASE + "manifest.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : null));
  } catch { return null; }
  if (!raw?.placements?.length) return null;
  Object.assign(materials, raw.materials || {});
  const group = new THREE.Group();
  group.name = "islandEnv";
  // Meshes are Y-up meters with world-baked XZ. Outdoor craft uses Z=−UE_Y;
  // CUE4Parse glTF keeps +Z ≈ +UE_Y — mirror Z so north matches craft/houses.
  group.scale.set(1, 1, -1);
  for (const p of raw.placements) {
    try {
      const node = await glb(p.mesh, MAP_BASE);
      node.position.set(p.location?.[0] || 0, p.location?.[1] || 0, p.location?.[2] || 0);
      group.add(node);
    } catch (err) {
      console.warn("village3d: island mesh failed", p.mesh, err);
    }
  }
  islandEnv = group;
  scene.add(group);
  return group;
}

function mkCanvasTex(draw, w = 256, h = 256) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

function herringboneTex() {
  // Screenshot 220942: warm honey parquet — soft tone steps + dark seams (wood, not tiles).
  return mkCanvasTex((ctx, w, h) => {
    ctx.fillStyle = "#c99658";
    ctx.fillRect(0, 0, w, h);
    const len = 160, thick = 32;
    // Narrow honey band so it doesn't checker into light/dark tiles
    const tones = ["#f0d6a0", "#ebd09a", "#e6c994", "#e0c28c", "#ebce96", "#e4c690"];
    for (let row = -5; row < (h / thick) + 5; row++) {
      const oddRow = row & 1;
      for (let col = -5; col < (w / len) + 5; col++) {
        const x = col * len + (oddRow ? len / 2 : 0);
        const y = row * thick;
        ctx.save();
        ctx.translate(x + len / 2, y + thick / 2);
        ctx.rotate(oddRow ? Math.PI / 4 : -Math.PI / 4);
        ctx.fillStyle = tones[((row * 5 + col * 2) % tones.length + tones.length) % tones.length];
        ctx.fillRect(-len / 2 + 1, -thick / 2 + 1, len - 2, thick - 2);
        // subtle grain
        ctx.strokeStyle = "rgba(150, 100, 40, 0.14)";
        ctx.lineWidth = 1.25;
        for (let g = -len / 2 + 18; g < len / 2 - 10; g += 18) {
          ctx.beginPath();
          ctx.moveTo(g, -thick / 2 + 6);
          ctx.quadraticCurveTo(g + 4, 0, g + 1, thick / 2 - 6);
          ctx.stroke();
        }
        // plank seam
        ctx.strokeStyle = "rgba(110, 70, 28, 0.42)";
        ctx.lineWidth = 1.8;
        ctx.strokeRect(-len / 2 + 0.5, -thick / 2 + 0.5, len - 1, thick - 1);
        ctx.restore();
      }
    }
  }, 512, 512);
}

function loadShellTex(rel, repeatU = 1, repeatV = 1, {
  wrapS = THREE.RepeatWrapping,
  wrapT = THREE.RepeatWrapping,
} = {}) {
  const t = new THREE.TextureLoader().load(BASE + rel);
  t.wrapS = wrapS;
  t.wrapT = wrapT;
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  t.flipY = true;
  t.repeat.set(repeatU, repeatV);
  return t;
}

function wallpaperTex(wallLenM) {
  // Horizontal: density so ~WALL_TARGET_SLATS span the north wall; scale with length.
  const northLen = 5.5; // typical My House (N−1)×cell visual width
  const slats = WALL_TARGET_SLATS * (wallLenM / northLen);
  const repeatU = Math.max(0.25, slats / WALL_SLAT_BASE);
  // Vertical: clamp — one wallpaper sheet floor→ceiling (chevron at top, wainscot at base).
  return loadShellTex("myhouse_wall.png", repeatU, 1.0, {
    wrapS: THREE.RepeatWrapping,
    wrapT: THREE.ClampToEdgeWrapping,
  });
}

function setup() {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setClearColor(0x87b8e0, 1);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x87b8e0, 40, 120);
  cam = new THREE.PerspectiveCamera(42, 1, 0.05, 400);
  ctl = new OrbitControls(cam, renderer.domElement);
  ctl.enableDamping = true;
  ctl.enablePan = true;
  ctl.enableZoom = true;
  ctl.enableRotate = true;
  ctl.minDistance = 0.8;
  ctl.maxDistance = 90;
  ctl.maxPolarAngle = Math.PI * 0.72; // enough pitch to read island cliffs / skirts
  ctl.minPolarAngle = 0.12;
  scene.add(new THREE.AmbientLight(0xdce9f5, 0.55));
  const sun = new THREE.DirectionalLight(0xfff2d6, 1.35);
  sun.position.set(18, 32, 12);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = 120;
  sun.shadow.camera.left = -55;
  sun.shadow.camera.right = 55;
  sun.shadow.camera.top = 55;
  sun.shadow.camera.bottom = -55;
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x9ec8ef, 0.35);
  fill.position.set(-14, 12, -8);
  scene.add(fill);
  const hemi = new THREE.HemisphereLight(0xb8dfff, 0x8a6a48, 0.35);
  scene.add(hemi);
  const el = renderer.domElement;
  // Capture phase so furniture pick runs before OrbitControls steals the gesture.
  el.addEventListener("pointerdown", onPointerDown, true);
  el.addEventListener("pointermove", onPointerMove, true);
  el.addEventListener("pointerup", onPointerUp, true);
  el.addEventListener("pointercancel", onPointerUp, true);
  window.addEventListener("keydown", (ev) => {
    if (!exploreMode) return;
    exploreKeys.add(ev.code);
  }, { passive: true });
  window.addEventListener("keyup", (ev) => { exploreKeys.delete(ev.code); }, { passive: true });
  el.title = "Drag orbit · scroll zoom · right-drag pan · click place/select";
  (function tick() {
    requestAnimationFrame(tick);
    ctl.update();
    if (host && renderer.domElement.parentNode === host) {
      const w = host.clientWidth || 1, h = host.clientHeight || 1;
      if (renderer.domElement.width !== w || renderer.domElement.height !== h) {
        renderer.setSize(w, h, false);
        cam.aspect = w / h;
        cam.updateProjectionMatrix();
      }
      tickExplore(0.016);
      if (cursor?.visible) {
        const gem = cursor.getObjectByName("placeGem");
        if (gem) { gem.rotation.y += 0.03; gem.position.y = 0.32 + Math.sin(performance.now() * 0.004) * 0.04; }
      }
      if (mode === "outdoor") syncCompassHud();
      renderer.render(scene, cam);
    }
  })();
}

function clearGroup(g) {
  if (!g) return;
  scene.remove(g);
  g.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) {
      if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose());
      else o.material.dispose();
    }
  });
}

/** Wipe cached meshes/materials so Reload rebuilds from the current save. */
function hardReset() {
  if (islandEnv) {
    scene?.remove(islandEnv);
    clearGroup(islandEnv);
    islandEnv = null;
  }
  clearGroup(root);
  root = null;
  clearGroup(terrain);
  terrain = null;
  terrainMesh = null;
  craftTerrain = null;
  clearGroup(room);
  room = null;
  if (cursor) {
    scene?.remove(cursor);
    clearGroup(cursor);
    cursor = null;
  }
  if (explorer) {
    scene?.remove(explorer);
    clearGroup(explorer);
    explorer = null;
  }
  buffers.clear();
  texCache.clear();
  materials = {};
  manifest = null;
  selected = null;
  drag = null;
  exploreMode = false;
  exploreKeys.clear();
}

/** Canvas sprite for a compass letter (world-space N/E/S/W). */
function compassSprite(letter, accent = "#5a3a18") {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "rgba(255,248,230,0.94)";
  ctx.beginPath();
  ctx.arc(64, 64, 58, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#c9a86a";
  ctx.lineWidth = 7;
  ctx.stroke();
  ctx.fillStyle = accent;
  ctx.font = "bold 70px Georgia, serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(letter, 64, 70);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({
    map: tex, transparent: true, depthTest: false, depthWrite: false,
  });
  const s = new THREE.Sprite(mat);
  s.scale.set(5.5, 5.5, 1);
  s.renderOrder = 20;
  s.name = `compass_${letter}`;
  return s;
}

/**
 * World-space N/E/S/W at craft-pad edges.
 * Game outdoor axes (verified): +X east, −Z north, +Z south, −X west.
 */
function attachCompass(parent, b) {
  if (!parent || !b) return;
  const old = parent.getObjectByName("compass");
  if (old) {
    parent.remove(old);
    old.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        o.material.map?.dispose?.();
        o.material.dispose();
      }
    });
  }
  const g = new THREE.Group();
  g.name = "compass";
  const cx = (b.wx0 + b.wx1) / 2;
  const cz = (b.wz0 + b.wz1) / 2;
  const span = Math.max(b.wx1 - b.wx0, b.wz1 - b.wz0);
  const pad = Math.max(6, span * 0.07);
  const marks = [
    { letter: "N", x: cx, z: b.wz0 - pad, color: "#b03030" }, // −Z
    { letter: "S", x: cx, z: b.wz1 + pad, color: "#5a3a18" }, // +Z
    { letter: "E", x: b.wx1 + pad, z: cz, color: "#5a3a18" }, // +X
    { letter: "W", x: b.wx0 - pad, z: cz, color: "#5a3a18" }, // −X
  ];
  for (const m of marks) {
    const s = compassSprite(m.letter, m.color);
    s.position.set(m.x, snapToTerrainY(m.x, m.z) + 3.2, m.z);
    g.add(s);
  }
  // Thin axis guides so the pad reads as oriented, not floating blobs.
  const axisY = snapToTerrainY(cx, cz) + 0.12;
  const mkLine = (a, bpt, color) => {
    const geo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(a.x, axisY, a.z),
      new THREE.Vector3(bpt.x, axisY, bpt.z),
    ]);
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({
      color, transparent: true, opacity: 0.55, depthWrite: false,
    }));
    line.renderOrder = 19;
    g.add(line);
  };
  mkLine({ x: cx, z: b.wz0 - pad }, { x: cx, z: b.wz1 + pad }, 0xb03030); // N–S
  mkLine({ x: b.wx0 - pad, z: cz }, { x: b.wx1 + pad, z: cz }, 0x3a6a9a); // W–E
  parent.add(g);
}

/** Radians: rotate HUD rose so N points toward world north on screen. */
function compassHeadingRad() {
  if (!cam) return 0;
  const fwd = new THREE.Vector3();
  cam.getWorldDirection(fwd);
  fwd.y = 0;
  if (fwd.lengthSq() < 1e-8) return 0;
  fwd.normalize();
  // World north = (0,0,−1). ang = signed angle from view dir → north.
  return Math.atan2(-fwd.x, -fwd.z);
}

function syncCompassHud() {
  const rose = host?.querySelector?.(".vil-compass-rose");
  if (!rose) return;
  rose.style.transform = `rotate(${compassHeadingRad()}rad)`;
}

function buildIndoorRoom(area) {
  clearGroup(terrain);
  terrain = null;
  clearGroup(room);
  room = new THREE.Group();
  bounds = null;
  const cell = (area?.voxel?.[0] || 50) / 100;
  // Visual floor is (N-1)×(N-1): last grid row/col is wall padding. Bucket at (0,10)
  // on a 12×12 area then sits flush in the back-left corner (matches Screenshot 220942).
  const ux = Math.max(1, (area?.width || 12) - 1);
  const uy = Math.max(1, (area?.depth || 12) - 1);
  const w = ux * cell;
  const d = uy * cell;
  // Visual wall height (~2.5m). Craft area Height×voxelZ is the placeable volume, not the shell.
  const h = 2.55;
  // Honey herringbone — chunky boards, ~7–8 chevron peaks across the room (was 1.35 → ×0.25).
  // Tuned slightly lower so the PNG's busy pattern still reads as broad planks.
  const floorRepeat = 1.35 * 0.22;
  const floorMap = new THREE.TextureLoader().load(BASE + "myhouse_floor.png", (t) => {
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(floorRepeat, floorRepeat);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 8;
    t.needsUpdate = true;
  });
  floorMap.wrapS = floorMap.wrapT = THREE.RepeatWrapping;
  floorMap.repeat.set(floorRepeat, floorRepeat);
  floorMap.colorSpace = THREE.SRGBColorSpace;
  const floorMat = new THREE.MeshBasicMaterial({ map: floorMap, color: 0xffffff });
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(w, d), floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  floor.userData.roomFloor = true;
  floor.userData.roomShell = true;
  room.add(floor);

  // Shell: N/E/W — thick fill + interior wallpaper plane (UV0: V=0 floor → V=1 ceiling).
  // South: continuous perimeter sill (no doorway boolean) + exterior threshold walkway.
  const wallT = cell * 0.4;
  const fillMat = new THREE.MeshBasicMaterial({ color: 0x5a4030 });
  const mkWall = (along, hx, hz, rotY) => {
    // Solid thickness (bury edge furniture); wallpaper is a separate inward face.
    const fill = new THREE.Mesh(
      new THREE.BoxGeometry(
        rotY === 0 ? along + wallT * 2 : wallT,
        h,
        rotY === 0 ? wallT : along + wallT * 2,
      ),
      fillMat.clone(),
    );
    fill.position.set(hx, h / 2, hz);
    fill.userData.roomShell = true;
    room.add(fill);

    // PlaneGeometry UV: U along width, V along height (0 at bottom, 1 at top) — no world-height multiply.
    const paper = new THREE.Mesh(
      new THREE.PlaneGeometry(along, h),
      new THREE.MeshBasicMaterial({ map: wallpaperTex(along), side: THREE.DoubleSide }),
    );
    paper.renderOrder = 1;
    // Sit just inside the fill's interior face. Plane default normal = +Z.
    const inward = 0.002;
    if (rotY === 0) {
      // north: face +Z (into room)
      paper.position.set(0, h / 2, -d / 2 + inward);
      paper.rotation.y = 0;
    } else if (rotY > 0) {
      // west: face +X (into room) — yaw −90° takes +Z → +X
      paper.position.set(-w / 2 + inward, h / 2, 0);
      paper.rotation.y = -Math.PI / 2;
    } else {
      // east: face −X (into room)
      paper.position.set(w / 2 - inward, h / 2, 0);
      paper.rotation.y = Math.PI / 2;
    }
    paper.userData.roomShell = true;
    paper.userData.roomWallpaper = true;
    room.add(paper);
    return paper;
  };
  mkWall(w, 0, -d / 2 - wallT / 2, 0); // north
  mkWall(d, -w / 2 - wallT / 2, 0, Math.PI / 2); // west
  mkWall(d, w / 2 + wallT / 2, 0, -Math.PI / 2); // east

  // Continuous south sill — unbroken across every column (no doorway cut).
  const sillH = cell * 0.55;
  const sillD = cell * 0.62;
  const sillMat = new THREE.MeshBasicMaterial({
    map: loadShellTex("myhouse_threshold.png", 8, 1),
    color: 0xffffff,
  });
  const sill = new THREE.Mesh(new THREE.BoxGeometry(w + wallT * 2, sillH, sillD), sillMat);
  sill.position.set(0, sillH / 2, d / 2 + sillD / 2);
  sill.userData.roomShell = true;
  room.add(sill);

  // Exterior dark-wood threshold walkway (decorate-mode stand-in), south front-center.
  const thrW = cell * 2.6;
  const thrD = cell * 1.7;
  const threshold = new THREE.Mesh(
    new THREE.PlaneGeometry(thrW, thrD),
    new THREE.MeshBasicMaterial({
      map: loadShellTex("myhouse_threshold.png", 2.4, 1.4),
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  );
  threshold.rotation.x = -Math.PI / 2;
  threshold.position.set(0, 0.03, d / 2 + sillD + thrD / 2 + cell * 0.06);
  threshold.userData.roomShell = true;
  room.add(threshold);

  // windows on interior faces of left / right walls
  const winMat = new THREE.MeshStandardMaterial({ color: 0x6a8aaa, roughness: 0.35, transparent: true, opacity: 0.85 });
  const frameMat = new THREE.MeshStandardMaterial({ color: 0x5a6a78 });
  [[-w / 2 + 0.02, Math.PI / 2], [w / 2 - 0.02, -Math.PI / 2]].forEach(([x, ry]) => {
    const frame = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.7), frameMat);
    frame.position.set(x, h * 0.55, 0);
    frame.rotation.y = ry;
    frame.userData.roomShell = true;
    room.add(frame);
    const glass = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.5), winMat);
    glass.position.copy(frame.position);
    glass.position.x += x < 0 ? 0.01 : -0.01;
    glass.rotation.copy(frame.rotation);
    glass.userData.roomShell = true;
    room.add(glass);
  });
  scene.add(room);
  roomCell = cell;
  roomHalf = { x: w / 2, z: d / 2 };
  rayPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  return { w, d, h, cell, ux, uy, wallT };
}

let craftTerrain = null; // { grid, mesh, water, lookup }
let onTerrainPaint = null; // ({ix, iy, mode}) => void
const craftTexCache = new Map();

function craftTerrainTex(rel) {
  if (craftTexCache.has(rel)) return craftTexCache.get(rel);
  const tex = new THREE.TextureLoader().load(BASE + rel);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  craftTexCache.set(rel, tex);
  return tex;
}

/**
 * Tileable Base Camp grass carpet (Customization close_* refs — soft felt, saturated).
 * House `*_grass_dif` atlases are thatch/foliage on black — NOT ground. Never use those on terrain.
 */
function grassCarpetTex() {
  if (craftTexCache.has("__grass_carpet__")) return craftTexCache.get("__grass_carpet__");
  const tex = mkCanvasTex((ctx, w, h) => {
    // Base felt green (close-up Customization).
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, "#46b84f");
    g.addColorStop(0.5, "#3aa846");
    g.addColorStop(1, "#4cbc55");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 14000; i++) {
      const x = Math.random() * w, y = Math.random() * h;
      const r = 0.4 + Math.random() * 1.8;
      const bright = Math.random() > 0.55;
      ctx.fillStyle = bright
        ? `rgba(120,210,90,${0.25 + Math.random() * 0.35})`
        : `rgba(25,100,45,${0.2 + Math.random() * 0.35})`;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    // Soft taller-grass flecks.
    for (let i = 0; i < 600; i++) {
      ctx.fillStyle = "rgba(30,110,50,0.4)";
      const x = Math.random() * w, y = Math.random() * h;
      ctx.fillRect(x, y, 1, 2 + Math.random() * 4);
    }
  }, 512, 512);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 8;
  craftTexCache.set("__grass_carpet__", tex);
  return tex;
}

/** Dark + marks at land-cell centers (Customization placement grid). */
function addCraftCellMarks(group, cells, cornerXZ, ix0, iy0, cell, tier) {
  const marks = new THREE.Group();
  marks.name = "craftCellMarks";
  const mat = new THREE.LineBasicMaterial({ color: 0x1a2818, transparent: true, opacity: 0.5 });
  const s = cell * 0.18;
  for (const c of cells) {
    if (!c || c.surface !== "land") continue;
    const ix = ix0 + c.mx * 2, iy = iy0 + c.my * 2;
    const a = cornerXZ(ix, iy), b = cornerXZ(ix + 2, iy + 2);
    const cx = (a.x + b.x) / 2, cz = (a.z + b.z) / 2;
    const y = (c.h | 0) * tier + 0.03;
    marks.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(cx - s, y, cz), new THREE.Vector3(cx + s, y, cz),
    ]), mat));
    marks.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(cx, y, cz - s), new THREE.Vector3(cx, y, cz + s),
    ]), mat));
  }
  group.add(marks);
}

/** Sparse blue flower clusters (close_* flora). */
function addBlueFlowerTufts(group, cells, cornerXZ, ix0, iy0, cell, tier) {
  const flora = new THREE.Group();
  flora.name = "craftFlora";
  const petal = new THREE.MeshBasicMaterial({ color: 0x7ec8ff, transparent: true, opacity: 0.92, depthWrite: false });
  let n = 0;
  for (const c of cells) {
    if (!c || c.surface !== "land") continue;
    // Deterministic sparse scatter (~1 in 18 cells).
    const h = ((c.mx * 73856093) ^ (c.my * 19349663)) >>> 0;
    if (h % 18 !== 0 || n > 120) continue;
    const ix = ix0 + c.mx * 2, iy = iy0 + c.my * 2;
    const a = cornerXZ(ix, iy), b = cornerXZ(ix + 2, iy + 2);
    const cx = (a.x + b.x) / 2 + ((h % 7) - 3) * 0.06;
    const cz = (a.z + b.z) / 2 + ((h % 5) - 2) * 0.06;
    const y = (c.h | 0) * tier + 0.04;
    const cluster = new THREE.Group();
    for (let k = 0; k < 5; k++) {
      const p = new THREE.Mesh(new THREE.CircleGeometry(0.04, 5), petal);
      p.rotation.x = -Math.PI / 2;
      p.position.set((k % 3 - 1) * 0.07, 0.01, (Math.floor(k / 3) - 0.5) * 0.07);
      cluster.add(p);
    }
    cluster.position.set(cx, y, cz);
    flora.add(cluster);
    n++;
  }
  group.add(flora);
}

/** Layered brown/tan soil like Customization cliff faces. */
function cliffStratifiedTex() {
  if (craftTexCache.has("__cliff_strat__")) return craftTexCache.get("__cliff_strat__");
  const tex = mkCanvasTex((ctx, w, h) => {
    const bands = ["#6b5340", "#7a5e45", "#8a6a4c", "#5c4636", "#9a7a58", "#6e5642", "#846848"];
    const bh = h / bands.length;
    bands.forEach((c, i) => {
      ctx.fillStyle = c;
      ctx.fillRect(0, i * bh, w, bh + 1);
      ctx.fillStyle = "rgba(0,0,0,0.12)";
      ctx.fillRect(0, (i + 1) * bh - 2, w, 2);
      ctx.fillStyle = "rgba(255,220,160,0.08)";
      ctx.fillRect(0, i * bh, w, 3);
    });
    ctx.fillStyle = "rgba(70,120,50,0.35)";
    for (let i = 0; i < 40; i++) {
      ctx.fillRect(Math.random() * w, Math.random() * h * 0.25, 6 + Math.random() * 10, 3);
    }
  }, 256, 512);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  craftTexCache.set("__cliff_strat__", tex);
  return tex;
}

/** Soft white foam where grass meets ocean. */
function addShoreFoam(group, wx0, wx1, wz0, wz1, y = -0.04) {
  const pad = 0.45;
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.85, 1.05, 64),
    new THREE.MeshBasicMaterial({
      color: 0xe8f6ff, transparent: true, opacity: 0.5, side: THREE.DoubleSide, depthWrite: false,
    }),
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.set((wx0 + wx1) / 2, y, (wz0 + wz1) / 2);
  ring.scale.set((wx1 - wx0) / 2 + pad, 1, (wz1 - wz0) / 2 + pad);
  ring.name = "shoreFoam";
  group.add(ring);
}


/** Flat grass island from craft area bounds when save terrain grid is empty. */
function syntheticTerrainFromArea(area) {
  if (!area) return null;
  const vw = area.voxel?.[0] || 50, vd = area.voxel?.[1] || 50, vh = area.voxel?.[2] || 150;
  const ox = area.origin?.[0] || 0, oy = area.origin?.[1] || 0;
  const mw = Math.max(1, Math.floor((area.width || 160) / 2));
  const md = Math.max(1, Math.floor((area.depth || 128) / 2));
  const cells = [];
  for (let my = 0; my < md; my++) {
    for (let mx = 0; mx < mw; mx++) {
      cells.push({ mx, my, ix: mx * 2, iy: my * 2, h: 0, surface: "land" });
    }
  }
  return {
    origin: [ox, oy, area.origin?.[2] || -150],
    voxel: [vw, vd, vh],
    ix0: 0, iy0: 0, width: mw, depth: md,
    tierUnit: vh / 100, cellSize: (vw * 2) / 100,
    cells,
  };
}

function buildOutdoorTerrain(opts) {
  clearGroup(terrain);
  clearGroup(room);
  room = null;
  roomHalf = null;
  terrainMesh = null;
  craftTerrain = null;
  terrain = new THREE.Group();
  bounds = opts.bounds || { minX: -17000, maxX: 17000, minY: -17000, maxY: 17000 };
  const sx = (bounds.maxX - bounds.minX) / 100;
  const sz = (bounds.maxY - bounds.minY) / 100;
  // Outdoor Z = −UE_Y/100 → map north (maxY) sits at −maxY/100.
  const cx = (bounds.minX + bounds.maxX) / 200;
  const cz = -(bounds.minY + bounds.maxY) / 200;

  // Deep ocean — the island sits ON this, not on a printed map photo.
  const ocean = new THREE.Mesh(
    new THREE.CircleGeometry(Math.max(sx, sz) * 0.95, 96),
    new THREE.MeshStandardMaterial({
      color: 0x2a7ab8, roughness: 0.22, metalness: 0.18,
      transparent: true, opacity: 0.92,
    }),
  );
  ocean.rotation.x = -Math.PI / 2;
  ocean.position.set(cx, -2.8, cz);
  ocean.name = "ocean";
  terrain.add(ocean);

  // Procedural 3D craft island (height tiers + cliffs). Never fall back to the static map JPG
  // as the walkable ground — that reads as a 2D screenshot, not Base Camp.
  let grid = opts.terrain?.cells?.length ? opts.terrain : syntheticTerrainFromArea(opts.area);
  if (grid?.cells?.length) {
    const craft = buildCraftSectorMesh(grid);
    terrain.add(craft.group);
    terrainMesh = craft.mesh || craft.group;
    craftTerrain = craft;
  }

  // No map JPG when the craft heightfield is present — it made Base Camp read as a static photo.
  if (opts.mapArt && !craftTerrain) {
    const tex = new THREE.TextureLoader().load(opts.mapArt);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
    tex.repeat.set(1, -1);
    tex.offset.set(0, 1);
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(sx * 0.55, sz * 0.55),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0.18, depthWrite: false }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(cx, -3.15, cz);
    ground.name = "mapArtHint";
    terrain.add(ground);
  }

  scene.add(terrain);
  // Tight fog around the craft pad so the scene reads as a floating 3D island.
  const fogNear = craftTerrain ? 35 : Math.max(sx, sz) * 0.4;
  const fogFar = craftTerrain ? 95 : Math.max(sx, sz) * 1.2;
  scene.fog = new THREE.Fog(0x7eb7e6, fogNear, fogFar);
  renderer.setClearColor(0x6eb0e8, 1);
  rayPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  return { w: sx, d: sz, h: 8, cx, cz };
}

/**
 * Build plateaus + cliff faces from the even-cell terrain grid.
 * Top Y for tier h = h * tierUnit (default ground top at Y=0).
 * World-space UVs so grass tiles seamlessly across elevation changes.
 */
function buildCraftSectorMesh(grid) {
  const cell = grid.cellSize || 1.0;
  const tier = grid.tierUnit || 1.5;
  const ox = (grid.origin?.[0] || 0) / 100;
  const oy = (grid.origin?.[1] || 0) / 100;
  const ix0 = grid.ix0 || 0, iy0 = grid.iy0 || 0;
  const mw = grid.width || 0, md = grid.depth || 0;
  const lookup = new Map();
  for (const c of grid.cells || []) lookup.set(`${c.mx},${c.my}`, c);

  const topPos = [], topUv = [], topIdx = [];
  const cliffPos = [], cliffUv = [], cliffIdx = [];
  const waterPos = [], waterUv = [], waterIdx = [];
  const foamPts = []; // land→water shoreline segments (close_* white foam)
  const GRASS_SCALE = 0.35, CLIFF_SCALE = 0.7;
  // Canals sit below same-tier grass (Customization ponds). Empty/ocean floor.
  const WATER_RECESS = 0.42;
  const OCEAN_Y = -0.08;
  let tBase = 0, cBase = 0, wBase = 0;

  /** Visual top Y (m). Water is recessed so land→water edges get real cliff banks. */
  const cellTopY = (c) => {
    if (!c || c.surface === "empty") return OCEAN_Y;
    if (c.surface === "water") return (c.h | 0) * tier - WATER_RECESS;
    return (c.h | 0) * tier;
  };
  const neighborTopY = (mx, my) => cellTopY(lookup.get(`${mx},${my}`));

  // World XZ of macro-cell corner (ix,iy even). +UE_Y → −Three Z.
  const cornerXZ = (ix, iy) => ({
    x: ox + (ix * (grid.voxel?.[0] || 50)) / 100,
    z: -(oy + (iy * (grid.voxel?.[1] || 50)) / 100),
  });

  for (let my = 0; my < md; my++) {
    for (let mx = 0; mx < mw; mx++) {
      const c = lookup.get(`${mx},${my}`);
      if (!c || c.surface === "empty") continue;
      const ix = ix0 + mx * 2, iy = iy0 + my * 2;
      const a = cornerXZ(ix, iy);
      const b = cornerXZ(ix + 2, iy);
      const d = cornerXZ(ix + 2, iy + 2);
      const e = cornerXZ(ix, iy + 2);
      // Four corners in XZ; after Z flip, iy+ → more −Z so winding needs care.
      const x0 = Math.min(a.x, b.x, d.x, e.x);
      const x1 = Math.max(a.x, b.x, d.x, e.x);
      const z0 = Math.min(a.z, b.z, d.z, e.z);
      const z1 = Math.max(a.z, b.z, d.z, e.z);
      const yTop = cellTopY(c);

      if (c.surface === "water") {
        waterPos.push(x0, yTop, z0, x1, yTop, z0, x1, yTop, z1, x0, yTop, z1);
        waterUv.push(x0 * GRASS_SCALE, z0 * GRASS_SCALE, x1 * GRASS_SCALE, z0 * GRASS_SCALE,
          x1 * GRASS_SCALE, z1 * GRASS_SCALE, x0 * GRASS_SCALE, z1 * GRASS_SCALE);
        waterIdx.push(wBase, wBase + 1, wBase + 2, wBase, wBase + 2, wBase + 3);
        wBase += 4;
        continue; // banks come from neighboring land cliffs
      }

      topPos.push(x0, yTop, z0, x1, yTop, z0, x1, yTop, z1, x0, yTop, z1);
      topUv.push(x0 * GRASS_SCALE, z0 * GRASS_SCALE, x1 * GRASS_SCALE, z0 * GRASS_SCALE,
        x1 * GRASS_SCALE, z1 * GRASS_SCALE, x0 * GRASS_SCALE, z1 * GRASS_SCALE);
      topIdx.push(tBase, tBase + 1, tBase + 2, tBase, tBase + 2, tBase + 3);
      tBase += 4;

      // Cliffs toward any lower surface (lower land, recessed water, or ocean).
      const dirs = [
        { dmx: 1, dmy: 0, ax: x1, az0: z0, az1: z1, horizontal: true },
        { dmx: -1, dmy: 0, ax: x0, az0: z1, az1: z0, horizontal: true },
        { dmx: 0, dmy: 1, ax: z1, az0: x1, az1: x0, horizontal: false },
        { dmx: 0, dmy: -1, ax: z0, az0: x0, az1: x1, horizontal: false },
      ];
      for (const dir of dirs) {
        const nCell = lookup.get(`${mx + dir.dmx},${my + dir.dmy}`);
        const yLo = neighborTopY(mx + dir.dmx, my + dir.dmy);
        const yHi = yTop;
        if (yHi <= yLo + 1e-4) continue;
        // White foam line where grass banks meet canal water (close_* refs).
        if (nCell && nCell.surface === "water") {
          const yF = yLo + 0.02;
          if (dir.horizontal) {
            foamPts.push(dir.ax, yF, dir.az0, dir.ax, yF, dir.az1);
          } else {
            foamPts.push(dir.az0, yF, dir.ax, dir.az1, yF, dir.ax);
          }
        }
        // Three-segment soft lip (Customization refs): soil → shoulder → grass overhang.
        const yA = yLo + (yHi - yLo) * 0.55;
        const yB = yLo + (yHi - yLo) * 0.88;
        const overhang = cell * 0.14;
        const shoulder = cell * 0.05;
        if (dir.horizontal) {
          const xFace = dir.ax;
          const xMid = xFace + dir.dmx * shoulder;
          const xOut = xFace + dir.dmx * overhang;
          cliffPos.push(xFace, yLo, dir.az0, xFace, yLo, dir.az1, xFace, yA, dir.az1, xFace, yA, dir.az0);
          cliffUv.push(dir.az0 * CLIFF_SCALE, yLo * CLIFF_SCALE, dir.az1 * CLIFF_SCALE, yLo * CLIFF_SCALE,
            dir.az1 * CLIFF_SCALE, yA * CLIFF_SCALE, dir.az0 * CLIFF_SCALE, yA * CLIFF_SCALE);
          cliffIdx.push(cBase, cBase + 1, cBase + 2, cBase, cBase + 2, cBase + 3); cBase += 4;
          cliffPos.push(xFace, yA, dir.az0, xFace, yA, dir.az1, xMid, yB, dir.az1, xMid, yB, dir.az0);
          cliffUv.push(dir.az0 * CLIFF_SCALE, yA * CLIFF_SCALE, dir.az1 * CLIFF_SCALE, yA * CLIFF_SCALE,
            dir.az1 * CLIFF_SCALE, yB * CLIFF_SCALE, dir.az0 * CLIFF_SCALE, yB * CLIFF_SCALE);
          cliffIdx.push(cBase, cBase + 1, cBase + 2, cBase, cBase + 2, cBase + 3); cBase += 4;
          cliffPos.push(xMid, yB, dir.az0, xMid, yB, dir.az1, xOut, yHi, dir.az1, xOut, yHi, dir.az0);
          cliffUv.push(dir.az0 * CLIFF_SCALE, yB * CLIFF_SCALE, dir.az1 * CLIFF_SCALE, yB * CLIFF_SCALE,
            dir.az1 * CLIFF_SCALE, yHi * CLIFF_SCALE, dir.az0 * CLIFF_SCALE, yHi * CLIFF_SCALE);
          cliffIdx.push(cBase, cBase + 1, cBase + 2, cBase, cBase + 2, cBase + 3); cBase += 4;
        } else {
          const zFace = dir.ax;
          const zSign = dir.dmy > 0 ? -1 : 1;
          const zMid = zFace + zSign * shoulder;
          const zOut = zFace + zSign * overhang;
          cliffPos.push(dir.az0, yLo, zFace, dir.az1, yLo, zFace, dir.az1, yA, zFace, dir.az0, yA, zFace);
          cliffUv.push(dir.az0 * CLIFF_SCALE, yLo * CLIFF_SCALE, dir.az1 * CLIFF_SCALE, yLo * CLIFF_SCALE,
            dir.az1 * CLIFF_SCALE, yA * CLIFF_SCALE, dir.az0 * CLIFF_SCALE, yA * CLIFF_SCALE);
          cliffIdx.push(cBase, cBase + 1, cBase + 2, cBase, cBase + 2, cBase + 3); cBase += 4;
          cliffPos.push(dir.az0, yA, zFace, dir.az1, yA, zFace, dir.az1, yB, zMid, dir.az0, yB, zMid);
          cliffUv.push(dir.az0 * CLIFF_SCALE, yA * CLIFF_SCALE, dir.az1 * CLIFF_SCALE, yA * CLIFF_SCALE,
            dir.az1 * CLIFF_SCALE, yB * CLIFF_SCALE, dir.az0 * CLIFF_SCALE, yB * CLIFF_SCALE);
          cliffIdx.push(cBase, cBase + 1, cBase + 2, cBase, cBase + 2, cBase + 3); cBase += 4;
          cliffPos.push(dir.az0, yB, zMid, dir.az1, yB, zMid, dir.az1, yHi, zOut, dir.az0, yHi, zOut);
          cliffUv.push(dir.az0 * CLIFF_SCALE, yB * CLIFF_SCALE, dir.az1 * CLIFF_SCALE, yB * CLIFF_SCALE,
            dir.az1 * CLIFF_SCALE, yHi * CLIFF_SCALE, dir.az0 * CLIFF_SCALE, yHi * CLIFF_SCALE);
          cliffIdx.push(cBase, cBase + 1, cBase + 2, cBase, cBase + 2, cBase + 3); cBase += 4;
        }
      }
    }
  }

  const group = new THREE.Group();
  group.name = "craftSector";

  const mkGeo = (pos, uv, idx) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    return g;
  };

  // Carpet grass — never house thatch atlases (black + leaves → brown/black slabs).
  const grassMap = grassCarpetTex();
  const cliffMap = cliffStratifiedTex();

  let mesh = null;
  if (topPos.length) {
    mesh = new THREE.Mesh(
      mkGeo(topPos, topUv, topIdx),
      new THREE.MeshLambertMaterial({
        map: grassMap, color: 0xffffff, side: THREE.DoubleSide,
      }),
    );
    mesh.name = "craftGrass";
    mesh.receiveShadow = true;
    mesh.castShadow = true;
    mesh.userData.craftTerrain = true;
    group.add(mesh);
  }
  if (cliffPos.length) {
    const cliffs = new THREE.Mesh(
      mkGeo(cliffPos, cliffUv, cliffIdx),
      new THREE.MeshStandardMaterial({ map: cliffMap, roughness: 0.95, metalness: 0.05 }),
    );
    cliffs.name = "craftCliffs";
    cliffs.castShadow = true;
    cliffs.receiveShadow = true;
    cliffs.userData.craftTerrain = true;
    group.add(cliffs);
    if (!mesh) mesh = cliffs;
  }
  if (waterPos.length) {
    const waters = new THREE.Mesh(
      mkGeo(waterPos, waterUv, waterIdx),
      new THREE.MeshStandardMaterial({
        color: 0x1a6fb8, roughness: 0.18, metalness: 0.25,
        transparent: true, opacity: 0.82, depthWrite: false,
      }),
    );
    waters.name = "craftWaterCells";
    waters.userData.craftTerrain = true;
    group.add(waters);
  }
  if (foamPts.length) {
    const foamGeo = new THREE.BufferGeometry();
    foamGeo.setAttribute("position", new THREE.Float32BufferAttribute(foamPts, 3));
    const foam = new THREE.LineSegments(
      foamGeo,
      new THREE.LineBasicMaterial({ color: 0xe8f6ff, transparent: true, opacity: 0.85 }),
    );
    foam.name = "canalFoam";
    foam.userData.craftTerrain = true;
    group.add(foam);
  }

  // Craft footprint AABB in Three XZ.
  const a0 = cornerXZ(ix0, iy0);
  const a1 = cornerXZ(ix0 + mw * 2, iy0 + md * 2);
  const wx0 = Math.min(a0.x, a1.x), wx1 = Math.max(a0.x, a1.x);
  const wz0 = Math.min(a0.z, a1.z), wz1 = Math.max(a0.z, a1.z);

  // Submerged hull only — shoreline banks are land→ocean cliffs above OCEAN_Y.
  const skirtTop = OCEAN_Y - 0.02;
  const skirtBot = -2.55;
  const skirtPos = [], skirtUv = [], skirtIdx = [];
  let sBase = 0;
  const skirtWalls = [
    // +X, -X, +Z, -Z faces (outward)
    [wx1, skirtBot, wz0, wx1, skirtBot, wz1, wx1, skirtTop, wz1, wx1, skirtTop, wz0],
    [wx0, skirtBot, wz1, wx0, skirtBot, wz0, wx0, skirtTop, wz0, wx0, skirtTop, wz1],
    [wx1, skirtBot, wz1, wx0, skirtBot, wz1, wx0, skirtTop, wz1, wx1, skirtTop, wz1],
    [wx0, skirtBot, wz0, wx1, skirtBot, wz0, wx1, skirtTop, wz0, wx0, skirtTop, wz0],
  ];
  for (const w of skirtWalls) {
    skirtPos.push(...w);
    const span = Math.hypot(w[3] - w[0], w[5] - w[2]);
    skirtUv.push(0, skirtBot * CLIFF_SCALE, span * CLIFF_SCALE, skirtBot * CLIFF_SCALE,
      span * CLIFF_SCALE, skirtTop * CLIFF_SCALE, 0, skirtTop * CLIFF_SCALE);
    skirtIdx.push(sBase, sBase + 1, sBase + 2, sBase, sBase + 2, sBase + 3);
    sBase += 4;
  }
  const skirt = new THREE.Mesh(
    mkGeo(skirtPos, skirtUv, skirtIdx),
    new THREE.MeshStandardMaterial({ map: cliffMap, roughness: 0.96, metalness: 0.04, color: 0xc4b49a }),
  );
  skirt.name = "islandSkirt";
  skirt.castShadow = true;
  skirt.receiveShadow = true;
  skirt.userData.craftTerrain = true;
  group.add(skirt);
  if (!mesh) mesh = skirt;

  // Soft underside so the island doesn't look hollow from below / oblique angles.
  const belly = new THREE.Mesh(
    new THREE.PlaneGeometry(wx1 - wx0, wz1 - wz0),
    new THREE.MeshStandardMaterial({ color: 0x6a5848, roughness: 1, side: THREE.DoubleSide }),
  );
  belly.rotation.x = -Math.PI / 2;
  belly.position.set((wx0 + wx1) / 2, skirtBot + 0.02, (wz0 + wz1) / 2);
  belly.name = "islandBelly";
  group.add(belly);

  // Canal water plane under the grass (pits / water cells reveal it).
  const waterY = OCEAN_Y;
  const water = new THREE.Mesh(
    new THREE.PlaneGeometry(wx1 - wx0, wz1 - wz0),
    new THREE.MeshBasicMaterial({
      color: 0x155a9a, transparent: true, opacity: 0.78, depthWrite: false,
    }),
  );
  water.rotation.x = -Math.PI / 2;
  water.position.set((wx0 + wx1) / 2, waterY, (wz0 + wz1) / 2);
  water.name = "craftWaterPlane";
  group.add(water);
  addShoreFoam(group, wx0, wx1, wz0, wz1, -0.05);
  addCraftCellMarks(group, grid.cells || [], cornerXZ, ix0, iy0, cell, tier);
  addBlueFlowerTufts(group, grid.cells || [], cornerXZ, ix0, iy0, cell, tier);

  return { group, mesh, water, grid, lookup, tier, cell, bounds: { wx0, wx1, wz0, wz1 } };
}

/** Ray down onto the craft sector (preferred) or map art; returns Y in meters. */
function snapToTerrainY(x, z) {
  const targets = [];
  if (craftTerrain?.group) targets.push(craftTerrain.group);
  else if (terrainMesh) targets.push(terrainMesh);
  if (!targets.length) return 0;
  const ray = new THREE.Raycaster(
    new THREE.Vector3(x, 1000, z),
    new THREE.Vector3(0, -1, 0),
  );
  const hits = ray.intersectObjects(targets, true);
  return hits.length ? hits[0].point.y : 0;
}

/** Map a Three.js XZ hit to fine-grid even (ix, iy) for terrain paint. */
function hitToTerrainCell(pt) {
  if (!craftTerrain?.grid) return null;
  const g = craftTerrain.grid;
  const originX = g.origin?.[0] || 0;
  const originY = g.origin?.[1] || 0;
  const vw = g.voxel?.[0] || 50;
  const vd = g.voxel?.[1] || 50;
  // Three X = UE_X/100; Three Z = −UE_Y/100 → UE_Y = −Three_Z*100
  const ueX = pt.x * 100;
  const ueY = -pt.z * 100;
  let ix = Math.round((ueX - originX) / vw);
  let iy = Math.round((ueY - originY) / vd);
  // Snap to even cells (land_obj lattice)
  ix = Math.round(ix / 2) * 2;
  iy = Math.round(iy / 2) * 2;
  const mx = (ix - (g.ix0 || 0)) / 2;
  const my = (iy - (g.iy0 || 0)) / 2;
  if (mx < 0 || my < 0 || mx >= g.width || my >= g.depth) return null;
  return { ix, iy, mx, my, cell: craftTerrain.lookup.get(`${mx},${my}`) };
}

function rebuildCraftTerrain(grid) {
  if (!terrain || !grid) return;
  if (craftTerrain?.group) {
    terrain.remove(craftTerrain.group);
    craftTerrain.group.traverse((o) => {
      o.geometry?.dispose();
      // Keep shared craft textures cached; only drop material wrappers.
      if (o.material) {
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of mats) { m.map = null; m.dispose(); }
      }
    });
  }
  const craft = buildCraftSectorMesh(grid);
  terrain.add(craft.group);
  terrainMesh = craft.mesh;
  craftTerrain = craft;
  if (craft.bounds) attachCompass(terrain, craft.bounds);
}

function ensureCursor() {
  if (cursor) return;
  cursor = new THREE.Group();
  cursor.visible = false;
  scene.add(cursor);
}

/** Outdoor footprint check: same height tier, no water/empty under the pad. */
function validateFootprintAt(x, z, wCells, dCells) {
  if (mode !== "outdoor" || !craftTerrain?.grid) {
    return { ok: true, reason: null };
  }
  const cellM = roomCell || 0.5;
  const hw = (Math.max(1, wCells) * cellM) / 2;
  const hd = (Math.max(1, dCells) * cellM) / 2;
  const samples = [
    [x - hw + 0.01, z - hd + 0.01],
    [x + hw - 0.01, z - hd + 0.01],
    [x - hw + 0.01, z + hd - 0.01],
    [x + hw - 0.01, z + hd - 0.01],
    [x, z],
  ];
  let tier = null;
  for (const [cx, cz] of samples) {
    const hit = hitToTerrainCell({ x: cx, y: 0, z: cz });
    if (!hit?.cell || hit.cell.surface === "empty" || hit.cell.surface === "water") {
      return { ok: false, reason: hit?.cell?.surface === "water" ? "water" : "empty" };
    }
    if (tier == null) tier = hit.cell.h | 0;
    else if ((hit.cell.h | 0) !== tier) return { ok: false, reason: "cliff" };
  }
  return { ok: true, reason: null, tier };
}

function setCursorValid(ok) {
  if (!cursor) return;
  cursor.userData.placeOk = ok !== false;
  const col = ok === false ? 0xff5a5a : 0x5ad0ff;
  cursor.traverse((o) => {
    if (o.isMesh && o.material?.color) o.material.color.setHex(col);
  });
}

function setCursorFootprint(wCells, dCells, cell = 0.5) {
  ensureCursor();
  while (cursor.children.length) {
    const c = cursor.children.pop();
    c.geometry?.dispose();
    if (c.material) {
      if (Array.isArray(c.material)) c.material.forEach((m) => m.dispose());
      else c.material.dispose();
    }
  }
  const ww = Math.max(1, wCells) * cell;
  const dd = Math.max(1, dCells) * cell;
  const plate = new THREE.Mesh(
    new THREE.PlaneGeometry(ww * 0.98, dd * 0.98),
    new THREE.MeshBasicMaterial({
      color: 0x5ad8ff, transparent: true, opacity: 0.42, side: THREE.DoubleSide, depthWrite: false,
    }),
  );
  plate.rotation.x = -Math.PI / 2;
  plate.position.y = 0.05;
  plate.name = "placePlate";
  cursor.add(plate);
  const rim = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.PlaneGeometry(ww, dd)),
    new THREE.LineBasicMaterial({ color: 0xb8f0ff, transparent: true, opacity: 0.95 }),
  );
  rim.rotation.x = -Math.PI / 2;
  rim.position.y = 0.06;
  cursor.add(rim);
  const halo = new THREE.Mesh(
    new THREE.PlaneGeometry(ww * 1.12, dd * 1.12),
    new THREE.MeshBasicMaterial({
      color: 0x3ec4ff, transparent: true, opacity: 0.14, side: THREE.DoubleSide, depthWrite: false,
    }),
  );
  halo.rotation.x = -Math.PI / 2;
  halo.position.y = 0.04;
  cursor.add(halo);
  // Floating cyan gear marker (Customization close_* cursor).
  const gem = new THREE.Group();
  gem.name = "placeGem";
  const gearMat = new THREE.MeshBasicMaterial({ color: 0x6adfff, transparent: true, opacity: 0.92 });
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.04, 10), gearMat);
  hub.rotation.x = Math.PI / 2;
  gem.add(hub);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.025, 6, 12), gearMat);
  ring.rotation.x = Math.PI / 2;
  gem.add(ring);
  for (let t = 0; t < 6; t++) {
    const tooth = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.04, 0.06), gearMat);
    const a = (t / 6) * Math.PI * 2;
    tooth.position.set(Math.cos(a) * 0.14, 0, Math.sin(a) * 0.14);
    gem.add(tooth);
  }
  gem.position.y = 0.38;
  gem.scale.setScalar(Math.min(ww, dd) * 1.4);
  cursor.add(gem);
  cursor.userData.placeOk = true;
  const gw = Math.max(1, wCells), gd = Math.max(1, dCells);
  for (let i = 1; i < gw; i++) {
    const x = -ww / 2 + i * cell;
    const pts = [new THREE.Vector3(x, 0.07, -dd / 2), new THREE.Vector3(x, 0.07, dd / 2)];
    cursor.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.45 })));
  }
  for (let j = 1; j < gd; j++) {
    const z = -dd / 2 + j * cell;
    const pts = [new THREE.Vector3(-ww / 2, 0.07, z), new THREE.Vector3(ww / 2, 0.07, z)];
    cursor.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.45 })));
  }
}


function buddyStub(name, color = 0xffb347) {
  const g = new THREE.Group();
  g.name = "buddyStub";
  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.22, 0.55, 5, 10),
    new THREE.MeshStandardMaterial({ color, roughness: 0.55 }),
  );
  body.position.y = 0.7;
  body.castShadow = true;
  g.add(body);
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.18, 10, 8),
    new THREE.MeshStandardMaterial({ color: 0xf2d6b0, roughness: 0.7 }),
  );
  head.position.y = 1.2;
  g.add(head);
  // Billboard-ish name plate (simple plane; no font atlas yet).
  const canvas = document.createElement("canvas");
  canvas.width = 256; canvas.height = 64;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "rgba(20,16,12,0.65)";
  ctx.fillRect(0, 0, 256, 64);
  ctx.fillStyle = "#fff8e8";
  ctx.font = "bold 28px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(name || "Buddy").slice(0, 18), 128, 32);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const plate = new THREE.Mesh(
    new THREE.PlaneGeometry(1.4, 0.35),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }),
  );
  plate.position.y = 1.55;
  g.add(plate);
  g.userData.buddyStub = true;
  g.userData.name = name;
  return g;
}

/** Dark X footprints under placed outdoor objects (Customization occupied tiles). */
function occupancyXMarks(wCells, dCells, cell = 0.5) {
  const g = new THREE.Group();
  g.name = "occupancyX";
  const mat = new THREE.LineBasicMaterial({ color: 0x1a2a18, transparent: true, opacity: 0.55 });
  const ww = Math.max(1, wCells) * cell;
  const dd = Math.max(1, dCells) * cell;
  const gw = Math.max(1, wCells), gd = Math.max(1, dCells);
  for (let iz = 0; iz < gd; iz++) {
    for (let ix = 0; ix < gw; ix++) {
      const cx = -ww / 2 + (ix + 0.5) * cell;
      const cz = -dd / 2 + (iz + 0.5) * cell;
      const s = cell * 0.28;
      g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(cx - s, 0.03, cz - s), new THREE.Vector3(cx + s, 0.03, cz + s),
      ]), mat));
      g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(cx + s, 0.03, cz - s), new THREE.Vector3(cx - s, 0.03, cz + s),
      ]), mat.clone()));
    }
  }
  return g;
}

function houseMesh(entry) {
  // Footprint in meters (voxel 50cm): width/depth cells → radius of thatched hut
  const cell = 0.5;
  const fw = Math.max(2, (entry.w || 6) * cell);
  const fd = Math.max(2, (entry.d || 6) * cell);
  const r = Math.max(fw, fd) * 0.55; // slight visual boost so thatched huts read at Customization distance
  const g = new THREE.Group();
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(r * 0.98, r * 1.02, 0.45, 24),
    new THREE.MeshStandardMaterial({ color: 0x2a5088, roughness: 0.65 }),
  );
  base.position.y = 0.22;
  base.castShadow = true;
  g.add(base);
  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(r * 0.88, r * 0.94, r * 0.7, 24),
    new THREE.MeshStandardMaterial({ color: 0xf0e6d0, roughness: 0.85 }),
  );
  body.position.y = 0.45 + r * 0.35;
  body.castShadow = true;
  g.add(body);
  const roof = new THREE.Mesh(
    new THREE.ConeGeometry(r * 1.2, r * 0.95, 24),
    new THREE.MeshStandardMaterial({ color: 0xfffaf0, roughness: 0.95, emissive: 0x222018, emissiveIntensity: 0.08 }),
  );
  roof.position.y = 0.45 + r * 0.7 + r * 0.45;
  roof.castShadow = true;
  g.add(roof);
  // blue band under thatch (in-game thatched look)
  const band = new THREE.Mesh(
    new THREE.TorusGeometry(r * 0.92, r * 0.05, 8, 28),
    new THREE.MeshStandardMaterial({ color: 0x4a90e0 }),
  );
  band.rotation.x = Math.PI / 2;
  band.position.y = 0.45 + r * 0.7;
  g.add(band);
  // door on local +X — matches craft glTF house shells
  const door = new THREE.Mesh(
    new THREE.BoxGeometry(0.08, r * 0.55, r * 0.35),
    new THREE.MeshStandardMaterial({ color: 0x1a3560 }),
  );
  door.position.set(r * 0.9, 0.35 + r * 0.2, 0);
  g.add(door);
  return g;
}

function bedMesh(entry) {
  const cell = 0.5;
  const w = Math.max(0.8, (entry.w || 2) * cell);
  const d = Math.max(1.2, (entry.d || 3) * cell);
  const g = new THREE.Group();
  const frame = new THREE.Mesh(
    new THREE.BoxGeometry(w, 0.18, d),
    new THREE.MeshStandardMaterial({ color: 0xc9a66b, roughness: 0.75 }),
  );
  frame.position.y = 0.12;
  g.add(frame);
  const mattress = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.92, 0.16, d * 0.88),
    new THREE.MeshStandardMaterial({ color: 0xf5f0e4, roughness: 0.9 }),
  );
  mattress.position.y = 0.28;
  g.add(mattress);
  const pillow = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.7, 0.12, 0.28),
    new THREE.MeshStandardMaterial({ color: 0xfffaf0, roughness: 0.85 }),
  );
  pillow.position.set(0, 0.4, -d * 0.32);
  g.add(pillow);
  return g;
}

function footprintMesh(entry, color = 0x5a9e6a) {
  if (entry.houseId || entry.category === "HOUSE" || entry.category === "GUILD_HOUSE") return houseMesh(entry);
  const name = String(entry.name || entry.craftObjId || "").toLowerCase();
  if (name.includes("bed")) return bedMesh({ ...entry, name });
  const cell = 0.5;
  const w = Math.max(0.3, (entry.w || 1) * cell);
  const d = Math.max(0.3, (entry.d || 1) * cell);
  const h = Math.max(0.2, (entry.h || 1) * cell * 0.7);
  if (entry.category === "WEED") {
    const g = new THREE.Group();
    const mat = new THREE.MeshStandardMaterial({ color: 0x4a9a3a, roughness: 0.9 });
    for (let i = 0; i < 3; i++) {
      const blade = new THREE.Mesh(new THREE.ConeGeometry(0.08, 0.35 + Math.random() * 0.2, 5), mat);
      blade.position.set((Math.random() - 0.5) * w, 0.15, (Math.random() - 0.5) * d);
      g.add(blade);
    }
    return g;
  }
  if (name.includes("bucket")) {
    const g = new THREE.Group();
    const pail = new THREE.Mesh(
      new THREE.CylinderGeometry(w * 0.42, w * 0.46, 0.42, 14),
      new THREE.MeshStandardMaterial({ color: 0x8b6914, roughness: 0.7 }),
    );
    pail.position.y = 0.22;
    g.add(pail);
    const rim = new THREE.Mesh(
      new THREE.TorusGeometry(w * 0.42, 0.025, 6, 16),
      new THREE.MeshStandardMaterial({ color: 0x6a5010, roughness: 0.6 }),
    );
    rim.rotation.x = Math.PI / 2;
    rim.position.y = 0.42;
    g.add(rim);
    return g;
  }
  // Guild square / plazas: flat ground decal (not a tall green slab that clips the map).
  if (entry.category === "GUILD_SQUARE") {
    const g = new THREE.Group();
    const pad = new THREE.Mesh(
      new THREE.PlaneGeometry(w, d),
      new THREE.MeshBasicMaterial({
        color: 0x8a8a8a, transparent: true, opacity: 0.55,
        depthWrite: false, side: THREE.DoubleSide,
        polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
      }),
    );
    pad.rotation.x = -Math.PI / 2;
    pad.position.y = 0.04;
    g.add(pad);
    return g;
  }
  let col = color;
  if (entry.category === "OBJECT") col = 0xc4a574;
  if (entry.category === "BRIDGE") col = 0xb08968;
  if (entry.category === "FENCE") col = 0x6b5344;
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshStandardMaterial({ color: col, roughness: 0.7, metalness: 0.05 }),
  );
  mesh.position.y = h / 2;
  mesh.castShadow = true;
  return mesh;
}

function worldFromUv(u, v) {
  // u = top→bottom (Y), v = left→right (X) matching app.js vilWorldToUv
  const rx = bounds.maxX - bounds.minX, ry = bounds.maxY - bounds.minY;
  return {
    x: bounds.minX + v * rx,
    y: bounds.maxY - u * ry,
  };
}

function pointerRay(ev) {
  if (!renderer) return null;
  const rect = renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(
    ((ev.clientX - rect.left) / rect.width) * 2 - 1,
    -((ev.clientY - rect.top) / rect.height) * 2 + 1,
  );
  const ray = new THREE.Raycaster();
  ray.setFromCamera(mouse, cam);
  return { ray, mouse };
}

function hitTerrain(ev) {
  if (!rayPlane) return null;
  const pr = pointerRay(ev);
  if (!pr) return null;
  const pt = new THREE.Vector3();
  if (!pr.ray.ray.intersectPlane(rayPlane, pt)) return null;
  return { three: pt, ray: pr.ray, mouse: pr.mouse };
}

function snapCell(v, cell = roomCell || 0.5) {
  return Math.round(v / cell) * cell;
}

/** Keep snapped furniture / cursor pivots on the indoor floor (not over the sill/void). */
function clampRoomXZ(x, z, cell = roomCell || 0.5) {
  if (mode !== "indoor" || !roomHalf) return { x, z };
  // Max cell center = half-floor − half-cell so a 1×1 footprint stays on the planks.
  const limX = Math.max(0, roomHalf.x - cell / 2);
  const limZ = Math.max(0, roomHalf.z - cell / 2);
  return {
    x: Math.max(-limX, Math.min(limX, x)),
    z: Math.max(-limZ, Math.min(limZ, z)),
  };
}

/** Walk up from a mesh to the outermost furniture group (root child) with a handle. */
function furnitureFromHit(obj) {
  let found = null;
  let o = obj;
  while (o && o !== root) {
    // Handles are stamped onto glTF descendants for highlight — prefer the root-level group
    // so drag updates the same Object3D that rebuild()/onMove read.
    if (o.userData?.handle != null && !o.userData.roomShell) found = o;
    o = o.parent;
  }
  return found;
}

function pickFurniture(ev) {
  if (!root) return null;
  const pr = pointerRay(ev);
  if (!pr) return null;
  // Recursive through mesh hierarchies (gltf children, stand-in groups).
  const hits = pr.ray.intersectObjects(root.children, true);
  for (const h of hits) {
    if (h.object.userData?.roomShell) continue;
    const g = furnitureFromHit(h.object);
    if (g) return g;
  }
  return null;
}

function onPointerDown(ev) {
  if (ev.button !== 0) return;
  // Terrain paint takes the click; don't start a furniture drag.
  if (mode === "outdoor" && terrainTool && onTerrainPaint) {
    pointerDown = { x: ev.clientX, y: ev.clientY, t: Date.now() };
    return;
  }
  const furn = pickFurniture(ev);
  if (furn) {
    // Capture furniture drag — disable OrbitControls so the camera does not steal the gesture.
    ctl.enabled = false;
    ev.preventDefault();
    ev.stopImmediatePropagation();
    drag = {
      handle: furn.userData.handle,
      group: furn,
      x: ev.clientX,
      y: ev.clientY,
      moved: false,
      orig: furn.position.clone(),
    };
    try { renderer.domElement.setPointerCapture(ev.pointerId); } catch { /* ignore */ }
    selected = furn.userData.handle;
    highlight(selected);
    if (onSelect) onSelect(selected);
    pointerDown = null;
    return;
  }
  pointerDown = { x: ev.clientX, y: ev.clientY, t: Date.now() };
}

function onPointerMove(ev) {
  if (drag) {
    ev.preventDefault();
    ev.stopImmediatePropagation();
    const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
    if (dx * dx + dy * dy > 25) drag.moved = true;
    // Project onto the invisible Y=0 ground plane, then snap to the tile grid.
    const hit = hitTerrain(ev);
    if (!hit) return;
    const cell = roomCell || 0.5;
    const p = clampRoomXZ(snapCell(hit.three.x, cell), snapCell(hit.three.z, cell), cell);
    drag.group.position.set(
      p.x,
      mode === "outdoor" ? snapToTerrainY(p.x, p.z) : 0,
      p.z,
    );
    return;
  }
  if (!cursor || !onPlace) return;
  const hit = hitTerrain(ev);
  if (!hit) { cursor.visible = false; return; }
  cursor.visible = true;
  const cell = roomCell || 0.5;
  const p = clampRoomXZ(snapCell(hit.three.x, cell), snapCell(hit.three.z, cell), cell);
  const cy = mode === "outdoor" ? snapToTerrainY(p.x, p.z) + 0.05 : 0.045;
  cursor.position.set(p.x, cy, p.z);
  if (mode === "outdoor") {
    const v = validateFootprintAt(p.x, p.z, placeSize.w, placeSize.d);
    setCursorValid(v.ok);
  }
}

function onPointerUp(ev) {
  // Always finish an active furniture drag (button can be 0 or -1 depending on event source).
  if (drag) {
    ctl.enabled = true;
    ev.preventDefault();
    ev.stopImmediatePropagation();
    try { renderer.domElement.releasePointerCapture(ev.pointerId); } catch { /* ignore */ }
    const d = drag;
    drag = null;
    if (d.moved && onMove) {
      const ue = threeToUeXZ(d.group.position.x, d.group.position.z, mode === "outdoor");
      onMove({
        handle: d.handle,
        x: ue.x,
        y: ue.y,
        three: d.group.position.clone(),
      });
    }
    return;
  }
  if (ev.button !== 0 && ev.type !== "pointercancel") return;
  if (!pointerDown) return;
  const dx = ev.clientX - pointerDown.x, dy = ev.clientY - pointerDown.y;
  const dragged = dx * dx + dy * dy > 36;
  pointerDown = null;
  if (dragged) return;

  const hit = hitTerrain(ev);
  if (!hit) return;

  // Terrain raise/lower paints the craft grid (Terrain tab).
  if (mode === "outdoor" && terrainTool && onTerrainPaint) {
    const cell = hitToTerrainCell(hit.three);
    if (cell) onTerrainPaint({ ix: cell.ix, iy: cell.iy, mode: terrainTool, cell });
    return;
  }

  if (onPlace && cursor?.visible) {
    if (mode === "outdoor" && cursor.userData.placeOk === false) return; // red footprint — blocked
    const ue = threeToUeXZ(cursor.position.x, cursor.position.z, mode === "outdoor");
    onPlace({
      x: ue.x, y: ue.y, three: cursor.position.clone(),
      placeOk: cursor.userData.placeOk !== false,
    });
  }
}

function highlight(handle) {
  if (!root) return;
  root.traverse((o) => {
    if (!o.isMesh || !o.material || o.userData.roomShell) return;
    const h = o.userData.handle ?? o.parent?.userData?.handle;
    const on = h === handle;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      if (m.emissive) m.emissive.setHex(on ? 0x446622 : 0x000000);
      else if (m.color && !m.map) {
        if (!m.userData._baseColor) m.userData._baseColor = m.color.getHex();
        m.color.setHex(on ? 0xb8e080 : m.userData._baseColor);
      }
    }
  });
}

function frameScene(size, placed, outdoor, craftCenter) {
  if (outdoor) {
    // Yellow craft-pad center (pad_* Customization refs) — never snap to house cluster.
    const tx = craftCenter?.x ?? size.cx ?? 0;
    const tz = craftCenter?.z ?? size.cz ?? 0;
    const padSpan = craftCenter?.span || 40;
    const span = Math.min(52, Math.max(24, padSpan * 0.55));
    ctl.target.set(tx, 0.5, tz);
    // High oblique like pad survey shots — whole yellow rectangle in view, cliffs still readable.
    cam.position.set(tx + span * 0.4, span * 1.15, tz + span * 0.95);
    ctl.minDistance = 8;
    ctl.maxDistance = Math.max(100, padSpan * 1.6);
    ctl.maxPolarAngle = Math.PI * 0.82;
    ctl.minPolarAngle = 0.08;
    ctl.update();
    return;
  }
  const pts = (placed || []).map((p) => ueToThree(p.location));
  // Look in over the south sill (+Z) from above, like in-game My House decorate.
  if (!pts.length) {
    ctl.target.set(0, 0.5, 0);
    cam.position.set(0, size.h * 1.2, size.d * 1.15);
    ctl.minDistance = 1.0;
    ctl.maxDistance = 28;
    ctl.maxPolarAngle = Math.PI * 0.82;
    ctl.update();
    return;
  }
  const box = new THREE.Box3();
  pts.forEach((p) => box.expandByPoint(p));
  box.expandByScalar(0.6);
  const center = new THREE.Vector3();
  box.getCenter(center);
  center.y = Math.max(0.45, center.y);
  const sphere = new THREE.Sphere();
  box.getBoundingSphere(sphere);
  const dist = Math.max(2.8, sphere.radius * 2.4);
  ctl.target.copy(center);
  cam.position.set(center.x + dist * 0.15, center.y + dist * 0.85, center.z + dist * 1.05);
  ctl.minDistance = 1.0;
  ctl.maxDistance = 28;
  ctl.maxPolarAngle = Math.PI * 0.82;
  ctl.update();
}

async function rebuild(placed) {
  clearGroup(root);
  root = new THREE.Group();
  scene.add(root);
  for (const p of placed || []) {
    // Weeds clutter the Customization view; keep houses / builds / furniture.
    if (mode === "outdoor" && p.category === "WEED") continue;
    const entry = {
      ...(manifest?.[p.craftObjId] || {}),
      w: p.w, d: p.d, h: p.h,
      houseId: p.houseId, category: p.category,
    };
    let node;
    const isHouse = !!(p.houseId || p.category === "HOUSE" || p.category === "GUILD_HOUSE");
    // cft00030x glbs ARE house shells (door/bird/propeller) — load them; stylized hut is fallback only.
    entry.name = p.name;
    entry.craftObjId = p.craftObjId;
    if (entry.mesh) {
      try { node = await glb(entry.mesh); }
      catch (err) {
        console.warn("village3d: glb failed", entry.mesh, err);
        node = isHouse ? houseMesh(entry) : footprintMesh(entry);
      }
    } else {
      node = isHouse ? houseMesh(entry) : footprintMesh(entry, 0x5a9e6a);
    }
    const g = new THREE.Group();
    g.userData.handle = p.handle;
    g.userData.craftObjId = p.craftObjId;
    g.userData.name = p.name;
    node.traverse((o) => { o.userData.handle = p.handle; });
    g.add(node);
    const outdoor = mode === "outdoor";
    g.position.copy(ueToThree(p.location, outdoor));
    if (outdoor) {
      // Sit on the island mesh (flat map today; ready for a heightfield later).
      g.position.y = snapToTerrainY(g.position.x, g.position.z);
    }
    g.quaternion.copy(yawToQuat(p.rotation, outdoor));
    if (outdoor && p.category !== "LAND" && p.category !== "WATER") {
      const xs = occupancyXMarks(entry.w || p.w || 1, entry.d || p.d || 1, roomCell || 0.5);
      xs.position.y = 0.01;
      g.add(xs);
    }
    root.add(g);
    if (outdoor && isHouse) {
      g.userData.houseId = p.houseId || entry.houseId || null;
      g.userData.isHouse = true;
    }
  }
  // Buddy stubs near assigned houses (Additive — show residents without blocking craft).
  if (mode === "outdoor" && Array.isArray(rebuild.residents)) {
    const houses = root.children.filter((c) => c.userData?.isHouse);
    for (const r of rebuild.residents) {
      if (!r || !r.name) continue;
      let home = null;
      const rid = String(r.id || "").replace(/^para_/, "").replace(/^chr/, "");
      for (const h of houses) {
        const hid = String(h.userData.houseId || h.userData.craftObjId || "");
        if (rid && hid.includes(rid)) { home = h; break; }
        // Islander thatched kit often hosts the first living buddy when ids don't embed.
        if (!home && /icf01021/.test(hid)) home = h;
      }
      if (!home && houses.length) home = houses[houses.length - 1];
      if (!home) continue;
      const stub = buddyStub(r.name, r.living ? 0x7ec8ff : 0xffb347);
      const ang = ((r.handle || 1) % 7) * 0.9;
      const rad = 1.8 + ((r.handle || 0) % 5) * 0.15;
      stub.position.set(
        home.position.x + Math.sin(ang) * rad,
        0,
        home.position.z + Math.cos(ang) * rad,
      );
      stub.position.y = snapToTerrainY(stub.position.x, stub.position.z);
      stub.userData.buddyId = r.id;
      root.add(stub);
    }
  }
  if (selected != null) highlight(selected);
}

/**
 * @param {HTMLElement} container
 * @param {object[]} placed
 * @param {object} opts
 *   mode: 'indoor' | 'outdoor'
 *   area, bounds, mapArt, selected, onSelect, onPlace, placeW, placeD, keepCamera
 */
async function show(container, placed, opts = {}) {
  // Always re-fetch so Reload picks up a fresh craft3d build (meshes + materials).
  {
    const raw = await fetch(BASE + "manifest.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
    materials = raw._materials || {};
    const { _materials, ...objs } = raw;
    manifest = objs;
    buffers.clear();
    texCache.clear();
  }
  if (!renderer) setup();
  host = container;
  onSelect = opts.onSelect || null;
  onPlace = opts.onPlace || null;
  onMove = opts.onMove || null;
  onTerrainPaint = opts.onTerrainPaint || null;
  terrainTool = opts.terrainTool || null;
  selected = opts.selected ?? null;
  mode = opts.mode || "indoor";
  placeSize = { w: opts.placeW || 1, d: opts.placeD || 1 };
  drag = null;
  if (ctl) ctl.enabled = true;
  container.innerHTML = "";
  container.appendChild(renderer.domElement);

  let size;
  let items = placed || [];
  let craftCenter = null;
  // Drop any leftover static map3d env — Village rebuilds from the save terrain + placements.
  if (islandEnv) {
    scene.remove(islandEnv);
    clearGroup(islandEnv);
    islandEnv = null;
  }
  if (mode === "outdoor") {
    size = buildOutdoorTerrain(opts);
    // Optional extracted map3d backdrop (off by default — stale meshes fought the save rebuild).
    if (opts.loadEnv) {
      await loadIslandEnv();
      if (islandEnv && terrain) {
        const ocean = terrain.getObjectByName("ocean");
        if (ocean) ocean.visible = false;
      }
    }
    roomCell = 0.5;
    items = (placed || []).map((p) => ({ ...p }));
    setCursorFootprint(placeSize.w, placeSize.d, 0.5);
    ensureCursor();
    cursor.visible = !!onPlace;
    // Frame on the procedural island AABB when we have it.
    if (craftTerrain?.bounds) {
      const b = craftTerrain.bounds;
      craftCenter = {
        x: (b.wx0 + b.wx1) / 2,
        z: (b.wz0 + b.wz1) / 2,
        span: Math.max(b.wx1 - b.wx0, b.wz1 - b.wz0),
      };
    }
    // Craft area outline in outdoor Three space (Z = −UE_Y/100). Wire rim only —
    // never a filled green plane (that sliced through the landscape).
    let compassBounds = craftTerrain?.bounds || null;
    if (opts.area) {
      const ox = (opts.area.origin?.[0] || 0) / 100;
      const oz0 = -(opts.area.origin?.[1] || 0) / 100;
      const aw = ((opts.area.width || 160) * (opts.area.voxel?.[0] || 50)) / 100;
      const ad = ((opts.area.depth || 128) * (opts.area.voxel?.[1] || 50)) / 100;
      // +UE_Y (north) → −Three Z, so the far edge is oz0 − ad.
      if (!craftCenter) {
        craftCenter = { x: ox + aw / 2, z: oz0 - ad / 2, span: Math.max(aw, ad) * 0.85 };
      }
      if (!compassBounds) {
        compassBounds = { wx0: ox, wx1: ox + aw, wz0: oz0 - ad, wz1: oz0 };
      }
      const yRim = 0.06;
      const corners = [
        new THREE.Vector3(ox, yRim, oz0),
        new THREE.Vector3(ox + aw, yRim, oz0),
        new THREE.Vector3(ox + aw, yRim, oz0 - ad),
        new THREE.Vector3(ox, yRim, oz0 - ad),
      ].map((p) => {
        p.y = snapToTerrainY(p.x, p.z) + 0.08;
        return p;
      });
      // Bright yellow craft pad outline (survey Customization free-cam shots).
      const rim = new THREE.LineLoop(
        new THREE.BufferGeometry().setFromPoints(corners),
        new THREE.LineBasicMaterial({
          color: 0xffe14a, transparent: true, opacity: 0.95,
          depthWrite: false,
          polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
        }),
      );
      rim.name = "craftPadRim";
      terrain.add(rim);
    }
    if (compassBounds && terrain) attachCompass(terrain, compassBounds);
  } else {
    size = buildIndoorRoom(opts.area);
    // My House craft axes vs door (Screenshot 220942): door / open front = +Z,
    // left-right = iy (high iy = left wall), depth = ix (ix=0 = back wall).
    // Bucket (0,10) → back-left; Tropical Bed (2,1) → right wall. Earlier ix→X
    // mapping put both on the left with the bed by the door.
    const aw = opts.area?.width || 12, ad = opts.area?.depth || 12;
    const cell = size.cell || (opts.area?.voxel?.[0] || 50) / 100;
    const cellZ = (opts.area?.voxel?.[2] || 100) / 100;
    const ux = size.ux || Math.max(1, aw - 1);
    const uy = size.uy || Math.max(1, ad - 1);
    const halfW = (ux * cell * 100) / 2;
    const halfD = (uy * cell * 100) / 2;
    items = (placed || []).map((p) => {
      let ix, iy, iz = 0;
      if (p.gridIdx != null && p.gridIdx >= 0) {
        const layer = aw * ad;
        iz = Math.floor(p.gridIdx / layer);
        const rem = p.gridIdx % layer;
        ix = Math.floor(rem / aw);
        iy = rem % aw;
      } else {
        ix = Math.round(ux / 2); iy = Math.round(uy / 2);
      }
      const fw = Math.max(1, p.w || 1), fd = Math.max(1, p.d || 1);
      // Along-wall extent uses footprint d (iy); depth along room uses footprint w (ix).
      const along = (iy + fd / 2) * cell * 100 - halfD; // iy → left/right
      const depth = (ix + fw / 2) * cell * 100 - halfW; // ix → back/door
      // +90° yaw: craft width/depth were X/Y; room shows them as Z/X — meshes follow.
      const rot = [p.rotation?.[0] || 0, (p.rotation?.[1] || 0) + 90, p.rotation?.[2] || 0];
      return {
        ...p,
        rotation: rot,
        // loc[0]=Three X (negated so high iy = left), [1]=Three Z (ix=0 back), [2]=up
        // ueToThree: (loc0/100, loc2/100, loc1/100)
        location: [-along, depth, iz * cellZ * 100],
      };
    });
    setCursorFootprint(placeSize.w, placeSize.d, cell);
    ensureCursor();
    cursor.visible = !!onPlace;
    renderer.setClearColor(0x1a1008, 1);
    scene.fog = null;
  }
  rebuild.residents = opts.residents || null;
  await rebuild(items);
  if (!opts.keepCamera) frameScene(size, items, mode === "outdoor", craftCenter);
  return true;
}

function setPlaceSize(w, d) {
  placeSize = { w: w || 1, d: d || 1 };
  setCursorFootprint(placeSize.w, placeSize.d, mode === "outdoor" ? 0.5 : 0.5);
}


let exploreMode = false;
let explorer = null; // third-person stand-in capsule
const exploreKeys = new Set();

function ensureExplorer() {
  if (explorer) return explorer;
  explorer = new THREE.Group();
  explorer.name = "explorer";
  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.28, 0.7, 6, 12),
    new THREE.MeshStandardMaterial({ color: 0x4a7cff, roughness: 0.55, metalness: 0.1 }),
  );
  body.position.y = 0.85;
  body.castShadow = true;
  explorer.add(body);
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.22, 12, 10),
    new THREE.MeshStandardMaterial({ color: 0xf2d6b0, roughness: 0.7 }),
  );
  head.position.y = 1.45;
  explorer.add(head);
  explorer.visible = false;
  scene.add(explorer);
  return explorer;
}

function setExploreMode(on) {
  exploreMode = !!on;
  const ex = ensureExplorer();
  ex.visible = exploreMode;
  if (exploreMode) {
    // Drop near camera look-at (craft pad center).
    const tx = ctl?.target?.x || 0;
    const tz = ctl?.target?.z || 0;
    ex.position.set(tx, snapToTerrainY(tx, tz), tz);
    if (ctl) {
      ctl.maxPolarAngle = Math.PI * 0.92;
      ctl.minDistance = 1.2;
      ctl.maxDistance = 12;
    }
  } else if (ctl) {
    ctl.maxPolarAngle = Math.PI * 0.48;
    ctl.minDistance = 0.8;
    ctl.maxDistance = 90;
  }
}

function tickExplore(dt) {
  if (!exploreMode || !explorer || !explorer.visible) return;
  let dx = 0, dz = 0;
  if (exploreKeys.has("KeyW") || exploreKeys.has("ArrowUp")) dz -= 1;
  if (exploreKeys.has("KeyS") || exploreKeys.has("ArrowDown")) dz += 1;
  if (exploreKeys.has("KeyA") || exploreKeys.has("ArrowLeft")) dx -= 1;
  if (exploreKeys.has("KeyD") || exploreKeys.has("ArrowRight")) dx += 1;
  if (!dx && !dz) return;
  const len = Math.hypot(dx, dz) || 1;
  const speed = 4.2 * dt;
  // Move relative to camera yaw on XZ.
  const yaw = Math.atan2(cam.position.x - explorer.position.x, cam.position.z - explorer.position.z);
  const fx = Math.sin(yaw), fz = Math.cos(yaw);
  const rx = Math.cos(yaw), rz = -Math.sin(yaw);
  const mx = ((-dz) * fx + dx * rx) * speed;
  const mz = ((-dz) * fz + dx * rz) * speed;
  const nx = explorer.position.x + mx;
  const nz = explorer.position.z + mz;
  explorer.position.set(nx, snapToTerrainY(nx, nz), nz);
  explorer.rotation.y = Math.atan2(mx, mz);
  if (ctl) {
    ctl.target.set(nx, explorer.position.y + 1.0, nz);
    // Keep a soft third-person follow without fighting OrbitControls too hard.
    const back = 4.5;
    const desired = new THREE.Vector3(
      nx - Math.sin(explorer.rotation.y) * back,
      explorer.position.y + 2.4,
      nz - Math.cos(explorer.rotation.y) * back,
    );
    cam.position.lerp(desired, Math.min(1, dt * 3.5));
  }
}

window.Village3D = {
  show, highlight, setPlaceSize, rebuildCraftTerrain, hardReset,
  compassHeadingRad,
  setTerrainTool(tool) { terrainTool = tool || null; },
  getTerrainGrid() { return craftTerrain?.grid || null; },
  validateFootprintAt, setExploreMode,
  isExploreMode() { return !!exploreMode; },
  setWallpaper(texRel) {
    if (!room) return;
    room.traverse((o) => {
      if (!o.userData?.roomWallpaper || !o.material) return;
      const along = o.geometry?.parameters?.width || 5.5;
      if (texRel) {
        o.material.map = loadShellTex(texRel, WALL_TARGET_SLATS / WALL_SLAT_BASE * (along / 0.5), 1.0, {
          wrapS: THREE.RepeatWrapping, wrapT: THREE.ClampToEdgeWrapping,
        });
      } else {
        o.material.map = wallpaperTex(along);
      }
      o.material.needsUpdate = true;
    });
  },
  setFloor(texRel) {
    if (!room || !texRel) return;
    const floorRepeat = 1.35 * 0.22;
    room.traverse((o) => {
      if (!o.userData?.roomFloor || !o.material) return;
      const tex = new THREE.TextureLoader().load(BASE + texRel);
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(floorRepeat, floorRepeat);
      tex.colorSpace = THREE.SRGBColorSpace;
      o.material.map = tex;
      o.material.needsUpdate = true;
    });
  },
  /** Project a world point to canvas client coordinates (for tests / tooling). */
  screenOf(x, y, z) {
    if (!renderer || !cam) return null;
    const v = new THREE.Vector3(x, y, z).project(cam);
    const rect = renderer.domElement.getBoundingClientRect();
    return {
      clientX: rect.left + (v.x * 0.5 + 0.5) * rect.width,
      clientY: rect.top + (-v.y * 0.5 + 0.5) * rect.height,
      ndc: [v.x, v.y, v.z],
    };
  },
  /** Hit the Y=0 ground plane at a client point (tests / tooling). */
  hitAt(clientX, clientY) {
    const hit = hitTerrain({ clientX, clientY });
    if (!hit) return null;
    const cell = roomCell || 0.5;
    return {
      three: hit.three.toArray(),
      snapped: [snapCell(hit.three.x, cell), snapCell(hit.three.z, cell)],
      cell,
    };
  },
  furniture() {
    const out = [];
    root?.children?.forEach((g) => {
      if (g.userData?.handle == null) return;
      const b = new THREE.Box3().setFromObject(g);
      const c = new THREE.Vector3();
      b.getCenter(c);
      out.push({
        handle: g.userData.handle,
        name: g.userData.name,
        craftObjId: g.userData.craftObjId,
        pos: g.position.toArray(),
        center: c.toArray(),
        box: { min: b.min.toArray(), max: b.max.toArray() },
      });
    });
    return out;
  },
  camState() {
    return {
      cam: cam?.position.toArray(),
      target: ctl?.target.toArray(),
      roomKids: room?.children?.length,
      ctlEnabled: ctl?.enabled,
      dragging: !!drag,
      shell: room?.children?.filter((c) => c.userData.roomShell).map((c) => ({
        type: c.geometry?.type, pos: c.position.toArray(),
        scale: c.scale.toArray(),
        size: c.geometry?.parameters
          ? Object.values(c.geometry.parameters)
          : null,
      })),
    };
  },
  debug() {
    const meshes = [];
    root?.traverse((o) => {
      if (!o.isMesh) return;
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      const uv = o.geometry?.attributes?.uv;
      meshes.push({
        name: o.name,
        pos: o.parent?.position?.toArray?.(),
        scale: o.scale?.toArray?.(),
        uv: uv ? { count: uv.count, itemSize: uv.itemSize } : null,
        box: (() => { const b = new THREE.Box3().setFromObject(o); return { min: b.min.toArray(), max: b.max.toArray() }; })(),
        mats: mats.map((m) => ({
          name: m?.name, map: !!m?.map, mapImg: m?.map?.image?.width,
          nml: !!m?.normalMap, color: m?.color?.getHexString?.(),
        })),
      });
    });
    return { materialKeys: Object.keys(materials), meshCount: meshes.length, meshes };
  },
  lookAt(name) {
    let target = null;
    root?.traverse((o) => { if (o.isMesh && o.name.includes(name)) target = o; });
    if (!target || !ctl) return false;
    const b = new THREE.Box3().setFromObject(target);
    const c = new THREE.Vector3(); b.getCenter(c);
    const s = new THREE.Sphere(); b.getBoundingSphere(s);
    ctl.target.copy(c);
    cam.position.set(c.x + s.radius * 1.2, c.y + s.radius * 1.4, c.z + s.radius * 1.8);
    ctl.update();
    return true;
  },
};
window.dispatchEvent(new Event("village3d-ready"));
