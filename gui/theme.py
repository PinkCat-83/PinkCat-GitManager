"""
theme.py
Paleta de colores, fuentes y helpers de formato/estado usados en toda la UI.
"""

import customtkinter as ctk
from datetime import datetime

# ─── Tema ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Paleta personalizada
C = {
    "bg":         "#0e0f11",
    "panel":      "#16181c",
    "card":       "#1c1f24",
    "card_hover": "#22262d",
    "border":     "#2a2d35",
    "accent":     "#3de6a0",        # verde terminal
    "accent_dim": "#1f7a55",
    "red":        "#e05c5c",
    "yellow":     "#e0c05c",
    "blue":       "#5c9fe0",
    "text":       "#e8eaf0",
    "text_dim":   "#6b7280",
    "text_muted": "#3d4148",
}

FONT_TITLE  = ("Consolas", 26, "bold")
FONT_MONO   = ("Consolas", 14)
FONT_MONO_S = ("Consolas", 13)
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
        return C["yellow"]
    return C["accent"]


def _dot_color(has_git: bool, status: dict) -> str:
    """Color del punto luminoso en la cabecera de la tarjeta."""
    if not has_git:
        return C["red"]
    if status.get("is_dirty") or status.get("ahead", 0) > 0:
        return C["yellow"]
    if not status:
        return C["text_muted"]   # aún cargando
    return C["accent"]


def _status_label(status: dict) -> str:
    if not status.get("has_remote"):
        return "Sin remoto configurado"
    parts = []
    n = status.get("new_count", 0)
    m = status.get("modified_count", 0)
    d = status.get("deleted_count", 0)
    a = status.get("ahead", 0)
    if n:
        parts.append(f"{n} nuevo{'s' if n != 1 else ''}")
    if m:
        parts.append(f"{m} modificado{'s' if m != 1 else ''}")
    if d:
        parts.append(f"{d} borrado{'s' if d != 1 else ''}")
    if a:
        parts.append(f"{a} commit{'s' if a != 1 else ''} sin subir")
    if not parts:
        return "Al día  ✓"
    return "  •  ".join(parts)
