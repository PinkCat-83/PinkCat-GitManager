"""
app.py
Orchestration entry point for Git Manager: builds the main window
(GitManagerApp) and wires the callbacks between the UI and the Git /
project-persistence logic.

The UI is split across several modules inside gui/:
  - theme.py         Active color palette, fonts, and format/status helpers
  - theme_loader.py   Single access point for theme palettes (gui/themes/*)
  - base.py           Shared base class (BaseDialog) for every dialog
  - dialogs.py        Action/confirmation dialogs (commit, merge conflict,
                       repo init, first-run setup, launcher, history purge)
  - project_card.py   The card for each project
  - windows.py         "Viewer" windows (log, ghosts, changes, .gitignore)
"""

import os
import sys

# Ensures the project root is on sys.path, regardless of the mechanism
# GitManager.pyw uses to launch this module (direct import, running as a
# script, etc.) — so "from gui..." and "from src..." always resolve the
# same way, no matter how this file is invoked.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from src import git_operations as git
from src import project_manager as pm
from src import i18n
from src.i18n import t

i18n.set_language(pm.get_active_language())

from gui.theme import C, FONT_TITLE, FONT_LABEL, FONT_LABEL_B, FONT_SMALL
from gui.theme_loader import AVAILABLE_THEMES
from gui.dialogs import (
    OutputWindow, CommitDialog, MergeConflictDialog, InitRepoDialog,
    FirstRunDialog, LauncherDialog, PurgeDialog, ProgressWindow,
)
from gui.project_card import ProjectCard
from gui.windows import LogWindow, GhostFilesWindow, ChangesWindow, GitignoreWindow

WINDOW_WIDTH = 1150
WINDOW_HEIGHT = 760

_ICON_PATH = os.path.join(_ROOT, "ico", "PinkCat-GitManager.ico")
_LOGO_PATH = os.path.join(_ROOT, "ico", "PinkCat-Mascot.png")
_LOGO_SIZE = 44


# ─── Main app ──────────────────────────────────────────────────────────────────
class GitManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(t("app_title"))
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])

        if os.path.isfile(_ICON_PATH):
            try:
                self.iconbitmap(_ICON_PATH)
            except Exception:
                pass

        self._cards: dict[str, ProjectCard] = {}

        if not pm.is_configured():
            self._first_run_setup()

        try:
            self._build_menu()
            self._build_ui()
            self._load_projects()
        except Exception as e:
            import traceback
            messagebox.showerror(
                t("error_startup_title"),
                t("error_startup_body", error=e, traceback=traceback.format_exc())
            )
            raise

    # ── Mandatory initial setup ──
    def _first_run_setup(self):
        """
        First run (or configuration was deleted): there is no automatic
        default path. The user explicitly chooses whether they already have
        a projects.json (e.g. inside a folder synced with Google Drive,
        Dropbox, etc.) or wants to create a new one.
        """
        def _pick_existing():
            path = filedialog.askopenfilename(
                title=t("dialog_pick_existing_title"),
                filetypes=[(t("filetype_json"), "*.json"), (t("filetype_all"), "*.*")],
            )
            if path:
                pm.set_active_json_path(path)

        def _pick_new():
            path = filedialog.asksaveasfilename(
                title=t("dialog_pick_new_title"),
                filetypes=[(t("filetype_json"), "*.json")],
                defaultextension=".json",
                initialfile="projects.json",
            )
            if path:
                pm.set_active_json_path(path)

        def _quit():
            if messagebox.askyesno(t("quit_confirm_title"), t("quit_confirm_body")):
                self.destroy()
                sys.exit(0)

        # If the user cancels the file picker, or answers "No" to quit, this
        # dialog is simply shown again until the configuration is complete.
        while not pm.is_configured():
            dialog = FirstRunDialog(self, on_existing=_pick_existing, on_new=_pick_new, on_quit=_quit)
            self.wait_window(dialog)

    # ── Settings menu ──
    def _build_menu(self):
        menubar = tk.Menu(self, tearoff=0)
        self._menubar = menubar

        settings_menu = tk.Menu(menubar, tearoff=0)
        self._settings_menu = settings_menu
        menubar.add_cascade(label=t("menu_settings"), menu=settings_menu)

        language_menu = tk.Menu(settings_menu, tearoff=0)
        self._language_var = tk.StringVar(value=i18n.get_language())
        for lang in i18n.AVAILABLE_LANGUAGES:
            language_menu.add_radiobutton(
                label=lang, variable=self._language_var, value=lang,
                command=lambda l=lang: self._change_language(l)
            )
        settings_menu.add_cascade(label=t("menu_language"), menu=language_menu)

        theme_menu = tk.Menu(settings_menu, tearoff=0)
        self._theme_menu = theme_menu
        self._theme_var = tk.StringVar(value=pm.get_active_theme())
        for theme_name in AVAILABLE_THEMES:
            theme_menu.add_radiobutton(
                label=t(f"menu_theme_{theme_name}"), variable=self._theme_var, value=theme_name,
                command=lambda th=theme_name: self._change_theme(th)
            )
        settings_menu.add_cascade(label=t("menu_theme"), menu=theme_menu)

        # Active projects file — infrequent, per-machine configuration action;
        # lives in the settings menu rather than as a loose header button
        # (Design System §9, confirmed with the author during the audit).
        settings_menu.add_separator()
        settings_menu.add_command(label=self._json_menu_label(), command=self._change_json)
        self._json_menu_index = settings_menu.index("end")

        self.configure(menu=menubar)

    def _change_language(self, language: str):
        # Language switches live, per PinkCat_Design_System.md §10 — no restart
        # needed. Persist it, flip src/i18n's active language, then re-read
        # every currently built widget's text instead of destroying/rebuilding.
        pm.set_active_language(language)
        i18n.set_language(language)
        self.refresh_language()

    def _change_theme(self, theme_name: str):
        # Theme (color) switching is deliberately NOT live (Design System
        # §10) — rebuilding every widget's colors was judged not worth the
        # complexity for a single-user tool. Restart notice stays explicit.
        pm.set_active_theme(theme_name)
        messagebox.showinfo(t("menu_restart_notice_title"), t("menu_restart_notice_body"))

    def refresh_language(self):
        """Re-reads every visible widget's text in the active language,
        without destroying or recreating any widget (Design System §10)."""
        self.title(t("app_title"))
        self._menubar.entryconfigure(0, label=t("menu_settings"))
        self._settings_menu.entryconfigure(0, label=t("menu_language"))
        self._settings_menu.entryconfigure(1, label=t("menu_theme"))
        for i, theme_name in enumerate(AVAILABLE_THEMES):
            self._theme_menu.entryconfigure(i, label=t(f"menu_theme_{theme_name}"))
        self._settings_menu.entryconfigure(self._json_menu_index, label=self._json_menu_label())

        self._title_label.configure(text=f"◈  {t('app_title').upper()}")
        self._btn_add_project.configure(text=t("btn_add_project"))
        self._btn_refresh_all.configure(text=t("btn_refresh_all"))
        self.empty_label.configure(text=t("empty_list_message"))
        self.statusbar.configure(text=t("status_ready"))

        for card in self._cards.values():
            card.refresh_language()

    # ── Layout ──
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        self._title_label = ctk.CTkLabel(
            header, text=f"◈  {t('app_title').upper()}",
            font=FONT_TITLE, text_color=C["accent"]
        )
        self._title_label.pack(side="left", padx=24, pady=0)

        # PinkCat mascot logo — always present in the top-right corner of the
        # title bar, outside the settings menu, regardless of the active theme.
        self._build_logo(header).pack(side="right", padx=(8, 24))

        self._btn_add_project = ctk.CTkButton(
            header, text=t("btn_add_project"),
            command=self._add_project,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=C["corner_radius_btn"],
            height=36, font=FONT_LABEL_B
        )
        self._btn_add_project.pack(side="right", padx=24)

        self._btn_refresh_all = ctk.CTkButton(
            header, text=t("btn_refresh_all"),
            command=self._refresh_all,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=C["corner_radius_btn"], height=36, font=FONT_SMALL
        )
        self._btn_refresh_all.pack(side="right", padx=(0, 8))

        # Scrollable area
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent_dim"],
            corner_radius=0
        )
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # Empty-list message
        self.empty_label = ctk.CTkLabel(
            self.scroll,
            text=t("empty_list_message"),
            font=FONT_LABEL, text_color=C["text_muted"]
        )

        # Status bar
        self.statusbar = ctk.CTkLabel(
            self, text=t("status_ready"),
            font=FONT_SMALL, text_color=C["text_dim"],
            fg_color=C["panel"], anchor="w", height=24
        )
        self.statusbar.pack(fill="x", side="bottom")

    def _build_logo(self, parent) -> ctk.CTkLabel:
        """
        Builds the PinkCat mascot logo label. Falls back to a paw emoji if
        Pillow isn't installed or the image is missing — the brand mark
        itself must never disappear, only its rendering degrades gracefully.
        """
        if _PIL_AVAILABLE and os.path.isfile(_LOGO_PATH):
            try:
                pil_img = Image.open(_LOGO_PATH).convert("RGBA")
                pil_img.thumbnail((_LOGO_SIZE, _LOGO_SIZE), Image.LANCZOS)
                logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                return ctk.CTkLabel(parent, image=logo_img, text="")
            except Exception:
                pass
        return ctk.CTkLabel(parent, text="🐾", font=("Segoe UI", 24), text_color=C["accent"])

    # ── Load/refresh ──
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
        self._set_status(t("status_updated"))

    # ── Add project ──
    def _add_project(self):
        folder = filedialog.askdirectory(title=t("dialog_add_project_title"))
        if not folder:
            return
        project = pm.add_project(folder)
        if project["id"] in self._cards:
            self._set_status(t("status_project_already_added", name=project["name"]))
            return
        self.empty_label.pack_forget()
        self._add_card(project)
        self._set_status(t("status_project_added", name=project["name"]))

    # ── Remove project ──
    def _remove_project(self, project_id: str):
        card = self._cards.get(project_id)
        if not card:
            return
        name = card.project["name"]
        if not messagebox.askyesno(t("confirm_remove_title"), t("confirm_remove_body", name=name)):
            return
        pm.remove_project(project_id)
        card.destroy()
        del self._cards[project_id]
        if not self._cards:
            self.empty_label.pack(pady=80)
        self._set_status(t("status_project_removed", name=name))

    # ── Push ──
    def _do_push(self, project: dict):
        if git.is_merging(project["path"]):
            self._warn_merge_conflict(project)
            return

        def _commit(message: str):
            card = self._cards.get(project["id"])
            if card:
                card.set_loading(True, "push")

            # Live window: shows Git's progress line by line while pushing.
            progress = ProgressWindow(self, t("op_title_commit_push"))

            def _worker():
                ok, msg = git.do_add_commit_push(
                    project["path"], message, on_line=progress.push_line
                )
                if ok:
                    pm.record_push(project["id"])
                self.after(0, lambda: self._after_operation(
                    project["id"], t("op_title_commit_push"), msg, ok, "push", progress=progress
                ))

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
                self.after(0, lambda: self._after_operation(project["id"], t("op_title_fetch_merge"), msg, ok, "pull"))

        threading.Thread(target=_worker, daemon=True).start()

    def _after_conflict(self, project: dict):
        """Clears the 'loading' state and opens the conflict dialog after a failed Pull."""
        card = self._cards.get(project["id"])
        if card:
            card.set_loading(False, "pull")
            card.refresh_status()
        self._set_status(t("status_merge_conflict", name=project["name"]))
        self._warn_merge_conflict(project)

    # ── Merge conflict warning ──
    def _warn_merge_conflict(self, project: dict):
        conflicts = git.get_conflicted_files(project["path"])

        def _abort():
            card = self._cards.get(project["id"])
            if card:
                card.set_loading(True, "both")

            def _worker():
                ok, msg = git.do_merge_abort(project["path"])
                self.after(0, lambda: self._after_operation(project["id"], t("op_title_abort_merge"), msg, ok, "both"))

            threading.Thread(target=_worker, daemon=True).start()

        MergeConflictDialog(self, project, conflicts, on_abort=_abort)

    # ── Initialize repository ──
    def _do_init(self, project: dict):
        def _confirm(remote_url: str):
            def _worker():
                ok, msg = git.init_repo_with_remote(project["path"], remote_url)
                self.after(0, lambda: self._after_init(project, msg, ok))

            threading.Thread(target=_worker, daemon=True).start()

        InitRepoDialog(self, project["name"], callback=_confirm)

    def _after_init(self, project: dict, msg: str, ok: bool):
        if ok:
            # has_git changed: reload the full list so the card is rebuilt
            # (branch, Push/Pull buttons...) while keeping alphabetical order
            self._load_projects()
        title = t("op_title_init_repo")
        self._set_status(t("status_op_done", title=title) if ok else t("status_op_failed", title=title))
        OutputWindow(self, t("op_title_init_repo"), msg, ok)

    # ── Post-operation ──
    def _after_operation(self, project_id: str, title: str, msg: str, ok: bool, btn: str,
                         progress: "ProgressWindow | None" = None):
        card = self._cards.get(project_id)
        if card:
            card.set_loading(False, btn)
            card.refresh_status()
            # Reload dates (recreate the card)
            self._reload_card(project_id)

        self._set_status(t("status_op_done", title=title) if ok else t("status_op_failed", title=title))
        if progress is not None and progress.is_open:
            # The live window stays open and turns into the result window
            progress.finish(ok, msg)
        else:
            OutputWindow(self, title, msg, ok)

    def _reload_card(self, project_id: str):
        """Refreshes the card's dates without destroying or moving it."""
        card = self._cards.get(project_id)
        if card:
            card.update_dates()

    # ── Configure launcher ──
    def _configure_launcher(self, project: dict):
        def _save(exe, icon):
            pm.update_project(project["id"], launcher_exe=exe, launcher_icon=icon)
            card = self._cards.get(project["id"])
            if card:
                card.refresh_launcher_btn()
            self._set_status(t("status_launcher_updated", name=project["name"]))

        LauncherDialog(self, project, callback=_save)

    # ── Purge (clean history) ──
    def _do_purge(self, project: dict):
        def _run_purge(target: str, is_folder: bool):
            card = self._cards.get(project["id"])
            if card:
                card.set_loading(True, "both")

            def _worker():
                ok, msg = git.purge_from_history(project["path"], target, is_folder)
                self.after(0, lambda: self._after_operation(
                    project["id"], t("op_title_purge"), msg, ok, "both"
                ))

            threading.Thread(target=_worker, daemon=True).start()

        PurgeDialog(self, project, callback=_run_purge)

    # ── Log ──
    def _show_log(self, project: dict):
        LogWindow(self, project)

    # ── Ghost files ──
    def _show_ghosts(self, project: dict):
        GhostFilesWindow(self, project)

    # ── Pending changes ──
    def _show_changes(self, project: dict):
        ChangesWindow(self, project)

    # ── .gitignore ──
    def _show_gitignore(self, project: dict):
        GitignoreWindow(self, project)

    # ── Active JSON ──
    def _json_menu_label(self) -> str:
        path = pm.get_active_json_path()
        return t("menu_active_json", name=os.path.basename(path))

    def _change_json(self):
        path = filedialog.askopenfilename(
            title=t("dialog_change_json_title"),
            filetypes=[(t("filetype_json"), "*.json"), (t("filetype_all"), "*.*")],
        )
        if not path:
            path = filedialog.asksaveasfilename(
                title=t("dialog_change_json_new_title"),
                filetypes=[(t("filetype_json"), "*.json")],
                defaultextension=".json",
            )
        if not path:
            return
        pm.set_active_json_path(path)
        self._settings_menu.entryconfigure(self._json_menu_index, label=self._json_menu_label())
        self._load_projects()
        self._set_status(t("status_active_json", name=os.path.basename(path)))

    # ── Status bar ──
    def _set_status(self, msg: str):
        self.statusbar.configure(text=f"  {msg}")


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = GitManagerApp()
    app.mainloop()
