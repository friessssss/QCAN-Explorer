#!/usr/bin/env python3
"""
Expandable Monitor Tab Demo
Demonstrates the new expandable message tree in the Monitor tab
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QHBoxLayout
from gui.monitor_tab import MessageTreeWidget
from canbus.interface_manager import CANInterfaceManager
from utils.sym_parser import SymParser


class ExpandableMonitorDemo(QMainWindow):
    """Demo window showing expandable Monitor tab functionality"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QCAN Explorer - Expandable Monitor Demo")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title = QLabel("🌳 Expandable Monitor Tab Demo")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Add instructions
        instructions = QLabel("""
📋 Instructions:
• Message names are shown by default (e.g., "Engine_Data", "Vehicle_Speed_Data")
• Click the expand arrow (▶) next to any message to see individual signals
• Each signal shows: SignalName = Value Unit (e.g., "EngineRPM = 1500.00 RPM")
• Click on messages or signals to see details in the bottom panel
• Tree structure makes it easy to organize and understand CAN data
        """)
        instructions.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.expand_all_btn = QPushButton("Expand All Messages")
        self.expand_all_btn.clicked.connect(self.expand_all)
        button_layout.addWidget(self.expand_all_btn)
        
        self.collapse_all_btn = QPushButton("Collapse All Messages")
        self.collapse_all_btn.clicked.connect(self.collapse_all)
        button_layout.addWidget(self.collapse_all_btn)
        
        button_layout.addStretch()
        
        self.add_test_data_btn = QPushButton("Add Test Messages")
        self.add_test_data_btn.clicked.connect(self.add_test_messages)
        button_layout.addWidget(self.add_test_data_btn)
        
        layout.addLayout(button_layout)
        
        # Create CAN manager and monitor components
        self.can_manager = CANInterfaceManager()
        
        # Create message tree
        self.message_tree = MessageTreeWidget()
        layout.addWidget(self.message_tree)
        
        # Load SYM file for decoding
        self.load_sym_file()
        
    def load_sym_file(self):
        """Load the virtual CAN SYM file"""
        sym_path = os.path.join(os.path.dirname(__file__), 'sym', 'virtual_can_network.sym')
        
        parser = SymParser()
        success = parser.parse_file(sym_path)
        
        if success:
            self.message_tree.set_sym_parser(parser)
            print(f"✅ Loaded SYM file with {len(parser.messages)} message definitions")
        else:
            print("❌ Failed to load SYM file")
            
    def expand_all(self):
        """Expand all message trees"""
        self.message_tree.expandAll()
        
    def collapse_all(self):
        """Collapse all message trees"""
        self.message_tree.collapseAll()
        
    def add_test_messages(self):
        """Add some test messages to demonstrate the expandable functionality"""
        from canbus.messages import CANMessage
        
        # Create realistic test messages with different signal values
        test_messages = [
            # Engine_Data with high RPM
            CANMessage(
                timestamp=time.time(),
                arbitration_id=0x100,
                data=b'\x0B\xB8\x4B\x64\x50\x00\x00\x00',  # RPM=3000, Load=75, Temp=100, Throttle=80
                is_extended_id=False, is_remote_frame=False, is_error_frame=False,
                channel='demo', direction='rx'
            ),
            
            # Vehicle_Speed_Data with highway speed
            CANMessage(
                timestamp=time.time() + 0.1,
                arbitration_id=0x101,
                data=b'\x2C\x01\x87\x65\x43\x21\x00\x00',  # Speed=100 km/h, Odometer=123456789
                is_extended_id=False, is_remote_frame=False, is_error_frame=False,
                channel='demo', direction='rx'
            ),
            
            # Body_Control_Data with doors open
            CANMessage(
                timestamp=time.time() + 0.2,
                arbitration_id=0x200,
                data=b'\x0F\x64\x03\x00\x00\x00\x00\x00',  # All doors open, window 100%, lights on
                is_extended_id=False, is_remote_frame=False, is_error_frame=False,
                channel='demo', direction='rx'
            ),
            
            # Electrical_System_Data
            CANMessage(
                timestamp=time.time() + 0.3,
                arbitration_id=0x300,
                data=b'\x50\x7C\x00\x00\x00\x00\x00\x00',  # Fuel=80%, Battery=12.4V
                is_extended_id=False, is_remote_frame=False, is_error_frame=False,
                channel='demo', direction='rx'
            ),
            
            # Climate_Control_Data
            CANMessage(
                timestamp=time.time() + 0.4,
                arbitration_id=0x400,
                data=b'\x16\x18\x02\x00\x00\x00\x00\x00',  # Target=22°C, Actual=24°C, Fan=Medium
                is_extended_id=False, is_remote_frame=False, is_error_frame=False,
                channel='demo', direction='rx'
            ),
        ]
        
        print(f"\n📨 Adding {len(test_messages)} test messages...")
        for i, msg in enumerate(test_messages):
            self.message_tree.add_message(msg)
            print(f"  Added: 0x{msg.arbitration_id:X} - {self.message_tree.get_message_name(msg.arbitration_id)}")
            
        print(f"\n🌳 Tree now has {self.message_tree.topLevelItemCount()} message types")
        print("📌 Click expand arrows (▶) to see individual signal values!")


def main():
    """Main demo function"""
    print("🚀 QCAN Explorer Expandable Monitor Demo")
    print("=" * 50)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create demo window
    demo_window = ExpandableMonitorDemo()
    demo_window.show()
    
    print("\n📋 Demo Features:")
    print("  • Hierarchical tree structure for CAN messages")
    print("  • Message names shown by default (compact view)")
    print("  • Expandable to show individual signal details")
    print("  • Real-time signal value decoding")
    print("  • Professional signal formatting with units")
    print("  • Click selection shows detailed information")
    
    print("\n🎯 Interactive Features:")
    print("  • Click 'Add Test Messages' to populate the tree")
    print("  • Use 'Expand All' / 'Collapse All' buttons")
    print("  • Click expand arrows (▶) next to message names")
    print("  • Select messages or signals to see details")
    
    print("\n⏱️  Demo ready - interact with the window!")
    print("   Close the window or press Ctrl+C to stop")
    
    try:
        # Run the application
        app.exec()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo stopped by user")
    
    print("\n✅ Demo completed!")
    print("\n💡 In the full QCAN Explorer:")
    print("   1. Start QCAN Explorer: python main.py")
    print("   2. Connect to virtual CAN network")
    print("   3. Load SYM file for message definitions")
    print("   4. Monitor tab now shows expandable message tree")
    print("   5. Real-time messages appear with expandable signal details")


if __name__ == "__main__":
    main()
