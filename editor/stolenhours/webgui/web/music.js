// Dashboard music: cycles through web/music/playlist.json. Add tracks there to grow the loop.
"use strict";

const Music = (() => {
  const KEY = "stolenhours-music-muted";
  let tracks = [];
  let volume = 0.45;
  let idx = 0;
  let audio = null;
  let armed = false; // user gesture received; may retry play until it sticks
  let muted = localStorage.getItem(KEY) === "1";

  function label() {
    const t = tracks[idx];
    return t ? t.title || t.file : "Music";
  }

  function syncUi() {
    for (const b of document.querySelectorAll("[data-music-toggle]")) {
      b.textContent = muted ? "Music off" : "Music on";
      b.title = muted ? "Unmute dashboard music" : `Playing: ${label()} (click to mute)`;
      b.setAttribute("aria-pressed", muted ? "true" : "false");
      b.classList.toggle("music-off", muted);
    }
  }

  async function load() {
    try {
      const r = await fetch("music/playlist.json", { cache: "no-cache" });
      if (!r.ok) return;
      const j = await r.json();
      tracks = (j.tracks || []).filter((t) => t && t.file);
      if (typeof j.volume === "number") volume = Math.min(1, Math.max(0, j.volume));
    } catch {
      tracks = [];
    }
  }

  function ensureAudio() {
    if (audio) return audio;
    audio = new Audio();
    audio.preload = "auto";
    audio.addEventListener("ended", () => {
      if (!tracks.length || muted) return;
      idx = (idx + 1) % tracks.length;
      playCurrent();
    });
    audio.addEventListener("error", () => {
      if (tracks.length > 1 && !muted) {
        idx = (idx + 1) % tracks.length;
        playCurrent();
      }
    });
    return audio;
  }

  function trackUrl(file) {
    return new URL(`music/${file}`, location.href).href;
  }

  function playCurrent() {
    if (!tracks.length || muted) {
      syncUi();
      return Promise.resolve();
    }
    const a = ensureAudio();
    const t = tracks[idx];
    const url = trackUrl(t.file);
    if (a.src !== url) a.src = url;
    a.volume = volume;
    a.loop = tracks.length === 1;
    syncUi();
    return a.play().catch(() => {
      // Gesture may have been spent (e.g. opening the save dropdown). Caller can retry on Start.
    });
  }

  async function start() {
    if (!tracks.length) await load();
    if (!tracks.length) return;
    if (!armed) {
      armed = true;
      idx = Math.floor(Math.random() * tracks.length);
    }
    // Always (re)attempt — earlier play() may have been blocked by the browser.
    if (!muted) await playCurrent();
    else syncUi();
  }

  function toggleMute() {
    muted = !muted;
    localStorage.setItem(KEY, muted ? "1" : "0");
    if (muted) {
      if (audio) {
        audio.pause();
        audio.volume = 0;
      }
      syncUi();
      return;
    }
    // Unmute: arm + play in this click (reliable user gesture).
    start();
  }

  function bind() {
    document.querySelectorAll("[data-music-toggle]").forEach((b) => {
      b.onclick = (ev) => {
        ev.stopPropagation();
        toggleMute();
      };
    });
    syncUi();
  }

  return { load, start, toggleMute, bind, syncUi };
})();

window.Music = Music;
