"""Tkinter desktop editor. Mode A edits the file while the game is closed; the Live tab is Mode B."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import live, paths, safety, savefile

POLL_MS = 2000


class App(tk.Tk):
    def __init__(self, save_path: Path | None):
        super().__init__()
        self.title("Stolen Hours - Fantasy Life i")
        self.geometry("980x640")
        self.save_path = save_path
        self.sf: savefile.SaveFile | None = None
        self.item_names = savefile.load_item_names()
        self.bridge = live.LiveBridge()
        self.game_running = False

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        self.path_var = tk.StringVar(value=str(save_path) if save_path else "")
        ttk.Label(top, text="Save:").pack(side="left")
        ttk.Combobox(top, textvariable=self.path_var, width=80,
                     values=[str(p) for p in paths.candidate_save_paths()]).pack(side="left", padx=4)
        ttk.Button(top, text="Browse", command=self.browse).pack(side="left")
        ttk.Button(top, text="Load", command=self.load).pack(side="left", padx=4)
        self.save_btn = ttk.Button(top, text="Save to file", command=self.save, state="disabled")
        self.save_btn.pack(side="left")

        self.status = tk.StringVar(value="not loaded")
        self.game_status = tk.StringVar()
        bar = ttk.Frame(self, padding=(6, 0))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status).pack(side="left")
        ttk.Label(bar, textvariable=self.game_status).pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._build_overview(nb)
        self._build_lives(nb)
        self._build_inventory(nb)
        self._build_appearance(nb)
        self._build_live(nb)

        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()
        self.after(50, self._drain)
        self.after(100, self.poll)
        self.after(200, self.load)

    def ui(self, fn):
        """Run fn on the Tk thread; worker threads must not touch Tk directly."""
        self._ui_queue.put(fn)

    def _drain(self):
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            fn()
        self.after(50, self._drain)

    # ---- layout ----------------------------------------------------------------
    def _build_overview(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="Overview")
        self.ov = {k: tk.StringVar() for k in ("name", "island", "money", "life", "playtime")}
        rows = [("Character name", "name", True), ("Island", "island", False), ("Dosh", "money", True),
                ("Current life", "life", False), ("Play time", "playtime", False)]
        for r, (label, key, editable) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(f, textvariable=self.ov[key], width=40,
                      state="normal" if editable else "readonly").grid(row=r, column=1, sticky="w")
        ttk.Button(f, text="Apply", command=self.apply_overview).grid(row=len(rows), column=1, sticky="w", pady=8)

    def _build_lives(self, nb):
        f = ttk.Frame(nb, padding=6)
        nb.add(f, text="Lives")
        cols = ("id", "name", "level", "exp", "rank", "star")
        self.lives_tv = ttk.Treeview(f, columns=cols, show="headings", height=16)
        for c in cols:
            self.lives_tv.heading(c, text=c + (" (unverified)" if c == "name" else ""))
            self.lives_tv.column(c, width=160 if c == "name" else 90)
        self.lives_tv.pack(fill="both", expand=True)
        ed = ttk.Frame(f)
        ed.pack(fill="x", pady=4)
        self.life_edit = {k: tk.StringVar() for k in ("level", "exp", "rank")}
        for k in ("level", "exp", "rank"):
            ttk.Label(ed, text=k).pack(side="left")
            ttk.Entry(ed, textvariable=self.life_edit[k], width=10).pack(side="left", padx=4)
        ttk.Button(ed, text="Apply to selected", command=self.apply_life).pack(side="left", padx=8)
        self.lives_tv.bind("<<TreeviewSelect>>", self.on_life_select)

    def _build_inventory(self, nb):
        f = ttk.Frame(nb, padding=6)
        nb.add(f, text="Inventory")
        row = ttk.Frame(f)
        row.pack(fill="x")
        self.cat_var = tk.StringVar()
        self.cat_cb = ttk.Combobox(row, textvariable=self.cat_var, state="readonly", width=30)
        self.cat_cb.pack(side="left")
        self.cat_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_items())
        cols = ("slot", "id", "name", "stock")
        self.items_tv = ttk.Treeview(f, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (60, 140, 360, 80)):
            self.items_tv.heading(c, text=c)
            self.items_tv.column(c, width=w)
        self.items_tv.pack(fill="both", expand=True, pady=4)
        ed = ttk.Frame(f)
        ed.pack(fill="x")
        self.stock_var = tk.StringVar()
        ttk.Label(ed, text="Stock").pack(side="left")
        ttk.Entry(ed, textvariable=self.stock_var, width=8).pack(side="left", padx=4)
        ttk.Button(ed, text="Set stock of selected", command=self.apply_stock).pack(side="left")
        ttk.Separator(ed, orient="vertical").pack(side="left", fill="y", padx=10)
        self.add_query = tk.StringVar()
        ttk.Label(ed, text="Add item (id or name)").pack(side="left")
        ttk.Entry(ed, textvariable=self.add_query, width=28).pack(side="left", padx=4)
        ttk.Button(ed, text="Add", command=self.add_item).pack(side="left")

    def _build_appearance(self, nb):
        outer = ttk.Frame(nb, padding=12)
        nb.add(outer, text="Appearance")
        ttk.Label(outer, wraplength=900, text=(
            "IDs must keep their current shape (e.g. color_hair_NN). Which IDs exist in game is not checked; "
            "an unknown ID may break the character. Every save write makes a backup first.")).pack(anchor="w")
        self.app_frame = ttk.Frame(outer)
        self.app_frame.pack(anchor="w", pady=6)
        self.app_vars: dict[str, tk.StringVar] = {}
        ttk.Button(outer, text="Apply", command=self.apply_appearance).pack(anchor="w")

    def _build_live(self, nb):
        f = ttk.Frame(nb, padding=6)
        nb.add(f, text="Live (game running)")
        ttk.Label(f, wraplength=900, text=(
            "Needs the game running with UE4SS and the StolenHours mod. Commands run on the game thread. "
            "Find a property first (e.g. Money), then Get/Set it on the object path it reports.")).pack(anchor="w")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=6)
        self.live_target = tk.StringVar()
        self.live_prop = tk.StringVar(value="Money")
        self.live_value = tk.StringVar()
        for label, var, w in (("Target (class or object path)", self.live_target, 46),
                              ("Property", self.live_prop, 16), ("Value", self.live_value, 12)):
            ttk.Label(row, text=label).pack(side="left")
            ttk.Entry(row, textvariable=var, width=w).pack(side="left", padx=4)
        btns = ttk.Frame(f)
        btns.pack(fill="x")
        for text, fn in (("Ping", lambda: self.bridge.ping()),
                         ("Find property", lambda: self.bridge.find_prop(self.live_prop.get())),
                         ("Get", lambda: self.bridge.get(self.live_target.get(), self.live_prop.get())),
                         ("Set", lambda: self.bridge.set(self.live_target.get(), self.live_prop.get(), self.live_value.get())),
                         ("List props", lambda: self.bridge.list_props(self.live_target.get())),
                         ("Dump everything", self._dump_and_analyze)):
            ttk.Button(btns, text=text, command=lambda fn=fn: self.run_live(fn)).pack(side="left", padx=2)
        self.live_out = tk.Text(f, height=20)
        self.live_out.pack(fill="both", expand=True, pady=6)

    # ---- actions ---------------------------------------------------------------
    def browse(self):
        p = filedialog.askopenfilename(filetypes=[("Fantasy Life i save", "*.bin"), ("All", "*.*")])
        if p:
            self.path_var.set(p)

    def load(self):
        if not self.path_var.get().strip():
            self.status.set("no save found automatically; use Browse")
            return
        self.status.set("loading (decrypt, parse, byte-exact checks)...")
        self.save_btn.config(state="disabled")
        path = Path(self.path_var.get())

        def work():
            try:
                sf = savefile.SaveFile.load(path)
            except Exception as e:  # shown to the user, nothing else to do
                self.ui(lambda e=e: (self.status.set(f"load failed: {e}"), messagebox.showerror("Load failed", str(e))))
                return
            self.ui(lambda: self._loaded(sf))
        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, sf):
        self.sf = sf
        self.status.set(f"loaded {sf.path.name}: roundtrip byte-exact")
        self.refresh_all()
        self.update_save_button()

    def refresh_all(self):
        sf = self.sf
        h, m = divmod(sf.play_time_seconds // 60, 60)
        self.ov["name"].set(sf.character_name)
        self.ov["island"].set(sf.island_name)
        self.ov["money"].set(str(sf.money))
        self.ov["life"].set(f"{sf.current_life} ({savefile.LIFE_NAMES.get(sf.current_life, '?')})")
        self.ov["playtime"].set(f"{h}h {m:02d}m")
        self.lives_tv.delete(*self.lives_tv.get_children())
        for l in sf.lives():
            self.lives_tv.insert("", "end", iid=l["id"], values=(l["id"], l["name"], l["level"], l["exp"], l["rank"], l["star"]))
        app = sf.appearance()
        if set(app) != set(self.app_vars):
            for w in self.app_frame.winfo_children():
                w.destroy()
            self.app_vars = {}
            for r, k in enumerate(app):
                self.app_vars[k] = tk.StringVar()
                ttk.Label(self.app_frame, text=k).grid(row=r % 11, column=(r // 11) * 2, sticky="w", padx=(0, 6), pady=1)
                ttk.Entry(self.app_frame, textvariable=self.app_vars[k], width=22).grid(
                    row=r % 11, column=(r // 11) * 2 + 1, sticky="w", padx=(0, 18))
        for k, v in app.items():
            self.app_vars[k].set(str(v))
        cats = sf.inventory_categories()
        self.cat_cb.config(values=cats)
        if self.cat_var.get() not in cats:
            self.cat_var.set("invMaterial" if "invMaterial" in cats else cats[0])
        self.refresh_items()

    def refresh_items(self):
        if not self.sf:
            return
        self.items_tv.delete(*self.items_tv.get_children())
        for it in self.sf.items(self.cat_var.get()):
            self.items_tv.insert("", "end", iid=str(it.index), values=(
                it.index, it.item_id, self.item_names.get(it.item_id, ""), "" if it.stock is None else it.stock))

    def _edit(self, fn):
        if not self.sf:
            return
        try:
            fn()
        except (savefile.SaveFileError, ValueError) as e:
            messagebox.showerror("Edit rejected", str(e))
            return
        self.refresh_all()
        self.status.set("unsaved changes")
        self.update_save_button()

    def apply_overview(self):
        def f():
            if self.ov["name"].get() != self.sf.character_name:
                self.sf.character_name = self.ov["name"].get()
            if int(self.ov["money"].get()) != self.sf.money:
                self.sf.money = int(self.ov["money"].get())
        self._edit(f)

    def apply_appearance(self):
        def f():
            cur = self.sf.appearance()
            for k, var in self.app_vars.items():
                if var.get() != str(cur[k]):
                    self.sf.set_appearance(k, var.get())
        self._edit(f)

    def on_life_select(self, _):
        sel = self.lives_tv.selection()
        if sel:
            v = self.lives_tv.item(sel[0], "values")
            self.life_edit["level"].set(v[2]); self.life_edit["exp"].set(v[3]); self.life_edit["rank"].set(v[4])

    def apply_life(self):
        sel = self.lives_tv.selection()
        if sel:
            self._edit(lambda: self.sf.set_life(sel[0], level=int(self.life_edit["level"].get()),
                                                exp=int(self.life_edit["exp"].get()), rank=int(self.life_edit["rank"].get())))

    def apply_stock(self):
        sel = self.items_tv.selection()
        if sel:
            self._edit(lambda: self.sf.set_stock(self.cat_var.get(), int(sel[0]), int(self.stock_var.get())))

    def add_item(self):
        q = self.add_query.get().strip()
        if not q:
            return
        ids = [q] if q in self.item_names else [k for k, v in self.item_names.items() if v.lower() == q.lower()]
        if not ids:
            ids = [k for k, v in self.item_names.items() if q.lower() in v.lower()]
            if len(ids) != 1:
                messagebox.showinfo("Add item", f"{len(ids)} matches; type the exact id or name.\n" +
                                    "\n".join(f"{k}  {self.item_names[k]}" for k in ids[:25]))
                return
        stock = int(self.stock_var.get() or 1)
        self._edit(lambda: self.sf.add_item(self.cat_var.get(), ids[0], stock))

    def save(self):
        if not self.sf:
            return
        if not messagebox.askyesno("Save", f"Write changes to\n{self.sf.path}\n\nA SHA-256 backup is made first."):
            return
        self.status.set("packing, verifying, writing...")
        self.save_btn.config(state="disabled")

        def work():
            try:
                res = self.sf.write()
            except Exception as e:
                self.ui(lambda e=e: (messagebox.showerror("Save failed", str(e)), self.update_save_button()))
                return
            self.ui(lambda: (self.status.set(f"saved; backup at {res['backup']}"), self.update_save_button()))
        threading.Thread(target=work, daemon=True).start()

    def _dump_and_analyze(self) -> live.Reply:
        """Runs on a worker thread (via run_live)."""
        from . import dumpscan
        r = self.bridge.dump()
        if not r.ok or not self.sf:
            return r
        path = dumpscan.latest_dump()
        targets = dumpscan.save_targets(self.sf)
        text = dumpscan.format_report(dumpscan.analyze(path, targets), targets)
        report = path.with_name(path.name.replace("values_", "report_"))
        report.write_text(text, encoding="utf-8")
        return live.Reply(True, r.text + " | report " + str(report) + " | " +
                          text.split("== Game-code properties")[0].replace("\n", " | "))

    def run_live(self, fn):
        def work():
            try:
                r = fn()
                text = ("OK  " if r.ok else "ERR ") + r.text.replace(" | ", "\n    ")
            except live.LiveError as e:
                text = f"ERR {e}"
            self.ui(lambda: self.live_out.insert("end", text + "\n"))
        threading.Thread(target=work, daemon=True).start()

    def update_save_button(self):
        ok = self.sf is not None and self.sf.dirty and not self.game_running
        self.save_btn.config(state="normal" if ok else "disabled")

    def poll(self):
        def work():
            procs = safety.running_game_processes()
            alive = self.bridge.mod_alive()
            self.ui(lambda: self._polled(procs, alive))
        threading.Thread(target=work, daemon=True).start()
        self.after(POLL_MS, self.poll)

    def _polled(self, procs, alive):
        self.game_running = bool(procs)
        mode = "Mode B (game running, file writes locked)" if procs else "Mode A (game closed)"
        self.game_status.set(f"{mode} | live mod: {'connected' if alive else 'not connected'}")
        self.update_save_button()


def main(save_path: Path | None):
    App(save_path).mainloop()
