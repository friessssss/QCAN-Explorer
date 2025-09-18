"""
Logging Tab - Data logging and playback functionality
"""

import os
import csv
import json
import time
from datetime import datetime, timezone
from typing import List, Dict
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel,
                             QLineEdit, QCheckBox, QComboBox, QSplitter, QTextEdit,
                             QGroupBox, QSpinBox, QMessageBox, QFileDialog,
                             QProgressBar, QSlider)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from canbus.messages import CANMessage
from utils.message_decoder import MessageDecoder


class LogTextWidget(QTextEdit):
    """Custom text widget with hover tooltips for decoded messages"""
    
    def __init__(self, network_manager=None):
        super().__init__()
        self.network_manager = network_manager
        self.messages = []  # Store message objects for tooltip lookup
        self.setMouseTracking(True)
        self.header_lines = 2  # Number of header lines to skip
        
    def get_symbol_parser_for_message(self, msg):
        """Get appropriate symbol parser for a message based on its bus number"""
        if not self.network_manager:
            return None
            
        networks = self.network_manager.get_all_networks()
        for network in networks.values():
            if network.config.bus_number == msg.bus_number:
                return network.get_symbol_parser()
        return None
        
    def get_message_name(self, msg_id: int, bus_number: int = 0) -> str:
        """Get message name from appropriate network's SYM parser"""
        return MessageDecoder.get_message_name(msg_id, bus_number, self.network_manager)
        
    def add_message_line(self, msg, line_text):
        """Add a message line with associated message data"""
        self.messages.append((msg, line_text))
        self.append(line_text)
        
    def clear_messages(self):
        """Clear all messages but keep header"""
        self.messages.clear()
        # Reset to header only
        header_text = "  #    Time (rel.)       Bus  ID        Message Name                     Dir Type DLC  Data (hex.)\n"
        header_text += "-" * 135 + "\n"
        self.setPlainText(header_text)
        
    def mouseMoveEvent(self, event):
        """Handle mouse move for hover tooltips"""
        try:
            if self.network_manager and self.messages:
                cursor = self.cursorForPosition(event.pos())
                line_number = cursor.blockNumber()
                
                # Adjust for header lines (subtract 1 more to fix off-by-1 issue)
                message_index = line_number - self.header_lines - 1
                
                # Debug info (uncomment to troubleshoot)
                # print(f"Tooltip debug - Line: {line_number}, Message index: {message_index}, Total messages: {len(self.messages)}")
                
                if 0 <= message_index < len(self.messages):
                    msg, line_text = self.messages[message_index]
                    decoded = self.decode_message_for_tooltip(msg)
                    if decoded and decoded.strip():
                        # Use simple plain text tooltip for maximum compatibility
                        self.setToolTip(decoded)
                    else:
                        # Fallback tooltip if decoding fails
                        self.setToolTip(f"Message ID: 0x{msg.arbitration_id:X}\\nBus: {msg.bus_number}")
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
        sym_parser = self.get_symbol_parser_for_message(msg)
        if not sym_parser or not sym_parser.messages:
            # Return basic info if no SYM file
            return f"ID: 0x{msg.arbitration_id:X}\nData: {' '.join(f'{b:02X}' for b in msg.data)}\nNo SYM file loaded for bus {msg.bus_number}"
            
        # Find matching message definition
        for msg_name, msg_def in sym_parser.messages.items():
            if msg_def.can_id == msg.arbitration_id:
                decoded_lines = [f"Message: {msg_name} (0x{msg.arbitration_id:X})"]
                decoded_lines.append("")  # Empty line for spacing
                
                # Use shared decoder
                signals = MessageDecoder.decode_message_signals(msg, sym_parser)
                for signal_name, signal_value in signals:
                    decoded_lines.append(f"  {signal_name}: {signal_value}")
                
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
    
    def __init__(self, messages: List[CANMessage], filename: str, format_type: str, log_start_time: float = None):
        super().__init__()
        self.messages = messages
        self.filename = filename
        self.format_type = format_type
        self.log_start_time = log_start_time
        
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
    
    def get_relative_timestamp(self, msg: CANMessage) -> float:
        """Get relative timestamp from log start, or absolute if no start time"""
        if self.log_start_time is not None:
            return msg.timestamp - self.log_start_time
        return msg.timestamp
    
    def unix_to_ole_date(self, unix_timestamp: float) -> float:
        """Convert Unix timestamp to OLE Automation Date format
        
        OLE Date: Days since December 30, 1899 (day 0) + fractional day
        Unix timestamp: Seconds since January 1, 1970
        """
        # OLE Date epoch: December 30, 1899 00:00:00 UTC
        # Unix epoch: January 1, 1970 00:00:00 UTC
        # Difference: 25567 days (70 years + 17 leap days + 1 day)
        ole_epoch_offset = 25567.0
        
        # Convert Unix timestamp to days
        days_since_unix_epoch = unix_timestamp / (24 * 60 * 60)
        
        # Add offset to get days since OLE epoch
        ole_date = ole_epoch_offset + days_since_unix_epoch
        
        return ole_date
            
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
                    self.get_relative_timestamp(msg),
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
                'timestamp': self.get_relative_timestamp(msg),
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
                timestamp_ms = self.get_relative_timestamp(msg) * 1000
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
        """Write messages in TRC format (PCAN Explorer compatible format)"""
        with open(self.filename, 'w') as f:
            # Write PCAN Explorer compatible header
            f.write(";$FILEVERSION=2.1\n")
            
            # Calculate OLE Automation Date for start time
            start_time = self.log_start_time if self.log_start_time else time.time()
            ole_start_time = self.unix_to_ole_date(start_time)
            f.write(f";$STARTTIME={ole_start_time:.10f}\n")
            
            f.write(";$COLUMNS=N,O,T,B,I,d,R,L,D\n")
            f.write(";\n")
            
            # Add human-readable start time
            start_datetime = datetime.fromtimestamp(start_time)
            f.write(f";   Start time: {start_datetime.strftime('%m/%d/%Y %H:%M:%S.%f')[:-3]}\n")
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
            
            # Write messages - TRC format uses relative timestamps by design
            for i, msg in enumerate(self.messages):
                timestamp_ms = self.get_relative_timestamp(msg) * 1000
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
            # Actual format: MessageNum) TimeOffset Bus Direction ID - DLC Data...
            try:
                parts = line.split()
                if len(parts) < 7:
                    continue
                    
                # Handle message number with potential closing parenthesis
                msg_num_str = parts[0].rstrip(')')  # Remove trailing parenthesis if present
                msg_num = int(msg_num_str)
                time_offset_ms = float(parts[1])
                bus = int(parts[2])
                direction = parts[3]  # 'Rx' or 'Tx'
                msg_id_hex = parts[4]
                # parts[5] is usually '-'
                dlc = int(parts[6])
                
                # Parse message ID
                msg_id = int(msg_id_hex, 16)
                
                # Parse data bytes (starting from index 7 now)
                data_bytes = []
                for j in range(7, min(7 + dlc, len(parts))):
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
                    direction='rx' if direction.upper() == 'RX' else 'tx',
                    bus_number=bus  # Set the bus number from the TRC file
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
    
    def __init__(self, network_manager):
        super().__init__()
        self.network_manager = network_manager
        self.setup_ui()
        self.setup_connections()
        
        # Logging state
        self.is_logging = False
        self.logged_messages = []
        self.log_start_time = None  # Track start time for relative timestamps
        
        # Playback state
        self.playback_messages = []
        self.playback_index = 0
        self.playback_start_time = None  # Track start time for relative timing in playback
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
        self.playback_text = LogTextWidget(self.network_manager)
        self.playback_text.setFont(QFont("Courier", 10))  # Use Courier for better column alignment
        self.playback_text.setReadOnly(True)
        self.playback_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                border: 1px solid gray;
                selection-background-color: #888888;
                line-height: 1.2;
            }
        """)
        
        # Add column header with bus number and wider message name column
        header_text = "  #    Time (rel.)       Bus  ID        Message Name                     Dir Type DLC  Data (hex.)\n"
        header_text += "-" * 135 + "\n"
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
        
        # Symbol file status
        self.sym_status_label = QLabel("Using network-assigned symbol files")
        self.sym_status_label.setStyleSheet("color: #666666; font-style: italic;")
        stats_layout.addWidget(self.sym_status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        stats_layout.addWidget(self.progress_bar)
        
        layout.addWidget(stats_group)
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_statistics)
        self.update_timer.start(1000)
        
        # Initial symbol status update
        self.update_symbol_status()
        
    def start_logging(self):
        """Start logging CAN messages"""
        # Check if any networks are connected
        connected_networks = [n for n in self.network_manager.get_all_networks().values() if n.is_connected()]
        if not connected_networks:
            QMessageBox.warning(self, "Warning", "No networks connected")
            return
            
        self.is_logging = True
        self.logged_messages.clear()
        self.log_start_time = time.time()  # Record start time for relative timestamps
        
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
            
        # Generate filename with start time
        if self.log_start_time:
            start_datetime = datetime.fromtimestamp(self.log_start_time)
            datetime_str = start_datetime.strftime("%Y-%m-%d_%H-%M-%S")
            default_filename = f"can_log_{datetime_str}{default_ext}"
        else:
            default_filename = f"can_log_{int(time.time())}{default_ext}"
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Log File", default_filename, filter_str
        )
        
        if filename:
            # Start background save
            self.log_writer = LogWriter(self.logged_messages.copy(), filename, format_type, self.log_start_time)
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
            self.log_reader.progress_updated.connect(self.on_load_progress)
            self.log_reader.message_loaded.connect(self.on_playback_message_loaded)
            self.log_reader.finished.connect(self.on_load_finished)
            self.log_reader.error_occurred.connect(self.on_load_error)
            
            self.playback_messages.clear()
            self.playback_index = 0
            self.playback_start_time = None  # Reset playback start time
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.playback_file_label.setText(f"File: {os.path.basename(filename)}")
            self.log_reader.start()
            
    def start_playback(self):
        """Start message playback"""
        if not self.playback_messages:
            QMessageBox.information(self, "Info", "No playback file loaded")
            return
            
        # Check if any networks are connected for playback
        connected_networks = [n for n in self.network_manager.get_all_networks().values() if n.is_connected()]
        if not connected_networks:
            QMessageBox.warning(self, "Warning", "No networks connected for playback")
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
            # Send on first available network (could be enhanced to use original bus)
            connected_networks = [n for n in self.network_manager.get_all_networks().values() if n.is_connected()]
            if connected_networks:
                connected_networks[0].send_message(msg.arbitration_id, msg.data, msg.is_extended_id)
            
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
            
        # Update symbol status periodically
        self.update_symbol_status()
            
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
                self.playback_start_time = None  # Reset playback start time
                
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
        
        # Don't update UI during loading - just store messages
        # UI will be updated when loading is complete
        
    def populate_playback_display(self):
        """Populate the playback display with a subset of loaded messages"""
        if not self.playback_messages:
            return
            
        # Clear existing display
        self.playback_text.clear_messages()
        
        # Set baseline timing from first message
        self.playback_start_time = self.playback_messages[0].timestamp
        
        # For large files, show first 1000 messages + every 100th message after that
        messages_to_display = []
        
        for i, msg in enumerate(self.playback_messages):
            if i < 1000 or i % 100 == 0:
                messages_to_display.append((i, msg))
                
        # Populate display efficiently
        for msg_index, msg in messages_to_display:
            # Calculate relative time
            relative_time = msg.timestamp - self.playback_start_time
            time_str = f"{relative_time:.4f}" if msg_index > 0 else "0.0000"
            
            id_str = f"0x{msg.arbitration_id:06X}"
            data_str = " ".join(f"{b:02X}" for b in msg.data)
            direction_str = msg.direction.upper()
            
            # Get message name from SYM parser
            message_name = self.playback_text.get_message_name(msg.arbitration_id, msg.bus_number)
            name_str = message_name[:30] if message_name else ""
            
            # Create line with proper column alignment
            line_text = f"{msg_index+1:4d} {time_str:16s} {msg.bus_number:3d}  {id_str:9s} {name_str:30s} {direction_str:3s} Data {len(msg.data):2d}  {data_str}"
            
            # Add to text widget
            self.playback_text.add_message_line(msg, line_text)
            
        # Update status
        total_messages = len(self.playback_messages)
        displayed_messages = len(messages_to_display)
        self.playback_file_label.setText(f"File: {total_messages:,} messages ({displayed_messages:,} displayed)")
        
    def on_load_progress(self, progress):
        """Handle load progress updates"""
        # Show progress as both message count and percentage estimate
        self.log_status_label.setText(f"Loading... {progress:,} messages")
        
        # Update progress bar (rough estimate based on file size)
        # For very large files, this gives visual feedback
        if hasattr(self, 'log_reader') and self.log_reader:
            # Estimate progress - this is rough but gives user feedback
            estimated_total = max(progress * 2, 100000)  # Rough estimate
            percentage = min(int((progress / estimated_total) * 100), 99)
            self.progress_bar.setValue(percentage)
        
    def on_load_finished(self, result):
        """Handle load completion"""
        # Now populate the UI with a subset of messages for display
        self.populate_playback_display()
        
        # Complete the progress bar
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        
        self.log_status_label.setText(f"Loaded {len(self.playback_messages):,} messages")
        QMessageBox.information(self, "Success", f"Loaded {len(self.playback_messages):,} messages from log file")
        
    def on_load_error(self, error):
        """Handle load error"""
        self.log_status_label.setText("Load failed")
        QMessageBox.critical(self, "Error", f"Failed to load log file: {error}")
        
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
            # Create status label if it doesn't exist
            if not hasattr(self, 'sym_status_label'):
                # Add it to the statistics group
                stats_group = self.findChild(QGroupBox, "Statistics")
                if stats_group:
                    layout = stats_group.layout()
                    if layout:
                        self.sym_status_label = QLabel()
                        layout.addWidget(self.sym_status_label)
            
            if hasattr(self, 'sym_status_label'):
                self.sym_status_label.setText(status_text)
                self.sym_status_label.setStyleSheet("color: #666666; font-weight: bold;")
        else:
            if hasattr(self, 'sym_status_label'):
                self.sym_status_label.setText("Using network-assigned symbol files")
                self.sym_status_label.setStyleSheet("color: #666666; font-style: italic;")
        
    def setup_connections(self):
        """Set up signal connections"""
        # Connect to multi-network manager signals for logging
        self.network_manager.message_received.connect(self.on_message_received)
        self.network_manager.message_transmitted.connect(self.on_message_transmitted)
        
    @pyqtSlot(str, object)
    def on_message_received(self, network_id: str, msg):
        """Handle received CAN message for logging"""
        if self.is_logging:
            self.logged_messages.append(msg)
            self.update_statistics()
            
            # Also display in playback area for real-time view
            self.add_message_to_display(msg)
            
    @pyqtSlot(str, object)
    def on_message_transmitted(self, network_id: str, msg):
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
        
        # Calculate relative time from log start
        if self.log_start_time is not None:
            relative_time = msg.timestamp - self.log_start_time
            time_str = f"{relative_time:.4f}"
        else:
            time_str = f"{msg.timestamp:.4f}"
            
        id_str = f"0x{msg.arbitration_id:06X}"
        data_str = " ".join(f"{b:02X}" for b in msg.data)
        direction_str = msg.direction.upper()
        
        # Get message name from SYM parser
        message_name = self.playback_text.get_message_name(msg.arbitration_id, msg.bus_number)
        name_str = message_name[:30] if message_name else ""  # Much wider - 30 chars for full names
        
        # Create line with proper column alignment including bus number and message name
        # Format: Number  Time            Bus  ID        MessageName      Dir Type DLC  Data
        line_text = f"{msg_num:4d} {time_str:16s} {msg.bus_number:3d}  {id_str:9s} {name_str:30s} {direction_str:3s} Data {len(msg.data):2d}  {data_str}"
        
        # Add to text widget
        self.playback_text.add_message_line(msg, line_text)
        
    def start_logging(self):
        """Start logging CAN messages"""
        self.is_logging = True
        self.start_log_btn.setEnabled(False)
        self.stop_log_btn.setEnabled(True)
        self.log_status_label.setText("Status: Logging...")
        
        # Clear previous log and set start time
        self.logged_messages.clear()
        self.log_start_time = time.time()  # Record start time for relative timestamps
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
        self.log_start_time = None  # Reset start time
        self.playback_text.clear_messages()
        self.log_status_label.setText("Status: Cleared")
        self.update_statistics()
        
    def save_log(self):
        """Save logged messages to file"""
        if not self.logged_messages:
            QMessageBox.warning(self, "Warning", "No messages to save")
            return
            
        format_type = self.save_format_combo.currentText()
        
        # Generate filename with start time
        if self.log_start_time:
            start_datetime = datetime.fromtimestamp(self.log_start_time)
            datetime_str = start_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        else:
            datetime_str = str(int(time.time()))
            
        # Get filename
        if format_type == "CSV":
            default_name = f"can_log_{datetime_str}.csv"
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", default_name, "CSV Files (*.csv)")
        elif format_type == "JSON":
            default_name = f"can_log_{datetime_str}.json"
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", default_name, "JSON Files (*.json)")
        elif format_type == "ASC":
            default_name = f"can_log_{datetime_str}.asc"
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", default_name, "ASC Files (*.asc)")
        elif format_type == "TRC":
            default_name = f"can_log_{datetime_str}.trc"
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", default_name, "TRC Files (*.trc)")
        else:
            default_name = f"can_log_{datetime_str}"
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log File", default_name, "All Files (*)")
            
        if filename:
            try:
                # Create log writer
                self.log_writer = LogWriter(self.logged_messages.copy(), filename, format_type, self.log_start_time)
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
