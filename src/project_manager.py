"""
project_manager.py
Management of the projects JSON: load, save, add, remove.

The active JSON path is configured MANUALLY by the user (e.g. a folder synced
with Google Drive, Dropbox, etc., so the project list travels between several
computers). There is no automatic default path: if none has been configured
yet, the app must ask the user where the file will live before it can load or
save anything (see GitManagerApp._first_run_setup in gui/app.py).
"""

import json
import os
import shutil
from datetime import datetime

# System configuration: %APPDATA%\PinkCatGitManager\config.json
# Exists per Windows user account, independent of where the app itself lives.
# This part IS automatic — it only stores a pointer to where the real
# projects.json lives, never the project data itself.
_APPDATA_ROOT = os.getenv("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
_APPDATA_DIR = os.path.join(_APPDATA_ROOT, "PinkCatGitManager")
_APP_CONFIG = os.path.join(_APPDATA_DIR, "config.json")

# Folder used by versions prior to the "PinkCat" naming convention (point 12
# of the audit checklist). Migrated automatically on first run so existing
# users don't have to reconfigure the app.
_LEGACY_APPDATA_DIR = os.path.join(_APPDATA_ROOT, "GitManager")
_LEGACY_APP_CONFIG = os.path.join(_LEGACY_APPDATA_DIR, "config.json")


def _migrate_legacy_config() -> None:
    """One-time copy of the pre-rename config.json into the new PinkCat-prefixed folder."""
    if os.path.exists(_APP_CONFIG) or not os.path.exists(_LEGACY_APP_CONFIG):
        return
    try:
        os.makedirs(_APPDATA_DIR, exist_ok=True)
        shutil.copyfile(_LEGACY_APP_CONFIG, _APP_CONFIG)
    except OSError:
        pass


_migrate_legacy_config()


# ─── System configuration (active JSON, language, theme) ─────────────────────

def _load_app_config() -> dict:
    os.makedirs(_APPDATA_DIR, exist_ok=True)
    if not os.path.exists(_APP_CONFIG):
        return {}
    try:
        with open(_APP_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_app_config(cfg: dict) -> None:
    os.makedirs(_APPDATA_DIR, exist_ok=True)
    with open(_APP_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_active_json_path() -> str:
    """Returns the path of the currently active projects JSON, or "" if none was chosen yet."""
    cfg = _load_app_config()
    path = cfg.get("active_projects_file", "")
    if path and os.path.isabs(path):
        return path
    return ""


def is_configured() -> bool:
    """True if the user has already chosen a projects.json path."""
    return bool(get_active_json_path())


def set_active_json_path(path: str) -> None:
    """Changes the active JSON and persists it to config.json."""
    cfg = _load_app_config()
    cfg["active_projects_file"] = os.path.normpath(os.path.abspath(path))
    _save_app_config(cfg)


def get_active_language() -> str:
    """Returns the active UI language name (see src/i18n.py), defaulting to Español."""
    cfg = _load_app_config()
    return cfg.get("language", "Español")


def set_active_language(language: str) -> None:
    cfg = _load_app_config()
    cfg["language"] = language
    _save_app_config(cfg)


def get_active_theme() -> str:
    """Returns the active theme name (see gui/theme_loader.py), defaulting to green."""
    cfg = _load_app_config()
    return cfg.get("theme", "green")


def set_active_theme(theme: str) -> None:
    cfg = _load_app_config()
    cfg["theme"] = theme
    _save_app_config(cfg)


# ─── Projects JSON read / write ───────────────────────────────────────────────

def _require_active_path() -> str:
    """Returns the active path, or raises a clear error if none is configured yet."""
    path = get_active_json_path()
    if not path:
        raise RuntimeError(
            "No projects file is configured. Call set_active_json_path() "
            "(or complete the app's initial setup) before loading or saving projects."
        )
    return path


def _load_raw() -> dict:
    data_file = _require_active_path()
    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    if not os.path.exists(data_file):
        return {"projects": []}
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"projects": []}


def _save_raw(data: dict) -> None:
    data_file = _require_active_path()
    os.makedirs(os.path.dirname(data_file), exist_ok=True)

    # Atomic write: write to a temp file first, then rename into place, so a
    # synced folder (Google Drive, Dropbox...) never observes a half-written file.
    tmp_file = data_file + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, data_file)


def load_projects() -> list[dict]:
    """Returns the list of stored projects."""
    return _load_raw().get("projects", [])


def save_projects(projects: list[dict]) -> None:
    """Saves the full project list."""
    _save_raw({"projects": projects})


def add_project(path: str, name: str = "") -> dict:
    """Adds a new project. Returns the project dict."""
    projects = load_projects()

    path = os.path.normpath(os.path.abspath(path))

    for p in projects:
        if os.path.normpath(p["path"]) == path:
            return p

    project = {
        "id":            _generate_id(),
        "name":          name or os.path.basename(path),
        "path":          path,
        "added_at":      datetime.now().isoformat(),
        "last_push":     None,
        "last_pull":     None,
        "launcher_exe":  None,
        "launcher_icon": None,
    }
    projects.append(project)
    save_projects(projects)
    return project


def remove_project(project_id: str) -> None:
    """Removes a project by id."""
    projects = [p for p in load_projects() if p.get("id") != project_id]
    save_projects(projects)


def update_project(project_id: str, **kwargs) -> None:
    """Updates fields on a project."""
    projects = load_projects()
    for p in projects:
        if p.get("id") == project_id:
            p.update(kwargs)
            break
    save_projects(projects)


def record_push(project_id: str) -> None:
    update_project(project_id, last_push=datetime.now().isoformat())


def record_pull(project_id: str) -> None:
    update_project(project_id, last_pull=datetime.now().isoformat())


def _generate_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8]
