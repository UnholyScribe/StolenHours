// 3D preview of the player character, assembled from the game's own avatar meshes (game/avatar3d, see avatar3d.py).
// Every part is rebound onto one skeleton by bone name, the same way the game attaches hair, ears and nose to the head.
// Shading is an approximation of the game's toon materials using its own masks and colour tables.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const BASE = "game/avatar3d/";
const loader = new GLTFLoader();
const texLoader = new THREE.TextureLoader();
const buffers = new Map();
const textures = new Map();
let manifest = null, renderer = null, scene = null, cam = null, ctl = null, rig = null, host = null, building = 0;

// Face slider limits from the head material (mat_avt000100_00 scalars). The save stores 0-20 (centre 10) for positions
// and small integers for sizes. UNVERIFIED: units (taken as 1/100 of the part's UV area) and slider direction.
const FACE = {
  eye: { u: [-2.5, 2.5], v: [-2.5, 2.5], s: [90, 110], sMax: 4, sMid: 2 },
  brow: { u: [-3, 3], v: [-5, 1], s: [90, 120], sMax: 2, sMid: 1 },
  mouth: { v: [-2, 1.6], s: [80, 110], sMax: 4, sMid: 2 },
};
const piece = (i, [lo, hi], mid = 10, max = 20) => (i <= mid ? lo * (mid - i) / mid : hi * (i - mid) / (max - mid));
const scaleOf = (i, f) => (i <= f.sMid ? f.s[0] + (100 - f.s[0]) * i / f.sMid : 100 + (f.s[1] - 100) * (i - f.sMid) / (f.sMax - f.sMid)) / 100;

const lin = (a, fallback = [0.5, 0.5, 0.5]) => new THREE.Color().setRGB(...(a || fallback), THREE.LinearSRGBColorSpace);

function tex(name, srgb = false) {
  if (!name) return null;
  const key = name + srgb;
  if (!textures.has(key)) {
    const t = texLoader.load(BASE + name);
    t.flipY = false;
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    textures.set(key, t);
  }
  return textures.get(key);
}

async function glb(name) {
  if (!buffers.has(name)) buffers.set(name, fetch(BASE + name).then((r) => r.arrayBuffer()));
  const g = await loader.parseAsync((await buffers.get(name)).slice(0), "");
  return g.scene || g.scenes[0];
}

const VERT = `
  #include <common>
  #include <skinning_pars_vertex>
  #ifdef FACE
  attribute vec2 aE1; attribute vec2 aE2; attribute vec2 aM;
  varying vec2 vE1; varying vec2 vE2; varying vec2 vM;
  #endif
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  void main() {
    vUv = uv;
    #ifdef FACE
    vE1 = aE1; vE2 = aE2; vM = aM;
    #endif
    #include <skinbase_vertex>
    #include <beginnormal_vertex>
    #include <skinnormal_vertex>
    #include <begin_vertex>
    #include <skinning_vertex>
    #include <project_vertex>
    vN = normalize(normalMatrix * objectNormal);
    vV = normalize(-mvPosition.xyz);
  }`;

const FRAG = `
  uniform sampler2D tMain; uniform float hasMain;
  uniform vec3 cA; uniform vec3 cB; uniform vec3 cC; uniform vec3 rim;
  varying vec2 vUv; varying vec3 vN; varying vec3 vV;
  #ifdef FACE
  uniform sampler2D tEye; uniform sampler2D tBrow; uniform sampler2D tMouth; uniform sampler2D tOpt;
  uniform float hasOpt; uniform vec3 eyeCol; uniform vec3 eyeHi; uniform vec3 browCol; uniform vec3 browShadow;
  uniform vec3 eyeXf; uniform vec3 browXf; uniform vec3 mouthXf; uniform float mirror;
  varying vec2 vE1; varying vec2 vE2; varying vec2 vM;
  vec4 cell(sampler2D t, vec2 uv, vec3 xf) {
    vec2 c = (uv - vec2(.5) - xf.yz) / xf.x + vec2(.5);
    if (c.x < 0. || c.y < 0. || c.x > 1. || c.y > 1.) return vec4(0.);
    return texture2D(t, c * .5);
  }
  #endif
  float lit() {
    vec3 n = normalize(vN);
    float d = dot(n, normalize(vec3(.35, .7, .6))) * .5 + .5;
    return smoothstep(.38, .52, d);
  }
  void main() {
    float l = lit();
    vec4 m = hasMain > .5 ? texture2D(tMain, vUv) : vec4(1.);
    vec3 col;
    #if defined(FACE) || defined(SKIN)
      col = mix(cB, cA, .55 + .45 * l);
      col = mix(col, cC, m.b * .45);
    #elif defined(HAIR)
      col = mix(cB, cA, clamp(m.g * 1.25, 0., 1.) * (.65 + .35 * l));
      col += cC * m.a * .35 * l;
    #else
      col = m.rgb * (.72 + .28 * l);
    #endif
    #ifdef FACE
      if (hasOpt > .5) { vec4 o = texture2D(tOpt, vUv); col = mix(col, o.rgb, o.a); }
      for (int i = 0; i < 2; i++) {
        vec2 uv = i == 0 ? vE1 : vE2;
        vec4 b = cell(tBrow, uv, browXf);
        col = mix(col, mix(browShadow, browCol, b.r), b.a);
        vec4 e = cell(tEye, uv, eyeXf);
        vec3 ec = vec3(.06, .04, .035);
        ec = mix(ec, eyeCol, e.r); ec = mix(ec, eyeHi, e.g); ec = mix(ec, vec3(1.), e.b);
        col = mix(col, ec, e.a);
      }
      vec4 mo = cell(tMouth, vM, mouthXf);
      col = mix(col, mo.rgb, mo.a);
    #endif
    float r = pow(1. - max(dot(normalize(vN), normalize(vV)), 0.), 3.);
    col += rim * r * .25;
    gl_FragColor = vec4(col, 1.);
    #include <colorspace_fragment>
  }`;

function shader(type, matDef, look) {
  const c = manifest.colors;
  const skin = c[look.FaceColorId] || {}, hair = c[look.HairColorId] || {}, eye = c[look.EyeColorId] || {};
  const defines = { face: { FACE: "" }, skin: { SKIN: "" }, hair: { HAIR: "" } }[type] || {};
  const main = matDef?.tex ? tex(matDef.tex, type === "diff") : null;
  const u = {
    tMain: { value: main }, hasMain: { value: main ? 1 : 0 },
    cA: { value: lin(type === "hair" ? hair.hair : skin.skin) },
    cB: { value: lin(type === "hair" ? hair.shadow : skin.shadow) },
    cC: { value: lin(type === "hair" ? hair.hi : skin.cheek) },
    rim: { value: lin(type === "hair" ? [0.3, 0.3, 0.3] : skin.rim || [0.3, 0.3, 0.3]) },
  };
  if (type === "face") {
    const p = manifest.parts, opt = p.OptionPartsId[look.OptionPartsId] || {};
    const eyeX = 0.01, F = FACE;
    Object.assign(u, {
      tEye: { value: tex(p.EyePartsId[look.EyePartsId]) }, tBrow: { value: tex(p.EyeBrowPartsId[look.EyeBrowPartsId]) },
      tMouth: { value: tex(p.MouthPartsId[look.MouthPartsId], true) },
      tOpt: { value: tex(opt.tex, true) }, hasOpt: { value: opt.tex ? 1 : 0 },
      eyeCol: { value: lin(eye.eye) }, eyeHi: { value: lin(eye.hi) },
      browCol: { value: lin(hair.hair) }, browShadow: { value: lin(hair.shadow) },
      eyeXf: { value: new THREE.Vector3(scaleOf(look.EyeScaleIndex, F.eye),
        piece(look.EyePositionXIndex, F.eye.u) * eyeX, -piece(look.EyePositionYIndex, F.eye.v) * eyeX) },
      browXf: { value: new THREE.Vector3(scaleOf(look.EyeBrowScaleIndex, F.brow),
        piece(look.EyeBrowPositionXIndex, F.brow.u) * eyeX, -piece(look.EyeBrowPositionYIndex, F.brow.v) * eyeX) },
      mouthXf: { value: new THREE.Vector3(scaleOf(look.MouthScaleIndex, F.mouth), 0, -piece(look.MouthPositionIndex, F.mouth.v) * eyeX) },
    });
  }
  return new THREE.ShaderMaterial({ uniforms: u, defines, vertexShader: VERT, fragmentShader: FRAG });
}

function setup() {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  scene = new THREE.Scene();
  cam = new THREE.PerspectiveCamera(26, 1, 0.05, 20);
  cam.position.set(3.9, 0.95, 1.1);
  ctl = new OrbitControls(cam, renderer.domElement);
  ctl.target.set(0, 0.66, 0);
  ctl.enablePan = false; ctl.minDistance = 0.9; ctl.maxDistance = 9; ctl.enableDamping = true;
  ctl.update();
  renderer.domElement.title = "Drag to turn, scroll to zoom, double-click for a face close-up";
  renderer.domElement.addEventListener("dblclick", () => faceView(!closeUp));
  const loop = () => {
    requestAnimationFrame(loop);
    if (!host || !host.isConnected) return;
    const w = host.clientWidth, h = host.clientHeight;
    const pr = renderer.getPixelRatio();
    if (w && h && (renderer.domElement.width !== Math.round(w * pr) || renderer.domElement.height !== Math.round(h * pr))) {
      renderer.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix();
      if (!closeUp) frame();
    }
    ctl.update();
    pose(performance.now());
    renderer.render(scene, cam);
  };
  loop();
}

// gear: {slot: wear model id}. Each worn piece replaces that slot's bare body part; hats and capes hang from their
// body sockets (their mesh's root bone is renamed to the socket so they attach like held items), and the hat picks
// the hair variant that fits under it.
function wornFiles(look, gear) {
  const p = manifest.parts, wear = manifest.wear || {}, body = p.BodyModelId[look.BodyModelId] || {};
  const worn = (slot) => wear[gear[slot]];
  const files = [];
  for (const slot of ["tops", "bottoms", "arm", "foot"]) {
    if (worn(slot)) files.push(...worn(slot).m);
    else if (!(slot === "bottoms" && worn("tops")?.dress)) files.push(...(body[slot] || []));
  }
  for (const slot of ["Head", "mantle"]) {
    const socket = manifest.sockets?.[slot];
    if (worn(slot) && socket) files.push(...worn(slot).m.map((f) => ({ f, socket })));
  }
  const rule = [worn("Head"), worn("mantle"), worn("tops")].find((w) => w?.hair)?.hair;
  const type = rule && (rule[look.HairModelId] || rule.None);
  const hair = type && manifest.hairTypes?.[look.HairModelId]?.[type];
  files.push(...(hair ? [hair] : p.HairModelId[look.HairModelId] || []));
  return files;
}

async function buildRig(look, heldFiles = [], gear = {}) {
  const p = manifest.parts;
  const opt = p.OptionPartsId[look.OptionPartsId] || {};
  const files = [
    ...(p.HeadModelId[look.HeadModelId] || []), ...wornFiles(look, gear), ...(p.EarPartsId[look.EarPartsId] || []),
    ...(opt.hideNose ? [] : p.NosePartsId[look.NosePartsId] || []), ...(opt.meshes || []), ...heldFiles,
  ];
  const roots = await Promise.all(files.map(async (f) => {
    const r = await glb(f.f || f);
    if (f.socket) r.traverse((o) => o.isBone && o.name === "root" && (o.name = f.socket));
    return r;
  }));
  let master = null;
  for (const r of roots) {
    const bones = {}; r.traverse((o) => o.isBone && (bones[o.name] = o));
    if (!master || Object.keys(bones).length > Object.keys(master).length) master = bones;
  }
  const group = new THREE.Group();
  group.add(Object.values(master)[0].parent);
  // bones a part adds below a shared bone (a weapon's "wpn" under R_hand_item_tag) move onto the shared skeleton
  const extra = [];
  for (const r of roots) r.traverse((o) => {
    if (o.isBone && master[o.name] !== o && !master[o.name] && o.parent?.isBone && master[o.parent.name] && master[o.parent.name] !== o.parent)
      extra.push(o);
  });
  for (const b of extra) master[b.parent.name].add(b);
  // Body sizes are applied in component space (Avatar_BoneModify_AnimBP: LocalToComponentSpace, then
  // CharamakeBoneModify), so a bone's scale only reshapes its own vertices and does not carry down the chain to
  // the hands and held items. The scale goes into the bind matrices instead of the bone.
  const sized = {};
  for (const [name, b] of Object.entries(manifest.sizes[look.BodyId] || {})) {
    const bone = master[name];
    if (!bone) continue;
    bone.position.add(new THREE.Vector3(...b.p));
    sized[name] = new THREE.Matrix4().makeScale(...b.s);
  }
  for (const bone of Object.values(master))
    bone.userData.base = { p: bone.position.clone(), q: bone.quaternion.clone(), s: bone.scale.clone() };
  group.userData.bones = master;
  group.updateMatrixWorld(true);
  for (const r of roots) {
    const meshes = []; r.traverse((o) => o.isSkinnedMesh && meshes.push(o));
    for (const m of meshes) {
      const name = (m.material.name || "").toLowerCase();
      const def = manifest.materials[name] || { type: "plain" };
      if (def.type === "face") {
        const g = m.geometry;
        g.setAttribute("aE1", g.attributes.uv1); g.setAttribute("aE2", g.attributes.uv2); g.setAttribute("aM", g.attributes.uv3);
      }
      m.material = shader(def.type, def, look);
      const sk = m.skeleton;
      const inverses = sk.bones.map((b, i) => sized[b.name] ? sized[b.name].clone().multiply(sk.boneInverses[i]) : sk.boneInverses[i]);
      m.bind(new THREE.Skeleton(sk.bones.map((b) => master[b.name] || b), inverses), m.bindMatrix);
      m.frustumCulled = false;
      group.add(m);
    }
  }
  return group;
}

// Game animations, applied as offsets from the skeleton's reference pose onto each bone's own rest pose (which
// already includes the body-size offsets), so body sizes and mesh-specific helper bones stay intact.
const POSES = [["menu", "Characters screen"], ["wardrobe", "Changing clothes"], ["field", "Standing in the field"], ["", "T-pose"]];
let poseKey = null, anim = null, lastLook = null, held = {}, onPose = null, gearSrc = null;
const _v = new THREE.Vector3(), _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _r = new THREE.Quaternion();

// Equipment-screen poses hold that life's weapon/tool (and shield): the save's equipped items, else the life's
// rented starter gear. The other poses are empty-handed, as on the Characters screen.
function heldFiles(key) {
  if (!key?.startsWith("life")) return [];
  // Empty gear {} = creation outfit: never fall back to rental starter tools.
  if (gearSrc && gearSrc !== "defaults" && !gearSrc.models && !gearSrc.items) return [];
  const ids = held[key]?.length ? held[key] : manifest.rental?.[key] || [];
  return ids.map((i) => manifest.items?.[i]).filter(Boolean);
}

// Armour: "defaults" dresses each life pose in that life's starter armour (GDSLifeData default*Id); otherwise the
// main character's gear in every pose, as wear model ids (live hook) or item ids (save).
function gearFor(key) {
  if (gearSrc === "defaults") return manifest.defaults?.[key] || {};
  if (gearSrc?.models) return gearSrc.models;
  return Object.fromEntries(Object.entries(gearSrc?.items || {}).map(([s, i]) => [s, manifest.armor?.[i]]));
}

async function rebuild() {
  const ticket = ++building;
  const [g, a] = await Promise.all([
    buildRig(lastLook, heldFiles(poseKey), gearFor(poseKey)),
    manifest.anims?.[poseKey] ? fetch(BASE + manifest.anims[poseKey], { cache: "no-cache" }).then((r) => r.json()).catch(() => null) : null,
  ]);
  if (ticket !== building) return;
  if (rig) scene.remove(rig);
  rig = g;
  anim = a;
  scene.add(rig);
}

async function setPose(key) {
  poseKey = key;
  document.querySelectorAll(".pose-bar select").forEach((s) => (s.value = key));
  if (lastLook) await rebuild();
}

function pose(now) {
  if (!anim || !rig) return;
  const span = anim.frames - 1;
  const f = (now / 1000 * anim.fps) % span, i = Math.floor(f), a = f - i, j = Math.min(i + 1, span);
  for (const [name, t] of Object.entries(anim.bones)) {
    const bone = rig.userData.bones[name];
    if (!bone) continue;
    const base = bone.userData.base;
    if (t.p) {
      _v.fromArray(t.p[i]).lerp(new THREE.Vector3().fromArray(t.p[j]), a).sub(new THREE.Vector3().fromArray(t.refP));
      bone.position.copy(base.p).add(_v);
    }
    if (t.r) {
      _q.fromArray(t.r[i]).slerp(_q2.fromArray(t.r[j]), a);
      _r.fromArray(t.refR).invert().multiply(_q);
      bone.quaternion.copy(base.q).multiply(_r);
    }
    if (t.s) bone.scale.copy(base.s).multiply(_v.fromArray(t.s[i]).lerp(new THREE.Vector3().fromArray(t.s[j]), a));
  }
}

// Life names come from the loaded save's summary; the default pose is the current life's Equipment-screen idle.
function poseBar(container, lives, currentLife) {
  if (poseKey === null) poseKey = manifest.anims?.[currentLife] ? currentLife : "menu";
  const existing = container.querySelector(".pose-bar select");
  if (existing) { existing.value = poseKey ?? ""; return; }
  const opt = ([k, label]) => `<option value="${k}" ${k === poseKey ? "selected" : ""}>${label}</option>`;
  const lifePoses = (lives || []).filter((l) => manifest.anims?.[l.id])
    .map((l) => [l.id, l.name + (l.id === currentLife ? " (current)" : "")]);
  const bar = document.createElement("div");
  bar.className = "pose-bar";
  bar.innerHTML = `<select title="Pose">
    <optgroup label="Equipment screen">${lifePoses.map(opt).join("")}</optgroup>
    <optgroup label="Other">${POSES.filter(([k]) => !k || manifest.anims?.[k]).map(opt).join("")}</optgroup></select>`;
  bar.querySelector("select").onchange = (e) => { setPose(e.target.value); onPose?.(e.target.value); };
  container.appendChild(bar);
}

// Full-body framing: fit about 1.75 m tall (room for hats and plumes) and 1.8 m wide (room for held tools) into the
// view, from the front-right.
let closeUp = false;
function frame() {
  const t = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
  const dist = Math.max(1.75 / (2 * t), 1.8 / (2 * t * cam.aspect));
  ctl.target.set(0, 0.76, 0);
  cam.position.copy(new THREE.Vector3(3.9, 0.3, 1.1).normalize().multiplyScalar(dist).add(ctl.target));
  ctl.update();
}

function faceView(close) {
  closeUp = close;
  if (!close) return frame();
  // Match Unholy's reference: upper chest through full hair (Ocean Spray / Slick Western).
  // Wider vertical span + slightly higher target so tall styles clear the frame top.
  const t = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
  const headSpan = 0.95;
  const dist = (headSpan / (2 * t)) * 1.25;
  ctl.target.set(0, 1.02, 0);
  cam.position.copy(new THREE.Vector3(3.6, 0.25, 1.05).normalize().multiplyScalar(dist).add(ctl.target));
  ctl.update();
}

// opts: lives / life (save summary), held ({life: [item ids]} from the save), gear ("defaults" or the main_gear
// API reply), pose (forces a pose, e.g. the life
// picked on the Licenses tab), bar (false hides the pose picker), barHost (element for the picker; default: on
// top of the view), onPose (called when the user picks a pose).
async function show(container, look, opts = {}) {
  if (!manifest) manifest = await fetch(BASE + "manifest.json", { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!manifest) { container.classList.add("no3d"); return false; }
  if (!renderer) setup();
  host = container;
  container.appendChild(renderer.domElement);
  if (opts.held) held = opts.held;
  gearSrc = opts.gear || null;
  onPose = opts.onPose || null;
  if (opts.pose === "" || manifest.anims?.[opts.pose]) poseKey = opts.pose;
  if (opts.bar === false) { if (poseKey === null) poseKey = "menu"; } else poseBar(opts.barHost || container, opts.lives, opts.life);
  lastLook = look;
  await rebuild();
  // Always re-frame: face tabs on Look pull in; Adventurer / Licenses / body stay full-body.
  // (Do not keep a leftover close-up when leaving Look — that stuck Adventurer on the face.)
  faceView(!!opts.faceClose);
  return true;
}

window.Look3D = { show, faceView };
window.dispatchEvent(new Event("look3d-ready"));
