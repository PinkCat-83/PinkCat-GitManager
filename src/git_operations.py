"""
git_operations.py
Module responsible for every Git operation used by the app.
"""

import subprocess
import os
from datetime import datetime

from src.i18n import t


def _run(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    """Runs a git command and returns (returncode, stdout, stderr)."""
    # On Windows, avoid a console window popping up for every subprocess.
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
        return -1, "", t("git_timeout")
    except Exception as e:
        return -1, "", str(e)


def has_git_repo(path: str) -> bool:
    """Checks whether the folder has a Git repository (.git)."""
    return os.path.isdir(os.path.join(path, ".git"))


def init_repo(path: str) -> tuple[bool, str]:
    """Initializes a Git repository in the folder (git init)."""
    code, out, err = _run(["git", "init"], path)
    if code == 0:
        return True, out or t("git_init_ok")
    return False, err or t("git_init_err")


def add_remote(path: str, url: str, name: str = "origin") -> tuple[bool, str]:
    """Adds a remote, or updates its URL if it already exists."""
    code, out, _ = _run(["git", "remote"], path)
    existing = out.splitlines() if code == 0 else []
    if name in existing:
        code2, out2, err2 = _run(["git", "remote", "set-url", name, url], path)
    else:
        code2, out2, err2 = _run(["git", "remote", "add", name, url], path)
    if code2 == 0:
        return True, t("git_remote_set_ok", name=name, url=url)
    return False, err2 or t("git_remote_set_err", name=name)


def init_repo_with_remote(path: str, remote_url: str = "") -> tuple[bool, str]:
    """
    Initializes a repository and, if given, configures the 'origin' remote.
    remote_url may be empty: in that case only git init runs.
    """
    ok, msg = init_repo(path)
    if not ok:
        return False, msg
    remote_url = (remote_url or "").strip()
    if remote_url:
        ok2, msg2 = add_remote(path, remote_url)
        if not ok2:
            return False, t("git_init_with_remote_err", msg=msg2)
        return True, f"{msg}\n{msg2}"
    return True, f"{msg}\n{t('git_init_no_remote')}"


def get_current_branch(path: str) -> str:
    """Returns the current branch."""
    code, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], path)
    return out if code == 0 else t("git_unknown_branch")


def get_remote_url(path: str) -> str:
    """Returns the URL of the origin remote."""
    code, out, _ = _run(["git", "remote", "get-url", "origin"], path)
    return out if code == 0 else ""


def get_last_commit_info(path: str) -> dict:
    """Returns information about the latest local commit."""
    code, out, _ = _run(
        ["git", "log", "-1", "--format=%H|%s|%ai|%an"],
        path,
    )
    if code != 0 or not out:
        return {"hash": "", "message": "", "date": "", "author": ""}
    parts = out.split("|", 3)
    return {
        "hash": parts[0][:7] if len(parts) > 0 else "",
        "message": parts[1] if len(parts) > 1 else "",
        "date": parts[2] if len(parts) > 2 else "",
        "author": parts[3] if len(parts) > 3 else "",
    }


def get_status(path: str) -> dict:
    """
    Returns the full repository status, classifying each change:
    - new_files:      untracked new files (??)
    - modified:       modified files (M, R, C...)
    - deleted:        files deleted locally (D)
    - staged:         changes in the index (staged)
    - ahead:          local commits not yet pushed to the remote
    - behind:         remote commits not yet pulled (requires a prior fetch)
    - is_dirty:       True if there is any uncommitted change
    - has_remote:     True if a remote is configured
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
        x, y = line[0], line[1]   # x = index (staged), y = working tree
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

    # Commits not yet pushed (ahead)
    code2, out2, _ = _run(["git", "rev-list", "--count", "@{u}..HEAD"], path)
    try:
        ahead = int(out2) if code2 == 0 else 0
    except ValueError:
        ahead = 0

    # Commits not yet pulled (behind) — only accurate after a fetch
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
    """True if the repo is in the middle of an unresolved merge."""
    return os.path.isfile(os.path.join(path, ".git", "MERGE_HEAD"))


def get_conflicted_files(path: str) -> list[str]:
    """Returns the files with unresolved conflicts."""
    code, out, _ = _run(["git", "diff", "--name-only", "--diff-filter=U"], path)
    return out.splitlines() if code == 0 else []


def do_merge_abort(path: str) -> tuple[bool, str]:
    """Aborts an in-progress merge and returns the repo to its previous state."""
    code, out, err = _run(["git", "merge", "--abort"], path)
    if code == 0:
        return True, t("git_merge_abort_ok")
    return False, err or t("git_merge_abort_err")


def do_fetch(path: str) -> tuple[bool, str]:
    """Runs git fetch."""
    code, out, err = _run(["git", "fetch"], path)
    if code == 0:
        return True, out or t("git_fetch_ok")
    return False, err or t("git_fetch_err")


def do_merge(path: str) -> tuple[bool, str]:
    """Runs git merge FETCH_HEAD."""
    code, out, err = _run(["git", "merge", "FETCH_HEAD"], path)
    if code == 0:
        return True, out or t("git_merge_ok")
    if is_merging(path):
        conflicts = get_conflicted_files(path)
        files_list = "\n".join(f"  • {f}" for f in conflicts) or t("merge_conflict_no_files")
        return False, t("git_merge_conflict", files=files_list)
    return False, err or t("git_merge_err")


def do_fetch_and_merge(path: str) -> tuple[bool, str]:
    """Fetch + Merge in sequence."""
    ok, msg = do_fetch(path)
    if not ok:
        return False, t("git_fetch_failed", msg=msg)
    ok2, msg2 = do_merge(path)
    if not ok2:
        return False, t("git_fetch_ok_merge_failed", msg=msg2)
    return True, t("git_fetch_merge_ok", msg=msg2)


def _push(path: str) -> tuple[bool, str]:
    """
    Runs git push. If the current branch has no upstream configured yet
    (typical on a repo's first push, or right after git init + remote add),
    it automatically retries with --set-upstream origin <branch>.
    """
    code, out, err = _run(["git", "push"], path)
    if code == 0:
        return True, out or t("git_push_ok")

    if "has no upstream branch" in err or "set-upstream" in err:
        branch_code, branch, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], path)
        branch = branch if branch_code == 0 and branch else "HEAD"
        code2, out2, err2 = _run(["git", "push", "--set-upstream", "origin", branch], path)
        if code2 == 0:
            return True, out2 or t("git_push_upstream_ok", branch=branch)
        return False, err2 or out2 or t("git_push_upstream_err")

    return False, err or out or t("git_push_err")


def do_add_commit_push(path: str, message: str = "") -> tuple[bool, str]:
    """git add -A + git commit -m + git push."""
    # Add
    code, _, err = _run(["git", "add", "-A"], path)
    if code != 0:
        return False, t("git_add_err", err=err)

    # Commit
    if not message:
        message = t("default_commit_message", datetime=datetime.now().strftime("%d/%m/%Y %H:%M"))
    code2, out2, err2 = _run(["git", "commit", "-m", message], path)
    if code2 != 0:
        # Might be "nothing to commit" — there could still be local commits
        # that haven't been pushed, so push is attempted anyway.
        if "nothing to commit" in (out2 + err2).lower():
            ok, msg = _push(path)
            if ok:
                return True, t("git_nothing_to_commit_pushed", msg=msg)
            return False, t("git_nothing_to_commit_push_failed", msg=msg)
        return False, t("git_commit_err", err=err2 or out2)

    # Push
    ok, msg = _push(path)
    if not ok:
        return False, t("git_push_after_commit_err", msg=msg)

    return True, t("git_commit_push_ok", msg=msg)


def get_log(path: str, n: int = 10) -> list[dict]:
    """Returns the last n commits."""
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
    Removes a file or folder from the entire Git history using filter-branch.
    target: path relative to the repo (e.g. "secrets/passwords.txt" or "build/")
    is_folder: True if it's a folder, False if it's a file.
    Returns (ok, message).
    """
    import shutil

    # Build the appropriate filter
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

    # Clean up the backup refs left behind by filter-branch
    backup_ref = os.path.join(repo_path, ".git", "refs", "original")
    if os.path.isdir(backup_ref):
        shutil.rmtree(backup_ref, ignore_errors=True)

    # Expire the reflog and run an aggressive gc to free orphaned objects
    _run(["git", "reflog", "expire", "--expire=now", "--all"], repo_path)
    _run(["git", "gc", "--prune=now", "--aggressive"], repo_path)

    kind = t("purge_type_folder") if is_folder else t("purge_type_file")
    msg = t(
        "git_purge_result",
        type=kind.capitalize(),
        target=target,
        output="\n".join(l for l in output_lines if l),
    )
    return True, msg


def get_deleted_files(repo_path: str) -> list[dict]:
    """
    Returns every file that existed in the history but is no longer present
    on the current branch (HEAD).
    Each entry: {path, hash_delete, date_delete, commit_msg, hash_full}
    """
    # Get every file deleted anywhere in the history, with the commit that deleted it
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

    # Files that DO exist right now on HEAD (to exclude them)
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
            # Only include it if it doesn't currently exist
            if filepath and filepath not in current_files:
                # Avoid duplicates (keep the most recent deletion)
                if not any(d["path"] == filepath for d in deleted):
                    # Find the last commit where the file was still alive
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
    Recovers a deleted file from the history.
    Uses the commit right before the deletion to get the last live version.
    """
    # The file was alive in the PARENT commit of the one that deleted it
    code, out, err = _run(
        ["git", "checkout", f"{hash_full}^", "--", filepath],
        repo_path,
    )
    if code == 0:
        return True, t("git_restore_ok", path=filepath)
    return False, t("git_restore_err", err=err or out)


def get_gitignore_data(repo_path: str) -> dict:
    """
    Reads the .gitignore and detects which tracked files match one of its rules.
    Returns:
      - rules:    list of .gitignore rules (comments and blank lines removed)
      - tracked:  files on HEAD that match a rule
      - gitignore_exists: bool
    """
    import fnmatch

    gitignore_path = os.path.join(repo_path, ".gitignore")
    if not os.path.exists(gitignore_path):
        return {"rules": [], "tracked": [], "gitignore_exists": False}

    # Read the rules
    with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = f.readlines()

    rules = []
    for line in raw_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            rules.append(stripped)

    # Files currently in the index (staged/tracked)
    # ls-files is more reliable than ls-tree for rm --cached
    code, out, _ = _run(
        ["git", "ls-files"],
        repo_path,
    )
    tracked_files = out.splitlines() if code == 0 else []

    # Check which ones match a .gitignore rule
    matches = []
    for filepath in tracked_files:
        filename = os.path.basename(filepath)
        for rule in rules:
            # Normalize the rule
            rule_clean = rule.lstrip("/").rstrip("/")
            # Compare against the filename, the full path, and path segments
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
                break  # One matching rule is enough

    return {
        "rules":            rules,
        "tracked":          matches,
        "gitignore_exists": True,
    }
