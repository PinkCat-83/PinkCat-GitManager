# 🔧 Technical README — Git Manager

> Internal reference for development, debugging, and AI-assisted work.  
> → [Presentation README](./README.md)

---

## 🤖 AI Instructions

- Wait for the author to specify what needs to be done before proceeding.
- Ask for the relevant files before making any modifications.
- Git operations are isolated in `git_operations.py` — keep them there. Do not add Git logic to `app.py`.
- Project persistence is handled exclusively by `project_manager.py` — do not add state management elsewhere.
- The active JSON path is stored in `%APPDATA%\GitManager\config.json` via `project_manager.py`. Do not hardcode JSON paths anywhere.
- The app detects and reports merge conflicts (see §7) but must never attempt to resolve them (no auto-merge strategies, no diff/picker UI). Only "abort" or "let the user resolve manually" are valid actions.

---

## 1. Project Structure

```
GitManager/
├── app.py                  # Main GUI (CustomTkinter)
├── git_operations.py       # All Git logic: fetch, merge, push, status, log
├── project_manager.py      # JSON read/write for the project list + active JSON config
├── data/
│   └── projects.json       # Default project list (can be overridden per machine)
├── ejecutar.bat            # Launch script
└── instalar_y_ejecutar.bat # First-run: install dependencies + launch
```

---

## 2. Module Responsibilities

| File | Responsibility |
|---|---|
| `app.py` | CustomTkinter GUI — project cards, buttons, status display |
| `git_operations.py` | All Git commands: `add -A`, `commit`, `push`, `fetch`, `merge`, `status`, `log` |
| `project_manager.py` | Load and save the active projects JSON; manage which JSON is active via `%APPDATA%` |

---

## 3. Data Format (`projects.json`)

The active JSON can be any file on disk — the path is stored in `%APPDATA%\GitManager\config.json`. If no override is configured, the app falls back to `data/projects.json`.

This allows using different project lists per machine or per context, by selecting a JSON from the `📁` button in the header.

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

---

## 4. System Config (`%APPDATA%\GitManager\config.json`)

Stored at `C:\Users\<user>\AppData\Roaming\GitManager\config.json`.  
Created automatically on first run. Independent of where the app is installed.

```json
{
  "active_projects_file": "D:/Shared/my_projects.json"
}
```

If `active_projects_file` is absent or invalid, the app uses `data/projects.json` as default.

---

## 5. Git Operations

| Operation | Git commands |
|---|---|
| **Push** | `git add -A` → `git commit -m "<message>"` → `git push` |
| **Pull** | `git fetch` → `git merge FETCH_HEAD` |
| **Init** | `git init` → (optional) `git remote add origin <url>` |
| **Status** | `git status` (modified files + unpushed commits) |
| **Log** | `git log` (last 20 commits) |
| **Merge conflict check** | `os.path.isfile(".git/MERGE_HEAD")` — detects an unresolved merge left by Pull |
| **Merge abort** | `git merge --abort` — reverts to the pre-Pull state |

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

**Detection (`git_operations.py`):**

| Function | Purpose |
|---|---|
| `is_merging(path)` | Checks for `.git/MERGE_HEAD` — True while a merge is unresolved |
| `get_conflicted_files(path)` | `git diff --name-only --diff-filter=U` — lists files still in conflict |
| `do_merge_abort(path)` | `git merge --abort` — cancels the merge, repo returns to its pre-Pull state |

`do_merge()` itself checks `is_merging()` after a failed merge and, if a real conflict is in progress, returns the list of conflicted files instead of Git's raw stderr.

**Flow in `app.py`:**

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

**`git_operations.py`:**

| Function | Purpose |
|---|---|
| `init_repo(path)` | `git init` |
| `add_remote(path, url, name="origin")` | Adds the remote, or `set-url` if it already exists |
| `init_repo_with_remote(path, remote_url="")` | Runs `init_repo`, then `add_remote` only if a URL was given |

**Flow in `app.py`:**

1. `_do_init()` opens `InitRepoDialog`, asking for a remote URL (optional — empty is valid, leaves the repo local-only).
2. On confirm, `init_repo_with_remote()` runs in a background thread.
3. `_after_init()` calls `_load_projects()` on success — the project list itself doesn't change, but `has_git_repo()` now returns `True`, so the card is rebuilt with the full Push/Pull/Log button set instead of the init button.

No first commit is made automatically — the user still triggers that via the normal Push flow (`git add -A` + commit + push) once ready.

---

## 9. Pending Tasks

- [ ] None currently tracked
