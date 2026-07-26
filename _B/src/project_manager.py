"""
project_manager.py
Gestión del JSON de proyectos: carga, guardado, añadir, eliminar.
"""

import json
import os
from datetime import datetime

# Ruta al JSON relativa al propio archivo
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(_BASE_DIR, "data", "projects.json")


def _load_raw() -> dict:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    if not os.path.exists(DATA_FILE):
        return {"projects": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"projects": []}


def _save_raw(data: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
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

    # Normalizar ruta
    path = os.path.normpath(os.path.abspath(path))

    # Comprobar duplicado
    for p in projects:
        if os.path.normpath(p["path"]) == path:
            return p  # Ya existe

    project = {
        "id": _generate_id(),
        "name": name or os.path.basename(path),
        "path": path,
        "added_at": datetime.now().isoformat(),
        "last_push": None,
        "last_pull": None,
        "launcher_exe": None,
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
