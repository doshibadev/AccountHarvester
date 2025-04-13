"""
Utility dialogs for the UI
"""
from PyQt6.QtWidgets import (
    QMessageBox, QInputDialog, QDialog, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QHBoxLayout,
    QFormLayout
)
from PyQt6.QtCore import Qt

def show_error(parent, title, message):
    """Show an error dialog"""
    QMessageBox.critical(parent, title, message)

def show_warning(parent, title, message):
    """Show a warning dialog"""
    QMessageBox.warning(parent, title, message)

def show_info(parent, title, message):
    """Show an information dialog"""
    QMessageBox.information(parent, title, message)

def show_confirmation(parent, title, message):
    """Show a confirmation dialog"""
    return QMessageBox.question(
        parent, 
        title, 
        message, 
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    ) == QMessageBox.StandardButton.Yes

class SteamGuardDialog(QDialog):
    """Dialog for entering SteamGuard codes"""
    
    def __init__(self, parent=None, email_auth=False):
        super().__init__(parent)
        
        self.setWindowTitle("SteamGuard Authentication")
        self.setFixedWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        if email_auth:
            instructions = QLabel(
                "Steam sent an authentication code to your email.\n"
                "Please enter that code below."
            )
        else:
            instructions = QLabel(
                "Please enter the SteamGuard code from your mobile authenticator."
            )
        
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Code input
        form_layout = QFormLayout()
        
        self.code_input = QLineEdit()
        self.code_input.setMaxLength(5)
        form_layout.addRow("Authentication Code:", self.code_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def get_code(self):
        """Get the entered code"""
        return self.code_input.text().strip()
