# 🔧 Technical README — PinkCat GitManager

> Internal reference for development, debugging, and AI-assisted work.  
> → [Presentation README](./README.md)

> **Scope:** single-user tool for organizing personal projects and launching/updating them quickly from one app. It only covers the basic Git operations (push, pull, status, log, init) — it is not a full Git client and is not built for multi-user collaboration workflows.

---

## 🤖 AI Instructions

- Wait for the author to specify what needs to be done before proceeding.
- Ask for the relevant files before making any modifications.
- All code additions (identifiers, comments, docstrings) must be written in English. No hardcoded text in any other language belongs in the source — user-facing text always goes through `src/i18n.py`'s `t(key)` (see §11).
- Git operations are isolated in `src/git_operations.py` — keep them there. Do not add Git logic anywhere in `gui/`. Result messages returned from that module are already localized via `t()` — don't format raw user-facing strings there without a translation key.
- Project persistence is handled exclusively by `src/project_manager.py` — do not add state management elsewhere. It also owns the active language and theme settings (same `%APPDATA%\PinkCatGitManager\config.json`, see §4).
- The active JSON path is stored in `%APPDATA%\PinkCatGitManager\config.json` via `src/project_manager.py`. Do not hardcode JSON paths anywhere.
- The app detects and reports merge conflicts (see §7) but must never attempt to resolve them (no auto-merge strategies, no diff/picker UI). Only "abort" or "let the user resolve manually" are valid actions.
- Keep the scope in mind (see disclaimer above) — this is deliberately a lightweight, single-user tool. Don't add multi-user/collaboration features (conflict resolution UI, branch management, PR review, etc.) unless explicitly requested.
- The `gui/` package is split by responsibility (see §1–§2). Keep new dialogs in `dialogs.py`, new detail windows in `windows.py`, and don't grow `app.py` back into a monolith — it should stay limited to `GitManagerApp` (layout + callback wiring).
- No UI file imports `gui.themes.*` directly — always go through `gui.theme_loader.get_theme()` (see §12). Colors always come from the `C` dict in `gui/theme.py`, never a hardcoded hex value in a `gui/*.py` screen file.
- Any new UI string needs a new row in `language/translations.csv` (Español + English at minimum) and must be read via `t("your_key")` — never a literal string in a widget's `text=`.

---

## 1. Project Structure

```
PinkCat GitManager/
├── PinkCat GitManager.pyw    # Entry point — launched directly (.pyw = no console window)
├── gui/
│   ├── app.py                 # GitManagerApp — main window, settings menu, layout, callback wiring
│   ├── theme.py                # Active palette (C), fonts (FONT_*), format/status helpers
│   ├── theme_loader.py          # get_theme(name) — single access point for gui/themes/*
│   ├── themes/
│   │   ├── green.py              # Terminal-green palette (this project's default/historical theme)
│   │   ├── pink.py                # Shared PinkCat Design System default theme
│   │   └── pro.py                 # Light professional theme
│   ├── base.py                 # BaseDialog — shared base class for every dialog/window
│   ├── dialogs.py               # Action dialogs: Output, Commit, MergeConflict, InitRepo,
│   │                            #   FirstRun, Launcher, Purge
│   ├── project_card.py           # ProjectCard widget
│   └── windows.py                # Detail windows: Log, GhostFiles, Changes, Gitignore
├── src/
│   ├── git_operations.py     # All Git logic: init, fetch, merge, push, status, log
│   ├── project_manager.py    # JSON read/write for the project list + app settings (JSON path, language, theme)
│   └── i18n.py                # Loads language/translations.csv, exposes t(key, **kwargs)
├── language/
│   └── translations.csv      # key;Español;English — every UI string in the app
├── ico/
│   ├── PinkCat-GitManager.ico
│   ├── PinkCat-GitManager.png
│   └── PinkCat-Mascot.png     # Mascot logo shown top-right in the title bar (§11)
├── README.md
└── README_TECH.md
```

> `gui/app.py` used to contain the entire UI (~2200 lines: every dialog, the project card, and the detail windows). It's now split by responsibility across the files above — `app.py` itself only holds `GitManagerApp` (window layout + menu + callback wiring). `gui/app.py` defensively inserts the project root into `sys.path` at import time (`if _ROOT not in sys.path: sys.path.insert(0, _ROOT)`), so `from gui.xxx import ...` and `from src import ...` resolve correctly regardless of exactly how `PinkCat GitManager.pyw` launches this module.
>
> The `data/projects.json` folder and the `.bat` launch scripts from earlier versions no longer exist. Launching is now done directly via `PinkCat GitManager.pyw`.

---

## 2. Module Responsibilities

| File | Responsibility |
|---|---|
| `PinkCat GitManager.pyw` | Entry point — launches the app with no console window |
| `gui/app.py` | `GitManagerApp` — header, settings menu (language/theme/projects file), project list, callback wiring between UI and `src/` |
| `gui/theme.py` | Active palette `C` (via `theme_loader.get_theme()`), fonts (`FONT_*`), and the `_fmt_date` / `_status_color` / `_dot_color` / `_status_label` helpers |
| `gui/theme_loader.py` | `get_theme(name)` — the only function allowed to import `gui.themes.*` |
| `gui/themes/green.py`, `pink.py`, `pro.py` | Palette dictionaries following the shared Design System key schema |
| `gui/base.py` | `BaseDialog` — focus-grabbing base class every dialog/window inherits from |
| `gui/dialogs.py` | `OutputWindow`, `CommitDialog`, `MergeConflictDialog`, `InitRepoDialog`, `FirstRunDialog`, `LauncherDialog`, `PurgeDialog` |
| `gui/project_card.py` | `ProjectCard` — the per-project card widget (header, launcher button, collapsible body, action buttons) |
| `gui/windows.py` | `LogWindow`, `GhostFilesWindow`, `ChangesWindow`, `GitignoreWindow` — detail/data-viewer windows |
| `src/git_operations.py` | All Git commands: `init`, `add -A`, `commit`, `push`, `fetch`, `merge`, `status`, `log` — result messages are localized via `src/i18n.t()` |
| `src/project_manager.py` | Load and save the active projects JSON; manage active JSON path, language, and theme via `%APPDATA%` |
| `src/i18n.py` | Loads `language/translations.csv`; exposes `t(key, **kwargs)`, `set_language()`, `get_language()` |

---

## 3. Data Format (`projects.json`)

The active JSON can be any file on disk, named however the user likes — the path is stored in `%APPDATA%\PinkCatGitManager\config.json`.

This allows using different project lists per machine or per context, by selecting a JSON from **Settings → 📁 Projects file: ...** (`GitManagerApp._change_json`, `gui/app.py`). This used to be a loose button in the header; moved into the settings menu during this audit per Design System §9 (infrequent config action, confirmed with the author instead of decided unilaterally).

There is **no automatic default location**. This is intentional (see §9, First-Run Setup): the user must explicitly pick or create the file the first time the app runs, since a common use case is pointing it at a folder synced with Google Drive/Dropbox/etc. so the list travels between computers — something the app can't guess on its own.

```json
{
  "projects": [
    {
      "id": "a1b2c3d4",
      "name": "MyRepo",
      "path": "C:/Users/user/Projects/MyRepo",
      "added_at": "2026-05-10T14:00:00",
      "last_push": "2026-05-10T14:32:00",
      "last_pull": "2026-05-09T09:15:00",
      "launcher_exe": "C:/Users/user/Projects/MyRepo/run.bat",
      "launcher_icon": "C:/Users/user/Projects/MyRepo/icon.png"
    }
  ]
}
```

`launcher_exe` and `launcher_icon` are `null` until configured by the user.  
Removing a project from the list does not affect the repository files in any way.

Writes to `projects.json` are atomic (`project_manager._save_raw`): the new content is written to a `.tmp` file in the same folder, then moved into place with `os.replace()`. This matters specifically because the file may live in a cloud-synced folder (Google Drive, Dropbox...) — a sync client should never observe a half-written file.

---

## 4. System Config (`%APPDATA%\PinkCatGitManager\config.json`)

Stored at `C:\Users\<user>\AppData\Roaming\PinkCatGitManager\config.json`.  
Created automatically on first run. Independent of where the app is installed.

```json
{
  "active_projects_file": "D:/Shared/my_projects.json",
  "language": "Español",
  "theme": "green"
}
```

If `active_projects_file` is absent or invalid, `project_manager.get_active_json_path()` returns `""` (`is_configured()` returns `False`) — by design, there is no fallback file. See §9. `language` defaults to `"Español"` and `theme` defaults to `"green"` (this project's historical palette) if absent.

**Migration from the pre-rename folder:** versions before this audit stored the same file at `%APPDATA%\GitManager\config.json` (no `PinkCat` prefix — see the audit checklist, point 12). `project_manager._migrate_legacy_config()` copies that file into the new `PinkCatGitManager` folder automatically, once, the first time the app runs after the update — the old folder is left untouched, nothing is deleted, and existing users don't need to reconfigure anything.

---

## 5. Git Operations

| Operation | Git commands |
|---|---|
| **Push** | `git add -A` → `git commit -m "<message>"` → `git push` (auto-retries with `--set-upstream origin <branch>` if the branch has no upstream yet) |
| **Pull** | `git fetch` → `git merge FETCH_HEAD` |
| **Init** | `git init` → (optional) `git remote add origin <url>` |
| **Status** | `git status` (modified files + unpushed commits) |
| **Log** | `git log` (last 20 commits) |
| **Merge conflict check** | `os.path.isfile(".git/MERGE_HEAD")` — detects an unresolved merge left by Pull |
| **Merge abort** | `git merge --abort` — reverts to the pre-Pull state |

`_push()` centralizes the actual `git push` call. If Git refuses with "has no upstream branch" (typical on a repo's first push, or right after `git init` + `remote add`), it retries once with `git push --set-upstream origin <current-branch>` instead of surfacing the raw error.

`do_add_commit_push()` always attempts the push, even when there's "nothing to commit" — local commits that were never pushed still need to go out.

---

## 6. Launcher Button

Each project card shows a launcher button in the header (between the status dot and the project name).

| State | Icon | Left click | Right click |
|---|---|---|---|
| Not configured | ⚙ (grey) | Open config dialog | Open config dialog |
| Configured, no image | ▶ (green) | Launch the file | Open config dialog |
| Configured, with image | Custom icon | Launch the file | Open config dialog |

- **Any file type** is supported: `.exe`, `.bat`, `.pyw`, or anything Windows can open.
- Launching uses `os.startfile()`, which delegates to the Windows shell (same as double-clicking in Explorer).
- The icon image (`.png`, `.ico`, `.jpg`) is rendered at 44×44 px using `pillow`. Without `pillow` installed, the ▶ symbol is shown instead.
- Configuration is saved to the active projects JSON (`launcher_exe`, `launcher_icon`).
- Hovering over the button shows a tooltip with the filename and available actions.

---

## 7. Merge Conflict Handling

The app **never resolves merge conflicts automatically**. It only detects when a Pull left one unresolved and gives the user two safe exits.

**Detection (`src/git_operations.py`):**

| Function | Purpose |
|---|---|
| `is_merging(path)` | Checks for `.git/MERGE_HEAD` — True while a merge is unresolved |
| `get_conflicted_files(path)` | `git diff --name-only --diff-filter=U` — lists files still in conflict |
| `do_merge_abort(path)` | `git merge --abort` — cancels the merge, repo returns to its pre-Pull state |

`do_merge()` itself checks `is_merging()` after a failed merge and, if a real conflict is in progress, returns the list of conflicted files instead of Git's raw stderr.

**Flow in `gui/app.py`:**

1. `ProjectCard.refresh_status()` checks `is_merging()` before running the normal status worker. If true, the card shows a red dot and the `card_merge_conflict_status` string ("⚠ Unresolved merge conflict") — visible without the user doing anything.
2. `_do_pull()` and `_do_push()` both check `is_merging()` first. If a conflict is already open, they call `_warn_merge_conflict()` instead of running the Git command.
3. If a Pull *causes* a new conflict, `_after_conflict()` intercepts the failed result and opens `MergeConflictDialog` directly (instead of the generic `OutputWindow`).
4. `MergeConflictDialog` lists the conflicted files and offers:
   - **Close** (`btn_close`) — leave it for the user to resolve manually (editor/terminal).
   - **Abort merge** (`btn_abort_merge`) — calls `do_merge_abort()` and refreshes the card.

No conflict-resolution UI (diff view, "ours/theirs" picker, etc.) exists or is planned — this is intentionally out of scope. See AI Instructions.

---

## 8. Repository Initialization

If a project's folder has no `.git` directory, the card shows a **"⚡ Initialize repository"** button (`card_init_repo_btn`) instead of Push/Pull.

**`src/git_operations.py`:**

| Function | Purpose |
|---|---|
| `init_repo(path)` | `git init` |
| `add_remote(path, url, name="origin")` | Adds the remote, or `set-url` if it already exists |
| `init_repo_with_remote(path, remote_url="")` | Runs `init_repo`, then `add_remote` only if a URL was given |

**Flow in `gui/app.py`:**

1. `_do_init()` opens `InitRepoDialog`, asking for a remote URL (optional — empty is valid, leaves the repo local-only).
2. On confirm, `init_repo_with_remote()` runs in a background thread.
3. `_after_init()` calls `_load_projects()` on success — the project list itself doesn't change, but `has_git_repo()` now returns `True`, so the card is rebuilt with the full Push/Pull/Log button set instead of the init button.

No first commit is made automatically — the user still triggers that via the normal Push flow (`git add -A` + commit + push) once ready.

---

## 9. First-Run Setup

There is no automatic default `projects.json` location (see §3–§4) — this is a deliberate design choice, not a gap. The user must explicitly configure it, because the intended use case (a folder synced with Google Drive/Dropbox/etc. so the list travels between computers) is something the app has no way to guess.

**`gui/dialogs.py` — `FirstRunDialog`:**

A `BaseDialog` with two explicit choices (no "cancel to get the other option" semantics):
- **"📂 I already have a projects file"** (`btn_pick_existing`) → open an existing JSON.
- **"✚ Create a new one"** (`btn_create_new`) → choose name + location for a new one (any filename works, `projects.json` is only the suggested default).
- **"Quit Git Manager"** (`btn_quit_app`) → confirms, then quits.

**Flow in `gui/app.py` — `GitManagerApp._first_run_setup()`:**

1. Called from `__init__` only when `pm.is_configured()` is `False`, *before* `_build_ui()` / `_load_projects()`.
2. Loops showing `FirstRunDialog` (via `self.wait_window(dialog)`) until `pm.is_configured()` becomes `True`. Canceling a file picker, or answering "No" to quit, just re-shows the same dialog — no dead ends.
3. `__init__` wraps `_build_ui()` / `_load_projects()` in a `try/except` that shows the error in a `messagebox` (with traceback) instead of crashing silently — added after an early version crashed with no visible error message during this flow.

⚠ Do not call `self.withdraw()` / `self.deiconify()` around this flow — an earlier version did, to hide the main window during setup, and it caused CustomTkinter to crash the app right after configuring (root cause not fully diagnosed, but reproducible). The window staying visible-but-empty behind the dialogs during setup is expected and harmless.

---

## 10. Internationalization (i18n)

All UI text lives in `language/translations.csv` — one row per key, one column per language (`key;Español;English`). Loaded once at import time by `src/i18n.py`.

| Function | Purpose |
|---|---|
| `t(key, **kwargs)` | Returns the string for `key` in the active language, formatting `{placeholder}` fields with `kwargs`. Falls back to Español, then to the raw key, if missing. |
| `set_language(lang)` | Switches the active language (`"Español"` or `"English"`). |
| `get_language()` | Returns the currently active language name. |

- Multi-line values are stored with a literal `\n` inside the CSV cell (not a real line break, so the row stays on one CSV line) — `t()` unescapes it to a real newline before returning.
- `gui/app.py` calls `i18n.set_language(pm.get_active_language())` once, immediately after importing `src.i18n` and before any dialog/window is built.
- `src/git_operations.py` calls `t()` directly to build its returned result messages, so Git logic stays in `src/` while its output is still fully localized — the `gui/` layer just displays whatever string it gets back, unchanged.
- The active language is switched from **Settings → Language** in the menu bar (`gui/app.py::_build_menu`) and persisted via `project_manager.set_active_language()`. Per Design System §10, this applies **live, without restarting** — see §11.

---

## 11. Theme System & Settings Menu

Palette handling follows the shared `PinkCat_Design_System.md`: `gui/theme_loader.get_theme(name)` is the only function that imports a `gui/themes/*` module; every screen imports the resolved `C` dict from `gui/theme.py` instead.

| Theme | File | Notes |
|---|---|---|
| `green` (default here) | `gui/themes/green.py` | This project's original terminal-green look; the Design System's historical reference palette. |
| `pink` | `gui/themes/pink.py` | Shared PinkCat default theme. |
| `pro` | `gui/themes/pro.py` | Light, professional theme — no dark variant. |

Each theme dict exposes exactly the shared key schema: `bg`, `panel`, `card`, `card_hover`, `border`, `accent`, `accent_dim`, `success`, `danger`, `warning`, `info`, `text`, `text_dim`, `text_muted`, `corner_radius_card`, `corner_radius_btn`. `gui/theme.py` also derives the mono/title font family from the active theme (Consolas for Green/Pink, Segoe UI only for Pro) — absolute sizes stay a project concern, not a theme one.

⚠ **Non-negotiable rule (Design System §3):** `success`/`danger`/`warning`/`info` are a fixed semantic palette — a status helper must never return `accent`/`accent_dim` for an "ok"/positive state. `gui/theme.py::_status_color()` / `_dot_color()` and every "operation succeeded" indicator across `gui/dialogs.py` and `gui/windows.py` return `C["success"]`, not `C["accent"]`. This matters in practice: in the `green` theme `accent` and `success` happen to share the same hex value, so a regression here is invisible until the user switches to `pink` or `pro` — always verify status colors under a non-`green` theme, not just the default one.

**Settings menu** (`gui/app.py::_build_menu`): a classic top menu bar (`tk.Menu`) with **Settings → Language** and **Settings → Theme** submenus, each a radio-button list.

**Language switches live (Design System §10) — theme does not:**
- `GitManagerApp._change_language()` persists the choice via `project_manager.set_active_language()`, flips `src.i18n`'s active language immediately (`i18n.set_language()`), then calls `GitManagerApp.refresh_language()`, which re-reads every visible widget's `text=` with `t()` — the window title, header title/buttons, empty-list message, status bar, the `menu_settings`/`menu_language`/`menu_theme` cascade labels and the theme radio labels (`entryconfigure(..., label=...)`), and `ProjectCard.refresh_language()` on every card (buttons, push/pull date labels, the launcher tooltip via `refresh_launcher_btn()`, and the status label/dot via `refresh_status()`). No widget is destroyed or recreated.
  - ⚠ The top-level `menubar = tk.Menu(self, tearoff=0)` **must** keep `tearoff=0`. Without it, Tk reserves index 0 for an invisible tearoff pseudo-entry and the `Settings` cascade shifts to index 1, silently breaking `entryconfigure(0, ...)` (`_tkinter.TclError: unknown option "-label"`) — this exact regression was caught by a smoke test while implementing live language switching.
- `GitManagerApp._change_theme()` persists via `project_manager.set_active_theme()` and shows a "restart required" `messagebox` instead — this is a deliberate choice, not a gap: `C`, `FONT_*`, and every widget's colors are resolved once at import/build time, and rebuilding every screen's palette in place was judged not worth the complexity for a single-user tool (Design System §10).

**PinkCat mascot logo** (`GitManagerApp._build_logo`, in `gui/app.py`): rendered from `ico/PinkCat-Mascot.png`, packed first among the header's right-side widgets so it always sits in the outermost top-right corner of the title bar — outside the settings menu, independent of the active theme, per Design System §8–§9. Loaded via Pillow and downscaled to `_LOGO_SIZE` (44px) with `Image.thumbnail()`. If Pillow isn't installed or the file is missing, it falls back to a 🐾 emoji instead of disappearing entirely — the brand mark itself must never be fully absent, only its rendering degrades.

---

## 12. Pending Tasks

- [ ] None currently tracked
