"""
app.py
Punto de orquestación de Git Manager: construye la ventana principal
(GitManagerApp) y conecta los callbacks entre la UI y la lógica de
Git / persistencia de proyectos.

La UI está dividida en varios módulos dentro de gui/:
  - theme.py         Paleta de colores, fuentes y helpers de formato/estado
  - base.py           Clase base común (BaseDialog) para todos los diálogos
  - dialogs.py        Diálogos de acción/confirmación (commit, conflicto de
                       merge, inicializar repo, primera configuración,
                       lanzador, purga de historial)
  - project_card.py   La tarjeta de cada proyecto
  - windows.py        Ventanas "visor" (log, fantasmas, cambios, .gitignore)
"""

import os
import sys

# Asegura que la raíz del proyecto esté en sys.path, sea cual sea el
# mecanismo que use GitManager.pyw para lanzar este módulo (import directo,
# ejecución como script, etc.) — así "from gui..." y "from src..." siempre
# resuelven igual, independientemente de cómo se invoque este archivo.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading

from src import git_operations as git
from src import project_manager as pm

from gui.theme import C, FONT_TITLE, FONT_LABEL, FONT_LABEL_B, FONT_SMALL
from gui.dialogs import (
    OutputWindow, CommitDialog, MergeConflictDialog, InitRepoDialog,
    FirstRunDialog, LauncherDialog, PurgeDialog,
)
from gui.project_card import ProjectCard
from gui.windows import LogWindow, GhostFilesWindow, ChangesWindow, GitignoreWindow


# ─── App principal ────────────────────────────────────────────────────────────
class GitManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Git Manager")
        self.geometry("1150x760")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])

        self._cards: dict[str, ProjectCard] = {}

        if not pm.is_configured():
            self._first_run_setup()

        try:
            self._build_ui()
            self._load_projects()
        except Exception as e:
            import traceback
            messagebox.showerror(
                "Error al iniciar Git Manager",
                f"Ocurrió un error al cargar la aplicación:\n\n{e}\n\n"
                f"{traceback.format_exc()}"
            )
            raise

    # ── Configuración inicial obligatoria ──
    def _first_run_setup(self):
        """
        Primera ejecución (o configuración borrada): no hay ninguna ruta
        por defecto automática. El usuario elige explícitamente si ya
        tiene un projects.json (por ejemplo, en una carpeta sincronizada
        con Google Drive, Dropbox, etc.) o si quiere crear uno nuevo.
        """
        def _pick_existing():
            path = filedialog.askopenfilename(
                title="Selecciona tu archivo de proyectos existente",
                filetypes=[("JSON", "*.json"), ("Todos los archivos", "*.*")],
            )
            if path:
                pm.set_active_json_path(path)

        def _pick_new():
            path = filedialog.asksaveasfilename(
                title="Elige nombre y ubicación (el nombre es libre, p. ej. 'trabajo.json')",
                filetypes=[("JSON", "*.json")],
                defaultextension=".json",
                initialfile="projects.json",
            )
            if path:
                pm.set_active_json_path(path)

        def _quit():
            if messagebox.askyesno(
                "Salir",
                "Git Manager necesita esta configuración para funcionar.\n"
                "¿Salir de la aplicación?"
            ):
                self.destroy()
                sys.exit(0)

        # Si el usuario cancela el selector de archivo, o dice "No" a salir,
        # simplemente se vuelve a mostrar este diálogo hasta que quede configurado.
        while not pm.is_configured():
            dialog = FirstRunDialog(self, on_existing=_pick_existing, on_new=_pick_new, on_quit=_quit)
            self.wait_window(dialog)

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
