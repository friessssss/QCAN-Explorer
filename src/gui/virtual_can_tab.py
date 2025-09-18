"""
Virtual CAN Tab - Controls for virtual CAN network
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel,
                             QLineEdit, QCheckBox, QComboBox, QSplitter, QTextEdit,
                             QGroupBox, QSpinBox, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QColor

from canbus.interface_manager import CANInterfaceManager


class VirtualMessageTable(QTableWidget):
    """Table widget for managing virtual CAN messages"""
    
    def __init__(self):
        super().__init__()
        self.setup_table()
        
    def setup_table(self):
        """Set up the virtual message table"""
        columns = ["Enabled", "ID", "Name", "Period (ms)", "Data Preview", "Count"]
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        
        # Set table properties
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Configure column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)      # Enabled
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Name
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)      # Period
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)    # Data Preview
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)      # Count
        
        self.setColumnWidth(0, 60)   # Enabled
        self.setColumnWidth(3, 80)   # Period
        self.setColumnWidth(5, 60)   # Count
        
        # Set font
        font = QFont("Consolas", 9)
        self.setFont(font)
        
    def update_virtual_messages(self, message_list):
        """Update table with virtual message list"""
        self.setRowCount(len(message_list))
        
        for row, msg_info in enumerate(message_list):
            # Enabled checkbox
            enabled_cb = QCheckBox()
            enabled_cb.setChecked(msg_info['enabled'])
            enabled_cb.stateChanged.connect(lambda state, r=row: self.on_enabled_changed(r, state))
            self.setCellWidget(row, 0, enabled_cb)
            
            # ID
            self.setItem(row, 1, QTableWidgetItem(f"0x{msg_info['id']:03X}"))
            
            # Name
            self.setItem(row, 2, QTableWidgetItem(msg_info['name']))
            
            # Period
            self.setItem(row, 3, QTableWidgetItem(f"{msg_info['period_ms']}"))
            
            # Data preview (will be updated by timer)
            self.setItem(row, 4, QTableWidgetItem("--"))
            
            # Count (will be updated by timer)
            self.setItem(row, 5, QTableWidgetItem("0"))
            
    def on_enabled_changed(self, row, state):
        """Handle enabled checkbox change"""
        # This will be connected to the parent widget
        pass


class VirtualCANTab(QWidget):
    """Virtual CAN network control tab"""
    
    def __init__(self, can_manager: CANInterfaceManager):
        super().__init__()
        self.can_manager = can_manager
        self.setup_ui()
        self.setup_connections()
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second
        
    def setup_ui(self):
        """Set up the virtual CAN tab UI"""
        layout = QVBoxLayout(self)
        
        # Status group
        status_group = QGroupBox("Virtual CAN Status")
        status_layout = QHBoxLayout(status_group)
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(QLabel("Status:"))
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.message_rate_label = QLabel("Rate: 0 msg/s")
        status_layout.addWidget(self.message_rate_label)
        
        layout.addWidget(status_group)
        
        # Virtual message controls
        control_group = QGroupBox("Virtual Message Control")
        control_layout = QVBoxLayout(control_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_all_btn = QPushButton("Start All Messages")
        self.start_all_btn.clicked.connect(self.start_all_messages)
        button_layout.addWidget(self.start_all_btn)
        
        self.stop_all_btn = QPushButton("Stop All Messages")
        self.stop_all_btn.clicked.connect(self.stop_all_messages)
        button_layout.addWidget(self.stop_all_btn)
        
        button_layout.addStretch()
        
        # Rate control buttons
        self.speed_up_btn = QPushButton("Speed Up (÷2)")
        self.speed_up_btn.clicked.connect(self.speed_up_messages)
        button_layout.addWidget(self.speed_up_btn)
        
        self.slow_down_btn = QPushButton("Slow Down (×2)")
        self.slow_down_btn.clicked.connect(self.slow_down_messages)
        button_layout.addWidget(self.slow_down_btn)
        
        self.inject_error_btn = QPushButton("Inject Error Frame")
        self.inject_error_btn.clicked.connect(self.inject_error_frame)
        button_layout.addWidget(self.inject_error_btn)
        
        control_layout.addLayout(button_layout)
        
        # Virtual message table
        self.message_table = VirtualMessageTable()
        self.message_table.on_enabled_changed = self.on_message_enabled_changed
        control_layout.addWidget(self.message_table)
        
        layout.addWidget(control_group)
        
        # Manual injection group
        injection_group = QGroupBox("Manual Message Injection")
        injection_layout = QVBoxLayout(injection_group)
        
        # Injection controls
        inject_controls = QHBoxLayout()
        
        inject_controls.addWidget(QLabel("ID:"))
        self.inject_id_edit = QLineEdit("0x123")
        self.inject_id_edit.setMaximumWidth(80)
        inject_controls.addWidget(self.inject_id_edit)
        
        inject_controls.addWidget(QLabel("Data:"))
        self.inject_data_edit = QLineEdit("01 02 03 04")
        inject_controls.addWidget(self.inject_data_edit)
        
        self.inject_btn = QPushButton("Inject")
        self.inject_btn.clicked.connect(self.inject_manual_message)
        inject_controls.addWidget(self.inject_btn)
        
        injection_layout.addLayout(inject_controls)
        
        layout.addWidget(injection_group)
        
        # Statistics group
        stats_group = QGroupBox("Network Statistics")
        stats_layout = QHBoxLayout(stats_group)
        
        self.total_messages_label = QLabel("Total: 0")
        self.active_messages_label = QLabel("Active: 0")
        self.errors_label = QLabel("Errors: 0")
        
        stats_layout.addWidget(self.total_messages_label)
        stats_layout.addWidget(self.active_messages_label)
        stats_layout.addWidget(self.errors_label)
        stats_layout.addStretch()
        
        layout.addWidget(stats_group)
        
    def setup_connections(self):
        """Set up signal connections"""
        self.can_manager.connection_changed.connect(self.on_connection_changed)
        
    @pyqtSlot(bool)
    def on_connection_changed(self, connected):
        """Handle CAN interface connection changes"""
        if connected and self.can_manager.is_virtual:
            self.status_label.setText("Virtual Network Active")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.update_virtual_message_table()
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
    def update_virtual_message_table(self):
        """Update the virtual message table"""
        virtual_network = self.can_manager.get_virtual_network()
        if virtual_network:
            message_list = virtual_network.get_message_list()
            self.message_table.update_virtual_messages(message_list)
            
    def on_message_enabled_changed(self, row, state):
        """Handle message enabled state change"""
        virtual_network = self.can_manager.get_virtual_network()
        if virtual_network:
            message_list = virtual_network.get_message_list()
            if 0 <= row < len(message_list):
                msg_id = message_list[row]['id']
                enabled = state == Qt.CheckState.Checked.value
                virtual_network.set_message_enabled(msg_id, enabled)
                
    def start_all_messages(self):
        """Enable all virtual messages"""
        virtual_network = self.can_manager.get_virtual_network()
        if virtual_network:
            message_list = virtual_network.get_message_list()
            for msg_info in message_list:
                virtual_network.set_message_enabled(msg_info['id'], True)
            self.update_virtual_message_table()
            
    def stop_all_messages(self):
        """Disable all virtual messages"""
        virtual_network = self.can_manager.get_virtual_network()
        if virtual_network:
            message_list = virtual_network.get_message_list()
            for msg_info in message_list:
                virtual_network.set_message_enabled(msg_info['id'], False)
            self.update_virtual_message_table()
            
    def inject_error_frame(self):
        """Inject an error frame"""
        if not self.can_manager.is_virtual:
            QMessageBox.warning(self, "Warning", "Virtual CAN network not active")
            return
            
        self.can_manager.simulate_error_frame()
        QMessageBox.information(self, "Info", "Error frame injected")
        
    def inject_manual_message(self):
        """Inject a manual message"""
        if not self.can_manager.is_virtual:
            QMessageBox.warning(self, "Warning", "Virtual CAN network not active")
            return
            
        try:
            # Parse ID
            id_text = self.inject_id_edit.text().strip()
            if id_text.startswith('0x'):
                msg_id = int(id_text, 16)
            else:
                msg_id = int(id_text)
                
            # Parse data
            data_text = self.inject_data_edit.text().strip()
            if data_text:
                data_bytes = bytes.fromhex(data_text.replace(' ', ''))
            else:
                data_bytes = b''
                
            # Inject message
            self.can_manager.inject_virtual_message(msg_id, data_bytes)
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Invalid message format: {str(e)}")
            
    def speed_up_messages(self):
        """Speed up all virtual messages by factor of 2"""
        virtual_network = self.can_manager.get_virtual_network()
        if virtual_network:
            virtual_network.set_all_message_periods(0.5)  # Divide periods by 2
            self.update_virtual_message_table()
            QMessageBox.information(self, "Info", "Message rates doubled (periods halved)")
            
    def slow_down_messages(self):
        """Slow down all virtual messages by factor of 2"""
        virtual_network = self.can_manager.get_virtual_network()
        if virtual_network:
            virtual_network.set_all_message_periods(2.0)  # Multiply periods by 2
            self.update_virtual_message_table()
            QMessageBox.information(self, "Info", "Message rates halved (periods doubled)")
            
    def update_display(self):
        """Update display information"""
        if not self.can_manager.is_virtual:
            return
            
        # Update statistics
        stats = self.can_manager.get_statistics()
        self.total_messages_label.setText(f"Total: {stats.get('message_count', 0)}")
        
        # Calculate message rate
        uptime = stats.get('uptime', 1)
        if uptime > 0:
            rate = stats.get('message_count', 0) / uptime
            self.message_rate_label.setText(f"Rate: {rate:.1f} msg/s")
            
        # Count active messages
        virtual_network = self.can_manager.get_virtual_network()
        if virtual_network:
            message_list = virtual_network.get_message_list()
            active_count = sum(1 for msg in message_list if msg['enabled'])
            self.active_messages_label.setText(f"Active: {active_count}")
            
        self.errors_label.setText(f"Errors: {stats.get('error_count', 0)}")
