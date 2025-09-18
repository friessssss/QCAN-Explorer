"""
Network Manager Tab - Multi-network CAN interface management
"""

from typing import Dict, List, Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
                             QGroupBox, QLabel, QPushButton, QComboBox, QSpinBox,
                             QLineEdit, QTextEdit, QCheckBox, QProgressBar,
                             QHeaderView, QMessageBox, QDialog, QDialogButtonBox,
                             QFormLayout, QTabWidget, QFrame, QFileDialog)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

from canbus.multi_network_manager import MultiNetworkManager
from canbus.network import NetworkConfiguration, HardwareInterface, ConnectionState, NetworkProtocol


class NetworkConfigDialog(QDialog):
    """Dialog for creating/editing network configurations"""
    
    def __init__(self, config: Optional[NetworkConfiguration] = None, parent=None):
        super().__init__(parent)
        self.config = config or NetworkConfiguration()
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        self.setWindowTitle("Network Configuration")
        self.setModal(True)
        self.resize(500, 600)
        
        layout = QVBoxLayout(self)
        
        # Create form layout
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        
        # Basic settings
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter network name")
        form_layout.addRow("Network Name:", self.name_edit)
        
        self.bus_number_spin = QSpinBox()
        self.bus_number_spin.setRange(1, 99)
        self.bus_number_spin.setValue(1)
        self.bus_number_spin.setToolTip("Bus number for message identification")
        form_layout.addRow("Bus Number:", self.bus_number_spin)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Optional description")
        form_layout.addRow("Description:", self.description_edit)
        
        # CAN settings
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.setEditable(True)
        self.bitrate_combo.addItems(["125000", "250000", "500000", "1000000"])
        form_layout.addRow("Bit Rate (bps):", self.bitrate_combo)
        
        self.sample_point_spin = QSpinBox()
        self.sample_point_spin.setRange(50, 90)
        self.sample_point_spin.setValue(75)
        self.sample_point_spin.setSuffix("%")
        form_layout.addRow("Sample Point:", self.sample_point_spin)
        
        self.protocol_combo = QComboBox()
        for protocol in NetworkProtocol:
            self.protocol_combo.addItem(protocol.value, protocol)
        form_layout.addRow("Protocol:", self.protocol_combo)
        
        # Advanced settings
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QFormLayout(advanced_group)
        
        self.listen_only_check = QCheckBox()
        self.listen_only_check.setToolTip("Enable listen-only mode (no transmission)")
        advanced_layout.addRow("Listen Only:", self.listen_only_check)
        
        self.error_frames_check = QCheckBox()
        self.error_frames_check.setChecked(True)
        self.error_frames_check.setToolTip("Enable error frame reception")
        advanced_layout.addRow("Error Frames:", self.error_frames_check)
        
        self.auto_reconnect_check = QCheckBox()
        self.auto_reconnect_check.setChecked(True)
        self.auto_reconnect_check.setToolTip("Automatically reconnect on connection loss")
        advanced_layout.addRow("Auto Reconnect:", self.auto_reconnect_check)
        
        self.reconnect_delay_spin = QSpinBox()
        self.reconnect_delay_spin.setRange(1, 60)
        self.reconnect_delay_spin.setValue(5)
        self.reconnect_delay_spin.setSuffix(" seconds")
        self.reconnect_delay_spin.setToolTip("Delay between reconnection attempts")
        advanced_layout.addRow("Reconnect Delay:", self.reconnect_delay_spin)
        
        # Symbol file selection
        symbol_layout = QHBoxLayout()
        self.symbol_file_edit = QLineEdit()
        self.symbol_file_edit.setPlaceholderText("No symbol file selected")
        self.symbol_file_edit.setReadOnly(True)
        symbol_layout.addWidget(self.symbol_file_edit)
        
        self.browse_symbol_btn = QPushButton("Browse...")
        self.browse_symbol_btn.clicked.connect(self.browse_symbol_file)
        symbol_layout.addWidget(self.browse_symbol_btn)
        
        self.clear_symbol_btn = QPushButton("Clear")
        self.clear_symbol_btn.clicked.connect(self.clear_symbol_file)
        symbol_layout.addWidget(self.clear_symbol_btn)
        
        advanced_layout.addRow("Symbol File:", symbol_layout)
        
        layout.addWidget(form_widget)
        layout.addWidget(advanced_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def load_config(self):
        """Load configuration into UI"""
        self.name_edit.setText(self.config.name)
        self.bus_number_spin.setValue(self.config.bus_number)
        self.description_edit.setPlainText(self.config.description)
        self.bitrate_combo.setCurrentText(str(self.config.bitrate))
        self.sample_point_spin.setValue(int(self.config.sample_point * 100))
        
        # Set protocol
        for i in range(self.protocol_combo.count()):
            if self.protocol_combo.itemData(i) == self.config.protocol:
                self.protocol_combo.setCurrentIndex(i)
                break
                
        self.listen_only_check.setChecked(self.config.listen_only)
        self.error_frames_check.setChecked(self.config.enable_error_frames)
        self.auto_reconnect_check.setChecked(self.config.auto_reconnect)
        self.reconnect_delay_spin.setValue(self.config.reconnect_delay)
        self.symbol_file_edit.setText(self.config.symbol_file_path)
        
    def get_config(self) -> NetworkConfiguration:
        """Get configuration from UI"""
        self.config.name = self.name_edit.text() or "New Network"
        self.config.bus_number = self.bus_number_spin.value()
        self.config.description = self.description_edit.toPlainText()
        self.config.bitrate = int(self.bitrate_combo.currentText())
        self.config.sample_point = self.sample_point_spin.value() / 100.0
        self.config.protocol = self.protocol_combo.currentData()
        self.config.listen_only = self.listen_only_check.isChecked()
        self.config.enable_error_frames = self.error_frames_check.isChecked()
        self.config.auto_reconnect = self.auto_reconnect_check.isChecked()
        self.config.reconnect_delay = self.reconnect_delay_spin.value()
        self.config.symbol_file_path = self.symbol_file_edit.text()
        
        return self.config
    
    def browse_symbol_file(self):
        """Browse for symbol file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Symbol File", "", 
            "Symbol Files (*.sym);;All Files (*)"
        )
        if filename:
            self.symbol_file_edit.setText(filename)
    
    def clear_symbol_file(self):
        """Clear symbol file selection"""
        self.symbol_file_edit.clear()


class NetworkManagerTab(QWidget):
    """Network management tab for multi-network CAN interface management"""
    
    # Signals
    network_selected = pyqtSignal(str)  # network_id
    message_received = pyqtSignal(str, object)  # network_id, CANMessage
    message_transmitted = pyqtSignal(str, object)  # network_id, CANMessage
    
    def __init__(self):
        super().__init__()
        self.network_manager = MultiNetworkManager()
        self.setup_ui()
        self.setup_connections()
        self.setup_timers()
        
        # Load or create default configuration
        if not self.network_manager.load_configuration():
            self.network_manager.create_default_networks()
            
    def setup_ui(self):
        """Set up the network manager UI"""
        layout = QHBoxLayout(self)
        
        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)
        
        # Left panel - Network list and hardware
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)
        
        # Right panel - Network details and controls
        right_panel = self.create_right_panel()
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        main_splitter.setSizes([400, 600])
        
    def create_left_panel(self) -> QWidget:
        """Create left panel with network list and hardware"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Network list
        networks_group = QGroupBox("CAN Networks")
        networks_layout = QVBoxLayout(networks_group)
        
        # Network list controls
        network_controls = QHBoxLayout()
        self.add_network_btn = QPushButton("Add Network")
        self.add_network_btn.clicked.connect(self.add_network)
        network_controls.addWidget(self.add_network_btn)
        
        self.edit_network_btn = QPushButton("Edit")
        self.edit_network_btn.clicked.connect(self.edit_network)
        self.edit_network_btn.setEnabled(False)
        network_controls.addWidget(self.edit_network_btn)
        
        self.remove_network_btn = QPushButton("Remove")
        self.remove_network_btn.clicked.connect(self.remove_network)
        self.remove_network_btn.setEnabled(False)
        network_controls.addWidget(self.remove_network_btn)
        
        network_controls.addStretch()
        networks_layout.addLayout(network_controls)
        
        # Network tree
        self.network_tree = QTreeWidget()
        self.network_tree.setHeaderLabels(["Network", "Bus", "Status", "Hardware", "Symbol File"])
        self.network_tree.itemSelectionChanged.connect(self.on_network_selection_changed)
        networks_layout.addWidget(self.network_tree)
        
        layout.addWidget(networks_group)
        
        # Hardware interfaces
        hardware_group = QGroupBox("Hardware Interfaces")
        hardware_layout = QVBoxLayout(hardware_group)
        
        # Hardware controls
        hardware_controls = QHBoxLayout()
        self.refresh_hardware_btn = QPushButton("Refresh")
        self.refresh_hardware_btn.clicked.connect(self.refresh_hardware)
        hardware_controls.addWidget(self.refresh_hardware_btn)
        hardware_controls.addStretch()
        hardware_layout.addLayout(hardware_controls)
        
        # Hardware table
        self.hardware_table = QTableWidget()
        self.hardware_table.setColumnCount(4)
        self.hardware_table.setHorizontalHeaderLabels(["Type", "Channel", "Name", "Status"])
        self.hardware_table.horizontalHeader().setStretchLastSection(True)
        self.hardware_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        hardware_layout.addWidget(self.hardware_table)
        
        layout.addWidget(hardware_group)
        
        return panel
        
    def create_right_panel(self) -> QWidget:
        """Create right panel with network details and controls"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Add logo header to right panel
        try:
            header_layout = QHBoxLayout()
            logo_label = QLabel()
            logo_pixmap = QPixmap("logo.png")
            if not logo_pixmap.isNull():
                scaled_logo = logo_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, 
                                               Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(scaled_logo)
                header_layout.addWidget(logo_label)
                
            header_title = QLabel("Network Management")
            header_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #666666;")
            header_layout.addWidget(header_title)
            header_layout.addStretch()
            
            layout.addLayout(header_layout)
        except Exception:
            pass
        
        # Network details
        details_group = QGroupBox("Network Details")
        details_layout = QVBoxLayout(details_group)
        
        # Network info
        info_layout = QFormLayout()
        self.network_name_label = QLabel("No network selected")
        self.network_name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        info_layout.addRow("Name:", self.network_name_label)
        
        self.network_status_label = QLabel("Disconnected")
        info_layout.addRow("Status:", self.network_status_label)
        
        self.network_hardware_label = QLabel("None")
        info_layout.addRow("Hardware:", self.network_hardware_label)
        
        self.network_bitrate_label = QLabel("N/A")
        info_layout.addRow("Bit Rate:", self.network_bitrate_label)
        
        self.network_bus_number_label = QLabel("N/A")
        info_layout.addRow("Bus Number:", self.network_bus_number_label)
        
        self.network_symbol_file_label = QLabel("N/A")
        info_layout.addRow("Symbol File:", self.network_symbol_file_label)
        
        details_layout.addLayout(info_layout)
        
        # Connection controls
        connection_controls = QHBoxLayout()
        
        self.hardware_combo = QComboBox()
        self.hardware_combo.setMinimumWidth(200)
        self.hardware_combo.currentTextChanged.connect(self.on_hardware_selection_changed)
        connection_controls.addWidget(QLabel("Hardware:"))
        connection_controls.addWidget(self.hardware_combo)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_network)
        self.connect_btn.setEnabled(False)
        connection_controls.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_network)
        self.disconnect_btn.setEnabled(False)
        connection_controls.addWidget(self.disconnect_btn)
        
        connection_controls.addStretch()
        details_layout.addLayout(connection_controls)
        
        # Symbol file controls
        symbol_controls = QHBoxLayout()
        
        symbol_controls.addWidget(QLabel("Symbol File:"))
        
        self.change_symbol_btn = QPushButton("Change Symbol File")
        self.change_symbol_btn.clicked.connect(self.change_symbol_file)
        self.change_symbol_btn.setEnabled(False)
        symbol_controls.addWidget(self.change_symbol_btn)
        
        self.remove_symbol_btn = QPushButton("Remove Symbol File")
        self.remove_symbol_btn.clicked.connect(self.remove_symbol_file)
        self.remove_symbol_btn.setEnabled(False)
        symbol_controls.addWidget(self.remove_symbol_btn)
        
        symbol_controls.addStretch()
        details_layout.addLayout(symbol_controls)
        
        layout.addWidget(details_group)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        # Create statistics table
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.verticalHeader().setVisible(False)
        stats_layout.addWidget(self.stats_table)
        
        layout.addWidget(stats_group)
        
        # Global controls
        global_group = QGroupBox("Global Controls")
        global_layout = QVBoxLayout(global_group)
        
        global_controls = QHBoxLayout()
        
        self.connect_all_btn = QPushButton("Connect All")
        self.connect_all_btn.clicked.connect(self.connect_all_networks)
        global_controls.addWidget(self.connect_all_btn)
        
        self.disconnect_all_btn = QPushButton("Disconnect All")
        self.disconnect_all_btn.clicked.connect(self.disconnect_all_networks)
        global_controls.addWidget(self.disconnect_all_btn)
        
        global_controls.addStretch()
        
        self.save_config_btn = QPushButton("Save Config")
        self.save_config_btn.clicked.connect(self.save_configuration)
        global_controls.addWidget(self.save_config_btn)
        
        self.load_config_btn = QPushButton("Load Config")
        self.load_config_btn.clicked.connect(self.load_configuration)
        global_controls.addWidget(self.load_config_btn)
        
        global_layout.addLayout(global_controls)
        
        layout.addWidget(global_group)
        
        return panel
        
    def setup_connections(self):
        """Set up signal connections"""
        # Network manager signals
        self.network_manager.network_added.connect(self.on_network_added)
        self.network_manager.network_removed.connect(self.on_network_removed)
        self.network_manager.network_state_changed.connect(self.on_network_state_changed)
        self.network_manager.message_received.connect(self.message_received.emit)
        self.network_manager.message_transmitted.connect(self.message_transmitted.emit)
        self.network_manager.error_occurred.connect(self.on_error_occurred)
        self.network_manager.hardware_discovered.connect(self.on_hardware_discovered)
        
    def setup_timers(self):
        """Set up update timers"""
        # Statistics update timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start(1000)  # Update every second
        
        # UI refresh timer (reduced frequency to avoid selection loss)
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.refresh_ui)
        self.ui_timer.start(5000)  # Refresh every 5 seconds
        
    def add_network(self):
        """Add a new network configuration"""
        dialog = NetworkConfigDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            self.network_manager.create_network(config)
            
    def edit_network(self):
        """Edit selected network configuration"""
        current_item = self.network_tree.currentItem()
        if not current_item:
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        network = self.network_manager.get_network(network_id)
        
        if network:
            dialog = NetworkConfigDialog(network.config, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Update network configuration
                network.config = dialog.get_config()
                self.refresh_network_list()
                
    def remove_network(self):
        """Remove selected network"""
        current_item = self.network_tree.currentItem()
        if not current_item:
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        network = self.network_manager.get_network(network_id)
        
        if network:
            reply = QMessageBox.question(
                self, "Remove Network",
                f"Are you sure you want to remove network '{network.config.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.network_manager.remove_network(network_id)
                
    def connect_network(self):
        """Connect selected network to selected hardware"""
        current_item = self.network_tree.currentItem()
        if not current_item:
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        hardware_text = self.hardware_combo.currentText()
        
        if hardware_text and hardware_text != "Select hardware...":
            # Extract hardware key from combo text
            hardware_key = self.hardware_combo.currentData()
            if hardware_key:
                success = self.network_manager.connect_network(network_id, hardware_key)
                if not success:
                    QMessageBox.warning(self, "Connection Failed", 
                                      "Failed to connect to hardware interface")
                    
    def disconnect_network(self):
        """Disconnect selected network"""
        current_item = self.network_tree.currentItem()
        if not current_item:
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        self.network_manager.disconnect_network(network_id)
        
    def connect_all_networks(self):
        """Connect all networks that have hardware assigned"""
        # This would need logic to assign hardware to networks
        QMessageBox.information(self, "Connect All", "Feature not yet implemented")
        
    def disconnect_all_networks(self):
        """Disconnect all networks"""
        self.network_manager.disconnect_all_networks()
        
    def change_symbol_file(self):
        """Change symbol file for selected network"""
        current_item = self.network_tree.currentItem()
        if not current_item:
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        network = self.network_manager.get_network(network_id)
        
        if network:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Select Symbol File", network.config.symbol_file_path,
                "Symbol Files (*.sym);;All Files (*)"
            )
            
            if filename:
                network.set_symbol_file(filename)
                self.refresh_network_list()
                self.update_network_details()
                
                # Auto-save configuration
                self.network_manager.save_configuration()
                
    def remove_symbol_file(self):
        """Remove symbol file from selected network"""
        current_item = self.network_tree.currentItem()
        if not current_item:
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        network = self.network_manager.get_network(network_id)
        
        if network:
            reply = QMessageBox.question(
                self, "Remove Symbol File",
                f"Remove symbol file from network '{network.config.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                network.set_symbol_file("")
                self.refresh_network_list()
                self.update_network_details()
                
                # Auto-save configuration
                self.network_manager.save_configuration()
    
    def on_hardware_selection_changed(self):
        """Handle hardware selection change"""
        self.update_connect_button_state()
    
    def update_connect_button_state(self):
        """Update the connect button state based on current conditions"""
        current_item = self.network_tree.currentItem()
        if not current_item:
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        network = self.network_manager.get_network(network_id)
        
        if network:
            # Check hardware selection
            hardware_data = self.hardware_combo.currentData()
            hardware_text = self.hardware_combo.currentText()
            has_hardware = (hardware_data is not None and 
                           hardware_text != "Select hardware..." and
                           hardware_text != "No networks connected")
            
            # Ensure is_connected returns a proper boolean
            is_connected = bool(network.is_connected())
            
            # Enable connect button if:
            # - Network is not connected AND
            # - Valid hardware is selected
            connect_enabled = not is_connected and has_hardware
            disconnect_enabled = is_connected
            
            # Ensure we have proper boolean values
            self.connect_btn.setEnabled(bool(connect_enabled))
            self.disconnect_btn.setEnabled(bool(disconnect_enabled))
            
        else:
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
        
    def refresh_hardware(self):
        """Refresh hardware interface discovery"""
        self.network_manager.discover_hardware()
        
    def save_configuration(self):
        """Save network configuration"""
        if self.network_manager.save_configuration():
            QMessageBox.information(self, "Save Configuration", "Configuration saved successfully")
        else:
            QMessageBox.warning(self, "Save Configuration", "Failed to save configuration")
            
    def load_configuration(self):
        """Load network configuration"""
        if self.network_manager.load_configuration():
            QMessageBox.information(self, "Load Configuration", "Configuration loaded successfully")
            self.refresh_network_list()
        else:
            QMessageBox.warning(self, "Load Configuration", "Failed to load configuration")
            
    @pyqtSlot(str)
    def on_network_added(self, network_id: str):
        """Handle network added"""
        self.refresh_network_list()
        
    @pyqtSlot(str)
    def on_network_removed(self, network_id: str):
        """Handle network removed"""
        self.refresh_network_list()
        
    @pyqtSlot(str, object)
    def on_network_state_changed(self, network_id: str, state: ConnectionState):
        """Handle network state change"""
        # Only refresh the specific network item instead of the entire list
        self.update_network_item_status(network_id, state)
        self.update_network_details()
        
        # Update hardware combo availability and connect button state
        # This will now show binding status and disable bound interfaces
        available_hardware = self.network_manager.get_available_hardware()
        self.update_hardware_combo(available_hardware)
        self.update_hardware_table(available_hardware)  # Also update the hardware table
        self.update_connect_button_state()
        
    @pyqtSlot(str, str)
    def on_error_occurred(self, network_id: str, error: str):
        """Handle network error"""
        QMessageBox.warning(self, f"Network Error ({network_id})", error)
        
    @pyqtSlot(list)
    def on_hardware_discovered(self, interfaces: List[HardwareInterface]):
        """Handle hardware discovery"""
        # Update both hardware table and combo with binding status
        self.update_hardware_table(interfaces)
        self.update_hardware_combo(interfaces)
        
    def on_network_selection_changed(self):
        """Handle network selection change"""
        current_item = self.network_tree.currentItem()
        has_selection = current_item is not None
        
        self.edit_network_btn.setEnabled(has_selection)
        self.remove_network_btn.setEnabled(has_selection)
        self.change_symbol_btn.setEnabled(has_selection)
        self.remove_symbol_btn.setEnabled(has_selection)
        
        if has_selection:
            network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
            self.network_selected.emit(network_id)
            
        self.update_network_details()
        # Ensure connect button state is updated when selection changes
        self.update_connect_button_state()
        
    def refresh_network_list(self):
        """Refresh the network list while preserving selection"""
        # Save current selection
        current_item = self.network_tree.currentItem()
        selected_network_id = None
        if current_item:
            selected_network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        
        # Block signals during refresh to prevent selection events
        self.network_tree.blockSignals(True)
        
        # Clear and rebuild
        self.network_tree.clear()
        
        networks = self.network_manager.get_all_networks()
        selected_item = None
        
        for network_id, network in networks.items():
            item = QTreeWidgetItem()
            item.setText(0, network.config.name)
            item.setData(0, Qt.ItemDataRole.UserRole, network_id)
            
            # Bus number
            item.setText(1, str(network.config.bus_number))
            
            # Status
            if network.is_connected():
                item.setText(2, "Connected")
                item.setForeground(2, QColor("green"))
            else:
                item.setText(2, "Disconnected")
                item.setForeground(2, QColor("red"))
                
            # Hardware
            if network.hardware:
                item.setText(3, f"{network.hardware.interface_type}:{network.hardware.channel}")
            else:
                item.setText(3, "None")
                
            # Symbol file
            if network.config.symbol_file_path:
                import os
                symbol_file_name = os.path.basename(network.config.symbol_file_path)
                item.setText(4, symbol_file_name)
                item.setToolTip(4, network.config.symbol_file_path)
            else:
                item.setText(4, "None")
                item.setToolTip(4, "No symbol file assigned")
                
            self.network_tree.addTopLevelItem(item)
            
            # Mark for re-selection if this was the previously selected item
            if network_id == selected_network_id:
                selected_item = item
        
        # Restore selection and unblock signals
        self.network_tree.blockSignals(False)
        if selected_item:
            self.network_tree.setCurrentItem(selected_item)
    
    def update_network_item_status(self, network_id: str, state):
        """Update the status of a specific network item without full refresh"""
        network = self.network_manager.get_network(network_id)
        if not network:
            return
            
        # Find the tree item for this network
        for i in range(self.network_tree.topLevelItemCount()):
            item = self.network_tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == network_id:
                # Update status column only
                if network.is_connected():
                    item.setText(2, "Connected")
                    item.setForeground(2, QColor("green"))
                else:
                    item.setText(2, "Disconnected")
                    item.setForeground(2, QColor("red"))
                    
                # Update hardware column if needed
                if network.hardware:
                    item.setText(3, f"{network.hardware.interface_type}:{network.hardware.channel}")
                else:
                    item.setText(3, "None")
                    
                # Update symbol file column
                if network.config.symbol_file_path:
                    import os
                    symbol_file_name = os.path.basename(network.config.symbol_file_path)
                    item.setText(4, symbol_file_name)
                    item.setToolTip(4, network.config.symbol_file_path)
                else:
                    item.setText(4, "None")
                    item.setToolTip(4, "No symbol file assigned")
                break
            
    def update_hardware_table(self, interfaces: List[HardwareInterface]):
        """Update hardware interfaces table with binding status"""
        self.hardware_table.setRowCount(len(interfaces))
        bound_interfaces = self.get_bound_interfaces()
        
        for row, interface in enumerate(interfaces):
            self.hardware_table.setItem(row, 0, QTableWidgetItem(interface.interface_type))
            self.hardware_table.setItem(row, 1, QTableWidgetItem(interface.channel))
            self.hardware_table.setItem(row, 2, QTableWidgetItem(interface.name))
            
            # Check if this interface is bound to a network
            hardware_key = f"{interface.interface_type}:{interface.channel}"
            
            if hardware_key in bound_interfaces:
                # Interface is bound to a network
                bound_network = bound_interfaces[hardware_key]
                status_text = f"Bound to {bound_network}"
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(QColor("orange"))
                status_item.setToolTip(f"Currently connected to network: {bound_network}")
            elif interface.available:
                # Interface is available for connection
                status_item = QTableWidgetItem("Available")
                status_item.setForeground(QColor("green"))
                status_item.setToolTip("Available for connection")
            else:
                # Interface exists but not available (hardware issue)
                status_item = QTableWidgetItem("Unavailable")
                status_item.setForeground(QColor("red"))
                status_item.setToolTip("Hardware interface not available")
                
            self.hardware_table.setItem(row, 3, status_item)
            
    def get_selected_network(self):
        """Get the currently selected network"""
        current_item = self.network_tree.currentItem()
        if not current_item:
            return None
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not network_id:
            return None
            
        return self.network_manager.get_network(network_id)
    
    def get_bound_interfaces(self) -> Dict[str, str]:
        """Get dictionary of bound interface keys to network names"""
        bound_interfaces = {}
        
        for network_id, network in self.network_manager.get_all_networks().items():
            if network.is_connected() and network.connection and network.connection.hardware:
                # Get the hardware key from the connection's hardware interface
                hardware = network.connection.hardware
                hardware_key = f"{hardware.interface_type}:{hardware.channel}"
                bound_interfaces[hardware_key] = network.config.name
                
        return bound_interfaces
    
    def update_hardware_combo(self, interfaces: List[HardwareInterface]):
        """Update hardware selection combo with binding status"""
        current_text = self.hardware_combo.currentText()
        current_network = self.get_selected_network()
        current_network_hardware = None
        
        # Get the hardware key for the currently selected network if connected
        if current_network and current_network.is_connected() and current_network.connection and current_network.connection.hardware:
            hardware = current_network.connection.hardware
            current_network_hardware = f"{hardware.interface_type}:{hardware.channel}"
        
        bound_interfaces = self.get_bound_interfaces()
        
        self.hardware_combo.clear()
        self.hardware_combo.addItem("Select hardware...", None)
        
        for interface in interfaces:
            if interface.available:
                hardware_key = f"{interface.interface_type}:{interface.channel}"
                base_text = f"{interface.name} ({interface.interface_type}:{interface.channel})"
                
                # Check if this interface is bound to a network
                if hardware_key in bound_interfaces:
                    bound_network = bound_interfaces[hardware_key]
                    
                    # If this is the currently selected network's interface, show as "Connected"
                    if hardware_key == current_network_hardware:
                        text = f"{base_text} - Connected"
                        self.hardware_combo.addItem(text, hardware_key)
                    else:
                        # Interface is bound to another network, show as unavailable
                        text = f"{base_text} - Bound to {bound_network}"
                        item_index = self.hardware_combo.count()
                        self.hardware_combo.addItem(text, None)  # Set data to None to make it unavailable
                        
                        # Disable the item
                        model = self.hardware_combo.model()
                        item = model.item(item_index)
                        if item:
                            item.setEnabled(False)
                            item.setForeground(QColor("gray"))
                else:
                    # Interface is available
                    self.hardware_combo.addItem(base_text, hardware_key)
                
        # Restore selection if possible
        index = self.hardware_combo.findText(current_text)
        if index >= 0:
            self.hardware_combo.setCurrentIndex(index)
            
        # Update connect button state after hardware combo update
        self.update_connect_button_state()
            
    def update_network_details(self):
        """Update network details panel"""
        current_item = self.network_tree.currentItem()
        
        if not current_item:
            self.network_name_label.setText("No network selected")
            self.network_status_label.setText("N/A")
            self.network_hardware_label.setText("N/A")
            self.network_bitrate_label.setText("N/A")
            self.network_bus_number_label.setText("N/A")
            self.network_symbol_file_label.setText("N/A")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
            self.change_symbol_btn.setEnabled(False)
            self.remove_symbol_btn.setEnabled(False)
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        network = self.network_manager.get_network(network_id)
        
        if network:
            self.network_name_label.setText(network.config.name)
            
            if network.is_connected():
                self.network_status_label.setText("Connected")
                self.network_status_label.setStyleSheet("color: green")
            else:
                self.network_status_label.setText("Disconnected")
                self.network_status_label.setStyleSheet("color: red")
                
            # Update button states using dedicated method
            self.update_connect_button_state()
                
            if network.hardware:
                self.network_hardware_label.setText(
                    f"{network.hardware.name} ({network.hardware.interface_type}:{network.hardware.channel})"
                )
            else:
                self.network_hardware_label.setText("None")
                
            self.network_bitrate_label.setText(f"{network.config.bitrate} bps")
            self.network_bus_number_label.setText(str(network.config.bus_number))
            
            # Symbol file
            if network.config.symbol_file_path:
                import os
                symbol_file_name = os.path.basename(network.config.symbol_file_path)
                self.network_symbol_file_label.setText(symbol_file_name)
                self.network_symbol_file_label.setToolTip(network.config.symbol_file_path)
            else:
                self.network_symbol_file_label.setText("None")
                self.network_symbol_file_label.setToolTip("")
                
            # Enable/disable symbol file controls
            self.change_symbol_btn.setEnabled(True)
            self.remove_symbol_btn.setEnabled(bool(network.config.symbol_file_path))
            
    def update_statistics(self):
        """Update statistics display"""
        current_item = self.network_tree.currentItem()
        
        if not current_item:
            self.stats_table.setRowCount(0)
            return
            
        network_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        stats = self.network_manager.get_network_statistics(network_id)
        
        if not stats:
            self.stats_table.setRowCount(0)
            return
            
        # Prepare statistics data
        stats_data = [
            ("Messages", str(stats.get('message_count', 0))),
            ("TX Count", str(stats.get('tx_count', 0))),
            ("RX Count", str(stats.get('rx_count', 0))),
            ("Errors", str(stats.get('error_count', 0))),
            ("Uptime", f"{stats.get('uptime', 0):.1f}s"),
        ]
        
        if stats.get('connection_uptime'):
            stats_data.append(("Connection Time", f"{stats['connection_uptime']:.1f}s"))
            
        # Update table
        self.stats_table.setRowCount(len(stats_data))
        for row, (metric, value) in enumerate(stats_data):
            self.stats_table.setItem(row, 0, QTableWidgetItem(metric))
            self.stats_table.setItem(row, 1, QTableWidgetItem(value))
            
    def refresh_ui(self):
        """Refresh UI elements (less frequently to preserve selection)"""
        # Only do a full refresh if no item is currently selected
        # This prevents disrupting user interaction
        if not self.network_tree.currentItem():
            self.refresh_network_list()
        
    def get_network_manager(self) -> MultiNetworkManager:
        """Get the network manager instance"""
        return self.network_manager
        
    def shutdown(self):
        """Shutdown the network manager"""
        self.network_manager.shutdown()
