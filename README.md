# ◈ PinkCat GitManager

Visual Git repository manager for Windows. Built with CustomTkinter.

> **Scope note:** this tool is built for a single user, as a way to organize your projects and reach them quickly from one app. It covers the most common Git operations (push, pull, status, log) — it is not meant as a full Git client or for multi-user collaboration workflows (conflict resolution, advanced branch management, pull request review, etc.).

---

## What is this?

A simple GUI for the Git operations used most often — push, pull, status, and log — so you never have to touch the command line.

---

## Requirements

- Python 3.10+
- Git installed and in the system PATH
- `pip install customtkinter pillow`
- Spanish and English available from the **Settings → Language** menu — applies immediately, no restart needed. The theme (Green / Pink / Pro) is switchable from **Settings → Theme**, but that one does need a restart to apply.

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
PinkCat GitManager/
├── PinkCat GitManager.pyw    # Entry point — double-click to launch
├── gui/
│   ├── app.py                 # Main window (GitManagerApp) — layout, menu & callback wiring
│   ├── theme.py                # Active color palette, fonts, status/format helpers
│   ├── theme_loader.py          # get_theme(name) — single access point for gui/themes/*
│   ├── themes/                  # green.py / pink.py / pro.py palettes
│   ├── base.py                 # Shared base class for all dialogs
│   ├── dialogs.py               # Action dialogs (commit, conflict, init, first-run, launcher, purge)
│   ├── project_card.py          # The project card widget
│   └── windows.py                # Detail windows (log, ghost files, changes, .gitignore)
├── src/
│   ├── git_operations.py     # Git logic (init, fetch, merge, push, status…)
│   ├── project_manager.py    # Project JSON management + app settings (language, theme)
│   └── i18n.py                # Loads language/translations.csv, exposes t(key)
├── language/
│   └── translations.csv      # UI text, one row per key, one column per language
├── ico/
│   ├── PinkCat-GitManager.ico
│   ├── PinkCat-GitManager.png
│   └── PinkCat-Mascot.png     # Mascot logo shown top-right in the title bar
├── README.md
└── README_TECH.md
```

---

## Notes

- There is no automatic default location for the project list — the first time you run the app, it asks you to pick an existing `projects.json` or create a new one. The file can be named anything you like, and you can keep several (e.g. `work.json`, `personal.json`) by switching from **Settings → 📁 Projects file** in the menu.
- The project list is stored as JSON — it only holds paths and dates, and never moves or deletes the files it references.
- Removing a project from the list **does not delete** its files.
- `pillow` is required to display custom launcher icons. Without it the launcher still works, showing a ▶ symbol instead.
- If a Pull results in a merge conflict, the app does not resolve it — it shows the affected files and lets you either abort the merge (back to the pre-Pull state) or resolve it manually outside the app. While a conflict is unresolved, Pull and Push are disabled for that project.

---

## Technical Documentation

→ [Technical README](./README_TECH.md)
