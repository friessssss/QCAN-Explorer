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
from PyQt6.QtGui import QFont, QColor, QPixmap

# Network manager will be passed in constructor
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
        self.selection_label.setStyleSheet("font-weight: bold; color: #666666;")
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

    def load_signals_from_networks(self, network_parsers: List[tuple]):
        """Load signals from multiple network parsers"""
        self.signal_tree.clear()
        
        if not network_parsers:
            return
            
        # Add signals from each network's parser
        for bus_number, sym_parser in network_parsers:
            if not sym_parser or not sym_parser.messages:
                continue
                
            # Add signals from each message
            for msg_name, message in sym_parser.messages.items():
                for variable in message.variables:
                    item = QTreeWidgetItem(self.signal_tree)
                    # Show full signal name with bus information
                    signal_display_name = f"Bus{bus_number}.{msg_name}.{variable.name}"
                    item.setText(0, signal_display_name)
                    item.setText(1, msg_name)  # Message name
                    item.setText(2, variable.unit or "")  # Unit
                    item.setText(3, getattr(variable, 'comment', '') or "")  # Description
                    
                    # Store message name, signal name, bus number, and CAN ID for internal use
                    item.setData(0, Qt.ItemDataRole.UserRole, (msg_name, variable.name, bus_number, message.can_id))
                
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
        """Get list of selected signals with bus information"""
        selected = []
        for item in self.signal_tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                if len(data) >= 4:
                    msg_name, signal_name, bus_number, can_id = data
                    selected.append((msg_name, signal_name, bus_number, can_id))
                else:
                    # Fallback for old format
                    msg_name, signal_name = data[:2]
                    selected.append((msg_name, signal_name, 0, 0))
        return selected


class SignalData:
    """Container for signal plotting data with professional analysis features"""
    
    def __init__(self, message_name: str, signal_name: str, can_id: int, color: str, bus_number: int = 0, max_points: int = 10000):
        self.message_name = message_name
        self.signal_name = signal_name
        self.can_id = can_id
        self.bus_number = bus_number
        self.color = color
        self.times = deque(maxlen=max_points)  # Configurable buffer size
        self.values = deque(maxlen=max_points)
        self.enabled = True
        self.y_axis = 'left'  # 'left' or 'right' for multiple axes
        self.plot_item = None  # pyqtgraph plot item
        
        # Statistics tracking
        self.min_value = float('inf')
        self.max_value = float('-inf')
        self.sum_values = 0.0
        self.sum_squares = 0.0
        self.point_count = 0
        
        # Message rate tracking
        self.last_message_time = None
        self.message_intervals = deque(maxlen=10)  # Track last 10 intervals for rate calculation
        
    def add_point(self, timestamp: float, value: float):
        """Add a new data point with statistics and rate tracking"""
        self.times.append(timestamp)
        self.values.append(value)
        
        # Update statistics
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        self.sum_values += value
        self.sum_squares += value * value
        self.point_count += 1
        
        # Track message rate
        if self.last_message_time is not None:
            interval = timestamp - self.last_message_time
            if interval > 0:  # Avoid division by zero
                self.message_intervals.append(interval)
        self.last_message_time = timestamp
        
    def get_statistics(self) -> Dict[str, float]:
        """Get signal statistics including message rate"""
        if self.point_count == 0:
            return {'current': 0, 'min': 0, 'max': 0, 'avg': 0, 'rms': 0, 'rate': 0}
            
        current = list(self.values)[-1] if self.values else 0
        avg = self.sum_values / self.point_count
        rms = (self.sum_squares / self.point_count) ** 0.5
        
        # Calculate message rate from intervals
        rate = 0
        if self.message_intervals:
            avg_interval = sum(self.message_intervals) / len(self.message_intervals)
            rate = 1.0 / avg_interval if avg_interval > 0 else 0
        
        return {
            'current': current,
            'min': self.min_value,
            'max': self.max_value,
            'avg': avg,
            'rms': rms,
            'rate': rate
        }
        
    def get_data_arrays(self):
        """Get data as arrays for plotting"""
        return list(self.times), list(self.values)
        
    def clear_data(self):
        """Clear all data points and reset statistics"""
        self.times.clear()
        self.values.clear()
        
        # Reset statistics
        self.min_value = float('inf')
        self.max_value = float('-inf')
        self.sum_values = 0.0
        self.sum_squares = 0.0
        self.point_count = 0


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
        


class PlottingTab(QWidget):
    """Real-time signal plotting and analysis tab"""
    
    def __init__(self, network_manager):
        super().__init__()
        self.network_manager = network_manager
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
        
        # Performance optimization - throttled updates
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_plots_throttled)
        self.plot_timer.start(33)  # ~30 FPS for smooth rendering
        
        # Data update tracking for performance
        self.data_updated = False
        self.pending_updates = set()  # Track which signals need updates
        
        # Performance settings
        self.max_plot_points = 10000  # Configurable buffer size
        self.update_batch_size = 100  # Batch updates for performance
        
        # Initialize features
        self.plot_frozen = False
        self.trigger_mode = "Free Run"
        
        # Load available presets on startup
        self.load_available_presets()
        
    def setup_ui(self):
        """Set up the plotting tab UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Reasonable margins
        
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
        self.load_trace_btn = QPushButton("Load Trace File")
        self.load_trace_btn.clicked.connect(self.load_trace_file)
        control_layout.addWidget(self.load_trace_btn)
        
        self.sym_status_label = QLabel("Using network-assigned symbol files")
        self.sym_status_label.setStyleSheet("color: #666666; font-style: italic;")
        control_layout.addWidget(self.sym_status_label)
        
        control_layout.addStretch()
        
        # Professional time axis controls
        control_layout.addWidget(QLabel("Time Window:"))
        self.time_window_combo = QComboBox()
        self.time_window_combo.addItems(["5s", "10s", "30s", "1m", "5m", "10m", "30m", "1h", "All"])
        self.time_window_combo.setCurrentText("30s")
        self.time_window_combo.currentTextChanged.connect(self.on_time_window_changed)
        control_layout.addWidget(self.time_window_combo)
        
        control_layout.addWidget(QLabel("|"))  # Separator
        
        # Buffer size control
        control_layout.addWidget(QLabel("Buffer Size:"))
        self.buffer_size_combo = QComboBox()
        self.buffer_size_combo.addItems(["1K", "5K", "10K", "50K", "100K", "500K", "1M"])
        self.buffer_size_combo.setCurrentText("10K")
        self.buffer_size_combo.currentTextChanged.connect(self.on_buffer_size_changed)
        control_layout.addWidget(self.buffer_size_combo)
        
        control_layout.addWidget(QLabel("|"))  # Separator
        
        # Update rate control
        control_layout.addWidget(QLabel("Update Rate:"))
        self.update_rate_combo = QComboBox()
        self.update_rate_combo.addItems(["15 FPS", "30 FPS", "60 FPS", "120 FPS"])
        self.update_rate_combo.setCurrentText("30 FPS")
        self.update_rate_combo.currentTextChanged.connect(self.on_update_rate_changed)
        control_layout.addWidget(self.update_rate_combo)
        
        layout.addWidget(control_group)
        
        # Essential analysis tools
        tools_group = QGroupBox("Analysis Tools")
        tools_layout = QHBoxLayout(tools_group)
        
        # Essential analysis tools
        self.auto_scale_btn = QPushButton("Auto Scale Y")
        self.auto_scale_btn.clicked.connect(self.auto_scale_y_axes)
        tools_layout.addWidget(self.auto_scale_btn)
        
        self.freeze_plot_btn = QPushButton("Freeze")
        self.freeze_plot_btn.clicked.connect(self.toggle_freeze)
        tools_layout.addWidget(self.freeze_plot_btn)
        
        self.clear_data_btn = QPushButton("Clear Data")
        self.clear_data_btn.clicked.connect(self.clear_all_data)
        tools_layout.addWidget(self.clear_data_btn)
        
        tools_layout.addWidget(QLabel("|"))  # Separator
        
        # Measurement cursor controls
        self.toggle_cursors_btn = QPushButton("Show Cursors")
        self.toggle_cursors_btn.clicked.connect(lambda: self.toggle_cursors(not self.cursors_visible))
        tools_layout.addWidget(self.toggle_cursors_btn)
        
        self.reset_cursors_btn = QPushButton("Reset Cursors")
        self.reset_cursors_btn.clicked.connect(self.reset_cursors)
        tools_layout.addWidget(self.reset_cursors_btn)
        
        tools_layout.addStretch()
        
        # Compact measurement display
        self.measurement_label = QLabel("Cursors: T1=---, T2=---, ΔT=---, V1=---")
        self.measurement_label.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 11px; font-weight: bold; "
            "background-color: #f0f0f0; color: #2c3e50; padding: 4px; border-radius: 3px; "
            "border: 1px solid #bdc3c7;"
        )
        tools_layout.addWidget(self.measurement_label)
        
        tools_layout.addWidget(QLabel("|"))  # Separator
        
        # Performance indicator
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("font-family: monospace; color: #666666;")
        tools_layout.addWidget(self.fps_label)
        
        layout.addWidget(tools_group)
        
        # Signal selection button
        signal_controls = QHBoxLayout()
        
        self.select_signals_btn = QPushButton("Select Signals to Plot")
        self.select_signals_btn.clicked.connect(self.open_signal_selection)
        self.select_signals_btn.setStyleSheet("background-color: #777777; color: white; font-weight: bold; padding: 8px;")
        signal_controls.addWidget(self.select_signals_btn)
        
        self.manage_signals_btn = QPushButton("Manage Active Signals")
        self.manage_signals_btn.clicked.connect(self.open_signal_management)
        self.manage_signals_btn.setEnabled(False)  # Enabled when signals are selected
        signal_controls.addWidget(self.manage_signals_btn)
        
        # Signal presets
        signal_controls.addWidget(QLabel("|"))
        self.save_preset_btn = QPushButton("Save Preset")
        self.save_preset_btn.clicked.connect(self.save_signal_preset)
        self.save_preset_btn.setEnabled(False)
        signal_controls.addWidget(self.save_preset_btn)
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Load Preset...")
        self.preset_combo.currentTextChanged.connect(self.load_signal_preset)
        signal_controls.addWidget(self.preset_combo)
        
        # Quick export presets
        signal_controls.addWidget(QLabel("|"))
        self.export_report_btn = QPushButton("Export Report")
        self.export_report_btn.clicked.connect(self.export_report)
        self.export_report_btn.setToolTip("Export PNG + CSV for engineering reports")
        signal_controls.addWidget(self.export_report_btn)
        
        self.export_presentation_btn = QPushButton("Export Presentation")
        self.export_presentation_btn.clicked.connect(self.export_presentation)
        self.export_presentation_btn.setToolTip("Export high-resolution PNG for presentations")
        signal_controls.addWidget(self.export_presentation_btn)
        
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
        
        # Create plot widget with proper size constraints
        self.plot_widget = pg.PlotWidget(title="CAN Signal Plotter - Professional Analysis")
        self.plot_widget.setBackground('w')  # White background
        self.plot_widget.setLabel('left', 'Signal Value')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        
        # Set size policy to prevent excessive expansion
        from PyQt6.QtWidgets import QSizePolicy
        self.plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.plot_widget.setMinimumSize(400, 300)  # Minimum reasonable size
        
        # Enable mouse interaction
        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.enableAutoRange(axis='y')
        
        # Add measurement cursors for professional analysis
        self.setup_measurement_cursors()
        
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
        
        # Add signal statistics panel
        self.setup_statistics_panel(layout)
        
    def setup_measurement_cursors(self):
        """Set up interactive measurement cursors"""
        try:
            # Vertical cursor (time measurement) - red dashed line
            self.v_cursor = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen('red', width=2))
            self.plot_widget.addItem(self.v_cursor)
            
            # Second vertical cursor for delta measurements - blue dashed line
            self.v_cursor2 = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen('blue', width=2))
            self.plot_widget.addItem(self.v_cursor2)
            
            # Horizontal cursor (value measurement) - green dashed line
            self.h_cursor = pg.InfiniteLine(angle=0, movable=True, pen=pg.mkPen('green', width=2))
            self.plot_widget.addItem(self.h_cursor)
            
            # Connect cursor movement to measurement updates
            self.v_cursor.sigPositionChanged.connect(self.update_measurements)
            self.v_cursor2.sigPositionChanged.connect(self.update_measurements)
            self.h_cursor.sigPositionChanged.connect(self.update_measurements)
            
            # Initially hide cursors
            self.cursors_visible = False
            self.toggle_cursors(False)
            
        except Exception as e:
            print(f"Warning: Could not set up measurement cursors: {e}")
            # Create dummy cursors for compatibility
            self.cursors_visible = False
        
        
    def setup_statistics_panel(self, parent_layout):
        """Set up real-time signal statistics panel"""
        stats_group = QGroupBox("Signal Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        # Enhanced signal statistics table with message rate monitoring
        self.stats_table = QTableWidget(0, 7)
        self.stats_table.setHorizontalHeaderLabels(["Signal", "Current", "Min", "Max", "Avg", "RMS", "Rate (Hz)"])
        self.stats_table.setMaximumHeight(150)
        self.stats_table.setAlternatingRowColors(True)
        
        # Configure stats table with size constraints
        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            
        # Set size policy to prevent expansion issues
        from PyQt6.QtWidgets import QSizePolicy
        self.stats_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        stats_layout.addWidget(self.stats_table)
        
        parent_layout.addWidget(stats_group)
        
    def setup_connections(self):
        """Set up signal connections"""
        # Connect to CAN manager for real-time data
        self.network_manager.message_received.connect(self.on_message_received, Qt.ConnectionType.QueuedConnection)
        
        # Update symbol status when networks change
        self.network_manager.network_state_changed.connect(self.update_symbol_status, Qt.ConnectionType.QueuedConnection)
        
        # Initial symbol status update
        self.update_symbol_status()
        
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
                
    def open_signal_selection(self):
        """Open signal selection dialog"""
        # Get all available symbol parsers from networks
        networks = self.network_manager.get_all_networks()
        available_parsers = []
        
        for network in networks.values():
            parser = network.get_symbol_parser()
            if parser and parser.messages:
                available_parsers.append((network.config.bus_number, parser))
        
        if not available_parsers:
            QMessageBox.warning(self, "Warning", "No symbol files assigned to any network")
            return
            
        dialog = SignalSelectionDialog(self)
        # Load signals from all available parsers
        dialog.load_signals_from_networks(available_parsers)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_signals = dialog.get_selected_signals()
            
            # Clear current signals
            self.clear_plots()
            
            # Add selected signals with bus information
            for signal_info in selected_signals:
                if len(signal_info) >= 4:
                    message_name, signal_name, bus_number, can_id = signal_info
                    self.on_signal_toggled_with_bus(message_name, signal_name, bus_number, can_id, True)
                else:
                    # Fallback for old format
                    message_name, signal_name = signal_info[:2]
                    self.on_signal_toggled(message_name, signal_name, True)
                
            # Update label
            if selected_signals:
                signal_names = []
                for signal_info in selected_signals:
                    if len(signal_info) >= 4:
                        msg, sig, bus, _ = signal_info
                        signal_names.append(f"Bus{bus}.{msg}.{sig}")
                    else:
                        msg, sig = signal_info[:2]
                        signal_names.append(f"{msg}.{sig}")
                
                if len(signal_names) <= 3:
                    label_text = ", ".join(signal_names)
                else:
                    label_text = f"{', '.join(signal_names[:3])} and {len(signal_names)-3} more"
                self.selected_signals_label.setText(label_text)
                self.selected_signals_label.setStyleSheet("color: #666666; font-weight: bold;")
            else:
                self.selected_signals_label.setText("No signals selected")
                self.selected_signals_label.setStyleSheet("color: gray; font-style: italic;")
                
            # Update button states and trigger signal combo
            self.update_button_states()
                
    def on_signal_toggled_with_bus(self, message_name: str, signal_name: str, bus_number: int, can_id: int, enabled: bool):
        """Handle signal selection toggle with bus information"""
        signal_key = f"Bus{bus_number}.{message_name}.{signal_name}"
        
        print(f"🔄 Signal toggle: {signal_key}, enabled: {enabled}, trace_mode: {self.is_trace_mode}")
        
        if enabled and signal_key not in self.signals:
            # Create new signal
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
            color = colors[len(self.signals) % len(colors)]
            
            signal_data = SignalData(message_name, signal_name, can_id, color, bus_number, self.max_plot_points)
            self.signals[signal_key] = signal_data
            
            print(f"📊 Created signal data: {signal_key} with CAN ID 0x{can_id:X}")
            
            # Add to plot if in real-time mode
            if not self.is_trace_mode:
                self.add_signal_to_plot(signal_data)
            else:
                # If in trace mode, plot the signal from loaded data
                self.plot_signal_from_trace(signal_data)
                
        elif not enabled and signal_key in self.signals:
            # Remove signal
            signal_data = self.signals[signal_key]
            if signal_data.plot_item:
                self.plot_widget.removeItem(signal_data.plot_item)
            del self.signals[signal_key]
            print(f"🗑️ Removed signal: {signal_key}")
            
        self.update_stats()

    @pyqtSlot(str, str, bool)
    def on_signal_toggled(self, message_name: str, signal_name: str, enabled: bool):
        """Handle signal selection toggle (legacy method)"""
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
        
    @pyqtSlot(str, object)
    def on_message_received(self, network_id: str, msg: CANMessage):
        """Handle received CAN message for plotting - optimized for performance"""
        if not self.is_recording:
            return
            
        # Find signals to update for this message (match both CAN ID and bus number)
        for signal_key, signal_data in self.signals.items():
            if signal_data.can_id == msg.arbitration_id and signal_data.bus_number == msg.bus_number:
                # Decode the signal value
                value = self.decode_signal_value(msg, signal_data.message_name, signal_data.signal_name)
                if value is not None:
                    # Calculate relative time
                    if self.start_time is None:
                        self.start_time = msg.timestamp
                    relative_time = msg.timestamp - self.start_time
                    
                    # Add data point
                    signal_data.add_point(relative_time, value)
                    
                    # Mark for throttled update (don't update plot immediately)
                    self.pending_updates.add(signal_key)
                    self.data_updated = True
                    
    def decode_signal_value(self, msg: CANMessage, message_name: str, signal_name: str) -> Optional[float]:
        """Decode a specific signal value from a CAN message using network-assigned symbol parser"""
        # Get symbol parser for this message's bus
        network = self.network_manager.get_network_by_bus_number(msg.bus_number)
        if not network:
            return None
            
        sym_parser = network.get_symbol_parser()
        if not sym_parser or not sym_parser.messages or message_name not in sym_parser.messages:
            return None
            
        message_def = sym_parser.messages[message_name]
        
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
        
    def update_plots_throttled(self):
        """Throttled plot update for smooth real-time performance"""
        # Check if plot is frozen
        if hasattr(self, 'plot_frozen') and self.plot_frozen:
            return
            
        if not self.data_updated or not self.pending_updates:
            return
            
        # Track FPS for performance monitoring
        current_time = time.time()
        if hasattr(self, 'last_update_time'):
            fps = 1.0 / (current_time - self.last_update_time)
            self.fps_label.setText(f"FPS: {fps:.1f}")
        self.last_update_time = current_time
            
        # Update only signals that have new data
        for signal_key in self.pending_updates:
            if signal_key in self.signals:
                signal_data = self.signals[signal_key]
                if signal_data.plot_item and signal_data.times:
                    times, values = signal_data.get_data_arrays()
                    signal_data.plot_item.setData(times, values)
        
        # Clear update flags
        self.data_updated = False
        self.pending_updates.clear()
        
        # Update statistics
        self.update_signal_statistics()
        
        # Apply time window if set
        self.apply_time_window()
        
    def apply_time_window(self):
        """Apply current time window setting to plot view"""
        window_text = self.time_window_combo.currentText()
        if window_text == "All" or not self.signals:
            return
            
        # Parse time window
        if window_text.endswith('s'):
            seconds = float(window_text[:-1])
        elif window_text.endswith('m'):
            seconds = float(window_text[:-1]) * 60
        elif window_text.endswith('h'):
            seconds = float(window_text[:-1]) * 3600
        else:
            return
            
        # Get latest time from all signals
        latest_times = []
        for signal_data in self.signals.values():
            if signal_data.times:
                latest_times.append(max(signal_data.times))
                
        if latest_times:
            max_time = max(latest_times)
            self.plot_widget.setXRange(max_time - seconds, max_time)
        
    def toggle_cursors(self, visible: bool):
        """Toggle measurement cursors visibility"""
        self.cursors_visible = visible
        
        # Safely toggle cursor visibility
        try:
            if hasattr(self, 'v_cursor') and self.v_cursor:
                self.v_cursor.setVisible(visible)
            if hasattr(self, 'v_cursor2') and self.v_cursor2:
                self.v_cursor2.setVisible(visible)
            if hasattr(self, 'h_cursor') and self.h_cursor:
                self.h_cursor.setVisible(visible)
        except Exception as e:
            print(f"Warning: Could not toggle cursors: {e}")
        
        self.toggle_cursors_btn.setText("Hide Cursors" if visible else "Show Cursors")
        
        if visible:
            self.update_measurements()
        
    def reset_cursors(self):
        """Reset cursors to default positions"""
        if self.signals:
            # Get time range
            all_times = []
            for signal_data in self.signals.values():
                if signal_data.times:
                    all_times.extend(signal_data.times)
            
            if all_times:
                min_time, max_time = min(all_times), max(all_times)
                quarter_time = min_time + (max_time - min_time) * 0.25
                three_quarter_time = min_time + (max_time - min_time) * 0.75
                
                self.v_cursor.setPos(quarter_time)
                self.v_cursor2.setPos(three_quarter_time)
                
                # Set horizontal cursor to middle of first signal's range
                first_signal = next(iter(self.signals.values()))
                if first_signal.values:
                    mid_value = (min(first_signal.values) + max(first_signal.values)) / 2
                    self.h_cursor.setPos(mid_value)
        
    def update_measurements(self):
        """Update compact measurement display based on cursor positions"""
        if not self.cursors_visible:
            # Show inactive state
            self.measurement_label.setText("Cursors: T1=---, T2=---, ΔT=---, V1=---")
            return
            
        try:
            t1 = self.v_cursor.value() if hasattr(self, 'v_cursor') and self.v_cursor else 0
            t2 = self.v_cursor2.value() if hasattr(self, 'v_cursor2') and self.v_cursor2 else 0
            v1 = self.h_cursor.value() if hasattr(self, 'h_cursor') and self.h_cursor else 0
            dt = abs(t2 - t1)
            
            freq = 1.0 / dt if dt > 0 else 0
            
            # Compact single-line format
            measurement_text = f"Cursors: T1={t1:.3f}s, T2={t2:.3f}s, ΔT={dt:.3f}s ({freq:.1f}Hz), V1={v1:.3f}"
            self.measurement_label.setText(measurement_text)
            
        except Exception as e:
            self.measurement_label.setText("Cursors: Error reading positions")
        
        
    def update_signal_statistics(self):
        """Update real-time signal statistics table using efficient built-in stats"""
        if not self.signals:
            self.stats_table.setRowCount(0)
            return
            
        self.stats_table.setRowCount(len(self.signals))
        
        for row, (signal_key, signal_data) in enumerate(self.signals.items()):
            # Use built-in statistics from SignalData
            stats = signal_data.get_statistics()
            
            # Update table with professional formatting
            self.stats_table.setItem(row, 0, QTableWidgetItem(signal_key))
            
            # Signal statistics
            self.stats_table.setItem(row, 1, QTableWidgetItem(f"{stats['current']:.3f}"))
            self.stats_table.setItem(row, 2, QTableWidgetItem(f"{stats['min']:.3f}"))
            self.stats_table.setItem(row, 3, QTableWidgetItem(f"{stats['max']:.3f}"))
            self.stats_table.setItem(row, 4, QTableWidgetItem(f"{stats['avg']:.3f}"))
            self.stats_table.setItem(row, 5, QTableWidgetItem(f"{stats['rms']:.3f}"))
            
            # Message rate
            rate_item = QTableWidgetItem(f"{stats['rate']:.1f}")
            if stats['rate'] > 100:
                rate_item.setForeground(QColor("red"))  # High rate warning
            elif stats['rate'] > 50:
                rate_item.setForeground(QColor("orange"))  # Medium rate
            else:
                rate_item.setForeground(QColor("green"))  # Normal rate
            self.stats_table.setItem(row, 6, rate_item)
            
            # Color-code current value based on range
            current_item = self.stats_table.item(row, 1)
            if current_item:
                if stats['current'] >= stats['max'] * 0.9:
                    current_item.setForeground(QColor("red"))  # Near maximum
                elif stats['current'] <= stats['min'] * 1.1:
                    current_item.setForeground(QColor("blue"))  # Near minimum
                else:
                    current_item.setForeground(QColor("black"))  # Normal range
    
    def on_time_window_changed(self, window_text: str):
        """Handle time window change"""
        # Parse time window and adjust plot view
        if window_text == "All":
            self.plot_widget.enableAutoRange(axis='x')
        else:
            # Parse time value
            if window_text.endswith('s'):
                seconds = float(window_text[:-1])
            elif window_text.endswith('m'):
                seconds = float(window_text[:-1]) * 60
            elif window_text.endswith('h'):
                seconds = float(window_text[:-1]) * 3600
            else:
                seconds = 30  # Default
            
            # Set fixed time window
            if self.signals and any(signal.times for signal in self.signals.values()):
                max_time = max(max(signal.times) for signal in self.signals.values() if signal.times)
                self.plot_widget.setXRange(max_time - seconds, max_time)
            
    def on_buffer_size_changed(self, size_text: str):
        """Handle buffer size change"""
        # Parse buffer size
        size_map = {"1K": 1000, "5K": 5000, "10K": 10000, "50K": 50000, 
                   "100K": 100000, "500K": 500000, "1M": 1000000}
        
        new_size = size_map.get(size_text, 10000)
        self.max_plot_points = new_size
        
        # Update existing signals (this will truncate if smaller)
        for signal_data in self.signals.values():
            # Create new deques with new size
            signal_data.times = deque(signal_data.times, maxlen=new_size)
            signal_data.values = deque(signal_data.values, maxlen=new_size)
            
        print(f"📊 Buffer size changed to {size_text} ({new_size} points)")
        
    def on_update_rate_changed(self, rate_text: str):
        """Handle update rate change"""
        # Parse FPS and update timer
        fps = int(rate_text.split()[0])
        interval_ms = int(1000 / fps)
        
        self.plot_timer.stop()
        self.plot_timer.start(interval_ms)
        
        print(f"🎯 Update rate changed to {fps} FPS ({interval_ms}ms interval)")
    
    def auto_scale_y_axes(self):
        """Auto-scale Y axes to fit all signal data"""
        if not self.signals:
            return
            
        # Get all signal values for auto-scaling
        all_values = []
        for signal_data in self.signals.values():
            if signal_data.values and signal_data.enabled:
                all_values.extend(list(signal_data.values))
        
        # Scale main plot to fit all visible signals
        if all_values:
            min_val, max_val = min(all_values), max(all_values)
            margin = (max_val - min_val) * 0.1 if max_val != min_val else 1.0  # 10% margin
            self.plot_widget.setYRange(min_val - margin, max_val + margin)
            print(f"📏 Auto-scaled Y axis: {min_val:.2f} to {max_val:.2f}")
        else:
            # No data, use default range
            self.plot_widget.enableAutoRange(axis='y')
            print("📏 Auto-scaled Y axis: No data, using auto-range")
        
    def toggle_freeze(self):
        """Toggle plot freeze mode"""
        if hasattr(self, 'plot_frozen') and self.plot_frozen:
            # Unfreeze
            self.plot_frozen = False
            self.freeze_plot_btn.setText("Freeze")
            self.freeze_plot_btn.setStyleSheet("")
            print("▶️ Plot unfrozen - resuming updates")
        else:
            # Freeze
            self.plot_frozen = True
            self.freeze_plot_btn.setText("Unfreeze")
            self.freeze_plot_btn.setStyleSheet("background-color: #e74c3c; color: white;")
            print("⏸️ Plot frozen - updates paused")
            
    def clear_all_data(self):
        """Clear all signal data but keep signal selection"""
        for signal_data in self.signals.values():
            signal_data.clear_data()
            
        # Reset start time
        self.start_time = None
        
        # Clear plots
        for signal_data in self.signals.values():
            if signal_data.plot_item:
                signal_data.plot_item.setData([], [])
                
        print("🗑️ Cleared all signal data")
                
    def add_signal_to_plot(self, signal_data: SignalData):
        """Add a signal to the plot widget"""
        try:
            # Create plot curve
            pen = pg.mkPen(color=signal_data.color, width=2)
            plot_item = self.plot_widget.plot([], [], pen=pen, name=f"Bus{signal_data.bus_number}.{signal_data.message_name}.{signal_data.signal_name}")
            signal_data.plot_item = plot_item
            
            print(f"✅ Added signal Bus{signal_data.bus_number}.{signal_data.message_name}.{signal_data.signal_name} to plot with color {signal_data.color}")
            
        except Exception as e:
            print(f"❌ Error adding signal to plot: {e}")
            import traceback
            traceback.print_exc()
        
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
        """Export plot as high-quality image with metadata"""
        # Get current timestamp for filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_filename = f"QCAN_Plot_{timestamp}.png"
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Plot Image", default_filename, 
            "PNG Files (*.png);;JPEG Files (*.jpg);;BMP Files (*.bmp);;SVG Files (*.svg);;All Files (*)"
        )
        
        if filename:
            try:
                # Prepare metadata
                metadata = self.get_export_metadata()
                
                # Try different pyqtgraph export methods with enhanced quality
                try:
                    # Method 1: Direct import of exporters with high quality settings
                    from pyqtgraph.exporters import ImageExporter
                    exporter = ImageExporter(self.plot_widget.plotItem)
                    
                    # Set high quality parameters
                    exporter.parameters()['width'] = 1920  # High resolution
                    exporter.parameters()['height'] = 1080
                    
                    exporter.export(filename)
                    
                except (ImportError, AttributeError):
                    try:
                        # Method 2: Try using pg.exporters if available
                        exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
                        exporter.export(filename)
                    except (ImportError, AttributeError):
                        # Method 3: High-quality Qt screenshot
                        print("Using high-quality Qt widget screenshot for image export")
                        
                        # Get high-resolution pixmap
                        scale_factor = 2.0  # 2x resolution for better quality
                        pixmap = self.plot_widget.grab()
                        
                        # Scale up for better quality
                        from PyQt6.QtCore import QSize
                        scaled_pixmap = pixmap.scaled(
                            QSize(int(pixmap.width() * scale_factor), int(pixmap.height() * scale_factor)),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        if not scaled_pixmap.save(filename):
                            raise Exception("Failed to save image file")
                
                # Show success with metadata
                signal_count = len(self.signals)
                point_count = sum(len(signal.times) for signal in self.signals.values())
                
                QMessageBox.information(self, "Export Success", 
                    f"Exported plot image to {filename}\\n\\n"
                    f"Signals: {signal_count}\\n"
                    f"Data Points: {point_count}\\n"
                    f"Time Range: {metadata.get('time_range', 'Unknown')}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export image: {str(e)}")
                
    def get_export_metadata(self) -> Dict[str, str]:
        """Get metadata for export"""
        metadata = {
            'application': 'QCAN Explorer',
            'version': '2.0.0',
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'signal_count': str(len(self.signals)),
            'networks': ', '.join(set(f"Bus{s.bus_number}" for s in self.signals.values())),
        }
        
        # Add time range if data exists
        if self.signals:
            all_times = []
            for signal_data in self.signals.values():
                if signal_data.times:
                    all_times.extend(signal_data.times)
            
            if all_times:
                time_range = f"{min(all_times):.3f}s to {max(all_times):.3f}s"
                metadata['time_range'] = time_range
                
        return metadata
        
    def open_signal_management(self):
        """Open signal management dialog"""
        if not self.signals:
            QMessageBox.information(self, "No Signals", "No signals are currently selected for plotting.")
            return
            
        dialog = SignalManagementDialog(self, self.signals)
        dialog.exec()
        
        # Update button states after management
        self.update_button_states()
        
    def save_signal_preset(self):
        """Save current signal selection as a preset"""
        if not self.signals:
            QMessageBox.warning(self, "No Signals", "No signals selected to save as preset.")
            return
            
        # Get preset name from user
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Preset", "Enter preset name:")
        
        if ok and name:
            preset_data = {
                'name': name,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'signals': []
            }
            
            for signal_key, signal_data in self.signals.items():
                preset_data['signals'].append({
                    'message_name': signal_data.message_name,
                    'signal_name': signal_data.signal_name,
                    'bus_number': signal_data.bus_number,
                    'can_id': signal_data.can_id,
                    'y_axis': signal_data.y_axis,
                    'color': signal_data.color
                })
            
            # Save to file
            preset_dir = "presets"
            if not os.path.exists(preset_dir):
                os.makedirs(preset_dir)
                
            preset_file = os.path.join(preset_dir, f"{name}.json")
            
            try:
                import json
                with open(preset_file, 'w') as f:
                    json.dump(preset_data, f, indent=2)
                    
                # Add to combo
                self.preset_combo.addItem(name)
                self.preset_combo.setCurrentText(name)
                
                QMessageBox.information(self, "Success", f"Saved signal preset '{name}'")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save preset: {e}")
                
    def load_signal_preset(self, preset_name: str):
        """Load a signal preset"""
        if preset_name == "Load Preset..." or not preset_name:
            return
            
        preset_file = os.path.join("presets", f"{preset_name}.json")
        
        if not os.path.exists(preset_file):
            QMessageBox.warning(self, "Preset Not Found", f"Preset file not found: {preset_file}")
            return
            
        try:
            import json
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
                
            # Clear current signals
            self.clear_plots()
            
            # Load preset signals
            for signal_info in preset_data['signals']:
                signal_key = f"Bus{signal_info['bus_number']}.{signal_info['message_name']}.{signal_info['signal_name']}"
                signal_data = SignalData(
                    signal_info['message_name'],
                    signal_info['signal_name'], 
                    signal_info['can_id'],
                    signal_info['color'],
                    signal_info['bus_number'],
                    self.max_plot_points
                )
                signal_data.y_axis = signal_info.get('y_axis', 'left')
                
                self.signals[signal_key] = signal_data
                self.add_signal_to_plot(signal_data)
                
            # Update button states without calling load_available_presets again
            has_signals = len(self.signals) > 0
            self.manage_signals_btn.setEnabled(has_signals)
            self.save_preset_btn.setEnabled(has_signals)
            
            QMessageBox.information(self, "Success", 
                f"Loaded preset '{preset_name}' with {len(preset_data['signals'])} signals")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preset: {e}")
            
    def export_report(self):
        """Export PNG + CSV for engineering reports"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Export high-quality PNG
        png_filename = f"QCAN_Report_{timestamp}.png"
        self.export_image_with_filename(png_filename, quality='report')
        
        # Export CSV data
        csv_filename = f"QCAN_Report_{timestamp}.csv"
        self.export_csv_with_filename(csv_filename)
        
        QMessageBox.information(self, "Report Exported", 
            f"Engineering report exported:\\n\\n"
            f"Plot: {png_filename}\\n"
            f"Data: {csv_filename}")
            
    def export_presentation(self):
        """Export high-resolution PNG for presentations"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        png_filename = f"QCAN_Presentation_{timestamp}.png"
        
        self.export_image_with_filename(png_filename, quality='presentation')
        
        QMessageBox.information(self, "Presentation Export", 
            f"High-resolution plot exported for presentations:\\n{png_filename}")
            
    def export_image_with_filename(self, filename: str, quality: str = 'standard'):
        """Export image with specified quality settings"""
        try:
            from pyqtgraph.exporters import ImageExporter
            exporter = ImageExporter(self.plot_widget.plotItem)
            
            # Set quality-specific parameters
            if quality == 'presentation':
                exporter.parameters()['width'] = 2560  # 4K width
                exporter.parameters()['height'] = 1440  # 4K height
            elif quality == 'report':
                exporter.parameters()['width'] = 1920  # HD width
                exporter.parameters()['height'] = 1080  # HD height
            else:
                exporter.parameters()['width'] = 1280  # Standard
                exporter.parameters()['height'] = 720
                
            exporter.export(filename)
            
        except Exception as e:
            # Fallback to Qt screenshot
            pixmap = self.plot_widget.grab()
            if not pixmap.save(filename):
                raise Exception("Failed to save image")
                
    def export_csv_with_filename(self, filename: str):
        """Export CSV data with specified filename"""
        try:
            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                
                # Write header
                header = ['Time']
                for signal_key in self.signals.keys():
                    header.append(signal_key)
                writer.writerow(header)
                
                # Write data
                if self.signals:
                    # Get all time points
                    all_times = set()
                    for signal_data in self.signals.values():
                        all_times.update(signal_data.times)
                    
                    # Sort times
                    sorted_times = sorted(all_times)
                    
                    # Write data rows
                    for time_point in sorted_times:
                        row = [f"{time_point:.6f}"]
                        for signal_data in self.signals.values():
                            # Find closest value for this time
                            if time_point in signal_data.times:
                                idx = list(signal_data.times).index(time_point)
                                value = list(signal_data.values)[idx]
                                row.append(f"{value:.6f}")
                            else:
                                row.append("")  # No data at this time
                        writer.writerow(row)
                        
        except Exception as e:
            raise Exception(f"CSV export failed: {e}")
            
    def update_button_states(self):
        """Update button enabled states based on current signals"""
        has_signals = len(self.signals) > 0
        self.manage_signals_btn.setEnabled(has_signals)
        self.save_preset_btn.setEnabled(has_signals)
        
    def load_available_presets(self):
        """Load available presets into combo box"""
        # Temporarily disconnect signal to avoid recursion
        self.preset_combo.currentTextChanged.disconnect()
        
        current_text = self.preset_combo.currentText()
        self.preset_combo.clear()
        self.preset_combo.addItem("Load Preset...")
        
        preset_dir = "presets"
        if os.path.exists(preset_dir):
            try:
                for filename in os.listdir(preset_dir):
                    if filename.endswith('.json'):
                        preset_name = filename[:-5]  # Remove .json extension
                        self.preset_combo.addItem(preset_name)
                        
                # Restore selection if possible
                index = self.preset_combo.findText(current_text)
                if index >= 0:
                    self.preset_combo.setCurrentIndex(index)
                    
            except Exception as e:
                print(f"Warning: Could not load presets: {e}")
                
        # Reconnect signal
        self.preset_combo.currentTextChanged.connect(self.load_signal_preset)
                
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
        self.sym_status_label.setStyleSheet("color: #666666; font-weight: bold;")
        
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
            # Find signals to update for this message (match both CAN ID and bus number)
            for signal_key, signal_data in self.signals.items():
                if signal_data.can_id == msg.arbitration_id and signal_data.bus_number == msg.bus_number:
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
        
        # Process trace messages for this specific signal (match both CAN ID and bus number)
        for msg in self.trace_messages:
            if signal_data.can_id == msg.arbitration_id and signal_data.bus_number == msg.bus_number:
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


class SignalManagementDialog(QDialog):
    """Enhanced dialog for managing active signals with Y-axis assignment"""
    
    def __init__(self, parent, signals: Dict[str, 'SignalData']):
        super().__init__(parent)
        self.signals = signals
        self.setWindowTitle("Manage Active Signals")
        self.setGeometry(300, 300, 600, 400)
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the signal management UI"""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("Manage active signals: toggle visibility and monitor message rates.")
        instructions.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Signal management table - simplified without Y-axis assignment
        self.signal_table = QTableWidget(len(self.signals), 4)
        self.signal_table.setHorizontalHeaderLabels(["Signal", "Visible", "Color", "Rate (Hz)"])
        self.signal_table.setAlternatingRowColors(True)
        
        # Configure table
        header = self.signal_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # Populate table
        for row, (signal_key, signal_data) in enumerate(self.signals.items()):
            # Signal name
            self.signal_table.setItem(row, 0, QTableWidgetItem(signal_key))
            
            # Visibility checkbox
            visible_cb = QCheckBox()
            visible_cb.setChecked(signal_data.enabled)
            visible_cb.stateChanged.connect(lambda state, sk=signal_key: self.on_visibility_changed(sk, state))
            self.signal_table.setCellWidget(row, 1, visible_cb)
            
            # Color indicator
            color_label = QLabel("●")
            color_label.setStyleSheet(f"color: {signal_data.color}; font-size: 20px;")
            color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.signal_table.setCellWidget(row, 2, color_label)
            
            # Message rate
            stats = signal_data.get_statistics()
            rate_item = QTableWidgetItem(f"{stats['rate']:.1f}")
            self.signal_table.setItem(row, 3, rate_item)
        
        layout.addWidget(self.signal_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Show All")
        self.select_all_btn.clicked.connect(self.show_all_signals)
        button_layout.addWidget(self.select_all_btn)
        
        self.hide_all_btn = QPushButton("Hide All")
        self.hide_all_btn.clicked.connect(self.hide_all_signals)
        button_layout.addWidget(self.hide_all_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setDefault(True)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
    def on_visibility_changed(self, signal_key: str, state: int):
        """Handle signal visibility change"""
        if signal_key in self.signals:
            enabled = state == Qt.CheckState.Checked.value
            self.signals[signal_key].enabled = enabled
            if self.signals[signal_key].plot_item:
                self.signals[signal_key].plot_item.setVisible(enabled)
            print(f"🔄 Signal {signal_key} visibility: {enabled}")
            
            
    def show_all_signals(self):
        """Show all signals"""
        for row in range(self.signal_table.rowCount()):
            cb = self.signal_table.cellWidget(row, 1)
            if cb:
                cb.setChecked(True)
                
    def hide_all_signals(self):
        """Hide all signals"""
        for row in range(self.signal_table.rowCount()):
            cb = self.signal_table.cellWidget(row, 1)
            if cb:
                cb.setChecked(False)
