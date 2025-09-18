#!/usr/bin/env python3
"""
Test script for QCAN Explorer
Runs basic functionality tests
"""

import sys
import os
import time
import threading
from unittest.mock import Mock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from canbus.interface_manager import CANInterfaceManager, CANMessage


def test_can_manager():
    """Test CAN interface manager"""
    print("Testing CAN Interface Manager...")
    
    manager = CANInterfaceManager()
    
    # Test initial state
    assert not manager.is_connected(), "Manager should not be connected initially"
    
    # Test statistics
    stats = manager.get_statistics()
    assert stats['message_count'] == 0, "Initial message count should be 0"
    
    # Test virtual interface connection
    try:
        success = manager.connect('virtual', 'test_channel', 500000)
        if success:
            print("✓ Virtual CAN interface connected")
            
            # Test message sending
            success = manager.send_message(0x123, b'\x01\x02\x03\x04', False)
            if success:
                print("✓ Message sent successfully")
            else:
                print("✗ Failed to send message")
                
            # Test periodic messages
            manager.add_periodic_message(0x456, b'\xAA\xBB', 100, False)
            print("✓ Periodic message added")
            
            # Clean up
            manager.disconnect()
            print("✓ Interface disconnected")
            
        else:
            print("✗ Failed to connect to virtual interface (this is normal if python-can virtual interface is not available)")
            
    except Exception as e:
        print(f"✗ CAN manager test failed: {e}")
        
    print()


def test_message_parsing():
    """Test CAN message parsing"""
    print("Testing CAN Message Parsing...")
    
    try:
        # Create test message
        msg = CANMessage(
            timestamp=time.time(),
            arbitration_id=0x123,
            data=b'\x01\x02\x03\x04',
            is_extended_id=False,
            is_remote_frame=False,
            is_error_frame=False,
            channel='test',
            direction='rx'
        )
        
        # Test message properties
        assert msg.arbitration_id == 0x123, "Message ID mismatch"
        assert msg.data == b'\x01\x02\x03\x04', "Message data mismatch"
        assert msg.direction == 'rx', "Message direction mismatch"
        
        print("✓ CAN message creation and properties")
        
    except Exception as e:
        print(f"✗ Message parsing test failed: {e}")
        
    print()


def test_gui_imports():
    """Test GUI component imports"""
    print("Testing GUI Imports...")
    
    try:
        from gui.main_window import MainWindow
        print("✓ Main window import")
        
        from gui.monitor_tab import MonitorTab
        print("✓ Monitor tab import")
        
        from gui.transmit_tab import TransmitTab
        print("✓ Transmit tab import")
        
        from gui.logging_tab import LoggingTab
        print("✓ Logging tab import")
        
        from gui.symbols_tab import SymbolsTab
        print("✓ Symbols tab import")
        
    except Exception as e:
        print(f"✗ GUI import test failed: {e}")
        
    print()


def test_file_examples():
    """Test example files exist"""
    print("Testing Example Files...")
    
    example_files = [
        'examples/dbc/example.dbc',
        'examples/configs/example_transmit_list.json',
        'examples/logs/example_log.csv'
    ]
    
    for file_path in example_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} not found")
            
    print()


def main():
    """Run all tests"""
    print("QCAN Explorer - Test Suite")
    print("=" * 40)
    
    test_can_manager()
    test_message_parsing()
    test_gui_imports()
    test_file_examples()
    
    print("Test suite completed!")
    print("\nTo run the application:")
    print("python main.py")
    print("\nMake sure to install dependencies first:")
    print("pip install -r requirements.txt")


if __name__ == "__main__":
    main()
