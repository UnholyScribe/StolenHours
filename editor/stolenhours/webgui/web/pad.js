"use strict";
// Controller and keyboard navigation (Steam Deck, Xbox, PlayStation, or arrows / Enter / Escape).
// The D-pad moves a highlight to the nearest control in that direction; anything with a click handler counts,
// so new screens work without extra wiring. Map-like surfaces get a pointer (Y) that fakes mouse input.

(() => {
  const NATIVE = "button, input, select, textarea, a[href], [tabindex]:not([tabindex='-1'])";
  const TYPING = /^(text|search|number|email|password|url|tel)$/;
  const BTN = { A: 0, B: 1, X: 2, Y: 3, LB: 4, RB: 5, LT: 6, RT: 7, VIEW: 8, START: 9, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15 };
  const DIRS = { [BTN.UP]: "up", [BTN.DOWN]: "down", [BTN.LEFT]: "left", [BTN.RIGHT]: "right" };
  const FIRST_REPEAT = 360, REPEAT = 95, DEAD = 0.5, PTR_SPEED = 1100;

  let cur = null;          // highlighted control
  let editing = null;      // field being changed: { el, start }
  let picker = null;       // { box, sel } while a dropdown's list is open
  let ptr = null;          // { x, y, el, over, down, moved } in pointer mode
  let kind = "xbox";       // glyph set: xbox, ps or keys
  let raf = 0, lastT = 0, fixQueued = false;
  const marks = new Map(); // scope element -> where the highlight was, to come back after dialogs / re-renders
  const held = {};         // button / direction -> { since, next }

  const on = () => document.body.classList.contains("pad-mode");
  const dialogOpen = () => !$("#dialog-veil").hidden;
  const busyOpen = () => !$("#busy").hidden;
  const inMenu = () => document.body.classList.contains("in-menu");
  const center = (r) => ({ x: (r.left + r.right) / 2, y: (r.top + r.bottom) / 2 });

  function scope() {
    if (picker) return picker.box;
    if (dialogOpen()) return $("#dialog-veil");
    return inMenu() ? $("#menu") : $("#title-screen");
  }

  // ---------- what can be highlighted ----------
  function actionable(el) {
    if (el.matches(NATIVE)) return !el.disabled && el.type !== "hidden";
    return !!(el.onclick || el.onpointerdown || el.onmousedown);
  }
  function visible(el, clipCache) {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2 || el.closest("[hidden]")) return false;
    if (getComputedStyle(el).visibility === "hidden") return false;
    // clipped away inside a non-scrolling box (map markers, zoomed board nodes) doesn't count
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      let c = clipCache.get(a);
      if (c === undefined) {
        const cs = getComputedStyle(a);
        const clips = cs.overflowX !== "visible" || cs.overflowY !== "visible";
        const scrolls = /auto|scroll/.test(cs.overflowX + cs.overflowY);
        c = clips && !scrolls ? a.getBoundingClientRect() : null;
        clipCache.set(a, c);
      }
      if (c && (r.right <= c.left || r.left >= c.right || r.bottom <= c.top || r.top >= c.bottom)) return false;
    }
    return true;
  }
  function candidates(root = scope(), near = null) {
    const cache = new Map(), w = innerWidth * 1.5, ht = innerHeight * 1.5;
    const list = [...root.querySelectorAll("*")].filter((el) => {
      if (!actionable(el)) return false;
      if (near) {
        const p = center(el.getBoundingClientRect());
        if (Math.abs(p.x - near.x) > w || Math.abs(p.y - near.y) > ht) return false;
      }
      return visible(el, cache);
    });
    // a drag surface (map, board) with controls inside steps aside for them; Y still gives the pointer
    return list.filter((el) => !(surface(el) && list.some((c) => c !== el && el.contains(c))));
  }
  const surface = (el) => !el.onclick && !el.matches(NATIVE) && !!(el.onpointerdown || el.onmousedown);

  // ---------- moving the highlight ----------
  function score(r, c, dir) {
    const horiz = dir === "left" || dir === "right", fwd = dir === "right" || dir === "down";
    const gap = horiz ? (fwd ? c.left - r.right : r.left - c.right) : (fwd ? c.top - r.bottom : r.top - c.bottom);
    if (gap < -4) return Infinity;
    const lo = horiz ? Math.max(r.top, c.top) : Math.max(r.left, c.left);
    const hi = horiz ? Math.min(r.bottom, c.bottom) : Math.min(r.right, c.right);
    const a = center(r), b = center(c), off = horiz ? Math.abs(b.y - a.y) : Math.abs(b.x - a.x);
    return Math.max(0, gap) + (hi > lo ? off * 0.05 : off * 2 + 40);
  }
  function move(dir) {
    if (!fix()) return;
    const r = cur.getBoundingClientRect();
    let best = null, bestScore = Infinity;
    for (const c of candidates(scope(), center(r))) {
      if (c === cur) continue;
      const s = score(r, c.getBoundingClientRect(), dir);
      if (s < bestScore) { bestScore = s; best = c; }
    }
    if (best) setCur(best);
  }
  function hover(el, enter) {
    if (!el || !(el.onmouseenter || el.onpointerenter || el.onmouseleave || el.onpointerleave)) return;
    const r = el.getBoundingClientRect(), p = center(r);
    const opt = { bubbles: false, clientX: p.x, clientY: p.y, view: window };
    if (enter) { el.dispatchEvent(new MouseEvent("mouseenter", opt)); el.dispatchEvent(new PointerEvent("pointerenter", opt)); }
    else { el.dispatchEvent(new MouseEvent("mouseleave", opt)); el.dispatchEvent(new PointerEvent("pointerleave", opt)); }
  }
  function signature(el) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const data = [...el.attributes].find((a) => a.name.startsWith("data-"));
    if (data) return `${el.tagName.toLowerCase()}[${data.name}="${data.value.replace(/["\\]/g, "\\$&")}"]`;
    return null;
  }
  function setCur(el, scroll = true) {
    if (!el) return;
    if (cur && cur !== el) { cur.classList.remove("pad-focus"); hover(cur, false); }
    cur = el;
    el.classList.add("pad-focus");
    hover(el, true);
    const a = document.activeElement;
    if (el.matches("button, a[href], input[type=checkbox]")) el.focus({ preventScroll: true });
    else if (a && a !== document.body && a !== el && !editing) a.blur();
    if (scroll) el.scrollIntoView({ block: "nearest", inline: "nearest" });
    const r = el.getBoundingClientRect();
    marks.set(scope(), { sel: signature(el), ...center(r) });
  }
  function nearest(list, p) {
    let best = null, d = Infinity;
    for (const c of list) {
      const q = center(c.getBoundingClientRect()), dd = (q.x - p.x) ** 2 + (q.y - p.y) ** 2;
      if (dd < d) { d = dd; best = c; }
    }
    return best;
  }
  function home(sc) {
    if (sc === $("#title-screen")) return $("#start-btn");
    if (sc === $("#dialog-veil")) return $("#dialog-actions button:last-child");
    if (picker && sc === picker.box) return $(".pad-opt.sel", sc) || $(".pad-opt", sc);
    const inView = candidates($("#view")).sort((a, b) => {
      const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      return ra.top - rb.top || ra.left - rb.left;
    });
    return inView[0] || $("#nav button.active");
  }
  // Keeps the highlight on something real after re-renders, dialogs and screen changes. Returns false if nothing.
  function fix() {
    const sc = scope();
    if (cur && cur.isConnected && sc.contains(cur) && visible(cur, new Map())) return true;
    const m = sc === $("#dialog-veil") ? null : marks.get(sc);
    let el = null;
    if (m) {
      const list = candidates(sc);
      const same = m.sel ? list.filter((c) => { try { return c.matches(m.sel); } catch { return false; } }) : [];
      el = nearest(same.length ? same : list, m);
    }
    el = el || home(sc);
    if (el) setCur(el);
    return !!el;
  }
  function queueFix() {
    if (fixQueued || !on()) return;
    fixQueued = true;
    requestAnimationFrame(() => { fixQueued = false; if (on() && !busyOpen()) fix(); });
  }

  // ---------- pressing things ----------
  function fire(el, type, init = {}) {
    const E = type.startsWith("pointer") ? PointerEvent : type === "wheel" ? WheelEvent : MouseEvent;
    el.dispatchEvent(new E(type, { bubbles: true, cancelable: true, composed: true, view: window, button: 0,
                                   pointerId: 1, pointerType: "mouse", isPrimary: true, ...init }));
  }
  function click(el) {
    if (typeof el.click === "function") el.click();
    else fire(el, "click");
  }
  function activate() {
    if (!fix()) return;
    const el = cur;
    if (el.tagName === "SELECT") return openPicker(el);
    if (el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && (TYPING.test(el.type) || el.type === "range"))) return edit(el);
    if (surface(el)) {
      const p = center(el.getBoundingClientRect());
      return pointerOn(p.x, p.y);
    }
    click(el);
    queueFix();
  }
  function back() {
    if (editing) return stopEdit();
    if (picker) return closePicker();
    if (ptr) return pointerOff();
    if (dialogOpen()) return $("#dialog-actions button")?.click();
    const sb = $("#sb-back");
    if (sb && cur && $("#view").contains(cur)) return sb.click();
    if (cur && $("#view")?.contains(cur)) setCur($("#nav button.active"));
  }

  // ---------- fields ----------
  function edit(el) {
    editing = { el, start: el.value };
    el.classList.add("pad-editing");
    el.focus({ preventScroll: true });
    if (TYPING.test(el.type) && el.type !== "number") el.select?.();
    hints();
  }
  function step(dir) {
    const el = editing.el;
    if (el.type !== "number" && el.type !== "range") return;
    try { dir === "up" || dir === "right" ? el.stepUp() : el.stepDown(); } catch { return; }
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }
  function stopEdit() {
    const { el, start } = editing;
    editing = null;
    el.classList.remove("pad-editing");
    const numeric = el.type === "number" || el.type === "range";
    el.blur();
    if (numeric && el.value !== start) el.dispatchEvent(new Event("change", { bubbles: true }));
    hints();
    queueFix();
  }
  function openPicker(sel) {
    const label = sel.labels?.[0]?.textContent?.trim() || sel.title || "Choose";
    const box = document.createElement("div");
    box.id = "pad-picker";
    box.innerHTML = `<div class="panel pad-picker-box"><div class="band"><span>${h(label)}</span></div>
      <div class="pad-picker-list">${[...sel.options].map((o, i) =>
        `<button class="pad-opt${i === sel.selectedIndex ? " sel" : ""}" data-padopt="${i}"${o.disabled ? " disabled" : ""}>${h(o.text)}</button>`).join("")}</div></div>`;
    document.body.appendChild(box);
    picker = { box, sel };
    box.onclick = (e) => { if (e.target === box) closePicker(); };
    $$("[data-padopt]", box).forEach((b) => (b.onclick = () => {
      const i = Number(b.dataset.padopt);
      closePicker();
      if (sel.selectedIndex !== i) {
        sel.selectedIndex = i;
        sel.dispatchEvent(new Event("input", { bubbles: true }));
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        queueFix();
      }
    }));
    padMode(true);
    setCur(home(box));
    hints();
  }
  function closePicker() {
    const { box, sel } = picker;
    picker = null;
    box.remove();
    if (sel.isConnected) setCur(sel); else queueFix();
    hints();
  }

  // ---------- pointer mode (maps, skill board, 3D preview) ----------
  function pointerOn(x, y) {
    if (ptr) return;
    const el = document.createElement("div");
    el.id = "pad-pointer";
    document.body.appendChild(el);
    ptr = { x, y, el, over: null, down: null, moved: 0 };
    pointerMove(0, 0);
    hints();
  }
  function pointerOff() {
    if (!ptr) return;
    if (ptr.down) pointerButton(false);
    ptr.el.remove();
    ptr = null;
    hints();
    queueFix();
  }
  function chain(el) { const out = []; for (; el; el = el.parentElement) out.push(el); return out; }
  function pointerMove(dx, dy) {
    const p = ptr;
    p.x = Math.max(0, Math.min(innerWidth - 1, p.x + dx));
    p.y = Math.max(0, Math.min(innerHeight - 1, p.y + dy));
    p.el.style.transform = `translate(${p.x}px, ${p.y}px)`;
    p.moved += Math.abs(dx) + Math.abs(dy);
    const at = { clientX: p.x, clientY: p.y, screenX: p.x, screenY: p.y, buttons: p.down ? 1 : 0 };
    const t = document.elementFromPoint(p.x, p.y);
    if (t !== p.over) {
      const was = chain(p.over), now = chain(t);
      if (p.over) { fire(p.over, "pointerout", at); fire(p.over, "mouseout", at); }
      was.filter((e) => !now.includes(e)).forEach((e) => { fire(e, "pointerleave", { ...at, bubbles: false }); fire(e, "mouseleave", { ...at, bubbles: false }); });
      if (t) { fire(t, "pointerover", at); fire(t, "mouseover", at); }
      now.filter((e) => !was.includes(e)).reverse().forEach((e) => { fire(e, "pointerenter", { ...at, bubbles: false }); fire(e, "mouseenter", { ...at, bubbles: false }); });
      p.over = t;
    }
    const target = p.down || t;
    if (target && (dx || dy)) { fire(target, "pointermove", at); fire(target, "mousemove", at); }
  }
  function pointerButton(down) {
    const p = ptr, at = { clientX: p.x, clientY: p.y, screenX: p.x, screenY: p.y };
    if (down) {
      const t = document.elementFromPoint(p.x, p.y);
      if (!t) return;
      p.down = t; p.moved = 0;
      fire(t, "pointerdown", { ...at, buttons: 1 });
      fire(t, "mousedown", { ...at, buttons: 1 });
      return;
    }
    const t = p.down;
    p.down = null;
    if (!t) return;
    fire(t, "pointerup", { ...at, buttons: 0 });
    fire(t, "mouseup", { ...at, buttons: 0 });
    if (p.moved < 8) {
      const under = document.elementFromPoint(p.x, p.y);
      const sel = under?.closest("select");
      if (sel) return openPicker(sel);
      const field = under?.closest("input, textarea");
      if (field && (TYPING.test(field.type) || field.tagName === "TEXTAREA")) { pointerOff(); setCur(field); return edit(field); }
      if (under) click(under);
    }
  }
  function pointerWheel(dy) {
    const t = document.elementFromPoint(ptr.x, ptr.y);
    if (!t) return;
    const ev = new WheelEvent("wheel", { bubbles: true, cancelable: true, view: window, clientX: ptr.x, clientY: ptr.y, deltaY: dy, deltaMode: 0 });
    t.dispatchEvent(ev);
    if (!ev.defaultPrevented) scroller(t)?.scrollBy(0, dy);
  }
  // synthetic pointers have no real capture; let handlers that ask for one carry on
  for (const name of ["setPointerCapture", "releasePointerCapture"]) {
    const orig = Element.prototype[name];
    Element.prototype[name] = function (id) { try { return orig.call(this, id); } catch (e) { if (!ptr) throw e; } };
  }

  // ---------- scrolling and paging ----------
  function scroller(el) {
    for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (/auto|scroll/.test(cs.overflowY) && a.scrollHeight > a.clientHeight + 1) return a;
    }
    return null;
  }
  function page(dir) {
    if (!fix()) return;
    const box = scroller(cur);
    if (!box) return move(dir > 0 ? "down" : "up");
    const was = center(cur.getBoundingClientRect());
    box.scrollBy({ top: dir * box.clientHeight * 0.85, behavior: "instant" });
    const br = box.getBoundingClientRect();
    const inside = candidates().filter((c) => {
      const r = c.getBoundingClientRect();
      return box.contains(c) && r.top >= br.top - 1 && r.bottom <= br.bottom + 1;
    });
    const el = nearest(inside, { x: was.x, y: dir > 0 ? br.bottom : br.top });
    if (el) setCur(el, false);
  }
  function switchScreen(d) {
    if (!inMenu() || dialogOpen() || picker) return;
    const bs = $$("#nav button");
    const i = bs.findIndex((b) => b.classList.contains("active"));
    const b = bs[(i + d + bs.length) % bs.length];
    b.click();
    setCur(b);
    // screens load their data; step into the content once it's there
    setTimeout(() => { if (cur === b) { const el = home(scope()); if (el && el !== b) setCur(el); } }, 350);
  }

  // ---------- mode, hints ----------
  function padMode(v) {
    if (v === on()) return;
    document.body.classList.toggle("pad-mode", v);
    if (!v) { pointerOff(); cur?.classList.remove("pad-focus"); }
    else if (cur) cur.classList.add("pad-focus");
    hints();
  }
  const GLYPH = {
    xbox: { A: "A", B: "B", X: "X", Y: "Y", LB: "LB", RB: "RB", LT: "LT", RT: "RT", LS: "L-stick", RS: "R-stick", START: "Menu" },
    ps: { A: "✕", B: "○", X: "□", Y: "△", LB: "L1", RB: "R1", LT: "L2", RT: "R2", LS: "L-stick", RS: "R-stick", START: "Options" },
    keys: { A: "Enter", B: "Esc", LB: "", RB: "", LT: "PgUp", RT: "PgDn" },
  };
  function hints() {
    let bar = $("#pad-hints");
    if (!bar) { bar = document.createElement("div"); bar.id = "pad-hints"; document.body.appendChild(bar); }
    bar.hidden = !on();
    if (!on()) return;
    const g = GLYPH[kind], k = (b, text) => (g[b] ? `<span class="ph"><b class="pg pg-${kind} pg-${b}">${g[b]}</b>${text}</span>` : "");
    let parts;
    if (editing) {
      const num = editing.el.type === "number" || editing.el.type === "range";
      parts = [num ? `<span class="ph"><b class="pg">D-pad</b>change</span>` : `<span class="ph"><b class="pg">Steam + X</b>keyboard</span>`, k("A", "done"), k("B", "done")];
    } else if (picker) parts = [k("A", "choose"), k("B", "cancel")];
    else if (ptr) parts = [`<span class="ph"><b class="pg">${kind === "keys" ? "Arrows" : g.LS}</b>move</span>`, k("A", kind === "keys" ? "click" : "click / hold to drag"), k("RS", "zoom"), k("B", "done")];
    else {
      parts = [k("A", "select"), k("B", "back")];
      if (inMenu()) parts.push(kind === "keys" ? "" : `<span class="ph"><b class="pg pg-${kind}">${g.LB}</b><b class="pg pg-${kind}">${g.RB}</b>screens</span>`, k("Y", "pointer"));
    }
    bar.innerHTML = parts.join("");
  }
  function padKind(pad) {
    const id = pad.id || "";
    const k = /054c|playstation|dualsense|dualshock|wireless controller/i.test(id) ? "ps" : "xbox";
    if (k !== kind) { kind = k; hints(); }
  }

  // ---------- gamepad loop ----------
  function repeat(key, active, t, fn) {
    if (!active) { delete held[key]; return; }
    const s = held[key];
    if (!s) { held[key] = { next: t + FIRST_REPEAT }; fn(); }
    else if (t >= s.next) { s.next = t + REPEAT; fn(); }
  }
  function pressed(key, active) {  // true once per press
    const was = held[key];
    if (!active) { delete held[key]; return false; }
    if (was) return false;
    held[key] = { next: Infinity };
    return true;
  }
  function loop(t) {
    const pads = navigator.getGamepads ? [...navigator.getGamepads()].filter(Boolean) : [];
    if (!pads.length) { raf = 0; return; }
    raf = requestAnimationFrame(loop);
    const dt = Math.min(0.05, (t - (lastT || t)) / 1000);
    lastT = t;
    const btn = (i) => pads.some((p) => p.buttons[i] && (p.buttons[i].pressed || p.buttons[i].value > 0.5));
    const axis = (i) => pads.reduce((v, p) => (Math.abs(p.axes[i] || 0) > Math.abs(v) ? p.axes[i] : v), 0);
    const lx = axis(0), ly = axis(1), rx = axis(2), ry = axis(3);
    const any = pads.some((p) => p.buttons.some((b) => b.pressed)) || [lx, ly, rx, ry].some((v) => Math.abs(v) > DEAD);
    if (!any) { for (const k of Object.keys(held)) delete held[k]; return; }
    const active = pads.find((p) => p.buttons.some((b) => b.pressed)) || pads[0];
    padKind(active);
    if (busyOpen() || document.hidden) return;
    let dir = null;
    for (const [b, d] of Object.entries(DIRS)) if (btn(Number(b))) dir = d;
    if (!dir && Math.hypot(lx, ly) > DEAD) dir = Math.abs(lx) > Math.abs(ly) ? (lx > 0 ? "right" : "left") : (ly > 0 ? "down" : "up");
    if (!on()) {  // the first touch only shows where the highlight is
      padMode(true); fix();
      for (const k of Object.keys(BTN)) if (btn(BTN[k])) held[k] = { next: Infinity };
      if (dir) held["dir-" + dir] = { next: Infinity };
      return;
    }
    if (ptr) {
      const mag = Math.hypot(lx, ly);
      if (mag > 0.18) {
        const s = PTR_SPEED * dt * Math.min(1, (mag - 0.18) / 0.82) ** 2 / mag;
        pointerMove(lx * s * mag, ly * s * mag);
      }
      for (const [b, d] of Object.entries(DIRS)) {
        repeat("p" + b, btn(Number(b)), t, () => pointerMove(d === "left" ? -6 : d === "right" ? 6 : 0, d === "up" ? -6 : d === "down" ? 6 : 0));
      }
      const a = btn(BTN.A);
      if (a && !ptr.down && pressed("A", true)) pointerButton(true);
      if (!a) { if (ptr.down) pointerButton(false); pressed("A", false); }
      if (Math.abs(ry) > DEAD) repeat("wheel", true, t, () => pointerWheel(ry > 0 ? 100 : -100));
      else delete held.wheel;
      if (pressed("B", btn(BTN.B)) || pressed("Y", btn(BTN.Y))) pointerOff();
      return;
    }
    for (const d of ["up", "down", "left", "right"]) {
      repeat("dir-" + d, dir === d, t, () => (editing ? step(d) : move(d)));
    }
    if (Math.abs(ry) > 0.2 && !editing && !picker) {
      const box = cur && scroller(cur);
      if (box) box.scrollBy(0, ry * 900 * dt);
    }
    if (pressed("A", btn(BTN.A))) editing ? stopEdit() : activate();
    if (pressed("B", btn(BTN.B))) back();
    if (pressed("Y", btn(BTN.Y)) && !editing && !picker && inMenu()) {
      const p = cur ? center(cur.getBoundingClientRect()) : { x: innerWidth / 2, y: innerHeight / 2 };
      pointerOn(p.x, p.y);
    }
    if (!editing) {
      if (pressed("LB", btn(BTN.LB))) switchScreen(-1);
      if (pressed("RB", btn(BTN.RB))) switchScreen(1);
      repeat("LT", btn(BTN.LT), t, () => page(-1));
      repeat("RT", btn(BTN.RT), t, () => page(1));
      if (pressed("START", btn(BTN.START)) && inMenu() && !dialogOpen() && !picker) setCur($("#save-btn"));
      if (pressed("VIEW", btn(BTN.VIEW)) && inMenu() && !dialogOpen() && !picker) setCur($("#nav button.active"));
    }
  }
  function startLoop() { if (!raf) { lastT = 0; raf = requestAnimationFrame(loop); } }
  addEventListener("gamepadconnected", (e) => {
    padKind(e.gamepad);
    if (typeof toast === "function") toast(`Controller connected: ${kind === "ps" ? "PlayStation" : "Xbox-style"} buttons`);
    startLoop();
  });
  if (navigator.getGamepads && [...navigator.getGamepads()].some(Boolean)) startLoop();

  // ---------- keyboard ----------
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    const a = document.activeElement;
    const field = a && a.matches("input, select, textarea") && !/^(checkbox|radio|button|submit)$/.test(a.type);
    const dir = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" }[e.key];
    if (field) {
      if (editing && (e.key === "Escape" || (e.key === "Enter" && a.tagName !== "TEXTAREA"))) { e.preventDefault(); stopEdit(); }
      else if (!editing && e.key === "Escape") a.blur();
      return;
    }
    if (busyOpen()) return;
    if (kind !== "keys" && !raf) { kind = "keys"; hints(); }
    if (dir) {
      e.preventDefault();
      if (!on()) { padMode(true); fix(); return; }
      if (ptr) pointerMove(dir === "left" ? -12 : dir === "right" ? 12 : 0, dir === "up" ? -12 : dir === "down" ? 12 : 0);
      else move(dir);
    } else if (e.key === "Enter" || e.key === " ") {
      if (!on()) return;
      if (ptr) { e.preventDefault(); pointerButton(true); pointerButton(false); return; }
      if (a && a === cur && a.matches("button, a[href]")) return;  // the browser presses it
      if (e.key === " " && a && a.matches("input[type=checkbox]")) return;
      e.preventDefault();
      activate();
    } else if (e.key === "Escape" && on() && (!dialogOpen() || picker || ptr)) {
      e.preventDefault(); e.stopImmediatePropagation(); back();
    } else if (e.key === "PageDown" || e.key === "PageUp") {
      if (!on()) return;
      e.preventDefault(); page(e.key === "PageDown" ? 1 : -1);
    }
  }, true);

  // real mouse or touch hands control back to the pointer
  addEventListener("mousemove", (e) => { if (e.isTrusted && (e.movementX || e.movementY) && on()) padMode(false); }, true);
  addEventListener("pointerdown", (e) => { if (e.isTrusted && on() && !picker) padMode(false); }, true);
  document.addEventListener("focusin", (e) => {
    if (on() && e.target !== cur && actionable(e.target) && scope().contains(e.target)) setCur(e.target, false);
  });
  new MutationObserver(queueFix).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });
})();
