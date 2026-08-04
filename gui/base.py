"""
base.py
Shared base class for every dialog (Toplevel) in the app.
"""

import customtkinter as ctk


class BaseDialog(ctk.CTkToplevel):
    """Base window. Ensures dialogs come to the front and grab focus on Windows."""
    def _grab_focus(self):
        try:
            self.attributes("-topmost", False)
            self.focus_force()
            self.grab_set()
        except Exception:
            pass
