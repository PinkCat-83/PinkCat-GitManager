"""
base.py
Clase base compartida por todos los diálogos (Toplevel) de la app.
"""

import customtkinter as ctk

# Ventana base para todos los dialogos - garantiza foco en Windows
class BaseDialog(ctk.CTkToplevel):
    """Clase base. Garantiza que los diálogos aparezcan al frente en Windows."""
    def _grab_focus(self):
        try:
            self.attributes("-topmost", False)
            self.focus_force()
            self.grab_set()
        except Exception:
            pass
