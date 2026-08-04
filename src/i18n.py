"""
i18n.py
Loads UI text translations from language/translations.csv and exposes
t(key, **kwargs) to fetch the active-language string for a key.
"""

import csv
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CSV_PATH = os.path.join(_ROOT, "language", "translations.csv")

DEFAULT_LANGUAGE = "Español"
AVAILABLE_LANGUAGES = ["Español", "English"]

_current_language = DEFAULT_LANGUAGE
_table: dict[str, dict[str, str]] = {}


def _load_table() -> None:
    global _table
    _table = {}
    if not os.path.isfile(_CSV_PATH):
        return
    with open(_CSV_PATH, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        if not header:
            return
        langs = header[1:]
        for row in reader:
            if not row or not row[0]:
                continue
            key = row[0]
            _table[key] = {
                lang: (row[i + 1] if i + 1 < len(row) else "")
                for i, lang in enumerate(langs)
            }


_load_table()


def set_language(lang: str) -> None:
    """Sets the active language for t(). Falls back silently if unknown."""
    global _current_language
    if lang in AVAILABLE_LANGUAGES:
        _current_language = lang


def get_language() -> str:
    return _current_language


def t(key: str, **kwargs) -> str:
    """
    Returns the translation of `key` in the active language, formatting
    `{placeholder}` fields with kwargs. Falls back to DEFAULT_LANGUAGE, then
    to the raw key, if a translation is missing.
    """
    entry = _table.get(key)
    if not entry:
        return key
    text = entry.get(_current_language) or entry.get(DEFAULT_LANGUAGE) or key
    text = text.replace("\\n", "\n")
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
