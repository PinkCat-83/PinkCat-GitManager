"""
git_operations.py
Módulo encargado de todas las operaciones Git del proyecto.
"""

import subprocess
import os
from datetime import datetime


def _run(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    """Ejecuta un comando git y devuelve (returncode, stdout, stderr)."""
    # En Windows, evita que cada subproceso abra una ventana de consola
    _flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=_flags,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Tiempo de espera agotado."
    except Exception as e:
        return -1, "", str(e)


def has_git_repo(path: str) -> bool:
    """Comprueba si la carpeta tiene un repositorio Git (.git)."""
    return os.path.isdir(os.path.join(path, ".git"))


def init_repo(path: str) -> tuple[bool, str]:
    """Inicializa un repositorio Git en la carpeta (git init)."""
    code, out, err = _run(["git", "init"], path)
    if code == 0:
        return True, out or "Repositorio inicializado."
    return False, err or "Error al inicializar el repositorio."


def add_remote(path: str, url: str, name: str = "origin") -> tuple[bool, str]:
    """Añade un remoto, o actualiza su URL si ya existe."""
    code, out, _ = _run(["git", "remote"], path)
    existing = out.splitlines() if code == 0 else []
    if name in existing:
        code2, out2, err2 = _run(["git", "remote", "set-url", name, url], path)
    else:
        code2, out2, err2 = _run(["git", "remote", "add", name, url], path)
    if code2 == 0:
        return True, f"Remoto '{name}' configurado: {url}"
    return False, err2 or f"Error al configurar el remoto '{name}'."


def init_repo_with_remote(path: str, remote_url: str = "") -> tuple[bool, str]:
    """
    Inicializa un repositorio y, si se indica una URL, configura el remoto 'origin'.
    remote_url puede ir vacío: en ese caso solo se hace git init.
    """
    ok, msg = init_repo(path)
    if not ok:
        return False, msg
    remote_url = (remote_url or "").strip()
    if remote_url:
        ok2, msg2 = add_remote(path, remote_url)
        if not ok2:
            return False, f"Repositorio inicializado, pero falló la configuración del remoto:\n{msg2}"
        return True, f"{msg}\n{msg2}"
    return True, f"{msg}\nSin remoto configurado — añádelo más tarde con 'git remote add origin <url>'."


def get_current_branch(path: str) -> str:
    """Devuelve la rama actual."""
    code, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], path)
    return out if code == 0 else "desconocida"


def get_remote_url(path: str) -> str:
    """Devuelve la URL del remoto origin."""
    code, out, _ = _run(["git", "remote", "get-url", "origin"], path)
    return out if code == 0 else ""


def get_last_commit_info(path: str) -> dict:
    """Devuelve información del último commit local."""
    code, out, _ = _run(
        ["git", "log", "-1", "--format=%H|%s|%ai|%an"],
        path,
    )
    if code != 0 or not out:
        return {"hash": "", "message": "Sin commits", "date": "", "author": ""}
    parts = out.split("|", 3)
    return {
        "hash": parts[0][:7] if len(parts) > 0 else "",
        "message": parts[1] if len(parts) > 1 else "",
        "date": parts[2] if len(parts) > 2 else "",
        "author": parts[3] if len(parts) > 3 else "",
    }


def get_status(path: str) -> dict:
    """
    Devuelve el estado completo del repositorio clasificando cada cambio:
    - new_files:      archivos nuevos sin seguimiento (??)
    - modified:       archivos modificados (M, R, C...)
    - deleted:        archivos borrados localmente (D)
    - staged:         cambios en el área de stage (index)
    - ahead:          commits locales no subidos al remoto
    - behind:         commits del remoto no bajados (requiere fetch previo)
    - is_dirty:       True si hay cualquier cambio sin commitear
    - has_remote:     True si hay un remoto configurado
    """
    code, out, _ = _run(["git", "status", "--porcelain"], path)
    lines = [l for l in out.splitlines() if l.strip()] if code == 0 else []

    new_files = []
    modified  = []
    deleted   = []
    staged    = []

    for line in lines:
        if len(line) < 2:
            continue
        x, y = line[0], line[1]   # x = índice (staged), y = working tree
        filepath = line[3:].strip()

        if x == "?" and y == "?":
            new_files.append(filepath)
        elif y == "D" or x == "D":
            deleted.append(filepath)
        elif y in ("M", "A", "R", "C", "U") or x in ("M", "A", "R", "C", "U"):
            if x != " " and x != "?":
                staged.append(filepath)
            else:
                modified.append(filepath)

    # Commits sin subir (ahead)
    code2, out2, _ = _run(["git", "rev-list", "--count", "@{u}..HEAD"], path)
    try:
        ahead = int(out2) if code2 == 0 else 0
    except ValueError:
        ahead = 0

    # Commits sin bajar (behind) — solo con fetch previo
    code3, out3, _ = _run(["git", "rev-list", "--count", "HEAD..@{u}"], path)
    try:
        behind = int(out3) if code3 == 0 else 0
    except ValueError:
        behind = 0

    is_dirty = bool(lines)

    return {
        "new_files":    new_files,
        "modified":     modified,
        "deleted":      deleted,
        "staged":       staged,
        "new_count":    len(new_files),
        "modified_count": len(modified) + len(staged),
        "deleted_count": len(deleted),
        "total_changes": len(lines),
        "ahead":        ahead,
        "behind":       behind,
        "is_dirty":     is_dirty,
        "has_remote":   bool(get_remote_url(path)),
    }


def is_merging(path: str) -> bool:
    """True si el repo está en medio de un merge sin resolver."""
    return os.path.isfile(os.path.join(path, ".git", "MERGE_HEAD"))


def get_conflicted_files(path: str) -> list[str]:
    """Devuelve los archivos con conflictos sin resolver."""
    code, out, _ = _run(["git", "diff", "--name-only", "--diff-filter=U"], path)
    return out.splitlines() if code == 0 else []


def do_merge_abort(path: str) -> tuple[bool, str]:
    """Aborta un merge en curso y devuelve el repo a su estado previo."""
    code, out, err = _run(["git", "merge", "--abort"], path)
    if code == 0:
        return True, "Merge abortado. El repositorio volvió a su estado anterior al Pull."
    return False, err or "No se pudo abortar el merge."


def do_fetch(path: str) -> tuple[bool, str]:
    """Hace git fetch."""
    code, out, err = _run(["git", "fetch"], path)
    if code == 0:
        return True, out or "Fetch completado."
    return False, err or "Error en fetch."


def do_merge(path: str) -> tuple[bool, str]:
    """Hace git merge FETCH_HEAD."""
    code, out, err = _run(["git", "merge", "FETCH_HEAD"], path)
    if code == 0:
        return True, out or "Merge completado."
    if is_merging(path):
        conflicts = get_conflicted_files(path)
        files_list = "\n".join(f"  • {f}" for f in conflicts) or "  (no se detectaron archivos, revisa manualmente)"
        return False, (
            "Conflicto de merge sin resolver.\n\n"
            f"Archivos en conflicto:\n{files_list}"
        )
    return False, err or "Error en merge."


def do_fetch_and_merge(path: str) -> tuple[bool, str]:
    """Fetch + Merge en secuencia."""
    ok, msg = do_fetch(path)
    if not ok:
        return False, f"Fetch falló: {msg}"
    ok2, msg2 = do_merge(path)
    if not ok2:
        return False, f"Fetch OK. Merge falló: {msg2}"
    return True, f"Fetch y merge completados.\n{msg2}"


def do_add_commit_push(path: str, message: str = "") -> tuple[bool, str]:
    """git add -A + git commit -m + git push."""
    # Add
    code, _, err = _run(["git", "add", "-A"], path)
    if code != 0:
        return False, f"Error en git add: {err}"

    # Commit
    if not message:
        message = f"Actualización automática: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    code2, out2, err2 = _run(["git", "commit", "-m", message], path)
    if code2 != 0:
        # Puede ser "nothing to commit"
        if "nothing to commit" in (out2 + err2).lower():
            return True, "Nada que commitear. Haciendo push igualmente..."
        return False, f"Error en git commit: {err2 or out2}"

    # Push
    code3, out3, err3 = _run(["git", "push"], path)
    if code3 != 0:
        return False, f"Commit OK. Error en push: {err3 or out3}"

    return True, f"Commit y push completados.\n{out3 or 'Push exitoso.'}"


def get_log(path: str, n: int = 10) -> list[dict]:
    """Devuelve los últimos n commits."""
    code, out, _ = _run(
        ["git", "log", f"-{n}", "--format=%H|%s|%ai|%an"],
        path,
    )
    if code != 0 or not out:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "hash": parts[0][:7],
                "message": parts[1],
                "date": parts[2][:16].replace("T", " "),
                "author": parts[3],
            })
    return commits


def purge_from_history(repo_path: str, target: str, is_folder: bool) -> tuple[bool, str]:
    """
    Elimina un archivo o carpeta del historial completo de Git usando filter-branch.
    target: ruta relativa al repo (ej: "secrets/passwords.txt" o "build/")
    is_folder: True si es carpeta, False si es archivo.
    Devuelve (ok, mensaje).
    """
    import shutil

    # Construir el filtro adecuado
    if is_folder:
        filter_cmd = f'git rm -rf --cached --ignore-unmatch "{target}"'
    else:
        filter_cmd = f'git rm -f --cached --ignore-unmatch "{target}"'

    code, out, err = _run(
        [
            "git", "filter-branch",
            "--force",
            "--index-filter", filter_cmd,
            "--prune-empty",
            "--tag-name-filter", "cat",
            "--", "--all",
        ],
        repo_path,
    )

    output_lines = [out, err]

    if code != 0:
        return False, "\n".join(l for l in output_lines if l)

    # Limpiar refs de respaldo que deja filter-branch
    backup_ref = os.path.join(repo_path, ".git", "refs", "original")
    if os.path.isdir(backup_ref):
        shutil.rmtree(backup_ref, ignore_errors=True)

    # Expirar reflog y gc agresivo para liberar objetos huerfanos
    _run(["git", "reflog", "expire", "--expire=now", "--all"], repo_path)
    _run(["git", "gc", "--prune=now", "--aggressive"], repo_path)

    tipo = "Carpeta" if is_folder else "Archivo"
    msg = (
        f"{tipo}  \"{target}\"  eliminado del historial completo.\n\n"
        "Objetos huerfanos limpiados (reflog + gc).\n\n"
        "SIGUIENTE PASO OBLIGATORIO:\n"
        "Haz un Push forzado para actualizar GitHub:\n\n"
        "  git push origin --force --all\n\n"
        "Puedes ejecutarlo desde la terminal en la carpeta del proyecto.\n\n"
        "─────────────────────────────────────\n"
        + "\n".join(l for l in output_lines if l)
    )
    return True, msg


def get_deleted_files(repo_path: str) -> list[dict]:
    """
    Devuelve todos los archivos que existieron en el historial pero
    ya no están en la rama actual (HEAD).
    Cada entrada: {path, hash_delete, date_delete, commit_msg, hash_last_alive}
    """
    # Obtener todos los archivos borrados del historial con su commit de borrado
    code, out, _ = _run(
        [
            "git", "log", "--all", "--full-history",
            "--diff-filter=D",
            "--format=COMMIT:%H|%ai|%s",
            "--name-only",
        ],
        repo_path,
    )
    if code != 0 or not out:
        return []

    # Obtener archivos que SÍ existen ahora en HEAD (para excluirlos)
    code2, out2, _ = _run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"],
        repo_path,
    )
    current_files = set(out2.splitlines()) if code2 == 0 else set()

    deleted = []
    current_commit = {}

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("COMMIT:"):
            parts = line[7:].split("|", 2)
            current_commit = {
                "hash":    parts[0][:7] if len(parts) > 0 else "",
                "hash_full": parts[0] if len(parts) > 0 else "",
                "date":    parts[1][:16].replace("T", " ") if len(parts) > 1 else "",
                "message": parts[2] if len(parts) > 2 else "",
            }
        else:
            filepath = line
            # Solo incluir si no existe actualmente
            if filepath and filepath not in current_files:
                # Evitar duplicados (quedarse con el borrado más reciente)
                if not any(d["path"] == filepath for d in deleted):
                    # Buscar el último commit donde el archivo estaba vivo
                    code3, out3, _ = _run(
                        ["git", "log", "--all", "--diff-filter=A",
                         "--format=%H", "--follow", "--", filepath],
                        repo_path,
                    )
                    hash_born = out3.splitlines()[-1][:7] if out3.strip() else current_commit["hash"]

                    deleted.append({
                        "path":         filepath,
                        "hash_delete":  current_commit["hash"],
                        "hash_full":    current_commit["hash_full"],
                        "date_delete":  current_commit["date"],
                        "commit_msg":   current_commit["message"],
                        "hash_born":    hash_born,
                    })

    return deleted


def restore_deleted_file(repo_path: str, filepath: str, hash_full: str) -> tuple[bool, str]:
    """
    Recupera un archivo borrado del historial.
    Usa el commit justo anterior al de borrado para obtener la última versión viva.
    """
    # El archivo estaba vivo en el commit PADRE del que lo borró
    code, out, err = _run(
        ["git", "checkout", f"{hash_full}^", "--", filepath],
        repo_path,
    )
    if code == 0:
        return True, (
            f"Archivo recuperado: {filepath}\n\n"
            f"El archivo ha vuelto a tu carpeta local.\n"
            f"Ahora aparecera como 'modificado' en git status.\n"
            f"Haz un Push cuando quieras subirlo de nuevo a GitHub."
        )
    return False, f"No se pudo recuperar el archivo.\n\n{err or out}"


def get_gitignore_data(repo_path: str) -> dict:
    """
    Lee el .gitignore y detecta qué archivos/carpetas del repositorio
    remoto coinciden con alguna regla del .gitignore.
    Devuelve:
      - rules:    lista de reglas del .gitignore (sin comentarios ni vacíos)
      - tracked:  archivos en HEAD que coinciden con alguna regla
      - gitignore_exists: bool
    """
    import fnmatch

    gitignore_path = os.path.join(repo_path, ".gitignore")
    if not os.path.exists(gitignore_path):
        return {"rules": [], "tracked": [], "gitignore_exists": False}

    # Leer reglas
    with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = f.readlines()

    rules = []
    for line in raw_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            rules.append(stripped)

    # Archivos actualmente en el índice (staged/tracked)
    # ls-files es más fiable que ls-tree para rm --cached
    code, out, _ = _run(
        ["git", "ls-files"],
        repo_path,
    )
    tracked_files = out.splitlines() if code == 0 else []

    # Comprobar cuáles coinciden con alguna regla del .gitignore
    matches = []
    for filepath in tracked_files:
        filename = os.path.basename(filepath)
        for rule in rules:
            # Normalizar regla
            rule_clean = rule.lstrip("/").rstrip("/")
            # Comparar contra nombre de archivo, ruta completa y segmentos
            if (
                fnmatch.fnmatch(filename,  rule_clean) or
                fnmatch.fnmatch(filepath,  rule_clean) or
                fnmatch.fnmatch(filepath,  f"*/{rule_clean}") or
                fnmatch.fnmatch(filepath,  f"{rule_clean}/*") or
                any(fnmatch.fnmatch(part, rule_clean) for part in filepath.split("/"))
            ):
                matches.append({
                    "file":  filepath,
                    "rule":  rule,
                })
                break  # Una regla que coincide es suficiente

    return {
        "rules":            rules,
        "tracked":          matches,
        "gitignore_exists": True,
    }
