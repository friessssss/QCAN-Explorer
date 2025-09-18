#!/usr/bin/env python3
"""
QCAN Explorer - Modern CAN Network Analysis Tool
Main application entry point
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPalette, QColor

# Add src directory to Python path
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from gui.main_window import MainWindow


def setup_application_style(app):
    """Set up the application's visual style"""
    # Use Fusion style for a modern look
    app.setStyle(QStyleFactory.create('Fusion'))
    
    # Set up dark theme
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    # Fix tooltip colors to ensure visibility
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 204))  # Light yellow background
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)   # Black text
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)


def main():
    """Main application entry point"""
    # Create QApplication instance
    app = QApplication(sys.argv)
    app.setApplicationName("QCAN Explorer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("QCAN Tools")
    
    # Set up application style
    setup_application_style(app)
    
    # Create and show main window
    main_window = MainWindow()
    main_window.show()
    
    # Start the application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
