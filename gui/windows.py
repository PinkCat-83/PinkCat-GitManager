"""
windows.py
Data "viewer" windows for a project: commit log, ghost files (deleted from
history), pending changes, and the .gitignore reviewer. All inherit from
BaseDialog.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading

from src import git_operations as git
from src.i18n import t

from gui.theme import C, FONT_BIG, FONT_LABEL, FONT_LABEL_B, FONT_MONO_S, FONT_SMALL
from gui.base import BaseDialog
from gui.dialogs import OutputWindow

_R_CARD = C["corner_radius_card"]
_R_BTN = C["corner_radius_btn"]


# ─── Log window ────────────────────────────────────────────────────────────────
class LogWindow(BaseDialog):
    def __init__(self, master, project: dict):
        super().__init__(master)
        self.title(t("window_title_log", name=project["name"]))
        self.geometry("680x460")
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)

        ctk.CTkLabel(
            self, text=t("log_header", name=project["name"]),
            font=FONT_BIG, text_color=C["text"]
        ).pack(padx=20, pady=(16, 8), anchor="w")

        box = ctk.CTkTextbox(
            self, font=FONT_MONO_S,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            corner_radius=_R_CARD
        )
        box.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        commits = git.get_log(project["path"], n=20)
        if not commits:
            box.insert("end", t("log_empty"))
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
            self, text=t("btn_close"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=34
        ).pack(pady=(0, 16))


# ─── Ghost files window ────────────────────────────────────────────────────────
class GhostFilesWindow(BaseDialog):
    """
    Shows every file that existed in the history but is no longer on the
    current branch. Allows recovering them.
    """
    def __init__(self, master, project: dict):
        super().__init__(master)
        self.title(t("window_title_ghosts", name=project["name"]))
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
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            hdr, text=t("ghosts_header"),
            font=FONT_BIG, text_color=C["text"]
        ).pack(side="left")

        self.count_label = ctk.CTkLabel(
            hdr, text=t("ghosts_searching"),
            font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.count_label.pack(side="left", padx=(12, 0))

        ctk.CTkButton(
            hdr, text=t("btn_reload"), width=90, height=30,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=_R_BTN, font=FONT_SMALL,
            command=self._load
        ).pack(side="right")

        ctk.CTkLabel(
            self,
            text=t("ghosts_intro"),
            font=FONT_SMALL, text_color=C["text_dim"], wraplength=740, justify="left"
        ).pack(padx=20, pady=(4, 10), anchor="w")

        # Table header
        cols = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=_R_BTN, height=32)
        cols.pack(fill="x", padx=20, pady=(0, 2))
        cols.pack_propagate(False)

        ctk.CTkLabel(cols, text=t("ghosts_col_path"), font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="w", width=700).pack(side="left", padx=(12,0))
        ctk.CTkLabel(cols, text=t("ghosts_col_deleted"), font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="w", width=130).pack(side="left", padx=(8,0))
        ctk.CTkLabel(cols, text=t("ghosts_col_commit"), font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="w", width=60).pack(side="left", padx=(8,0))
        ctk.CTkLabel(cols, text=t("ghosts_col_message"), font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="w").pack(side="left", padx=(8,0), fill="x", expand=True)

        # Scrollable list
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=C["bg"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent_dim"],
            corner_radius=0
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkButton(
            footer, text=t("btn_close"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=36, width=120
        ).pack(side="left")

    def _load(self):
        # Clear the list
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.count_label.configure(text=t("ghosts_searching"), text_color=C["text_dim"])

        def _worker():
            files = git.get_deleted_files(self.project["path"])
            self._files = files
            self.after(0, lambda: self._populate(files))

        threading.Thread(target=_worker, daemon=True).start()

    def _populate(self, files: list):
        if not files:
            self.count_label.configure(text=t("ghosts_none_found"), text_color=C["success"])
            ctk.CTkLabel(
                self.list_frame,
                text=t("ghosts_none_found_body"),
                font=FONT_LABEL, text_color=C["text_muted"]
            ).pack(pady=40)
            return

        self.count_label.configure(
            text=t("ghosts_found_count", n=len(files)),
            text_color=C["warning"]
        )

        for i, f in enumerate(files):
            row_color = C["card"] if i % 2 == 0 else C["panel"]
            row = ctk.CTkFrame(self.list_frame, fg_color=row_color, corner_radius=_R_BTN, height=40)
            row.pack(fill="x", pady=(0, 2))
            row.pack_propagate(False)

            # Path
            ctk.CTkLabel(
                row, text=f["path"],
                font=FONT_MONO_S, text_color=C["text"], anchor="w", width=700,
                wraplength=700
            ).pack(side="left", padx=(10, 0))

            # Deletion date
            ctk.CTkLabel(
                row, text=f["date_delete"],
                font=FONT_SMALL, text_color=C["text_dim"], anchor="w", width=130
            ).pack(side="left", padx=(8, 0))

            # Commit hash
            ctk.CTkLabel(
                row, text=f["hash_delete"],
                font=FONT_MONO_S, text_color=C["accent_dim"], anchor="w", width=60
            ).pack(side="left", padx=(8, 0))

            # Commit message (truncated)
            msg = f["commit_msg"][:40] + "..." if len(f["commit_msg"]) > 40 else f["commit_msg"]
            ctk.CTkLabel(
                row, text=msg,
                font=FONT_SMALL, text_color=C["text_dim"], anchor="w"
            ).pack(side="left", padx=(8, 0), fill="x", expand=True)

            # Recover button
            fdata = f  # local capture
            ctk.CTkButton(
                row, text=t("btn_recover"), width=88, height=28,
                fg_color=C["accent_dim"], hover_color=C["accent"],
                text_color="#000000", corner_radius=5, font=FONT_SMALL,
                command=lambda fd=fdata: self._recover(fd)
            ).pack(side="right", padx=(0, 8))

    def _recover(self, fdata: dict):
        if not messagebox.askyesno(
            t("ghosts_recover_confirm_title"),
            t("ghosts_recover_confirm_body", path=fdata["path"]),
            parent=self
        ):
            return

        ok, msg = git.restore_deleted_file(
            self.project["path"], fdata["path"], fdata["hash_full"]
        )
        icon = "✓" if ok else "✗"
        color = C["success"] if ok else C["danger"]

        win = ctk.CTkToplevel(self)
        win.title(t("ghosts_recover_confirm_title"))
        win.geometry("500x260")
        win.configure(fg_color=C["bg"])
        win.transient(self)
        win.lift()
        win.attributes("-topmost", True)
        win.after(100, lambda: (win.attributes("-topmost", False), win.focus_force(), win.grab_set()))

        ctk.CTkLabel(win, text=f"{icon}  {t('ghosts_recovered_ok') if ok else t('ghosts_recovered_err')}",
                     font=FONT_BIG, text_color=color).pack(padx=20, pady=(18, 8), anchor="w")

        box = ctk.CTkTextbox(win, font=FONT_MONO_S,
                             fg_color=C["panel"], text_color=C["text"],
                             border_color=C["border"], border_width=1, corner_radius=_R_CARD)
        box.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        box.insert("end", msg)
        box.configure(state="disabled")

        ctk.CTkButton(win, text=t("btn_close"), command=win.destroy,
                      fg_color=C["border"], hover_color=C["card_hover"],
                      text_color=C["text"], corner_radius=_R_BTN, height=34).pack(pady=(0, 14))

        if ok:
            self._load()  # Reload the list in case something changed


# ─── Pending changes window ────────────────────────────────────────────────────
class ChangesWindow(BaseDialog):
    """
    Shows which files have changes relative to the last commit: new,
    modified, deleted, and staged.
    """
    def __init__(self, master, project: dict):
        super().__init__(master)
        self.title(t("window_title_changes", name=project["name"]))
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
            hdr, text=t("changes_header"),
            font=FONT_BIG, text_color=C["text"]
        ).pack(side="left")

        ctk.CTkButton(
            hdr, text="↻", width=36, height=30,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=_R_BTN, font=FONT_BIG,
            command=self._load
        ).pack(side="right")

        self.summary = ctk.CTkLabel(
            self, text=t("changes_calculating"),
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
            self, text=t("btn_close"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=34
        ).pack(pady=(0, 14))

    def _load(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.summary.configure(text=t("changes_calculating"), text_color=C["text_dim"])

        def _worker():
            status = git.get_status(self.project["path"])
            self.after(0, lambda: self._populate(status))
        threading.Thread(target=_worker, daemon=True).start()

    def _populate(self, status: dict):
        groups = [
            (t("changes_group_new"),      status.get("new_files", []), C["success"]),
            (t("changes_group_modified"), status.get("modified",   []), C["warning"]),
            (t("changes_group_staged"),   status.get("staged",     []), C["info"]),
            (t("changes_group_deleted"),  status.get("deleted",    []), C["danger"]),
        ]

        total = status.get("total_changes", 0)
        ahead = status.get("ahead", 0)

        parts = []
        if total:
            parts.append(t("changes_files_with_changes", n=total))
        if ahead:
            parts.append(t("changes_commits_ahead", n=ahead))
        if not parts:
            self.summary.configure(text=t("changes_none_pending"), text_color=C["success"])
            ctk.CTkLabel(
                self.list_frame,
                text=t("changes_none_pending_body"),
                font=FONT_LABEL, text_color=C["text_muted"]
            ).pack(pady=40)
            return

        self.summary.configure(text="  ·  ".join(parts), text_color=C["warning"])

        for group_name, files, color in groups:
            if not files:
                continue

            # Group header
            g_hdr = ctk.CTkFrame(self.list_frame, fg_color=C["panel"], corner_radius=_R_BTN, height=28)
            g_hdr.pack(fill="x", pady=(8, 2))
            g_hdr.pack_propagate(False)
            ctk.CTkLabel(
                g_hdr,
                text=f"  {group_name}  ({len(files)})",
                font=FONT_SMALL, text_color=color, anchor="w"
            ).pack(fill="x", padx=8, pady=4)

            # File rows
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

        # Commits not yet pushed
        if ahead:
            g_hdr2 = ctk.CTkFrame(self.list_frame, fg_color=C["panel"], corner_radius=_R_BTN, height=28)
            g_hdr2.pack(fill="x", pady=(8, 2))
            g_hdr2.pack_propagate(False)
            ctk.CTkLabel(
                g_hdr2,
                text=f"  {t('changes_group_commits_ahead')}  ({ahead})",
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


# ─── .gitignore window ─────────────────────────────────────────────────────────
class GitignoreWindow(BaseDialog):
    """
    Shows the .gitignore contents and detects files on GitHub that match one
    of its rules (uploaded by mistake).
    """
    def __init__(self, master, project: dict):
        super().__init__(master)
        self.title(t("window_title_gitignore", name=project["name"]))
        self.geometry("980x620")
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.project = project
        self._untracked = set()  # files already processed in this session
        self._build()
        self._load()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            hdr, text=t("gitignore_header"),
            font=FONT_BIG, text_color=C["text"]
        ).pack(side="left")

        ctk.CTkButton(
            hdr, text="↻", width=36, height=30,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=_R_BTN, font=FONT_BIG, command=self._load
        ).pack(side="right")

        ctk.CTkLabel(
            self,
            text=t("gitignore_intro"),
            font=FONT_SMALL, text_color=C["text_dim"], wraplength=940, justify="left"
        ).pack(padx=20, pady=(4, 10), anchor="w")

        # Two side-by-side panels
        panels = ctk.CTkFrame(self, fg_color="transparent")
        panels.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=2)
        panels.rowconfigure(0, weight=1)

        # ── Left panel: .gitignore rules ──
        left = ctk.CTkFrame(panels, fg_color=C["panel"], corner_radius=_R_CARD, border_color=C["border"], border_width=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(
            left, text=t("gitignore_rules_label"),
            font=FONT_LABEL_B, text_color=C["text_dim"]
        ).pack(padx=12, pady=(10, 6), anchor="w")

        self.rules_box = ctk.CTkTextbox(
            left, font=FONT_MONO_S,
            fg_color=C["card"], text_color=C["text_dim"],
            border_width=0, corner_radius=_R_BTN
        )
        self.rules_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # ── Right panel: matches ──
        right = ctk.CTkFrame(panels, fg_color=C["panel"], corner_radius=_R_CARD, border_color=C["border"], border_width=1)
        right.grid(row=0, column=1, sticky="nsew")

        right_hdr = ctk.CTkFrame(right, fg_color="transparent")
        right_hdr.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(
            right_hdr, text=t("gitignore_matches_label"),
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
            corner_radius=_R_BTN
        )
        self.matches_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkButton(
            footer, text=t("btn_close"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=36, width=120
        ).pack(side="left")

        self.btn_apply = ctk.CTkButton(
            footer, text=t("btn_untrack_selected"),
            command=self._apply_untrack,
            fg_color="#2a1010", hover_color="#6b1a1a",
            text_color=C["danger"], border_color="#6b1a1a", border_width=1,
            corner_radius=_R_BTN, height=36, font=FONT_LABEL_B, state="disabled"
        )
        self.btn_apply.pack(side="right")

        self.sel_count_label = ctk.CTkLabel(
            footer, text="", font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.sel_count_label.pack(side="right", padx=(0, 12))

    def _load(self):
        self.rules_box.configure(state="normal")
        self.rules_box.delete("1.0", "end")
        self.rules_box.insert("end", t("changes_calculating"))
        self.rules_box.configure(state="disabled")
        for w in self.matches_frame.winfo_children():
            w.destroy()
        self.match_count.configure(text="")
        # Do NOT reset self._untracked — we want to keep the visual state

        def _worker():
            data = git.get_gitignore_data(self.project["path"])
            self.after(0, lambda: self._populate(data))
        threading.Thread(target=_worker, daemon=True).start()

    def _populate(self, data: dict):
        self.rules_box.configure(state="normal")
        self.rules_box.delete("1.0", "end")
        self._checkboxes = {}   # filepath -> BooleanVar

        if not data["gitignore_exists"]:
            self.rules_box.insert("end", t("gitignore_not_found"))
            self.rules_box.configure(state="disabled")
            self.match_count.configure(text=t("gitignore_no_gitignore_short"), text_color=C["text_muted"])
            return

        if not data["rules"]:
            self.rules_box.insert("end", t("gitignore_empty"))
        else:
            for rule in data["rules"]:
                self.rules_box.insert("end", f"  {rule}\n")
        self.rules_box.configure(state="disabled")

        matches = data["tracked"]
        if not matches:
            self.match_count.configure(text=t("gitignore_no_matches"), text_color=C["success"])
            ctk.CTkLabel(
                self.matches_frame,
                text=t("gitignore_no_matches_body"),
                font=FONT_LABEL, text_color=C["text_muted"], justify="center"
            ).pack(pady=40)
            self.btn_apply.configure(state="disabled")
            self.sel_count_label.configure(text="")
            return

        self.match_count.configure(
            text=t("gitignore_suspicious_count", n=len(matches)),
            text_color=C["danger"]
        )

        # Header with "select all"
        col_hdr = ctk.CTkFrame(self.matches_frame, fg_color=C["panel"], corner_radius=4, height=28)
        col_hdr.pack(fill="x", pady=(0, 4))
        col_hdr.pack_propagate(False)

        self._all_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            col_hdr, text=f"  {t('gitignore_col_github_file')}", variable=self._all_var,
            font=FONT_SMALL, text_color=C["text_dim"],
            fg_color=C["accent_dim"], hover_color=C["accent"],
            border_color=C["border"], checkmark_color="#000",
            command=self._toggle_all, width=20, height=20
        ).pack(side="left", padx=(8, 0), pady=4)
        ctk.CTkLabel(col_hdr, text=f"{t('gitignore_col_matching_rule')}  ", font=FONT_SMALL,
                     text_color=C["text_dim"], anchor="e", width=200).pack(side="right", padx=8)

        for i, m in enumerate(matches):
            row_color = C["card"] if i % 2 == 0 else C["panel"]
            row = ctk.CTkFrame(self.matches_frame, fg_color=row_color, corner_radius=4, height=32)
            row.pack(fill="x", pady=(0, 2))
            row.pack_propagate(False)

            var = tk.BooleanVar(value=False)
            self._checkboxes[m["file"]] = var

            ctk.CTkLabel(
                row, text=f"{m['rule']}  ",
                font=FONT_MONO_S, text_color=C["danger"], anchor="e", width=200
            ).pack(side="right", padx=8)

            already_done = m["file"] in self._untracked
            if already_done:
                # Row already processed: green tick + dimmed text
                ctk.CTkLabel(
                    row, text="  ✓", font=FONT_MONO_S,
                    text_color=C["success"], width=28
                ).pack(side="left", padx=(8, 0))
                ctk.CTkLabel(
                    row, text=f"  {m['file']}  {t('gitignore_pending_push')}",
                    font=FONT_MONO_S, text_color=C["text_muted"]
                ).pack(side="left", fill="x", expand=True)
                # Disable this row's checkbox so it doesn't get counted
                var.set(False)
            else:
                ctk.CTkCheckBox(
                    row, text=f"  {m['file']}", variable=var,
                    font=FONT_MONO_S, text_color=C["warning"],
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
                text=t("gitignore_selected_count", n=n),
                text_color=C["warning"]
            )
        else:
            self.btn_apply.configure(state="disabled")
            self.sel_count_label.configure(text="")

    def _apply_untrack(self):
        selected = [f for f, v in self._checkboxes.items() if v.get()]
        if not selected:
            return
        file_list = "\n".join(f"  • {f}" for f in selected)
        if not messagebox.askyesno(
            t("gitignore_untrack_title"),
            t("gitignore_untrack_body", list=file_list),
            parent=self
        ):
            return

        errors = []
        done = []
        for filepath in selected:
            # --ignore-unmatch avoids an error if the file is no longer in the index
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
            lines.append(t("gitignore_untrack_removed", n=len(done)))
            lines += [f"  ✓ {f}" for f in done]
        if errors:
            lines.append(f"\n{t('gitignore_untrack_errors', n=len(errors))}")
            lines += [f"  ✗ {e}" for e in errors]
        if done:
            lines.append(f"\n{t('gitignore_untrack_push_reminder')}")

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

        win = OutputWindow(self, t("gitignore_untrack_title"), "\n".join(lines), ok)
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), _after_close()))
        # Also when closed via the internal Close button
        win._on_close = _after_close
