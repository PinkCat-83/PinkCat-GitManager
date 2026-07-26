# 🔧 Technical README — Git Manager

> Internal reference for development, debugging, and AI-assisted work.  
> → [Presentation README](./README.md)

> **Scope:** single-user tool for organizing personal projects and launching/updating them quickly from one app. It only covers the basic Git operations (push, pull, status, log, init) — it is not a full Git client and is not built for multi-user collaboration workflows.

---

## 🤖 AI Instructions

- Wait for the author to specify what needs to be done before proceeding.
- Ask for the relevant files before making any modifications.
- Git operations are isolated in `src/git_operations.py` — keep them there. Do not add Git logic anywhere in `gui/`.
- Project persistence is handled exclusively by `src/project_manager.py` — do not add state management elsewhere.
- The active JSON path is stored in `%APPDATA%\GitManager\config.json` via `src/project_manager.py`. Do not hardcode JSON paths anywhere.
- The app detects and reports merge conflicts (see §7) but must never attempt to resolve them (no auto-merge strategies, no diff/picker UI). Only "abort" or "let the user resolve manually" are valid actions.
- Keep the scope in mind (see disclaimer above) — this is deliberately a lightweight, single-user tool. Don't add multi-user/collaboration features (conflict resolution UI, branch management, PR review, etc.) unless explicitly requested.
- The `gui/` package is split by responsibility (see §1–§2). Keep new dialogs in `dialogs.py`, new detail windows in `windows.py`, and don't grow `app.py` back into a monolith — it should stay limited to `GitManagerApp` (layout + callback wiring).

---

## 1. Project Structure

```
GitManager/
├── GitManager.pyw           # Entry point — launched directly (.pyw = no console window)
├── gui/
│   ├── app.py                 # GitManagerApp — main window, layout, callback wiring
│   ├── theme.py                # Color palette (C), fonts (FONT_*), format/status helpers
│   ├── base.py                 # BaseDialog — shared base class for every dialog/window
│   ├── dialogs.py               # Action dialogs: Output, Commit, MergeConflict, InitRepo,
│   │                            #   FirstRun, Launcher, Purge
│   ├── project_card.py           # ProjectCard widget
│   └── windows.py                # Detail windows: Log, GhostFiles, Changes, Gitignore
├── src/
│   ├── git_operations.py     # All Git logic: init, fetch, merge, push, status, log
│   └── project_manager.py    # JSON read/write for the project list + active JSON config
├── ico/
│   ├── PinkCat-GuitManager.ico
│   └── PinkCat-GuitManager.png
├── README.md
└── README_TECH.md
```

> `gui/app.py` used to contain the entire UI (~2200 lines: every dialog, the project card, and the detail windows). It's now split by responsibility across the six files above — `app.py` itself only holds `GitManagerApp` (window layout + callback wiring). `gui/app.py` defensively inserts the project root into `sys.path` at import time (`if _ROOT not in sys.path: sys.path.insert(0, _ROOT)`), so `from gui.xxx import ...` and `from src import ...` resolve correctly regardless of exactly how `GitManager.pyw` launches this module.
>
> The `data/projects.json` folder and the `.bat` launch scripts from earlier versions no longer exist. Launching is now done directly via `GitManager.pyw`.

---

## 2. Module Responsibilities

| File | Responsibility |
|---|---|
| `GitManager.pyw` | Entry point — launches the app with no console window |
| `gui/app.py` | `GitManagerApp` — header, project list, callback wiring between UI and `src/` |
| `gui/theme.py` | Color palette `C`, fonts (`FONT_*`), and the `_fmt_date` / `_status_color` / `_dot_color` / `_status_label` helpers |
| `gui/base.py` | `BaseDialog` — focus-grabbing base class every dialog/window inherits from |
| `gui/dialogs.py` | `OutputWindow`, `CommitDialog`, `MergeConflictDialog`, `InitRepoDialog`, `FirstRunDialog`, `LauncherDialog`, `PurgeDialog` |
| `gui/project_card.py` | `ProjectCard` — the per-project card widget (header, launcher button, collapsible body, action buttons) |
| `gui/windows.py` | `LogWindow`, `GhostFilesWindow`, `ChangesWindow`, `GitignoreWindow` — detail/data-viewer windows |
| `src/git_operations.py` | All Git commands: `init`, `add -A`, `commit`, `push`, `fetch`, `merge`, `status`, `log` |
| `src/project_manager.py` | Load and save the active projects JSON; manage which JSON is active via `%APPDATA%` |

---

## 3. Data Format (`projects.json`)

The active JSON can be any file on disk, named however the user likes — the path is stored in `%APPDATA%\GitManager\config.json`.

This allows using different project lists per machine or per context, by selecting a JSON from the `📁` button in the header.

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

## 4. System Config (`%APPDATA%\GitManager\config.json`)

Stored at `C:\Users\<user>\AppData\Roaming\GitManager\config.json`.  
Created automatically on first run. Independent of where the app is installed.

```json
{
  "active_projects_file": "D:/Shared/my_projects.json"
}
```

If `active_projects_file` is absent or invalid, `project_manager.get_active_json_path()` returns `""` (`is_configured()` returns `False`) — by design, there is no fallback file. See §9.

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

1. `ProjectCard.refresh_status()` checks `is_merging()` before running the normal status worker. If true, the card shows a red dot and "⚠ Conflicto de merge sin resolver" — visible without the user doing anything.
2. `_do_pull()` and `_do_push()` both check `is_merging()` first. If a conflict is already open, they call `_warn_merge_conflict()` instead of running the Git command.
3. If a Pull *causes* a new conflict, `_after_conflict()` intercepts the failed result and opens `MergeConflictDialog` directly (instead of the generic `OutputWindow`).
4. `MergeConflictDialog` lists the conflicted files and offers:
   - **Cerrar** — leave it for the user to resolve manually (editor/terminal).
   - **Abortar merge** — calls `do_merge_abort()` and refreshes the card.

No conflict-resolution UI (diff view, "ours/theirs" picker, etc.) exists or is planned — this is intentionally out of scope. See AI Instructions.

---

## 8. Repository Initialization

If a project's folder has no `.git` directory, the card shows an **"⚡ Inicializar repositorio"** button instead of Push/Pull.

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
- **"📂 Ya tengo un archivo de proyectos"** → open an existing JSON.
- **"✚ Crear uno nuevo"** → choose name + location for a new one (any filename works, `projects.json` is only the suggested default).
- **"Salir de Git Manager"** → confirms, then quits.

**Flow in `gui/app.py` — `GitManagerApp._first_run_setup()`:**

1. Called from `__init__` only when `pm.is_configured()` is `False`, *before* `_build_ui()` / `_load_projects()`.
2. Loops showing `FirstRunDialog` (via `self.wait_window(dialog)`) until `pm.is_configured()` becomes `True`. Canceling a file picker, or answering "No" to quit, just re-shows the same dialog — no dead ends.
3. `__init__` wraps `_build_ui()` / `_load_projects()` in a `try/except` that shows the error in a `messagebox` (with traceback) instead of crashing silently — added after an early version crashed with no visible error message during this flow.

⚠ Do not call `self.withdraw()` / `self.deiconify()` around this flow — an earlier version did, to hide the main window during setup, and it caused CustomTkinter to crash the app right after configuring (root cause not fully diagnosed, but reproducible). The window staying visible-but-empty behind the dialogs during setup is expected and harmless.

---

## 10. Pending Tasks

- [ ] None currently tracked
