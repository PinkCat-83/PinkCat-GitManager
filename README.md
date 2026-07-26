# ◈ Git Manager

Visual Git repository manager for Windows. Built with CustomTkinter.

> **Nota de alcance:** esta herramienta está pensada para un único usuario, como forma de organizar sus proyectos y acceder a ellos rápidamente desde una sola aplicación. Cubre las operaciones de Git más básicas (push, pull, status, log) — no está diseñada como cliente Git completo ni para flujos de colaboración multiusuario (resolución de conflictos, gestión de ramas avanzada, revisión de pull requests, etc.).

---

## What is this?

A simple GUI for the Git operations used most often — push, pull, status, and log — so you never have to touch the command line.

---

## Requirements

- Python 3.10+
- Git installed and in the system PATH
- `pip install customtkinter pillow`

---

## Getting Started

```
GitManager.pyw
```
Double-click to launch (no console window). Make sure the requirements below are installed first.

---

## Features

- **Add projects** by folder — auto-detects if a `.git` directory is present
- **Manual project-list location** — on first run, you choose (or create) the `projects.json` file yourself; point it at a folder synced with Google Drive, Dropbox, etc. to share your project list across computers
- **Initialize a repository** — if a project has no `.git`, a button lets you run `git init` directly, optionally setting the remote `origin` URL in the same dialog
- **Real-time status** — modified files and unpushed commits
- **Push** — `add -A` + commit with message + push, with a confirmation window
- **Pull** — fetch + merge FETCH_HEAD
- **Merge conflict detection** — if a Pull leaves a conflict, the app detects it and warns you (it does not resolve it automatically)
- **Log** — last 20 commits
- **Last push / pull dates** per project
- **Current branch** shown on each project card
- **Launcher button** — configure an executable and icon per project; click to launch directly from the card

---

## File Structure

```
GitManager/
├── GitManager.pyw           # Entry point — double-click to launch
├── gui/
│   ├── app.py                 # Main window (GitManagerApp) — layout & callback wiring
│   ├── theme.py                # Color palette, fonts, status/format helpers
│   ├── base.py                 # Shared base class for all dialogs
│   ├── dialogs.py               # Action dialogs (commit, conflict, init, first-run, launcher, purge)
│   ├── project_card.py          # The project card widget
│   └── windows.py                # Detail windows (log, ghost files, changes, .gitignore)
├── src/
│   ├── git_operations.py     # Git logic (init, fetch, merge, push, status…)
│   └── project_manager.py    # Project JSON management
├── ico/
│   ├── PinkCat-GuitManager.ico
│   └── PinkCat-GuitManager.png
├── README.md
└── README_TECH.md
```

---

## Notes

- There is no automatic default location for the project list — the first time you run the app, it asks you to pick an existing `projects.json` or create a new one. The file can be named anything you like, and you can keep several (e.g. `work.json`, `personal.json`) by switching with the 📁 button in the header.
- The project list is stored as JSON — it only holds paths and dates, and never moves or deletes the files it references.
- Removing a project from the list **does not delete** its files.
- `pillow` is required to display custom launcher icons. Without it the launcher still works, showing a ▶ symbol instead.
- If a Pull results in a merge conflict, the app does not resolve it — it shows the affected files and lets you either abort the merge (back to the pre-Pull state) or resolve it manually outside the app. While a conflict is unresolved, Pull and Push are disabled for that project.

---

## Technical Documentation

→ [Technical README](./README_TECH.md)
