#!/usr/bin/env python3
"""
Complete Plotting Demo
Demonstrates both real-time and trace file plotting capabilities
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QHBoxLayout
from gui.plotting_tab import PlottingTab
from canbus.interface_manager import CANInterfaceManager
from utils.sym_parser import SymParser


class CompletePlottingDemo(QMainWindow):
    """Demo window showing complete plotting functionality"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QCAN Explorer - Complete Plotting Demo")
        self.setGeometry(50, 50, 1700, 1100)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("📈 Complete CAN Signal Plotting Demo")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Add instructions
        instructions = QLabel("""
🚀 Advanced Plotting Features:
• REAL-TIME PLOTTING: Live signal visualization from virtual CAN network
• TRACE FILE PLOTTING: Load and analyze historical CAN data from TRC/CSV/JSON/ASC files
• DUAL-MODE OPERATION: Switch between live monitoring and trace analysis
• PROFESSIONAL VISUALIZATION: Industry-standard time-series plots with interactive controls

📊 Plotting Capabilities:
• Multiple signals with automatic color assignment
• Interactive zoom, pan, and measurement tools
• Signal selection from SYM file definitions
• Export plots as images (PNG, JPEG) and data as CSV
• Professional time-series analysis tools
        """)
        instructions.setStyleSheet("background-color: #e8f4f8; padding: 15px; border-radius: 8px; border: 2px solid #3498db;")
        layout.addWidget(instructions)
        
        # Demo controls
        demo_controls = QHBoxLayout()
        
        self.real_time_demo_btn = QPushButton("🔴 Real-time Plotting Demo")
        self.real_time_demo_btn.clicked.connect(self.start_real_time_demo)
        self.real_time_demo_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 8px;")
        demo_controls.addWidget(self.real_time_demo_btn)
        
        self.trace_demo_btn = QPushButton("📁 Trace File Plotting Demo")
        self.trace_demo_btn.clicked.connect(self.start_trace_demo)
        self.trace_demo_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 8px;")
        demo_controls.addWidget(self.trace_demo_btn)
        
        self.create_trace_btn = QPushButton("📝 Create Sample Trace")
        self.create_trace_btn.clicked.connect(self.create_sample_trace)
        self.create_trace_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        demo_controls.addWidget(self.create_trace_btn)
        
        demo_controls.addStretch()
        
        layout.addLayout(demo_controls)
        
        # Create CAN manager and plotting tab
        self.can_manager = CANInterfaceManager()
        self.plotting_tab = PlottingTab(self.can_manager)
        
        # Load SYM file for signal definitions
        self.load_sym_file()
        
        # Add plotting tab
        layout.addWidget(self.plotting_tab)
        
    def load_sym_file(self):
        """Load the virtual CAN SYM file"""
        sym_path = os.path.join(os.path.dirname(__file__), 'sym', 'virtual_can_network.sym')
        
        parser = SymParser()
        success = parser.parse_file(sym_path)
        
        if success:
            self.plotting_tab.set_sym_parser(parser)
            print(f"✅ Loaded SYM file with {len(parser.messages)} messages for plotting")
        else:
            print("❌ Failed to load SYM file")
            
    def start_real_time_demo(self):
        """Start real-time plotting demo"""
        # Connect to virtual CAN
        success = self.can_manager.connect('virtual', 'virtual0', 500000)
        
        if success:
            print("🔴 Starting REAL-TIME plotting demo...")
            
            # Clear any trace data
            self.plotting_tab.clear_plots()
            self.plotting_tab.is_trace_mode = False
            
            # Select interesting signals
            signals_to_plot = [
                ('Engine_Data', 'EngineRPM'),
                ('Vehicle_Speed_Data', 'VehicleSpeed'),
                ('Electrical_System_Data', 'BatteryVoltage'),
                ('Body_Control_Data', 'WindowPosition'),
            ]
            
            for message_name, signal_name in signals_to_plot:
                self.plotting_tab.on_signal_toggled(message_name, signal_name, True)
                
            # Start recording
            self.plotting_tab.start_recording()
            
            print("✅ Real-time plotting started!")
            print("📈 Watch the signals update live as virtual CAN messages arrive")
        else:
            print("❌ Failed to connect to virtual CAN")
            
    def create_sample_trace(self):
        """Create a sample trace file for demonstration"""
        print("📝 Creating sample trace file...")
        
        # Connect to virtual CAN
        success = self.can_manager.connect('virtual', 'virtual0', 500000)
        
        if success:
            # Create a temporary logging session
            from gui.logging_tab import LoggingTab
            
            temp_logging = LoggingTab(self.can_manager)
            temp_logging.start_logging()
            
            # Record for 8 seconds
            time.sleep(8)
            
            temp_logging.stop_logging()
            message_count = len(temp_logging.logged_messages)
            
            if message_count > 0:
                # Save as trace file
                trace_filename = 'examples/logs/demo_trace.trc'
                
                from gui.logging_tab import LogWriter
                log_writer = LogWriter(trace_filename, 'TRC', temp_logging.logged_messages)
                log_writer.run()
                
                print(f"✅ Created demo trace file: {trace_filename}")
                print(f"   Contains {message_count} messages over 8 seconds")
            else:
                print("❌ No messages recorded for trace")
                
            self.can_manager.disconnect()
        else:
            print("❌ Failed to connect to virtual CAN for trace creation")
            
    def start_trace_demo(self):
        """Start trace file plotting demo"""
        print("📁 Starting TRACE FILE plotting demo...")
        
        # Check if we have a demo trace file
        trace_file = 'examples/logs/demo_trace.trc'
        if not os.path.exists(trace_file):
            trace_file = 'examples/logs/virtual_can_trace.trc'
            
        if not os.path.exists(trace_file):
            print("❌ No demo trace file found. Click 'Create Sample Trace' first.")
            return
            
        # Load the trace file
        try:
            from gui.logging_tab import LogReader
            
            # Clear current data
            self.plotting_tab.clear_plots()
            self.plotting_tab.trace_messages = []
            
            # Load trace
            log_reader = LogReader(trace_file)
            
            trace_messages = []
            def on_message_loaded(msg):
                trace_messages.append(msg)
                
            log_reader.message_loaded.connect(on_message_loaded)
            log_reader.run()
            
            # Set trace data
            self.plotting_tab.trace_messages = trace_messages
            self.plotting_tab.is_trace_mode = True
            self.plotting_tab.on_trace_file_loaded(len(trace_messages))
            
            # Auto-select signals for demo
            signals_to_plot = [
                ('Engine_Data', 'EngineRPM'),
                ('Vehicle_Speed_Data', 'VehicleSpeed'),
                ('Electrical_System_Data', 'BatteryVoltage'),
            ]
            
            for message_name, signal_name in signals_to_plot:
                self.plotting_tab.on_signal_toggled(message_name, signal_name, True)
                
            print(f"✅ Loaded and plotted trace file with {len(trace_messages)} messages")
            print("📈 Historical signal data now displayed on plot")
            
        except Exception as e:
            print(f"❌ Error loading trace file: {e}")


def main():
    """Main demo function"""
    print("🚀 QCAN Explorer Complete Plotting Demo")
    print("=" * 60)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create demo window
    demo_window = CompletePlottingDemo()
    demo_window.show()
    
    print("\n📊 Complete Plotting Features:")
    print("  • REAL-TIME PLOTTING: Live signal visualization from CAN network")
    print("  • TRACE FILE PLOTTING: Historical data analysis from saved files")
    print("  • DUAL-MODE OPERATION: Switch between live and historical analysis")
    print("  • INTERACTIVE CONTROLS: Zoom, pan, export, and measurement tools")
    print("  • PROFESSIONAL VISUALIZATION: Industry-standard time-series plots")
    
    print("\n🎯 Demo Workflow:")
    print("  1. Click 'Create Sample Trace' to generate demo data")
    print("  2. Click 'Real-time Plotting Demo' for live signal visualization")
    print("  3. Click 'Trace File Plotting Demo' for historical data analysis")
    print("  4. Use plot controls: zoom with mouse wheel, pan by dragging")
    print("  5. Select/deselect signals from left panel")
    print("  6. Export plots and data using bottom controls")
    
    print("\n📈 Expected Results:")
    print("  • Engine RPM: Varying between 800-6000 RPM")
    print("  • Vehicle Speed: Gradually changing 0-120 km/h")
    print("  • Battery Voltage: Stable around 12-14V")
    print("  • Window Position: Occasional step changes")
    
    print("\n⏱️  Demo ready - try both real-time and trace plotting!")
    print("   Close the window or press Ctrl+C to stop")
    
    try:
        # Run the application
        app.exec()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo stopped by user")
    
    # Cleanup
    demo_window.can_manager.disconnect()
    print("\n✅ Complete plotting demo finished!")
    print("\n💡 In the full QCAN Explorer:")
    print("   1. Start QCAN Explorer: python main.py")
    print("   2. Go to Plotting tab")
    print("   3. Load SYM file for signal definitions")
    print("   4. Either connect to CAN for real-time OR load trace file")
    print("   5. Select signals and start analysis")


if __name__ == "__main__":
    main()
