"""
Plotting Tab - Real-time signal plotting and analysis
"""

import time
import os
from typing import Dict, List, Optional, Tuple
from collections import deque
import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QLineEdit, QCheckBox, QComboBox, QSplitter, QTextEdit,
                             QGroupBox, QSpinBox, QTreeWidget, QTreeWidgetItem,
                             QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QSlider, QDialog)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from canbus.interface_manager import CANInterfaceManager
from canbus.messages import CANMessage
from utils.sym_parser import SymParser


class SignalSelectionDialog(QDialog):
    """Dialog for selecting signals to plot"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Signals to Plot")
        self.setGeometry(200, 200, 800, 600)
        self.selected_signals = []
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("Select the signals you want to plot. Use Ctrl+Click for multiple selection.")
        instructions.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Signal tree
        self.signal_tree = QTreeWidget()
        self.signal_tree.setHeaderLabels(["Signal Name", "Message", "Unit", "Description"])
        self.signal_tree.setAlternatingRowColors(True)
        self.signal_tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        
        # Configure column widths
        header = self.signal_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.signal_tree)
        
        # Selection info
        self.selection_label = QLabel("0 signals selected")
        self.selection_label.setStyleSheet("font-weight: bold; color: #2980b9;")
        layout.addWidget(self.selection_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(self.select_all_btn)
        
        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(self.clear_selection_btn)
        
        button_layout.addStretch()
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setDefault(True)
        button_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Connect selection change
        self.signal_tree.itemSelectionChanged.connect(self.update_selection_count)
        
    def load_signals(self, sym_parser: SymParser):
        """Load signals from SYM parser"""
        self.signal_tree.clear()
        
        if not sym_parser or not sym_parser.messages:
            return
            
        # Add signals from each message
        for msg_name, message in sym_parser.messages.items():
            # Add variables (these are the actual plottable signals)
            for variable in message.variables:
                item = QTreeWidgetItem(self.signal_tree)
                item.setText(0, variable.name)  # Just signal name
                item.setText(1, msg_name)       # Message name
                item.setText(2, variable.unit or "")  # Unit
                item.setText(3, getattr(variable, 'comment', '') or "")  # Description if available
                
                # Store full info for retrieval
                item.setData(0, Qt.ItemDataRole.UserRole, (msg_name, variable.name))
                
            # Also add signals from the signals list if they exist
            # (Some SYM files might have signals defined separately)
            for signal_assignment in message.signals:
                # Signal assignments are tuples of (signal_name, start_bit)
                if isinstance(signal_assignment, tuple) and len(signal_assignment) >= 2:
                    signal_name = signal_assignment[0]
                    # Check if this signal is defined in the global signals dictionary
                    if signal_name in sym_parser.signals:
                        signal_def = sym_parser.signals[signal_name]
                        item = QTreeWidgetItem(self.signal_tree)
                        item.setText(0, signal_def.name)  # Signal name
                        item.setText(1, msg_name)         # Message name
                        item.setText(2, signal_def.unit or "")  # Unit
                        item.setText(3, signal_def.comment or "")  # Description
                        
                        # Store full info for retrieval
                        item.setData(0, Qt.ItemDataRole.UserRole, (msg_name, signal_def.name))
                
    def update_selection_count(self):
        """Update selection count label"""
        selected_count = len(self.signal_tree.selectedItems())
        self.selection_label.setText(f"{selected_count} signals selected")
        
    def select_all(self):
        """Select all signals"""
        self.signal_tree.selectAll()
        
    def clear_selection(self):
        """Clear all selections"""
        self.signal_tree.clearSelection()
        
    def get_selected_signals(self):
        """Get list of selected signals"""
        selected = []
        for item in self.signal_tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                msg_name, signal_name = data
                selected.append((msg_name, signal_name))
        return selected


class SignalData:
    """Container for signal plotting data"""
    
    def __init__(self, message_name: str, signal_name: str, can_id: int, color: str):
        self.message_name = message_name
        self.signal_name = signal_name
        self.can_id = can_id
        self.color = color
        self.times = deque(maxlen=10000)  # Store last 10k points
        self.values = deque(maxlen=10000)
        self.enabled = True
        self.y_axis = 'left'  # 'left' or 'right'
        self.plot_item = None  # pyqtgraph plot item
        
    def add_point(self, timestamp: float, value: float):
        """Add a new data point"""
        self.times.append(timestamp)
        self.values.append(value)
        
    def get_data_arrays(self):
        """Get data as arrays for plotting"""
        return list(self.times), list(self.values)
        
    def clear_data(self):
        """Clear all data points"""
        self.times.clear()
        self.values.clear()


class SignalSelectionWidget(QTreeWidget):
    """Widget for selecting which signals to plot"""
    
    signal_toggled = pyqtSignal(str, str, bool)  # message_name, signal_name, enabled
    
    def __init__(self):
        super().__init__()
        self.setup_tree()
        
    def setup_tree(self):
        """Set up the signal selection tree"""
        self.setHeaderLabels(["Signal", "Unit", "Plot"])
        self.setAlternatingRowColors(True)
        
        # Configure column widths
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(2, 50)
        
    def load_signals(self, sym_parser: SymParser):
        """Load signals from SYM parser"""
        self.clear()
        
        if not sym_parser or not sym_parser.messages:
            return
            
        # Add signals from each message
        for msg_name, message in sym_parser.messages.items():
            for variable in message.variables:
                item = QTreeWidgetItem(self)
                # Show full signal name (no truncation)
                signal_display_name = f"{msg_name}.{variable.name}"
                item.setText(0, signal_display_name)
                item.setText(1, variable.unit or "")
                
                # Store message name and signal name for internal use
                item.setData(0, Qt.ItemDataRole.UserRole, (msg_name, variable.name))
                
                # Add checkbox for plotting
                checkbox = QCheckBox()
                checkbox.stateChanged.connect(
                    lambda state, mn=msg_name, sn=variable.name: 
                    self.signal_toggled.emit(mn, sn, state == Qt.CheckState.Checked.value)
                )
                self.setItemWidget(item, 2, checkbox)


class PlottingTab(QWidget):
    """Real-time signal plotting and analysis tab"""
    
    def __init__(self, can_manager: CANInterfaceManager):
        super().__init__()
        self.can_manager = can_manager
        self.sym_parser = None
        self.setup_ui()
        self.setup_connections()
        
        # Plotting data
        self.signals: Dict[str, SignalData] = {}  # Key: "message_name.signal_name"
        self.plot_colors = ['#ff0000', '#00ff00', '#0000ff', '#ff8800', '#8800ff', 
                           '#00ffff', '#ffff00', '#ff0088', '#88ff00', '#0088ff']
        self.color_index = 0
        
        # Plotting state
        self.is_recording = False
        self.start_time = None
        self.trace_messages = []  # Loaded trace file messages
        self.is_trace_mode = False  # True when plotting from trace file
        
        # Update timer for real-time plotting
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_plots)
        self.plot_timer.start(100)  # Update every 100ms
        
    def setup_ui(self):
        """Set up the plotting tab UI"""
        layout = QVBoxLayout(self)
        
        # Control panel
        control_group = QGroupBox("Plotting Controls")
        control_layout = QHBoxLayout(control_group)
        
        # Recording controls
        self.start_recording_btn = QPushButton("Start Recording")
        self.start_recording_btn.clicked.connect(self.start_recording)
        control_layout.addWidget(self.start_recording_btn)
        
        self.stop_recording_btn = QPushButton("Stop Recording")
        self.stop_recording_btn.clicked.connect(self.stop_recording)
        self.stop_recording_btn.setEnabled(False)
        control_layout.addWidget(self.stop_recording_btn)
        
        self.clear_plots_btn = QPushButton("Clear Plots")
        self.clear_plots_btn.clicked.connect(self.clear_plots)
        control_layout.addWidget(self.clear_plots_btn)
        
        control_layout.addWidget(QLabel("|"))  # Separator
        
        # File controls
        self.load_sym_btn = QPushButton("Load SYM File")
        self.load_sym_btn.clicked.connect(self.load_sym_file)
        control_layout.addWidget(self.load_sym_btn)
        
        self.load_trace_btn = QPushButton("Load Trace File")
        self.load_trace_btn.clicked.connect(self.load_trace_file)
        control_layout.addWidget(self.load_trace_btn)
        
        self.sym_status_label = QLabel("No SYM file loaded")
        self.sym_status_label.setStyleSheet("color: gray; font-style: italic;")
        control_layout.addWidget(self.sym_status_label)
        
        control_layout.addStretch()
        
        # Time axis controls
        control_layout.addWidget(QLabel("Time Window:"))
        self.time_window_combo = QComboBox()
        self.time_window_combo.addItems(["10s", "30s", "1m", "5m", "10m", "All"])
        self.time_window_combo.setCurrentText("30s")
        control_layout.addWidget(self.time_window_combo)
        
        layout.addWidget(control_group)
        
        # Signal selection button
        signal_controls = QHBoxLayout()
        
        self.select_signals_btn = QPushButton("Select Signals to Plot")
        self.select_signals_btn.clicked.connect(self.open_signal_selection)
        self.select_signals_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 8px;")
        signal_controls.addWidget(self.select_signals_btn)
        
        self.selected_signals_label = QLabel("No signals selected")
        self.selected_signals_label.setStyleSheet("color: gray; font-style: italic;")
        signal_controls.addWidget(self.selected_signals_label)
        
        signal_controls.addStretch()
        
        # Plot configuration controls
        self.auto_scale_cb = QCheckBox("Auto-scale")
        self.auto_scale_cb.setChecked(True)
        signal_controls.addWidget(self.auto_scale_cb)
        
        self.show_grid_cb = QCheckBox("Grid")
        self.show_grid_cb.setChecked(True)
        self.show_grid_cb.toggled.connect(self.toggle_grid)
        signal_controls.addWidget(self.show_grid_cb)
        
        self.show_legend_cb = QCheckBox("Legend")
        self.show_legend_cb.setChecked(True)
        self.show_legend_cb.toggled.connect(self.toggle_legend)
        signal_controls.addWidget(self.show_legend_cb)
        
        layout.addLayout(signal_controls)
        
        # Plot area - full width
        plot_layout = QVBoxLayout()
        
        # Create plot widget - full width
        self.plot_widget = pg.PlotWidget(title="CAN Signal Plotter")
        self.plot_widget.setBackground('w')  # White background
        self.plot_widget.setLabel('left', 'Signal Value')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        
        # Enable mouse interaction
        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.enableAutoRange(axis='y')
        
        plot_layout.addWidget(self.plot_widget)
        
        # Plot statistics and export controls
        stats_layout = QHBoxLayout()
        self.plot_stats_label = QLabel("Signals: 0 | Points: 0 | Recording: Stopped")
        stats_layout.addWidget(self.plot_stats_label)
        stats_layout.addStretch()
        
        # Export controls
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.clicked.connect(self.export_csv)
        stats_layout.addWidget(self.export_csv_btn)
        
        self.export_image_btn = QPushButton("Export Image")
        self.export_image_btn.clicked.connect(self.export_image)
        stats_layout.addWidget(self.export_image_btn)
        
        plot_layout.addLayout(stats_layout)
        
        layout.addLayout(plot_layout)
        
    def setup_connections(self):
        """Set up signal connections"""
        # Connect to CAN manager for real-time data
        self.can_manager.message_received.connect(self.on_message_received, Qt.ConnectionType.QueuedConnection)
        
    def set_sym_parser(self, parser: SymParser):
        """Set SYM parser for signal definitions"""
        self.sym_parser = parser
        
        if parser:
            self.sym_status_label.setText(f"Loaded: {len(parser.messages)} messages")
            self.sym_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.sym_status_label.setText("No SYM file loaded")
            self.sym_status_label.setStyleSheet("color: gray; font-style: italic;")
            
    def load_sym_file(self):
        """Load SYM file for plotting"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load SYM File", "", "SYM Files (*.sym);;All Files (*)"
        )
        
        if filename:
            try:
                parser = SymParser()
                success = parser.parse_file(filename)
                
                if success:
                    self.set_sym_parser(parser)
                    
                    # Notify main window
                    main_window = self.window()
                    if hasattr(main_window, 'symbols_tab'):
                        main_window.symbols_tab.sym_parser = parser
                        main_window.symbols_tab.sym_parser_changed.emit(parser)
                    
                    QMessageBox.information(self, "Success", 
                                          f"Loaded SYM file with {len(parser.messages)} messages")
                else:
                    QMessageBox.critical(self, "Error", "Failed to parse SYM file")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load SYM file: {str(e)}")
                
    def open_signal_selection(self):
        """Open signal selection dialog"""
        if not self.sym_parser:
            QMessageBox.warning(self, "Warning", "Please load a SYM file first")
            return
            
        dialog = SignalSelectionDialog(self)
        dialog.load_signals(self.sym_parser)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_signals = dialog.get_selected_signals()
            
            # Clear current signals
            self.clear_plots()
            
            # Add selected signals
            for message_name, signal_name in selected_signals:
                self.on_signal_toggled(message_name, signal_name, True)
                
            # Update label
            if selected_signals:
                signal_names = [f"{msg}.{sig}" for msg, sig in selected_signals]
                if len(signal_names) <= 3:
                    label_text = ", ".join(signal_names)
                else:
                    label_text = f"{', '.join(signal_names[:3])} and {len(signal_names)-3} more"
                self.selected_signals_label.setText(label_text)
                self.selected_signals_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.selected_signals_label.setText("No signals selected")
                self.selected_signals_label.setStyleSheet("color: gray; font-style: italic;")
                
    @pyqtSlot(str, str, bool)
    def on_signal_toggled(self, message_name: str, signal_name: str, enabled: bool):
        """Handle signal selection toggle"""
        signal_key = f"{message_name}.{signal_name}"
        
        if enabled:
            # Add signal to plotting
            if signal_key not in self.signals:
                color = self.plot_colors[self.color_index % len(self.plot_colors)]
                self.color_index += 1
                
                signal_data = SignalData(message_name, signal_name, 0, color)
                
                # Find CAN ID for this message
                if self.sym_parser and message_name in self.sym_parser.messages:
                    signal_data.can_id = self.sym_parser.messages[message_name].can_id
                
                self.signals[signal_key] = signal_data
                
                # Create plot curve
                pen = pg.mkPen(color=color, width=2)
                signal_data.plot_item = self.plot_widget.plot(
                    [], [], pen=pen, name=f"{message_name}.{signal_name}"
                )
                
                # If we have trace data loaded, plot it immediately
                if self.is_trace_mode and self.trace_messages:
                    self.plot_signal_from_trace(signal_data)
                
                print(f"Added signal for plotting: {signal_key}")
        else:
            # Remove signal from plotting
            if signal_key in self.signals:
                signal_data = self.signals[signal_key]
                if signal_data.plot_item:
                    self.plot_widget.removeItem(signal_data.plot_item)
                del self.signals[signal_key]
                print(f"Removed signal from plotting: {signal_key}")
                
        self.update_stats()
        
    @pyqtSlot(object)
    def on_message_received(self, msg: CANMessage):
        """Handle received CAN message for plotting"""
        if not self.is_recording or not self.sym_parser:
            return
            
        # Find signals to update for this message
        for signal_key, signal_data in self.signals.items():
            if signal_data.can_id == msg.arbitration_id:
                # Decode the signal value
                value = self.decode_signal_value(msg, signal_data.message_name, signal_data.signal_name)
                if value is not None:
                    # Calculate relative time
                    if self.start_time is None:
                        self.start_time = msg.timestamp
                    relative_time = msg.timestamp - self.start_time
                    
                    signal_data.add_point(relative_time, value)
                    
    def decode_signal_value(self, msg: CANMessage, message_name: str, signal_name: str) -> Optional[float]:
        """Decode a specific signal value from a CAN message"""
        if not self.sym_parser or message_name not in self.sym_parser.messages:
            return None
            
        message_def = self.sym_parser.messages[message_name]
        
        # Find the signal variable
        for variable in message_def.variables:
            if variable.name == signal_name:
                if variable.start_bit + variable.bit_length <= len(msg.data) * 8:
                    # Extract bits
                    start_byte = variable.start_bit // 8
                    end_byte = (variable.start_bit + variable.bit_length - 1) // 8 + 1
                    
                    if end_byte <= len(msg.data):
                        raw_bytes = msg.data[start_byte:end_byte]
                        raw_value = int.from_bytes(raw_bytes, byteorder='little')
                        
                        # Apply bit masking
                        if variable.start_bit % 8 != 0 or variable.bit_length % 8 != 0:
                            bit_offset = variable.start_bit % 8
                            mask = (1 << variable.bit_length) - 1
                            raw_value = (raw_value >> bit_offset) & mask
                        
                        # Apply scaling
                        scaled_value = raw_value * variable.factor + variable.offset
                        return float(scaled_value)
                        
        return None
        
    def update_plots(self):
        """Update all plot curves with latest data"""
        if not self.is_recording:
            return
            
        for signal_data in self.signals.values():
            if signal_data.plot_item and signal_data.times:
                times, values = signal_data.get_data_arrays()
                signal_data.plot_item.setData(times, values)
                
        self.update_stats()
        
    def update_stats(self):
        """Update plotting statistics"""
        signal_count = len(self.signals)
        total_points = sum(len(signal.times) for signal in self.signals.values())
        status = "Recording" if self.is_recording else "Stopped"
        
        self.plot_stats_label.setText(f"Signals: {signal_count} | Points: {total_points} | Recording: {status}")
        
    def start_recording(self):
        """Start recording and plotting signals"""
        if not self.signals:
            QMessageBox.warning(self, "Warning", "No signals selected for plotting")
            return
            
        self.is_recording = True
        self.start_time = None  # Will be set on first message
        
        self.start_recording_btn.setEnabled(False)
        self.stop_recording_btn.setEnabled(True)
        
        print("Started signal recording for plotting")
        
    def stop_recording(self):
        """Stop recording signals"""
        self.is_recording = False
        
        self.start_recording_btn.setEnabled(True)
        self.stop_recording_btn.setEnabled(False)
        
        print("Stopped signal recording")
        
    def clear_plots(self):
        """Clear all plot data"""
        for signal_data in self.signals.values():
            signal_data.clear_data()
            if signal_data.plot_item:
                signal_data.plot_item.setData([], [])
                
        self.start_time = None
        self.is_trace_mode = False
        self.trace_messages = []
        
        # Reset status if it was showing trace info
        if "Trace loaded" in self.sym_status_label.text():
            self.sym_status_label.setText("No SYM file loaded")
            self.sym_status_label.setStyleSheet("color: gray; font-style: italic;")
            
        print("Cleared all plot data")
        
    def toggle_grid(self, enabled: bool):
        """Toggle plot grid display"""
        self.plot_widget.showGrid(x=enabled, y=enabled)
        
    def toggle_legend(self, enabled: bool):
        """Toggle plot legend display"""
        if enabled:
            if not hasattr(self.plot_widget, 'legend') or self.plot_widget.legend is None:
                self.plot_widget.addLegend()
        else:
            if hasattr(self.plot_widget, 'legend') and self.plot_widget.legend:
                self.plot_widget.legend.scene().removeItem(self.plot_widget.legend)
                self.plot_widget.legend = None
                
    def export_csv(self):
        """Export plot data to CSV"""
        if not self.signals:
            QMessageBox.warning(self, "Warning", "No data to export")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Plot Data", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if filename:
            try:
                import csv
                
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    
                    # Write header
                    header = ['Time']
                    for signal_key in self.signals.keys():
                        header.append(signal_key)
                    writer.writerow(header)
                    
                    # Find all unique timestamps
                    all_times = set()
                    for signal_data in self.signals.values():
                        all_times.update(signal_data.times)
                    
                    # Write data rows
                    for timestamp in sorted(all_times):
                        row = [timestamp]
                        for signal_data in self.signals.values():
                            # Find closest value for this timestamp
                            if timestamp in signal_data.times:
                                idx = list(signal_data.times).index(timestamp)
                                row.append(signal_data.values[idx])
                            else:
                                row.append('')  # No data at this timestamp
                        writer.writerow(row)
                        
                QMessageBox.information(self, "Success", f"Exported plot data to {filename}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export CSV: {str(e)}")
                
    def export_image(self):
        """Export plot as image"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Plot Image", "", 
            "PNG Files (*.png);;JPEG Files (*.jpg);;BMP Files (*.bmp);;All Files (*)"
        )
        
        if filename:
            try:
                # Export plot as image
                exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
                exporter.export(filename)
                
                QMessageBox.information(self, "Success", f"Exported plot image to {filename}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export image: {str(e)}")
                
    def load_trace_file(self):
        """Load trace file for plotting analysis"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Trace File", "", 
            "All Supported (*.csv *.json *.asc *.trc);;TRC Files (*.trc);;CSV Files (*.csv);;JSON Files (*.json);;ASC Files (*.asc);;All Files (*)"
        )
        
        if filename:
            try:
                # Import the LogReader from logging tab
                from gui.logging_tab import LogReader
                
                # Clear current data
                self.clear_plots()
                self.trace_messages = []
                
                # Create log reader
                log_reader = LogReader(filename)
                
                # Connect signals
                def on_message_loaded(msg):
                    self.trace_messages.append(msg)
                    
                def on_load_finished(count):
                    self.on_trace_file_loaded(count)
                    
                def on_load_error(error):
                    QMessageBox.critical(self, "Error", f"Failed to load trace file: {error}")
                
                log_reader.message_loaded.connect(on_message_loaded)
                log_reader.finished.connect(on_load_finished)
                log_reader.error_occurred.connect(on_load_error)
                
                # Update status
                self.sym_status_label.setText("Loading trace file...")
                
                # Start loading
                log_reader.run()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load trace file: {str(e)}")
                
    def on_trace_file_loaded(self, message_count):
        """Handle trace file loading completion"""
        self.is_trace_mode = True
        
        # Update status
        self.sym_status_label.setText(f"Trace loaded: {message_count} messages")
        self.sym_status_label.setStyleSheet("color: blue; font-weight: bold;")
        
        # Process all messages to populate selected signals
        if self.signals and self.trace_messages:
            self.plot_trace_data()
            
        QMessageBox.information(self, "Success", 
                              f"Loaded trace file with {message_count} messages\\nSelect signals and they will be plotted automatically")
                              
    def plot_trace_data(self):
        """Plot data from loaded trace file"""
        if not self.trace_messages or not self.signals:
            return
            
        print(f"Plotting {len(self.trace_messages)} messages from trace file...")
        
        # Find the start time
        if self.trace_messages:
            self.start_time = min(msg.timestamp for msg in self.trace_messages)
        
        # Process each message in the trace
        for msg in self.trace_messages:
            # Find signals to update for this message
            for signal_key, signal_data in self.signals.items():
                if signal_data.can_id == msg.arbitration_id:
                    # Decode the signal value
                    value = self.decode_signal_value(msg, signal_data.message_name, signal_data.signal_name)
                    if value is not None:
                        # Calculate relative time
                        relative_time = msg.timestamp - self.start_time
                        signal_data.add_point(relative_time, value)
        
        # Update all plots with trace data
        for signal_data in self.signals.values():
            if signal_data.plot_item and signal_data.times:
                times, values = signal_data.get_data_arrays()
                signal_data.plot_item.setData(times, values)
                
        self.update_stats()
        print(f"✅ Plotted trace data for {len(self.signals)} signals")
        
    def plot_signal_from_trace(self, signal_data: SignalData):
        """Plot a specific signal from loaded trace data"""
        if not self.trace_messages:
            return
            
        # Clear existing data for this signal
        signal_data.clear_data()
        
        # Find the start time if not set
        if self.start_time is None and self.trace_messages:
            self.start_time = min(msg.timestamp for msg in self.trace_messages)
        
        # Process trace messages for this specific signal
        for msg in self.trace_messages:
            if signal_data.can_id == msg.arbitration_id:
                # Decode the signal value
                value = self.decode_signal_value(msg, signal_data.message_name, signal_data.signal_name)
                if value is not None:
                    # Calculate relative time
                    relative_time = msg.timestamp - self.start_time
                    signal_data.add_point(relative_time, value)
        
        # Update the plot
        if signal_data.plot_item and signal_data.times:
            times, values = signal_data.get_data_arrays()
            signal_data.plot_item.setData(times, values)
            
        print(f"Plotted {len(signal_data.times)} points for {signal_data.message_name}.{signal_data.signal_name}")
