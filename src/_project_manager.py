"""
project_manager.py
Gestión del JSON de proyectos: carga, guardado, añadir, eliminar.

El JSON activo se configura mediante app_config.json (data/app_config.json).
Esto permite tener varios JSONs (por equipo, por contexto) y cambiar entre ellos.
"""

import json
import os
from datetime import datetime

_BASE_DIR          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DATA_FILE = os.path.join(_BASE_DIR, "data", "projects.json")

# Configuración del sistema: %APPDATA%\GitManager\config.json
# Existe por usuario en cualquier Windows, independiente de dónde esté la app.
_APPDATA_DIR = os.path.join(
    os.getenv("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming"),
    "GitManager"
)
_APP_CONFIG = os.path.join(_APPDATA_DIR, "config.json")


# ─── Configuración del sistema (qué JSON está activo) ────────────────────────

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
    """Devuelve la ruta del JSON de proyectos actualmente activo."""
    cfg = _load_app_config()
    path = cfg.get("active_projects_file", "")
    if path and os.path.isabs(path):
        return path
    return _DEFAULT_DATA_FILE


def set_active_json_path(path: str) -> None:
    """Cambia el JSON activo y lo persiste en app_config.json."""
    cfg = _load_app_config()
    cfg["active_projects_file"] = os.path.normpath(os.path.abspath(path))
    _save_app_config(cfg)


# ─── Lectura / escritura del JSON de proyectos ────────────────────────────────

def _load_raw() -> dict:
    data_file = get_active_json_path()
    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    if not os.path.exists(data_file):
        return {"projects": []}
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"projects": []}


def _save_raw(data: dict) -> None:
    data_file = get_active_json_path()
    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_projects() -> list[dict]:
    """Devuelve la lista de proyectos guardados."""
    return _load_raw().get("projects", [])


def save_projects(projects: list[dict]) -> None:
    """Guarda la lista completa de proyectos."""
    _save_raw({"projects": projects})


def add_project(path: str, name: str = "") -> dict:
    """Añade un proyecto nuevo. Devuelve el dict del proyecto."""
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
    """Elimina un proyecto por su id."""
    projects = [p for p in load_projects() if p.get("id") != project_id]
    save_projects(projects)


def update_project(project_id: str, **kwargs) -> None:
    """Actualiza campos de un proyecto."""
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
