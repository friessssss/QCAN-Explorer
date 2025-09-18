"""
Monitor Tab - Real-time CAN message monitoring
"""

import time
from typing import Dict, List
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel,
                             QLineEdit, QCheckBox, QComboBox, QSplitter, QTextEdit,
                             QGroupBox, QSpinBox, QTreeWidget, QTreeWidgetItem,
                             QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QColor

from canbus.messages import CANMessage
from utils.sym_parser import SymParser


class MessageTreeWidget(QTreeWidget):
    """Expandable tree widget for CAN messages with signal details"""
    
    def __init__(self):
        super().__init__()
        self.setup_tree()
        self.message_data = []  # Store message data
        self.message_stats = {}  # Track message statistics
        self.message_items = {}  # Track tree items by message key (bus+ID)
        
    def setup_tree(self):
        """Set up the message tree"""
        # Define columns
        columns = ["Time", "Bus", "ID", "DLC", "Data", "Direction", "Count", "Period", "Message/Signal"]
        self.setColumnCount(len(columns))
        self.setHeaderLabels(columns)
        
        # Set tree properties
        self.setSortingEnabled(True)  # Enable sorting by column headers
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setRootIsDecorated(True)
        
        # Configure column widths - make all columns resizable by user
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Time - resizable
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # Bus - resizable
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # ID - resizable
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # DLC - resizable
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # Data - resizable
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)  # Direction - resizable
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)  # Count - resizable
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)  # Period - resizable
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Interactive)  # Message/Signal - resizable
        
        # Set initial column widths (user can resize these)
        self.setColumnWidth(0, 120)  # Time
        self.setColumnWidth(1, 50)   # Bus
        self.setColumnWidth(2, 80)   # ID
        self.setColumnWidth(3, 50)   # DLC
        self.setColumnWidth(4, 120)  # Data
        self.setColumnWidth(5, 80)   # Direction
        self.setColumnWidth(6, 60)   # Count
        self.setColumnWidth(7, 80)   # Period
        self.setColumnWidth(8, 200)  # Message/Signal
        
        # Enable header click sorting
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        
        # Set font
        font = QFont("Consolas", 9)
        self.setFont(font)
        
    def set_network_manager(self, network_manager):
        """Set the network manager for accessing symbol parsers"""
        self.network_manager = network_manager
        
    def get_sym_parser_for_bus(self, bus_number: int):
        """Get symbol parser for a specific bus number"""
        if hasattr(self, 'network_manager') and self.network_manager:
            network = self.network_manager.get_network_by_bus_number(bus_number)
            if network:
                return network.get_symbol_parser()
        return None
        
    def get_message_name(self, msg_id: int, bus_number: int = 0) -> str:
        """Get message name from network-assigned SYM parser"""
        sym_parser = self.get_sym_parser_for_bus(bus_number)
        if not sym_parser or not sym_parser.messages:
            return f"Unknown_0x{msg_id:X}"
        
        for msg_name, msg_def in sym_parser.messages.items():
            if msg_def.can_id == msg_id:
                return msg_name
        
        return f"Unknown_0x{msg_id:X}"
        
    def decode_message_signals(self, msg: CANMessage) -> List[tuple]:
        """Decode message into individual signal name-value pairs"""
        sym_parser = self.get_sym_parser_for_bus(msg.bus_number)
        if not sym_parser or not sym_parser.messages:
            return []
        
        # Find matching message definition
        for msg_name, msg_def in sym_parser.messages.items():
            if msg_def.can_id == msg.arbitration_id:
                signals = []
                
                # Decode each variable
                for var in msg_def.variables:
                    if var.start_bit + var.bit_length <= len(msg.data) * 8:
                        # Extract bits (simplified - assumes byte-aligned)
                        start_byte = var.start_bit // 8
                        end_byte = (var.start_bit + var.bit_length - 1) // 8 + 1
                        
                        if end_byte <= len(msg.data):
                            # Extract raw value
                            raw_bytes = msg.data[start_byte:end_byte]
                            raw_value = int.from_bytes(raw_bytes, byteorder='little')
                            
                            # Apply bit masking for partial bytes
                            if var.start_bit % 8 != 0 or var.bit_length % 8 != 0:
                                # Simplified bit extraction
                                bit_offset = var.start_bit % 8
                                mask = (1 << var.bit_length) - 1
                                raw_value = (raw_value >> bit_offset) & mask
                            
                            # Apply scaling
                            scaled_value = raw_value * var.factor + var.offset
                            
                            # Format output
                            unit_str = f" {var.unit}" if var.unit else ""
                            
                            # Handle enum values
                            if var.enum_name and sym_parser.enums and var.enum_name in sym_parser.enums:
                                enum = sym_parser.enums[var.enum_name]
                                if int(scaled_value) in enum.values:
                                    value_str = enum.values[int(scaled_value)]
                                else:
                                    value_str = f"{scaled_value:.2f}{unit_str}"
                            else:
                                value_str = f"{scaled_value:.2f}{unit_str}"
                            
                            signals.append((var.name, value_str))
                
                return signals
        
        return []
        
    def add_message(self, msg: CANMessage):
        """Add a new CAN message to the tree"""
        # Use combination of bus number and message ID as unique key
        msg_key = f"bus{msg.bus_number}_id{msg.arbitration_id}"
        current_time = time.time()
        
        # Update statistics
        if msg_key not in self.message_stats:
            self.message_stats[msg_key] = {
                'count': 0,
                'last_time': 0,
                'period': 0,
                'item': None
            }
            
        stats = self.message_stats[msg_key]
        stats['count'] += 1
        
        # Calculate period
        if stats['last_time'] > 0:
            period = current_time - stats['last_time']
            stats['period'] = period * 1000  # Convert to milliseconds
        stats['last_time'] = current_time
        
        # Check if message ID already exists in tree
        if stats['item'] is not None:
            # Update existing item
            self.update_tree_item(stats['item'], msg, stats)
        else:
            # Add new top-level item
            item = QTreeWidgetItem(self)
            stats['item'] = item
            self.update_tree_item(item, msg, stats)
                
    def update_tree_item(self, item: QTreeWidgetItem, msg: CANMessage, stats: Dict):
        """Update a tree item with message data"""
        # Time
        time_str = time.strftime("%H:%M:%S.%f", time.localtime(msg.timestamp))[:-3]
        item.setText(0, time_str)
        
        # Bus number with color coding
        item.setText(1, str(msg.bus_number))
        if msg.bus_number > 0:
            # Color code buses for easy identification - vibrant but readable colors
            colors = [QColor(255, 200, 200), QColor(200, 255, 200), QColor(200, 200, 255), 
                     QColor(255, 255, 150), QColor(255, 150, 255), QColor(150, 255, 255)]
            color = colors[(msg.bus_number - 1) % len(colors)]
            item.setBackground(1, color)
        
        # ID (format as hex)
        id_format = f"0x{msg.arbitration_id:08X}" if msg.is_extended_id else f"0x{msg.arbitration_id:03X}"
        item.setText(2, id_format)
        if msg.is_extended_id:
            item.setBackground(2, QColor(255, 255, 200))  # Light yellow for extended IDs
        
        # DLC (Data Length Code)
        item.setText(3, str(len(msg.data)))
        
        # Data (format as hex bytes)
        data_str = " ".join(f"{byte:02X}" for byte in msg.data)
        item.setText(4, data_str)
        
        # Direction
        item.setText(5, msg.direction.upper())
        if msg.direction == 'tx':
            item.setBackground(5, QColor(200, 255, 200))  # Light green for TX
        else:
            item.setBackground(5, QColor(200, 200, 255))  # Light blue for RX
        
        # Count
        item.setText(6, str(stats['count']))
        
        # Period
        period_str = f"{stats['period']:.1f} ms" if stats['period'] > 0 else "-"
        item.setText(7, period_str)
        
        # Message name in the Message/Signal column
        message_name = self.get_message_name(msg.arbitration_id, msg.bus_number)
        item.setText(8, message_name)
        
        # Update signal children only if the item doesn't have children yet
        # This prevents disrupting the tree structure when just updating values
        if item.childCount() == 0:
            signals = self.decode_message_signals(msg)
            for signal_name, signal_value in signals:
                signal_item = QTreeWidgetItem(item)
                signal_item.setText(8, f"{signal_name} = {signal_value}")  # Column 8: Message/Signal
                
                # Set different styling for signal rows
                signal_item.setForeground(8, QColor(100, 100, 100))  # Gray text
        else:
            # Update existing signal children with new values
            signals = self.decode_message_signals(msg)
            for i, (signal_name, signal_value) in enumerate(signals):
                if i < item.childCount():
                    child = item.child(i)
                    child.setText(8, f"{signal_name} = {signal_value}")  # Column 8: Message/Signal
            
    def clear_messages(self):
        """Clear all messages from the tree"""
        self.clear()
        self.message_data.clear()
        self.message_stats.clear()
        self.message_items.clear()


class MessageTableWidget(QTableWidget):
    """Custom table widget for CAN messages"""
    
    def __init__(self):
        super().__init__()
        self.setup_table()
        self.message_data = []  # Store message data
        self.message_stats = {}  # Track message statistics
        
    def setup_table(self):
        """Set up the message table"""
        # Define columns - added Bus and Decoded Signals columns
        columns = ["Time", "Bus", "ID", "DLC", "Data", "Direction", "Count", "Period", "Decoded Signals"]
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        
        # Set table properties
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Configure column widths - make all columns resizable by user
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Time - resizable
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # Bus - resizable
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # ID - resizable
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # DLC - resizable
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # Data - resizable
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)  # Direction - resizable
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)  # Count - resizable
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)  # Period - resizable
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Interactive)  # Decoded Signals - resizable
        
        # Set initial column widths (user can resize these)
        self.setColumnWidth(0, 120)  # Time
        self.setColumnWidth(1, 50)   # Bus
        self.setColumnWidth(2, 80)   # ID
        self.setColumnWidth(3, 50)   # DLC
        self.setColumnWidth(4, 120)  # Data
        self.setColumnWidth(5, 80)   # Direction
        self.setColumnWidth(6, 60)   # Count
        self.setColumnWidth(7, 80)   # Period
        self.setColumnWidth(8, 200)  # Decoded Signals
        
        # Enable header click sorting
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        
        # Set font
        font = QFont("Consolas", 9)
        self.setFont(font)
        
    def set_network_manager(self, network_manager):
        """Set the network manager for accessing symbol parsers"""
        self.network_manager = network_manager
        
    def get_sym_parser_for_bus(self, bus_number: int):
        """Get symbol parser for a specific bus number"""
        if hasattr(self, 'network_manager') and self.network_manager:
            network = self.network_manager.get_network_by_bus_number(bus_number)
            if network:
                return network.get_symbol_parser()
        return None
        
    def decode_message(self, msg: CANMessage) -> str:
        """Decode a CAN message using network-assigned SYM file definitions"""
        sym_parser = self.get_sym_parser_for_bus(msg.bus_number)
        if not sym_parser or not sym_parser.messages:
            return "No symbol file assigned to this bus"
        
        # Find matching message definition
        for msg_name, msg_def in sym_parser.messages.items():
            if msg_def.can_id == msg.arbitration_id:
                decoded_lines = []
                
                # Decode each variable
                for var in msg_def.variables:
                    if var.start_bit + var.bit_length <= len(msg.data) * 8:
                        # Extract bits (simplified - assumes byte-aligned)
                        start_byte = var.start_bit // 8
                        end_byte = (var.start_bit + var.bit_length - 1) // 8 + 1
                        
                        if end_byte <= len(msg.data):
                            # Extract raw value
                            raw_bytes = msg.data[start_byte:end_byte]
                            raw_value = int.from_bytes(raw_bytes, byteorder='little')
                            
                            # Apply bit masking for partial bytes
                            if var.start_bit % 8 != 0 or var.bit_length % 8 != 0:
                                # Simplified bit extraction
                                bit_offset = var.start_bit % 8
                                mask = (1 << var.bit_length) - 1
                                raw_value = (raw_value >> bit_offset) & mask
                            
                            # Apply scaling
                            scaled_value = raw_value * var.factor + var.offset
                            
                            # Format output
                            unit_str = f" {var.unit}" if var.unit else ""
                            
                            # Handle enum values
                            if var.enum_name and sym_parser.enums and var.enum_name in sym_parser.enums:
                                enum = sym_parser.enums[var.enum_name]
                                if int(scaled_value) in enum.values:
                                    value_str = enum.values[int(scaled_value)]
                                else:
                                    value_str = f"{scaled_value:.2f}{unit_str}"
                            else:
                                value_str = f"{scaled_value:.2f}{unit_str}"
                            
                            decoded_lines.append(f"{var.name} = {value_str}")
                
                return "\n".join(decoded_lines) if decoded_lines else "No variables decoded"
        
        return f"Unknown message ID: 0x{msg.arbitration_id:X}"
        
    def add_message(self, msg: CANMessage):
        """Add a new CAN message to the table"""
        # Use combination of bus number and message ID as unique key
        msg_key = f"bus{msg.bus_number}_id{msg.arbitration_id}"
        current_time = time.time()
        
        # Update statistics
        if msg_key not in self.message_stats:
            self.message_stats[msg_key] = {
                'count': 0,
                'last_time': 0,
                'period': 0,
                'row': -1
            }
            
        stats = self.message_stats[msg_key]
        stats['count'] += 1
        
        # Calculate period
        if stats['last_time'] > 0:
            period = current_time - stats['last_time']
            stats['period'] = period * 1000  # Convert to milliseconds
        stats['last_time'] = current_time
        
        # Check if message key already exists in table
        if stats['row'] >= 0 and stats['row'] < self.rowCount():
            # Update existing row
            row = stats['row']
            self.update_row(row, msg, stats)
        else:
            # Add new row
            row = self.rowCount()
            self.insertRow(row)
            stats['row'] = row
            self.update_row(row, msg, stats)
            
    def update_row(self, row: int, msg: CANMessage, stats: Dict):
        """Update a table row with message data"""
        # Time
        time_str = time.strftime("%H:%M:%S.%f", time.localtime(msg.timestamp))[:-3]
        self.setItem(row, 0, QTableWidgetItem(time_str))
        
        # Bus number
        bus_item = QTableWidgetItem(str(msg.bus_number))
        if msg.bus_number > 0:
            # Color code buses for easy identification - vibrant but readable colors
            colors = [QColor(255, 200, 200), QColor(200, 255, 200), QColor(200, 200, 255), 
                     QColor(255, 255, 150), QColor(255, 150, 255), QColor(150, 255, 255)]
            color = colors[(msg.bus_number - 1) % len(colors)]
            bus_item.setBackground(color)
        self.setItem(row, 1, bus_item)
        
        # ID (format as hex)
        id_format = f"0x{msg.arbitration_id:08X}" if msg.is_extended_id else f"0x{msg.arbitration_id:03X}"
        id_item = QTableWidgetItem(id_format)
        if msg.is_extended_id:
            id_item.setBackground(QColor(255, 255, 200))  # Light yellow for extended IDs
        self.setItem(row, 2, id_item)
        
        # DLC (Data Length Code)
        self.setItem(row, 3, QTableWidgetItem(str(len(msg.data))))
        
        # Data (format as hex bytes)
        data_str = " ".join(f"{byte:02X}" for byte in msg.data)
        self.setItem(row, 4, QTableWidgetItem(data_str))
        
        # Direction
        direction_item = QTableWidgetItem(msg.direction.upper())
        if msg.direction == 'tx':
            direction_item.setBackground(QColor(200, 255, 200))  # Light green for TX
        else:
            direction_item.setBackground(QColor(200, 200, 255))  # Light blue for RX
        self.setItem(row, 5, direction_item)
        
        # Count
        self.setItem(row, 6, QTableWidgetItem(str(stats['count'])))
        
        # Period
        period_str = f"{stats['period']:.1f} ms" if stats['period'] > 0 else "-"
        self.setItem(row, 7, QTableWidgetItem(period_str))
        
        # Decoded Signals
        decoded_text = self.decode_message(msg)
        decoded_item = QTableWidgetItem(decoded_text)
        decoded_item.setToolTip(decoded_text)  # Show full text in tooltip
        self.setItem(row, 8, decoded_item)
        
    def clear_messages(self):
        """Clear all messages from the table"""
        self.setRowCount(0)
        self.message_data.clear()
        self.message_stats.clear()


class MonitorTab(QWidget):
    """CAN message monitoring tab"""
    
    def __init__(self, network_manager):
        super().__init__()
        self.network_manager = network_manager
        self.setup_ui()
        self.setup_connections()
        
        # Auto-scroll and update settings
        self.auto_scroll = True
        self.max_messages = 1000
        self.monitoring_active = False
        
    def setup_ui(self):
        """Set up the monitor tab UI"""
        layout = QVBoxLayout(self)
        
        # Control panel
        control_group = QGroupBox("Monitor Controls")
        control_layout = QHBoxLayout(control_group)
        
        # Start/Stop monitoring
        self.start_btn = QPushButton("Start Monitoring")
        self.start_btn.clicked.connect(self.start_monitoring)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Monitoring")
        self.stop_btn.clicked.connect(self.stop_monitoring)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        # Clear messages
        self.clear_btn = QPushButton("Clear Messages")
        self.clear_btn.clicked.connect(self.clear_messages)
        control_layout.addWidget(self.clear_btn)
        
        control_layout.addStretch()
        
        # Auto-scroll checkbox
        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(self.toggle_auto_scroll)
        control_layout.addWidget(self.auto_scroll_cb)
        
        # Smart scroll checkbox
        self.smart_scroll_cb = QCheckBox("Smart scroll")
        self.smart_scroll_cb.setChecked(True)
        self.smart_scroll_cb.setToolTip("Preserve position when manually navigating")
        control_layout.addWidget(self.smart_scroll_cb)
        
        # Max messages setting
        control_layout.addWidget(QLabel("Max Messages:"))
        self.max_messages_spin = QSpinBox()
        self.max_messages_spin.setRange(100, 10000)
        self.max_messages_spin.setValue(1000)
        self.max_messages_spin.valueChanged.connect(self.set_max_messages)
        control_layout.addWidget(self.max_messages_spin)
        
        layout.addWidget(control_group)
        
        # Network symbol status
        symbol_group = QGroupBox("Symbol Decoding Status")
        symbol_layout = QHBoxLayout(symbol_group)
        
        self.sym_status_label = QLabel("Using network-assigned symbol files")
        self.sym_status_label.setStyleSheet("color: #666666; font-style: italic;")
        symbol_layout.addWidget(self.sym_status_label)
        
        symbol_layout.addStretch()
        
        layout.addWidget(symbol_group)
        
        # Filter panel
        filter_group = QGroupBox("Message Filters")
        filter_layout = QHBoxLayout(filter_group)
        
        # ID filter
        filter_layout.addWidget(QLabel("ID Filter:"))
        self.id_filter_edit = QLineEdit()
        self.id_filter_edit.setPlaceholderText("e.g., 0x123, 123-456, *")
        self.id_filter_edit.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.id_filter_edit)
        
        # Direction filter
        filter_layout.addWidget(QLabel("Direction:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["All", "RX Only", "TX Only"])
        self.direction_combo.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.direction_combo)
        
        # Data filter
        filter_layout.addWidget(QLabel("Data Filter:"))
        self.data_filter_edit = QLineEdit()
        self.data_filter_edit.setPlaceholderText("e.g., AA BB *, 00 ?? FF")
        self.data_filter_edit.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.data_filter_edit)
        
        layout.addWidget(filter_group)
        
        # Create splitter for table and details
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Message tree (expandable table)
        self.message_table = MessageTreeWidget()
        self.message_table.set_network_manager(self.network_manager)
        self.message_table.itemSelectionChanged.connect(self.on_message_selected)
        splitter.addWidget(self.message_table)
        
        # Message details panel
        details_group = QGroupBox("Message Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(150)
        self.details_text.setFont(QFont("Consolas", 9))
        details_layout.addWidget(self.details_text)
        
        splitter.addWidget(details_group)
        splitter.setSizes([600, 150])
        
        layout.addWidget(splitter)
        
        # Status panel
        status_layout = QHBoxLayout()
        self.message_count_label = QLabel("Messages: 0")
        self.rx_count_label = QLabel("RX: 0")
        self.tx_count_label = QLabel("TX: 0")
        self.unique_ids_label = QLabel("Unique IDs: 0")
        
        status_layout.addWidget(self.message_count_label)
        status_layout.addWidget(self.rx_count_label)
        status_layout.addWidget(self.tx_count_label)
        status_layout.addWidget(self.unique_ids_label)
        status_layout.addStretch()
        
        layout.addLayout(status_layout)
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
        
    def setup_connections(self):
        """Set up signal connections"""
        # Use QueuedConnection for thread-safe signal handling
        from PyQt6.QtCore import Qt
        self.network_manager.message_received.connect(self.on_message_received, Qt.ConnectionType.QueuedConnection)
        self.network_manager.message_transmitted.connect(self.on_message_transmitted, Qt.ConnectionType.QueuedConnection)
        self.network_manager.network_state_changed.connect(self.on_network_state_changed, Qt.ConnectionType.QueuedConnection)
        
        # Update symbol status when networks change
        self.network_manager.network_state_changed.connect(self.update_symbol_status, Qt.ConnectionType.QueuedConnection)
        
        # Initial symbol status update
        self.update_symbol_status()
        
    @pyqtSlot(str, object)
    def on_message_received(self, network_id: str, msg: CANMessage):
        """Handle received CAN message from multi-network manager"""
        if self.monitoring_active and self.passes_filters(msg):
            # Store current selection and scroll position
            current_item = self.message_table.currentItem()
            
            self.message_table.add_message(msg)
            
            # Handle auto-scroll and selection preservation
            if self.auto_scroll:
                if self.smart_scroll_cb.isChecked():
                    # Smart scroll: only auto-scroll if no manual selection or user is at bottom
                    should_auto_scroll = (current_item is None or 
                                        (self.message_table.topLevelItemCount() > 0 and
                                         current_item == self.message_table.topLevelItem(self.message_table.topLevelItemCount() - 2)))
                    
                    if should_auto_scroll and self.message_table.topLevelItemCount() > 0:
                        last_item = self.message_table.topLevelItem(self.message_table.topLevelItemCount() - 1)
                        self.message_table.scrollToItem(last_item)
                    else:
                        # Restore selection if smart scroll is preventing auto-scroll
                        if current_item is not None and current_item.parent() is None:
                            try:
                                self.message_table.setCurrentItem(current_item)
                            except:
                                pass
                else:
                    # Traditional auto-scroll: always scroll to bottom
                    if self.message_table.topLevelItemCount() > 0:
                        last_item = self.message_table.topLevelItem(self.message_table.topLevelItemCount() - 1)
                        self.message_table.scrollToItem(last_item)
            else:
                # No auto-scroll: always preserve selection
                if current_item is not None and current_item.parent() is None:
                    try:
                        self.message_table.setCurrentItem(current_item)
                    except:
                        pass
                
            # Limit number of messages
            if self.message_table.topLevelItemCount() > self.max_messages:
                # Remove oldest message (first item)
                item = self.message_table.takeTopLevelItem(0)
                if item:
                    # Remove from stats tracking
                    msg_id = None
                    for mid, stats in self.message_table.message_stats.items():
                        if stats.get('item') == item:
                            msg_id = mid
                            break
                    if msg_id:
                        del self.message_table.message_stats[msg_id]
                
    @pyqtSlot(str, object)
    def on_message_transmitted(self, network_id: str, msg: CANMessage):
        """Handle transmitted CAN message from multi-network manager"""
        if self.monitoring_active and self.passes_filters(msg):
            # Store current selection
            current_item = self.message_table.currentItem()
            
            self.message_table.add_message(msg)
            
            # Handle auto-scroll and selection preservation
            if self.auto_scroll:
                if self.smart_scroll_cb.isChecked():
                    # Smart scroll: only auto-scroll if no manual selection or user is at bottom
                    should_auto_scroll = (current_item is None or 
                                        (self.message_table.topLevelItemCount() > 0 and
                                         current_item == self.message_table.topLevelItem(self.message_table.topLevelItemCount() - 2)))
                    
                    if should_auto_scroll and self.message_table.topLevelItemCount() > 0:
                        last_item = self.message_table.topLevelItem(self.message_table.topLevelItemCount() - 1)
                        self.message_table.scrollToItem(last_item)
                    else:
                        # Restore selection if smart scroll is preventing auto-scroll
                        if current_item is not None and current_item.parent() is None:
                            try:
                                self.message_table.setCurrentItem(current_item)
                            except:
                                pass
                else:
                    # Traditional auto-scroll: always scroll to bottom
                    if self.message_table.topLevelItemCount() > 0:
                        last_item = self.message_table.topLevelItem(self.message_table.topLevelItemCount() - 1)
                        self.message_table.scrollToItem(last_item)
            else:
                # No auto-scroll: always preserve selection
                if current_item is not None and current_item.parent() is None:
                    try:
                        self.message_table.setCurrentItem(current_item)
                    except:
                        pass
                
    @pyqtSlot(str, object)
    def on_network_state_changed(self, network_id: str, state):
        """Handle network state changes"""
        # Update monitoring status based on active networks
        active_networks = len([n for n in self.network_manager.get_all_networks().values() if n.is_connected()])
        
        # Enable/disable monitoring based on network availability
        has_networks = active_networks > 0
        self.start_btn.setEnabled(has_networks and not self.monitoring_active)
        
        if active_networks == 0 and self.monitoring_active:
            self.stop_monitoring()
            
    def start_monitoring(self):
        """Start message monitoring"""
        self.monitoring_active = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
    def stop_monitoring(self):
        """Stop message monitoring"""
        self.monitoring_active = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
    def clear_messages(self):
        """Clear all messages"""
        self.message_table.clear_messages()
        self.details_text.clear()
        
    def toggle_auto_scroll(self, enabled: bool):
        """Toggle auto-scroll feature"""
        self.auto_scroll = enabled
        
    def set_max_messages(self, value: int):
        """Set maximum number of messages to display"""
        self.max_messages = value
        
    def apply_filters(self):
        """Apply message filters"""
        # This would implement filtering logic
        # For now, just a placeholder
        pass
        
    def passes_filters(self, msg: CANMessage) -> bool:
        """Check if message passes current filters"""
        # ID filter
        id_filter = self.id_filter_edit.text().strip()
        if id_filter and id_filter != "*":
            # Simple implementation - could be enhanced
            if not str(msg.arbitration_id) in id_filter and not f"0x{msg.arbitration_id:X}" in id_filter:
                return False
                
        # Direction filter
        direction_filter = self.direction_combo.currentText()
        if direction_filter == "RX Only" and msg.direction != 'rx':
            return False
        elif direction_filter == "TX Only" and msg.direction != 'tx':
            return False
            
        # Data filter (basic implementation)
        data_filter = self.data_filter_edit.text().strip()
        if data_filter and data_filter != "*":
            data_hex = " ".join(f"{byte:02X}" for byte in msg.data)
            if data_filter.upper() not in data_hex:
                return False
                
        return True
        
    def on_message_selected(self):
        """Handle message selection in tree"""
        current_item = self.message_table.currentItem()
        if current_item:
            # Only show details for top-level items (messages, not signals)
            if current_item.parent() is None:
                # Get message details
                time_text = current_item.text(0)
                id_text = current_item.text(1)
                data_text = current_item.text(3)
                direction_text = current_item.text(4)
                message_name = current_item.text(7)
                
                details = f"""Message Details:
Time: {time_text}
ID: {id_text}
Message: {message_name}
Direction: {direction_text}
Data: {data_text}
Length: {len(data_text.split())} bytes

Raw Data (Binary):
{' '.join(f'{int(b, 16):08b}' for b in data_text.split())}

Raw Data (Decimal):
{' '.join(str(int(b, 16)) for b in data_text.split())}

Decoded Signals:
"""
                # Add decoded signals
                for i in range(current_item.childCount()):
                    child = current_item.child(i)
                    signal_info = child.text(7)
                    details += f"  {signal_info}\n"
                
                self.details_text.setPlainText(details)
            else:
                # Signal selected - show signal details
                signal_info = current_item.text(7)
                parent_message = current_item.parent().text(7)
                
                details = f"""Signal Details:
Message: {parent_message}
Signal: {signal_info}
"""
                self.details_text.setPlainText(details)
                
    def update_status(self):
        """Update status labels"""
        # Get combined stats from all networks
        total_messages = 0
        rx_count = 0
        tx_count = 0
        
        for network in self.network_manager.get_all_networks().values():
            stats = network.get_statistics()
            total_messages += stats.get('message_count', 0)
            rx_count += stats.get('rx_count', 0)
            tx_count += stats.get('tx_count', 0)
            
        unique_ids = len(self.message_table.message_stats)
        
        self.message_count_label.setText(f"Messages: {total_messages}")
        self.rx_count_label.setText(f"RX: {rx_count}")
        self.tx_count_label.setText(f"TX: {tx_count}")
        self.unique_ids_label.setText(f"Unique IDs: {unique_ids}")
        
    def update_symbol_status(self):
        """Update symbol file status based on network assignments"""
        networks = self.network_manager.get_all_networks()
        sym_files = []
        
        for network in networks.values():
            if network.config.symbol_file_path:
                import os
                filename = os.path.basename(network.config.symbol_file_path)
                sym_files.append(f"Bus {network.config.bus_number}: {filename}")
        
        if sym_files:
            status_text = "Symbol files: " + ", ".join(sym_files)
            self.sym_status_label.setText(status_text)
            self.sym_status_label.setStyleSheet("color: #666666; font-weight: bold;")
        else:
            self.sym_status_label.setText("Using network-assigned symbol files")
            self.sym_status_label.setStyleSheet("color: #666666; font-style: italic;")
