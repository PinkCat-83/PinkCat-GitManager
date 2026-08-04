"""
theme_loader.py
Single access point for theme palettes (see PinkCat_Design_System.md).
No UI file should import gui.themes.* directly — always go through get_theme().
"""

import importlib

DEFAULT_THEME = "green"
AVAILABLE_THEMES = ["green", "pink", "pro"]


def get_theme(name: str = DEFAULT_THEME) -> dict:
    if name not in AVAILABLE_THEMES:
        name = DEFAULT_THEME
    module = importlib.import_module(f"gui.themes.{name}")
    return module.THEME
