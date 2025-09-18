"""
Transmit Tab - CAN message transmission
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel,
                             QLineEdit, QCheckBox, QComboBox, QSplitter, QTextEdit,
                             QGroupBox, QSpinBox, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QColor
import json
import time

from canbus.interface_manager import CANInterfaceManager


class TransmitListWidget(QTableWidget):
    """Table widget for managing transmit messages"""
    
    def __init__(self):
        super().__init__()
        self.setup_table()
        
    def setup_table(self):
        """Set up the transmit list table"""
        columns = ["Enabled", "Name", "ID", "DLC", "Data", "Period (ms)", "Count", "Actions"]
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        
        # Set table properties
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Configure column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)      # Enabled
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)      # DLC
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)    # Data
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)      # Period
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)      # Count
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)      # Actions
        
        self.setColumnWidth(0, 60)   # Enabled
        self.setColumnWidth(3, 50)   # DLC
        self.setColumnWidth(5, 80)   # Period
        self.setColumnWidth(6, 60)   # Count
        self.setColumnWidth(7, 100)  # Actions
        
        # Set font
        font = QFont("Consolas", 9)
        self.setFont(font)
        
    def add_message(self, name: str, msg_id: int, data: bytes, period: int = 0, enabled: bool = False):
        """Add a new message to the transmit list"""
        row = self.rowCount()
        self.insertRow(row)
        
        # Enabled checkbox
        enabled_cb = QCheckBox()
        enabled_cb.setChecked(enabled)
        self.setCellWidget(row, 0, enabled_cb)
        
        # Name
        self.setItem(row, 1, QTableWidgetItem(name))
        
        # ID
        id_str = f"0x{msg_id:08X}" if msg_id > 0x7FF else f"0x{msg_id:03X}"
        self.setItem(row, 2, QTableWidgetItem(id_str))
        
        # DLC
        self.setItem(row, 3, QTableWidgetItem(str(len(data))))
        
        # Data
        data_str = " ".join(f"{byte:02X}" for byte in data)
        self.setItem(row, 4, QTableWidgetItem(data_str))
        
        # Period
        period_str = str(period) if period > 0 else "Manual"
        self.setItem(row, 5, QTableWidgetItem(period_str))
        
        # Count
        self.setItem(row, 6, QTableWidgetItem("0"))
        
        # Actions
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(2, 2, 2, 2)
        
        send_btn = QPushButton("Send")
        send_btn.setMaximumWidth(40)
        send_btn.clicked.connect(lambda: self.send_message(row))
        actions_layout.addWidget(send_btn)
        
        delete_btn = QPushButton("Del")
        delete_btn.setMaximumWidth(30)
        delete_btn.clicked.connect(lambda: self.delete_message(row))
        actions_layout.addWidget(delete_btn)
        
        self.setCellWidget(row, 7, actions_widget)
        
    def send_message(self, row: int):
        """Send message at specified row"""
        # This will be connected to the parent's send function
        pass
        
    def delete_message(self, row: int):
        """Delete message at specified row"""
        self.removeRow(row)
        
    def get_message_data(self, row: int) -> dict:
        """Get message data from specified row"""
        if row < 0 or row >= self.rowCount():
            return None
            
        enabled_cb = self.cellWidget(row, 0)
        name = self.item(row, 1).text()
        id_text = self.item(row, 2).text()
        data_text = self.item(row, 4).text()
        period_text = self.item(row, 5).text()
        
        # Parse ID
        msg_id = int(id_text, 16) if id_text.startswith('0x') else int(id_text)
        
        # Parse data
        data_bytes = bytes.fromhex(data_text.replace(' ', ''))
        
        # Parse period
        period = 0 if period_text == "Manual" else int(period_text)
        
        return {
            'enabled': enabled_cb.isChecked(),
            'name': name,
            'id': msg_id,
            'data': data_bytes,
            'period': period,
            'is_extended': msg_id > 0x7FF
        }


class TransmitTab(QWidget):
    """CAN message transmission tab"""
    
    def __init__(self, can_manager: CANInterfaceManager):
        super().__init__()
        self.can_manager = can_manager
        self.setup_ui()
        self.setup_connections()
        
        # Periodic transmission timer
        self.periodic_timer = QTimer()
        self.periodic_timer.timeout.connect(self.send_periodic_messages)
        
    def setup_ui(self):
        """Set up the transmit tab UI"""
        layout = QVBoxLayout(self)
        
        # Manual transmission group
        manual_group = QGroupBox("Manual Message Transmission")
        manual_layout = QVBoxLayout(manual_group)
        
        # Message input fields
        input_layout = QHBoxLayout()
        
        input_layout.addWidget(QLabel("ID:"))
        self.id_edit = QLineEdit("0x123")
        self.id_edit.setMaximumWidth(100)
        input_layout.addWidget(self.id_edit)
        
        input_layout.addWidget(QLabel("Data:"))
        self.data_edit = QLineEdit("00 01 02 03 04 05 06 07")
        input_layout.addWidget(self.data_edit)
        
        self.extended_cb = QCheckBox("Extended ID")
        input_layout.addWidget(self.extended_cb)
        
        self.remote_cb = QCheckBox("Remote Frame")
        input_layout.addWidget(self.remote_cb)
        
        manual_layout.addLayout(input_layout)
        
        # Manual send buttons
        button_layout = QHBoxLayout()
        
        self.send_once_btn = QPushButton("Send Once")
        self.send_once_btn.clicked.connect(self.send_manual_message)
        button_layout.addWidget(self.send_once_btn)
        
        button_layout.addWidget(QLabel("Repeat:"))
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(1, 1000)
        self.repeat_spin.setValue(10)
        button_layout.addWidget(self.repeat_spin)
        
        self.send_repeat_btn = QPushButton("Send Repeat")
        self.send_repeat_btn.clicked.connect(self.send_repeat_message)
        button_layout.addWidget(self.send_repeat_btn)
        
        button_layout.addStretch()
        
        manual_layout.addLayout(button_layout)
        layout.addWidget(manual_group)
        
        # Transmit list group
        list_group = QGroupBox("Transmit Lists")
        list_layout = QVBoxLayout(list_group)
        
        # List controls
        list_controls = QHBoxLayout()
        
        self.add_message_btn = QPushButton("Add Message")
        self.add_message_btn.clicked.connect(self.add_message_to_list)
        list_controls.addWidget(self.add_message_btn)
        
        self.load_list_btn = QPushButton("Load List")
        self.load_list_btn.clicked.connect(self.load_transmit_list)
        list_controls.addWidget(self.load_list_btn)
        
        self.save_list_btn = QPushButton("Save List")
        self.save_list_btn.clicked.connect(self.save_transmit_list)
        list_controls.addWidget(self.save_list_btn)
        
        list_controls.addStretch()
        
        self.start_periodic_btn = QPushButton("Start Periodic")
        self.start_periodic_btn.clicked.connect(self.start_periodic_transmission)
        list_controls.addWidget(self.start_periodic_btn)
        
        self.stop_periodic_btn = QPushButton("Stop Periodic")
        self.stop_periodic_btn.clicked.connect(self.stop_periodic_transmission)
        self.stop_periodic_btn.setEnabled(False)
        list_controls.addWidget(self.stop_periodic_btn)
        
        list_layout.addLayout(list_controls)
        
        # Transmit list table
        self.transmit_table = TransmitListWidget()
        list_layout.addWidget(self.transmit_table)
        
        layout.addWidget(list_group)
        
        # Statistics group
        stats_group = QGroupBox("Transmission Statistics")
        stats_layout = QHBoxLayout(stats_group)
        
        self.tx_count_label = QLabel("Transmitted: 0")
        self.error_count_label = QLabel("Errors: 0")
        self.periodic_status_label = QLabel("Periodic: Stopped")
        
        stats_layout.addWidget(self.tx_count_label)
        stats_layout.addWidget(self.error_count_label)
        stats_layout.addWidget(self.periodic_status_label)
        stats_layout.addStretch()
        
        layout.addWidget(stats_group)
        
        # Update timer for statistics
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start(1000)
        
    def setup_connections(self):
        """Set up signal connections"""
        self.can_manager.message_transmitted.connect(self.on_message_transmitted)
        self.can_manager.error_occurred.connect(self.on_error_occurred)
        self.can_manager.connection_changed.connect(self.on_connection_changed)
        
    def send_manual_message(self):
        """Send a single manual message"""
        if not self.can_manager.is_connected():
            QMessageBox.warning(self, "Warning", "Not connected to CAN interface")
            return
            
        try:
            # Parse message data
            msg_data = self.parse_message_input()
            if msg_data is None:
                return
                
            # Send message
            success = self.can_manager.send_message(
                msg_data['id'], 
                msg_data['data'], 
                msg_data['is_extended']
            )
            
            if not success:
                QMessageBox.critical(self, "Error", "Failed to send message")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error sending message: {str(e)}")
            
    def send_repeat_message(self):
        """Send a message multiple times"""
        if not self.can_manager.is_connected():
            QMessageBox.warning(self, "Warning", "Not connected to CAN interface")
            return
            
        try:
            msg_data = self.parse_message_input()
            if msg_data is None:
                return
                
            repeat_count = self.repeat_spin.value()
            
            for i in range(repeat_count):
                success = self.can_manager.send_message(
                    msg_data['id'], 
                    msg_data['data'], 
                    msg_data['is_extended']
                )
                if not success:
                    QMessageBox.critical(self, "Error", f"Failed to send message {i+1}")
                    break
                    
                # Small delay between messages
                time.sleep(0.01)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error sending repeated messages: {str(e)}")
            
    def parse_message_input(self) -> dict:
        """Parse message input fields"""
        try:
            # Parse ID
            id_text = self.id_edit.text().strip()
            if id_text.startswith('0x'):
                msg_id = int(id_text, 16)
            else:
                msg_id = int(id_text)
                
            # Parse data
            data_text = self.data_edit.text().strip()
            if data_text:
                data_bytes = bytes.fromhex(data_text.replace(' ', ''))
            else:
                data_bytes = b''
                
            # Check data length
            if len(data_bytes) > 8:
                QMessageBox.warning(self, "Warning", "CAN data length cannot exceed 8 bytes")
                return None
                
            return {
                'id': msg_id,
                'data': data_bytes,
                'is_extended': self.extended_cb.isChecked()
            }
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Invalid message format: {str(e)}")
            return None
            
    def add_message_to_list(self):
        """Add current message to transmit list"""
        msg_data = self.parse_message_input()
        if msg_data is None:
            return
            
        # Generate a name for the message
        name = f"Message_{msg_data['id']:03X}"
        
        self.transmit_table.add_message(
            name, 
            msg_data['id'], 
            msg_data['data'], 
            period=100,  # Default 100ms period
            enabled=False
        )
        
    def start_periodic_transmission(self):
        """Start periodic transmission of enabled messages"""
        if not self.can_manager.is_connected():
            QMessageBox.warning(self, "Warning", "Not connected to CAN interface")
            return
            
        # Clear existing periodic tasks
        self.can_manager.periodic_tasks.clear()
        
        # Add enabled messages to periodic tasks
        enabled_count = 0
        for row in range(self.transmit_table.rowCount()):
            msg_data = self.transmit_table.get_message_data(row)
            if msg_data and msg_data['enabled'] and msg_data['period'] > 0:
                self.can_manager.add_periodic_message(
                    msg_data['id'],
                    msg_data['data'],
                    msg_data['period'],
                    msg_data['is_extended']
                )
                enabled_count += 1
                
        if enabled_count == 0:
            QMessageBox.information(self, "Info", "No periodic messages enabled")
            return
            
        # Start periodic timer
        self.periodic_timer.start(10)  # Check every 10ms
        
        # Update UI
        self.start_periodic_btn.setEnabled(False)
        self.stop_periodic_btn.setEnabled(True)
        self.periodic_status_label.setText(f"Periodic: Running ({enabled_count} messages)")
        
    def stop_periodic_transmission(self):
        """Stop periodic transmission"""
        self.periodic_timer.stop()
        self.can_manager.periodic_tasks.clear()
        
        # Update UI
        self.start_periodic_btn.setEnabled(True)
        self.stop_periodic_btn.setEnabled(False)
        self.periodic_status_label.setText("Periodic: Stopped")
        
    def send_periodic_messages(self):
        """Send periodic messages that are due"""
        # This is handled by the CAN manager's periodic timer
        pass
        
    def load_transmit_list(self):
        """Load transmit list from file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Transmit List", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                    
                # Clear current list
                self.transmit_table.setRowCount(0)
                
                # Load messages
                for msg in data.get('messages', []):
                    self.transmit_table.add_message(
                        msg['name'],
                        msg['id'],
                        bytes(msg['data']),
                        msg.get('period', 0),
                        msg.get('enabled', False)
                    )
                    
                QMessageBox.information(self, "Success", f"Loaded {len(data.get('messages', []))} messages")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")
                
    def save_transmit_list(self):
        """Save transmit list to file"""
        if self.transmit_table.rowCount() == 0:
            QMessageBox.information(self, "Info", "No messages to save")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Transmit List", 
            "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                messages = []
                for row in range(self.transmit_table.rowCount()):
                    msg_data = self.transmit_table.get_message_data(row)
                    if msg_data:
                        messages.append({
                            'name': msg_data['name'],
                            'id': msg_data['id'],
                            'data': list(msg_data['data']),
                            'period': msg_data['period'],
                            'enabled': msg_data['enabled']
                        })
                        
                data = {
                    'version': '1.0',
                    'description': 'QCAN Explorer Transmit List',
                    'messages': messages
                }
                
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
                    
                QMessageBox.information(self, "Success", f"Saved {len(messages)} messages")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
                
    @pyqtSlot(object)
    def on_message_transmitted(self, msg):
        """Handle transmitted message"""
        # Update count in table if it's a periodic message
        for row in range(self.transmit_table.rowCount()):
            msg_data = self.transmit_table.get_message_data(row)
            if msg_data and msg_data['id'] == msg.arbitration_id:
                count_item = self.transmit_table.item(row, 6)
                if count_item:
                    current_count = int(count_item.text())
                    count_item.setText(str(current_count + 1))
                break
                
    @pyqtSlot(str)
    def on_error_occurred(self, error_msg):
        """Handle transmission errors"""
        # Could display error in status or log
        pass
        
    @pyqtSlot(bool)
    def on_connection_changed(self, connected):
        """Handle connection state changes"""
        self.send_once_btn.setEnabled(connected)
        self.send_repeat_btn.setEnabled(connected)
        
        if not connected and self.periodic_timer.isActive():
            self.stop_periodic_transmission()
            
    def update_statistics(self):
        """Update transmission statistics"""
        stats = self.can_manager.get_statistics()
        tx_count = stats.get('tx_count', 0)
        error_count = stats.get('error_count', 0)
        
        self.tx_count_label.setText(f"Transmitted: {tx_count}")
        self.error_count_label.setText(f"Errors: {error_count}")
