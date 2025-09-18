#!/usr/bin/env python3
"""
Monitor Tab Decoding Demo
Demonstrates the enhanced Monitor tab with decoded signals display
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from gui.monitor_tab import MonitorTab
from canbus.interface_manager import CANInterfaceManager
from utils.sym_parser import SymParser


class DemoWindow(QMainWindow):
    """Demo window showing Monitor tab with decoded signals"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QCAN Explorer - Monitor Tab Decoding Demo")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("🔍 Monitor Tab with Decoded Signals Demo")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Create CAN manager and monitor tab
        self.can_manager = CANInterfaceManager()
        self.monitor_tab = MonitorTab(self.can_manager)
        
        # Load SYM file
        self.load_sym_file()
        
        # Add monitor tab
        layout.addWidget(self.monitor_tab)
        
        # Start virtual CAN and monitoring
        self.start_demo()
        
    def load_sym_file(self):
        """Load the virtual CAN SYM file"""
        sym_path = os.path.join(os.path.dirname(__file__), 'sym', 'virtual_can_network.sym')
        
        parser = SymParser()
        success = parser.parse_file(sym_path)
        
        if success:
            self.monitor_tab.set_sym_parser(parser)
            print(f"✅ Loaded SYM file with {len(parser.messages)} message definitions")
        else:
            print("❌ Failed to load SYM file")
            
    def start_demo(self):
        """Start the demo with virtual CAN"""
        # Connect to virtual CAN
        success = self.can_manager.connect('virtual', 'virtual0', 500000)
        
        if success:
            print("✅ Connected to virtual CAN network")
            
            # Start monitoring
            self.monitor_tab.start_monitoring()
            print("✅ Started monitoring - messages will appear with decoded signals")
            
            # Add some manual messages to demonstrate
            self.inject_demo_messages()
        else:
            print("❌ Failed to connect to virtual CAN")
            
    def inject_demo_messages(self):
        """Inject some demo messages to show decoding"""
        # Wait a moment for virtual messages to start
        time.sleep(1)
        
        # Inject some specific messages to demonstrate decoding
        demo_messages = [
            # Engine data with specific values
            (0x100, b'\x05\xDC\x32\x5A\x3C\x00\x00\x00'),  # RPM=1500, Load=50, Temp=90, Throttle=60
            # Vehicle speed
            (0x101, b'\x19\x64\x12\x34\x56\x78\x00\x00'),  # Speed=65.0 km/h, Odometer=2018915346
            # Body control
            (0x200, b'\x0F\x50\x03\x00\x00\x00\x00\x00'),  # All doors open, window 80%, lights on
        ]
        
        for msg_id, data in demo_messages:
            self.can_manager.inject_virtual_message(msg_id, data)
            time.sleep(0.1)
            
        print("✅ Injected demo messages with known values")


def main():
    """Main demo function"""
    print("🚀 QCAN Explorer Monitor Tab Decoding Demo")
    print("=" * 50)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create demo window
    demo_window = DemoWindow()
    demo_window.show()
    
    print("\n📋 Demo Features:")
    print("  • Monitor tab with 8 columns including 'Decoded Signals'")
    print("  • Real-time message decoding using SYM file")
    print("  • Virtual CAN network generating realistic messages")
    print("  • Human-readable signal values (RPM, speed, temperature, etc.)")
    print("  • Key-value format: 'SignalName = Value Unit'")
    
    print("\n🎯 What you'll see:")
    print("  • Raw CAN data in hex format")
    print("  • Decoded signals like 'EngineRPM = 1500.00 RPM'")
    print("  • Real-time updates as virtual messages are generated")
    print("  • Message statistics and filtering")
    
    print("\n⏱️  Demo will run for 30 seconds...")
    print("   Close the window or press Ctrl+C to stop early")
    
    try:
        # Run for 30 seconds
        app.processEvents()
        time.sleep(30)
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo stopped by user")
    
    # Cleanup
    demo_window.can_manager.disconnect()
    print("\n✅ Demo completed!")
    print("\n💡 To use this in the full QCAN Explorer:")
    print("   1. Start QCAN Explorer: python main.py")
    print("   2. Select 'virtual' interface and 'virtual0' channel")
    print("   3. Click Connect")
    print("   4. Load SYM file: examples/sym/virtual_can_network.sym")
    print("   5. Switch to Monitor tab to see decoded messages")


if __name__ == "__main__":
    main()
