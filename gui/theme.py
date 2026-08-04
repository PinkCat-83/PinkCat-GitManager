"""
theme.py
Active color palette (see gui/theme_loader.py), fonts, and format/status
helpers used throughout the UI.
"""

import customtkinter as ctk
from datetime import datetime

from src import project_manager as pm
from src.i18n import t
from gui.theme_loader import get_theme

# ─── Active theme ──────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACTIVE_THEME_NAME = pm.get_active_theme()
C = get_theme(ACTIVE_THEME_NAME)

# Font family follows the Design System: Consolas/Segoe UI for Green & Pink,
# Segoe UI only for Pro. Absolute sizes stay a project concern, not a theme one.
_MONO_FAMILY = "Segoe UI" if ACTIVE_THEME_NAME == "pro" else "Consolas"

FONT_TITLE  = (_MONO_FAMILY, 26, "bold")
FONT_MONO   = (_MONO_FAMILY, 14)
FONT_MONO_S = (_MONO_FAMILY, 13)
FONT_LABEL  = ("Segoe UI", 14)
FONT_LABEL_B= ("Segoe UI", 14, "bold")
FONT_SMALL  = ("Segoe UI", 12)
FONT_BIG    = ("Segoe UI", 16, "bold")


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y  %H:%M")
    except Exception:
        return iso[:16]


def _status_color(status: dict) -> str:
    if not status.get("has_remote"):
        return C["text_dim"]
    if status.get("is_dirty") or status.get("ahead", 0) > 0:
        return C["warning"]
    return C["success"]


def _dot_color(has_git: bool, status: dict) -> str:
    """Color of the status dot in the card header."""
    if not has_git:
        return C["danger"]
    if status.get("is_dirty") or status.get("ahead", 0) > 0:
        return C["warning"]
    if not status:
        return C["text_muted"]   # still loading
    return C["success"]


def _status_label(status: dict) -> str:
    if not status.get("has_remote"):
        return t("status_no_remote")
    parts = []
    n = status.get("new_count", 0)
    m = status.get("modified_count", 0)
    d = status.get("deleted_count", 0)
    a = status.get("ahead", 0)
    if n:
        parts.append(t("status_new", n=n))
    if m:
        parts.append(t("status_modified", n=m))
    if d:
        parts.append(t("status_deleted", n=d))
    if a:
        parts.append(t("status_ahead", n=a))
    if not parts:
        return t("status_up_to_date")
    return "  •  ".join(parts)
