"""
Main Window for QCAN Explorer
Provides the primary interface with tabbed workspace
"""

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, 
                             QWidget, QMenuBar, QStatusBar, QToolBar, QLabel,
                             QComboBox, QPushButton, QSplitter, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon

from gui.monitor_tab import MonitorTab
from gui.transmit_tab import TransmitTab
from gui.logging_tab import LoggingTab
from gui.symbols_tab import SymbolsTab
from gui.virtual_can_tab import VirtualCANTab
from gui.plotting_tab import PlottingTab
from canbus.interface_manager import CANInterfaceManager


class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""
    
    # Signals
    interface_connected = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.can_manager = CANInterfaceManager()
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_connections()
        
    def setup_ui(self):
        """Set up the main user interface"""
        self.setWindowTitle("QCAN Explorer - CAN Network Analysis Tool")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget with tab widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.monitor_tab = MonitorTab(self.can_manager)
        self.transmit_tab = TransmitTab(self.can_manager)
        self.logging_tab = LoggingTab(self.can_manager)
        self.symbols_tab = SymbolsTab(self.can_manager)
        self.virtual_can_tab = VirtualCANTab(self.can_manager)
        self.plotting_tab = PlottingTab(self.can_manager)
        
        # Add tabs to widget
        self.tab_widget.addTab(self.monitor_tab, "Monitor")
        self.tab_widget.addTab(self.transmit_tab, "Transmit")
        self.tab_widget.addTab(self.logging_tab, "Logging")
        self.tab_widget.addTab(self.symbols_tab, "Symbols")
        self.tab_widget.addTab(self.plotting_tab, "Plotting")
        self.tab_widget.addTab(self.virtual_can_tab, "Virtual CAN")
        
        # Connect SYM parser from symbols tab to monitor tab
        self.symbols_tab.sym_parser_changed.connect(self.on_sym_parser_changed)
        
    def setup_menu(self):
        """Set up the application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Configuration", self)
        new_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Configuration", self)
        open_action.setShortcut("Ctrl+O")
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Configuration", self)
        save_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Interface menu
        interface_menu = menubar.addMenu("Interface")
        
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self.connect_interface)
        interface_menu.addAction(connect_action)
        
        disconnect_action = QAction("Disconnect", self)
        disconnect_action.triggered.connect(self.disconnect_interface)
        interface_menu.addAction(disconnect_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def setup_toolbar(self):
        """Set up the main toolbar"""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Interface selection
        toolbar.addWidget(QLabel("Interface:"))
        self.interface_combo = QComboBox()
        # Get available interfaces and add them
        available_interfaces = self.can_manager.get_available_interfaces()
        self.interface_combo.addItems(["Select Interface..."] + available_interfaces)
        toolbar.addWidget(self.interface_combo)
        
        # Channel selection
        toolbar.addWidget(QLabel("Channel:"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["virtual0", "virtual1", "can0", "can1", "PCAN_USBBUS1", "PCAN_USBBUS2"])
        toolbar.addWidget(self.channel_combo)
        
        # Bitrate selection
        toolbar.addWidget(QLabel("Bitrate:"))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["125000", "250000", "500000", "1000000"])
        self.bitrate_combo.setCurrentText("500000")
        toolbar.addWidget(self.bitrate_combo)
        
        toolbar.addSeparator()
        
        # Connect/Disconnect buttons
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_interface)
        toolbar.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_interface)
        self.disconnect_btn.setEnabled(False)
        toolbar.addWidget(self.disconnect_btn)
        
    def setup_statusbar(self):
        """Set up the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Status labels
        self.connection_label = QLabel("Disconnected")
        self.message_count_label = QLabel("Messages: 0")
        self.error_count_label = QLabel("Errors: 0")
        
        self.status_bar.addWidget(self.connection_label)
        self.status_bar.addPermanentWidget(self.message_count_label)
        self.status_bar.addPermanentWidget(self.error_count_label)
        
        # Update timer for status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
    def setup_connections(self):
        """Set up signal connections"""
        self.interface_connected.connect(self.on_interface_connected)
        
    def connect_interface(self):
        """Connect to the selected CAN interface"""
        interface_type = self.interface_combo.currentText()
        channel = self.channel_combo.currentText()
        bitrate = int(self.bitrate_combo.currentText())
        
        if interface_type == "Select Interface...":
            QMessageBox.warning(self, "Warning", "Please select a CAN interface")
            return
            
        try:
            success = self.can_manager.connect(interface_type, channel, bitrate)
            if success:
                self.interface_connected.emit(True)
                self.status_bar.showMessage("Connected successfully", 3000)
            else:
                QMessageBox.critical(self, "Error", "Failed to connect to CAN interface")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error: {str(e)}")
            
    def disconnect_interface(self):
        """Disconnect from the CAN interface"""
        self.can_manager.disconnect()
        self.interface_connected.emit(False)
        self.status_bar.showMessage("Disconnected", 3000)
        
    def on_interface_connected(self, connected):
        """Handle interface connection state changes"""
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected)
        
        if connected:
            self.connection_label.setText("Connected")
            self.connection_label.setStyleSheet("color: green")
        else:
            self.connection_label.setText("Disconnected")
            self.connection_label.setStyleSheet("color: red")
            
    def update_status(self):
        """Update status bar information"""
        stats = self.can_manager.get_statistics()
        self.message_count_label.setText(f"Messages: {stats.get('message_count', 0)}")
        self.error_count_label.setText(f"Errors: {stats.get('error_count', 0)}")
        
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About QCAN Explorer", 
                         "QCAN Explorer v1.0.0\\n\\n"
                         "Modern CAN Network Analysis Tool\\n"
                         "Built with Python and PyQt6\\n\\n"
                         "Features:\\n"
                         "• Real-time message monitoring\\n"
                         "• Message transmission\\n"
                         "• Symbolic representation\\n"
                         "• Data logging & playback\\n"
                         "• Multi-interface support")
        
    def closeEvent(self, event):
        """Handle application close event"""
        if self.can_manager.is_connected():
            reply = QMessageBox.question(self, "Confirm Exit",
                                       "CAN interface is still connected. Disconnect and exit?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.can_manager.disconnect()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
            
    def on_sym_parser_changed(self, parser):
        """Handle SYM parser changes from symbols tab"""
        self.monitor_tab.set_sym_parser(parser)
        self.logging_tab.set_sym_parser(parser)
        self.plotting_tab.set_sym_parser(parser)
