#!/usr/bin/env python3
"""
Enhanced Logging Tab Demo
Showcases the professional logging interface with distinct columns and hover tooltips
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QHBoxLayout
from gui.logging_tab import LoggingTab
from canbus.interface_manager import CANInterfaceManager
from utils.sym_parser import SymParser


class EnhancedLoggingDemo(QMainWindow):
    """Demo window showing enhanced logging functionality"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QCAN Explorer - Enhanced Logging Demo")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("📊 Enhanced Professional Logging Demo")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Add instructions
        instructions = QLabel("""
📋 Professional Logging Features:
• Streamlined single-row controls: Start | Stop | Clear | Save | Open | Format
• Industry-standard column formatting with distinct spacing
• Professional headers like Vector CANoe/CANalyzer
• Hover tooltips show decoded signal values (with SYM files loaded)
• No message count limits - log unlimited CAN traffic
• Open existing log files in multiple formats (CSV, JSON, ASC, TRC)

🖱️  Hover over any message data to see decoded signal values!
        """)
        instructions.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Demo controls
        demo_controls = QHBoxLayout()
        
        self.load_trc_btn = QPushButton("Load Example TRC File")
        self.load_trc_btn.clicked.connect(self.load_example_trc)
        demo_controls.addWidget(self.load_trc_btn)
        
        demo_controls.addStretch()
        
        layout.addLayout(demo_controls)
        
        # Create CAN manager and logging tab
        self.can_manager = CANInterfaceManager()
        self.logging_tab = LoggingTab(self.can_manager)
        
        # Load SYM file for tooltips
        self.load_sym_file()
        
        # Add logging tab
        layout.addWidget(self.logging_tab)
        
        # Start virtual CAN demo
        self.start_virtual_demo()
        
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
            
    def start_virtual_demo(self):
        """Start virtual CAN demo"""
        # Connect to virtual CAN
        success = self.can_manager.connect('virtual', 'virtual0', 500000)
        
        if success:
            print("✅ Connected to virtual CAN network")
            
            # Auto-start logging for demo
            self.logging_tab.start_logging()
            print("✅ Logging started automatically")
            print("📊 Watch the professional message display!")
        else:
            print("❌ Failed to connect to virtual CAN")
            
    def load_example_trc(self):
        """Load the example TRC file"""
        trc_path = os.path.join(os.path.dirname(__file__), 'logs', 'example.trc')
        
        if os.path.exists(trc_path):
            # Clear current display
            self.logging_tab.playback_text.clear_messages()
            self.logging_tab.playback_messages = []
            
            # Load TRC file
            from gui.logging_tab import LogReader
            
            try:
                log_reader = LogReader(trc_path)
                
                def on_message_loaded(msg):
                    self.logging_tab.on_playback_message_loaded(msg)
                
                def on_finished(count):
                    print(f"✅ Loaded {count} messages from example TRC file")
                    
                log_reader.message_loaded.connect(on_message_loaded)
                log_reader.finished.connect(on_finished)
                log_reader.run()
                
            except Exception as e:
                print(f"❌ Error loading TRC file: {e}")
        else:
            print(f"❌ Example TRC file not found: {trc_path}")


def main():
    """Main demo function"""
    print("🚀 QCAN Explorer Enhanced Logging Demo")
    print("=" * 50)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create demo window
    demo_window = EnhancedLoggingDemo()
    demo_window.show()
    
    print("\n📋 Enhanced Features:")
    print("  • Professional column formatting with distinct spacing")
    print("  • Industry-standard headers like Vector CANoe/CANalyzer")
    print("  • Streamlined single-row control layout")
    print("  • Hover tooltips with decoded signal values")
    print("  • No message count limits")
    print("  • Open/Save multiple log file formats")
    
    print("\n🎯 Try These Features:")
    print("  • Watch real-time logging with professional formatting")
    print("  • Hover over message data to see decoded values")
    print("  • Use Start/Stop/Clear/Save/Open controls")
    print("  • Click 'Load Example TRC File' to see file loading")
    print("  • Try different save formats (CSV, JSON, ASC, TRC)")
    
    print("\n📊 Professional Format:")
    print("    #    Time (rel.)         ID        Dir Type DLC Data (hex.)")
    print("  ---------------------------------------------------------------------------")
    print("     1 1758001108.7693    0x000100  RX  Data  8 09 F1 19 5E 46 00 00 00")
    print("     2 1758001108.7694    0x000101  RX  Data  8 00 BB 12 34 56 78 00 00")
    
    print("\n⏱️  Demo ready - logging starts automatically!")
    print("   Hover over messages to see tooltips!")
    print("   Close the window or press Ctrl+C to stop")
    
    try:
        # Run the application
        app.exec()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo stopped by user")
    
    # Cleanup
    demo_window.can_manager.disconnect()
    print("\n✅ Demo completed!")


if __name__ == "__main__":
    main()
