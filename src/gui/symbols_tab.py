"""
Symbols Tab - Symbolic representation and DBC file support
"""

import os
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel,
                             QLineEdit, QCheckBox, QComboBox, QSplitter, QTextEdit,
                             QGroupBox, QSpinBox, QMessageBox, QFileDialog, QTreeWidget,
                             QTreeWidgetItem, QTabWidget)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from canbus.interface_manager import CANInterfaceManager
from canbus.messages import CANMessage
from utils.sym_parser import SymParser, SymMessage, SymEnum


class MessageTreeWidget(QTreeWidget):
    """Tree widget for displaying SYM message structure"""
    
    def __init__(self):
        super().__init__()
        self.setup_tree()
        
    def setup_tree(self):
        """Set up the message tree"""
        self.setHeaderLabels(["Name", "ID", "Size", "Signals", "Description"])
        self.setAlternatingRowColors(True)
        
        # Configure column widths
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        self.setColumnWidth(2, 60)   # Size
        self.setColumnWidth(3, 60)   # Signals
        
    def load_database(self, sym_parser):
        """Load SYM database into tree"""
        self.clear()
        
        if not sym_parser or not sym_parser.messages:
            return
            
        # Add messages
        for message in sym_parser.messages.values():
            msg_item = QTreeWidgetItem(self)
            msg_item.setText(0, message.name)
            msg_item.setText(1, f"0x{message.can_id:X}")
            msg_item.setText(2, str(message.length))
            msg_item.setText(3, str(len(message.variables) + len(message.signals)))
            msg_item.setText(4, message.comment or "")
            
            # Add variables as children
            for variable in message.variables:
                var_item = QTreeWidgetItem(msg_item)
                var_item.setText(0, variable.name)
                var_item.setText(1, f"Bit {variable.start_bit}")
                var_item.setText(2, f"{variable.bit_length} bit")
                var_item.setText(3, f"{variable.factor}*x+{variable.offset}" if variable.factor != 1.0 or variable.offset != 0.0 else "")
                
                # Add enum info if available
                enum_info = ""
                if variable.enum_name and variable.enum_name in sym_parser.enums:
                    enum_info = f" ({variable.enum_name})"
                var_item.setText(4, f"{variable.unit}{enum_info}")
                
            # Add signal assignments as children
            for signal_name, start_bit in message.signals:
                if signal_name in sym_parser.signals:
                    signal = sym_parser.signals[signal_name]
                    signal_item = QTreeWidgetItem(msg_item)
                    signal_item.setText(0, signal_name)
                    signal_item.setText(1, f"Bit {start_bit}")
                    signal_item.setText(2, f"{signal.bit_length} bit")
                    signal_item.setText(3, f"{signal.factor}*x+{signal.offset}" if signal.factor != 1.0 or signal.offset != 0.0 else "")
                    
                    # Add enum info if available
                    enum_info = ""
                    if signal.enum_name and signal.enum_name in sym_parser.enums:
                        enum_info = f" ({signal.enum_name})"
                    signal_item.setText(4, f"{signal.unit}{enum_info} - {signal.comment}")
                
        self.expandAll()


class SignalTableWidget(QTableWidget):
    """Table widget for displaying decoded signals"""
    
    def __init__(self):
        super().__init__()
        self.setup_table()
        
    def setup_table(self):
        """Set up the signal table"""
        columns = ["Message", "Signal", "Raw Value", "Scaled Value", "Unit", "Min", "Max", "Description"]
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        
        # Set table properties
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSortingEnabled(True)
        
        # Configure column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        
        self.setColumnWidth(2, 80)   # Raw Value
        self.setColumnWidth(3, 100)  # Scaled Value
        self.setColumnWidth(4, 60)   # Unit
        self.setColumnWidth(5, 60)   # Min
        self.setColumnWidth(6, 60)   # Max
        
        # Set font
        font = QFont("Consolas", 9)
        self.setFont(font)
        
    def add_decoded_message(self, message_name: str, decoded_signals: Dict):
        """Add decoded message signals to table"""
        # Clear existing signals for this message
        for row in range(self.rowCount() - 1, -1, -1):
            if self.item(row, 0) and self.item(row, 0).text() == message_name:
                self.removeRow(row)
                
        # Add new signals
        for signal_name, signal_data in decoded_signals.items():
            row = self.rowCount()
            self.insertRow(row)
            
            self.setItem(row, 0, QTableWidgetItem(message_name))
            self.setItem(row, 1, QTableWidgetItem(signal_name))
            self.setItem(row, 2, QTableWidgetItem(str(signal_data.get('raw_value', ''))))
            self.setItem(row, 3, QTableWidgetItem(f"{signal_data.get('scaled_value', ''):.3f}"))
            self.setItem(row, 4, QTableWidgetItem(signal_data.get('unit', '')))
            self.setItem(row, 5, QTableWidgetItem(str(signal_data.get('minimum', ''))))
            self.setItem(row, 6, QTableWidgetItem(str(signal_data.get('maximum', ''))))
            self.setItem(row, 7, QTableWidgetItem(signal_data.get('comment', '')))


class SymbolsTab(QWidget):
    """Symbolic representation and SYM file support tab"""
    
    # Signal emitted when SYM parser changes
    sym_parser_changed = pyqtSignal(object)  # SymParser
    
    def __init__(self, can_manager: CANInterfaceManager):
        super().__init__()
        self.can_manager = can_manager
        self.setup_ui()
        self.setup_connections()
        
        # SYM parser
        self.sym_parser = None
        self.loaded_file = None
        
        # Message cache for decoding
        self.message_cache = {}
        
    def setup_ui(self):
        """Set up the symbols tab UI"""
        layout = QVBoxLayout(self)
        
        # SYM file controls
        file_group = QGroupBox("SYM File Management")
        file_layout = QHBoxLayout(file_group)
        
        self.load_sym_btn = QPushButton("Load SYM File")
        self.load_sym_btn.clicked.connect(self.load_sym_file)
        file_layout.addWidget(self.load_sym_btn)
        
        self.unload_sym_btn = QPushButton("Unload SYM")
        self.unload_sym_btn.clicked.connect(self.unload_sym_file)
        self.unload_sym_btn.setEnabled(False)
        file_layout.addWidget(self.unload_sym_btn)
        
        file_layout.addStretch()
        
        self.sym_file_label = QLabel("No SYM file loaded")
        file_layout.addWidget(self.sym_file_label)
        
        layout.addWidget(file_group)
        
        # Create tab widget for different views
        self.tab_widget = QTabWidget()
        
        # Database structure tab
        structure_tab = QWidget()
        structure_layout = QVBoxLayout(structure_tab)
        
        # Message tree
        tree_group = QGroupBox("Database Structure")
        tree_layout = QVBoxLayout(tree_group)
        
        self.message_tree = MessageTreeWidget()
        tree_layout.addWidget(self.message_tree)
        
        structure_layout.addWidget(tree_group)
        
        # Database info
        info_group = QGroupBox("Database Information")
        info_layout = QVBoxLayout(info_group)
        
        self.db_info_text = QTextEdit()
        self.db_info_text.setMaximumHeight(100)
        self.db_info_text.setReadOnly(True)
        info_layout.addWidget(self.db_info_text)
        
        structure_layout.addWidget(info_group)
        
        self.tab_widget.addTab(structure_tab, "Database Structure")
        
        # Signal decoding tab
        decoding_tab = QWidget()
        decoding_layout = QVBoxLayout(decoding_tab)
        
        # Decoding controls
        decode_controls = QHBoxLayout()
        
        self.auto_decode_cb = QCheckBox("Auto-decode messages")
        self.auto_decode_cb.setChecked(True)
        decode_controls.addWidget(self.auto_decode_cb)
        
        self.clear_signals_btn = QPushButton("Clear Signals")
        self.clear_signals_btn.clicked.connect(self.clear_decoded_signals)
        decode_controls.addWidget(self.clear_signals_btn)
        
        decode_controls.addStretch()
        
        self.decoded_count_label = QLabel("Decoded signals: 0")
        decode_controls.addWidget(self.decoded_count_label)
        
        decoding_layout.addLayout(decode_controls)
        
        # Signal table
        signals_group = QGroupBox("Decoded Signals")
        signals_layout = QVBoxLayout(signals_group)
        
        self.signal_table = SignalTableWidget()
        signals_layout.addWidget(self.signal_table)
        
        decoding_layout.addWidget(signals_group)
        
        self.tab_widget.addTab(decoding_tab, "Signal Decoding")
        
        # Message details tab
        details_tab = QWidget()
        details_layout = QVBoxLayout(details_tab)
        
        # Message selection
        msg_select_layout = QHBoxLayout()
        msg_select_layout.addWidget(QLabel("Select Message:"))
        
        self.message_combo = QComboBox()
        self.message_combo.currentTextChanged.connect(self.on_message_selected)
        msg_select_layout.addWidget(self.message_combo)
        
        msg_select_layout.addStretch()
        
        details_layout.addLayout(msg_select_layout)
        
        # Message details
        details_group = QGroupBox("Message Details")
        details_layout_inner = QVBoxLayout(details_group)
        
        self.message_details_text = QTextEdit()
        self.message_details_text.setReadOnly(True)
        details_layout_inner.addWidget(self.message_details_text)
        
        details_layout.addWidget(details_group)
        
        self.tab_widget.addTab(details_tab, "Message Details")
        
        layout.addWidget(self.tab_widget)
        
        # Statistics
        stats_layout = QHBoxLayout()
        self.messages_count_label = QLabel("Messages: 0")
        self.signals_count_label = QLabel("Signals: 0")
        self.nodes_count_label = QLabel("Nodes: 0")
        
        stats_layout.addWidget(self.messages_count_label)
        stats_layout.addWidget(self.signals_count_label)
        stats_layout.addWidget(self.nodes_count_label)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
    def setup_connections(self):
        """Set up signal connections"""
        self.can_manager.message_received.connect(self.on_message_received)
        self.can_manager.message_transmitted.connect(self.on_message_transmitted)
        
    def load_sym_file(self):
        """Load SYM file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load SYM File", "", "SYM Files (*.sym);;All Files (*)"
        )
        
        if filename:
            try:
                # Load SYM file
                self.sym_parser = SymParser()
                success = self.sym_parser.parse_file(filename)
                
                if success:
                    self.loaded_file = filename
                    
                    # Update UI
                    self.load_sym_btn.setEnabled(False)
                    self.unload_sym_btn.setEnabled(True)
                    self.sym_file_label.setText(f"Loaded: {os.path.basename(filename)}")
                    
                    # Update database structure
                    self.message_tree.load_database(self.sym_parser)
                    self.update_database_info()
                    self.update_message_combo()
                    self.update_statistics()
                    
                    # Emit signal to notify other tabs
                    self.sym_parser_changed.emit(self.sym_parser)
                    
                    QMessageBox.information(self, "Success", 
                                          f"Loaded SYM file with {len(self.sym_parser.messages)} messages")
                else:
                    QMessageBox.critical(self, "Error", "Failed to parse SYM file")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load SYM file: {str(e)}")
                
    def unload_sym_file(self):
        """Unload current SYM file"""
        self.sym_parser = None
        self.loaded_file = None
        
        # Update UI
        self.load_sym_btn.setEnabled(True)
        self.unload_sym_btn.setEnabled(False)
        self.sym_file_label.setText("No SYM file loaded")
        
        # Clear displays
        self.message_tree.clear()
        self.signal_table.setRowCount(0)
        self.db_info_text.clear()
        self.message_combo.clear()
        self.message_details_text.clear()
        self.message_cache.clear()
        
        # Emit signal to notify other tabs
        self.sym_parser_changed.emit(None)
        
        self.update_statistics()
        
    def update_database_info(self):
        """Update database information display"""
        if not self.sym_parser:
            self.db_info_text.clear()
            return
            
        stats = self.sym_parser.get_statistics()
        info = f"""Symbol File Information:
File: {os.path.basename(self.loaded_file) if self.loaded_file else 'Unknown'}
Format Version: {self.sym_parser.version}
Title: {self.sym_parser.title}
Messages: {stats['messages']}
Enumerations: {stats['enums']}
Signals: {stats['signals']}
Variables: {stats['total_variables']}
"""
        self.db_info_text.setPlainText(info)
        
    def update_message_combo(self):
        """Update message selection combo box"""
        self.message_combo.clear()
        
        if self.sym_parser:
            message_names = list(self.sym_parser.messages.keys())
            message_names.sort()
            self.message_combo.addItems(message_names)
            
    def update_statistics(self):
        """Update statistics display"""
        if self.sym_parser:
            stats = self.sym_parser.get_statistics()
            msg_count = stats['messages']
            signal_count = stats['signals']
            enum_count = stats['enums']
        else:
            msg_count = signal_count = enum_count = 0
            
        self.messages_count_label.setText(f"Messages: {msg_count}")
        self.signals_count_label.setText(f"Signals: {signal_count}")
        self.nodes_count_label.setText(f"Enums: {enum_count}")
        
        # Update decoded signals count
        decoded_count = self.signal_table.rowCount()
        self.decoded_count_label.setText(f"Decoded signals: {decoded_count}")
        
    def on_message_selected(self, message_name: str):
        """Handle message selection in combo box"""
        if not self.sym_parser or not message_name:
            self.message_details_text.clear()
            return
            
        # Find message in database
        message = self.sym_parser.messages.get(message_name)
        if not message:
            return
            
        # Display message details
        details = f"""Message: {message.name}
ID: 0x{message.can_id:X} ({message.can_id})
Length: {message.length} bytes
Cycle Time: {message.cycle_time or 'Unknown'} ms

Comment: {message.comment or 'None'}

Variables ({len(message.variables)}):
"""
        
        for variable in message.variables:
            details += f"""
  {variable.name}:
    Start Bit: {variable.start_bit}
    Length: {variable.bit_length} bits
    Data Type: {variable.data_type}
    Scale: {variable.factor}
    Offset: {variable.offset}
    Unit: {variable.unit or 'None'}
    Range: {variable.minimum or 'None'} to {variable.maximum or 'None'}
    Enum: {variable.enum_name or 'None'}
    Hex: {'Yes' if variable.is_hex else 'No'}
"""
        
        details += f"""
Signal Assignments ({len(message.signals)}):
"""
        
        for signal_name, start_bit in message.signals:
            if signal_name in self.sym_parser.signals:
                signal = self.sym_parser.signals[signal_name]
                details += f"""
  {signal_name}:
    Start Bit: {start_bit}
    Length: {signal.bit_length} bits
    Data Type: {signal.data_type}
    Scale: {signal.factor}
    Offset: {signal.offset}
    Unit: {signal.unit or 'None'}
    Range: {signal.minimum or 'None'} to {signal.maximum or 'None'}
    Enum: {signal.enum_name or 'None'}
    Comment: {signal.comment or 'None'}
"""
        
        self.message_details_text.setPlainText(details)
        
    def clear_decoded_signals(self):
        """Clear all decoded signals"""
        self.signal_table.setRowCount(0)
        self.message_cache.clear()
        self.update_statistics()
        
    @pyqtSlot(object)
    def on_message_received(self, msg: CANMessage):
        """Handle received CAN message"""
        if self.auto_decode_cb.isChecked():
            self.decode_message(msg)
            
    @pyqtSlot(object)
    def on_message_transmitted(self, msg: CANMessage):
        """Handle transmitted CAN message"""
        if self.auto_decode_cb.isChecked():
            self.decode_message(msg)
            
    def decode_message(self, msg: CANMessage):
        """Decode CAN message using SYM database"""
        if not self.sym_parser:
            return
            
        try:
            # Decode message using SYM parser
            decoded = self.sym_parser.decode_message(msg.arbitration_id, msg.data)
            
            if decoded:
                # Find message name for display
                message = self.sym_parser.get_message_by_id(msg.arbitration_id)
                message_name = message.name if message else f"ID_0x{msg.arbitration_id:X}"
                
                # Convert to signal data format
                signal_data = {}
                for signal_name, data in decoded.items():
                    signal_data[signal_name] = {
                        'raw_value': data['raw_value'],
                        'scaled_value': data['scaled_value'],
                        'unit': data['unit'],
                        'minimum': data['minimum'],
                        'maximum': data['maximum'],
                        'comment': data.get('enum_text', '') or ''
                    }
                
                # Add to signal table
                self.signal_table.add_decoded_message(message_name, signal_data)
                
                # Cache the decoded message
                self.message_cache[msg.arbitration_id] = {
                    'message': message,
                    'decoded': decoded,
                    'timestamp': msg.timestamp
                }
                
                self.update_statistics()
                
        except Exception as e:
            # Message not found in database or decode error - ignore silently
            pass
