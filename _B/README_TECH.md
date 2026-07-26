# 🔧 Technical README — Git Manager

> Internal reference for development, debugging, and AI-assisted work.  
> → [Presentation README](./README.md)

---

## 🤖 AI Instructions

- Wait for the author to specify what needs to be done before proceeding.
- Ask for the relevant files before making any modifications.
- Git operations are isolated in `git_operations.py` — keep them there. Do not add Git logic to `app.py`.
- Project persistence is handled exclusively by `project_manager.py` via `data/projects.json` — do not add state management elsewhere.

---

## 1. Project Structure

```
GitManager/
├── app.py                  # Main GUI (CustomTkinter)
├── git_operations.py       # All Git logic: fetch, merge, push, status, log
├── project_manager.py      # JSON read/write for the project list
├── data/
│   └── projects.json       # Saved project paths and dates
├── ejecutar.bat            # Launch script
└── instalar_y_ejecutar.bat # First-run: install dependencies + launch
```

---

## 2. Module Responsibilities

| File | Responsibility |
|---|---|
| `app.py` | CustomTkinter GUI — project cards, buttons, status display |
| `git_operations.py` | All Git commands: `add -A`, `commit`, `push`, `fetch`, `merge`, `status`, `log` |
| `project_manager.py` | Load and save `data/projects.json` (project paths and last push/pull dates) |

---

## 3. Data Format (`data/projects.json`)

Stores only paths and dates — never file contents or Git objects.

```json
[
  {
    "path": "C:/Users/user/Projects/MyRepo",
    "last_push": "2026-05-10T14:32:00",
    "last_pull": "2026-05-09T09:15:00",
    "launcher_exe": "C:/Users/user/Projects/MyRepo/run.bat",
    "launcher_icon": "C:/Users/user/Projects/MyRepo/icon.png"
  }
]
```

`launcher_exe` and `launcher_icon` are `null` until configured by the user.  
Removing a project from this list does not affect the repository files in any way.

---

## 4. Git Operations

| Operation | Git commands |
|---|---|
| **Push** | `git add -A` → `git commit -m "<message>"` → `git push` |
| **Pull** | `git fetch` → `git merge FETCH_HEAD` |
| **Status** | `git status` (modified files + unpushed commits) |
| **Log** | `git log` (last 20 commits) |

---

## 5. Launcher Button

Each project card shows a launcher button in the header (between the status dot and the project name).

| State | Icon | Left click | Right click |
|---|---|---|---|
| Not configured | ⚙ (grey) | Open config dialog | Open config dialog |
| Configured, no image | ▶ (green) | Launch the file | Open config dialog |
| Configured, with image | Custom icon | Launch the file | Open config dialog |

- **Any file type** is supported: `.exe`, `.bat`, `.pyw`, or anything Windows can open.
- Launching uses `os.startfile()`, which delegates to the Windows shell (same as double-clicking in Explorer).
- The icon image (`.png`, `.ico`, `.jpg`) is rendered at 44×44 px using `pillow`. Without `pillow` installed, the ▶ symbol is shown instead.
- Configuration is saved to `data/projects.json` (`launcher_exe`, `launcher_icon`).
- Hovering over the button shows a tooltip with the filename and available actions.

---

## 6. Pending Tasks

- [ ] None currently tracked
