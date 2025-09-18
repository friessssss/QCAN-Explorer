#!/usr/bin/env python3
"""
Plotting Tab Demo
Demonstrates real-time signal plotting functionality
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


class PlottingDemo(QMainWindow):
    """Demo window showing plotting functionality"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QCAN Explorer - Real-time Signal Plotting Demo")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("📈 Real-time CAN Signal Plotting Demo")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Add instructions
        instructions = QLabel("""
📋 Plotting Features Demo:
• Real-time signal plotting from CAN message data
• Multiple signal overlay with different colors
• Interactive zoom and pan functionality
• Signal selection from SYM file definitions
• Export to CSV and image formats
• Professional time-series visualization

🎯 Try These Features:
1. Select signals from the left panel (check the boxes)
2. Click "Start Recording" to begin real-time plotting
3. Watch signals update in real-time as virtual CAN messages arrive
4. Use mouse to zoom and pan the plot
5. Try "Export CSV" and "Export Image" buttons
        """)
        instructions.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Demo controls
        demo_controls = QHBoxLayout()
        
        self.auto_select_btn = QPushButton("Auto-Select Key Signals")
        self.auto_select_btn.clicked.connect(self.auto_select_signals)
        demo_controls.addWidget(self.auto_select_btn)
        
        demo_controls.addStretch()
        
        layout.addLayout(demo_controls)
        
        # Create CAN manager and plotting tab
        self.can_manager = CANInterfaceManager()
        self.plotting_tab = PlottingTab(self.can_manager)
        
        # Load SYM file for signal definitions
        self.load_sym_file()
        
        # Add plotting tab
        layout.addWidget(self.plotting_tab)
        
        # Start virtual CAN demo
        self.start_demo()
        
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
            
    def start_demo(self):
        """Start the demo"""
        # Connect to virtual CAN
        success = self.can_manager.connect('virtual', 'virtual0', 500000)
        
        if success:
            print("✅ Connected to virtual CAN network")
            print("📊 Ready for real-time signal plotting!")
        else:
            print("❌ Failed to connect to virtual CAN")
            
    def auto_select_signals(self):
        """Auto-select some interesting signals for demo"""
        # Select key signals that show interesting behavior
        interesting_signals = [
            ('Engine_Data', 'EngineRPM'),
            ('Vehicle_Speed_Data', 'VehicleSpeed'),
            ('Electrical_System_Data', 'BatteryVoltage'),
            ('Body_Control_Data', 'WindowPosition'),
        ]
        
        for message_name, signal_name in interesting_signals:
            self.plotting_tab.on_signal_toggled(message_name, signal_name, True)
            
        # Start recording automatically
        self.plotting_tab.start_recording()
        
        print("✅ Auto-selected key signals and started recording")
        print("📈 Watch the real-time plots update!")


def main():
    """Main demo function"""
    print("🚀 QCAN Explorer Real-time Plotting Demo")
    print("=" * 50)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create demo window
    demo_window = PlottingDemo()
    demo_window.show()
    
    print("\n📊 Plotting Features:")
    print("  • Real-time signal visualization from CAN data")
    print("  • Multiple signals with different colors")
    print("  • Interactive zoom and pan (mouse wheel + drag)")
    print("  • Signal selection from SYM file definitions")
    print("  • Export capabilities (CSV data + PNG images)")
    print("  • Professional time-series analysis")
    
    print("\n🎯 Demo Instructions:")
    print("  1. Click 'Auto-Select Key Signals' for instant demo")
    print("  2. Or manually select signals from left panel")
    print("  3. Click 'Start Recording' to begin plotting")
    print("  4. Watch real-time signal updates")
    print("  5. Use mouse to zoom/pan the plot")
    print("  6. Try export buttons to save data/images")
    
    print("\n📈 Expected Signals:")
    print("  • EngineRPM: Varying engine speed (red)")
    print("  • VehicleSpeed: Gradually changing speed (green)")
    print("  • BatteryVoltage: Stable ~12V with small variations (blue)")
    print("  • WindowPosition: Occasional position changes (orange)")
    
    print("\n⏱️  Demo ready - start plotting!")
    print("   Close the window or press Ctrl+C to stop")
    
    try:
        # Run the application
        app.exec()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo stopped by user")
    
    # Cleanup
    demo_window.can_manager.disconnect()
    print("\n✅ Demo completed!")
    print("\n💡 In the full QCAN Explorer:")
    print("   1. Start QCAN Explorer: python main.py")
    print("   2. Connect to virtual CAN or real hardware")
    print("   3. Go to Plotting tab")
    print("   4. Load SYM file or use built-in virtual CAN symbols")
    print("   5. Select signals and start recording")
    print("   6. Analyze real-time signal behavior")


if __name__ == "__main__":
    main()
