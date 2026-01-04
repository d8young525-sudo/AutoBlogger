from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from config import Config

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{Config.APP_NAME} v{Config.VERSION}")
        self.resize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        layout = QVBoxLayout(central_widget)
        
        # Welcome Label
        welcome_label = QLabel("Welcome to AutoBlogger")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        
        layout.addWidget(welcome_label)
        
        # Status Bar
        self.statusBar().showMessage("Ready")
