"""
Logging Tab - Data logging and playback functionality
"""

import os
import csv
import json
import time
from datetime import datetime
from typing import List, Dict
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel,
                             QLineEdit, QCheckBox, QComboBox, QSplitter, QTextEdit,
                             QGroupBox, QSpinBox, QMessageBox, QFileDialog,
                             QProgressBar, QSlider)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from canbus.interface_manager import CANInterfaceManager
from canbus.messages import CANMessage


class LogTextWidget(QTextEdit):
    """Custom text widget with hover tooltips for decoded messages"""
    
    def __init__(self):
        super().__init__()
        self.sym_parser = None
        self.messages = []  # Store message objects for tooltip lookup
        self.setMouseTracking(True)
        self.header_lines = 2  # Number of header lines to skip
        
    def set_sym_parser(self, parser):
        """Set SYM parser for message decoding"""
        self.sym_parser = parser
        
    def get_message_name(self, msg_id: int) -> str:
        """Get message name from SYM parser"""
        if not self.sym_parser or not self.sym_parser.messages:
            return ""
        
        for msg_name, msg_def in self.sym_parser.messages.items():
            if msg_def.can_id == msg_id:
                return msg_name
        
        return ""
        
    def add_message_line(self, msg, line_text):
        """Add a message line with associated message data"""
        self.messages.append((msg, line_text))
        self.append(line_text)
        
    def clear_messages(self):
        """Clear all messages but keep header"""
        self.messages.clear()
        # Reset to header only
        header_text = "  #    Time (rel.)         ID        Message Name                     Dir Type DLC  Data (hex.)\n"
        header_text += "-" * 125 + "\n"
        self.setPlainText(header_text)
        
    def mouseMoveEvent(self, event):
        """Handle mouse move for hover tooltips"""
        try:
            if self.sym_parser and self.messages:
                cursor = self.cursorForPosition(event.pos())
                line_number = cursor.blockNumber()
                
                # Adjust for header lines
                message_index = line_number - self.header_lines
                
                # Debug info (uncomment to troubleshoot)
                # print(f"Tooltip debug - Line: {line_number}, Message index: {message_index}, Total messages: {len(self.messages)}")
                
                if 0 <= message_index < len(self.messages):
                    msg, line_text = self.messages[message_index]
                    decoded = self.decode_message_for_tooltip(msg)
                    if decoded and decoded.strip():
                        # Use simple plain text tooltip for maximum compatibility
                        self.setToolTip(decoded)
                        return
                        
            # Clear tooltip if no message or no decoding
            self.setToolTip("")
            
        except Exception as e:
            # Fail silently to avoid crashes
            self.setToolTip("")
            
        super().mouseMoveEvent(event)
        
    def enterEvent(self, event):
        """Handle mouse enter event"""
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Handle mouse leave event"""
        self.setToolTip("")
        super().leaveEvent(event)
        
    def decode_message_for_tooltip(self, msg):
        """Decode message for tooltip display"""
        if not self.sym_parser or not self.sym_parser.messages:
            # Return basic info if no SYM file
            return f"ID: 0x{msg.arbitration_id:X}\nData: {' '.join(f'{b:02X}' for b in msg.data)}\nNo SYM file loaded"
            
        # Find matching message definition
        for msg_name, msg_def in self.sym_parser.messages.items():
            if msg_def.can_id == msg.arbitration_id:
                decoded_lines = [f"Message: {msg_name} (0x{msg.arbitration_id:X})"]
                decoded_lines.append("")  # Empty line for spacing
                
                # Decode each variable
                for var in msg_def.variables:
                    if var.start_bit + var.bit_length <= len(msg.data) * 8:
                        # Extract bits (simplified)
                        start_byte = var.start_bit // 8
                        end_byte = (var.start_bit + var.bit_length - 1) // 8 + 1
                        
                        if end_byte <= len(msg.data):
                            raw_bytes = msg.data[start_byte:end_byte]
                            raw_value = int.from_bytes(raw_bytes, byteorder='little')
                            
                            # Apply bit masking
                            if var.start_bit % 8 != 0 or var.bit_length % 8 != 0:
                                bit_offset = var.start_bit % 8
                                mask = (1 << var.bit_length) - 1
                                raw_value = (raw_value >> bit_offset) & mask
                            
                            # Apply scaling
                            scaled_value = raw_value * var.factor + var.offset
                            unit_str = f" {var.unit}" if var.unit else ""
                            
                            # Handle enum values
                            if var.enum_name and var.enum_name in self.sym_parser.enums:
                                enum = self.sym_parser.enums[var.enum_name]
                                if int(scaled_value) in enum.values:
                                    value_str = enum.values[int(scaled_value)]
                                else:
                                    value_str = f"{scaled_value:.2f}{unit_str}"
                            else:
                                value_str = f"{scaled_value:.2f}{unit_str}"
                            
                            decoded_lines.append(f"  {var.name}: {value_str}")
                
                if len(decoded_lines) > 2:  # More than just header and empty line
                    return "\n".join(decoded_lines)
                else:
                    return f"Message: {msg_name} (0x{msg.arbitration_id:X})\n\nNo variables decoded"
        
        # Unknown message
        return f"Unknown Message\nID: 0x{msg.arbitration_id:X}\nData: {' '.join(f'{b:02X}' for b in msg.data)}"


class LogWriter(QThread):
    """Background thread for writing log data"""
    
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, messages: List[CANMessage], filename: str, format_type: str):
        super().__init__()
        self.messages = messages
        self.filename = filename
        self.format_type = format_type
        
    def run(self):
        """Write messages to file"""
        try:
            if self.format_type == 'CSV':
                self.write_csv()
            elif self.format_type == 'JSON':
                self.write_json()
            elif self.format_type == 'ASC':
                self.write_asc()
            elif self.format_type == 'TRC':
                self.write_trc()
            else:
                raise ValueError(f"Unsupported format: {self.format_type}")
                
            self.finished.emit(f"Successfully saved {len(self.messages)} messages")
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            
    def write_csv(self):
        """Write messages in CSV format"""
        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['Timestamp', 'ID', 'DLC', 'Data', 'Direction', 'Extended', 'Remote', 'Error'])
            
            # Write messages
            for i, msg in enumerate(self.messages):
                data_hex = ' '.join(f'{b:02X}' for b in msg.data)
                writer.writerow([
                    msg.timestamp,
                    f'0x{msg.arbitration_id:X}',
                    len(msg.data),
                    data_hex,
                    msg.direction,
                    msg.is_extended_id,
                    msg.is_remote_frame,
                    msg.is_error_frame
                ])
                
                # Update progress
                if i % 100 == 0:
                    progress = int((i / len(self.messages)) * 100)
                    self.progress_updated.emit(progress)
                    
    def write_json(self):
        """Write messages in JSON format"""
        data = {
            'version': '1.0',
            'timestamp': datetime.now().isoformat(),
            'message_count': len(self.messages),
            'messages': []
        }
        
        for i, msg in enumerate(self.messages):
            msg_data = {
                'timestamp': msg.timestamp,
                'id': msg.arbitration_id,
                'data': list(msg.data),
                'dlc': len(msg.data),
                'direction': msg.direction,
                'extended_id': msg.is_extended_id,
                'remote_frame': msg.is_remote_frame,
                'error_frame': msg.is_error_frame,
                'channel': msg.channel
            }
            data['messages'].append(msg_data)
            
            # Update progress
            if i % 100 == 0:
                progress = int((i / len(self.messages)) * 100)
                self.progress_updated.emit(progress)
                
        with open(self.filename, 'w') as f:
            json.dump(data, f, indent=2)
            
    def write_asc(self):
        """Write messages in ASC format (Vector format)"""
        with open(self.filename, 'w') as f:
            # Write header
            f.write("date Wed Jan 01 12:00:00.000 2025\n")
            f.write("base hex  timestamps absolute\n")
            f.write("no internal events logged\n")
            f.write("Begin Triggerblock Wed Jan 01 12:00:00.000 2025\n")
            
            # Write messages
            for i, msg in enumerate(self.messages):
                timestamp_ms = msg.timestamp * 1000
                data_hex = ''.join(f'{b:02X}' for b in msg.data)
                
                direction = 'Rx' if msg.direction == 'rx' else 'Tx'
                extended = 'x' if msg.is_extended_id else ''
                
                f.write(f"{timestamp_ms:10.3f} 1  {msg.arbitration_id:X}{extended}             "
                       f"{direction}   d {len(msg.data)} {data_hex}\n")
                
                # Update progress
                if i % 100 == 0:
                    progress = int((i / len(self.messages)) * 100)
                    self.progress_updated.emit(progress)
                    
            f.write("End TriggerBlock\n")
            
    def write_trc(self):
        """Write messages in TRC format (Vector CANoe/CANalyzer format)"""
        with open(self.filename, 'w') as f:
            # Write header
            f.write(";$FILEVERSION=2.1\n")
            f.write(f";$STARTTIME={time.time()}\n")
            f.write(";$COLUMNS=N,O,T,B,I,d,R,L,D\n")
            f.write(";\n")
            f.write(f";   Start time: {datetime.now().strftime('%m/%d/%Y %H:%M:%S.%f')[:-3]}\n")
            f.write(";   Generated by QCAN Explorer\n")
            f.write(";-------------------------------------------------------------------------------\n")
            f.write(";   Bus  Connection        Protocol  Bit rate\n")
            f.write(";   1    CAN               CAN       500 kbit/s\n")
            f.write(";-------------------------------------------------------------------------------\n")
            f.write(";   Message    Time    Type    ID     Rx/Tx\n")
            f.write(";   Number     Offset  |  Bus  [hex]  |  Reserved\n")
            f.write(";   |          [ms]    |  |    |      |  |  Data Length Code\n")
            f.write(";   |          |       |  |    |      |  |  |    Data [hex] ...\n")
            f.write(";   |          |       |  |    |      |  |  |    |\n")
            f.write(";---+--- ------+------ +- +- --+----- +- +- +--- +- -- -- -- -- -- -- --\n")
            
            # Write messages
            start_time = self.messages[0].timestamp if self.messages else time.time()
            for i, msg in enumerate(self.messages):
                timestamp_ms = (msg.timestamp - start_time) * 1000
                data_hex = ' '.join(f'{b:02X}' for b in msg.data)
                
                direction = 'Rx' if msg.direction == 'rx' else 'Tx'
                
                f.write(f"{i+1:8d} {timestamp_ms:10.3f} DT 1 {msg.arbitration_id:08X} {direction} - "
                       f"{len(msg.data):2d}    {data_hex}\n")
                
                # Update progress
                if i % 100 == 0:
                    progress = int((i / len(self.messages)) * 100)
                    self.progress_updated.emit(progress)


class LogReader(QThread):
    """Background thread for reading log data"""
    
    progress_updated = pyqtSignal(int)
    message_loaded = pyqtSignal(object)
    finished = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self.messages = []
        
    def run(self):
        """Read messages from file"""
        try:
            file_ext = os.path.splitext(self.filename)[1].lower()
            
            if file_ext == '.csv':
                self.read_csv()
            elif file_ext == '.json':
                self.read_json()
            elif file_ext == '.asc':
                self.read_asc()
            elif file_ext == '.trc':
                self.read_trc()
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
                
            self.finished.emit(len(self.messages))
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            
    def read_csv(self):
        """Read messages from CSV format"""
        with open(self.filename, 'r') as f:
            reader = csv.DictReader(f)
            
            for i, row in enumerate(reader):
                # Parse message data
                msg_id = int(row['ID'], 16) if row['ID'].startswith('0x') else int(row['ID'])
                data_bytes = bytes.fromhex(row['Data'].replace(' ', ''))
                
                msg = CANMessage(
                    timestamp=float(row['Timestamp']),
                    arbitration_id=msg_id,
                    data=data_bytes,
                    is_extended_id=row['Extended'].lower() == 'true',
                    is_remote_frame=row['Remote'].lower() == 'true',
                    is_error_frame=row['Error'].lower() == 'true',
                    channel='file',
                    direction=row['Direction']
                )
                
                self.messages.append(msg)
                self.message_loaded.emit(msg)
                
                # Update progress every 100 messages
                if i % 100 == 0:
                    self.progress_updated.emit(i)
                    
    def read_json(self):
        """Read messages from JSON format"""
        with open(self.filename, 'r') as f:
            data = json.load(f)
            
        messages = data.get('messages', [])
        
        for i, msg_data in enumerate(messages):
            msg = CANMessage(
                timestamp=msg_data['timestamp'],
                arbitration_id=msg_data['id'],
                data=bytes(msg_data['data']),
                is_extended_id=msg_data.get('extended_id', False),
                is_remote_frame=msg_data.get('remote_frame', False),
                is_error_frame=msg_data.get('error_frame', False),
                channel=msg_data.get('channel', 'file'),
                direction=msg_data['direction']
            )
            
            self.messages.append(msg)
            self.message_loaded.emit(msg)
            
            # Update progress
            if i % 100 == 0:
                progress = int((i / len(messages)) * 100)
                self.progress_updated.emit(progress)
                
    def read_trc(self):
        """Read messages from TRC format (Vector CANoe/CANalyzer)"""
        import re
        
        with open(self.filename, 'r') as f:
            lines = f.readlines()
            
        start_time = None
        message_count = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip comments and headers
            if line.startswith(';') or not line:
                # Extract start time from header if available
                if line.startswith(';$STARTTIME='):
                    try:
                        start_time = float(line.split('=')[1])
                    except:
                        pass
                continue
                
            # Skip separator lines
            if line.startswith(';---'):
                continue
                
            # Parse data line
            # Format: MessageNum TimeOffset Type Bus ID Direction - DLC Data...
            try:
                parts = line.split()
                if len(parts) < 8:
                    continue
                    
                msg_num = int(parts[0])
                time_offset_ms = float(parts[1])
                msg_type = parts[2]  # Usually 'DT' for data
                bus = int(parts[3])
                msg_id_hex = parts[4]
                direction = parts[5]  # 'Rx' or 'Tx'
                # parts[6] is usually '-'
                dlc = int(parts[7])
                
                # Parse message ID
                msg_id = int(msg_id_hex, 16)
                
                # Parse data bytes
                data_bytes = []
                for j in range(8, min(8 + dlc, len(parts))):
                    if j < len(parts):
                        data_bytes.append(int(parts[j], 16))
                        
                data = bytes(data_bytes)
                
                # Calculate absolute timestamp
                if start_time is not None:
                    timestamp = start_time + (time_offset_ms / 1000.0)
                else:
                    timestamp = time.time() + (time_offset_ms / 1000.0)
                    
                # Create CAN message
                msg = CANMessage(
                    timestamp=timestamp,
                    arbitration_id=msg_id,
                    data=data,
                    is_extended_id=msg_id > 0x7FF,
                    is_remote_frame=False,
                    is_error_frame=False,
                    channel=f'bus{bus}',
                    direction='rx' if direction.upper() == 'RX' else 'tx'
                )
                
                self.messages.append(msg)
                self.message_loaded.emit(msg)
                
                message_count += 1
                
                # Update progress every 100 messages
                if message_count % 100 == 0:
                    self.progress_updated.emit(message_count)
                    
            except (ValueError, IndexError) as e:
                # Skip malformed lines
                continue


class LoggingTab(QWidget):
    """Data logging and playback tab"""
    
    def __init__(self, can_manager: CANInterfaceManager):
        super().__init__()
        self.can_manager = can_manager
        self.setup_ui()
        self.setup_connections()
        
        # Logging state
        self.is_logging = False
        self.logged_messages = []
        
        # Playback state
        self.playback_messages = []
        self.playback_index = 0
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.playback_next_message)
        
        # Background threads
        self.log_writer = None
        self.log_reader = None
        
    def setup_ui(self):
        """Set up the logging tab UI"""
        layout = QVBoxLayout(self)
        
        # Logging controls - single row
        logging_group = QGroupBox("Data Logging")
        logging_layout = QVBoxLayout(logging_group)
        
        # Single controls row
        log_controls = QHBoxLayout()
        
        self.start_log_btn = QPushButton("Start Logging")
        self.start_log_btn.clicked.connect(self.start_logging)
        log_controls.addWidget(self.start_log_btn)
        
        self.stop_log_btn = QPushButton("Stop Logging")
        self.stop_log_btn.clicked.connect(self.stop_logging)
        self.stop_log_btn.setEnabled(False)
        log_controls.addWidget(self.stop_log_btn)
        
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_controls.addWidget(self.clear_log_btn)
        
        log_controls.addWidget(QLabel("|"))  # Separator
        
        self.save_log_btn = QPushButton("Save Log")
        self.save_log_btn.clicked.connect(self.save_log)
        log_controls.addWidget(self.save_log_btn)
        
        self.open_log_btn = QPushButton("Open Log")
        self.open_log_btn.clicked.connect(self.open_log)
        log_controls.addWidget(self.open_log_btn)
        
        log_controls.addWidget(QLabel("Format:"))
        self.save_format_combo = QComboBox()
        self.save_format_combo.addItems(["CSV", "JSON", "ASC", "TRC"])
        log_controls.addWidget(self.save_format_combo)
        
        log_controls.addStretch()
        
        self.log_status_label = QLabel("Status: Ready")
        log_controls.addWidget(self.log_status_label)
        
        logging_layout.addLayout(log_controls)
        
        layout.addWidget(logging_group)
        
        # Data Playback area - simple text display
        playback_group = QGroupBox("Data Playback")
        playback_layout = QVBoxLayout(playback_group)
        
        # Create custom text widget with hover tooltips
        self.playback_text = LogTextWidget()
        self.playback_text.setFont(QFont("Courier", 10))  # Use Courier for better column alignment
        self.playback_text.setReadOnly(True)
        self.playback_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                border: 1px solid gray;
                selection-background-color: #3399ff;
                line-height: 1.2;
            }
        """)
        
        # Add column header with significantly wider message name column
        header_text = "  #    Time (rel.)         ID        Message Name                     Dir Type DLC  Data (hex.)\n"
        header_text += "-" * 125 + "\n"
        self.playback_text.setPlainText(header_text)
        playback_layout.addWidget(self.playback_text)
        
        layout.addWidget(playback_group)
        
        # Statistics and progress
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        # Stats row 1
        stats_row1 = QHBoxLayout()
        self.logged_count_label = QLabel("Logged: 0")
        self.file_size_label = QLabel("Size: 0 MB")
        self.playback_file_label = QLabel("File: None")
        
        stats_row1.addWidget(self.logged_count_label)
        stats_row1.addWidget(self.file_size_label)
        stats_row1.addWidget(self.playback_file_label)
        stats_row1.addStretch()
        
        stats_layout.addLayout(stats_row1)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        stats_layout.addWidget(self.progress_bar)
        
        layout.addWidget(stats_group)
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_statistics)
        self.update_timer.start(1000)
        
    def setup_connections(self):
        """Set up signal connections"""
        self.can_manager.message_received.connect(self.on_message_received)
        self.can_manager.message_transmitted.connect(self.on_message_transmitted)
        self.can_manager.connection_changed.connect(self.on_connection_changed)
        
    def start_logging(self):
        """Start logging CAN messages"""
        if not self.can_manager.is_connected():
            QMessageBox.warning(self, "Warning", "Not connected to CAN interface")
            return
            
        self.is_logging = True
        self.logged_messages.clear()
        
        # Update UI
        self.start_log_btn.setEnabled(False)
        self.stop_log_btn.setEnabled(True)
        self.log_status_label.setText("Status: Logging...")
        
    def stop_logging(self):
        """Stop logging CAN messages"""
        self.is_logging = False
        
        # Update UI
        self.start_log_btn.setEnabled(True)
        self.stop_log_btn.setEnabled(False)
        self.log_status_label.setText(f"Status: Stopped ({len(self.logged_messages)} messages)")
        
    def clear_log(self):
        """Clear logged messages"""
        self.logged_messages.clear()
        self.log_status_label.setText("Status: Ready")
        
    def set_max_log_messages(self, value: int):
        """Set maximum number of messages to log"""
        self.max_log_messages = value
        
    def save_log(self):
        """Save logged messages to file"""
        if not self.logged_messages:
            QMessageBox.information(self, "Info", "No messages to save")
            return
            
        format_type = self.save_format_combo.currentText()
        
        # File dialog
        if format_type == 'CSV':
            filter_str = "CSV Files (*.csv);;All Files (*)"
            default_ext = ".csv"
        elif format_type == 'JSON':
            filter_str = "JSON Files (*.json);;All Files (*)"
            default_ext = ".json"
        elif format_type == 'ASC':
            filter_str = "ASC Files (*.asc);;All Files (*)"
            default_ext = ".asc"
        else:  # TRC
            filter_str = "TRC Files (*.trc);;All Files (*)"
            default_ext = ".trc"
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Log File", f"can_log_{int(time.time())}{default_ext}", filter_str
        )
        
        if filename:
            # Start background save
            self.log_writer = LogWriter(self.logged_messages.copy(), filename, format_type)
            self.log_writer.progress_updated.connect(self.progress_bar.setValue)
            self.log_writer.finished.connect(self.on_save_finished)
            self.log_writer.error_occurred.connect(self.on_save_error)
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.log_writer.start()
            
    def load_log_file(self):
        """Load log file for playback"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Log File", "", 
            "Log Files (*.csv *.json *.asc *.trc);;CSV Files (*.csv);;JSON Files (*.json);;ASC Files (*.asc);;TRC Files (*.trc);;All Files (*)"
        )
        
        if filename:
            # Start background load
            self.log_reader = LogReader(filename)
            self.log_reader.progress_updated.connect(self.progress_bar.setValue)
            self.log_reader.message_loaded.connect(self.on_playback_message_loaded)
            self.log_reader.finished.connect(self.on_load_finished)
            self.log_reader.error_occurred.connect(self.on_load_error)
            
            self.playback_messages.clear()
            self.playback_index = 0
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.playback_file_label.setText(f"File: {os.path.basename(filename)}")
            self.log_reader.start()
            
    def start_playback(self):
        """Start message playback"""
        if not self.playback_messages:
            QMessageBox.information(self, "Info", "No playback file loaded")
            return
            
        if not self.can_manager.is_connected():
            QMessageBox.warning(self, "Warning", "Not connected to CAN interface")
            return
            
        # Calculate playback interval based on speed
        speed_text = self.playback_speed_combo.currentText()
        speed = float(speed_text.replace('x', ''))
        
        # Start playback timer
        self.playback_timer.start(int(10 / speed))  # Base 10ms interval
        
        # Update UI
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_playback_btn.setEnabled(True)
        
    def pause_playback(self):
        """Pause message playback"""
        self.playback_timer.stop()
        
        # Update UI
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        
    def stop_playback(self):
        """Stop message playback"""
        self.playback_timer.stop()
        self.playback_index = 0
        
        # Update UI
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_playback_btn.setEnabled(False)
        self.playback_progress.setValue(0)
        
    def playback_next_message(self):
        """Send next message in playback"""
        if self.playback_index >= len(self.playback_messages):
            self.stop_playback()
            return
            
        msg = self.playback_messages[self.playback_index]
        
        # Send message if it's a TX message or if we're replaying all
        if msg.direction == 'tx':
            self.can_manager.send_message(msg.arbitration_id, msg.data, msg.is_extended_id)
            
        self.playback_index += 1
        
        # Update progress
        progress = int((self.playback_index / len(self.playback_messages)) * 100)
        self.playback_progress.setValue(progress)
        self.playback_position_label.setText(f"{self.playback_index} / {len(self.playback_messages)}")
        
    def on_playback_seek_start(self):
        """Handle playback seek start"""
        if self.playback_timer.isActive():
            self.playback_timer.stop()
            
    def on_playback_seek_end(self):
        """Handle playback seek end"""
        if self.playback_messages:
            progress = self.playback_progress.value()
            self.playback_index = int((progress / 100) * len(self.playback_messages))
            self.playback_position_label.setText(f"{self.playback_index} / {len(self.playback_messages)}")
            
    @pyqtSlot(object)
    def on_message_received(self, msg: CANMessage):
        """Handle received CAN message"""
        if self.is_logging and len(self.logged_messages) < self.max_log_messages:
            self.logged_messages.append(msg)
            
    @pyqtSlot(object)
    def on_message_transmitted(self, msg: CANMessage):
        """Handle transmitted CAN message"""
        if self.is_logging and len(self.logged_messages) < self.max_log_messages:
            self.logged_messages.append(msg)
            
    @pyqtSlot(object)
    def on_playback_message_loaded(self, msg: CANMessage):
        """Handle playback message loaded"""
        self.playback_messages.append(msg)
        
    @pyqtSlot(str)
    def on_save_finished(self, message: str):
        """Handle save completion"""
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Success", message)
        
    @pyqtSlot(str)
    def on_save_error(self, error: str):
        """Handle save error"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", f"Save failed: {error}")
        
    @pyqtSlot(int)
    def on_load_finished(self, count: int):
        """Handle load completion"""
        self.progress_bar.setVisible(False)
        self.playback_progress.setMaximum(len(self.playback_messages))
        self.playback_position_label.setText(f"0 / {len(self.playback_messages)}")
        
        # Enable playback controls
        self.play_btn.setEnabled(True)
        
        QMessageBox.information(self, "Success", f"Loaded {count} messages")
        
    @pyqtSlot(str)
    def on_load_error(self, error: str):
        """Handle load error"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", f"Load failed: {error}")
        
    @pyqtSlot(bool)
    def on_connection_changed(self, connected: bool):
        """Handle connection state changes"""
        if not connected:
            if self.is_logging:
                self.stop_logging()
            if self.playback_timer.isActive():
                self.stop_playback()
                
    def update_statistics(self):
        """Update statistics display"""
        # Logged messages count
        self.logged_count_label.setText(f"Logged: {len(self.logged_messages)}")
        
        # Estimate file size (rough calculation)
        if self.logged_messages:
            avg_msg_size = 50  # Average bytes per message in CSV
            estimated_size = len(self.logged_messages) * avg_msg_size / (1024 * 1024)
            self.file_size_label.setText(f"Size: {estimated_size:.1f} MB")
            
    def open_log(self):
        """Open an existing log file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Log File", "", 
            "All Supported (*.csv *.json *.asc *.trc);;CSV Files (*.csv);;JSON Files (*.json);;ASC Files (*.asc);;TRC Files (*.trc);;All Files (*)"
        )
        
        if filename:
            try:
                # Clear current playback data
                self.playback_text.clear_messages()
                self.playback_messages = []
                
                # Determine file type and load
                file_ext = filename.lower().split('.')[-1]
                
                # Create log reader
                self.log_reader = LogReader(filename)
                self.log_reader.message_loaded.connect(self.on_playback_message_loaded)
                self.log_reader.progress_updated.connect(self.on_load_progress)
                self.log_reader.finished.connect(self.on_load_finished)
                self.log_reader.error_occurred.connect(self.on_load_error)
                
                # Start loading
                self.log_status_label.setText("Loading log file...")
                self.log_reader.start()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open log file: {str(e)}")
                
    def on_playback_message_loaded(self, msg):
        """Handle message loaded from file for playback"""
        self.playback_messages.append(msg)
        
        # Format message for text display with distinct columns and message name
        msg_num = len(self.playback_messages)
        time_str = f"{msg.timestamp:.4f}"
        id_str = f"0x{msg.arbitration_id:06X}"
        data_str = " ".join(f"{b:02X}" for b in msg.data)
        direction_str = msg.direction.upper()
        
        # Get message name from SYM parser
        message_name = self.playback_text.get_message_name(msg.arbitration_id)
        name_str = message_name[:30] if message_name else ""  # Much wider - 30 chars for full names
        
        # Create line with proper column alignment including message name
        line_text = f"{msg_num:4d} {time_str:18s} {id_str:9s} {name_str:30s} {direction_str:3s} Data {len(msg.data):2d}  {data_str}"
        
        # Add to text widget
        self.playback_text.add_message_line(msg, line_text)
        
    def on_load_progress(self, progress):
        """Handle load progress updates"""
        self.log_status_label.setText(f"Loading... {progress} messages")
        
    def on_load_finished(self, result):
        """Handle load completion"""
        self.log_status_label.setText(f"Loaded {len(self.playback_messages)} messages")
        QMessageBox.information(self, "Success", f"Loaded {len(self.playback_messages)} messages from log file")
        
    def on_load_error(self, error):
        """Handle load error"""
        self.log_status_label.setText("Load failed")
        QMessageBox.critical(self, "Error", f"Failed to load log file: {error}")
        
    def set_sym_parser(self, parser):
        """Set SYM parser for message decoding in tooltips"""
        self.playback_text.set_sym_parser(parser)
        
    def setup_connections(self):
        """Set up signal connections"""
        # Connect to CAN manager signals for logging
        self.can_manager.message_received.connect(self.on_message_received)
        self.can_manager.message_transmitted.connect(self.on_message_transmitted)
        
    @pyqtSlot(object)
    def on_message_received(self, msg):
        """Handle received CAN message for logging"""
        if self.is_logging:
            self.logged_messages.append(msg)
            self.update_statistics()
            
            # Also display in playback area for real-time view
            self.add_message_to_display(msg)
            
    @pyqtSlot(object)
    def on_message_transmitted(self, msg):
        """Handle transmitted CAN message for logging"""
        if self.is_logging:
            self.logged_messages.append(msg)
            self.update_statistics()
            
            # Also display in playback area for real-time view
            self.add_message_to_display(msg)
            
    def add_message_to_display(self, msg):
        """Add message to the playback text display"""
        # Format message for text display with distinct columns and message name
        msg_num = len(self.logged_messages)
        time_str = f"{msg.timestamp:.4f}"
        id_str = f"0x{msg.arbitration_id:06X}"
        data_str = " ".join(f"{b:02X}" for b in msg.data)
        direction_str = msg.direction.upper()
        
        # Get message name from SYM parser
        message_name = self.playback_text.get_message_name(msg.arbitration_id)
        name_str = message_name[:30] if message_name else ""  # Much wider - 30 chars for full names
        
        # Create line with proper column alignment including message name
        # Format: Number  Time            ID        MessageName      Dir Type DLC  Data
        line_text = f"{msg_num:4d} {time_str:18s} {id_str:9s} {name_str:30s} {direction_str:3s} Data {len(msg.data):2d}  {data_str}"
        
        # Add to text widget
        self.playback_text.add_message_line(msg, line_text)
        
    def start_logging(self):
        """Start logging CAN messages"""
        self.is_logging = True
        self.start_log_btn.setEnabled(False)
        self.stop_log_btn.setEnabled(True)
        self.log_status_label.setText("Status: Logging...")
        
        # Clear previous log
        self.logged_messages.clear()
        self.playback_text.clear_messages()
        
    def stop_logging(self):
        """Stop logging CAN messages"""
        self.is_logging = False
        self.start_log_btn.setEnabled(True)
        self.stop_log_btn.setEnabled(False)
        self.log_status_label.setText(f"Status: Stopped ({len(self.logged_messages)} messages)")
        
    def clear_log(self):
        """Clear logged messages"""
        self.logged_messages.clear()
        self.playback_text.clear_messages()
        self.log_status_label.setText("Status: Cleared")
        self.update_statistics()
        
    def save_log(self):
        """Save logged messages to file"""
        if not self.logged_messages:
            QMessageBox.warning(self, "Warning", "No messages to save")
            return
            
        format_type = self.save_format_combo.currentText()
        
        # Get filename
        if format_type == "CSV":
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", "", "CSV Files (*.csv)")
        elif format_type == "JSON":
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", "", "JSON Files (*.json)")
        elif format_type == "ASC":
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", "", "ASC Files (*.asc)")
        elif format_type == "TRC":
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", "", "TRC Files (*.trc)")
        else:
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", "", "All Files (*)")
            
        if filename:
            try:
                # Create log writer
                self.log_writer = LogWriter(filename, format_type, self.logged_messages)
                self.log_writer.progress_updated.connect(self.on_save_progress)
                self.log_writer.finished.connect(self.on_save_finished)
                self.log_writer.error_occurred.connect(self.on_save_error)
                
                # Start saving
                self.log_status_label.setText("Saving...")
                self.log_writer.start()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save log file: {str(e)}")
                
    def on_save_progress(self, progress):
        """Handle save progress updates"""
        self.log_status_label.setText(f"Saving... {progress}%")
        
    def on_save_finished(self, result):
        """Handle save completion"""
        self.log_status_label.setText("Save completed")
        QMessageBox.information(self, "Success", "Log file saved successfully")
        
    def on_save_error(self, error):
        """Handle save error"""
        self.log_status_label.setText("Save failed")
        QMessageBox.critical(self, "Error", f"Failed to save log file: {error}")
