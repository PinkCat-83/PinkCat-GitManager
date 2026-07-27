import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gui.app import GitManagerApp
app = GitManagerApp()
app.mainloop()
