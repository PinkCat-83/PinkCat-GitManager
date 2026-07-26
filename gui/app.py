"""
app.py
Interfaz gráfica principal del Git Manager.
Diseño: dark industrial con acentos en verde terminal.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import subprocess
from datetime import datetime

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from src import git_operations as git
from src import project_manager as pm

# ─── Tema ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Paleta personalizada
C = {
    "bg":         "#0e0f11",
    "panel":      "#16181c",
    "card":       "#1c1f24",
    "card_hover": "#22262d",
    "border":     "#2a2d35",
    "accent":     "#3de6a0",        # verde terminal
    "accent_dim": "#1f7a55",
    "red":        "#e05c5c",
    "yellow":     "#e0c05c",
    "blue":       "#5c9fe0",
    "text":       "#e8eaf0",
    "text_dim":   "#6b7280",
    "text_muted": "#3d4148",
}

FONT_TITLE  = ("Consolas", 26, "bold")
FONT_MONO   = ("Consolas", 14)
FONT_MONO_S = ("Consolas", 13)
FONT_LABEL  = ("Segoe UI", 14)
FONT_LABEL_B= ("Segoe UI", 14, "bold")
FONT_SMALL  = ("Segoe UI", 12)
FONT_BIG    = ("Segoe UI", 16, "bold")


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y  %H:%M")
    except Exception:
        return iso[:16]


def _status_color(status: dict) -> str:
    if not status.get("has_remote"):
        return C["text_dim"]
    if status.get("is_dirty") or status.get("ahead", 0) > 0:
        return C["yellow"]
    return C["accent"]


def _dot_color(has_git: bool, status: dict) -> str:
    """Color del punto luminoso en la cabecera de la tarjeta."""
    if not has_git:
        return C["red"]
    if status.get("is_dirty") or status.get("ahead", 0) > 0:
        return C["yellow"]
    if not status:
        return C["text_muted"]   # aún cargando
    return C["accent"]


def _status_label(status: dict) -> str:
    if not status.get("has_remote"):
        return "Sin remoto configurado"
    parts = []
    n = status.get("new_count", 0)
    m = status.get("modified_count", 0)
    d = status.get("deleted_count", 0)
    a = status.get("ahead", 0)
    if n:
        parts.append(f"{n} nuevo{'s' if n != 1 else ''}")
    if m:
        parts.append(f"{m} modificado{'s' if m != 1 else ''}")
    if d:
        parts.append(f"{d} borrado{'s' if d != 1 else ''}")
    if a:
        parts.append(f"{a} commit{'s' if a != 1 else ''} sin subir")
    if not parts:
        return "Al día  ✓"
    return "  ·  ".join(parts)



# Ventana base para todos los dialogos - garantiza foco en Windows
class BaseDialog(ctk.CTkToplevel):
    """Clase base. Garantiza que los diálogos aparezcan al frente en Windows."""
    def _grab_focus(self):
        try:
            self.attributes("-topmost", False)
            self.focus_force()
            self.grab_set()
        except Exception:
            pass


# ─── Ventana de log/resultado ─────────────────────────────────────────────────
class OutputWindow(BaseDialog):
    def __init__(self, master, title: str, content: str, success: bool):
        super().__init__(master)
        self.title(title)
        self.geometry("600x380")
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)

        color = C["accent"] if success else C["red"]
        icon  = "✓" if success else "✗"

        header = ctk.CTkLabel(
            self, text=f"{icon}  {title}",
            font=FONT_BIG, text_color=color
        )
        header.pack(padx=20, pady=(18, 8), anchor="w")

        box = ctk.CTkTextbox(
            self, font=FONT_MONO_S,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            corner_radius=8
        )
        box.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        box.insert("end", content)
        box.configure(state="disabled")

        ctk.CTkButton(
            self, text="Cerrar", command=self._close,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=34
        ).pack(pady=(0, 16))
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._on_close = None  # callback opcional

    def _close(self):
        cb = self._on_close
        self.destroy()
        if cb:
            cb()


# ─── Diálogo de commit ────────────────────────────────────────────────────────
class CommitDialog(BaseDialog):
    def __init__(self, master, project_name: str, callback):
        super().__init__(master)
        self.title("Commit & Push")
        self.geometry("480x230")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.callback = callback

        ctk.CTkLabel(
            self, text=f"Subir:  {project_name}",
            font=FONT_BIG, text_color=C["text"]
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            self, text="Mensaje del commit (vacío = fecha/hora automática):",
            font=FONT_LABEL, text_color=C["text_dim"]
        ).pack(padx=24, anchor="w")

        self.entry = ctk.CTkEntry(
            self, font=FONT_MONO,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            placeholder_text="Ej: Añadir funcionalidad X",
            height=38, corner_radius=6
        )
        self.entry.pack(padx=24, pady=(6, 16), fill="x")
        self.entry.bind("<Return>", lambda _: self._confirm())

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, fill="x")

        ctk.CTkButton(
            row, text="Cancelar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=36, width=110
        ).pack(side="left")

        ctk.CTkButton(
            row, text="⬆  Subir", command=self._confirm,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=6, height=36, font=FONT_LABEL_B
        ).pack(side="right")

    def _confirm(self):
        msg = self.entry.get().strip()
        self.destroy()
        self.callback(msg)


# ─── Diálogo de conflicto de merge ────────────────────────────────────────────
class MergeConflictDialog(BaseDialog):
    """Se muestra cuando el repo queda en conflicto de merge sin resolver."""
    def __init__(self, master, project: dict, conflicts: list[str], on_abort):
        super().__init__(master)
        self.title("Conflicto de merge")
        self.geometry("480x340")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)

        ctk.CTkLabel(
            self, text=f"⚠  Conflicto en «{project['name']}»",
            font=FONT_BIG, text_color=C["red"]
        ).pack(padx=24, pady=(20, 8), anchor="w")

        ctk.CTkLabel(
            self,
            text="Esta app no resuelve conflictos automáticamente.\nArchivos afectados:",
            font=FONT_LABEL, text_color=C["text_dim"], justify="left"
        ).pack(padx=24, anchor="w")

        box = ctk.CTkTextbox(
            self, font=FONT_MONO_S, height=110,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1, corner_radius=8
        )
        box.pack(fill="x", padx=24, pady=(6, 12))
        box.insert("end", "\n".join(conflicts) or "(no se detectaron archivos, revisa manualmente)")
        box.configure(state="disabled")

        ctk.CTkLabel(
            self,
            text="Resuélvelos manualmente (editor/terminal) y haz commit,\n"
                 "o aborta el merge para volver al estado anterior al Pull.",
            font=FONT_SMALL, text_color=C["text_dim"], justify="left"
        ).pack(padx=24, anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, pady=(16, 20), fill="x")

        ctk.CTkButton(
            row, text="Cerrar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=36, width=110
        ).pack(side="left")

        ctk.CTkButton(
            row, text="⏪  Abortar merge", command=lambda: (self.destroy(), on_abort()),
            fg_color="#6b1a1a", hover_color=C["red"],
            text_color="#ffffff", corner_radius=6, height=36, font=FONT_LABEL_B
        ).pack(side="right")


# ─── Diálogo de inicialización de repositorio ────────────────────────────────
class InitRepoDialog(BaseDialog):
    """Pide (opcionalmente) la URL del remoto antes de hacer git init."""
    def __init__(self, master, project_name: str, callback):
        super().__init__(master)
        self.title("Inicializar repositorio")
        self.geometry("500x250")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.callback = callback

        ctk.CTkLabel(
            self, text=f"Inicializar:  {project_name}",
            font=FONT_BIG, text_color=C["text"]
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            self, text="URL del remoto 'origin' (opcional, puedes dejarlo vacío):",
            font=FONT_LABEL, text_color=C["text_dim"]
        ).pack(padx=24, anchor="w")

        self.entry = ctk.CTkEntry(
            self, font=FONT_MONO,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            placeholder_text="https://github.com/usuario/repo.git",
            height=38, corner_radius=6
        )
        self.entry.pack(padx=24, pady=(6, 4), fill="x")
        self.entry.bind("<Return>", lambda _: self._confirm())

        ctk.CTkLabel(
            self, text="Sin remoto, el repositorio queda solo en local\n"
                       "(podrás configurarlo más tarde).",
            font=FONT_SMALL, text_color=C["text_muted"], justify="left"
        ).pack(padx=24, pady=(0, 12), anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, fill="x")

        ctk.CTkButton(
            row, text="Cancelar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=36, width=110
        ).pack(side="left")

        ctk.CTkButton(
            row, text="⚡  Inicializar", command=self._confirm,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=6, height=36, font=FONT_LABEL_B
        ).pack(side="right")

    def _confirm(self):
        url = self.entry.get().strip()
        self.destroy()
        self.callback(url)


# ─── Diálogo de configuración del lanzador ───────────────────────────────────
class LauncherDialog(BaseDialog):
    """Permite elegir el ejecutable y el icono del lanzador de un proyecto."""
    def __init__(self, master, project: dict, callback):
        super().__init__(master)
        self.title("Configurar lanzador")
        self.geometry("520x300")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.callback = callback
        self.project  = project

        self._exe_var  = tk.StringVar(value=project.get("launcher_exe") or "")
        self._icon_var = tk.StringVar(value=project.get("launcher_icon") or "")

        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text=f"Lanzador  —  {self.project['name']}",
            font=FONT_BIG, text_color=C["text"]
        ).pack(padx=24, pady=(20, 14), anchor="w")

        # Ejecutable
        ctk.CTkLabel(
            self, text="Archivo a ejecutar (.exe, .bat, .pyw, ...):",
            font=FONT_LABEL, text_color=C["text_dim"]
        ).pack(padx=24, anchor="w")

        row_exe = ctk.CTkFrame(self, fg_color="transparent")
        row_exe.pack(fill="x", padx=24, pady=(4, 12))

        ctk.CTkEntry(
            row_exe, textvariable=self._exe_var,
            font=FONT_MONO_S, fg_color=C["panel"],
            text_color=C["text"], border_color=C["border"],
            border_width=1, height=34, corner_radius=6
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row_exe, text="Examinar", width=90, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=self._browse_exe
        ).pack(side="left")

        # Icono
        ctk.CTkLabel(
            self, text="Imagen del icono (.png / .ico / .jpg):",
            font=FONT_LABEL, text_color=C["text_dim"]
        ).pack(padx=24, anchor="w")

        row_icon = ctk.CTkFrame(self, fg_color="transparent")
        row_icon.pack(fill="x", padx=24, pady=(4, 16))

        ctk.CTkEntry(
            row_icon, textvariable=self._icon_var,
            font=FONT_MONO_S, fg_color=C["panel"],
            text_color=C["text"], border_color=C["border"],
            border_width=1, height=34, corner_radius=6
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row_icon, text="Examinar", width=90, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=self._browse_icon
        ).pack(side="left")

        # Botones
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24)

        ctk.CTkButton(
            btn_row, text="Cancelar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=36, width=110
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="Limpiar", command=self._clear,
            fg_color="transparent", hover_color=C["card_hover"],
            text_color=C["text_muted"], corner_radius=6, height=36, width=90
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="Guardar", command=self._confirm,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=6, height=36, font=FONT_LABEL_B
        ).pack(side="right")

    def _browse_exe(self):
        path = filedialog.askopenfilename(
            title="Selecciona el archivo a ejecutar",
            filetypes=[("Todos los archivos", "*.*")]
        )
        if path:
            self._exe_var.set(path)

    def _browse_icon(self):
        path = filedialog.askopenfilename(
            title="Selecciona el icono",
            filetypes=[("Imágenes", "*.png *.ico *.jpg *.jpeg"), ("Todos", "*.*")]
        )
        if path:
            self._icon_var.set(path)

    def _clear(self):
        self._exe_var.set("")
        self._icon_var.set("")

    def _confirm(self):
        exe  = self._exe_var.get().strip() or None
        icon = self._icon_var.get().strip() or None
        self.destroy()
        self.callback(exe, icon)


# ─── Diálogo de purga de historial ───────────────────────────────────────────
class PurgeDialog(BaseDialog):
    """
    Ventana de advertencia + selección para eliminar un archivo o carpeta
    del historial completo de Git.
    """
    def __init__(self, master, project: dict, callback):
        super().__init__(master)
        self.title("Limpiar historial de Git")
        self.geometry("620x640")
        self.resizable(False, True)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.callback = callback
        self.project  = project
        self._mode    = tk.StringVar(value="file")

        self._build()

    def _build(self):
        # Cabecera de peligro
        hdr = ctk.CTkFrame(self, fg_color="#2a1010", corner_radius=8)
        hdr.pack(fill="x", padx=20, pady=(18, 0))

        ctk.CTkLabel(
            hdr, text="OPERACION DESTRUCTIVA E IRREVERSIBLE",
            font=FONT_LABEL_B, text_color=C["red"]
        ).pack(padx=16, pady=(12, 4), anchor="w")

        ctk.CTkLabel(
            hdr,
            text=(
                "Esta funcion reescribe TODO el historial del repositorio.\n"
                "El archivo o carpeta elegido desaparecera de cada commit que haya existido."
            ),
            font=FONT_SMALL, text_color="#e8a0a0", justify="left"
        ).pack(padx=16, pady=(0, 12), anchor="w")

        ctk.CTkLabel(
            self, text="Cuando tiene sentido usar esto:",
            font=FONT_LABEL_B, text_color=C["yellow"]
        ).pack(padx=20, pady=(14, 4), anchor="w")

        casos = (
            "OK  Subiste por error una contrasena, API key o dato sensible.\n"
            "OK  Metiste un archivo enorme que no deberia estar en el repo.\n"
            "OK  Quieres borrar una carpeta de cache o build de todo el historial.\n"
            "OK  Eres el unico participante del repo (tu caso: perfecto para esto)."
        )
        ctk.CTkLabel(
            self, text=casos,
            font=FONT_SMALL, text_color=C["text"], justify="left"
        ).pack(padx=28, anchor="w")

        ctk.CTkLabel(
            self, text="Cuando NO deberias usarlo:",
            font=FONT_LABEL_B, text_color=C["red"]
        ).pack(padx=20, pady=(12, 4), anchor="w")

        no_casos = (
            "NO  Si hay mas personas colaborando: sus clones quedaran desincronizados.\n"
            "NO  Si no tienes claro que estas borrando.\n"
            "NO  Como sustituto de un .gitignore (mejor prevenir que curar)."
        )
        ctk.CTkLabel(
            self, text=no_casos,
            font=FONT_SMALL, text_color="#e8a0a0", justify="left"
        ).pack(padx=28, anchor="w")

        ctk.CTkLabel(
            self, text="Que hacer despues:",
            font=FONT_LABEL_B, text_color=C["blue"]
        ).pack(padx=20, pady=(12, 4), anchor="w")

        post = (
            "Tras limpiar el historial local, haz un push forzado\n"
            "para que GitHub tambien lo olvide:\n\n"
            "    git push origin --force --all\n\n"
            "La ventana de resultado te lo recordara."
        )
        ctk.CTkLabel(
            self, text=post,
            font=FONT_MONO_S, text_color=C["text_dim"], justify="left"
        ).pack(padx=28, anchor="w")

        ctk.CTkFrame(self, fg_color=C["border"], height=1).pack(fill="x", padx=20, pady=(14, 10))

        ctk.CTkLabel(
            self, text="Que quieres eliminar del historial?",
            font=FONT_LABEL_B, text_color=C["text"]
        ).pack(padx=20, anchor="w")

        radio_row = ctk.CTkFrame(self, fg_color="transparent")
        radio_row.pack(padx=28, pady=(6, 0), anchor="w")

        ctk.CTkRadioButton(
            radio_row, text="Un archivo concreto", variable=self._mode,
            value="file", font=FONT_LABEL, text_color=C["text"],
            fg_color=C["accent"], border_color=C["border"],
            command=self._update_hint
        ).pack(side="left", padx=(0, 24))

        ctk.CTkRadioButton(
            radio_row, text="Una carpeta entera", variable=self._mode,
            value="folder", font=FONT_LABEL, text_color=C["text"],
            fg_color=C["accent"], border_color=C["border"],
            command=self._update_hint
        ).pack(side="left")

        self.hint_label = ctk.CTkLabel(
            self, text="Ruta relativa al repo  (ej: secrets/api_key.txt)",
            font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.hint_label.pack(padx=20, pady=(8, 2), anchor="w")

        entry_row = ctk.CTkFrame(self, fg_color="transparent")
        entry_row.pack(fill="x", padx=20, pady=(0, 4))

        self.path_entry = ctk.CTkEntry(
            entry_row, font=FONT_MONO,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            placeholder_text="carpeta/archivo.ext",
            height=38, corner_radius=6
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            entry_row, text="Examinar", width=90, height=38,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=self._browse
        ).pack(side="left")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(12, 16))

        ctk.CTkButton(
            btn_row, text="Cancelar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=38, width=120
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="Limpiar historial", command=self._confirm,
            fg_color="#6b1a1a", hover_color=C["red"],
            text_color=C["text"], corner_radius=6, height=38, font=FONT_LABEL_B
        ).pack(side="right")

    def _update_hint(self):
        if self._mode.get() == "file":
            self.hint_label.configure(text="Ruta relativa al repo  (ej: secrets/api_key.txt)")
        else:
            self.hint_label.configure(text="Ruta relativa al repo  (ej: build/  o  node_modules)")

    def _browse(self):
        repo = self.project["path"]
        if self._mode.get() == "file":
            chosen = filedialog.askopenfilename(initialdir=repo, title="Selecciona el archivo")
        else:
            chosen = filedialog.askdirectory(initialdir=repo, title="Selecciona la carpeta")
        if not chosen:
            return
        try:
            rel = os.path.relpath(chosen, repo).replace("\\", "/")
        except ValueError:
            rel = chosen
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, rel)

    def _confirm(self):
        target = self.path_entry.get().strip().strip("/")
        if not target:
            messagebox.showwarning("Falta la ruta", "Introduce o selecciona el archivo/carpeta.", parent=self)
            return
        is_folder = self._mode.get() == "folder"
        tipo = "carpeta" if is_folder else "archivo"
        if not messagebox.askyesno(
            "Confirmar limpieza",
            f"Seguro que quieres eliminar el {tipo}:\n\n  {target}\n\n"
            f"...de TODO el historial?\n\nEsta accion NO se puede deshacer.",
            parent=self
        ):
            return
        self.destroy()
        self.callback(target, is_folder)

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
            status = git.get_status(self.project["path"])
            self._status = status
            label = _status_label(status)
            color = _status_color(status)
            dot_c = _dot_color(True, status)
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


# ─── Ventana de Log ───────────────────────────────────────────────────────────
class LogWindow(BaseDialog):
    def __init__(self, master, project: dict):
        super().__init__(master)
        self.title(f"Log — {project['name']}")
        self.geometry("680x460")
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)

        ctk.CTkLabel(
            self, text=f"Historial de commits  —  {project['name']}",
            font=FONT_BIG, text_color=C["text"]
        ).pack(padx=20, pady=(16, 8), anchor="w")

        box = ctk.CTkTextbox(
            self, font=FONT_MONO_S,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            corner_radius=8
        )
        box.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        commits = git.get_log(project["path"], n=20)
        if not commits:
            box.insert("end", "No hay commits o no se pudo leer el log.")
        else:
            for c in commits:
                box.insert("end", f"  {c['hash']}  ", "hash")
                box.insert("end", f"{c['date']}  ", "date")
                box.insert("end", f"{c['message']}\n", "msg")

        box.tag_config("hash", foreground=C["accent"])
        box.tag_config("date", foreground=C["text_dim"])
        box.tag_config("msg",  foreground=C["text"])
        box.configure(state="disabled")

        ctk.CTkButton(
            self, text="Cerrar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=34
        ).pack(pady=(0, 16))



# ─── Ventana de Archivos Fantasma ────────────────────────────────────────────
class GhostFilesWindow(BaseDialog):
    """
    Muestra todos los archivos que existieron en el historial
    pero ya no están en la rama actual. Permite recuperarlos.
    """
    def __init__(self, master, project: dict):
        super().__init__(master)
        self.title(f"Archivos borrados  —  {project['name']}")
        self.geometry("1340x560")
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.project = project
        self._files  = []

        self._build()
        self._load()

    def _build(self):
        # Cabecera
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            hdr, text="Archivos fantasma",
            font=FONT_BIG, text_color=C["text"]
        ).pack(side="left")

        self.count_label = ctk.CTkLabel(
            hdr, text="Buscando...",
            font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.count_label.pack(side="left", padx=(12, 0))

        ctk.CTkButton(
            hdr, text="↻ Recargar", width=90, height=30,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_SMALL,
            command=self._load
        ).pack(side="right")

        ctk.CTkLabel(
            self,
            text="Estos archivos ya no existen en la rama actual, pero viven en el historial de Git y se pueden recuperar.",
            font=FONT_SMALL, text_color=C["text_dim"], wraplength=740, justify="left"
        ).pack(padx=20, pady=(4, 10), anchor="w")

        # Cabecera de tabla
        cols = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=6, height=32)
        cols.pack(fill="x", padx=20, pady=(0, 2))
        cols.pack_propagate(False)

        ctk.CTkLabel(cols, text="Ruta del archivo", font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="w", width=700).pack(side="left", padx=(12,0))
        ctk.CTkLabel(cols, text="Borrado en", font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="w", width=130).pack(side="left", padx=(8,0))
        ctk.CTkLabel(cols, text="Commit", font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="w", width=60).pack(side="left", padx=(8,0))
        ctk.CTkLabel(cols, text="Mensaje", font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="w").pack(side="left", padx=(8,0), fill="x", expand=True)

        # Lista scrollable
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent_dim"],
            corner_radius=0
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        # Pie
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkButton(
            footer, text="Cerrar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=36, width=120
        ).pack(side="left")

        self.btn_apply = ctk.CTkButton(
            footer, text="Dejar de rastrear seleccionados",
            command=self._apply_untrack,
            fg_color="#2a1010", hover_color="#6b1a1a",
            text_color=C["red"], border_color="#6b1a1a", border_width=1,
            corner_radius=6, height=36, font=FONT_LABEL_B, state="disabled"
        )
        self.btn_apply.pack(side="right")

        self.sel_count_label = ctk.CTkLabel(
            footer, text="", font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.sel_count_label.pack(side="right", padx=(0, 12))

    def _load(self):
        # Limpiar lista
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.count_label.configure(text="Buscando...", text_color=C["text_dim"])

        def _worker():
            files = git.get_deleted_files(self.project["path"])
            self._files = files
            self.after(0, lambda: self._populate(files))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _populate(self, files: list):
        if not files:
            self.count_label.configure(text="No se encontraron archivos borrados.", text_color=C["accent"])
            ctk.CTkLabel(
                self.list_frame,
                text="El historial no contiene archivos borrados\n(o todos siguen existiendo en la rama actual).",
                font=FONT_LABEL, text_color=C["text_muted"]
            ).pack(pady=40)
            return

        self.count_label.configure(
            text=f"{len(files)} archivo{'s' if len(files) != 1 else ''} encontrado{'s' if len(files) != 1 else ''}",
            text_color=C["yellow"]
        )

        for i, f in enumerate(files):
            row_color = C["card"] if i % 2 == 0 else C["panel"]
            row = ctk.CTkFrame(self.list_frame, fg_color=row_color, corner_radius=6, height=40)
            row.pack(fill="x", pady=(0, 2))
            row.pack_propagate(False)

            # Ruta
            ctk.CTkLabel(
                row, text=f["path"],
                font=FONT_MONO_S, text_color=C["text"], anchor="w", width=700,
                wraplength=700
            ).pack(side="left", padx=(10, 0))

            # Fecha borrado
            ctk.CTkLabel(
                row, text=f["date_delete"],
                font=FONT_SMALL, text_color=C["text_dim"], anchor="w", width=130
            ).pack(side="left", padx=(8, 0))

            # Hash commit
            ctk.CTkLabel(
                row, text=f["hash_delete"],
                font=FONT_MONO_S, text_color=C["accent_dim"], anchor="w", width=60
            ).pack(side="left", padx=(8, 0))

            # Mensaje commit (truncado)
            msg = f["commit_msg"][:40] + "..." if len(f["commit_msg"]) > 40 else f["commit_msg"]
            ctk.CTkLabel(
                row, text=msg,
                font=FONT_SMALL, text_color=C["text_dim"], anchor="w"
            ).pack(side="left", padx=(8, 0), fill="x", expand=True)

            # Botón recuperar
            fdata = f  # captura local
            ctk.CTkButton(
                row, text="Recuperar", width=88, height=28,
                fg_color=C["accent_dim"], hover_color=C["accent"],
                text_color="#000000", corner_radius=5, font=FONT_SMALL,
                command=lambda fd=fdata: self._recover(fd)
            ).pack(side="right", padx=(0, 8))

    def _recover(self, fdata: dict):
        if not messagebox.askyesno(
            "Recuperar archivo",
            f"Restaurar el archivo:\n\n  {fdata['path']}\n\n"
            "El archivo volverá a tu carpeta local.\n"
            "Después podrás hacer Push para subirlo a GitHub.",
            parent=self
        ):
            return

        ok, msg = git.restore_deleted_file(
            self.project["path"], fdata["path"], fdata["hash_full"]
        )
        icon = "✓" if ok else "✗"
        color = C["accent"] if ok else C["red"]

        win = ctk.CTkToplevel(self)
        win.title("Recuperar archivo")
        win.geometry("500x260")
        win.configure(fg_color=C["bg"])
        win.transient(self)
        win.lift()
        win.attributes("-topmost", True)
        win.after(100, lambda: (win.attributes("-topmost", False), win.focus_force(), win.grab_set()))

        ctk.CTkLabel(win, text=f"{icon}  {'Archivo recuperado' if ok else 'Error al recuperar'}",
                     font=FONT_BIG, text_color=color).pack(padx=20, pady=(18, 8), anchor="w")

        box = ctk.CTkTextbox(win, font=FONT_MONO_S,
                             fg_color=C["panel"], text_color=C["text"],
                             border_color=C["border"], border_width=1, corner_radius=8)
        box.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        box.insert("end", msg)
        box.configure(state="disabled")

        ctk.CTkButton(win, text="Cerrar", command=win.destroy,
                      fg_color=C["border"], hover_color=C["card_hover"],
                      text_color=C["text"], corner_radius=6, height=34).pack(pady=(0, 14))

        if ok:
            self._load()  # Recargar la lista por si algo cambió



# ─── Ventana de cambios pendientes ───────────────────────────────────────────
class ChangesWindow(BaseDialog):
    """
    Muestra qué archivos tienen cambios respecto al último commit:
    nuevos, modificados, borrados y en stage.
    """
    def __init__(self, master, project: dict):
        super().__init__(master)
        self.title(f"Cambios pendientes  —  {project['name']}")
        self.geometry("920x560")
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.project = project
        self._build()
        self._load()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            hdr, text="Cambios pendientes de commit/push",
            font=FONT_BIG, text_color=C["text"]
        ).pack(side="left")

        ctk.CTkButton(
            hdr, text="↻", width=36, height=30,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_BIG,
            command=self._load
        ).pack(side="right")

        self.summary = ctk.CTkLabel(
            self, text="Calculando...",
            font=FONT_SMALL, text_color=C["text_dim"], anchor="w"
        )
        self.summary.pack(padx=20, pady=(4, 10), anchor="w")

        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent_dim"],
            corner_radius=0
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        ctk.CTkButton(
            self, text="Cerrar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=34
        ).pack(pady=(0, 14))

    def _load(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.summary.configure(text="Calculando...", text_color=C["text_dim"])

        import threading
        def _worker():
            from src import git_operations as git
            status = git.get_status(self.project["path"])
            self.after(0, lambda: self._populate(status))
        threading.Thread(target=_worker, daemon=True).start()

    def _populate(self, status: dict):
        groups = [
            ("Nuevos  (sin seguimiento)",  status.get("new_files", []),  "#5ce05c"),
            ("Modificados",                status.get("modified",   []),  C["yellow"]),
            ("En stage (listos para commit)", status.get("staged",  []),  C["blue"]),
            ("Borrados localmente",         status.get("deleted",   []),  C["red"]),
        ]

        total = status.get("total_changes", 0)
        ahead = status.get("ahead", 0)

        parts = []
        if total:
            parts.append(f"{total} archivo{'s' if total != 1 else ''} con cambios")
        if ahead:
            parts.append(f"{ahead} commit{'s' if ahead != 1 else ''} sin subir")
        if not parts:
            self.summary.configure(text="Sin cambios pendientes. Todo al día ✓", text_color=C["accent"])
            ctk.CTkLabel(
                self.list_frame,
                text="No hay nada pendiente de subir a GitHub.",
                font=FONT_LABEL, text_color=C["text_muted"]
            ).pack(pady=40)
            return

        self.summary.configure(text="  ·  ".join(parts), text_color=C["yellow"])

        for group_name, files, color in groups:
            if not files:
                continue

            # Cabecera de grupo
            g_hdr = ctk.CTkFrame(self.list_frame, fg_color=C["panel"], corner_radius=6, height=28)
            g_hdr.pack(fill="x", pady=(8, 2))
            g_hdr.pack_propagate(False)
            ctk.CTkLabel(
                g_hdr,
                text=f"  {group_name}  ({len(files)})",
                font=FONT_SMALL, text_color=color, anchor="w"
            ).pack(fill="x", padx=8, pady=4)

            # Filas de archivos
            for i, filepath in enumerate(files):
                row_color = C["card"] if i % 2 == 0 else C["panel"]
                row = ctk.CTkFrame(self.list_frame, fg_color=row_color, corner_radius=4, height=30)
                row.pack(fill="x", pady=(0, 1))
                row.pack_propagate(False)
                ctk.CTkLabel(
                    row, text=f"  {filepath}",
                    font=FONT_MONO_S, text_color=C["text"], anchor="w",
                    wraplength=860
                ).pack(fill="x", padx=8, pady=4)

        # Commits sin subir
        if ahead:
            g_hdr2 = ctk.CTkFrame(self.list_frame, fg_color=C["panel"], corner_radius=6, height=28)
            g_hdr2.pack(fill="x", pady=(8, 2))
            g_hdr2.pack_propagate(False)
            ctk.CTkLabel(
                g_hdr2,
                text=f"  Commits sin subir  ({ahead})",
                font=FONT_SMALL, text_color=C["accent"], anchor="w"
            ).pack(fill="x", padx=8, pady=4)

            from src import git_operations as git
            commits = git.get_log(self.project["path"], n=ahead)
            for i, c in enumerate(commits):
                row_color = C["card"] if i % 2 == 0 else C["panel"]
                row = ctk.CTkFrame(self.list_frame, fg_color=row_color, corner_radius=4, height=30)
                row.pack(fill="x", pady=(0, 1))
                row.pack_propagate(False)
                ctk.CTkLabel(
                    row,
                    text=f"  {c['hash']}  {c['date']}  {c['message']}",
                    font=FONT_MONO_S, text_color=C["text"], anchor="w"
                ).pack(fill="x", padx=8, pady=4)


# ─── Ventana de .gitignore ────────────────────────────────────────────────────
class GitignoreWindow(BaseDialog):
    """
    Muestra el contenido del .gitignore y detecta archivos en GitHub
    que coincidan con alguna de sus reglas (subidos por error).
    """
    def __init__(self, master, project: dict):
        super().__init__(master)
        self.title(f".gitignore  —  {project['name']}")
        self.geometry("980x620")
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.project = project
        self._untracked = set()  # archivos ya procesados en esta sesión
        self._build()
        self._load()

    def _build(self):
        # Cabecera
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            hdr, text="Revisor de .gitignore",
            font=FONT_BIG, text_color=C["text"]
        ).pack(side="left")

        ctk.CTkButton(
            hdr, text="↻", width=36, height=30,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_BIG, command=self._load
        ).pack(side="right")

        ctk.CTkLabel(
            self,
            text="Archivos que están en GitHub pero coinciden con una regla del .gitignore — podrían haberse subido por error.",
            font=FONT_SMALL, text_color=C["text_dim"], wraplength=940, justify="left"
        ).pack(padx=20, pady=(4, 10), anchor="w")

        # Dos paneles lado a lado
        panels = ctk.CTkFrame(self, fg_color="transparent")
        panels.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=2)
        panels.rowconfigure(0, weight=1)

        # ── Panel izquierdo: reglas del .gitignore ──
        left = ctk.CTkFrame(panels, fg_color=C["panel"], corner_radius=8, border_color=C["border"], border_width=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(
            left, text="Reglas en .gitignore",
            font=FONT_LABEL_B, text_color=C["text_dim"]
        ).pack(padx=12, pady=(10, 6), anchor="w")

        self.rules_box = ctk.CTkTextbox(
            left, font=FONT_MONO_S,
            fg_color=C["card"], text_color=C["text_dim"],
            border_width=0, corner_radius=6
        )
        self.rules_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # ── Panel derecho: coincidencias ──
        right = ctk.CTkFrame(panels, fg_color=C["panel"], corner_radius=8, border_color=C["border"], border_width=1)
        right.grid(row=0, column=1, sticky="nsew")

        right_hdr = ctk.CTkFrame(right, fg_color="transparent")
        right_hdr.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(
            right_hdr, text="Archivos en GitHub que coinciden",
            font=FONT_LABEL_B, text_color=C["text"]
        ).pack(side="left")

        self.match_count = ctk.CTkLabel(
            right_hdr, text="",
            font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.match_count.pack(side="left", padx=(10, 0))

        self.matches_frame = ctk.CTkScrollableFrame(
            right, fg_color=C["card"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent_dim"],
            corner_radius=6
        )
        self.matches_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Pie
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkButton(
            footer, text="Cerrar", command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=6, height=36, width=120
        ).pack(side="left")

        self.btn_apply = ctk.CTkButton(
            footer, text="Dejar de rastrear seleccionados",
            command=self._apply_untrack,
            fg_color="#2a1010", hover_color="#6b1a1a",
            text_color=C["red"], border_color="#6b1a1a", border_width=1,
            corner_radius=6, height=36, font=FONT_LABEL_B, state="disabled"
        )
        self.btn_apply.pack(side="right")

        self.sel_count_label = ctk.CTkLabel(
            footer, text="", font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.sel_count_label.pack(side="right", padx=(0, 12))

    def _load(self):
        self.rules_box.configure(state="normal")
        self.rules_box.delete("1.0", "end")
        self.rules_box.insert("end", "Cargando...")
        self.rules_box.configure(state="disabled")
        for w in self.matches_frame.winfo_children():
            w.destroy()
        self.match_count.configure(text="")
        # NO reseteamos self._untracked — queremos conservar el estado visual

        import threading
        def _worker():
            from src import git_operations as git
            data = git.get_gitignore_data(self.project["path"])
            self.after(0, lambda: self._populate(data))
        threading.Thread(target=_worker, daemon=True).start()

    def _populate(self, data: dict):
        self.rules_box.configure(state="normal")
        self.rules_box.delete("1.0", "end")
        self._checkboxes = {}   # filepath -> BooleanVar

        if not data["gitignore_exists"]:
            self.rules_box.insert("end", "No se encontró .gitignore\nen este repositorio.")
            self.rules_box.configure(state="disabled")
            self.match_count.configure(text="Sin .gitignore", text_color=C["text_muted"])
            return

        if not data["rules"]:
            self.rules_box.insert("end", "El .gitignore está vacío.")
        else:
            for rule in data["rules"]:
                self.rules_box.insert("end", f"  {rule}\n")
        self.rules_box.configure(state="disabled")

        matches = data["tracked"]
        if not matches:
            self.match_count.configure(text="Ninguna coincidencia  ✓", text_color=C["accent"])
            ctk.CTkLabel(
                self.matches_frame,
                text="No se encontró ningún archivo en GitHub\nque coincida con las reglas del .gitignore.\n\n¡Todo correcto!",
                font=FONT_LABEL, text_color=C["text_muted"], justify="center"
            ).pack(pady=40)
            self.btn_apply.configure(state="disabled")
            self.sel_count_label.configure(text="")
            return

        self.match_count.configure(
            text=f"{len(matches)} archivo{'s' if len(matches) != 1 else ''} sospechoso{'s' if len(matches) != 1 else ''}",
            text_color=C["red"]
        )

        # Cabecera con "marcar todos"
        col_hdr = ctk.CTkFrame(self.matches_frame, fg_color=C["panel"], corner_radius=4, height=28)
        col_hdr.pack(fill="x", pady=(0, 4))
        col_hdr.pack_propagate(False)

        self._all_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            col_hdr, text="  Archivo en GitHub", variable=self._all_var,
            font=FONT_SMALL, text_color=C["text_dim"],
            fg_color=C["accent_dim"], hover_color=C["accent"],
            border_color=C["border"], checkmark_color="#000",
            command=self._toggle_all, width=20, height=20
        ).pack(side="left", padx=(8, 0), pady=4)
        ctk.CTkLabel(col_hdr, text="Regla que coincide  ", font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="e", width=200).pack(side="right", padx=8)

        for i, m in enumerate(matches):
            row_color = C["card"] if i % 2 == 0 else "#1a1a20"
            row = ctk.CTkFrame(self.matches_frame, fg_color=row_color, corner_radius=4, height=32)
            row.pack(fill="x", pady=(0, 2))
            row.pack_propagate(False)

            var = tk.BooleanVar(value=False)
            self._checkboxes[m["file"]] = var

            ctk.CTkLabel(
                row, text=f"{m['rule']}  ",
                font=FONT_MONO_S, text_color=C["red"], anchor="e", width=200
            ).pack(side="right", padx=8)

            already_done = m["file"] in self._untracked
            if already_done:
                # Fila ya procesada: tick verde + texto apagado
                ctk.CTkLabel(
                    row, text="  ✓", font=FONT_MONO_S,
                    text_color=C["accent"], width=28
                ).pack(side="left", padx=(8, 0))
                ctk.CTkLabel(
                    row, text=f"  {m['file']}  (pendiente de push)",
                    font=FONT_MONO_S, text_color=C["text_muted"]
                ).pack(side="left", fill="x", expand=True)
                # Deshabilitar checkbox de esta fila para que no cuente
                var.set(False)
            else:
                ctk.CTkCheckBox(
                    row, text=f"  {m['file']}", variable=var,
                    font=FONT_MONO_S, text_color=C["yellow"],
                    fg_color=C["accent_dim"], hover_color=C["accent"],
                    border_color=C["border"], checkmark_color="#000",
                    command=self._update_apply_btn, width=20, height=20
                ).pack(side="left", padx=(8, 0), fill="x", expand=True)

    def _toggle_all(self):
        val = self._all_var.get()
        for var in self._checkboxes.values():
            var.set(val)
        self._update_apply_btn()

    def _update_apply_btn(self):
        selected = [f for f, v in self._checkboxes.items() if v.get()]
        n = len(selected)
        if n:
            self.btn_apply.configure(state="normal")
            self.sel_count_label.configure(
                text=f"{n} seleccionado{'s' if n != 1 else ''}",
                text_color=C["yellow"]
            )
        else:
            self.btn_apply.configure(state="disabled")
            self.sel_count_label.configure(text="")

    def _apply_untrack(self):
        selected = [f for f, v in self._checkboxes.items() if v.get()]
        if not selected:
            return
        lista = "\n".join(f"  • {f}" for f in selected)
        if not messagebox.askyesno(
            "Dejar de rastrear",
            f"¿Quitar del seguimiento de Git los siguientes archivos?\n\n{lista}\n\n"
            "Seguirán en tu carpeta local pero Git dejará de incluirlos\n"
            "en futuros commits.\n\n"
            "Después haz un Push para que desaparezcan de GitHub.",
            parent=self
        ):
            return

        from src import git_operations as git
        errors = []
        done = []
        for filepath in selected:
            # --ignore-unmatch evita error si el archivo ya no está en el índice
            code, out, err = git._run(
                ["git", "rm", "--cached", "-r", "--ignore-unmatch", filepath],
                self.project["path"]
            )
            if code == 0:
                done.append(filepath)
            else:
                errors.append(f"{filepath}: {err or out}")

        lines = []
        if done:
            lines.append(f"Eliminados del seguimiento ({len(done)}):")
            lines += [f"  ✓ {f}" for f in done]
        if errors:
            lines.append(f"\nErrores ({len(errors)}):")
            lines += [f"  ✗ {e}" for e in errors]
        if done:
            lines.append("\nHaz un Push para que los cambios se reflejen en GitHub.")

        ok = len(done) > 0
        for f in done:
            self._untracked.add(f)

        def _after_close():
            if hasattr(self, "_all_var"):
                self._all_var.set(False)
            self._checkboxes = {}
            self.btn_apply.configure(state="disabled")
            self.sel_count_label.configure(text="")
            self._load()

        win = OutputWindow(self, "Dejar de rastrear", "\n".join(lines), ok)
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), _after_close()))
        # También cuando se cierra con el botón Cerrar interno
        win._on_close = _after_close


# ─── App principal ────────────────────────────────────────────────────────────
class GitManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Git Manager")
        self.geometry("1150x760")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])

        self._cards: dict[str, ProjectCard] = {}
        self._build_ui()
        self._load_projects()

    # ── Layout ──
    def _build_ui(self):
        # Cabecera
        header = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="◈  GIT MANAGER",
            font=FONT_TITLE, text_color=C["accent"]
        ).pack(side="left", padx=24, pady=0)

        ctk.CTkButton(
            header, text="+ Añadir proyecto",
            command=self._add_project,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=6,
            height=36, font=FONT_LABEL_B
        ).pack(side="right", padx=24)

        ctk.CTkButton(
            header, text="↻ Actualizar todo",
            command=self._refresh_all,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=6, height=36, font=FONT_SMALL
        ).pack(side="right", padx=(0, 8))

        self.json_label = ctk.CTkButton(
            header, text=self._short_json_label(),
            command=self._change_json,
            fg_color="transparent", hover_color=C["card_hover"],
            text_color=C["text_muted"], border_color=C["border"], border_width=1,
            corner_radius=6, height=36, font=FONT_SMALL, anchor="w"
        )
        self.json_label.pack(side="right", padx=(0, 8))

        # Área scrollable
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent_dim"],
            corner_radius=0
        )
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # Mensaje vacío
        self.empty_label = ctk.CTkLabel(
            self.scroll,
            text="No hay proyectos.\nPulsa  + Añadir proyecto  para empezar.",
            font=FONT_LABEL, text_color=C["text_muted"]
        )

        # Barra de estado
        self.statusbar = ctk.CTkLabel(
            self, text="Listo",
            font=FONT_SMALL, text_color=C["text_dim"],
            fg_color=C["panel"], anchor="w", height=24
        )
        self.statusbar.pack(fill="x", side="bottom")

    # ── Carga/refresco ──
    def _load_projects(self):
        for card in self._cards.values():
            card.destroy()
        self._cards.clear()

        projects = sorted(pm.load_projects(), key=lambda p: p["name"].lower())
        if not projects:
            self.empty_label.pack(pady=80)
        else:
            self.empty_label.pack_forget()
            for p in projects:
                self._add_card(p)

    def _add_card(self, project: dict):
        card = ProjectCard(
            self.scroll, project,
            on_remove=self._remove_project,
            on_push=self._do_push,
            on_pull=self._do_pull,
            on_log=self._show_log,
            on_purge=self._do_purge,
            on_ghost=self._show_ghosts,
            on_changes=self._show_changes,
            on_gitignore=self._show_gitignore,
            on_launcher=self._configure_launcher,
            on_init=self._do_init,
        )
        card.pack(fill="x", padx=16, pady=(10, 0))
        self._cards[project["id"]] = card

    def _refresh_all(self):
        for card in self._cards.values():
            card.refresh_status()
        self._set_status("Estado actualizado.")

    # ── Añadir proyecto ──
    def _add_project(self):
        folder = filedialog.askdirectory(title="Selecciona la carpeta del proyecto")
        if not folder:
            return
        project = pm.add_project(folder)
        if project["id"] in self._cards:
            self._set_status(f"'{project['name']}' ya está en la lista.")
            return
        self.empty_label.pack_forget()
        self._add_card(project)
        self._set_status(f"Proyecto '{project['name']}' añadido.")

    # ── Eliminar proyecto ──
    def _remove_project(self, project_id: str):
        card = self._cards.get(project_id)
        if not card:
            return
        name = card.project["name"]
        if not messagebox.askyesno("Eliminar proyecto", f"¿Quitar '{name}' de la lista?\n(No se borrarán los archivos.)"):
            return
        pm.remove_project(project_id)
        card.destroy()
        del self._cards[project_id]
        if not self._cards:
            self.empty_label.pack(pady=80)
        self._set_status(f"Proyecto '{name}' eliminado de la lista.")

    # ── Push ──
    def _do_push(self, project: dict):
        if git.is_merging(project["path"]):
            self._warn_merge_conflict(project)
            return

        def _commit(message: str):
            card = self._cards.get(project["id"])
            if card:
                card.set_loading(True, "push")

            def _worker():
                ok, msg = git.do_add_commit_push(project["path"], message)
                if ok:
                    pm.record_push(project["id"])
                self.after(0, lambda: self._after_operation(project["id"], "Commit & Push", msg, ok, "push"))

            threading.Thread(target=_worker, daemon=True).start()

        CommitDialog(self, project["name"], callback=_commit)

    # ── Pull (fetch + merge) ──
    def _do_pull(self, project: dict):
        if git.is_merging(project["path"]):
            self._warn_merge_conflict(project)
            return

        card = self._cards.get(project["id"])
        if card:
            card.set_loading(True, "pull")

        def _worker():
            ok, msg = git.do_fetch_and_merge(project["path"])
            if ok:
                pm.record_pull(project["id"])
            if not ok and git.is_merging(project["path"]):
                self.after(0, lambda: self._after_conflict(project))
            else:
                self.after(0, lambda: self._after_operation(project["id"], "Fetch & Merge", msg, ok, "pull"))

        threading.Thread(target=_worker, daemon=True).start()

    def _after_conflict(self, project: dict):
        """Cierra el estado de 'cargando' y abre el diálogo de conflicto tras un Pull fallido."""
        card = self._cards.get(project["id"])
        if card:
            card.set_loading(False, "pull")
            card.refresh_status()
        self._set_status(f"Conflicto de merge en '{project['name']}'.")
        self._warn_merge_conflict(project)

    # ── Aviso de conflicto de merge ──
    def _warn_merge_conflict(self, project: dict):
        conflicts = git.get_conflicted_files(project["path"])

        def _abort():
            card = self._cards.get(project["id"])
            if card:
                card.set_loading(True, "both")

            def _worker():
                ok, msg = git.do_merge_abort(project["path"])
                self.after(0, lambda: self._after_operation(project["id"], "Abortar merge", msg, ok, "both"))

            threading.Thread(target=_worker, daemon=True).start()

        MergeConflictDialog(self, project, conflicts, on_abort=_abort)

    # ── Inicializar repositorio ──
    def _do_init(self, project: dict):
        def _confirm(remote_url: str):
            def _worker():
                ok, msg = git.init_repo_with_remote(project["path"], remote_url)
                self.after(0, lambda: self._after_init(project, msg, ok))

            threading.Thread(target=_worker, daemon=True).start()

        InitRepoDialog(self, project["name"], callback=_confirm)

    def _after_init(self, project: dict, msg: str, ok: bool):
        if ok:
            # has_git cambió: recargamos la lista completa para que la tarjeta
            # se reconstruya (rama, botones de Push/Pull...) y mantenga el orden alfabético
            self._load_projects()
        self._set_status(f"Inicializar repositorio {'completado' if ok else 'fallido'}.")
        OutputWindow(self, "Inicializar repositorio", msg, ok)

    # ── Post-operación ──
    def _after_operation(self, project_id: str, title: str, msg: str, ok: bool, btn: str):
        card = self._cards.get(project_id)
        if card:
            card.set_loading(False, btn)
            card.refresh_status()
            # Recargar fechas (recrear la tarjeta)
            self._reload_card(project_id)

        verb = "completado" if ok else "fallido"
        self._set_status(f"{title} {verb}.")
        OutputWindow(self, title, msg, ok)

    def _reload_card(self, project_id: str):
        """Actualiza las fechas de la tarjeta sin destruirla ni moverla."""
        card = self._cards.get(project_id)
        if card:
            card.update_dates()

    # ── Configurar lanzador ──
    def _configure_launcher(self, project: dict):
        def _save(exe, icon):
            pm.update_project(project["id"], launcher_exe=exe, launcher_icon=icon)
            card = self._cards.get(project["id"])
            if card:
                card.refresh_launcher_btn()
            self._set_status(f"Lanzador de '{project['name']}' actualizado.")

        LauncherDialog(self, project, callback=_save)

    # ── Purge (limpiar historial) ──
    def _do_purge(self, project: dict):
        def _run_purge(target: str, is_folder: bool):
            card = self._cards.get(project["id"])
            if card:
                card.set_loading(True, "both")

            def _worker():
                ok, msg = git.purge_from_history(project["path"], target, is_folder)
                self.after(0, lambda: self._after_operation(
                    project["id"], "Limpiar historial", msg, ok, "both"
                ))

            threading.Thread(target=_worker, daemon=True).start()

        PurgeDialog(self, project, callback=_run_purge)

    # ── Log ──
    def _show_log(self, project: dict):
        LogWindow(self, project)

    # ── Archivos fantasma ──
    def _show_ghosts(self, project: dict):
        GhostFilesWindow(self, project)

    # ── Cambios pendientes ──
    def _show_changes(self, project: dict):
        ChangesWindow(self, project)

    # ── .gitignore ──
    def _show_gitignore(self, project: dict):
        GitignoreWindow(self, project)

    # ── JSON activo ──
    def _short_json_label(self) -> str:
        path = pm.get_active_json_path()
        return f"📁  {os.path.basename(path)}"

    def _change_json(self):
        path = filedialog.askopenfilename(
            title="Selecciona el archivo JSON de proyectos",
            filetypes=[("JSON", "*.json"), ("Todos los archivos", "*.*")],
        )
        if not path:
            path = filedialog.asksaveasfilename(
                title="O crea un JSON nuevo",
                filetypes=[("JSON", "*.json")],
                defaultextension=".json",
            )
        if not path:
            return
        pm.set_active_json_path(path)
        self.json_label.configure(text=self._short_json_label())
        self._load_projects()
        self._set_status(f"JSON activo: {os.path.basename(path)}")

    # ── Barra de estado ──
    def _set_status(self, msg: str):
        self.statusbar.configure(text=f"  {msg}")


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = GitManagerApp()
    app.mainloop()
