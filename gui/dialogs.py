"""
dialogs.py
Action/confirmation dialogs: operation result, commit, merge conflict,
repository initialization, first-run setup, launcher, and history purge.
All inherit from BaseDialog.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import queue

from src.i18n import t
from gui.theme import C, FONT_MONO, FONT_MONO_S, FONT_LABEL, FONT_LABEL_B, FONT_SMALL, FONT_BIG
from gui.base import BaseDialog

_R_CARD = C["corner_radius_card"]
_R_BTN = C["corner_radius_btn"]


# ─── Output/result window ─────────────────────────────────────────────────────
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

        color = C["success"] if success else C["danger"]
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
            corner_radius=_R_CARD
        )
        box.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        box.insert("end", content)
        box.configure(state="disabled")

        ctk.CTkButton(
            self, text=t("btn_close"), command=self._close,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=34
        ).pack(pady=(0, 16))
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._on_close = None  # optional callback

    def _close(self):
        cb = self._on_close
        self.destroy()
        if cb:
            cb()


# ─── Live progress window ─────────────────────────────────────────────────────
class ProgressWindow(BaseDialog):
    """
    Shows the live output of a long-running Git operation (e.g. push).

    push_line() is thread-safe (it only enqueues), so the Git worker thread
    can call it directly; the window drains the queue on the Tk main thread.
    finish() must be called from the main thread once the operation is over.
    """
    _POLL_MS = 80

    def __init__(self, master, title: str):
        super().__init__(master)
        self._op_title = title
        self._queue: "queue.Queue[tuple[str, bool]]" = queue.Queue()
        self._alive = True
        self._finished = False
        self._last_is_progress = False

        self.title(title)
        self.geometry("620x420")
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._header = ctk.CTkLabel(
            self, text=f"⏳  {title}", font=FONT_BIG, text_color=C["info"]
        )
        self._header.pack(padx=20, pady=(18, 4), anchor="w")

        self._hint = ctk.CTkLabel(
            self, text=t("progress_hint"), font=FONT_SMALL, text_color=C["text_dim"]
        )
        self._hint.pack(padx=20, pady=(0, 6), anchor="w")

        self._bar = ctk.CTkProgressBar(
            self, mode="indeterminate",
            fg_color=C["border"], progress_color=C["accent"], height=6
        )
        self._bar.pack(fill="x", padx=20, pady=(0, 10))
        self._bar.start()

        self._box = ctk.CTkTextbox(
            self, font=FONT_MONO_S,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            corner_radius=_R_CARD
        )
        self._box.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self._box.configure(state="disabled")

        self._btn_close = ctk.CTkButton(
            self, text=t("btn_close"), command=self._close,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=34
        )
        self._btn_close.pack(pady=(0, 16))

        self.after(self._POLL_MS, self._poll)

    # ── Public API ──
    @property
    def is_open(self) -> bool:
        return self._alive

    def push_line(self, text: str, is_progress: bool = False):
        """Thread-safe: queues a line to be shown by the main thread."""
        self._queue.put((text, is_progress))

    def finish(self, ok: bool, message: str):
        """Main thread only: flushes pending lines and shows the final result."""
        if not self._alive:
            return
        self._drain()
        self._finished = True
        self._bar.stop()
        self._bar.pack_forget()
        self._hint.pack_forget()
        icon = "✓" if ok else "✗"
        self._header.configure(
            text=f"{icon}  {self._op_title}",
            text_color=C["success"] if ok else C["danger"],
        )
        self._append("─" * 40, False)
        self._append(message, False)

    # ── Internals ──
    def _poll(self):
        if not self._alive:
            return
        self._drain()
        if not self._finished:
            self.after(self._POLL_MS, self._poll)

    def _drain(self):
        try:
            while True:
                text, is_progress = self._queue.get_nowait()
                self._append(text, is_progress)
        except queue.Empty:
            pass

    def _append(self, text: str, is_progress: bool):
        self._box.configure(state="normal")
        if self._last_is_progress:
            # Overwrite the previous in-place progress line (Git's "\r" updates)
            self._box.delete("end-1c linestart", "end-1c")
        self._box.insert("end", text if is_progress else text + "\n")
        self._box.configure(state="disabled")
        self._box.see("end")
        self._last_is_progress = is_progress

    def _close(self):
        self._alive = False
        self.destroy()


# ─── Commit dialog ────────────────────────────────────────────────────────────
class CommitDialog(BaseDialog):
    def __init__(self, master, project_name: str, callback):
        super().__init__(master)
        self.title(t("op_title_commit_push"))
        self.geometry("480x230")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.callback = callback

        ctk.CTkLabel(
            self, text=t("commit_upload_label", name=project_name),
            font=FONT_BIG, text_color=C["text"]
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            self, text=t("commit_msg_label"),
            font=FONT_LABEL, text_color=C["text_dim"]
        ).pack(padx=24, anchor="w")

        self.entry = ctk.CTkEntry(
            self, font=FONT_MONO,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            placeholder_text=t("commit_msg_placeholder"),
            height=38, corner_radius=_R_BTN
        )
        self.entry.pack(padx=24, pady=(6, 16), fill="x")
        self.entry.bind("<Return>", lambda _: self._confirm())

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, fill="x")

        ctk.CTkButton(
            row, text=t("btn_cancel"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=36, width=110
        ).pack(side="left")

        ctk.CTkButton(
            row, text=t("btn_upload"), command=self._confirm,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=_R_BTN, height=36, font=FONT_LABEL_B
        ).pack(side="right")

    def _confirm(self):
        msg = self.entry.get().strip()
        self.destroy()
        self.callback(msg)


# ─── Merge conflict dialog ─────────────────────────────────────────────────────
class MergeConflictDialog(BaseDialog):
    """Shown when the repo is left with an unresolved merge conflict."""
    def __init__(self, master, project: dict, conflicts: list[str], on_abort):
        super().__init__(master)
        self.title(t("dialog_title_merge_conflict"))
        self.geometry("480x340")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)

        ctk.CTkLabel(
            self, text=t("merge_conflict_header", name=project["name"]),
            font=FONT_BIG, text_color=C["danger"]
        ).pack(padx=24, pady=(20, 8), anchor="w")

        ctk.CTkLabel(
            self,
            text=t("merge_conflict_intro"),
            font=FONT_LABEL, text_color=C["text_dim"], justify="left"
        ).pack(padx=24, anchor="w")

        box = ctk.CTkTextbox(
            self, font=FONT_MONO_S, height=110,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1, corner_radius=_R_CARD
        )
        box.pack(fill="x", padx=24, pady=(6, 12))
        box.insert("end", "\n".join(conflicts) or t("merge_conflict_no_files"))
        box.configure(state="disabled")

        ctk.CTkLabel(
            self,
            text=t("merge_conflict_footer"),
            font=FONT_SMALL, text_color=C["text_dim"], justify="left"
        ).pack(padx=24, anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, pady=(16, 20), fill="x")

        ctk.CTkButton(
            row, text=t("btn_close"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=36, width=110
        ).pack(side="left")

        ctk.CTkButton(
            row, text=t("btn_abort_merge"), command=lambda: (self.destroy(), on_abort()),
            fg_color="#6b1a1a", hover_color=C["danger"],
            text_color="#ffffff", corner_radius=_R_BTN, height=36, font=FONT_LABEL_B
        ).pack(side="right")


# ─── Repository initialization dialog ─────────────────────────────────────────
class InitRepoDialog(BaseDialog):
    """Optionally asks for the remote URL before running git init."""
    def __init__(self, master, project_name: str, callback):
        super().__init__(master)
        self.title(t("op_title_init_repo"))
        self.geometry("500x250")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.callback = callback

        ctk.CTkLabel(
            self, text=t("init_repo_label", name=project_name),
            font=FONT_BIG, text_color=C["text"]
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            self, text=t("init_repo_url_label"),
            font=FONT_LABEL, text_color=C["text_dim"]
        ).pack(padx=24, anchor="w")

        self.entry = ctk.CTkEntry(
            self, font=FONT_MONO,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            placeholder_text=t("init_repo_url_placeholder"),
            height=38, corner_radius=_R_BTN
        )
        self.entry.pack(padx=24, pady=(6, 4), fill="x")
        self.entry.bind("<Return>", lambda _: self._confirm())

        ctk.CTkLabel(
            self, text=t("init_repo_note"),
            font=FONT_SMALL, text_color=C["text_muted"], justify="left"
        ).pack(padx=24, pady=(0, 12), anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, fill="x")

        ctk.CTkButton(
            row, text=t("btn_cancel"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=36, width=110
        ).pack(side="left")

        ctk.CTkButton(
            row, text=t("btn_init"), command=self._confirm,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=_R_BTN, height=36, font=FONT_LABEL_B
        ).pack(side="right")

    def _confirm(self):
        url = self.entry.get().strip()
        self.destroy()
        self.callback(url)


# ─── First-run setup dialog ────────────────────────────────────────────────────
class FirstRunDialog(BaseDialog):
    """
    Shown when no projects.json has been configured yet.
    Offers two explicit paths (no "cancel to get the other option" semantics).
    """
    def __init__(self, master, on_existing, on_new, on_quit):
        super().__init__(master)
        self.title(t("dialog_title_first_run"))
        self.geometry("520x400")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.transient(master)
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, self._grab_focus)
        self.protocol("WM_DELETE_WINDOW", on_quit)

        ctk.CTkLabel(
            self, text=t("first_run_welcome"),
            font=FONT_BIG, text_color=C["accent"]
        ).pack(padx=24, pady=(24, 8), anchor="w")

        ctk.CTkLabel(
            self,
            text=t("first_run_body"),
            font=FONT_LABEL, text_color=C["text_dim"], justify="left"
        ).pack(padx=24, anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, pady=(24, 8), fill="x")

        ctk.CTkButton(
            row, text=t("btn_pick_existing"), height=42,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text"], border_color=C["border"], border_width=1,
            corner_radius=_R_BTN, font=FONT_LABEL_B,
            command=lambda: (self.destroy(), on_existing())
        ).pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            row, text=t("btn_create_new"), height=42,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=_R_BTN, font=FONT_LABEL_B,
            command=lambda: (self.destroy(), on_new())
        ).pack(fill="x")

        ctk.CTkButton(
            self, text=t("btn_quit_app"), command=on_quit,
            fg_color="transparent", hover_color=C["card_hover"],
            text_color=C["text_muted"], corner_radius=_R_BTN, height=32, font=FONT_SMALL
        ).pack(pady=(16, 16))


# ─── Launcher configuration dialog ────────────────────────────────────────────
class LauncherDialog(BaseDialog):
    """Lets the user choose the executable and icon for a project's launcher."""
    def __init__(self, master, project: dict, callback):
        super().__init__(master)
        self.title(t("dialog_title_launcher"))
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
            self, text=t("launcher_title", name=self.project["name"]),
            font=FONT_BIG, text_color=C["text"]
        ).pack(padx=24, pady=(20, 14), anchor="w")

        # Executable
        ctk.CTkLabel(
            self, text=t("launcher_exe_label"),
            font=FONT_LABEL, text_color=C["text_dim"]
        ).pack(padx=24, anchor="w")

        row_exe = ctk.CTkFrame(self, fg_color="transparent")
        row_exe.pack(fill="x", padx=24, pady=(4, 12))

        ctk.CTkEntry(
            row_exe, textvariable=self._exe_var,
            font=FONT_MONO_S, fg_color=C["panel"],
            text_color=C["text"], border_color=C["border"],
            border_width=1, height=34, corner_radius=_R_BTN
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row_exe, text=t("btn_browse"), width=90, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=_R_BTN, font=FONT_SMALL,
            command=self._browse_exe
        ).pack(side="left")

        # Icon
        ctk.CTkLabel(
            self, text=t("launcher_icon_label"),
            font=FONT_LABEL, text_color=C["text_dim"]
        ).pack(padx=24, anchor="w")

        row_icon = ctk.CTkFrame(self, fg_color="transparent")
        row_icon.pack(fill="x", padx=24, pady=(4, 16))

        ctk.CTkEntry(
            row_icon, textvariable=self._icon_var,
            font=FONT_MONO_S, fg_color=C["panel"],
            text_color=C["text"], border_color=C["border"],
            border_width=1, height=34, corner_radius=_R_BTN
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row_icon, text=t("btn_browse"), width=90, height=34,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=_R_BTN, font=FONT_SMALL,
            command=self._browse_icon
        ).pack(side="left")

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24)

        ctk.CTkButton(
            btn_row, text=t("btn_cancel"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=36, width=110
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text=t("btn_clear"), command=self._clear,
            fg_color="transparent", hover_color=C["card_hover"],
            text_color=C["text_muted"], corner_radius=_R_BTN, height=36, width=90
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text=t("btn_save"), command=self._confirm,
            fg_color=C["accent_dim"], hover_color=C["accent"],
            text_color="#000000", corner_radius=_R_BTN, height=36, font=FONT_LABEL_B
        ).pack(side="right")

    def _browse_exe(self):
        path = filedialog.askopenfilename(
            title=t("launcher_browse_exe_title"),
            filetypes=[(t("filetype_all"), "*.*")]
        )
        if path:
            self._exe_var.set(path)

    def _browse_icon(self):
        path = filedialog.askopenfilename(
            title=t("launcher_browse_icon_title"),
            filetypes=[(t("filetype_images"), "*.png *.ico *.jpg *.jpeg"), (t("filetype_all_short"), "*.*")]
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


# ─── History purge dialog ──────────────────────────────────────────────────────
class PurgeDialog(BaseDialog):
    """
    Warning + selection window to remove a file or folder from the entire
    Git history.
    """
    def __init__(self, master, project: dict, callback):
        super().__init__(master)
        self.title(t("dialog_title_purge"))
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
        # Danger header
        hdr = ctk.CTkFrame(self, fg_color="#2a1010", corner_radius=_R_CARD)
        hdr.pack(fill="x", padx=20, pady=(18, 0))

        ctk.CTkLabel(
            hdr, text=t("purge_danger_title"),
            font=FONT_LABEL_B, text_color=C["danger"]
        ).pack(padx=16, pady=(12, 4), anchor="w")

        ctk.CTkLabel(
            hdr,
            text=t("purge_danger_body"),
            font=FONT_SMALL, text_color="#e8a0a0", justify="left"
        ).pack(padx=16, pady=(0, 12), anchor="w")

        ctk.CTkLabel(
            self, text=t("purge_when_to_use_title"),
            font=FONT_LABEL_B, text_color=C["warning"]
        ).pack(padx=20, pady=(14, 4), anchor="w")

        ctk.CTkLabel(
            self, text=t("purge_when_to_use_body"),
            font=FONT_SMALL, text_color=C["text"], justify="left"
        ).pack(padx=28, anchor="w")

        ctk.CTkLabel(
            self, text=t("purge_when_not_to_use_title"),
            font=FONT_LABEL_B, text_color=C["danger"]
        ).pack(padx=20, pady=(12, 4), anchor="w")

        ctk.CTkLabel(
            self, text=t("purge_when_not_to_use_body"),
            font=FONT_SMALL, text_color="#e8a0a0", justify="left"
        ).pack(padx=28, anchor="w")

        ctk.CTkLabel(
            self, text=t("purge_after_title"),
            font=FONT_LABEL_B, text_color=C["info"]
        ).pack(padx=20, pady=(12, 4), anchor="w")

        ctk.CTkLabel(
            self, text=t("purge_after_body"),
            font=FONT_MONO_S, text_color=C["text_dim"], justify="left"
        ).pack(padx=28, anchor="w")

        ctk.CTkFrame(self, fg_color=C["border"], height=1).pack(fill="x", padx=20, pady=(14, 10))

        ctk.CTkLabel(
            self, text=t("purge_what_label"),
            font=FONT_LABEL_B, text_color=C["text"]
        ).pack(padx=20, anchor="w")

        radio_row = ctk.CTkFrame(self, fg_color="transparent")
        radio_row.pack(padx=28, pady=(6, 0), anchor="w")

        ctk.CTkRadioButton(
            radio_row, text=t("purge_radio_file"), variable=self._mode,
            value="file", font=FONT_LABEL, text_color=C["text"],
            fg_color=C["accent"], border_color=C["border"],
            command=self._update_hint
        ).pack(side="left", padx=(0, 24))

        ctk.CTkRadioButton(
            radio_row, text=t("purge_radio_folder"), variable=self._mode,
            value="folder", font=FONT_LABEL, text_color=C["text"],
            fg_color=C["accent"], border_color=C["border"],
            command=self._update_hint
        ).pack(side="left")

        self.hint_label = ctk.CTkLabel(
            self, text=t("purge_hint_file"),
            font=FONT_SMALL, text_color=C["text_dim"]
        )
        self.hint_label.pack(padx=20, pady=(8, 2), anchor="w")

        entry_row = ctk.CTkFrame(self, fg_color="transparent")
        entry_row.pack(fill="x", padx=20, pady=(0, 4))

        self.path_entry = ctk.CTkEntry(
            entry_row, font=FONT_MONO,
            fg_color=C["panel"], text_color=C["text"],
            border_color=C["border"], border_width=1,
            placeholder_text=t("purge_path_placeholder"),
            height=38, corner_radius=_R_BTN
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            entry_row, text=t("btn_browse"), width=90, height=38,
            fg_color=C["panel"], hover_color=C["card_hover"],
            text_color=C["text_dim"], border_color=C["border"], border_width=1,
            corner_radius=_R_BTN, font=FONT_SMALL,
            command=self._browse
        ).pack(side="left")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(12, 16))

        ctk.CTkButton(
            btn_row, text=t("btn_cancel"), command=self.destroy,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["text"], corner_radius=_R_BTN, height=38, width=120
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text=t("btn_clean_history"), command=self._confirm,
            fg_color="#6b1a1a", hover_color=C["danger"],
            text_color=C["text"], corner_radius=_R_BTN, height=38, font=FONT_LABEL_B
        ).pack(side="right")

    def _update_hint(self):
        if self._mode.get() == "file":
            self.hint_label.configure(text=t("purge_hint_file"))
        else:
            self.hint_label.configure(text=t("purge_hint_folder"))

    def _browse(self):
        repo = self.project["path"]
        if self._mode.get() == "file":
            chosen = filedialog.askopenfilename(initialdir=repo, title=t("purge_browse_file_title"))
        else:
            chosen = filedialog.askdirectory(initialdir=repo, title=t("purge_browse_folder_title"))
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
            messagebox.showwarning(t("purge_missing_path_title"), t("purge_missing_path_body"), parent=self)
            return
        is_folder = self._mode.get() == "folder"
        kind = t("purge_type_folder") if is_folder else t("purge_type_file")
        if not messagebox.askyesno(
            t("purge_confirm_title"),
            t("purge_confirm_body", type=kind, target=target),
            parent=self
        ):
            return
        self.destroy()
        self.callback(target, is_folder)
