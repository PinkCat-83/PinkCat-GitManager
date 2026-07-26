"""
windows.py
Ventanas "visor" de datos de un proyecto: log de commits, archivos fantasma
(borrados del historial), cambios pendientes de commit/push, y revisor de
.gitignore. Todas heredan de BaseDialog.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading

from src import git_operations as git

from gui.theme import C, FONT_BIG, FONT_LABEL, FONT_LABEL_B, FONT_MONO_S, FONT_SMALL
from gui.base import BaseDialog
from gui.dialogs import OutputWindow

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

    def _load(self):
        # Limpiar lista
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.count_label.configure(text="Buscando...", text_color=C["text_dim"])

        def _worker():
            files = git.get_deleted_files(self.project["path"])
            self._files = files
            self.after(0, lambda: self._populate(files))

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

        def _worker():
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

        def _worker():
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
