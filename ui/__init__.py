"""
UI module for the AccountHarvester application
This module provides the graphical user interface components
"""

from ui.main_window import MainWindow

def start_ui():
    """Launch the GUI application"""
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
