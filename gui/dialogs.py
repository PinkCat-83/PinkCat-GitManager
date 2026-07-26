"""
dialogs.py
Diálogos de acción/confirmación: resultado de operaciones, commit, conflicto
de merge, inicialización de repositorio, primera configuración, lanzador y
purga de historial. Todos heredan de BaseDialog.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import os

from gui.theme import C, FONT_MONO, FONT_MONO_S, FONT_LABEL, FONT_LABEL_B, FONT_SMALL, FONT_BIG
from gui.base import BaseDialog

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


# ─── Diálogo de primera configuración ─────────────────────────────────────────
class FirstRunDialog(BaseDialog):
    """
    Se muestra cuando no hay ningún projects.json configurado todavía.
    Ofrece explícitamente dos caminos (nada de 'cancela para crear uno nuevo').
    """
    def __init__(self, master, on_existing, on_new, on_quit):
        super().__init__(master)
        self.title("Configuración inicial — Git Manager")
        self.geometry("520x400")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.protocol("WM_DELETE_WINDOW", on_quit)

        ctk.CTkLabel(
            self, text="◈  Bienvenido a Git Manager",
            font=FONT_BIG, text_color=C["accent"]
        ).pack(padx=24, pady=(24, 8), anchor="w")

        ctk.CTkLabel(
            self,
            text="Aún no hay ningún archivo de proyectos configurado.\n"
                 "Puedes llamarlo como quieras y tener varios distintos.\n\n"
                 "Si quieres que se sincronice entre varios ordenadores,\n"
                 "elige una carpeta dentro de Google Drive, Dropbox, etc.",
            font=FONT_LABEL, text_color=C["text_dim"], justify="left"
        ).pack(padx=24, anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, pady=(24, 8), fill="x")

        ctk.CTkButton(
            row, text="📂  Ya tengo un archivo de proyectos", height=42,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text"], border_color=C["border"], border_width=1,
            corner_radius=6, font=FONT_LABEL_B,
            command=lambda: (self.destroy(), on_existing())
        ).pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            row, text="✚  Crear uno nuevo", height=42,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=6, font=FONT_LABEL_B,
            command=lambda: (self.destroy(), on_new())
        ).pack(fill="x")

        ctk.CTkButton(
            self, text="Salir de Git Manager", command=on_quit,
            fg_color="transparent", hover_color=C["card_hover"],
            text_color=C["text_muted"], corner_radius=6, height=32, font=FONT_SMALL
        ).pack(pady=(16, 16))


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
