#!/usr/bin/env python3
"""
Enhanced Logging Tab Demo
Demonstrates the redesigned logging functionality with text-based display and hover tooltips
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from gui.logging_tab import LoggingTab
from canbus.interface_manager import CANInterfaceManager
from utils.sym_parser import SymParser


class LoggingDemo(QMainWindow):
    """Demo window showing enhanced logging functionality"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QCAN Explorer - Enhanced Logging Demo")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("📝 Enhanced Logging Tab Demo")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Add instructions
        instructions = QLabel("""
📋 New Logging Features:
• Streamlined controls: Start | Stop | Clear | Save | Open | Format (all on one line)
• No maximum message count limit - log as many messages as needed
• Professional text-based display similar to Vector CANoe/CANalyzer
• Hover over any message to see decoded signal values (when SYM file loaded)
• Real-time message display during logging
• Open existing log files (CSV, JSON, ASC, TRC formats)
        """)
        instructions.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Create CAN manager and logging tab
        self.can_manager = CANInterfaceManager()
        self.logging_tab = LoggingTab(self.can_manager)
        
        # Load SYM file for tooltips
        self.load_sym_file()
        
        # Add logging tab
        layout.addWidget(self.logging_tab)
        
        # Start demo
        self.start_demo()
        
    def load_sym_file(self):
        """Load the virtual CAN SYM file for tooltips"""
        sym_path = os.path.join(os.path.dirname(__file__), 'sym', 'virtual_can_network.sym')
        
        parser = SymParser()
        success = parser.parse_file(sym_path)
        
        if success:
            self.logging_tab.set_sym_parser(parser)
            print(f"✅ Loaded SYM file for hover tooltips")
        else:
            print("❌ Failed to load SYM file")
            
    def start_demo(self):
        """Start the demo"""
        # Connect to virtual CAN
        success = self.can_manager.connect('virtual', 'virtual0', 500000)
        
        if success:
            print("✅ Connected to virtual CAN network")
            print("✅ Ready for logging demo")
            
            # Auto-start logging for demo
            self.logging_tab.start_logging()
            print("✅ Logging started automatically")
        else:
            print("❌ Failed to connect to virtual CAN")


def main():
    """Main demo function"""
    print("🚀 QCAN Explorer Enhanced Logging Demo")
    print("=" * 50)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create demo window
    demo_window = LoggingDemo()
    demo_window.show()
    
    print("\n📋 Demo Features:")
    print("  • Streamlined control layout (single row)")
    print("  • Text-based message display (professional format)")
    print("  • Real-time logging with immediate display")
    print("  • Hover tooltips with decoded signal values")
    print("  • No message count limits")
    print("  • Open/Save log files in multiple formats")
    
    print("\n🎯 Try These Features:")
    print("  • Logging starts automatically in this demo")
    print("  • Hover over message data to see decoded values")
    print("  • Use Start/Stop/Clear buttons")
    print("  • Try Save Log and Open Log buttons")
    print("  • Change format dropdown (CSV, JSON, ASC, TRC)")
    
    print("\n📊 Message Format:")
    print("  Number    Time        ID        Dir  Type  DLC  Data")
    print("       1  12345.6789  0x000100   RX  Data    8  01 02 03 04 05 06 07 08")
    
    print("\n⏱️  Demo ready - interact with the logging controls!")
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
    print("   3. Go to Logging tab")
    print("   4. Use streamlined controls for logging")
    print("   5. Hover over messages to see decoded values")


if __name__ == "__main__":
    main()
