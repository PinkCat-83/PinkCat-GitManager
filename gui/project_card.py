"""
project_card.py
Widget de tarjeta de proyecto: cabecera con estado y lanzador,
cuerpo colapsable con metadatos y botones de acción (Push/Pull/Log/...).
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
import threading

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from src import git_operations as git
from src import project_manager as pm

from gui.theme import (
    C, FONT_BIG, FONT_MONO_S, FONT_SMALL, FONT_LABEL_B,
    _fmt_date, _status_color, _dot_color, _status_label,
)

# ─── Tarjeta de proyecto ──────────────────────────────────────────────────────
class ProjectCard(ctk.CTkFrame):
    def __init__(self, master, project: dict, on_remove, on_push, on_pull, on_log, on_purge, on_ghost, on_changes, on_gitignore, on_launcher=None, on_init=None, **kwargs):
        super().__init__(
            master, fg_color=C["card"],
            corner_radius=10, border_color=C["border"], border_width=1,
            **kwargs
        )
        self.project   = project
        self.on_remove = on_remove
        self.on_push   = on_push
        self.on_pull   = on_pull
        self.on_log    = on_log
        self.on_purge  = on_purge
        self.on_ghost   = on_ghost
        self.on_changes   = on_changes
        self.on_gitignore = on_gitignore
        self.on_launcher  = on_launcher
        self.on_init      = on_init

        self._status   = {}
        self._loading  = False

        self._build()
        self.refresh_status()

    def _build(self):
        p = self.project
        has_git = git.has_git_repo(p["path"])
        self._collapsed = True

        # ── Fila superior (siempre visible) ──
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 12))

        # Chevron colapso
        self.chevron = ctk.CTkLabel(
            top, text="▸", font=("Consolas", 20), text_color=C["text_dim"],
            width=24, cursor="hand2"
        )
        self.chevron.pack(side="left", padx=(0, 6))
        self.chevron.bind("<Button-1>", lambda _: self._toggle())

        # Indicador git (color dinámico: verde=ok, amarillo=cambios, rojo=sin repo)
        init_dot = C["red"] if not has_git else C["text_muted"]
        self.dot = ctk.CTkLabel(
            top, text="●", font=("Consolas", 18), text_color=init_dot, width=20
        )
        self.dot.pack(side="left", padx=(0, 8))

        # Botón lanzador (icono del programa)
        self._launcher_btn = self._make_launcher_btn(top, p)
        self._launcher_btn.pack(side="left", padx=(0, 8))

        # Nombre — clic también colapsa
        name_lbl = ctk.CTkLabel(
            top, text=p["name"],
            font=FONT_BIG, text_color=C["text"], anchor="w", cursor="hand2"
        )
        name_lbl.pack(side="left", fill="x", expand=True)
        name_lbl.bind("<Button-1>", lambda _: self._toggle())

        # Botón abrir carpeta
        ctk.CTkButton(
            top, text="📁", width=32, height=32,
            fg_color="transparent", hover_color=C["card_hover"],
            text_color=C["text_dim"], corner_radius=6, font=("Segoe UI", 15),
            command=lambda: self._open_folder(p["path"])
        ).pack(side="right", padx=(4, 0))

        # Botón eliminar
        ctk.CTkButton(
            top, text="✕", width=28, height=32,
            fg_color="transparent", hover_color=C["card_hover"],
            text_color=C["text_muted"], corner_radius=6, font=("Segoe UI", 13),
            command=lambda: self.on_remove(p["id"])
        ).pack(side="right")

        # ── Cuerpo colapsable (empieza colapsado) ──
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        # NO hacemos pack aquí; se muestra al hacer _toggle

        # Ruta
        ctk.CTkLabel(
            self.body, text=p["path"],
            font=FONT_MONO_S, text_color=C["text_dim"], anchor="w",
            wraplength=560
        ).pack(fill="x", padx=44, pady=(0, 2))

        # Estado
        self.status_label = ctk.CTkLabel(
            self.body, text="Calculando estado...",
            font=FONT_SMALL, text_color=C["text_dim"], anchor="w"
        )
        self.status_label.pack(fill="x", padx=44, pady=(0, 8))

        # Separador
        ctk.CTkFrame(self.body, fg_color=C["border"], height=1).pack(fill="x", padx=16, pady=(0, 8))

        # Fila inferior: metadatos + botones
        bottom = ctk.CTkFrame(self.body, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 12))

        # Metadatos
        meta = ctk.CTkFrame(bottom, fg_color="transparent")
        meta.pack(side="left", fill="y")

        if has_git:
            branch = git.get_current_branch(p["path"])
            ctk.CTkLabel(
                meta, text=f"⎇  {branch}",
                font=FONT_MONO_S, text_color=C["blue"]
            ).pack(anchor="w")

        self.lbl_push = ctk.CTkLabel(
            meta, text=f"↑ Push: {_fmt_date(p.get('last_push'))}",
            font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.lbl_push.pack(anchor="w")
        self.lbl_pull = ctk.CTkLabel(
            meta, text=f"↓ Pull: {_fmt_date(p.get('last_pull'))}",
            font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.lbl_pull.pack(anchor="w")

        # Botones
        btns = ctk.CTkFrame(bottom, fg_color="transparent")
        btns.pack(side="right")

        if not has_git:
            ctk.CTkLabel(
                btns, text="Sin repositorio Git", width=0,
                font=FONT_SMALL, text_color=C["text_muted"]
            ).pack(side="left", padx=(0, 10))
            ctk.CTkButton(
                btns, text="⚡  Inicializar repositorio", width=190, height=34,
                fg_color=C["accent_dim"], hover_color=C["accent"],
                text_color="#000000", corner_radius=6, font=FONT_LABEL_B,
                command=lambda: self.on_init(p) if self.on_init else None
            ).pack(side="left")
            return

        self.btn_pull = ctk.CTkButton(
            btns, text="⬇  Pull  (bajar)", width=148, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_LABEL_B,
            command=lambda: self.on_pull(p)
        )
        self.btn_pull.pack(side="left", padx=(0, 8))

        self.btn_push = ctk.CTkButton(
            btns, text="⬆  Push  (subir)", width=148, height=34,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=6, font=FONT_LABEL_B,
            command=lambda: self.on_push(p)
        )
        self.btn_push.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns, text="Log", width=60, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=lambda: self.on_log(p)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns, text="Limpiar hist.", width=110, height=34,
            fg_color="#2a1010", hover_color="#6b1a1a",
            text_color=C["red"], border_color="#6b1a1a", border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=lambda: self.on_purge(p)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns, text="Fantasmas", width=90, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["blue"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=lambda: self.on_ghost(p)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns, text="Cambios", width=80, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["yellow"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=lambda: self.on_changes(p)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns, text=".gitignore", width=88, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=lambda: self.on_gitignore(p)
        ).pack(side="left")

    def _make_launcher_btn(self, parent, p: dict):
        """Crea el botón de lanzador con icono o texto de fallback."""
        exe  = p.get("launcher_exe")
        icon = p.get("launcher_icon")

        has_exe = bool(exe and os.path.isfile(exe))

        def on_left(_event=None):
            if has_exe:
                self._launch_exe(exe)
            else:
                self._open_launcher_config()

        def on_right(_event=None):
            self._open_launcher_config()

        # Intentar cargar imagen
        img = None
        if icon and os.path.isfile(icon) and _PIL_AVAILABLE:
            try:
                pil_img = Image.open(icon).resize((44, 44), Image.LANCZOS)
                img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(44, 44))
            except Exception:
                img = None

        if img:
            btn = ctk.CTkButton(
                parent, image=img, text="", width=48, height=48,
                fg_color=C["border"], hover_color=C["card_hover"],
                corner_radius=8, cursor="hand2",
                command=on_left
            )
        elif has_exe:
            btn = ctk.CTkButton(
                parent, text="▶", width=48, height=48,
                fg_color=C["border"], hover_color=C["card_hover"],
                text_color=C["accent"], corner_radius=8,
                font=("Segoe UI", 20), cursor="hand2",
                command=on_left
            )
        else:
            btn = ctk.CTkButton(
                parent, text="⚙", width=48, height=48,
                fg_color=C["border"], hover_color=C["card_hover"],
                text_color=C["text_dim"], corner_radius=8,
                font=("Segoe UI", 20), cursor="hand2",
                command=on_left
            )

        btn.bind("<Button-3>", on_right)
        btn.bind("<Button-2>", on_right)

        if has_exe:
            tip = f"Clic: lanzar  —  {os.path.basename(exe)}\nClic derecho: cambiar configuración"
        else:
            tip = "Sin lanzador configurado\nClic para configurar"
        self._bind_tooltip(btn, tip)
        return btn

    def _launch_exe(self, exe: str):
        try:
            os.startfile(exe)
        except Exception as e:
            messagebox.showerror("Error al lanzar", str(e))

    def _open_launcher_config(self):
        if self.on_launcher:
            self.on_launcher(self.project)

    def refresh_launcher_btn(self):
        """Reconstruye el botón del lanzador tras guardar cambios."""
        # Recargar el proyecto desde disco
        projects = pm.load_projects()
        proj = next((p for p in projects if p["id"] == self.project["id"]), None)
        if proj:
            self.project = proj

        p = self.project
        parent = self._launcher_btn.master

        # Averiguar qué widget va justo antes en el pack order
        slaves = parent.pack_slaves()
        idx = slaves.index(self._launcher_btn)
        prev = slaves[idx - 1] if idx > 0 else None

        self._launcher_btn.destroy()
        self._launcher_btn = self._make_launcher_btn(parent, p)

        # Reposicionar en el mismo hueco usando 'after'
        if prev:
            self._launcher_btn.pack(side="left", padx=(0, 8), after=prev)
        else:
            self._launcher_btn.pack(side="left", padx=(0, 8), before=slaves[1] if len(slaves) > 1 else None)

    @staticmethod
    def _bind_tooltip(widget, text: str):
        """Tooltip minimalista con after / destroy."""
        tip = None

        def show(_e):
            nonlocal tip
            if tip:
                return
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            tk.Label(
                tip, text=text, background="#1c1f24", foreground="#e8eaf0",
                font=("Segoe UI", 11), padx=8, pady=4,
                relief="flat", bd=0
            ).pack()

        def hide(_e):
            nonlocal tip
            if tip:
                try:
                    tip.destroy()
                except Exception:
                    pass
                tip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def update_dates(self):
        """Recarga las fechas de push/pull desde el JSON sin recrear la tarjeta."""
        projects = pm.load_projects()
        proj = next((p for p in projects if p["id"] == self.project["id"]), None)
        if not proj:
            return
        self.project = proj
        try:
            self.lbl_push.configure(text=f"↑ Push: {_fmt_date(proj.get('last_push'))}")
            self.lbl_pull.configure(text=f"↓ Pull: {_fmt_date(proj.get('last_pull'))}")
        except AttributeError:
            pass  # sin repositorio git, las etiquetas no existen

    def _toggle(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.body.pack_forget()
            self.chevron.configure(text="▸")
        else:
            self.body.pack(fill="x")
            self.chevron.configure(text="▾")

    def _open_folder(self, path: str):
        import subprocess, sys
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def refresh_status(self):
        """Actualiza el estado en segundo plano."""
        has_git = git.has_git_repo(self.project["path"])
        if not has_git:
            self.status_label.configure(text="Sin repositorio Git", text_color=C["text_muted"])
            try:
                self.dot.configure(text_color=C["red"])
            except Exception:
                pass
            return

        if git.is_merging(self.project["path"]):
            self.status_label.configure(text="⚠ Conflicto de merge sin resolver", text_color=C["red"])
            try:
                self.dot.configure(text_color=C["red"])
            except Exception:
                pass
            return

        def _worker():
            try:
                status = git.get_status(self.project["path"])
                self._status = status
                label = _status_label(status)
                color = _status_color(status)
                dot_c = _dot_color(True, status)
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(
                    text=f"Error al calcular estado: {e}", text_color=C["red"]
                ))
                return
            self.after(0, lambda: (
                self.status_label.configure(text=label, text_color=color),
                self.dot.configure(text_color=dot_c),
            ))

        threading.Thread(target=_worker, daemon=True).start()

    def set_loading(self, loading: bool, btn: str = "both"):
        self._loading = loading
        state = "disabled" if loading else "normal"
        try:
            if btn in ("push", "both"):
                self.btn_push.configure(state=state)
            if btn in ("pull", "both"):
                self.btn_pull.configure(state=state)
        except AttributeError:
            pass
