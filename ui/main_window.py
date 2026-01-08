"""
AutoBlogger Main Window UI Module
메인 윈도우 GUI 컴포넌트
"""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit,
    QTabWidget, QGroupBox, QFormLayout, QMessageBox,
    QProgressBar, QStatusBar, QMenuBar, QMenu
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QFont

from config import Config, ConfigError

logger = logging.getLogger(__name__)


class GeneratorWorker(QThread):
    """Background worker for blog generation"""
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(int, str)
    
    def __init__(self, topic: str, parent=None):
        super().__init__(parent)
        self.topic = topic
    
    def run(self):
        try:
            self.progress.emit(10, "Initializing generator...")
            
            from core.blog_generator import BlogGenerator
            generator = BlogGenerator()
            
            self.progress.emit(30, "Generating content...")
            result = generator.generate(self.topic)
            
            self.progress.emit(100, "Complete!")
            self.finished.emit(result if result else "Generation completed but no content returned.")
            
        except ImportError as e:
            self.error.emit(f"Module import error: {e}")
        except Exception as e:
            self.error.emit(f"Generation failed: {e}")


class MainWindow(QMainWindow):
    """Main Application Window"""
    
    def __init__(self):
        super().__init__()
        self._setup_window()
        self._setup_menu()
        self._setup_ui()
        self._setup_statusbar()
        
        logger.info("MainWindow initialized")
    
    def _setup_window(self):
        """Configure main window properties"""
        self.setWindowTitle(f"{Config.APP_NAME} v{Config.VERSION}")
        self.resize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        self.setMinimumSize(800, 600)
    
    def _setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")
        
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help Menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        config_action = QAction("&Configuration Info", self)
        config_action.triggered.connect(self._show_config_info)
        help_menu.addAction(config_action)
    
    def _setup_ui(self):
        """Setup main UI components"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_label = QLabel(f"🚀 {Config.APP_NAME}")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header_label.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        main_layout.addWidget(header_label)
        
        # Tab Widget
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Tab 1: Blog Generator
        generator_tab = self._create_generator_tab()
        tab_widget.addTab(generator_tab, "📝 Blog Generator")
        
        # Tab 2: Settings
        settings_tab = self._create_settings_tab()
        tab_widget.addTab(settings_tab, "⚙️ Settings")
    
    def _create_generator_tab(self) -> QWidget:
        """Create blog generator tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Topic Input Group
        input_group = QGroupBox("Blog Topic")
        input_layout = QHBoxLayout(input_group)
        
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("Enter your blog topic here...")
        self.topic_input.setStyleSheet("padding: 8px; font-size: 14px;")
        input_layout.addWidget(self.topic_input)
        
        self.generate_btn = QPushButton("🚀 Generate")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        input_layout.addWidget(self.generate_btn)
        
        layout.addWidget(input_group)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Output Group
        output_group = QGroupBox("Generated Content")
        output_layout = QVBoxLayout(output_group)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("Generated blog content will appear here...")
        self.output_text.setStyleSheet("font-size: 13px; padding: 10px;")
        output_layout.addWidget(self.output_text)
        
        # Copy Button
        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        output_layout.addWidget(copy_btn)
        
        layout.addWidget(output_group)
        
        return tab
    
    def _create_settings_tab(self) -> QWidget:
        """Create settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # API Settings Group
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout(api_group)
        
        gemini_status = "✅ Configured" if Config.GEMINI_API_KEY else "❌ Not Set"
        api_layout.addRow("Gemini API:", QLabel(gemini_status))
        
        naver_status = "✅ Configured" if Config.NAVER_ID else "❌ Not Set"
        api_layout.addRow("Naver Account:", QLabel(naver_status))
        
        firebase_status = "✅ Found" if Config.FIREBASE_CREDENTIALS_PATH else "❌ Not Set"
        api_layout.addRow("Firebase:", QLabel(firebase_status))
        
        layout.addWidget(api_group)
        
        # App Info Group
        info_group = QGroupBox("Application Info")
        info_layout = QFormLayout(info_group)
        
        info_layout.addRow("Version:", QLabel(Config.VERSION))
        info_layout.addRow("Debug Mode:", QLabel("✅ On" if Config.DEBUG_MODE else "❌ Off"))
        info_layout.addRow("Headless Mode:", QLabel("✅ On" if Config.HEADLESS_MODE else "❌ Off"))
        
        layout.addWidget(info_group)
        
        # Instructions
        instructions = QLabel("""
        <h3>Setup Instructions:</h3>
        <ol>
            <li>Create a <code>.env</code> file in the application directory</li>
            <li>Add your API keys:<br>
                <code>GEMINI_API_KEY=your_key_here</code><br>
                <code>NAVER_ID=your_naver_id</code><br>
                <code>NAVER_PW=your_naver_password</code>
            </li>
            <li>Restart the application</li>
        </ol>
        """)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 15px; background-color: #f8f9fa; border-radius: 5px;")
        layout.addWidget(instructions)
        
        layout.addStretch()
        
        return tab
    
    def _setup_statusbar(self):
        """Setup status bar"""
        self.statusBar().showMessage("Ready")
        self.statusBar().setStyleSheet("font-size: 12px; padding: 5px;")
    
    def _on_generate_clicked(self):
        """Handle generate button click"""
        topic = self.topic_input.text().strip()
        
        if not topic:
            QMessageBox.warning(self, "Warning", "Please enter a blog topic.")
            return
        
        if not Config.GEMINI_API_KEY:
            QMessageBox.warning(
                self, "Configuration Required",
                "Gemini API key is not configured.\n\n"
                "Please set GEMINI_API_KEY in your .env file."
            )
            return
        
        self._start_generation(topic)
    
    def _start_generation(self, topic: str):
        """Start background generation"""
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.output_text.clear()
        self.statusBar().showMessage(f"Generating blog about: {topic}")
        
        self.worker = GeneratorWorker(topic)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_generation_finished)
        self.worker.error.connect(self._on_generation_error)
        self.worker.start()
    
    def _on_progress(self, value: int, message: str):
        """Handle progress updates"""
        self.progress_bar.setValue(value)
        self.statusBar().showMessage(message)
    
    def _on_generation_finished(self, content: str):
        """Handle generation completion"""
        self.output_text.setPlainText(content)
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Generation completed!")
        
        QMessageBox.information(self, "Success", "Blog content generated successfully!")
    
    def _on_generation_error(self, error: str):
        """Handle generation error"""
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Generation failed")
        
        QMessageBox.critical(self, "Error", f"Generation failed:\n\n{error}")
        logger.error(f"Generation error: {error}")
    
    def _copy_to_clipboard(self):
        """Copy output to clipboard"""
        from PySide6.QtWidgets import QApplication
        
        content = self.output_text.toPlainText()
        if content:
            QApplication.clipboard().setText(content)
            self.statusBar().showMessage("Content copied to clipboard!")
        else:
            QMessageBox.warning(self, "Warning", "No content to copy.")
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            f"About {Config.APP_NAME}",
            f"<h2>{Config.APP_NAME}</h2>"
            f"<p>Version: {Config.VERSION}</p>"
            f"<p>An automated blog posting tool powered by AI.</p>"
            f"<p>Features:</p>"
            f"<ul>"
            f"<li>AI-powered content generation</li>"
            f"<li>Naver Blog integration</li>"
            f"<li>Firebase database support</li>"
            f"</ul>"
        )
    
    def _show_config_info(self):
        """Show configuration info"""
        info = Config.get_info()
        info_text = "\n".join(f"{k}: {v}" for k, v in info.items())
        
        QMessageBox.information(
            self,
            "Configuration Info",
            f"Current Configuration:\n\n{info_text}"
        )
    
    def closeEvent(self, event):
        """Handle window close event"""
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Application closing")
            event.accept()
        else:
            event.ignore()
