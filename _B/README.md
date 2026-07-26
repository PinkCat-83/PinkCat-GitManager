# ◈ Git Manager

Visual Git repository manager for Windows. Built with CustomTkinter.

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

**First time:**
```
instalar_y_ejecutar.bat
```
Installs dependencies and launches the app.

**After that:**
```
ejecutar.bat
```
or `python app.py` directly.

---

## Features

- **Add projects** by folder — auto-detects if a `.git` directory is present
- **Real-time status** — modified files and unpushed commits
- **Push** — `add -A` + commit with message + push, with a confirmation window
- **Pull** — fetch + merge FETCH_HEAD
- **Log** — last 20 commits
- **Last push / pull dates** per project
- **Current branch** shown on each project card
- **Launcher button** — configure an executable and icon per project; click to launch directly from the card

---

## File Structure

```
GitManager/
├── app.py                  # Main GUI
├── git_operations.py       # Git logic (fetch, merge, push, status…)
├── project_manager.py      # Project JSON management
├── data/
│   └── projects.json       # Saved project list
├── ejecutar.bat
└── instalar_y_ejecutar.bat
```

---

## Notes

- `data/projects.json` stores only paths and dates — it never moves or deletes files.
- Removing a project from the list **does not delete** its files.
- `pillow` is required to display custom launcher icons. Without it the launcher still works, showing a ▶ symbol instead.

---

## Technical Documentation

→ [Technical README](./README_TECH.md)
