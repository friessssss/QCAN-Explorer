"""
Main Window for QCAN Explorer
Provides the primary interface with tabbed workspace
"""

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, 
                             QWidget, QMenuBar, QStatusBar, QToolBar, QLabel,
                             QComboBox, QPushButton, QSplitter, QMessageBox, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap

from gui.monitor_tab import MonitorTab
from gui.transmit_tab import TransmitTab
from gui.logging_tab import LoggingTab
from gui.virtual_can_tab import VirtualCANTab
from gui.plotting_tab import PlottingTab
from gui.network_manager_tab import NetworkManagerTab


class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""
    
    # Signals
    interface_connected = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_connections()
        
    def setup_ui(self):
        """Set up the main user interface"""
        self.setWindowTitle("QCAN Explorer - CAN Network Analysis Tool")
        self.setGeometry(100, 100, 1400, 900)
        
        # Set window icon and application properties
        try:
            icon = QIcon("logo.png")
            if not icon.isNull():
                self.setWindowIcon(icon)
                # Set application icon for macOS dock and taskbar
                from PyQt6.QtWidgets import QApplication
                QApplication.instance().setWindowIcon(icon)
        except Exception as e:
            print(f"Warning: Could not set window icon: {e}")
        
        # Create central widget with tab widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create network manager tab (primary multi-network system)
        self.network_manager_tab = NetworkManagerTab()
        self.multi_network_manager = self.network_manager_tab.get_network_manager()
        
        # Create tabs using the multi-network system
        self.monitor_tab = MonitorTab(self.multi_network_manager)
        self.transmit_tab = TransmitTab(self.multi_network_manager)
        self.logging_tab = LoggingTab(self.multi_network_manager)
        self.virtual_can_tab = VirtualCANTab(self.multi_network_manager)
        self.plotting_tab = PlottingTab(self.multi_network_manager)
        
        # Add tabs to widget (Network Manager first)
        self.tab_widget.addTab(self.network_manager_tab, "Network Manager")
        self.tab_widget.addTab(self.monitor_tab, "Monitor")
        self.tab_widget.addTab(self.transmit_tab, "Transmit")
        self.tab_widget.addTab(self.logging_tab, "Logging")
        self.tab_widget.addTab(self.plotting_tab, "Plotting")
        self.tab_widget.addTab(self.virtual_can_tab, "Virtual CAN")
        
        # Symbol files are now managed per-network in the Network Manager
        
        # Connect multi-network manager signals
        self.multi_network_manager.message_received.connect(self.on_multi_network_message_received)
        self.multi_network_manager.error_occurred.connect(self.on_multi_network_error)
        
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
        
        # Network menu
        network_menu = menubar.addMenu("Networks")
        
        connect_all_action = QAction("Connect All Networks", self)
        connect_all_action.setShortcut("Ctrl+Shift+C")
        connect_all_action.triggered.connect(self.connect_all_networks)
        network_menu.addAction(connect_all_action)
        
        disconnect_all_action = QAction("Disconnect All Networks", self)
        disconnect_all_action.setShortcut("Ctrl+Shift+D")
        disconnect_all_action.triggered.connect(self.disconnect_all_networks)
        network_menu.addAction(disconnect_all_action)
        
        network_menu.addSeparator()
        
        refresh_hardware_action = QAction("Refresh Hardware", self)
        refresh_hardware_action.setShortcut("F5")
        refresh_hardware_action.triggered.connect(self.refresh_hardware)
        network_menu.addAction(refresh_hardware_action)
        
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
        
        # Add logo
        try:
            logo_label = QLabel()
            logo_pixmap = QPixmap("logo.png")
            if not logo_pixmap.isNull():
                # Scale logo to appropriate size for toolbar
                scaled_logo = logo_pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, 
                                               Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(scaled_logo)
                logo_label.setToolTip("QCAN Explorer - Professional Multi-Network CAN Analysis")
                toolbar.addWidget(logo_label)
                
                # Add small spacer after logo
                toolbar.addSeparator()
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")
        
        # Network Manager title
        title_label = QLabel("QCAN Explorer - Multi-Network CAN Analysis")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #666666; margin: 5px;")
        toolbar.addWidget(title_label)
        
        # Add spacer widget to push status to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        # Multi-network status
        self.network_status_label = QLabel("Networks: 0 active")
        self.network_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        toolbar.addWidget(self.network_status_label)
        
        # Global network controls
        toolbar.addSeparator()
        
        self.global_connect_btn = QPushButton("Connect All")
        self.global_connect_btn.clicked.connect(self.connect_all_networks)
        self.global_connect_btn.setToolTip("Connect all configured networks")
        toolbar.addWidget(self.global_connect_btn)
        
        self.global_disconnect_btn = QPushButton("Disconnect All")
        self.global_disconnect_btn.clicked.connect(self.disconnect_all_networks)
        self.global_disconnect_btn.setToolTip("Disconnect all active networks")
        toolbar.addWidget(self.global_disconnect_btn)
        
    def setup_statusbar(self):
        """Set up the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Network-focused status labels
        self.networks_status_label = QLabel("Networks: 0/0")
        self.message_count_label = QLabel("Messages: 0")
        self.error_count_label = QLabel("Errors: 0")
        
        self.status_bar.addWidget(self.networks_status_label)
        self.status_bar.addPermanentWidget(self.message_count_label)
        self.status_bar.addPermanentWidget(self.error_count_label)
        
        # Update timer for status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
    def setup_connections(self):
        """Set up signal connections"""
        # Multi-network manager is the primary system now
        pass
        
    def connect_all_networks(self):
        """Connect all configured networks that have hardware assigned"""
        connected_count = 0
        total_networks = len(self.multi_network_manager.get_all_networks())
        
        if total_networks == 0:
            QMessageBox.information(self, "Connect All", 
                                  "No networks configured. Please use the Network Manager tab to create networks.")
            return
        
        # Try to connect networks that have available hardware
        hardware_interfaces = self.multi_network_manager.get_available_hardware()
        available_hardware = [hw for hw in hardware_interfaces if hw.available]
        
        networks = self.multi_network_manager.get_all_networks()
        for network_id, network in networks.items():
            if not network.is_connected() and available_hardware:
                # Try to assign the first available hardware
                hardware = available_hardware.pop(0)
                hardware_key = f"{hardware.interface_type}:{hardware.channel}"
                if self.multi_network_manager.connect_network(network_id, hardware_key):
                    connected_count += 1
                    
        if connected_count > 0:
            self.status_bar.showMessage(f"Connected {connected_count} of {total_networks} networks", 5000)
        else:
            self.status_bar.showMessage("No networks could be connected - check hardware availability", 5000)
            
    def disconnect_all_networks(self):
        """Disconnect all active networks"""
        self.multi_network_manager.disconnect_all_networks()
        self.status_bar.showMessage("All networks disconnected", 3000)
        
    def refresh_hardware(self):
        """Refresh hardware interface discovery"""
        self.multi_network_manager.discover_hardware()
        self.status_bar.showMessage("Hardware interfaces refreshed", 2000)
            
    def update_status(self):
        """Update status bar information"""
        # Multi-network stats (primary system)
        multi_stats = self.multi_network_manager.get_global_statistics()
        total_messages = multi_stats.get('total_messages', 0)
        total_errors = multi_stats.get('total_errors', 0)
        active_networks = multi_stats.get('active_connections', 0)
        total_networks = multi_stats.get('total_networks', 0)
        
        # Update status displays
        self.message_count_label.setText(f"Messages: {total_messages}")
        self.error_count_label.setText(f"Errors: {total_errors}")
        self.networks_status_label.setText(f"Networks: {active_networks}/{total_networks}")
        self.network_status_label.setText(f"Networks: {active_networks}/{total_networks} active")
        
        # Update global button states
        self.global_connect_btn.setEnabled(active_networks < total_networks)
        self.global_disconnect_btn.setEnabled(active_networks > 0)
        
    def show_about(self):
        """Show about dialog"""
        # Create custom about dialog with logo
        about_dialog = QMessageBox(self)
        about_dialog.setWindowTitle("About QCAN Explorer")
        
        # Try to add logo to the dialog
        try:
            logo_pixmap = QPixmap("logo.png")
            if not logo_pixmap.isNull():
                # Scale logo for dialog
                scaled_logo = logo_pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, 
                                               Qt.TransformationMode.SmoothTransformation)
                about_dialog.setIconPixmap(scaled_logo)
        except Exception:
            pass
            
        about_dialog.setText(
            "QCAN Explorer v2.0.0\n\n"
            "Professional Multi-Network CAN Analysis Tool\n"
            "Built with Python and PyQt6\n\n"
            "Features:\n"
            "• Multi-network CAN bus monitoring\n"
            "• Hardware auto-discovery\n"
            "• Real-time message analysis\n"
            "• Bus number identification\n"
            "• Message transmission & logging\n"
            "• Per-network symbolic representation\n"
            "• Network configuration management\n"
            "• PCAN Explorer compatibility"
        )
        
        about_dialog.exec()
        
    def on_multi_network_message_received(self, network_id: str, message):
        """Handle messages received from multi-network manager"""
        # Forward to existing tabs that expect CAN messages
        # This provides integration between new multi-network system and existing tabs
        pass  # For now, existing tabs use the legacy interface
        
    def on_multi_network_error(self, network_id: str, error: str):
        """Handle errors from multi-network manager"""
        self.status_bar.showMessage(f"Network {network_id}: {error}", 5000)
        
    def closeEvent(self, event):
        """Handle application close event"""
        # Check if any networks are connected
        multi_stats = self.multi_network_manager.get_global_statistics()
        active_networks = multi_stats.get('active_connections', 0)
        
        if active_networks > 0:
            reply = QMessageBox.question(self, "Confirm Exit",
                                       f"There are {active_networks} active network connections. Disconnect and exit?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # Shutdown multi-network manager
                self.network_manager_tab.shutdown()
                event.accept()
            else:
                event.ignore()
        else:
            # Shutdown cleanly
            self.network_manager_tab.shutdown()
            event.accept()
            
    # Symbol files are now managed per-network - no global symbol parser needed
