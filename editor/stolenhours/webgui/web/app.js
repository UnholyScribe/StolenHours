"use strict";

const TOKEN = new URLSearchParams(location.search).get("t") || "";
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const h = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

async function api(method, args = {}) {
  const r = await fetch("/api/" + method, {
    method: "POST", headers: { "X-Token": TOKEN, "Content-Type": "application/json" }, body: JSON.stringify(args),
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error);
  return j.data;
}

const S = { state: null, sum: null, view: "overview", life: null, cat: null, items: [], item: null,
            filter: "", allPockets: false, addPick: null, results: [], log: [] };

// ---------- game data labels ----------
const LIFE_GROUP = (id) => {
  const n = Number(id.slice(4));
  return n === 0 ? "base" : n <= 4 ? "combat" : n <= 8 ? "gather" : "craft";
};
const LIFE_LABEL = { life0000: "No License" };
const lifeName = (l) => LIFE_LABEL[l.id] || String(l.name).replace("?", "");
const POCKETS = {
  invConsume: "Consumables", invWeapon: "Weapons", invLifeTools: "Life Tools", invShield: "Shields",
  invArmor: "Outfits", invCraft: "Crafted", invKit: "Kits", invMaterial: "Materials", invRecipe: "Recipes",
  invImportant: "Key Items", invMount: "Mounts", invPlantDungeonBranch: "Branches", invPowerUp: "Power-Ups",
};
const pocketName = (c) => POCKETS[c] || c.replace(/^inv/, "").replace(/SupportChara/, "Ally ")
  .replace(/InstantChara/, "Guest ").replace(/([a-z])([A-Z])/g, "$1 $2");
const MAIN_POCKETS = Object.keys(POCKETS);
const SCREENS = {
  overview: ["Adventurer", "nav_overview"], lives: ["Licenses", "nav_lives"], inventory: ["Bag", "nav_inventory"],
  appearance: ["Look", "nav_appearance"], map: ["Map", "nav_map"], livemap: ["Live Map", "nav_livemap"],
  island: ["Island", "nav_island"], live: ["Time Hook", "nav_live"], collection: ["Collection", "nav_collection"],
  forge: ["Vulcan's Forge", "nav_forge"], file: ["Records", "nav_file"], backups: ["Backups", "nav_backups"],
};

// ---------- feedback ----------
let toastTimer;
function toast(text, err = false) {
  const t = $("#toast");
  t.textContent = text; t.className = err ? "err" : ""; t.hidden = false;
  t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), err ? 6000 : 2600);
}
function status(text, warn = false) {
  const s = $("#status-text"); s.textContent = text; s.classList.toggle("warn", warn);
}
function dialog(title, body, buttons = [["OK", "green", true]], badge = true) {
  return new Promise((resolve) => {
    $("#dialog-title").textContent = title;
    $("#dialog-body").textContent = body;
    $(".dialog-badge").classList.toggle("hide", !badge);
    const box = $("#dialog-actions"); box.innerHTML = "";
    for (const [label, kind, value] of buttons) {
      const b = document.createElement("button");
      b.className = "btn btn-" + kind; b.textContent = label;
      b.onclick = () => { $("#dialog-veil").hidden = true; resolve(value); };
      box.appendChild(b);
    }
    $("#dialog-veil").hidden = false;
    box.lastChild.focus();
  });
}
const confirmDlg = (title, body) => dialog(title, body, [["Cancel", "cream", false], ["OK", "green", true]]);
async function busy(text, fn) {
  $("#busy-text").textContent = text; $("#busy").hidden = false;
  try { return await fn(); } finally { $("#busy").hidden = true; }
}
async function attempt(fn, okText) {
  try {
    const r = await fn();
    if (okText) toast(okText);
    return r;
  } catch (e) {
    dialog("That didn't work", e.message);
    return undefined;
  }
}

// ---------- title screen ----------
async function initTitle() {
  try { S.state = await api("state"); } catch (e) { $("#title-note").textContent = e.message; return; }
  const sel = $("#save-select");
  const saves = S.state.saves.length ? S.state.saves : [S.state.path].filter(Boolean);
  sel.innerHTML = saves.map((p) => `<option value="${h(p)}">${h(shortPath(p))}</option>`).join("") +
    `<option value="__custom">Other file...</option>`;
  $("#title-note").textContent = saves.length ? `${saves.length} save(s) found automatically.` :
    "No save found automatically. Choose Other file and paste the path to gamedata.bin.";
  if (!S.state.assets) $("#title-note").textContent += "  Game art not built yet: run  py -3.12 -m stolenhours build-ui";
  if (window.Music) {
    await Music.load();
    Music.bind();
    // Browsers need a gesture. Skip the Music button (it handles itself) so we don't
    // start then immediately mute on the same click.
    const kick = (ev) => {
      if (ev.target.closest?.("[data-music-toggle]")) return;
      Music.start();
      document.removeEventListener("pointerdown", kick, true);
    };
    document.addEventListener("pointerdown", kick, true);
  }
  $("#start-btn").onclick = startGame;
}
function shortPath(p) {
  const parts = p.split(/[\\/]/);
  return parts.length > 4 ? `...\\${parts.slice(-4).join("\\")}` : p;
}
async function startGame() {
  let path = $("#save-select").value;
  if (path === "__custom") {
    path = prompt("Full path to the save (gamedata.bin):") || "";
    if (!path) return;
  }
  if (window.Music) Music.start();
  const st = await attempt(() => api("state"));
  const keep = st && st.loaded && st.dirty && (!path || st.path === path);
  const sum = await busy("Opening your save...", () => attempt(() => (keep ? api("summary") : api("load", { path }))));
  if (!sum) return;
  S.sum = sum; S.ev = null;
  document.body.classList.add("in-menu");
  $("#menu").hidden = false;
  if (window.Music) Music.bind();
  show("overview");
  status(`Loaded ${shortPath(sum.path)}. Decrypt, parse and repack all checked byte-exact.`);
  poll();
  setInterval(poll, 2000);
}

// ---------- shell ----------
function show(view) {
  S.view = view;
  S.boardLife = null;
  lmStop();
  $$("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  const [title, icon] = SCREENS[view];
  $("#screen-title").textContent = title;
  $("#screen-icon").src = `game/${icon}.png`;
  render();
}
function render() {
  $("#top-dosh").textContent = fmt(S.sum?.money);
  const lives = () => (S.boardLife ? vBoard() : vLives());
  const fn = { overview: vOverview, lives, inventory: vInventory, appearance: vAppearance, map: vMap,
    livemap: vLiveMap, island: vIsland, live: vLive, collection: vCollection, forge: vForge, file: vFile,
    backups: vBackups }[S.view];
  fn();
  updateButtons();
}
function updateButtons() {
  const st = S.state || {};
  const dirty = !!S.sum?.dirty;
  $("#save-btn").disabled = !dirty || st.game_running;
  $("#save-btn").classList.toggle("nudge", dirty && !st.game_running);
  $("#revert-btn").disabled = !dirty;
  $("#save-btn").title = st.game_running ? "Close the game first: saves are never written while it runs." : "";
}
async function poll() {
  const wasAlive = S.state?.mod_alive;
  try { S.state = await api("state"); } catch { return; }
  if (S.view === "map" && S.ev && wasAlive !== S.state.mod_alive) drawMap();
  const st = S.state;
  const chip = $("#mode-chip");
  chip.classList.toggle("b", st.game_running);
  chip.innerHTML = `<span class="dot ${st.mod_alive ? "on" : ""}"></span>` +
    (st.game_running ? "Game running · file locked" : "Game closed · file editable");
  chip.title = st.mod_alive ? "Time Hook mod connected" : "Time Hook mod not connected";
  if (S.view === "live") liveStatus();
  updateButtons();
  if (st.stale) await followDisk();
}
// the game saved: pick that up, unless it would throw away the user's own edits or typing
async function followDisk() {
  if (S.reloading || !S.sum) return;
  if (S.sum.dirty) {
    status("The game saved since you opened this file. Your edits can't be saved over it: press Revert to load the new save, then redo them.", true);
    return;
  }
  if (document.activeElement?.matches("input, textarea, select") || !$("#dialog-veil").hidden) return;
  S.reloading = true;
  try {
    const sum = await api("load", { path: S.sum.path });
    S.sum = sum; S.item = null; S.boardData = null; S.ev = null;
    render();
    status("The game saved; the editor reloaded the new save.");
  } catch { /* the game may still be writing; next poll retries */ }
  finally { S.reloading = false; }
}
function afterEdit(sum, text) {
  if (sum) S.sum = sum;
  render();
  status("Unsaved changes. Use Save to file when the game is closed.", true);
  if (text) toast(`${text}. Not in your save yet: press Save to file.`);
}
const icon = (src, cls = "", alt = "") => `<img class="${cls}" src="${src}" alt="${h(alt)}" onerror="this.style.visibility='hidden'">`;
const itemIcon = (it) => `<img src="game/items/${h(it.icon || it.id)}.png" alt="" onerror="this.outerHTML='<div class=noicon>${h(it.id)}</div>'">`;

// ---------- 3D character (shared by Adventurer, Licenses and Look) ----------
const VIEW3D_KEY = "stolenhours.view3d";
const use3d = () => !!window.Look3D && !S.no3d && localStorage.getItem(VIEW3D_KEY) !== "0";
const viewToggle = () => `<div class="view-toggle" title="Show the game's 2D art or your character in 3D">
  <button data-v3="0" class="${use3d() ? "" : "active"}">2D</button><button data-v3="1" class="${use3d() ? "active" : ""}">3D</button></div>`;
function bindViewToggle() {
  $$("[data-v3]").forEach((b) => (b.onclick = () => { localStorage.setItem(VIEW3D_KEY, b.dataset.v3); render(); }));
}
// Appearance and held items come from the editor's copy of the save, so unsaved edits show up. Armour is the main
// character's (live hook, else its last reading, else the save) unless opts.gear is set ({} = bare creation outfit).
async function stage3d(box, opts = {}, fallback = render) {
  const [look, held, gear] = await Promise.all([
    attempt(() => api("appearance")),
    ("held" in opts) ? Promise.resolve(opts.held) : attempt(() => api("held_items")),
    ("gear" in opts) ? Promise.resolve(opts.gear) : attempt(() => api("main_gear")),
  ]);
  if (!look || !box.isConnected) return;
  S.look = look;
  box.classList.add("is3d");
  const fail = (e) => { if (e) console.error(e); S.no3d = true; fallback(); };
  window.Look3D.show(box, look, { lives: S.sum.lives, life: S.sum.life, held: held || {}, ...opts, gear: gear || {} })
    .then((ok) => ok || fail()).catch(fail);
}

// ---------- Adventurer ----------
function vOverview() {
  const s = S.sum;
  const life = s.lives.find((l) => l.id === s.life) || { id: s.life, name: s.life };
  const hrs = Math.floor(s.play_time / 3600), mins = Math.floor((s.play_time % 3600) / 60);
  const three = use3d();
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: 1fr 1.15fr">
    <div class="ov-portrait ${three ? "stage-mode" : ""}">
      ${viewToggle()}
      ${three ? `<div class="stage" id="ov-stage"></div>` : icon(`game/life/${life.id}_portrait.png`, "portrait")}
      <div class="plate"><div class="who">${h(s.name)}</div><div class="ribbon">${h(lifeName(life))} · Lv ${life.level ?? "?"}</div>
        ${three ? `<div class="pose-host" id="ov-pose"></div>` : ""}</div>
    </div>
    <div class="panel scroll"><div class="pad">
      <div class="band"><span>Adventurer</span></div>
      <label class="field-label">Name</label>
      <input type="text" id="ov-name" maxlength="64" value="${h(s.name)}">
      <label class="field-label">Dosh</label>
      <div class="big-dosh">${icon("game/coin.png")}<input type="number" id="ov-money" min="0" max="${s.money_max}" value="${s.money}"></div>
      <div class="quick">
        <button class="btn btn-cream btn-small" data-add="10000">+10,000</button>
        <button class="btn btn-cream btn-small" data-add="100000">+100,000</button>
        <button class="btn btn-cream btn-small" data-add="1000000">+1,000,000</button>
        <button class="btn btn-orange btn-small" data-set="9999999">9,999,999</button>
      </div>
      <div class="divider"></div>
      <div class="stat-grid">
        <div><label class="field-label">Island</label><input type="text" id="ov-island" maxlength="${s.island_max}" value="${h(s.island)}"></div>
        <div><label class="field-label">Play time</label><div class="row pt-row">
          <input type="number" id="ov-hours" min="0" max="${Math.floor(s.play_time_max / 3600)}" value="${hrs}"><span>h</span>
          <input type="number" id="ov-mins" min="0" max="59" value="${mins}"><span>m</span></div></div>
        <div><label class="field-label">Current license</label><input type="text" readonly value="${h(lifeName(life))}"></div>
        <div><label class="field-label">Licenses held</label><input type="text" readonly value="${s.lives.filter((l) => l.rank > 0 && l.id !== "life0000").length}"></div>
      </div>
      <div class="row" style="margin-top:18px; justify-content:flex-end; padding-left:60px">
        <span class="muted">Edits stay in the editor until you press Save to file.</span>
        <button class="btn btn-green shrink" id="ov-apply">Apply</button>
      </div>
      <div class="note">The island name and play time are each stored once in the save, with no record of changes, so an edit looks
        the same as if it had always been that way. Play time can't go past the real time since you started the adventure
        (${fmt(Math.floor(s.play_time_max / 3600))}h). Steam's own hours are kept by Steam and don't change.
        The in-game Dosh cap is not confirmed yet; the save field holds up to ${fmt(s.money_max)}.</div>
    </div></div>
  </div>`;
  $$("[data-add]").forEach((b) => (b.onclick = () => {
    const m = $("#ov-money"); m.value = Math.min(s.money_max, Number(m.value || 0) + Number(b.dataset.add));
  }));
  $$("[data-set]").forEach((b) => (b.onclick = () => ($("#ov-money").value = b.dataset.set)));
  bindViewToggle();
  if (three) stage3d($("#ov-stage"), { barHost: $("#ov-pose"), pose: S.ovPose ?? s.life, onPose: (p) => (S.ovPose = p) });
  $("#ov-apply").onclick = async () => {
    const h_ = Number($("#ov-hours").value || 0), m_ = Number($("#ov-mins").value || 0);
    // keep the seconds the save already has when hours and minutes are unchanged
    const play_time = h_ === hrs && m_ === mins ? s.play_time : h_ * 3600 + m_ * 60;
    const sum = await attempt(() => api("set_overview", { name: $("#ov-name").value, money: Number($("#ov-money").value),
      island: $("#ov-island").value, play_time }));
    if (sum) afterEdit(sum, "Adventurer updated");
  };
}

// ---------- Licenses ----------
function vLives() {
  const s = S.sum;
  if (!S.life) S.life = s.life;
  const groups = [["combat", "Combat"], ["gather", "Gathering"], ["craft", "Crafting"], ["base", "Other"]];
  const card = (l) => `
    <div class="card ${LIFE_GROUP(l.id)} ${l.rank > 0 || l.id === "life0000" ? "" : "locked"} ${S.life === l.id ? "selected" : ""}" data-life="${l.id}">
      ${l.id === s.life ? icon("game/check.png", "current", "current") : ""}
      <div class="card-rank">${l.rank > 0 ? "Rank " + l.rank : l.id === "life0000" ? "" : "Not licensed"}</div>
      ${icon(`game/life/${l.id}.png`, "card-icon")}
      <div class="card-name">${h(lifeName(l))}</div>
      ${l.level ? `<div class="card-lv">Lv ${l.level}</div>` : ""}
    </div>`;
  const sel = s.lives.find((l) => l.id === S.life) || s.lives[0];
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: 1.7fr 1fr">
    <div class="scroll">
      ${groups.map(([g, label]) => {
        const ls = s.lives.filter((l) => LIFE_GROUP(l.id) === g);
        return ls.length ? `<div class="group-title">${label}</div><div class="cards">${ls.map(card).join("")}</div>` : "";
      }).join("")}
    </div>
    <div class="life-side">
      <div class="portrait-box ${use3d() ? "stage-mode" : ""}">${viewToggle()}
        ${use3d() ? `<div class="stage" id="lf-stage"></div>` : icon(`game/life/${sel.id}_portrait.png`)}</div>
      <div class="info-plate">
        <div class="head">
          ${icon(`game/life/${sel.id}.png`)}
          <div style="text-align:center"><div class="ribbon">${h(lifeName(sel))}</div></div>
          <div class="lvbig"><small>LV</small>${sel.level ?? 0}</div>
        </div>
        <div class="row" style="margin-top:8px">
          <div><label class="field-label">Level</label><input type="number" id="lf-level" min="0" max="65535" value="${sel.level ?? 0}"></div>
          <div><label class="field-label">Exp</label><input type="number" id="lf-exp" min="0" value="${sel.exp ?? 0}"></div>
          <div><label class="field-label">Rank</label><input type="number" id="lf-rank" min="0" max="20" value="${sel.rank ?? 0}"></div>
        </div>
        <div class="muted" style="margin-top:6px">Stars ${sel.star} · skill points ${sel.skillMaxPoint}. Level and rank caps in game are not confirmed yet.</div>
        ${sel.id === "life0000" ? "" : `<div class="muted" style="margin-top:4px">Skill Board opens this Life's panels (or double-click a License).</div>`}
        <div class="row" style="justify-content:flex-end;margin-top:10px">
          ${sel.id === "life0000" ? "" : `<button class="btn btn-orange shrink" id="lf-board">Skill Board</button>`}
          <button class="btn btn-green shrink" id="lf-apply">Apply</button></div>
      </div>
    </div>
  </div>`;
  // each click redraws the cards, so a double-click is two clicks on the same Life within 400 ms
  $$("[data-life]").forEach((c) => (c.onclick = () => {
    const id = c.dataset.life, again = S.lastLifeClick?.id === id && Date.now() - S.lastLifeClick.at < 400;
    S.life = id;
    S.lastLifeClick = { id, at: Date.now() };
    if (again && id !== "life0000") { S.boardLife = id; S.boardData = null; S.boardPick = null; vBoard(); }
    else vLives();
  }));
  bindViewToggle();
  if (use3d()) stage3d($("#lf-stage"), { pose: sel.id, bar: false, gear: "defaults" });
  $("#lf-apply").onclick = async () => {
    const sum = await attempt(() => api("set_life", {
      life_id: sel.id, level: Number($("#lf-level").value), exp: Number($("#lf-exp").value), rank: Number($("#lf-rank").value),
    }));
    if (sum) afterEdit(sum, `${lifeName(sel)} updated`);
  };
  const boardBtn = $("#lf-board");
  if (boardBtn) boardBtn.onclick = () => { S.boardLife = sel.id; S.boardData = null; S.boardPick = null; vBoard(); };
}

// ---------- Skill board (inside Licenses) ----------
// Icon art: tex_icon_skillboard_0000<family><shape>; shape 0 technique, 1 unique, 2 stat (matches the game's
// skill list); family 0 dark (out of reach), 1 lock, 2 grey glow (learnable), 3/5/7 learned combat/gather/craft.
const SB_SHAPE = { technique: 0, unique: 1, status: 2 };
const SB_FAMILY = { combat: 3, gather: 5, craft: 7 };
const SB_LINE = { combat: "#33b6ff", gather: "#4fd43c", craft: "#ff63b0" };
const sbArt = (n) => `game/skillboard/tex_icon_skillboard_${String(n).padStart(6, "0")}.png`;
async function vBoard() {
  const life = S.boardLife;
  if (!S.boardData || S.boardData.life !== life) {
    $("#view").innerHTML = `<div class="view"><div class="pad muted">Opening the skill board...</div></div>`;
    const [data, skills] = await Promise.all([attempt(() => api("skill_board", { life_id: life })),
      S.sbSkills || fetch("game/skillboard/boards.json").then((r) => r.json()).then((j) => j.skills).catch(() => ({}))]);
    S.sbSkills = skills;
    if (!data || S.boardLife !== life) { if (!data) { S.boardLife = null; vLives(); } return; }
    S.boardData = data;
  }
  drawBoard();
}
function sbSkill(p) {
  return (S.sbSkills || {})[p.skill] || { kind: "status", name: p.skill || "Empty panel", desc: "", params: [] };
}
function sbDesc(sk) {
  return String(sk.desc || "").replace(/<SKILL_PARAM_(\d+)>/g, (_, i) => sk.params?.[i - 1] ?? "?")
    .replace(/<CMD_[A-Z_]+>/g, "the skill button");
}
function sbCond(c) {
  const life = S.sum.lives.find((l) => l.id === c.life);
  if (c.type === "rank") return `${life && life.id !== S.boardLife ? lifeName(life) + " " : ""}license rank ${c.rank}`;
  if (c.type === "panels") return `${c.count} panels learned`;
  return c.type;
}
function drawBoard() {
  const d = S.boardData, life = S.sum.lives.find((l) => l.id === d.life);
  const group = LIFE_GROUP(d.life), C = 44;
  const ps = d.panels, byNo = Object.fromEntries(ps.map((p) => [p.no, p]));
  const xs = ps.map((p) => p.x), ys = ps.map((p) => p.y);
  const x0 = Math.min(...xs) - 1, y0 = Math.min(...ys) - 1;
  const W = (Math.max(...xs) - x0 + 1) * C, H = (Math.max(...ys) - y0 + 1) * C;
  const at = (p) => [(p.x - x0) * C, (p.y - y0) * C];
  const lit = (p) => p.status === "learned" || p.status === "root" || (p.blank && !!byNo[p.parent] && lit(byNo[p.parent]));
  const lines = ps.filter((p) => byNo[p.parent]).map((p) => {
    const [x1, y1] = at(byNo[p.parent]), [x2, y2] = at(p), on = lit(p) && lit(byNo[p.parent]);
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="${on ? "on" : p.status === "hidden" ? "off" : ""}"
      ${on ? `style="stroke:${SB_LINE[group]}"` : ""}/>`;
  }).join("");
  const nodes = ps.map((p) => {
    const [x, y] = at(p);
    if (p.status === "root") {
      const s = C * 2.3;
      return `<g class="sb-root"><image href="${sbArt(200 + ({ combat: 0, gather: 1, craft: 2 }[group] ?? 0))}" x="${x - s / 2}" y="${y - s / 2}" width="${s}" height="${s}"/>
        <image href="game/life/${d.life}.png" x="${x - C * 0.62}" y="${y - C * 0.62}" width="${C * 1.24}" height="${C * 1.24}"/></g>`;
    }
    if (p.blank) return `<circle cx="${x}" cy="${y}" r="${C * 0.12}" class="sb-dot ${lit(p) ? "on" : ""}"/>`;
    const shape = SB_SHAPE[sbSkill(p).kind] ?? 2;
    const art = p.status === "learned" ? SB_FAMILY[group] * 10 + shape
      : p.status === "available" ? (p.conds.length ? 11 : 20 + shape)
      : p.status === "locked" ? 10 : (p.conds.length ? 3 : shape);
    const s = C * (p.special ? 1.2 : 1.0) * (p.status === "learned" ? 1.12 : 1);
    return `<g class="sb-node ${p.status} ${S.boardPick === p.no ? "picked" : ""}" data-no="${p.no}">
      <image href="${sbArt(art)}" x="${x - s / 2}" y="${y - s / 2}" width="${s}" height="${s}"/>
      ${p.status === "available" || p.status === "locked" ? `<text x="${x}" y="${y + C * 0.62}">${p.cost}</text>` : ""}</g>`;
  }).join("");
  const sp = d.sp;
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: minmax(0, 1fr) 310px">
    <div class="board-wrap" id="sb-wrap">
      <svg class="board" id="sb-svg" preserveAspectRatio="xMidYMid meet" style="--sb:${SB_LINE[group]}">${lines}${nodes}</svg>
      <div class="board-hint">Left-click learns · right-click forgets (and everything after it) · wheel zooms, drag moves</div>
    </div>
    <div class="life-side">
      <div class="info-plate sb-side">
        <div class="head">
          ${icon(`game/life/${d.life}.png`)}
          <div style="text-align:center"><div class="ribbon">${h(lifeName(life))}</div></div>
          <div class="lvbig"><small>LV</small>${life.level ?? 0}</div>
        </div>
        <div class="sb-stats">
          <div><span class="k">SP free</span><span class="v ${sp.free < 0 ? "bad" : ""}">${sp.free}</span></div>
          <div><span class="k">SP earned</span><span class="v">${sp.earned}</span></div>
          <div><span class="k">Panels</span><span class="v">${d.learned} / ${d.total}</span></div>
        </div>
        <div class="sb-detail" id="sb-detail"></div>
        <label class="sb-free"><input type="checkbox" id="sb-free" ${S.sbFree ? "checked" : ""}>
          Ignore game rules: learn any panel with the path to it; SP earned grows to pay for it</label>
        <div class="row sb-actions">
          <button class="btn btn-cream btn-small" id="sb-back">Back</button>
          <button class="btn btn-cream btn-small" id="sb-reset" title="Forget every panel on this board">Reset</button>
          <button class="btn btn-orange btn-small" id="sb-all">Learn all</button>
        </div>
      </div>
    </div>
  </div>`;
  sbDetail(byNo[S.boardPick]);
  sbZoom(d.life, [-C / 2, -C / 2, W + C, H + C]);
  $$(".sb-node").forEach((n) => {
    const p = byNo[n.dataset.no];
    n.onmouseenter = () => sbDetail(p);
    n.onmouseleave = () => sbDetail(byNo[S.boardPick]);
    n.onclick = () => { if (S.sbDragged) return; S.boardPick = p.no; sbEdit("learn", p); };
    n.oncontextmenu = (e) => { e.preventDefault(); S.boardPick = p.no; sbEdit("remove", p); };
  });
  $("#sb-free").onchange = (e) => (S.sbFree = e.target.checked);
  $("#sb-back").onclick = () => { S.boardLife = null; vLives(); };
  $("#sb-all").onclick = async () => {
    if (await confirmDlg("Learn every panel?", `Every panel on the ${lifeName(life)} board gets learned. SP earned grows to cover the cost (the level stays as it is).`)) sbEdit("learn_all");
  };
  $("#sb-reset").onclick = async () => {
    if (await confirmDlg("Reset this board?", `Every learned ${lifeName(life)} panel is forgotten and its SP comes back.`)) sbEdit("reset");
  };
}
// Wheel zooms toward the cursor, dragging pans; the view per board survives redraws after each edit.
function sbZoom(life, full) {
  const svg = $("#sb-svg");
  S.sbViews = S.sbViews || {};
  const v = S.sbViews[life] = S.sbViews[life] || full.slice();
  const apply = () => svg.setAttribute("viewBox", v.join(" "));
  apply();
  const toBoard = (e) => {
    const r = svg.getBoundingClientRect(), s = Math.max(v[2] / r.width, v[3] / r.height);
    return [v[0] + v[2] / 2 + (e.clientX - r.left - r.width / 2) * s, v[1] + v[3] / 2 + (e.clientY - r.top - r.height / 2) * s, s];
  };
  svg.onwheel = (e) => {
    e.preventDefault();
    const [bx, by] = toBoard(e);
    const k = Math.min(Math.max(e.deltaY > 0 ? 1.15 : 1 / 1.15, full[2] / 6 / v[2]), full[2] * 1.2 / v[2]);
    v[0] = bx - (bx - v[0]) * k; v[1] = by - (by - v[1]) * k; v[2] *= k; v[3] *= k;
    apply();
  };
  svg.onmousedown = (e) => {
    if (e.button !== 0) return;
    const start = [e.clientX, e.clientY], v0 = v.slice(), s = toBoard(e)[2];
    S.sbDragged = false;
    const move = (m) => {
      const dx = m.clientX - start[0], dy = m.clientY - start[1];
      if (!S.sbDragged && Math.hypot(dx, dy) < 5) return;
      S.sbDragged = true;
      v[0] = v0[0] - dx * s; v[1] = v0[1] - dy * s; apply();
    };
    const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up);
      setTimeout(() => (S.sbDragged = false), 0); };
    addEventListener("mousemove", move); addEventListener("mouseup", up);
  };
  svg.ondblclick = () => { v.splice(0, 4, ...full); apply(); };
}
function sbDetail(p) {
  const box = $("#sb-detail");
  if (!box) return;
  if (!p) { box.innerHTML = `<div class="muted">Point at a panel to see what it does.</div>`; return; }
  const sk = sbSkill(p);
  const label = { learned: "Learned", available: "Can learn", locked: "Locked", hidden: "Out of reach" }[p.status] || "";
  box.innerHTML = `
    <div class="sb-name">${h(sk.name)}</div>
    <div class="sb-tags"><span class="tag ${p.status}">${label}</span><span class="tag">${h(sk.kind)}</span>
      <span class="tag">${p.cost} SP</span>${p.lifeLimit ? `<span class="tag">this life only</span>` : ""}</div>
    <div class="sb-desc">${h(sbDesc(sk)) || "&nbsp;"}</div>
    ${p.conds.map((c) => `<div class="sb-cond ${c.met ? "met" : ""}">${c.met ? "✓" : "✗"} Needs ${h(sbCond(c))}</div>`).join("")}`;
}
async function sbEdit(action, p) {
  if (p && p.blank) return;
  const r = await attempt(() => api("skill_edit", { life_id: S.boardLife, action, no: p ? p.no : -1, free: !!S.sbFree }));
  if (!r) return;
  S.boardData = r.board; S.sum = r.summary;
  drawBoard();
  updateButtons();
  status("Unsaved changes. Use Save to file when the game is closed.", true);
}

// ---------- Bag ----------
async function loadItems() {
  if (!S.details) S.details = await fetch("game/items/details.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
  S.items = await attempt(() => api("items", { category: S.cat })) || [];
  if (S.item) S.item = S.items.find((i) => i.index === S.item.index) || null;
}
async function vInventory() {
  const s = S.sum;
  if (!S.cat) S.cat = s.categories.includes("invMaterial") ? "invMaterial" : s.categories[0];
  await loadItems();
  drawInventory();
}
function drawInventory() {
  const s = S.sum;
  const cats = s.categories.filter((c) => S.allPockets || MAIN_POCKETS.includes(c) || s.counts[c] > 0);
  const q = S.filter.toLowerCase();
  const items = S.items.filter((i) => !q || i.name.toLowerCase().includes(q) || i.id.includes(q));
  const it = S.item;
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: 1.7fr 1fr">
    <div style="display:flex;flex-direction:column;min-height:0">
      <div class="tabs">
        ${cats.map((c) => `<div class="tab ${c === S.cat ? "active" : ""} ${s.counts[c] ? "" : "empty"}" data-cat="${c}">${h(pocketName(c))}<span class="n">${s.counts[c]}</span></div>`).join("")}
        <div class="tab" id="all-pockets">${S.allPockets ? "Fewer pockets" : "All pockets"}</div>
      </div>
      <div class="row" style="padding:0 6px 10px 50px"><input type="text" id="inv-filter" placeholder="Filter this pocket..." value="${h(S.filter)}"></div>
      <div class="scroll" style="flex:1">
        <div class="tiles">
          ${items.map((i) => `<div class="tile ${it && it.index === i.index ? "selected" : ""}" data-idx="${i.index}" title="${h(i.name)}">
             ${itemIcon(i)}${i.stock != null ? `<div class="stock">${i.stock}</div>` : ""}</div>`).join("")
          || `<div class="muted" style="grid-column:1/-1;padding:20px">Nothing in this pocket.</div>`}
        </div>
      </div>
    </div>
    <div class="panel scroll"><div class="pad">
      <div class="band"><span>${it ? "Item" : "Pick an item"}</span></div>
      ${it ? `
        <img class="detail-icon" src="game/items/${h(it.icon || it.id)}.png" alt="" onerror="this.style.visibility='hidden'">
        <div class="detail-name">${h(it.name)}</div>
        <div class="muted" style="text-align:center">${h(it.id)} · slot ${it.index}</div>
        ${itemDetails(it)}
        ${it.stock != null ? `
          <label class="field-label">Quantity</label>
          <div class="stepper"><button class="minus" data-step="-1"></button><input type="number" id="it-stock" min="1" max="65535" value="${it.stock}"><button class="plus" data-step="1"></button></div>
          <div class="quick"><button class="btn btn-cream btn-small" data-q="99">99</button><button class="btn btn-cream btn-small" data-q="999">999</button>
          <button class="btn btn-green btn-small" id="it-set" style="margin-left:auto">Set</button></div>`
        : `<div class="note">This pocket holds single items (no stack count).</div>`}` :
        `<div class="muted" style="text-align:center;padding:10px">Select something on the left to change its quantity.</div>`}
      <div class="band band-gap"><span>Add to ${h(pocketName(S.cat))}</span></div>
      <input type="text" id="add-q" placeholder="Name or id..." title="Search ${h(pocketName(S.cat))} by name or id">
      <div class="results scroll" id="add-results"></div>
      <div class="row" style="margin-top:8px">
        <div><label class="field-label">Quantity</label><input type="number" id="add-n" min="1" max="65535" value="1"></div>
        <button class="btn btn-green shrink" id="add-go" style="margin-top:28px">Add</button>
      </div>
      <div class="note">Gear added here comes out plain, at the lowest grade it's made in. To pick its grade, quality and
        skills, use Vulcan. Whether every item works when added is not confirmed in game yet.</div>
    </div></div>
  </div>`;
  $$("[data-cat]").forEach((t) => (t.onclick = async () => { S.cat = t.dataset.cat; S.item = null; S.addPick = null; S.results = []; await loadItems(); drawInventory(); }));
  $("#all-pockets").onclick = () => { S.allPockets = !S.allPockets; drawInventory(); };
  const f = $("#inv-filter");
  f.oninput = () => { S.filter = f.value; const pos = f.selectionStart; drawInventory(); const nf = $("#inv-filter"); nf.focus(); nf.setSelectionRange(pos, pos); };
  $$("[data-idx]").forEach((t) => (t.onclick = () => { S.item = S.items.find((i) => i.index === Number(t.dataset.idx)); drawInventory(); }));
  $$("[data-step]").forEach((b) => (b.onclick = () => { const n = $("#it-stock"); n.value = Math.max(1, Math.min(65535, Number(n.value) + Number(b.dataset.step))); }));
  $$("[data-q]").forEach((b) => (b.onclick = () => ($("#it-stock").value = b.dataset.q)));
  if ($("#it-set")) $("#it-set").onclick = async () => {
    const items = await attempt(() => api("set_stock", { category: S.cat, index: it.index, stock: Number($("#it-stock").value) }));
    if (items) { S.items = items; S.item = items.find((i) => i.index === it.index); S.sum.dirty = true; afterEdit(null, `${it.name} × ${S.item.stock}`); }
  };
  const aq = $("#add-q");
  let timer;
  aq.oninput = () => { clearTimeout(timer); timer = setTimeout(async () => { S.results = await attempt(() => api("search_items", { query: aq.value, pocket: S.cat })) || []; drawResults(); }, 180); };
  drawResults();
  $("#add-go").onclick = async () => {
    if (!S.addPick) { toast("Search and pick an item first", true); return; }
    const r = await attempt(() => api("add_item", { category: S.cat, item_id: S.addPick.id, stock: Number($("#add-n").value) }));
    if (r) {
      S.items = r.items; S.item = r.items.find((i) => i.index === r.slot); S.sum.counts[S.cat] = r.items.length; S.sum.dirty = true;
      afterEdit(null, `Added ${S.addPick.name}`);
    }
  };
}
function itemDetails(it) {
  const D = S.details;
  if (!D) return "";
  const rows = [];
  const g = it.gear, info = D.gear[it.id];
  if (g) {
    const tags = [g.grade ? D.grades[g.grade] : "", `${D.qualities[g.quality] || g.quality} quality`, g.equipped ? "Equipped" : ""].filter(Boolean);
    rows.push(`<div class="it-tags">${tags.map((t) => `<span>${h(t)}</span>`).join("")}</div>`);
    if (info && g.grade) {
      for (const [label, list] of info.stats) {
        const v = list[g.grade - 1];
        rows.push(`<div class="it-stat"><span>${h(label)}</span><b>${v > 1 ? fmt(v) : "—"}</b></div>`);
      }
    }
    if (g.bonus) rows.push(`<div class="it-stat"><span>Bonus stat</span><b>${h(D.status[g.bonus] || g.bonus)}</b></div>`);
    for (const s of g.skills) rows.push(`<div class="it-skill">${h(D.skills[s]?.desc || D.skills[s]?.name || s)}</div>`);
    if (!g.skills.length) rows.push(`<div class="it-skill none">No skills</div>`);
    if (g.quality) rows.push(`<div class="it-hint">Stats shown are the base for this grade; the game adds the quality bonus on top.</div>`);
  }
  for (const e of D.effects[it.id] || []) rows.push(`<div class="it-skill">${h(e)}</div>`);
  const price = D.prices?.[it.id], at = g?.grade ? g.grade - 1 : 0;
  if (price?.sell[at]) {
    const total = it.stock > 1 ? ` <small>(${fmt(it.stock)}: ${fmt(price.sell[at] * it.stock)})</small>` : "";
    rows.push(`<div class="it-stat"><span>Sells for</span><b>${fmt(price.sell[at])} Dosh${total}</b></div>`);
  }
  if (price?.buy[at]) rows.push(`<div class="it-stat"><span>Shop price</span><b>${fmt(price.buy[at])} Dosh</b></div>`);
  return rows.length ? `<div class="it-details">${rows.join("")}</div>` : "";
}
function drawResults() {
  const box = $("#add-results");
  if (!box) return;
  box.innerHTML = S.results.map((r) => `<div class="result ${S.addPick && S.addPick.id === r.id ? "selected" : ""}" data-pick="${h(r.id)}">
      <img src="game/items/${h(r.icon || r.id)}.png" alt="" onerror="this.style.visibility='hidden'"><span>${h(r.name)}</span>
      <span class="id">${r.pocket_guess ? "pocket unconfirmed · " : ""}${h(r.id)}</span></div>`).join("") ||
    ($("#add-q")?.value ? `<div class="muted" style="padding:8px">No ${h(pocketName(S.cat))} match. Items only go in their own pocket.</div>` : "");
  $$("[data-pick]", box).forEach((d) => (d.onclick = () => { S.addPick = S.results.find((r) => r.id === d.dataset.pick); drawResults(); }));
}

// ---------- Look ----------
// Slider ranges: positions 0-20 (centre 10) and eyebrow size 0-2 are spanned by the game's own presets
// (GDSAvatarPresetData); eye/mouth size above the preset maximum (3 / 2) is UNVERIFIED.
const LOOK_SLIDERS = {
  EyeBrowPartsId: [["EyeBrowPositionXIndex", "Spacing", 0, 20], ["EyeBrowPositionYIndex", "Height", 0, 20], ["EyeBrowScaleIndex", "Size", 0, 2]],
  EyePartsId: [["EyePositionXIndex", "Spacing", 0, 20], ["EyePositionYIndex", "Height", 0, 20], ["EyeScaleIndex", "Size", 0, 4, 3]],
  MouthPartsId: [["MouthPositionIndex", "Height", 0, 20], ["MouthScaleIndex", "Size", 0, 4, 2]],
};
const LOOK_GROUPS = [["Body", ["BodyModelId", "BodyId", "VoiceId"]], ["Face", ["HeadModelId", "FaceColorId", "OptionPartsId", "EarPartsId"]],
  ["Hair", ["HairModelId", "HairColorId"]], ["Eyes", ["EyePartsId", "EyeColorId", "EyeBrowPartsId"]], ["Nose & Mouth", ["NosePartsId", "MouthPartsId"]]];
// Same idea as the in-game create-a-character screen: head tabs pull the camera in.
const LOOK_FACE_FIELDS = new Set(LOOK_GROUPS.filter(([g]) => g !== "Body").flatMap(([, fs]) => fs));

async function lookCatalog() {
  if (!S.lookCat) S.lookCat = await fetch("game/avatar/catalog.json").then((r) => r.json()).catch(() => ({ fields: [] }));
  return S.lookCat;
}

async function vAppearance() {
  const [cat, app] = await Promise.all([lookCatalog(), attempt(() => api("appearance"))]);
  if (!app) return;
  S.look = app;
  S.lookField = S.lookField || "HairModelId";
  if (S.lookBare == null) S.lookBare = true; // Look tab defaults to the creation outfit
  drawLook();
}

function lookOpt(field, id) {
  const f = S.lookCat.fields.find((x) => x.field === field);
  return f && f.options.find((o) => o.id === id);
}

function drawLook() {
  const cat = S.lookCat, app = S.look;
  const field = cat.fields.find((f) => f.field === S.lookField) || cat.fields[0];
  const cur = app[field.field];
  const opts = field.options.filter((o) => S.lookAll || !o.hidden || o.id === cur);
  const hiddenN = field.options.filter((o) => o.hidden).length;
  const hairTint = field.field === "HairModelId" && lookOpt("HairColorId", app.HairColorId)?.color;
  const pick = (o) => o.color
    ? `<div class="swatch ${o.id === cur ? "selected" : ""}" data-opt="${h(o.id)}" title="${h(o.name || o.id)}" style="--c:${o.color}"></div>`
    : `<div class="opt ${o.id === cur ? "selected" : ""} ${o.hidden ? "unused" : ""}" data-opt="${h(o.id)}" title="${h(o.id)}">
        ${o.icon && hairTint ? `<div class="tinted" style="--c:${hairTint};--m:url('${h(o.icon)}')"><img src="${h(o.icon)}" alt=""></div>`
          : o.icon ? `<img src="${h(o.icon)}" alt="">` : `<div class="opt-text">${h(o.name || o.id)}</div>`}
        ${o.unlock ? `<span class="lock" title="Unlocked in game by an item; picking it here works anyway"></span>` : ""}
        <span class="opt-name">${h(o.name || o.id)}</span></div>`;
  const sliders = LOOK_SLIDERS[field.field] || [];
  const summary = cat.fields.map((f) => {
    const o = lookOpt(f.field, app[f.field]);
    const vis = o?.color ? `<i class="sw" style="--c:${o.color}"></i>` : o?.icon ? `<img src="${h(o.icon)}" alt="">` : "";
    return `<div class="pick-row ${f.field === field.field ? "active" : ""}" data-field="${h(f.field)}">${vis}<span class="k">${h(f.label)}</span>
      <span class="v">${h(o?.name || app[f.field])}</span></div>`;
  }).join("");

  $("#view").innerHTML = `
  <div class="view look">
    <div class="panel scroll look-card"><div class="pad">
      <div class="band"><span>Your character</span></div>
      <div id="look-preview" class="look-preview"></div>
      <div class="row look-sub" style="margin-top:8px">
        <label class="check" title="Bare body like the create-a-character screen: no armor, no held gear, creation idle">
          <input type="checkbox" id="look-bare" ${S.lookBare ? "checked" : ""}> Creation outfit</label>
      </div>
      <div class="pick-list">${summary}</div>
    </div></div>
    <div class="panel look-main"><div class="pad">
      <div class="tabs look-tabs">${LOOK_GROUPS.map(([g, fs]) => fs.map((fid) => {
        const f = cat.fields.find((x) => x.field === fid);
        return f ? `<div class="tab ${fid === field.field ? "active" : ""}" data-field="${fid}">${h(f.label)}</div>` : "";
      }).join("")).join("")}</div>
      <div class="band"><span>${h(field.label)}</span></div>
      <div class="row look-sub">
        <span class="muted">${opts.length} options · current: <b>${h(lookOpt(field.field, cur)?.name || cur)}</b></span>
        ${hiddenN ? `<label class="check"><input type="checkbox" id="look-all" ${S.lookAll ? "checked" : ""}> Show ${hiddenN} unused game entries</label>` : ""}
      </div>
      <div class="scroll look-opts ${field.kind === "color" ? "swatches" : ""}">${opts.map(pick).join("")}</div>
      ${sliders.length ? `<div class="look-sliders">${sliders.map(([k, label, lo, hi, seen]) => `
        <div class="slider-row"><span class="k">${h(label)}</span>
          <input type="range" min="${lo}" max="${hi}" step="1" value="${app[k]}" data-slider="${k}">
          <span class="v" id="sv-${k}">${app[k]}</span>
          ${seen != null && app[k] > seen ? `<span class="warn" title="Above what the game's own presets use; not confirmed in game">?</span>` : ""}</div>`).join("")}
        <div class="note">Spacing and height centre at 10.</div></div>` : ""}
    </div></div>
  </div>`;
  drawLookPreview();
  $(".look-opts .selected")?.scrollIntoView({ block: "nearest" });

  $$("[data-field]").forEach((t) => (t.onclick = () => { S.lookField = t.dataset.field; drawLook(); }));
  if ($("#look-all")) $("#look-all").onchange = (e) => { S.lookAll = e.target.checked; drawLook(); };
  if ($("#look-bare")) $("#look-bare").onchange = (e) => {
    S.lookBare = e.target.checked;
    if (S.lookBare) S.lookPose = "menu";
    drawLook();
  };
  $$("[data-opt]").forEach((d) => (d.onclick = () => setLook({ [field.field]: d.dataset.opt })));
  $$("[data-slider]").forEach((r) => {
    r.oninput = () => ($("#sv-" + r.dataset.slider).textContent = r.value);
    r.onchange = () => setLook({ [r.dataset.slider]: Number(r.value) });
  });
}

async function setLook(values) {
  const r = await attempt(() => api("set_appearance", { values }));
  if (!r) return;
  S.look = r;
  S.sum.dirty = true;
  updateButtons();
  status("Unsaved changes. Use Save to file when the game is closed.", true);
  drawLook();
}

function drawLookPreview() {
  const box = $("#look-preview");
  if (!box) return;
  if (window.Look3D && !S.no3d) {
    const faceClose = LOOK_FACE_FIELDS.has(S.lookField);
    const opts = {
      pose: S.lookBare ? "menu" : (S.lookPose ?? "menu"),
      faceClose,
      onPose: (p) => { S.lookPose = p; },
    };
    if (S.lookBare) { opts.gear = {}; opts.held = {}; opts.bar = true; }
    stage3d(box, opts, drawLookPreview);
    return;
  }
  box.classList.remove("is3d");
  const icon = (f) => lookOpt(f, S.look[f])?.icon;
  const color = (f) => lookOpt(f, S.look[f])?.color || "transparent";
  box.innerHTML = `<div class="paperdoll" style="--skin:${color("FaceColorId")};--hair:${color("HairColorId")};--eye:${color("EyeColorId")}">
    ${["HeadModelId", "HairModelId", "EyePartsId", "EyeBrowPartsId", "NosePartsId", "MouthPartsId", "EarPartsId", "OptionPartsId", "BodyModelId"]
      .map((f) => !icon(f) ? "" : f === "HairModelId"
        ? `<div class="pd-part pd-${f} tinted" style="--c:var(--hair);--m:url('${h(icon(f))}')"><img src="${h(icon(f))}" alt=""></div>`
        : `<div class="pd-part pd-${f}"><img src="${h(icon(f))}" alt=""></div>`).join("")}
    <div class="pd-chips"><i style="--c:var(--skin)" title="Skin"></i><i style="--c:var(--hair)" title="Hair"></i><i style="--c:var(--eye)" title="Eyes"></i></div>
  </div>`;
}

// ---------- Map (the game's Active Events) ----------
const EV_CATS = [["all", "All"], ["legendary", "Legendary"], ["boss", "Rare boss"], ["special", "Special"],
  ["monster", "Monster"], ["battle", "Battle"], ["gathering", "Gathering"], ["delivery", "Delivery"], ["other", "Other"]];
const EV_CAT_LABEL = Object.fromEntries(EV_CATS);
const EV_WEATHER = { 1: "Sunny", 2: "Rainy", 3: "Cloudy" };
function evCond(c) {
  const areas = S.evCat.areas;
  if (c.type === "period") return c.period ? "Night only" : "Day only";
  if (c.type === "area") return `${areas[c.area] || c.area} rank ${c.rank}+`;
  if (c.type === "rank") {
    const l = S.sum.lives.find((x) => x.id === c.life);
    return `${l ? lifeName(l) : c.life} rank ${c.rank}+`;
  }
  if (c.type === "weather") return `${EV_WEATHER[c.weather] || c.weather} only`;
  if (c.type === "flag") return "Story flag";
  return c.type;
}
async function vMap() {
  if (!S.evCat) {
    try { S.evCat = await (await fetch("game/events/events.json")).json(); }
    catch { $("#view").innerHTML = `<div class="view panel"><div class="pad"><div class="band"><span>Map</span></div>
      <div class="note">Map events not built yet: run  py -3.12 -m stolenhours build-ui</div></div></div>`; return; }
    S.evById = Object.fromEntries(S.evCat.events.map((e) => [e.id, e]));
  }
  if (!S.ev) S.ev = await attempt(() => api("events"));
  if (!S.ev) return;
  S.evFilter ??= { cat: "all", area: "", q: "", allowed: false };
  drawMap();
}
function drawMap() {
  const f = S.evFilter, ev = S.ev, cat = S.evCat;
  const live = new Set(ev.live.map((l) => l.id));
  const t = ev.time;
  const areaOpts = Object.entries(cat.areas).map(([id, n]) => `<option value="${id}" ${f.area === id ? "selected" : ""}>${h(n)}</option>`).join("");
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: minmax(0, 1fr) 330px">
    <div class="panel" style="display:flex;flex-direction:column;min-height:0;padding:0 18px 14px">
      <div class="band"><span>Map Events</span></div>
      <div class="tabs">${EV_CATS.map(([k, label]) => `<button class="tab ${f.cat === k ? "active" : ""}" data-evcat="${k}">${label}</button>`).join("")}</div>
      <div class="row ev-filters">
        <select id="ev-area"><option value="">All areas</option>${areaOpts}</select>
        <input type="text" id="ev-q" placeholder="Event name..." value="${h(f.q)}">
      </div>
      <label class="ev-check ev-allowed"><input type="checkbox" id="ev-allowed" ${f.allowed ? "checked" : ""}> Only ones the game would pick right now</label>
      <div class="ev-list scroll" id="ev-list"></div>
    </div>
    <div class="panel scroll ev-side"><div class="pad">
      <div class="band"><span>On the Map</span></div>
      <div class="sb-stats"><div><span class="k">Live</span><span class="v">${ev.live.length}</span></div>
        <div><span class="k">Game max</span><span class="v">${ev.mapSize}</span></div>
        <div><span class="k">Cleared</span><span class="v">${ev.cleared.length}</span></div></div>
      <div class="ev-live">${ev.live.length ? ev.live.map((l) => {
        const e = S.evById[l.id] || { title: l.id };
        return `<div class="ev-live-row"><span title="${h(l.id)}">${h(e.title)}<small>${h(cat.areas[e.area] || "")}</small></span>
          <button class="ev-x" data-evoff="${h(l.id)}" title="Take it off the map">✕</button></div>`;
      }).join("") : `<div class="muted" style="padding:8px 2px">No events on the map in this save.</div>`}</div>
      <div class="quick">
        <button class="btn btn-cream btn-small" id="ev-clear" ${ev.live.length ? "" : "disabled"}>Clear map</button>
        <button class="btn btn-cream btn-small" id="ev-reset" ${ev.cleared.length ? "" : "disabled"} title="Cleared events become available again">Reset cleared</button>
      </div>
      <label class="field-label">Random draw</label>
      <div class="row"><input type="number" id="ev-count" min="1" max="30" value="${S.evCount ?? ev.mapSize}" class="shrink" style="width:76px">
        <button class="btn btn-orange btn-small" id="ev-draw">Draw</button></div>
      <label class="ev-check"><input type="checkbox" id="ev-rules" ${S.evRules === false ? "" : "checked"}> Follow the game's rules</label>
      <label class="ev-check"><input type="checkbox" id="ev-onlycat" ${S.evOnlyCat ? "checked" : ""}> Only the ${h(EV_CAT_LABEL[f.cat] === "All" ? "listed" : EV_CAT_LABEL[f.cat])} category</label>
      <div class="band"><span>Time &amp; Weather</span></div>
      <div class="muted">Day ${t.day} · ${String(t.hour).padStart(2, "0")}:${String(t.minute).padStart(2, "0")} · ${t.period ? "Night" : "Day"} · ${[...new Set(t.weather)].map((w) => EV_WEATHER[w] || w).join(" / ")}</div>
      <div class="row" style="margin-top:6px">
        <input type="number" class="shrink ev-clock" id="ev-hour" min="0" max="23" value="${t.hour}" title="Hour">
        <input type="number" class="shrink ev-clock" id="ev-min" min="0" max="59" value="${t.minute}" title="Minute">
        <select id="ev-period"><option value="0" ${t.period ? "" : "selected"}>Day</option><option value="1" ${t.period ? "selected" : ""}>Night</option></select>
      </div>
      <div class="row" style="margin-top:8px">
        <select id="ev-weather">${Object.entries(EV_WEATHER).map(([k, n]) => `<option value="${k}" ${t.weather[0] == k ? "selected" : ""}>${n}</option>`).join("")}</select>
        <button class="btn btn-green btn-small shrink" id="ev-time">Apply</button>
      </div>
      <div class="note">The game reads these when it loads the save. Not confirmed in game yet: that events put on the map show up,
        and that the clock is in game minutes. Save, load the game, and check the map.</div>
      <div class="band"><span>Live Game</span></div>
      ${S.state?.mod_alive ? `
        <div class="muted" id="ev-live-clock">${h(S.evLiveText || "Read the running game's clock first.")}</div>
        <div class="quick">
          <button class="btn btn-cream btn-small" id="ev-live-read">Read</button>
          <button class="btn btn-green btn-small" id="ev-live-set">Set time &amp; weather in game</button>
        </div>
        <div class="note">Uses the time and weather fields above and writes them straight into the running game. Whether the sky
          and events follow right away is not confirmed yet: watch the in-game clock after setting it.</div>`
      : `<div class="muted">Start the game with the Time Hook mod to read and set its clock live.</div>`}
    </div></div>
  </div>`;
  drawEventList();
  $$("[data-evcat]").forEach((b) => (b.onclick = () => { f.cat = b.dataset.evcat; drawMap(); }));
  $("#ev-area").onchange = (e) => { f.area = e.target.value; drawEventList(); };
  $("#ev-q").oninput = (e) => { f.q = e.target.value; drawEventList(); };
  $("#ev-allowed").onchange = (e) => { f.allowed = e.target.checked; drawEventList(); };
  $$("[data-evoff]").forEach((b) => (b.onclick = () => evEdit("dismiss", { ids: [b.dataset.evoff] })));
  $("#ev-clear").onclick = async () => {
    if (await confirmDlg("Clear the map?", "Take every event off the map? The game draws new ones by itself as time passes.")) evEdit("clear");
  };
  $("#ev-reset").onclick = () => evEdit("reset_progress");
  $("#ev-draw").onclick = async () => {
    S.evCount = Number($("#ev-count").value) || ev.mapSize;
    S.evRules = $("#ev-rules").checked; S.evOnlyCat = $("#ev-onlycat").checked;
    const cats = S.evOnlyCat && f.cat !== "all" ? [f.cat] : null;
    if (!(await confirmDlg("Random draw?", `Clear the map and draw ${S.evCount} event(s) with the game's own weights` +
      `${S.evRules ? ", only ones the game allows right now" : ", ignoring time of day, area rank, weather and story flags"}?`))) return;
    evEdit("draw", { count: S.evCount, rules: S.evRules, cats });
  };
  const liveRead = $("#ev-live-read");
  if (liveRead) {
    liveRead.onclick = evLiveRead;
    $("#ev-live-set").onclick = async () => {
      const c = S.evLive || await evLiveRead();
      if (!c) return;
      const day = Math.floor(c.time / 1440);
      const minutes = day * 1440 + Number($("#ev-hour").value) * 60 + Number($("#ev-min").value);
      if (!(await confirmDlg("Change the running game?", `Set the game's clock to ${$("#ev-hour").value}:${String($("#ev-min").value).padStart(2, "0")} (${$("#ev-period").selectedOptions[0].text}), weather ${$("#ev-weather").selectedOptions[0].text}?`))) return;
      for (const [action, value] of [["set_time", minutes], ["set_period", $("#ev-period").value], ["set_weather", $("#ev-weather").value]]) {
        const r = await attempt(() => api("live", { action, value: String(value) }));
        if (!r || !r.ok) { dialog("The game refused", r ? r.text : "no reply"); return; }
      }
      await evLiveRead();
      toast("Clock and weather set in game");
    };
  }
  $("#ev-time").onclick = async () => {
    const r = await evEdit("time", { hour: Number($("#ev-hour").value), minute: Number($("#ev-min").value), period: Number($("#ev-period").value) }, true);
    if (r) evEdit("weather", { weather: Number($("#ev-weather").value) }, false, "Time and weather set");
  };
}
const liveNum = (s) => Number((String(s).match(/-?\d+(\.\d+)?(?=\)?$)/) || [NaN])[0]);
async function evLiveRead() {
  const r = await attempt(() => api("live", { action: "get_clock" }));
  if (!r) return null;
  if (!r.ok) { S.evLiveText = `Couldn't read: ${r.text}`; S.evLive = null; }
  else {
    const t = liveNum(r.clock.time), p = liveNum(r.clock.period), w = liveNum(r.clock.weather);
    const m = Math.floor(t) % 1440;
    S.evLive = { time: t, period: p, weather: w };
    S.evLiveText = `In game now: day ${Math.floor(t / 1440) + 1}, ${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")} · ${p ? "Night" : "Day"} · ${EV_WEATHER[w] || w}`;
  }
  const el = $("#ev-live-clock"); if (el) el.textContent = S.evLiveText;
  return S.evLive;
}
function drawEventList() {
  const f = S.evFilter, ev = S.ev;
  const live = new Set(ev.live.map((l) => l.id));
  const q = f.q.trim().toLowerCase();
  const rows = S.evCat.events.filter((e) => (f.cat === "all" || e.cat === f.cat) && (!f.area || e.area === f.area)
    && (!q || e.title.toLowerCase().includes(q)) && (!f.allowed || !ev.unmet[e.id]));
  rows.sort((a, b) => (live.has(b.id) - live.has(a.id)) || (a.rate - b.rate) || a.title.localeCompare(b.title));
  const shown = rows.slice(0, 250);
  $("#ev-list").innerHTML = shown.length ? shown.map((e) => {
    const unmet = ev.unmet[e.id];
    const on = live.has(e.id);
    return `<div class="ev-row ${on ? "on" : ""}">
      <div class="ev-main">
        <div class="ev-title">${h(e.title)}</div>
        <div class="sb-tags"><span class="tag ev-${e.cat}">${h(EV_CAT_LABEL[e.cat] || e.cat)}</span>
          <span class="tag ev-area">${h(S.evCat.areas[e.area] || e.area)}</span>
          ${e.conds.map((c) => `<span class="tag ev-cond">${h(evCond(c))}</span>`).join("")}</div>
        <div class="muted">Weight ${e.rate} (${e.share < 0.1 ? e.share.toFixed(3) : e.share.toFixed(2)}% of the pool) · Gold: ${fmt(e.reward.dosh)} Dosh, ${e.reward.chestnut} chestnuts, ${fmt(e.reward.areaPoint)} area pts
          ${unmet ? `<br><span class="ev-unmet">Game wouldn't pick it now: ${h(unmet.join(", "))}</span>` : ""}</div>
      </div>
      <button class="btn ${on ? "btn-cream" : "btn-green"} btn-small shrink" data-ev="${h(e.id)}" data-on="${on ? 1 : 0}">${on ? "Remove" : "Put on map"}</button>
    </div>`;
  }).join("") + (rows.length > shown.length ? `<div class="muted" style="padding:8px">${rows.length - shown.length} more: narrow the filter.</div>` : "")
    : `<div class="muted" style="padding:12px">No events match.</div>`;
  $$("[data-ev]").forEach((b) => (b.onclick = () => evEdit(b.dataset.on === "1" ? "dismiss" : "emerge", { ids: [b.dataset.ev] })));
}
async function evEdit(action, args = {}, quiet = false, okText = null) {
  const r = await attempt(() => api("events_edit", { action, ...args }));
  if (!r) return null;
  S.ev = r.events;
  if (quiet) return r;
  const msg = okText || r.note || { emerge: "Put on the map", dismiss: "Taken off the map", clear: "Map cleared" }[action] || "Done";
  afterEdit(r.summary, msg);
  return r;
}

// ---------- Live Map (read-only view of the running game) ----------
// The viewport stands in for a 1920x1080 game screen scaled to fit. Zoom steps, scroll margin and the map's texture
// width come from each map's <map>_GDSMapMinimap row; icons are the 64x64 MenuLayer_Map_Icon widget scaled per step by
// GDSMapIconData. Event icons and glows also take the table's mapIconScale (0.8): checked against the game at the
// Medium step, where it matches the measured tree icon and glow within ~8%; the player arrow does not take it.
// UNVERIFIED: glow size at the other steps (zoom-scaled icons taken as 64px at the first step) and the ripple, which
// is rebuilt from mat_map_000012's parameters.
const LM_ICON_PX = 64;
const LM_SCREEN_H = 1080;
const LM_STEPS = [["small", "s"], ["Medium", "m"], ["large", "l"]];
const LM_POLL_MS = 1500;
const LM_PHASE = { 1: "On the map", 2: "In progress", 3: "Second phase", open: "Open" };
function lmStop() { clearTimeout(S.lmTimer); S.lmTimer = null; }
// StolenHours mod shipped inside the editor: status + install/update into this PC's game (UE4SS must be there)
async function modBox(box) {
  const st = await attempt(() => api("mod_status"));
  if (!st || !box.isConnected) return;
  const line = !st.game ? "Fantasy Life i wasn't found on this PC."
    : !st.ue4ss ? "UE4SS isn't installed in the game folder. Install UE4SS first; the editor then adds its own mod."
    : st.current ? `Installed and up to date (${h(st.installed)}).`
    : st.installed ? `Installed: ${h(st.installed)}${st.enabled ? "" : " (switched off)"}. This editor has ${h(st.bundled)}.`
    : `Not installed. This editor has ${h(st.bundled)}.`;
  const can = st.ue4ss && !st.current;
  box.innerHTML = `<div class="muted">${line}</div>${can ? `<div class="quick">
    <button class="btn btn-green btn-small" id="mod-install">${st.installed ? "Update mod" : "Install mod"}</button></div>` : ""}`;
  const b = $("#mod-install", box);
  if (b) b.onclick = async () => {
    if (S.state?.game_running) { dialog("Close the game first", "The mod can only be installed while Fantasy Life i is closed."); return; }
    if (!(await confirmDlg("Install the StolenHours mod?", `Copy the StolenHours mod ${st.bundled} into the game's UE4SS Mods folder and switch it on? Any existing copy is backed up first.`))) return;
    const r = await busy("Installing the mod...", () => attempt(() => api("mod_install")));
    if (r) toast(`StolenHours mod ${r.installed} installed. Start the game to use it`);
    modBox(box);
  };
}
async function vLiveMap() {
  if (!S.lmMeta?.maps) {
    try { S.lmMeta = await (await fetch("game/mapview/mapview.json", { cache: "no-cache" })).json(); if (!S.lmMeta.maps) throw 0; }
    catch { $("#view").innerHTML = `<div class="view panel"><div class="pad"><div class="band"><span>Live Map</span></div>
      <div class="note">Live map not built yet: run  py -3.12 -m stolenhours build-ui</div></div></div>`; return; }
  }
  S.lm ??= { map: S.lmMeta.eventMap, step: 0, u: 0.5, v: 0.5, follow: true, off: new Set(LM_OFF_START), q: "" };
  const groups = [[2, "Ginormosia"], [1, "Past"], [0, "Present"]];
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: minmax(0, 1fr) 320px">
    <div class="panel lm-panel"><div class="lm-vp" id="lm-vp">
      <img class="lm-art" id="lm-art" alt="" draggable="false">
      <div class="lm-layer" id="lm-layer"></div>
      <div class="lm-veil" id="lm-veil" hidden></div>
      <div class="lm-tip" id="lm-tip" hidden></div>
      <div class="lm-zoom"><button id="lm-in" title="Zoom in">+</button>
        <button id="lm-out" title="Zoom out">−</button>
        <button id="lm-me" title="Follow you">◎</button></div>
    </div></div>
    <div class="panel lm-side"><div class="pad lm-side-top">
      <div class="band"><span>Live Map</span></div>
      <div id="lm-status"></div>
      <div id="lm-mod"></div>
      <select id="lm-map">${groups.map(([r, label]) => `<optgroup label="${label}">${S.lmMeta.maps.filter((m) => m.region === r)
        .map((m) => `<option value="${m.id}">${h(m.name)}</option>`).join("")}</optgroup>`).join("")}</select>
      <div class="band"><span>Show</span></div>
      <div class="lm-cats" id="lm-cats"></div>
      <input id="lm-q" placeholder="Search this map..." value="${h(S.lm.q)}">
    </div>
    <div class="scroll lm-list" id="lm-list"></div>
    <div class="pad lm-side-foot"><div class="note">View only: nothing here changes the game. Places, gathering spots and
      monsters come from the game's map data, so some may still be hidden in your game until found or unlocked
      (UNVERIFIED per kind). Map events and your position are live from the running game.</div></div>
    </div>
  </div>`;
  $("#lm-map").value = S.lm.map;
  $("#lm-map").onchange = (e) => lmSetMap(e.target.value, false);
  $("#lm-q").oninput = (e) => { S.lm.q = e.target.value; lmList(); };
  lmBind();
  lmSetMap(S.lm.map, S.lm.follow);
  lmTick();
  modBox($("#lm-mod"));
}
const LM_OFF_START = ["wood", "ore", "fish", "crop", "monster", "request"];
const lmMap = () => S.lmMeta.maps.find((m) => m.id === S.lm.map) || S.lmMeta.maps[0];
function lmUvOf(m, x, y) {
  const b = m.bounds;
  return { u: (b.maxY - y) / (b.maxY - b.minY), v: (x - b.minX) / (b.maxX - b.minX) };
}
function lmPlayer() {
  const p = S.lmLive?.player, m = lmMap();
  return p && p.map === m.id ? { ...p, ...lmUvOf(m, p.x, p.y) } : null;
}
function lmSetMap(id, follow) {
  if (!S.lmMeta.maps.some((m) => m.id === id)) return;
  const changed = id !== S.lm.map || !$("#lm-art").getAttribute("src");
  S.lm.map = id; S.lm.follow = follow;
  if (changed) {
    const m = lmMap();
    if (m.art) $("#lm-art").src = `game/mapview/${m.art}`; else $("#lm-art").removeAttribute("src");
    S.lm.u = S.lm.v = 0.5; S.lm.step = 0;
    $("#lm-map").value = id;
  }
  lmCats();
  lmList();
  lmLayout();
}
function lmBind() {
  const vp = $("#lm-vp");
  let drag = null;
  vp.onpointerdown = (e) => { if (e.target.closest(".lm-zoom")) return; drag = { x: e.clientX, y: e.clientY, u: S.lm.u, v: S.lm.v }; vp.setPointerCapture(e.pointerId); };
  vp.onpointermove = (e) => {
    if (drag) {
      S.lm.u = drag.u - (e.clientX - drag.x) / S.lm.zoom; S.lm.v = drag.v - (e.clientY - drag.y) / S.lm.zoom;
      S.lm.follow = false; lmLayout();
    }
  };
  vp.onpointerup = () => (drag = null);
  vp.onwheel = (e) => {
    e.preventDefault();
    const r = vp.getBoundingClientRect();
    lmStep(e.deltaY < 0 ? 1 : -1, e.clientX - r.left, e.clientY - r.top);
  };
  $("#lm-in").onclick = () => lmStep(1);
  $("#lm-out").onclick = () => lmStep(-1);
  $("#lm-me").onclick = () => {
    const p = S.lmLive?.player;
    if (p && p.map !== S.lm.map && S.lmMeta.maps.some((m) => m.id === p.map)) lmSetMap(p.map, true);
    else { S.lm.follow = true; lmLayout(); }
  };
  new ResizeObserver(() => lmLayout()).observe(vp);
}
const lmUi = () => $("#lm-vp").clientHeight / LM_SCREEN_H;
const lmZoom = (step = S.lm.step) => lmMap().textureSize * lmMap().zoom[LM_STEPS[step][0]] * lmUi();
function lmStep(dir, px, py) {
  const vp = $("#lm-vp"), step = Math.max(0, Math.min(LM_STEPS.length - 1, S.lm.step + dir));
  if (step === S.lm.step) return;
  px ??= vp.clientWidth / 2; py ??= vp.clientHeight / 2;
  const z = lmZoom(), nz = lmZoom(step);
  // keep the map point under the cursor in place
  const mu = S.lm.u + (px - vp.clientWidth / 2) / z, mv = S.lm.v + (py - vp.clientHeight / 2) / z;
  S.lm.u = mu - (px - vp.clientWidth / 2) / nz; S.lm.v = mv - (py - vp.clientHeight / 2) / nz;
  S.lm.step = step;
  lmLayout();
}
function lmLayout() {
  const vp = $("#lm-vp");
  if (!vp || !vp.clientWidth) return;
  const m = lmMap(), z = lmZoom(), p = lmPlayer();
  S.lm.zoom = z;
  if (S.lm.follow && p) { S.lm.u = p.u; S.lm.v = p.v; }
  // the game scrolls from scrollMin to scrollMax texture px, i.e. a margin past each edge of the map
  const lo = m.scroll[0] / m.textureSize, hi = m.scroll[1] / m.textureSize;
  const clamp = (c, half) => (hi - lo < 2 * half ? (lo + hi) / 2 : Math.min(hi - half, Math.max(lo + half, c)));
  S.lm.u = clamp(S.lm.u, vp.clientWidth / z / 2);
  S.lm.v = clamp(S.lm.v, vp.clientHeight / z / 2);
  const ox = vp.clientWidth / 2 - S.lm.u * z, oy = vp.clientHeight / 2 - S.lm.v * z;
  const art = $("#lm-art");
  art.style.width = art.style.height = `${z}px`;
  art.style.transform = `translate(${ox}px, ${oy}px)`;
  S.lm.ox = ox; S.lm.oy = oy;
  lmDraw();
}
function lmIcon(type, px, extra = "") {
  const ic = S.lmMeta.icons[type];
  return `<img class="lm-ic ${extra}" src="game/mapview/icons/${type}.png" alt="" draggable="false"
    style="width:${px}px;height:${px}px;margin:${-px / 2}px 0 0 ${-px / 2}px;z-index:${ic?.priority ?? 100}">`;
}
const lmLiveEvents = () => (lmMap().id === S.lmMeta.eventMap && !S.lm.off.has("events") ? S.lmLive?.events || [] : [])
  .filter((ev) => S.lmMeta.events[ev.id]);
function lmMarkers() {
  const q = S.lm.q.trim().toLowerCase();
  return lmMap().markers.filter((k) => !S.lm.off.has(k[0]) && (!q || `${k[4]} ${k[5]}`.toLowerCase().includes(q)));
}
function lmDraw() {
  const layer = $("#lm-layer");
  if (!layer) return;
  const m = lmMap(), M = S.lmMeta, z = S.lm.zoom, tier = LM_STEPS[S.lm.step][1], ui = lmUi();
  const iconPx = LM_ICON_PX * ui * m.mapIconScale;
  const glowPx = iconPx * m.zoom[LM_STEPS[S.lm.step][0]] / m.zoom.small;
  const W = layer.clientWidth, H = layer.clientHeight, pad = iconPx * 2;
  const at = (u, v) => `left:${S.lm.ox + u * z}px;top:${S.lm.oy + v * z}px`;
  const inView = (u, v) => { const x = S.lm.ox + u * z, y = S.lm.oy + v * z; return x > -pad && y > -pad && x < W + pad && y < H + pad; };
  let html = "";
  lmMarkers().forEach((k) => {
    if (!inView(k[2], k[3])) return;
    const ic = M.icons[k[1]];
    html += `<div class="lm-mark" data-mk="${m.markers.indexOf(k)}" style="${at(k[2], k[3])}">${lmIcon(k[1], iconPx * (ic?.scale[tier] ?? 1))}</div>`;
  });
  for (const ev of lmLiveEvents()) {
    const e = M.events[ev.id];
    const ic = M.icons[e.icon], gl = M.icons[e.glow];
    const px = iconPx * ic.scale[tier];
    html += `<div class="lm-mark" data-lm="${h(ev.id)}" style="${at(e.u, e.v)}">
      ${gl ? lmIcon(e.glow, glowPx * gl.scale[tier], "lm-glow") : ""}
      <div class="lm-ripple" style="width:${px}px;height:${px}px;margin:${-px / 2}px 0 0 ${-px / 2}px;z-index:${ic.priority}"></div>
      ${lmIcon(e.icon, px)}</div>`;
  }
  const p = lmPlayer();
  if (p) {
    const ic = M.icons[M.player], px = LM_ICON_PX * ui * ic.scale[tier];
    html += `<div class="lm-mark lm-player" style="${at(p.u, p.v)};z-index:${ic.priority}">
      <div style="transform:rotate(${180 + p.yaw}deg)">${lmIcon(M.player, px)}</div></div>`;
  }
  layer.innerHTML = html;
  const tip = $("#lm-tip");
  $$("[data-lm], [data-mk]", layer).forEach((el) => {
    el.onpointerenter = () => {
      if (el.dataset.mk) {
        const k = m.markers[el.dataset.mk];
        tip.innerHTML = `<b>${h(k[4])}</b>${k[5] ? `<br><small>${h(k[5])}</small>` : ""}`;
      } else {
        const id = el.dataset.lm, e = M.events[id], ev = S.lmLive.events.find((x) => x.id === id);
        tip.innerHTML = `<b>${h(e.title)}</b><br><small>${h(LM_PHASE[ev.phase] || ev.phase)} · ${h(id)}</small>`;
      }
      tip.style.left = el.style.left; tip.style.top = el.style.top; tip.hidden = false;
    };
    el.onpointerleave = () => (tip.hidden = true);
  });
}
function lmCats() {
  const m = lmMap(), count = {};
  m.markers.forEach((k) => (count[k[0]] = (count[k[0]] || 0) + 1));
  const cats = [...(m.id === S.lmMeta.eventMap ? [["events", "Map events", 124]] : []), ...S.lmMeta.categories]
    .filter(([id]) => id === "events" || count[id]);
  $("#lm-cats").innerHTML = cats.map(([id, label, icon]) => `<button class="lm-cat ${S.lm.off.has(id) ? "off" : ""}" data-cat="${id}"
    title="${h(label)}"><img src="game/mapview/icons/${icon}.png" alt=""><span>${h(label)}</span>
    <small>${id === "events" ? (S.lmLive?.events ? lmLiveEvents().length : "live") : count[id]}</small></button>`).join("")
    + `<button class="lm-cat lm-cat-all" data-cat="*all"><span>All</span></button><button class="lm-cat lm-cat-all" data-cat="*none"><span>None</span></button>`;
  $$("[data-cat]", $("#lm-cats")).forEach((b) => (b.onclick = () => {
    const id = b.dataset.cat;
    if (id === "*all") S.lm.off.clear();
    else if (id === "*none") cats.forEach(([c]) => S.lm.off.add(c));
    else if (S.lm.off.has(id)) S.lm.off.delete(id); else S.lm.off.add(id);
    lmCats(); lmList(); lmDraw();
  }));
}
const LM_LIST_MAX = 300;
function lmList() {
  const box = $("#lm-list");
  if (!box) return;
  const m = lmMap(), M = S.lmMeta, label = Object.fromEntries(M.categories.map(([id, l]) => [id, l]));
  const q = S.lm.q.trim().toLowerCase();
  const evs = lmLiveEvents().filter((ev) => !q || M.events[ev.id].title.toLowerCase().includes(q));
  const ms = lmMarkers();
  let html = evs.length ? `<div class="group-title">Map events now</div>` + evs.map((ev) => {
    const e = M.events[ev.id];
    return `<div class="lm-row" data-go="${e.u},${e.v}"><img src="game/mapview/icons/${e.icon}.png" alt="">
      <span>${h(e.title)}<small>${h(LM_PHASE[ev.phase] || ev.phase)}</small></span></div>`;
  }).join("") : "";
  let last = null;
  ms.slice(0, LM_LIST_MAX).forEach((k) => {
    if (k[0] !== last) { html += `<div class="group-title">${h(label[k[0]] || k[0])}</div>`; last = k[0]; }
    html += `<div class="lm-row" data-go="${k[2]},${k[3]}"><img src="game/mapview/icons/${k[1]}.png" alt="">
      <span>${h(k[4])}${k[5] ? `<small>${h(k[5])}</small>` : ""}</span></div>`;
  });
  if (ms.length > LM_LIST_MAX) html += `<div class="muted pad">${ms.length - LM_LIST_MAX} more: search or switch some kinds off to narrow the list.</div>`;
  box.innerHTML = html || `<div class="muted pad">Nothing to list. Switch some kinds on above${q ? " or change the search" : ""}.</div>`;
  $$("[data-go]", box).forEach((r) => (r.onclick = () => {
    const [u, v] = r.dataset.go.split(",").map(Number);
    S.lm.follow = false; S.lm.u = u; S.lm.v = v;
    if (S.lm.step < 1) S.lm.step = 1;
    lmLayout();
  }));
}
async function lmTick() {
  lmStop();
  if (S.view !== "livemap") return;
  const had = JSON.stringify(S.lmLive?.events || null);
  try { S.lmLive = await api("mapview_live"); }
  catch (e) { S.lmLive = { game: false, mod: false, events: null, notes: [e.message] }; }
  if (S.view !== "livemap" || !$("#lm-vp")) return;
  const p = S.lmLive.player;
  if (S.lm.follow && p && p.map !== S.lm.map && S.lmMeta.maps.some((m) => m.id === p.map)) lmSetMap(p.map, true);
  lmStatus();
  if (JSON.stringify(S.lmLive.events || null) !== had) { lmCats(); lmList(); }
  lmLayout();
  S.lmTimer = setTimeout(lmTick, LM_POLL_MS);
}
function lmStatus() {
  const L = S.lmLive || {};
  const veil = $("#lm-veil");
  const msg = L.needs_update ? "The installed StolenHours mod is older than the live map. Close the game, press Update mod on the right, then start the game again."
    : !L.mod && !L.game ? "Game not running: showing the map's places. Start the game to see map events and where you are."
    : !L.mod ? "The game is running but the StolenHours mod isn't answering. Load your save; if it still doesn't answer, close the game and install the mod (right)."
    : !L.events ? "Waiting for the game..." : "";
  veil.hidden = !msg;
  veil.textContent = msg;
  const dot = (on) => `<span class="dot-big" style="color:${on ? "#3fae1b" : "#b9a27a"}">●</span>`;
  const p = L.player, here = S.lmMeta.maps.find((m) => m.id === p?.map);
  $("#lm-status").innerHTML = `
    <div class="status-row">${dot(L.game)} Game ${L.game ? "running" : "not running"}</div>
    <div class="status-row">${dot(L.mod && !L.needs_update)} Mod ${L.needs_update ? "needs update" : L.mod ? "connected" : "not connected"}</div>
    ${p ? `<div class="muted">You: ${here ? h(here.name) : `${h(p.map)} (no map for this place)`}${p.map === S.lm.map ? ` · ${Math.round(p.x)}, ${Math.round(p.y)}` : ""}</div>` : ""}
    ${(L.notes || []).map((n) => `<div class="muted ev-unmet">${h(n)}</div>`).join("")}`;
}

// ---------- Time Hook ----------
function liveStatus() {
  const st = S.state || {};
  const box = $("#live-status");
  if (!box) return;
  box.innerHTML = `
    <div class="status-row"><span class="dot-big" style="color:${st.game_running ? "#3fae1b" : "#b9a27a"}">●</span> Game ${st.game_running ? "running" : "not running"}</div>
    <div class="status-row"><span class="dot-big" style="color:${st.mod_alive ? "#3fae1b" : "#b9a27a"}">●</span> Time Hook mod ${st.mod_alive ? "connected" : "not connected"}</div>`;
  $$("[data-live]").forEach((b) => (b.disabled = !st.mod_alive));
}
function logLine(text, ok = true) {
  S.log.push(`${new Date().toLocaleTimeString()}  ${ok ? "OK " : "ERR"}  ${text}`);
  const l = $("#live-log"); if (l) { l.textContent = S.log.join("\n"); l.scrollTop = l.scrollHeight; }
}
async function liveCall(action, value = "", label = action) {
  try {
    const r = await (action === "dump" ? busy("Dumping game memory... keep the game open", () => api("live", { action, value })) : api("live", { action, value }));
    logLine(`${label}: ${r.text}`, r.ok);
    return r;
  } catch (e) { logLine(`${label}: ${e.message}`, false); return null; }
}
function vLive() {
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: 1fr 1.2fr">
    <div class="panel scroll"><div class="pad">
      <div class="band"><span>Time Hook</span></div>
      <div id="live-status"></div>
      <div class="muted">Changes the running game directly through the StolenHours mod. The save file is not touched; the game writes its own save later.</div>
      <div id="live-mod"></div>
      <div class="divider"></div>
      <label class="field-label">Dosh in the running game</label>
      <div class="big-dosh">${icon("game/coin.png")}<input type="number" id="live-dosh" min="0" placeholder="Read first"></div>
      <div class="quick">
        <button class="btn btn-cream btn-small" data-live id="live-read">Read</button>
        <button class="btn btn-green btn-small" data-live id="live-write">Write</button>
        <button class="btn btn-cream btn-small" data-live id="live-ping">Ping</button>
      </div>
      <div class="divider"></div>
      <label class="field-label">Research</label>
      <div class="quick"><button class="btn btn-orange btn-small" data-live id="live-dump">Dump everything</button>
        <button class="btn btn-cream btn-small" data-live id="live-probe" title="Needs Time Hook mod 0.4.0">Probe map events</button></div>
      <div class="note">Live Dosh writing is new: after Write, check the number on screen in game. If it doesn't change, tell Tock.</div>
    </div></div>
    <div class="panel" style="padding:0 18px 18px;display:flex;flex-direction:column">
      <div class="band"><span>Log</span></div>
      <div class="log scroll" id="live-log" style="flex:1">${h(S.log.join("\n"))}</div>
    </div>
  </div>`;
  liveStatus();
  modBox($("#live-mod"));
  $("#live-read").onclick = async () => { const r = await liveCall("get_dosh", "", "read Dosh"); if (r?.ok) $("#live-dosh").value = r.text; };
  $("#live-write").onclick = async () => {
    const v = $("#live-dosh").value;
    if (v === "") { toast("Read the current Dosh first", true); return; }
    if (await confirmDlg("Change Dosh in game?", `Set Dosh in the running game to ${fmt(v)}?`)) await liveCall("set_dosh", v, "write Dosh");
  };
  $("#live-ping").onclick = () => liveCall("ping");
  $("#live-dump").onclick = () => liveCall("dump", "", "dump");
  $("#live-probe").onclick = () => liveCall("probe_events", "", "probe map events");
}

// ---------- Island: debris, terrain, village, house, buddies ----------
const ISL_TABS = [
  ["debris", "Debris"], ["terrain", "Terrain"], ["village", "Village"], ["house", "House"], ["buddies", "Buddies"],
];
const ISL_GROUPS = {
  base: "Base Camp", depths_b1: "Depths – B1", depths_b2: "Depths – B2", depths_b3: "Depths – B3", other: "Other",
};

async function vIsland() {
  if (S.islKeep) S.islKeep = false;
  else {
    const [isl, bud] = await Promise.all([
      attempt(() => api("island")),
      attempt(() => api("companions")),
    ]);
    if (!isl || !bud || S.view !== "island") return;
    S.isl = isl; S.bud = bud;
  }
  S.islTab ||= "debris";
  S.islGroup ||= "base";
  S.islQ ||= "";
  S.vilFree = S.vilFree === true;
  drawIsland();
}
function drawIsland() {
  const t = S.islTab;
  const wide = t === "village" || t === "house" || t === "terrain";
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: minmax(0, 1fr) ${wide ? "300px" : "320px"}">
    <div class="panel" style="display:flex;flex-direction:column;min-height:0;padding:0 18px 14px">
      <div class="band"><span>Island</span></div>
      <div class="tabs">${ISL_TABS.map(([k, label]) =>
        `<button class="tab ${t === k ? "active" : ""}" data-isltab="${k}">${label}</button>`).join("")}</div>
      <div id="isl-body" class="col-body" style="${wide ? "display:flex;flex-direction:column;min-height:0;flex:1" : ""}"></div>
    </div>
    <div class="panel scroll"><div class="pad" id="isl-side"></div></div>
  </div>`;
  $$("[data-isltab]").forEach((b) => (b.onclick = () => { S.islTab = b.dataset.isltab; S.islQ = ""; drawIsland(); }));
  ({ debris: islDebris, terrain: islTerrain, village: islVillage, house: islHouse, buddies: islBuddies })[t]();
}
/** Three.js indoor hit (x,y = Three X/Z ×100) → UE Location for My House craft grid. */
function vilIndoorLoc(v, placed, x, y) {
  const cell = v.area?.voxel?.[0] || 50;
  const aw = v.area?.width || 12, ad = v.area?.depth || 12;
  const ux = Math.max(1, aw - 1), uy = Math.max(1, ad - 1);
  // Match village3d indoor: Three X ← −iy (high iy = left), Three Z ← ix (0 = back).
  const ix = Math.max(0, Math.min(ux - 1, Math.floor((y + (ux * cell) / 2) / cell)));
  const iy = Math.max(0, Math.min(uy - 1, Math.floor((-x + (uy * cell) / 2) / cell)));
  let ox = -250, oy = -250, oz = 0;
  if (placed?.length) {
    const p = placed[0];
    const rem = (p.gridIdx || 0) % (aw * ad);
    const pix = Math.floor(rem / aw), piy = rem % aw;
    ox = p.location[0] - pix * cell;
    oy = p.location[1] - piy * cell;
    oz = p.location[2] || 0;
  }
  return [ox + ix * cell, oy + iy * cell, oz];
}
async function vilEdit(action, args = {}) {
  // Live + game running: move actors in Customization only (disk save is locked). Persist in-game.
  const liveMove = action === "move" && S.state?.mod_alive && S.state?.game_running
    && args.handle != null && args.location;
  if (liveMove) {
    const loc = args.location;
    const yaw = (args.rotation && args.rotation[1]) || 0;
    const lr = await attempt(() => api("village_live", {
      action: "teleport", handle: args.handle, location: loc, yaw,
    }));
    toast(lr?.ok ? "Moved in-game — Save in Customization to keep it" : (lr?.text || "Live move failed"));
    return;
  }
  const r = await attempt(() => api("village_edit", { action, free: !!S.vilFree, ...args }));
  if (!r) return;
  if ((r.village?.mapId === "Map_MyHouse") || args.kind === "indoor") S.vilH = r.village;
  else S.vil = r.village;
  S.islKeep = true;
  afterEdit(r.summary, r.note.charAt(0).toUpperCase() + r.note.slice(1));
  drawIsland();
}
async function islEdit(action, args = {}) {
  const r = await attempt(() => api("island_edit", { action, ...args }));
  if (!r) return;
  S.isl = r.island; S.islKeep = true;
  afterEdit(r.summary, r.note.charAt(0).toUpperCase() + r.note.slice(1));
  drawIsland();
}
async function budEdit(action, args = {}) {
  const r = await attempt(() => api("companions_edit", { action, ...args }));
  if (!r) return;
  S.bud = r.companions; S.islKeep = true;
  afterEdit(r.summary, r.note.charAt(0).toUpperCase() + r.note.slice(1));
  drawIsland();
}
function islDebris() {
  const order = Object.keys(ISL_GROUPS);
  const isl = S.isl, groups = Object.keys(isl.groups || {}).sort((a, b) => {
    const ia = order.includes(a) ? order.indexOf(a) : 99, ib = order.includes(b) ? order.indexOf(b) : 99;
    return ia - ib || a.localeCompare(b);
  });
  if (!groups.includes(S.islGroup)) S.islGroup = groups[0] || "base";
  const rows = (isl.groups[S.islGroup] || []).filter((o) =>
    !S.islQ || o.name.toLowerCase().includes(S.islQ) || o.id.toLowerCase().includes(S.islQ));
  const left = rows.filter((o) => !o.cleared);
  $("#isl-body").innerHTML = `
    <div class="row col-filters">
      <select id="isl-group">${groups.map((g) =>
        `<option value="${g}" ${S.islGroup === g ? "selected" : ""}>${h(ISL_GROUPS[g] || g)} (${(isl.groups[g] || []).filter((o) => !o.cleared).length} left)</option>`).join("")}</select>
      <input id="isl-q" type="search" placeholder="Search debris…" value="${h(S.islQ)}" style="flex:1">
    </div>
    <div class="row" style="gap:8px;margin:4px 0 10px">
      <button class="btn btn-green btn-small" id="isl-clear-shown" ${left.length ? "" : "disabled"}>Clear shown (${left.length})</button>
      <button class="btn btn-cream btn-small" id="isl-clear-all" ${isl.remaining ? "" : "disabled"}>Clear all remaining (${isl.remaining})</button>
    </div>
    <div id="col-list" class="col-list">${rows.length ? rows.map((o) => `
      <div class="col-row ${o.cleared ? "on" : ""}">
        <div class="col-main">
          <div class="col-title">${h(o.name)}${o.cleared ? " · cleared" : ""}</div>
          <div class="col-sub muted">${h(o.type)}${o.friends ? ` · needs ${o.friends} buddy(ies)` : ""}
            ${o.rewardName ? ` · reward ${h(o.rewardName)} ×${o.rewardNum}` : ""}
            ${o.craftPresent ? " · craft object still placed" : ""}</div>
        </div>
        <button class="btn ${o.cleared ? "btn-cream" : "btn-green"} btn-small shrink" data-islclear="${h(o.id)}"
          ${o.cleared ? "disabled" : ""}>${o.cleared ? "Cleared" : "Clear"}</button>
      </div>`).join("") : `<div class="muted" style="padding:12px 2px">No debris in this group.</div>`}</div>`;
  $("#isl-side").innerHTML = `
    <div class="band"><span>Maps</span></div>
    <div class="note">Personal island = Base Camp. Past = The Depths (craft floors B1–B3). Big island = Ginormosia
      (area ranks below). Live Map already shows all three.</div>
    <div class="it-stat"><span>Debris cleared</span><b>${isl.cleared} / ${isl.cleared + isl.remaining}</b></div>
    <div class="it-stat"><span>obstacleReleaseNum</span><b>${fmt(isl.obstacleReleaseNum)}</b></div>
    ${(isl.houses || []).length ? `<div class="band" style="margin-top:14px"><span>Houses</span></div>
      ${isl.houses.map((hh) => `<div class="it-stat"><span>${h(hh.id)}</span><b>${h(hh.map || "?")}${hh.rooms ? ` · ${hh.rooms} room(s)` : ""}</b></div>`).join("")}` : ""}
    <div class="band" style="margin-top:14px"><span>Ginormosia areas</span></div>
    ${(isl.huge || []).map((a) => `<div class="it-stat"><span>${h(a.id)}</span><b>rank ${a.rank} · ${fmt(a.points)} pts</b></div>`).join("") ||
      `<div class="muted">No area data.</div>`}
    <div class="note" style="margin-top:12px">Clearing sets the game's sync flag to 255 and removes the debris craft
      object, matching the starter house after you cleared it in game. Load the save and check the island.</div>`;
  $("#isl-group").onchange = () => { S.islGroup = $("#isl-group").value; drawIsland(); };
  $("#isl-q").oninput = () => { S.islQ = $("#isl-q").value.trim().toLowerCase(); drawIsland(); };
  $$("[data-islclear]").forEach((b) => (b.onclick = () => islEdit("clear", { ids: [b.dataset.islclear] })));
  $("#isl-clear-shown").onclick = async () => {
    if (await confirmDlg("Clear shown debris?", `Clear ${left.length} site(s) on this map?`))
      islEdit("clear", { ids: left.map((o) => o.id) });
  };
  $("#isl-clear-all").onclick = async () => {
    if (await confirmDlg("Clear every debris site?", `Clear all ${isl.remaining} remaining site(s) on every island map?`))
      islEdit("clear_all");
  };
}
async function islTerrain() {
  const mapId = "Map_000100";
  S.terrainTool ||= "raise";
  S.terrainCamKept = S.terrainCamKept === true;
  const t = S.isl.terrain || {};
  // Load height field once per visit (refresh after paint).
  if (!S.terrainGrid || S.terrainGrid.mapId !== mapId || !S.islKeep) {
    const g = await attempt(() => api("village_terrain", { map_id: mapId }));
    if (!g || S.view !== "island" || S.islTab !== "terrain") return;
    S.terrainGrid = g;
  }
  if (!S.vilMapMeta) {
    try {
      const meta = await (await fetch("game/mapview/mapview.json", { cache: "no-cache" })).json();
      S.vilMapMeta = (meta.maps || []).find((m) => m.id === mapId) || null;
    } catch { S.vilMapMeta = null; }
  }
  const bounds = S.vilMapMeta?.bounds || { minX: -17000, maxX: 17000, minY: -17000, maxY: 17000 };
  const art = S.vilMapMeta?.art ? `game/mapview/${S.vilMapMeta.art}` : "game/mapview/maps/Map_000100.jpg";
  const g = S.terrainGrid;
  const raised = (g.cells || []).filter((c) => c.h > 0).length;
  const waterN = (g.cells || []).filter((c) => c.surface === "water").length;

  $("#isl-body").innerHTML = `
    <div class="row col-filters" style="flex-wrap:wrap">
      <button class="tab ${S.terrainTool === "raise" ? "active" : ""}" data-ttool="raise">Raise Ground</button>
      <button class="tab ${S.terrainTool === "lower" ? "active" : ""}" data-ttool="lower">Lower Ground</button>
      <button class="tab ${S.terrainTool === "level" ? "active" : ""}" data-ttool="level">Level / Smooth</button>
      <button class="btn btn-cream btn-small" id="vil-cam-reset">Reset cam</button>
      <button class="btn btn-cream btn-small" id="vil-refresh">Reload</button>
    </div>
    <div class="vil-3d" id="vil-3d">${vilOutdoorHud("Base Camp · Terrain")}</div>
    <div class="note" style="margin-top:6px">Click a tile to ${
      S.terrainTool === "lower" ? "lower" : S.terrainTool === "level" ? "level toward neighbors" : "raise"
    } it.
      Procedural mesh from <code>land_obj</code>/<code>water_obj</code> height tiers (even cells).
      Writes the save — check in game (semantics UNVERIFIED).</div>`;

  $("#isl-side").innerHTML = `
    <div class="band"><span>Terraforming</span></div>
    <div class="it-stat"><span>Grid</span><b>${g.width || 0}×${g.depth || 0}</b></div>
    <div class="it-stat"><span>Raised cells</span><b>${fmt(raised)}</b></div>
    <div class="it-stat"><span>Water cells</span><b>${fmt(waterN)}</b></div>
    <div class="it-stat"><span>Land objs</span><b>${fmt(t.land)} (${fmt(t.shavedLand)} shaved)</b></div>
    <div class="it-stat"><span>Water objs</span><b>${fmt(t.water)}</b></div>
    <div class="row" style="margin-top:14px">
      <button class="btn btn-cream" id="isl-reset-shave" ${t.shaved ? "" : "disabled"}>Reset all Shave flags</button>
    </div>
    <div class="note" style="margin-top:10px">Default ground is tier 0 (Y=0). Each raise stacks a
      <code>land_obj</code> (+1.5 m). Lower removes the top tier; at ground, land becomes water.</div>`;

  $$("[data-ttool]").forEach((b) => (b.onclick = () => {
    S.terrainTool = b.dataset.ttool;
    if (window.Village3D) window.Village3D.setTerrainTool(S.terrainTool);
    drawIsland();
  }));
  $("#isl-reset-shave").onclick = async () => {
    if (await confirmDlg("Reset terrain Shave flags?", `Clear the Shave bit on ${fmt(t.shaved)} cell(s)?`))
      islEdit("reset_shave");
  };
  $("#vil-refresh").onclick = () => {
    vilHardReload();
    drawIsland();
  };
  $("#vil-cam-reset").onclick = () => { S.terrainCamKept = false; showTerrain3d(false); };

  const host = $("#vil-3d");
  const showTerrain3d = async (keep) => {
    if (!window.Village3D) {
      host.innerHTML = `<div class="muted" style="padding:20px">Loading 3D…</div>`;
      await new Promise((r) => window.addEventListener("village3d-ready", r, { once: true }));
    }
    // Fetch placed houses so they sit on the new mesh for context.
    let placed = [];
    if (!S.vil || S.vil.mapId !== mapId) {
      const v = await attempt(() => api("village", { map_id: mapId, kind: "map" }));
      if (v) S.vil = v;
    }
    placed = (S.vil?.placed || []).filter((p) => p.category !== "LAND" && p.category !== "WEED");
    await window.Village3D.show(host, placed, {
      mode: "outdoor",
      area: S.vil?.area,
      bounds,
      mapArt: art,
      terrain: S.terrainGrid,
      terrainTool: S.terrainTool,
      keepCamera: keep || S.terrainCamKept,
      onTerrainPaint: async ({ ix, iy, mode: tool }) => {
        const action = tool === "lower" ? "terrain_lower"
          : tool === "level" ? "terrain_level" : "terrain_raise";
        const r = await attempt(() => api("village_edit", { action, map_id: mapId, ix, iy, kind: "map" }));
        if (!r) return;
        if (r.terrain) {
          S.terrainGrid = r.terrain;
          window.Village3D.rebuildCraftTerrain(r.terrain);
        }
        if (r.village) S.vil = r.village;
        if (r.summary) S.sum = r.summary;
        S.islKeep = true;
        // Don't call afterEdit/render — that would rebuild the whole 3D view mid-stroke.
        status("Unsaved changes. Use Save to file when the game is closed.", true);
        if (r.note) toast(`${r.note.charAt(0).toUpperCase() + r.note.slice(1)}. Not in your save yet: press Save to file.`);
        const tg = S.terrainGrid;
        const raised2 = (tg.cells || []).filter((c) => c.h > 0).length;
        const water2 = (tg.cells || []).filter((c) => c.surface === "water").length;
        const side = $("#isl-side");
        if (side) {
          const raisedEl = side.querySelectorAll(".it-stat b");
          if (raisedEl[1]) raisedEl[1].textContent = fmt(raised2);
          if (raisedEl[2]) raisedEl[2].textContent = fmt(water2);
        }
      },
    });
    if (!host.querySelector(".vil-hud")) {
      host.insertAdjacentHTML("afterbegin", vilOutdoorHud("Base Camp · Terrain"));
    }
    S.terrainCamKept = true;
  };
  showTerrain3d(false);
}
/** HUD + compass rose for outdoor Village (N/−Z · E/+X · S/+Z · W/−X). */
function vilOutdoorHud(label) {
  return `<div class="vil-hud"><span class="vil-hud-label">${label}</span></div>
    <div class="vil-compass" title="Game axes: N = −Z · E = +X · S = +Z · W = −X">
      <div class="vil-compass-rose">
        <span class="n">N</span><span class="e">E</span><span class="s">S</span><span class="w">W</span>
        <i class="needle"></i>
      </div>
    </div>`;
}

function vilHardReload() {
  if (window.Village3D?.hardReset) window.Village3D.hardReset();
  S.islKeep = false;
  S.vil = null;
  S.craftCat = null;
  S.terrainGrid = null;
  S.vilCamKept = false;
  S.terrainCamKept = false;
  S.vilMapMeta = null;
}

function vilModeToggleHtml() {
  return `<label class="vil-mode" title="Legal uses invCraft stock; Free places any catalog item">
    <span class="${S.vilFree ? "" : "on"}">Legal</span>
    <button type="button" class="vil-toggle ${S.vilFree ? "free" : ""}" id="vil-free" aria-pressed="${S.vilFree}">
      <span class="knob"></span></button>
    <span class="${S.vilFree ? "on" : ""}">Free</span></label>`;
}
function vilBindMode(redraw) {
  $("#vil-free").onclick = () => { S.vilFree = !S.vilFree; redraw(); };
}
function vilWorldToUv(x, y, bounds) {
  const rx = bounds.maxX - bounds.minX, ry = bounds.maxY - bounds.minY;
  return { u: (bounds.maxY - y) / ry, v: (x - bounds.minX) / rx };
}
function vilUvToWorld(u, v, bounds) {
  const rx = bounds.maxX - bounds.minX, ry = bounds.maxY - bounds.minY;
  return { x: bounds.minX + v * rx, y: bounds.maxY - u * ry };
}
async function loadCraftCatalog() {
  if (S.craftCat) return S.craftCat;
  try {
    const j = await (await fetch("game/village/craft.json", { cache: "no-cache" })).json();
    S.craftCat = { objects: j.objects || [], houses: j.houses || [] };
  } catch {
    S.craftCat = { objects: [], houses: [] };
  }
  return S.craftCat;
}
function vilCatRows(items, stock, placeId, limit = 200) {
  return items.slice(0, limit).map((c) => {
    const own = c.itemId && stock[c.itemId] ? stock[c.itemId] : 0;
    const on = placeId === c.id ? "on" : "";
    const icon = c.itemId ? `game/items/${h(c.itemId)}.png` : "";
    return `<button class="vil-cat-row ${on}" data-place="${h(c.id)}" title="${h(c.id)}">
      ${icon ? `<img src="${icon}" alt="" onerror="this.remove()">` : ""}
      <span>${h(c.name)}${!S.vilFree && c.itemId ? ` · ×${own}` : ""}</span></button>`;
  }).join("") || `<div class="muted">No matches.</div>`;
}
function vilApplyCam(world) {
  const cam = S.vilCam || { scale: 1.6, x: 0, y: 0 };
  world.style.transform = `translate(calc(-50% + ${cam.x}px), calc(-50% + ${cam.y}px)) scale(${cam.scale})`;
}
function vilBindMapCam(stage, world) {
  S.vilCam ||= { scale: 1.6, x: 0, y: 0 };
  vilApplyCam(world);
  stage.classList.toggle("placing", !!S.vilPlaceId);
  let pan = null;
  stage.onwheel = (ev) => {
    ev.preventDefault();
    const cam = S.vilCam;
    const before = cam.scale;
    const factor = ev.deltaY > 0 ? 0.9 : 1.11;
    cam.scale = Math.min(6, Math.max(0.55, before * factor));
    // zoom toward cursor
    const rect = stage.getBoundingClientRect();
    const cx = ev.clientX - rect.left - rect.width / 2;
    const cy = ev.clientY - rect.top - rect.height / 2;
    const k = cam.scale / before;
    cam.x = cx - (cx - cam.x) * k;
    cam.y = cy - (cy - cam.y) * k;
    vilApplyCam(world);
  };
  stage.onpointerdown = (ev) => {
    const panBtn = ev.button === 1 || ev.button === 2 || (ev.button === 0 && !S.vilPlaceId && !ev.target.closest(".vil-fp"));
    if (!panBtn && ev.button !== 0) return;
    if (ev.button === 0 && S.vilPlaceId && !ev.target.closest(".vil-fp")) return; // place on click
    if (ev.button === 2) ev.preventDefault();
    pan = { id: ev.pointerId, x: ev.clientX, y: ev.clientY, ox: S.vilCam.x, oy: S.vilCam.y, moved: false };
    stage.setPointerCapture(ev.pointerId);
    stage.classList.add("panning");
  };
  stage.onpointermove = (ev) => {
    if (!pan || pan.id !== ev.pointerId) return;
    const dx = ev.clientX - pan.x, dy = ev.clientY - pan.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) pan.moved = true;
    S.vilCam.x = pan.ox + dx;
    S.vilCam.y = pan.oy + dy;
    vilApplyCam(world);
  };
  const endPan = (ev) => {
    if (!pan || pan.id !== ev.pointerId) return;
    const wasDrag = pan.moved;
    pan = null;
    stage.classList.remove("panning");
    stage._vilDragged = wasDrag;
  };
  stage.onpointerup = endPan;
  stage.onpointercancel = endPan;
  stage.oncontextmenu = (ev) => ev.preventDefault();
}

async function islVillage() {
  const mapId = "Map_000100";
  const craft = await loadCraftCatalog();
  if (!S.vil || S.vil.mapId !== mapId || !S.islKeep) {
    const v = await attempt(() => api("village", { map_id: mapId, kind: "map" }));
    if (!v || S.view !== "island" || S.islTab !== "village") return;
    S.vil = v;
  }
  if (!S.vilMapMeta) {
    try {
      const meta = await (await fetch("game/mapview/mapview.json", { cache: "no-cache" })).json();
      S.vilMapMeta = (meta.maps || []).find((m) => m.id === mapId) || null;
    } catch { S.vilMapMeta = null; }
  }
  S.vilSel ||= null;
  S.vilPlaceId ||= "";
  S.vilCatQ ||= "";
  S.vilCatTab ||= "build"; // build | houses | placed
  S.vilCraftMode ||= "craft"; // craft (Customization) | ground
  S.vilCamKept = S.vilCamKept === true;
  const v = S.vil, bounds = S.vilMapMeta?.bounds || { minX: -17000, maxX: 17000, minY: -17000, maxY: 17000 };
  const art = S.vilMapMeta?.art ? `game/mapview/${S.vilMapMeta.art}` : "game/mapview/maps/Map_000100.jpg";
  const placed = (v.placed || []).filter((p) => p.category !== "LAND");
  const nameOf = (id) => (craft.objects.find((o) => o.id === id) || {}).name
    || (craft.houses.find((hh) => hh.id === id || hh.craftObj === id) || {}).name || id;
  placed.forEach((p) => { if (!p.name || p.name === p.craftObjId) p.name = nameOf(p.craftObjId) || p.name; });

  const placeMeta = () => {
    if (!S.vilPlaceId) return { w: 1, d: 1 };
    if (S.vilPlaceId.startsWith("house:")) {
      const hh = craft.houses.find((x) => x.id === S.vilPlaceId.slice(6));
      const obj = hh && craft.objects.find((o) => o.id === hh.craftObj);
      return { w: obj?.w || 8, d: obj?.d || 8 };
    }
    const o = craft.objects.find((x) => x.id === S.vilPlaceId) || {};
    return { w: o.w || 1, d: o.d || 1 };
  };

  const liveOn = !!S.state?.mod_alive;
  $("#isl-body").innerHTML = `
    <div class="vil-craft-bar">
      <button type="button" class="vil-craft-tab ${S.vilCraftMode === "craft" ? "on" : ""}" data-cmode="craft"
        title="Customization — place houses & outdoor objects">
        <span class="ic">🪑</span>Customization</button>
      <button type="button" class="vil-craft-tab ${S.vilCraftMode === "ground" ? "on" : ""}" data-cmode="ground"
        title="Ground — terrain raise/lower (Island → Terrain for now)">
        <span class="ic">🟫</span>Ground</button>
    </div>
    <div class="row col-filters" style="flex-wrap:wrap;align-items:center;gap:8px">
      ${vilModeToggleHtml()}
      <input id="vil-q" type="search" placeholder="Filter catalog…" value="${h(S.vilCatQ)}" style="flex:1;min-width:120px">
      <button class="btn btn-cream btn-small" id="vil-cam-reset">Reset cam</button>
      <button class="btn btn-cream btn-small" id="vil-explore">${S.vilExplore ? "Build view" : "Walk / Explore"}</button>
      <button class="btn btn-cream btn-small" id="vil-refresh">Reload</button>
    </div>
    <div class="note" id="vil-live-banner" style="margin-top:6px;${liveOn ? "border-left:3px solid #3a8;padding-left:8px" : ""}">
      ${liveOn
        ? `<b>Live linked</b> — Fantasy Life is the truth view. Open <b>Customization</b> in-game; this pane is the schematic.
           <button class="btn btn-green btn-small" id="vil-live-cam" style="margin-left:6px">Unlock craft cam</button>
           <button class="btn btn-cream btn-small" id="vil-live-status">Craft status</button>
           <span class="muted" id="vil-live-txt" style="margin-left:6px"></span>`
        : `Offline schematic. Start the game with the Stolen Hours mod (0.7+) for live Customization + craft cam.`}
    </div>
    <div class="row" style="flex-wrap:wrap;gap:6px;margin-top:6px;align-items:center">
      <input id="vil-preset-name" type="text" placeholder="Loadout name…" value="${h(S.vilPresetName || "")}" style="width:140px">
      <button class="btn btn-cream btn-small" id="vil-preset-save">Save village loadout</button>
      <select id="vil-preset-pick" style="min-width:120px"><option value="">Load loadout…</option></select>
      <button class="btn btn-green btn-small" id="vil-preset-load" disabled>Apply loadout</button>
      <button class="btn btn-cream btn-small" id="vil-preset-del" disabled>Delete</button>
    </div>
    <div class="vil-3d" id="vil-3d">${vilOutdoorHud(`Base Camp · ${S.vilExplore ? "Explore" : "Craft Mode"}`)}</div>
    <div class="note" style="margin-top:6px">${S.vilExplore
      ? "WASD / arrows to walk · mouse orbit follow · height snaps to terrain. Toggle Build view to place."
      : "Float above like in-game Customization. Cyan = valid footprint, red = water/cliff. Drag orbit · scroll zoom · click to place. N/−Z · E/+X · S/+Z · W/−X."
    }</div>`;

  $$("[data-cmode]").forEach((b) => (b.onclick = () => {
    if (b.dataset.cmode === "ground") {
      S.islTab = "terrain";
      drawIsland();
      return;
    }
    S.vilCraftMode = "craft";
    drawIsland();
  }));

  // Outdoor facilities + outdoor OBJECT deco. House kits separate tab.
  const OUTDOOR = new Set(["BRIDGE", "FENCE", "ROAD", "SLOPE", "GUILD_SQUARE",
    "GUILD_HOUSE", "PLANNED_CONSTRUCT", "VEGETABLE_FIELD", "PICK", "WEED", "TAMAGEMONO", "OBJECT"]);

  const vilSide = () => {
    const sel = placed.find((p) => p.handle === S.vilSel);
    const stock = v.inventory || {};
    const q = (S.vilCatQ || "").toLowerCase();
    const onIsland = (v.houses || []).map((hh) => {
      const meta = craft.houses.find((x) => x.id === hh.id) || {};
      const fromObj = meta.craftObj ? nameOf(meta.craftObj) : null;
      return {
        ...hh,
        name: (hh.name && !hh.name.startsWith("house_") ? hh.name : null)
          || meta.name || fromObj || nameOf(hh.id) || hh.id,
      };
    });
    const houseShells = (craft.houses || []).filter((hh) =>
      !q || hh.name.toLowerCase().includes(q) || hh.id.toLowerCase().includes(q));
    const buildItems = (craft.objects.length ? craft.objects : (v.catalog || []))
      .filter((c) => OUTDOOR.has(c.category) && c.category !== "HOUSE")
      .filter((c) => !q || c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q));

    const isleName = S.sum?.island || S.state?.island || "Base Camp";
    const rank = S.sum?.development_rank ?? S.sum?.devRank;
    const resN = (S.bud?.residents || []).length;
    const debrisLeft = S.isl?.remaining;
    $("#isl-side").innerHTML = `
      <div class="band"><span>Boyle · Guild desk</span></div>
      <div class="it-stat"><span>Island</span><b>${h(isleName)}</b></div>
      ${rank != null ? `<div class="it-stat"><span>Development</span><b>${fmt(rank)}</b></div>` : ""}
      <div class="it-stat"><span>Residents</span><b>${fmt(resN)}</b></div>
      ${debrisLeft != null ? `<div class="it-stat"><span>Debris left</span><b>${fmt(debrisLeft)}</b>
        <button class="btn btn-cream btn-small" id="vil-to-debris" style="margin-left:6px">Clear…</button></div>` : ""}
      <div class="band" style="margin-top:10px"><span>Cooke · Kits</span></div>
      <div class="note">Infrastructure kits (bridges, slopes, house kits) come from Cooke in game.
        Place from the Build / House kits tabs with Legal (consumes bag) or Free. Direct Dosh shop UI next.</div>
      <div class="band" style="margin-top:10px"><span>Object list</span></div>
      <div class="note">${placed.length} on island · Legal / Free above. Cyan = valid pad, red = water/cliff.</div>
      ${sel ? `<div class="band" style="margin-top:10px"><span>Selected</span></div>
        <div class="it-stat"><span>${h(sel.name)}</span><b>${h(sel.craftObjId)}</b></div>
        <div class="row" style="gap:6px;flex-wrap:wrap;margin:8px 0">
          <button class="btn btn-cream btn-small" id="vil-rot">Rotate 90°</button>
          <button class="btn btn-cream btn-small" id="vil-rm">Remove</button>
        </div>` : `<div class="muted" style="margin:8px 0">Click a placed object in the 3D view.</div>`}
      <div class="band" style="margin-top:10px"><span>Houses on island</span></div>
      <div class="vil-list">${onIsland.length ? onIsland.map((hh) =>
        `<div class="vil-list-row"><span>${h(hh.name)}</span><small>${h(hh.map || "")}</small></div>`).join("")
        : `<div class="muted">None yet.</div>`}</div>
      <div class="row" style="gap:4px;margin:4px 0 8px;flex-wrap:wrap">
        <button class="tab ${S.vilCatTab === "build" ? "active" : ""}" data-vtab="build">Build</button>
        <button class="tab ${S.vilCatTab === "houses" ? "active" : ""}" data-vtab="houses">House kits</button>
        <button class="tab ${S.vilCatTab === "placed" ? "active" : ""}" data-vtab="placed">Placed</button>
      </div>
      <div class="vil-cat" id="vil-cat"></div>`;

    const cat = $("#vil-cat");
    if (S.vilCatTab === "placed") {
      cat.innerHTML = placed.length ? placed.map((p) =>
        `<button class="vil-list-row ${S.vilSel === p.handle ? "on" : ""}" data-h="${p.handle}">
          <span>${h(p.name)}</span><small>${h(p.category || "")}</small></button>`).join("")
        : `<div class="muted">Nothing placed.</div>`;
      $$("[data-h]").forEach((b) => (b.onclick = () => {
        S.vilSel = +b.dataset.h;
        if (window.Village3D) window.Village3D.highlight(S.vilSel);
        vilSide();
      }));
    } else if (S.vilCatTab === "houses") {
      cat.innerHTML = houseShells.slice(0, 200).map((hh) => {
        const pid = `house:${hh.id}`;
        return `<button class="vil-cat-row ${S.vilPlaceId === pid ? "on" : ""}" data-place="${h(pid)}">
          <span>${h(hh.name)} <small>${h(hh.structure || "")}</small></span></button>`;
      }).join("") || `<div class="muted">No house kits (run build-ui).</div>`;
    } else {
      cat.innerHTML = vilCatRows(buildItems, stock, S.vilPlaceId, 250);
    }

    $$("[data-vtab]").forEach((b) => (b.onclick = () => { S.vilCatTab = b.dataset.vtab; vilSide(); }));
    $$("[data-place]").forEach((b) => (b.onclick = () => {
      S.vilPlaceId = b.dataset.place;
      const sz = placeMeta();
      if (window.Village3D) window.Village3D.setPlaceSize(sz.w, sz.d);
      vilSide();
      show3d(true);
    }));
    const toDeb = $("#vil-to-debris");
    if (toDeb) toDeb.onclick = () => { S.islTab = "debris"; drawIsland(); };
    if (sel) {
      $("#vil-rot").onclick = () => vilEdit("rotate", { handle: sel.handle, map_id: mapId, kind: "map" });
      $("#vil-rm").onclick = async () => {
        if (await confirmDlg("Remove object?", `Remove ${sel.name} from Base Camp?`))
          vilEdit("remove", { handle: sel.handle, map_id: mapId, kind: "map" });
      };
    }
  };

  const host = $("#vil-3d");
  const show3d = async (keep) => {
    if (!window.Village3D) {
      host.querySelector(".vil-hud") || (host.innerHTML = `<div class="muted" style="padding:20px">Loading 3D…</div>`);
      await new Promise((r) => window.addEventListener("village3d-ready", r, { once: true }));
    }
    // Always refresh the height field so Village is a 3D craft island, not the static map JPG.
    {
      const g = await attempt(() => api("village_terrain", { map_id: mapId }));
      if (g) S.terrainGrid = g;
    }
    const sz = placeMeta();
    const z0 = v.area?.origin?.[2] ?? -150;
    await window.Village3D.show(host, placed, {
      mode: "outdoor",
      area: v.area,
      bounds,
      mapArt: art,
      terrain: S.terrainGrid,
      residents: S.bud?.residents || [],
      selected: S.vilSel,
      placeW: sz.w,
      placeD: sz.d,
      keepCamera: keep || S.vilCamKept,
      onSelect: (handle) => { S.vilSel = handle; vilSide(); },
      onPlace: async ({ x, y }) => {
        if (!S.vilPlaceId) return;
        const vw = v.area?.voxel?.[0] || 50;
        const px = Math.round(x / vw) * vw, py = Math.round(y / vw) * vw;
        if (S.vilPlaceId.startsWith("house:")) {
          await vilEdit("place_house", { house_id: S.vilPlaceId.slice(6), map_id: mapId,
            location: [px, py, z0 + 150], kind: "map" });
        } else {
          await vilEdit("place", { craft_obj_id: S.vilPlaceId, map_id: mapId,
            location: [px, py, z0 + 150], kind: "map" });
        }
      },
      onMove: async ({ handle, x, y }) => {
        const vw = v.area?.voxel?.[0] || 50;
        const px = Math.round(x / vw) * vw, py = Math.round(y / vw) * vw;
        vilEdit("move", { handle, map_id: mapId, kind: "map", location: [px, py, z0 + 150] });
      },
    });
    // re-attach hud + compass after Village3D clears host
    if (!host.querySelector(".vil-hud")) {
      host.insertAdjacentHTML("afterbegin",
        vilOutdoorHud(`Base Camp · ${S.vilExplore ? "Explore" : "Craft Mode"}`));
    }
    if (window.Village3D?.setExploreMode) window.Village3D.setExploreMode(!!S.vilExplore);
    S.vilCamKept = true;
  };

  vilSide();
  vilBindMode(() => { drawIsland(); });
  $("#vil-q").oninput = () => { S.vilCatQ = $("#vil-q").value.trim(); vilSide(); };
  $("#vil-cam-reset").onclick = () => { S.vilCamKept = false; show3d(false); };
  $("#vil-explore").onclick = () => {
    S.vilExplore = !S.vilExplore;
    if (window.Village3D) window.Village3D.setExploreMode(S.vilExplore);
    const hud = host.querySelector(".vil-hud-label");
    if (hud) hud.textContent = `Base Camp · ${S.vilExplore ? "Explore" : "Craft Mode"}`;
    // Avoid full redraw so the walk pose / cam stay put.
    const btn = $("#vil-explore");
    if (btn) btn.textContent = S.vilExplore ? "Build view" : "Walk / Explore";
  };
  $("#vil-refresh").onclick = async () => {
    vilHardReload();
    drawIsland();
  };

  const liveCam = $("#vil-live-cam");
  if (liveCam) {
    liveCam.onclick = async () => {
      const r = await attempt(() => api("village_live", { action: "cam_unlock" }));
      const t = $("#vil-live-txt");
      if (t) t.textContent = r?.text || (r?.ok ? "cam unlocked" : "failed");
    };
  }
  const liveSt = $("#vil-live-status");
  if (liveSt) {
    liveSt.onclick = async () => {
      const r = await attempt(() => api("village_live", { action: "status" }));
      const t = $("#vil-live-txt");
      if (t) t.textContent = r?.text || "";
    };
  }

  const refreshPresets = async () => {
    const r = await attempt(() => api("village_presets", { action: "list" }));
    const sel = $("#vil-preset-pick");
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = `<option value="">Load loadout…</option>` +
      (r?.presets || []).map((p) =>
        `<option value="${h(p.name)}">${h(p.name)} (${p.objects || 0} objs)</option>`).join("");
    if (cur) sel.value = cur;
    const has = !!sel.value;
    const loadBtn = $("#vil-preset-load"), delBtn = $("#vil-preset-del");
    if (loadBtn) loadBtn.disabled = !has;
    if (delBtn) delBtn.disabled = !has;
  };
  await refreshPresets();
  $("#vil-preset-pick").onchange = () => {
    const has = !!$("#vil-preset-pick").value;
    $("#vil-preset-load").disabled = !has;
    $("#vil-preset-del").disabled = !has;
  };
  $("#vil-preset-save").onclick = async () => {
    const name = ($("#vil-preset-name").value || "").trim() || `village_${new Date().toISOString().slice(0, 10)}`;
    S.vilPresetName = name;
    const r = await attempt(() => api("village_presets", {
      action: "export", name, map_id: mapId, kind: "map", note: "Base Camp loadout",
    }));
    if (r) {
      toast(`Saved loadout “${name}” (${r.objects} objects)`);
      $("#vil-preset-name").value = name;
      await refreshPresets();
      $("#vil-preset-pick").value = name;
      $("#vil-preset-load").disabled = false;
      $("#vil-preset-del").disabled = false;
    }
  };
  $("#vil-preset-load").onclick = async () => {
    const name = $("#vil-preset-pick").value;
    if (!name) return;
    if (!(await confirmDlg("Apply village loadout?",
      `Replace non-house Base Camp objects with “${name}”? Quit the game first. Houses are placed/moved best-effort.`)))
      return;
    const r = await attempt(() => api("village_presets", {
      action: "import", name, free: !!S.vilFree, replace: true,
    }));
    if (r) {
      toast(`Applied “${name}”: removed ${r.removed}, placed ${r.placed}`);
      S.vil = r.village || null;
      S.islKeep = false;
      drawIsland();
    }
  };
  $("#vil-preset-del").onclick = async () => {
    const name = $("#vil-preset-pick").value;
    if (!name) return;
    if (!(await confirmDlg("Delete loadout?", `Delete saved loadout “${name}”?`))) return;
    await attempt(() => api("village_presets", { action: "delete", name }));
    await refreshPresets();
  };

  show3d(false);
}

async function islHouse() {
  const mapId = "Map_MyHouse";
  const craft = await loadCraftCatalog();
  if (!S.vilH || S.vilH.mapId !== mapId || !S.islKeep) {
    const v = await attempt(() => api("village", { map_id: mapId, kind: "indoor" }));
    if (!v || S.view !== "island" || S.islTab !== "house") return;
    S.vilH = v;
  }
  S.vilHSel ||= null;
  S.vilPlaceId ||= "";
  S.vilCatQ ||= "";
  S.vilHTab ||= "furniture"; // furniture | placed | houses
  const v = S.vilH;
  const placed = [...(v.placed || [])];
  const nameOf = (id) => (craft.objects.find((o) => o.id === id) || {}).name
    || (craft.houses.find((hh) => hh.id === id || hh.craftObj === id) || {}).name || id;
  placed.forEach((p) => { if (!p.name || p.name === p.craftObjId) p.name = nameOf(p.craftObjId) || p.name; });
  const FURN = new Set(["OBJECT", "TABLE", "WALLDECO", "RUG", "LUNCH_EATS", "LUNCH_DRINK"]);

  $("#isl-body").innerHTML = `
    <div class="row col-filters" style="flex-wrap:wrap">
      ${vilModeToggleHtml()}
      <input id="vil-q" type="search" placeholder="Filter furniture…" value="${h(S.vilCatQ)}" style="flex:1;min-width:120px">
      <button class="btn btn-cream btn-small" id="vil-cam-reset">Reset cam</button>
      <button class="btn btn-cream btn-small" id="vil-refresh">Reload</button>
    </div>
    <div class="vil-3d" id="vil-3d" style="background:#1a1008">
      <div class="vil-hud"><span class="vil-hud-label">My House · Decorate</span></div>
    </div>
    <div class="note" style="margin-top:6px">Cutaway room like in-game. Orbit 360° · zoom · cyan tile = place · click furniture to select.</div>`;

  const furnMeta = () => {
    const o = craft.objects.find((x) => x.id === S.vilPlaceId) || {};
    return { w: o.w || 1, d: o.d || 1 };
  };

  const side = () => {
    const sel = placed.find((p) => p.handle === S.vilHSel);
    const stock = v.inventory || {};
    const q = (S.vilCatQ || "").toLowerCase();
    const furnOrder = { OBJECT: 0, TABLE: 1, RUG: 2, WALLDECO: 3, LUNCH_EATS: 4, LUNCH_DRINK: 5 };
    const furn = (craft.objects.length ? craft.objects : (v.catalog || []))
      .filter((c) => FURN.has(c.category))
      .filter((c) => !q || c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q))
      .sort((a, b) => (furnOrder[a.category] - furnOrder[b.category]) || a.name.localeCompare(b.name));
    const onIsland = (v.houses || []).map((hh) => ({
      ...hh, name: hh.name || nameOf(hh.id) || hh.id,
    }));
    const houseKits = (craft.houses || []).filter((hh) =>
      !q || hh.name.toLowerCase().includes(q) || hh.id.toLowerCase().includes(q));

    $("#isl-side").innerHTML = `
      <div class="band"><span>Furniture list</span></div>
      <div class="it-stat"><span>In room</span><b>${placed.length}</b></div>
      ${sel ? `<div class="band" style="margin-top:10px"><span>Selected</span></div>
        <div class="it-stat"><span>${h(sel.name)}</span><b>${h(sel.craftObjId)}</b></div>
        <div class="row" style="gap:6px;flex-wrap:wrap;margin:8px 0">
          <button class="btn btn-cream btn-small" id="vil-rot">Rotate 90°</button>
          <button class="btn btn-cream btn-small" id="vil-rm">Remove</button>
        </div>` : `<div class="muted" style="margin:8px 0">Pick from the list, then click a cyan tile in the room.</div>`}
      <div class="row" style="gap:4px;margin:12px 0 8px;flex-wrap:wrap">
        <button class="tab ${S.vilHTab === "furniture" ? "active" : ""}" data-htab="furniture">Furniture</button>
        <button class="tab ${S.vilHTab === "placed" ? "active" : ""}" data-htab="placed">Placed (${placed.length})</button>
        <button class="tab ${S.vilHTab === "houses" ? "active" : ""}" data-htab="houses">Houses</button>
      </div>
      <div class="vil-cat" id="vil-cat"></div>`;

    const cat = $("#vil-cat");
    if (S.vilHTab === "placed") {
      cat.innerHTML = placed.length ? placed.map((p) =>
        `<button class="vil-list-row ${S.vilHSel === p.handle ? "on" : ""}" data-h="${p.handle}">
          <span>${h(p.name)}</span><small>${h(p.category || "")}</small></button>`).join("")
        : `<div class="muted">No furniture placed yet.</div>`;
      $$("[data-h]").forEach((b) => (b.onclick = () => {
        S.vilHSel = +b.dataset.h;
        if (window.Village3D) window.Village3D.highlight(S.vilHSel);
        side();
      }));
    } else if (S.vilHTab === "houses") {
      cat.innerHTML = `
        <div class="muted" style="padding:4px 0">On your island</div>
        ${onIsland.length ? onIsland.map((hh) =>
          `<div class="vil-list-row"><span>${h(hh.name)}</span><small>${h(hh.map || "")}</small></div>`).join("")
          : `<div class="muted">None.</div>`}
        <div class="muted" style="padding:8px 0 4px">House kits (place from Village tab)</div>
        ${houseKits.slice(0, 120).map((hh) =>
          `<div class="vil-list-row"><span>${h(hh.name)}</span><small>${h(hh.structure || "")}</small></div>`).join("")}`;
    } else {
      cat.innerHTML = vilCatRows(furn, stock, S.vilPlaceId, 300);
      $$("[data-place]").forEach((b) => (b.onclick = () => {
        S.vilPlaceId = b.dataset.place;
        const sz = furnMeta();
        if (window.Village3D) window.Village3D.setPlaceSize(sz.w, sz.d);
        side();
        show3d(true);
      }));
    }

    $$("[data-htab]").forEach((b) => (b.onclick = () => { S.vilHTab = b.dataset.htab; side(); }));
    if (sel) {
      $("#vil-rot").onclick = () => vilEdit("rotate", { handle: sel.handle, map_id: mapId, kind: "indoor" });
      $("#vil-rm").onclick = async () => {
        if (await confirmDlg("Remove furniture?", `Remove ${sel.name}?`))
          vilEdit("remove", { handle: sel.handle, map_id: mapId, kind: "indoor" });
      };
    }
  };
  side();
  vilBindMode(() => { drawIsland(); });
  $("#vil-q").oninput = () => { S.vilCatQ = $("#vil-q").value.trim(); side(); };
  $("#vil-refresh").onclick = () => {
    S.islKeep = false; S.vilH = null; S.craftCat = null; S.vilHCamKept = false; drawIsland();
  };
  $("#vil-cam-reset").onclick = () => { S.vilHCamKept = false; show3d(false); };

  const host = $("#vil-3d");
  const show3d = async (keep) => {
    if (!window.Village3D) {
      host.innerHTML = `<div class="muted" style="padding:20px">Loading 3D…</div>`;
      await new Promise((r) => window.addEventListener("village3d-ready", r, { once: true }));
    }
    const sz = furnMeta();
    const origin = v.area?.origin || [0, 0, 0];
    const vw = (v.area?.width || 12) * (v.area?.voxel?.[0] || 50);
    const vd = (v.area?.depth || 12) * (v.area?.voxel?.[1] || 50);
    await window.Village3D.show(host, placed, {
      mode: "indoor",
      area: v.area,
      selected: S.vilHSel,
      placeW: sz.w,
      placeD: sz.d,
      keepCamera: keep || !!S.vilHCamKept,
      onSelect: (handle) => { S.vilHSel = handle; side(); },
      onPlace: async ({ x, y }) => {
        if (!S.vilPlaceId || S.vilPlaceId.startsWith("house:")) return;
        const loc = vilIndoorLoc(v, placed, x, y);
        if (!loc) return;
        vilEdit("place", { craft_obj_id: S.vilPlaceId, map_id: mapId, kind: "indoor", location: loc });
      },
      onMove: async ({ handle, x, y }) => {
        const loc = vilIndoorLoc(v, placed, x, y);
        if (!loc) return;
        vilEdit("move", { handle, map_id: mapId, kind: "indoor", location: loc });
      },
    });
    if (!host.querySelector(".vil-hud")) {
      host.insertAdjacentHTML("afterbegin",
        `<div class="vil-hud"><span class="vil-hud-label">My House · Decorate</span></div>`);
    }
    S.vilHCamKept = true;
  };
  show3d(false);
}

function islBuddies() {
  const b = S.bud, q = S.islQ || "";
  const catalog = [...(b.buddies || []), ...(b.extras || [])]
    .filter((c, i, arr) => arr.findIndex((x) => x.id === c.id) === i)
    .filter((c) => !q || c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q));
  const have = new Set((b.friends || []).map((f) => f.id));
  $("#isl-body").innerHTML = `
    <div class="row col-filters">
      <input id="isl-q" type="search" placeholder="Search buddies…" value="${h(S.islQ)}" style="flex:1">
    </div>
    <div class="band"><span>In your save</span></div>
    <div class="ev-live">${(b.friends || []).length ? b.friends.map((f) => `
      <div class="ev-live-row"><span>${h(f.name)}<small>Lv ${f.level} · friendship ${f.friendship}${f.talk != null ? ` · talked ${f.talk}` : ""} · ${h(f.id)}</small></span>
        <button class="ev-x" data-budrm="${h(f.id)}" title="Remove">✕</button></div>`).join("")
      : `<div class="muted" style="padding:8px 2px">No buddies in the friend roster yet.</div>`}</div>
    ${(b.residents || []).length ? `<div class="band" style="margin-top:10px"><span>On the island</span></div>
      <div class="muted">${b.residents.map((r) => `${h(r.name)}${r.living ? " (living)" : ""}`).join(" · ")}</div>` : ""}
    <div class="band" style="margin-top:12px"><span>All buddies</span></div>
    <div id="col-list" class="col-list">${catalog.map((c) => `
      <div class="col-row ${have.has(c.id) ? "on" : ""}">
        <div class="col-main">
          <div class="col-title">${h(c.name)}</div>
          <div class="col-sub muted">${h(c.id)}${c.library ? " · encyclopedia" : ""}</div>
        </div>
        <button class="btn ${have.has(c.id) ? "btn-cream" : "btn-green"} btn-small shrink" data-budadd="${h(c.id)}"
          ${have.has(c.id) ? "disabled" : ""}>${have.has(c.id) ? "In list" : "Add"}</button>
      </div>`).join("")}</div>`;
  const fol = b.follower || {};
  $("#isl-side").innerHTML = `
    <div class="band"><span>Follower</span></div>
    <div class="it-stat"><span>Current</span><b>${h(fol.name || "None")}</b></div>
    <label class="field-label" for="bud-fol">Set follower</label>
    <select id="bud-fol">
      <option value="None">None</option>
      ${(b.followers || []).map((f) =>
        `<option value="${h(f.id)}" ${fol.id === f.id ? "selected" : ""}>${h(f.name)}</option>`).join("")}
    </select>
    <button class="btn btn-green btn-small" id="bud-fol-set" style="margin-top:8px">Apply</button>
    <div class="band" style="margin-top:14px"><span>Party</span></div>
    ${(b.party || []).map((p) => `<div class="it-stat"><span>${p.leader ? "Leader" : "Slot"}</span><b>${h(p.who)}</b></div>`).join("")}
    <div class="it-stat"><span>Free buddy slots</span><b>${b.slotsFree} / 64</b></div>
    <div class="note" style="margin-top:12px">Adding a buddy fills an empty friend slot. That path is UNVERIFIED in game
      until you load a save that had a real recruit and compare. Follower is a single name field (Trip on your save).</div>`;
  $("#isl-q").oninput = () => { S.islQ = $("#isl-q").value.trim().toLowerCase(); drawIsland(); };
  $$("[data-budadd]").forEach((btn) => (btn.onclick = () => budEdit("add", { id: btn.dataset.budadd })));
  $$("[data-budrm]").forEach((btn) => (btn.onclick = async () => {
    if (await confirmDlg("Remove buddy?", `Remove ${btn.dataset.budrm} from the friend roster?`))
      budEdit("remove", { id: btn.dataset.budrm });
  }));
  $("#bud-fol-set").onclick = () => budEdit("follower", { id: $("#bud-fol").value });
}

// ---------- Collection: recipes, library, gifts ----------
const COL_TABS = [["recipes", "Recipes"], ["library", "Encyclopedia"], ["gifts", "Gifts"]];
const COL_LIVES = ["life0009", "life0010", "life0011", "life0012", "life0013", "life0014"];
const COL_MAX = 400;
const colName = (id) => S.col.names[id] || id;
const colIcon = (id) => `<img src="game/items/${h(S.col.icons[id] || id)}.png" alt="" onerror="this.style.visibility='hidden'">`;
const stars = (n) => (n > 0 ? "★".repeat(n) : "");
const colLife = (id) => String(S.col.lives[id] || id).replace("?", "");

async function vCollection() {
  if (S.colKeep) S.colKeep = false;
  else {
    const c = await attempt(() => api("collection"));
    if (!c || S.view !== "collection") return;
    S.col = c;
  }
  S.colTab ||= "recipes";
  S.colF ||= { life: "life0009", show: "all", cat: "", q: "", lib: "0" };
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: minmax(0, 1fr) 320px">
    <div class="panel" style="display:flex;flex-direction:column;min-height:0;padding:0 18px 14px">
      <div class="band"><span>Collection</span></div>
      <div class="tabs">${COL_TABS.map(([k, label]) => `<button class="tab ${S.colTab === k ? "active" : ""}" data-coltab="${k}">${label}</button>`).join("")}</div>
      <div id="col-body" class="col-body"></div>
    </div>
    <div class="panel scroll"><div class="pad" id="col-side"></div></div>
  </div>`;
  $$("[data-coltab]").forEach((b) => (b.onclick = () => { S.colTab = b.dataset.coltab; S.colF.show = "all"; S.colF.q = ""; vCollectionDraw(); }));
  vCollectionDraw();
}
function vCollectionDraw() {
  $$("[data-coltab]").forEach((b) => b.classList.toggle("active", b.dataset.coltab === S.colTab));
  ({ recipes: colRecipes, library: colLibrary, gifts: colGifts })[S.colTab]();
}
async function colEdit(action, args) {
  const keep = $("#col-list")?.scrollTop || 0;
  const r = await attempt(() => api("collection_edit", { action, ...args }));
  if (!r) return;
  S.col = r.collection; S.colKeep = true;
  afterEdit(r.summary, r.note.charAt(0).toUpperCase() + r.note.slice(1));
  const l = $("#col-list"); if (l) l.scrollTop = keep;
}
const colFilters = (shows) => `<div class="row col-filters">
    <select id="col-show">${shows.map(([v, label]) => `<option value="${v}" ${S.colF.show === v ? "selected" : ""}>${label}</option>`).join("")}</select>
    ${S.colTab === "recipes" ? `<select id="col-cat"><option value="">All kinds</option>${Object.entries(S.col.recipes.tabs).filter(([k]) => k !== "10")
      .map(([k, v]) => `<option value="${k}" ${S.colF.cat === k ? "selected" : ""}>${h(v)}</option>`).join("")}</select>` : ""}
    <input type="text" id="col-q" placeholder="Search..." value="${h(S.colF.q)}"></div>`;
function colBindFilters(redraw) {
  $("#col-show").onchange = (e) => { S.colF.show = e.target.value; redraw(); };
  if ($("#col-cat")) $("#col-cat").onchange = (e) => { S.colF.cat = e.target.value; redraw(); };
  $("#col-q").oninput = (e) => { S.colF.q = e.target.value; redraw(); };
}
function colListHtml(rows, row) {
  const more = rows.length > COL_MAX ? `<div class="muted" style="padding:8px">Showing ${COL_MAX} of ${fmt(rows.length)}. Search or filter to narrow it down.</div>` : "";
  return (rows.slice(0, COL_MAX).map(row).join("") || `<div class="muted" style="padding:12px">Nothing here.</div>`) + more;
}

// recipes
function colRecipeRows() {
  const f = S.colF, q = f.q.trim().toLowerCase();
  return S.col.recipes.recipes.filter((r) => r.life === f.life && (f.show === "all" || (f.show === "learned") === r.learned)
    && (!f.cat || String(r.cat) === f.cat) && (!q || colName(r.item).toLowerCase().includes(q)));
}
function colRecipes() {
  const all = S.col.recipes.recipes, f = S.colF;
  const count = (life) => { const rs = all.filter((r) => r.life === life); return [rs.filter((r) => r.learned).length, rs.length]; };
  $("#col-body").innerHTML = `
    <div class="tabs">${COL_LIVES.map((l) => { const [a, b] = count(l);
      return `<button class="tab ${f.life === l ? "active" : ""}" data-collife="${l}"><img class="col-life" src="game/life/${l}.png" alt="">${h(colLife(l))}<span class="n">${a}/${b}</span></button>`; }).join("")}</div>
    ${colFilters([["all", "All recipes"], ["locked", "Not learned yet"], ["learned", "Learned"]])}
    <div class="col-list" id="col-list"></div>
    <div class="row col-foot" id="col-foot"></div>`;
  $$("[data-collife]").forEach((b) => (b.onclick = () => { S.colF.life = b.dataset.collife; colRecipes(); }));
  colBindFilters(colRecipeList);
  colRecipeList();
  const [a, b] = [all.filter((r) => r.learned).length, all.length];
  $("#col-side").innerHTML = `
    <div class="band"><span>Recipes</span></div>
    <div class="col-big">${fmt(a)} <small>of ${fmt(b)} learned</small></div>
    ${COL_LIVES.map((l) => { const [x, y] = count(l); return `<div class="col-stat"><img src="game/life/${l}.png" alt=""><span>${h(colLife(l))}</span><b>${x} / ${y}</b></div>`; }).join("")}
    <div class="note">Unlocking a recipe gives it the same three marks the game gives a recipe you learned: the recipe in the
      list, its recipe book in your bag, and the "obtained" mark on the book.<br><br>
      UNVERIFIED until checked in game: load the save and open that Life's crafting list.</div>`;
}
function colRecipeList() {
  const rows = colRecipeRows(), tabs = S.col.recipes.tabs;
  $("#col-list").innerHTML = colListHtml(rows, (r) => `<div class="col-row ${r.learned ? "" : "locked"}">${colIcon(r.item)}
    <span><b>${h(colName(r.item))}</b><small>${h(tabs[r.cat] || "")} <span class="col-stars">${stars(r.rarity)}</span></small></span>
    ${r.learned ? `<span class="col-pill">Learned</span>` : `<button class="btn btn-green btn-small shrink" data-unlock="${h(r.id)}">Unlock</button>`}</div>`);
  const locked = rows.filter((r) => !r.learned);
  $("#col-foot").innerHTML = `<span class="muted">${fmt(rows.length)} shown · ${fmt(locked.length)} not learned</span>
    <button class="btn btn-green shrink" id="col-all" ${locked.length ? "" : "disabled"}>Unlock all ${fmt(locked.length)} shown</button>`;
  $$("[data-unlock]").forEach((b) => (b.onclick = () => colEdit("recipes", { ids: [b.dataset.unlock] })));
  $("#col-all").onclick = async () => {
    if (!(await confirmDlg("Unlock recipes?", `Learn ${locked.length} ${colLife(S.colF.life)} recipe(s)?\nTheir recipe books go into your Recipes bag.`))) return;
    colEdit("recipes", { ids: locked.map((r) => r.id) });
  };
}

// library
const LIB_ITEMS = "items";
function colLibRows() {
  const f = S.colF, q = f.q.trim().toLowerCase(), L = S.col.library;
  const rows = f.lib === LIB_ITEMS ? L.items.map((e) => ({ ...e, name: colName(e.id), item: true }))
    : L.entries.filter((e) => String(e.cat) === f.lib);
  return rows.filter((e) => (f.show === "all" || (f.show === "seen") === e.seen) && (!q || e.name.toLowerCase().includes(q)));
}
function colLibrary() {
  const L = S.col.library, f = S.colF;
  const cats = [...Object.entries(L.cats), [LIB_ITEMS, "Items"]];
  const count = (k) => { const rs = k === LIB_ITEMS ? L.items : L.entries.filter((e) => String(e.cat) === k); return [rs.filter((e) => e.seen).length, rs.length]; };
  $("#col-body").innerHTML = `
    <div class="tabs">${cats.map(([k, label]) => { const [a, b] = count(k);
      return `<button class="tab ${f.lib === k ? "active" : ""}" data-collib="${k}">${h(label)}<span class="n">${a}/${b}</span></button>`; }).join("")}</div>
    ${colFilters([["all", "All entries"], ["unseen", "Not filled in yet"], ["seen", "Filled in"]])}
    <div class="col-list" id="col-list"></div>
    <div class="row col-foot" id="col-foot"></div>`;
  $$("[data-collib]").forEach((b) => (b.onclick = () => { S.colF.lib = b.dataset.collib; colLibrary(); }));
  colBindFilters(colLibList);
  colLibList();
  $("#col-side").innerHTML = `
    <div class="band"><span>Encyclopedia</span></div>
    ${cats.map(([k, label]) => { const [a, b] = count(k); return `<div class="col-stat"><span>${h(label)}</span><b>${a} / ${b}</b></div>`; }).join("")}
    <div class="note">The game's Encyclopedia (Menu > Encyclopedia). Filling in an entry sets the same flag the game sets when you
      first meet that monster, gathering spot, Strangeling or character, plus its "new" mark. Items count once you have
      obtained them, so filling in an item marks it as obtained.<br><br>
      UNVERIFIED until checked in game: load the save and open the Encyclopedia.</div>`;
}
function colLibList() {
  const rows = colLibRows();
  $("#col-list").innerHTML = colListHtml(rows, (e) => `<div class="col-row ${e.seen ? "" : "locked"}">${e.item ? colIcon(e.id) : ""}
    <span><b>${h(e.name)}</b></span>
    ${e.seen ? `<span class="col-pill">Filled in</span>` : `<button class="btn btn-green btn-small shrink" data-fill="${h(e.id)}">Fill in</button>`}</div>`);
  const open = rows.filter((e) => !e.seen);
  $("#col-foot").innerHTML = `<span class="muted">${fmt(rows.length)} shown · ${fmt(open.length)} not filled in</span>
    <button class="btn btn-green shrink" id="col-all" ${open.length ? "" : "disabled"}>Fill in all ${fmt(open.length)} shown</button>`;
  $$("[data-fill]").forEach((b) => (b.onclick = () => colEdit("library", { ids: [b.dataset.fill] })));
  $("#col-all").onclick = async () => {
    if (!(await confirmDlg("Fill in the Encyclopedia?", `Fill in ${open.length} entr${open.length === 1 ? "y" : "ies"}?`))) return;
    colEdit("library", { ids: open.map((e) => e.id) });
  };
}

// gifts
const codeLabel = (id) => {
  const m = id.match(/^password_recieve_download_0*(\d+)$/);
  return m ? `Gift code #${m[1]}` : id.startsWith("compensation_") ? "Compensation gift" : "Gift code";
};
const GIFT_KINDS = [["pack", "Add-on packs"], ["level5", "LEVEL5 ID bonus content"]];
function colGifts() {
  const G = S.col.gifts;
  const card = (g) => `<div class="col-gift ${g.claimed ? "" : "locked"}">
    <div class="row"><b class="grow">${h(g.name)}</b>
      ${g.claimed ? `<span class="col-pill">Claimed</span><button class="btn btn-green btn-small shrink" data-reclaim="${h(g.id)}">Claim again</button>`
        : `<span class="col-pill off">Not claimed</span>`}</div>
    <div class="col-gift-items">${g.items.map((i) => `<span>${colIcon(i.id)}${h(colName(i.id))}${i.num > 1 ? ` ×${i.num}` : ""}</span>`).join("")}</div></div>`;
  const items = (list) => `<div class="col-gift-items">${list.map((i) => `<span>${colIcon(i.id)}${h(colName(i.id))}${i.num > 1 ? ` ×${i.num}` : ""}</span>`).join("")}</div>`;
  const known = (k) => `<div class="col-gift">
    <div class="row"><b class="col-code">${h(k.code)}</b><span class="grow muted">${h(k.why)} · ${h(k.when)}</span>
      ${k.claimed === true ? `<span class="col-pill">Claimed</span><button class="btn btn-green btn-small shrink" data-reclaim="${h(k.gift)}">Claim again</button>`
        : k.claimed === false ? `<span class="col-pill off">Not claimed</span>` : ""}
      <button class="btn btn-cream btn-small shrink" data-copy="${h(k.code)}">Copy</button>
      <button class="btn btn-green btn-small shrink" data-grant="${h(k.code)}">Add to bag</button></div>
    ${items(k.items)}</div>`;
  $("#col-body").innerHTML = `<div class="col-list" id="col-list">
    <div class="group-title">Gift codes</div>
    <div class="muted" style="padding:0 4px 4px">Type a code in game (Menu > Gifts > Gift Code Entry), or press Add to bag to put its
      rewards straight into your bag without the code.</div>
    ${G.known.map(known).join("")}
    ${GIFT_KINDS.map(([k, label]) => `<div class="group-title">${label}</div>${G.gifts.filter((g) => g.kind === k).map(card).join("")}`).join("")}
    <div class="group-title">Downloaded gift codes this save redeemed</div>
    ${G.codes.length ? G.codes.map((c) => `<div class="col-gift"><div class="row"><b class="grow">${h(codeLabel(c.id))}</b>
      <small class="muted">${h(c.id)}</small><button class="btn btn-green btn-small shrink" data-recode="${c.flag}">Claim again</button></div></div>`).join("")
      : `<div class="muted" style="padding:6px 4px">No gift codes redeemed on this save yet. Once you redeem one in game, it shows up here.</div>`}
  </div>
  <div class="row col-foot" id="col-foot"><span class="muted">${G.gifts.filter((g) => g.claimed).length + G.codes.length} claimed</span>
    <button class="btn btn-green shrink" id="col-all" ${G.gifts.some((g) => g.claimed) || G.codes.length ? "" : "disabled"}>Claim everything again</button></div>`;
  $$("[data-reclaim]").forEach((b) => (b.onclick = () => colEdit("reclaim", { ids: [b.dataset.reclaim] })));
  $$("[data-recode]").forEach((b) => (b.onclick = () => colEdit("reclaim", { codes: [Number(b.dataset.recode)] })));
  $$("[data-copy]").forEach((b) => (b.onclick = async () => {
    try { await navigator.clipboard.writeText(b.dataset.copy); toast(`Copied ${b.dataset.copy}`); }
    catch { dialog("Gift code", b.dataset.copy, [["OK", "green", true]], false); }
  }));
  $$("[data-grant]").forEach((b) => (b.onclick = async () => {
    if (!(await confirmDlg("Add to bag?", `Put the ${b.dataset.grant} rewards straight into your bag?\nThis doesn't use the code, so you can still redeem it in game.`))) return;
    colEdit("grant", { ids: [b.dataset.grant] });
  }));
  $("#col-all").onclick = async () => {
    if (!(await confirmDlg("Claim everything again?", "Mark every claimed gift and gift code as not claimed yet?"))) return;
    colEdit("reclaim", { ids: G.gifts.filter((g) => g.claimed).map((g) => g.id), codes: G.codes.map((c) => c.flag) });
  };
  $("#col-side").innerHTML = `
    <div class="band"><span>Gifts</span></div>
    <div class="muted">The game remembers each gift you claimed with one flag in the save. Claim again clears that flag.</div>
    <label class="field-label">Then, in game</label>
    <div class="muted">Save to file, start the game and open Menu > Gifts (second page of the menu). Add-on packs and LEVEL5 ID bonus content should be
      handed out again. For a gift code, enter the same code again in Gift Code Entry.</div>
    <div class="note">UNVERIFIED until checked in game. Gift codes are downloaded when you redeem them, so the server may
      still say a code was used, even with the flag cleared. Add-on packs still need the DLC on your Steam account.</div>`;
}

// ---------- Vulcan's Forge: craft out of game, pick the result ----------
const FG_ALL = "all";
const fgName = (id) => S.fg.names[id] || id;
const fgIcon = (id) => `<img src="game/items/${h(S.fg.icons[id] || id)}.png" alt="" onerror="this.style.visibility='hidden'">`;
const fgLife = (id) => String(S.fg.lives[id] || id).replace("?", "");

async function vForge() {
  if (!S.fg) {
    const d = await attempt(() => api("forge"));
    if (!d || S.view !== "forge") return;
    S.fg = d;
  }
  S.fgF ||= { life: "life0010", kind: FG_ALL, q: "" };
  S.fgPick ||= { id: null, grade: null, bonus: true, skills: ["", "", ""], plus: false, count: 1 };
  const tabs = [...new Set(S.fg.items.filter((e) => e.lives.includes(S.fgF.life)).map((e) => e.tab))].sort();
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: minmax(0, 1fr) 380px">
    <div class="panel" style="display:flex;flex-direction:column;min-height:0;padding:0 18px 14px">
      <div class="band"><span>Vulcan's Forge</span></div>
      <div class="tabs">${COL_LIVES.map((l) => `<button class="tab ${S.fgF.life === l ? "active" : ""}" data-fglife="${l}">
        <img class="col-life" src="game/life/${l}.png" alt="">${h(fgLife(l))}</button>`).join("")}</div>
      <div class="row col-filters">
        <select id="fg-kind"><option value="${FG_ALL}">All kinds</option>${tabs.map((t) => `<option ${S.fgF.kind === t ? "selected" : ""}>${h(t)}</option>`).join("")}</select>
        <input type="text" id="fg-q" placeholder="Search..." value="${h(S.fgF.q)}"></div>
      <div class="col-list" id="fg-list"></div>
    </div>
    <div class="panel scroll"><div class="pad" id="fg-side"></div></div>
  </div>`;
  $$("[data-fglife]").forEach((b) => (b.onclick = () => { S.fgF.life = b.dataset.fglife; S.fgF.kind = FG_ALL; vForge(); }));
  $("#fg-kind").onchange = (e) => { S.fgF.kind = e.target.value; fgList(); };
  $("#fg-q").oninput = (e) => { S.fgF.q = e.target.value; fgList(); };
  fgList();
  fgSide();
}
function fgList() {
  const f = S.fgF, q = f.q.trim().toLowerCase();
  const rows = S.fg.items.filter((e) => e.lives.includes(f.life) && (f.kind === FG_ALL || e.tab === f.kind)
    && (!q || fgName(e.id).toLowerCase().includes(q)));
  $("#fg-list").innerHTML = colListHtml(rows, (e) => `<div class="col-row fg-row ${S.fgPick.id === e.id ? "picked" : ""}" data-fgpick="${h(e.id)}">${fgIcon(e.id)}
    <span><b>${h(fgName(e.id))}</b><small>${h(e.tab)} <span class="col-stars">${stars(e.rarity)}</span></small></span>
    <span class="col-pill">${e.grades ? e.grades.map((g) => S.fg.grades[g]).join(" · ") : e.plus ? "Normal or +" : "Normal"}</span></div>`);
  $$("[data-fgpick]").forEach((b) => (b.onclick = () => {
    const e = S.fg.items.find((x) => x.id === b.dataset.fgpick);
    S.fgPick = { id: e.id, grade: e.grades ? e.grades[e.grades.length - 1] : null, quality: 3, bonus: true, skills: ["", "", ""], plus: !!e.plus, count: 1 };
    $$(".fg-row").forEach((r) => r.classList.toggle("picked", r.dataset.fgpick === e.id));
    fgSide();
  }));
}
function fgSide() {
  const p = S.fgPick, e = p.id && S.fg.items.find((x) => x.id === p.id);
  if (!e) {
    $("#fg-side").innerHTML = `<div class="band"><span>Vulcan's Forge</span></div>
      <div class="muted">Pick a recipe on the left. Vulcan makes it on the spot, no materials or minigame, and you choose how it
        comes out: the grade (Ordinary up to Legendary), the quality (Normal up to Top), its bonus stat and skills, or the
        + version of food and potions.</div>
      <div class="note">The item goes into your bag here in the editor. Press Save to file (with the game closed) to keep it.</div>`;
    return;
  }
  const gear = !!e.grades, g = p.grade;
  const mats = e.mats[String(g)] || e.mats["0"] || Object.values(e.mats)[0] || [];
  let body;
  if (gear) {
    const pool = e.pools[g - 1] || [], bonus = e.bonus[g - 1];
    const skillOpt = (cur) => `<option value="">(no skill)</option>` + pool.map((s) => `<option value="${h(s)}" ${cur === s ? "selected" : ""}>${h(S.fg.skills[s]?.desc || S.fg.skills[s]?.name || s)}</option>`).join("");
    body = `
      <label class="field-label">Grade</label>
      <div class="fg-grades">${[1, 2, 3, 4, 5].map((n) => { const ok = e.grades.includes(n);
        return `<button class="fg-grade ${n === g ? "active" : ""}" data-fggrade="${n}" ${ok ? "" : "disabled"}>
          <b>${h(S.fg.grades[n])}</b>
          <small>${ok ? e.stats.map(([lab, l]) => `${h(lab)} ${fmt(l[n - 1])}`).join("<br>") || "&nbsp;" : "not made in this grade"}</small></button>`; }).join("")}</div>
      <label class="field-label">Quality <small class="muted">(the minigame result)</small></label>
      <div class="fg-grades four">${[0, 1, 2, 3].map((n) => `<button class="fg-grade ${n === p.quality ? "active" : ""}" data-fgquality="${n}">
        <b>${h(S.fg.qualities[n])}</b></button>`).join("")}</div>
      ${bonus ? `<label class="fg-check"><input type="checkbox" id="fg-bonus" ${p.bonus ? "checked" : ""}> Bonus stat: ${h(S.fg.status[bonus] || bonus)}</label>` : ""}
      <label class="field-label">Skills ${pool.length ? `<small class="muted">(${pool.length} can roll at ${h(S.fg.grades[g])})</small>` : ""}</label>
      ${pool.length ? [0, 1, 2].map((i) => `<select class="fg-skill" data-fgskill="${i}">${skillOpt(p.skills[i])}</select>`).join("")
        : `<div class="muted">No skills roll on this item at this grade.</div>`}`;
  } else {
    body = e.plus ? `
      <label class="field-label">Result</label>
      <div class="fg-grades two">${[[false, e.id, "Normal craft"], [true, e.plus, "Great craft"]].map(([plus, id, lab]) =>
        `<button class="fg-grade ${p.plus === plus ? "active" : ""}" data-fgplus="${plus ? 1 : 0}">${fgIcon(id)}<b>${h(fgName(id))}</b><small>${lab}</small></button>`).join("")}</div>`
      : `<div class="muted">This recipe only has one result.</div>`;
  }
  $("#fg-side").innerHTML = `
    <div class="band"><span>${h(fgName(p.plus && e.plus && !gear ? e.plus : e.id))}</span></div>
    <div class="fg-head">${fgIcon(p.plus && e.plus && !gear ? e.plus : e.id)}<div><b>${h(e.tab)}</b>
      <small>${e.lives.map(fgLife).map(h).join(", ")} <span class="col-stars">${stars(e.rarity)}</span></small></div></div>
    ${body}
    <label class="field-label">How many</label>
    <div class="row"><input type="number" id="fg-count" min="1" max="99" value="${p.count}" style="width:90px">
      <button class="btn btn-green grow" id="fg-make">Forge</button></div>
    ${mats.length ? `<label class="field-label">The recipe would need</label>
      <div class="col-gift-items">${mats.map((m) => `<span>${fgIcon(m.id)}${h(fgName(m.id))} ×${m.num}</span>`).join("")}</div>
      <div class="muted" style="margin-top:4px">Vulcan doesn't take these from your bag.</div>` : ""}
    <div class="note">UNVERIFIED until checked in game: forge one, Save to file, load the save and look at the item in your bag
      (grade, quality, bonus stat and skills). The bonus amount is left for the game to work out, the way it is on every
      crafted item in your save. No item in your save has a quality yet, so how much Good, Great and Top add is the
      game's call.</div>`;
  $$("[data-fggrade]").forEach((b) => (b.onclick = () => { p.grade = Number(b.dataset.fggrade); p.skills = ["", "", ""]; fgSide(); }));
  $$("[data-fgquality]").forEach((b) => (b.onclick = () => { p.quality = Number(b.dataset.fgquality); fgSide(); }));
  $$("[data-fgplus]").forEach((b) => (b.onclick = () => { p.plus = b.dataset.fgplus === "1"; fgSide(); }));
  if ($("#fg-bonus")) $("#fg-bonus").onchange = (ev) => { p.bonus = ev.target.checked; };
  $$("[data-fgskill]").forEach((s) => (s.onchange = () => { p.skills[Number(s.dataset.fgskill)] = s.value; }));
  $("#fg-count").onchange = (ev) => { p.count = Math.max(1, Math.min(99, Number(ev.target.value) || 1)); ev.target.value = p.count; };
  $("#fg-make").onclick = async () => {
    const skills = p.skills.filter(Boolean);
    if (new Set(skills).size !== skills.length) return dialog("Pick different skills", "The same skill is picked twice.");
    const r = await attempt(() => api("forge_craft", { item_id: e.id, count: p.count, grade: gear ? g : null,
      bonus: p.bonus, skills: gear ? skills : [], plus: !gear && p.plus, quality: gear ? p.quality : 0 }));
    if (!r) return;
    const keep = $("#fg-list").scrollTop;
    afterEdit(r.summary, `Vulcan forged ${r.count} × ${gear ? `${S.fg.grades[g]} ` : ""}${r.name}${gear ? ` (${S.fg.qualities[p.quality]} quality)` : ""}`);
    if ($("#fg-list")) $("#fg-list").scrollTop = keep;
  };
}

// ---------- Records ----------
const recValue = (r) => (r.key === "playTime" ? `${Math.floor(r.value / 3600)}h ${String(Math.floor((r.value % 3600) / 60)).padStart(2, "0")}m` : fmt(r.value));
function recDelta(r) {
  const d = r.sinceFirst;
  if (!d) return "";
  const txt = r.key === "playTime" ? `${Math.floor(Math.abs(d) / 3600)}h ${Math.floor((Math.abs(d) % 3600) / 60)}m` : fmt(Math.abs(d));
  return `<span class="rec-delta ${d < 0 ? "down" : ""}" title="Change since the editor started tracking this save">${d < 0 ? "−" : "+"}${txt}</span>`;
}
async function fillRewalk() {
  const box = $("#rewalk-box");
  if (!box) return;
  const st = await attempt(() => api("rewalk_status"));
  if (!st) { box.textContent = "Could not read game fingerprint."; return; }
  const fp = st.fingerprint || {};
  const bits = [
    fp.ok ? `build ${fp.buildid || "?"}` : "game not found",
    st.key_ok ? "save key ok" : "save key needs rewalk",
    st.changed ? "fingerprint changed — will rewalk on start" : "fingerprint current",
    st.cache?.using_cache_pak ? "pak/usmap cache ready" : "pak/usmap from project (or missing)",
  ];
  box.innerHTML = `<div class="it-stat"><span>Install</span><b>${h(shortPath(fp.game || "?"))}</b></div>
    <div class="muted">${bits.map(h).join(" · ")}</div>`;
}
async function vFile() {
  const st = S.state || {}, s = S.sum;
  const rec = await attempt(() => api("records"));
  if (!rec || S.view !== "file") return;
  const tr = rec.tracking;
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: minmax(0, 1fr) 330px">
    <div class="panel scroll"><div class="pad">
      <div class="band"><span>Play Records</span></div>
      <div class="rec-summary">${rec.summary.map((r) => `<div><span class="k">${h(r.label)}</span><span class="v">${recValue(r)}</span>${recDelta(r)}</div>`).join("")}</div>
      ${rec.groups.map((g) => `<div class="group-title rec-group">${h(g.title)}</div>
        <div class="rec-grid">${g.rows.map((r) => `<label class="rec-row ${r.value ? "" : "zero"}"><span>${h(r.label)}${recDelta(r)}</span>
          <input type="number" min="0" max="${r.max}" data-rec="${h(r.key)}" value="${r.value}"></label>`).join("")}</div>`).join("")}
      <div class="row" style="margin-top:16px;justify-content:flex-end">
        <span class="muted">Edit any number, then Apply. Saved with Save to file like every other edit.</span>
        <button class="btn btn-green shrink" id="rec-apply">Apply</button></div>
      <div class="note">These are the counters the game itself keeps in the save. Several stay at 0 until later in the story, and
        the labels come from the save's field names, so a few may be worded differently in game.</div>
    </div></div>
    <div class="panel scroll"><div class="pad">
      <div class="band"><span>This Save</span></div>
      <div class="muted">Adventure started ${h(rec.started || "?")} · last saved ${h(rec.saved || "?")}</div>
      <label class="field-label">Tracking</label>
      <div class="muted">${tr.since ? `The editor has kept ${tr.snapshots} snapshot(s) of this save since ${h(tr.since)}. The green numbers show what changed since then, for things the game itself doesn't total up.` : "No snapshots yet."}</div>
      <label class="field-label">Loaded save</label>
      <input type="text" readonly value="${h(s.path)}" title="${h(s.path)}">
      <label class="field-label">Open another save</label>
      <div class="row"><select id="file-select">${(st.saves || []).map((p) => `<option ${p === s.path ? "selected" : ""} value="${h(p)}">${h(shortPath(p))}</option>`).join("")}</select>
        <button class="btn btn-cream btn-small shrink" id="file-open">Open</button></div>
      <div class="band" style="margin-top:14px"><span>Game install</span></div>
      <div id="rewalk-box" class="muted">Checking…</div>
      <button class="btn btn-cream btn-small" id="rewalk-btn" style="margin-top:8px">Rewalk game</button>
      <div class="note">Before every write the editor checks the game is closed, that the file hasn't changed since it was loaded, and makes a backup with a SHA-256. The packed file is re-read and verified before and after writing. After a Steam update it re-finds the install and save key on its own; Rewalk forces that now.</div>
    </div></div>
  </div>`;
  fillRewalk();
  $("#rewalk-btn").onclick = async () => {
    const r = await busy("Rewalking game…", () => attempt(() => api("rewalk", { force: true })));
    if (!r) return;
    toast(r.ok ? `Rewalk ok (${r.seconds}s)` : "Rewalk failed", !r.ok);
    fillRewalk();
  };
  $("#rec-apply").onclick = async () => {
    const values = {};
    for (const i of $$("[data-rec]")) {
      const row = rec.groups.flatMap((g) => g.rows).find((r) => r.key === i.dataset.rec);
      if (row && Number(i.value) !== row.value) values[i.dataset.rec] = Number(i.value);
    }
    if (!Object.keys(values).length) { toast("Nothing changed"); return; }
    const r = await attempt(() => api("set_records", { values }));
    if (r) afterEdit(r.summary, `${Object.keys(values).length} record(s) updated`);
  };
  $("#file-open").onclick = async () => {
    if (S.sum.dirty && !(await confirmDlg("Discard changes?", "You have unsaved edits. Open another save anyway?"))) return;
    const sum = await busy("Opening save...", () => attempt(() => api("load", { path: $("#file-select").value })));
    if (sum) { S.sum = sum; S.item = null; S.cat = null; S.ev = null; S.boardData = null; render(); status(`Loaded ${shortPath(sum.path)}.`); }
  };
}

// ---------- backups ----------
const hm = (sec) => `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
const saveLine = (i) => `${i.name} of ${i.island} · ${fmt(i.money)} Dosh · played ${hm(i.play_time)} · saved in game ${i.saved || "?"}`;
async function pickPath(mode, name = "") {
  const r = await attempt(() => api("pick", { mode, name }));
  if (!r) return null;
  if (!r.manual) return r.path;
  return prompt(mode === "save" ? "Full path (file or folder) to put the copy in:" : "Full path to the save copy to restore:") || null;
}
async function vBackups() {
  const b = await attempt(() => api("backups"));
  if (!b || S.view !== "backups") return;
  const cur = b.save;
  $("#view").innerHTML = `
  <div class="view cols" style="grid-template-columns: minmax(0, 1fr) 360px">
    <div class="panel scroll"><div class="pad">
      <div class="band"><span>Automatic Backups</span></div>
      <div class="muted">A copy of your save is made here before every save and every restore. Newest first.</div>
      <div class="bk-list">${b.backups.length ? b.backups.map((k, n) => `<div class="bk-row">
          <div><b>${h(k.when)}</b> <span class="bk-why">${h(k.reason || "backup")}</span>
            <div class="muted">${k.intact ? "Checked: matches its SHA-256" : k.intact === null ? "No SHA-256 record; checked again when restored"
              : "<span class='bad'>Does not match its SHA-256 record</span>"}</div></div>
          <button class="btn btn-cream btn-small shrink" data-restore="${n}">Restore</button></div>`).join("")
        : `<div class="muted" style="margin-top:12px">No backups yet. Press Back up now to make the first one.</div>`}</div>
      <label class="field-label">Backup folder</label>
      <div class="row"><input type="text" readonly value="${h(b.folder)}" title="${h(b.folder)}">
        <button class="btn btn-cream btn-small shrink" id="bk-folder">Open folder</button></div>
    </div></div>
    <div class="panel scroll"><div class="pad">
      <div class="band"><span>Your Save</span></div>
      <div class="muted">${h(saveLine(cur))}</div>
      <label class="field-label">Make a copy</label>
      <button class="btn btn-green bk-btn" id="bk-now">Back up now</button>
      <button class="btn btn-cream bk-btn" id="bk-to">Save a copy to...</button>
      <label class="field-label">Put a copy back</label>
      <button class="btn btn-cream bk-btn" id="bk-restore">Restore from file...</button>
      <div class="note">How your save is protected:<br>
        · Nothing is written while the game is running.<br>
        · A save only opens if it decrypts and repacks byte for byte, so the editor never works on a file it can't fully read.<br>
        · Before writing, the new file is re-read and checked; then a backup with a SHA-256 is made, the file is swapped in
        all at once (never half-written), and read back again.<br>
        · If the game saved since you opened the file, the editor refuses to overwrite that newer progress.<br>
        · A restore checks the copy the same way first, and backs up the current save before replacing it.</div>
    </div></div>
  </div>`;
  $("#bk-now").onclick = async () => {
    const r = await busy("Backing up...", () => attempt(() => api("backup_now")));
    if (r) { toast("Backed up"); vBackups(); }
  };
  $("#bk-to").onclick = async () => {
    const name = `${new Date().toISOString().slice(0, 10)} ${cur.name} ${cur.path.split(/[\\/]/).pop()}`.replace(/[\\/:*?"<>|]/g, "");
    const path = await pickPath("save", name);
    if (!path) return;
    const r = await busy("Copying and checking...", () => attempt(() => api("backup_to", { path })));
    if (r) dialog("Copy saved", `${r.path}\nSHA-256: ${r.sha256}\n\nKeep it wherever you like. Restore from file puts it back.`, [["OK", "green", true]], false);
  };
  const restore = async (path) => {
    const info = await busy("Checking the copy...", () => attempt(() => api("inspect", { path })));
    if (!info) return;
    const warn = [
      info.sha256 === cur.sha256 ? "This copy is identical to your current save." : "",
      info.same_adventure ? "" : "This copy is from a DIFFERENT adventure (other start date or island) than the loaded save.",
      S.sum.dirty ? "Your unsaved edits will be thrown away." : "",
    ].filter(Boolean).join("\n");
    const ok = await confirmDlg("Restore this copy?",
      `${saveLine(info)}\n\nIt will replace\n${cur.path}\n\nYour current save is backed up first.${warn ? "\n\n" + warn : ""}`);
    if (!ok) return;
    const r = await busy("Restoring...", () => attempt(() => api("restore", { path })));
    if (!r) return;
    S.sum = r.summary; S.item = null; S.cat = null; S.ev = null; S.boardData = null;
    status(`Restored from ${shortPath(r.from)}.`);
    dialog("Restored", `Your save is back to that copy.\nThe save it replaced was backed up to:\n${r.backup}`, [["OK", "green", true]], false);
    render();
  };
  $$("[data-restore]").forEach((x) => (x.onclick = () => restore(b.backups[Number(x.dataset.restore)].path)));
  $("#bk-folder").onclick = () => attempt(() => api("open_backups"));
  $("#bk-restore").onclick = async () => { const p = await pickPath("open"); if (p) restore(p); };
}

// ---------- save / revert ----------
async function saveNow() {
  if ($("#save-btn").disabled) return;
  if (!(await confirmDlg("Save to file?", `Write your changes to\n${S.sum.path}\n\nA backup with SHA-256 is made first.`))) return;
  const r = await busy("Packing, verifying and writing...", () => attempt(() => api("save")));
  if (!r) return;
  S.sum.dirty = false; updateButtons();
  status("Saved. Launch the game to see the changes.");
  dialog("Saved!", `Backup: ${r.backup}\nSHA-256: ${r.sha256}`, [["OK", "green", true]], false);
}
async function revert() {
  if (!(await confirmDlg("Revert?", "Throw away all unsaved edits and reload the save from disk?"))) return;
  const sum = await busy("Reloading...", () => attempt(() => api("revert")));
  if (sum) { S.sum = sum; S.item = null; S.boardData = null; S.ev = null; render(); status("Reverted to the file on disk."); }
}

// ---------- boot ----------
$$("#nav button").forEach((b) => (b.onclick = () => show(b.dataset.view)));
$("#save-btn").onclick = saveNow;
$("#revert-btn").onclick = revert;
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key.toLowerCase() === "s") { e.preventDefault(); saveNow(); }
  if (e.key === "Escape" && !$("#dialog-veil").hidden) $("#dialog-actions button")?.click();
});
document.addEventListener("contextmenu", (e) => { if (!e.target.matches("input, textarea, .log")) e.preventDefault(); });
initTitle();
