#!/usr/bin/env python3
"""
Virtual CAN Network Demo
Demonstrates QCAN Explorer's virtual CAN network with symbolic decoding
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from canbus.interface_manager import CANInterfaceManager
from utils.sym_parser import SymParser


def decode_message_with_sym(parser, msg):
    """Decode a CAN message using SYM file definitions"""
    if not parser or not parser.messages:
        return "No SYM file loaded"
    
    # Find matching message definition
    for msg_name, msg_def in parser.messages.items():
        if msg_def.can_id == msg.arbitration_id:
            decoded = f"📋 {msg_name} (0x{msg.arbitration_id:X}):\n"
            
            # Decode each variable
            for var in msg_def.variables:
                if var.start_bit + var.bit_length <= len(msg.data) * 8:
                    # Extract bits (simplified - assumes byte-aligned)
                    start_byte = var.start_bit // 8
                    end_byte = (var.start_bit + var.bit_length - 1) // 8 + 1
                    
                    if end_byte <= len(msg.data):
                        # Extract raw value
                        raw_bytes = msg.data[start_byte:end_byte]
                        raw_value = int.from_bytes(raw_bytes, byteorder='little')
                        
                        # Apply bit masking for partial bytes
                        if var.start_bit % 8 != 0 or var.bit_length % 8 != 0:
                            # Simplified bit extraction
                            bit_offset = var.start_bit % 8
                            mask = (1 << var.bit_length) - 1
                            raw_value = (raw_value >> bit_offset) & mask
                        
                        # Apply scaling
                        scaled_value = raw_value * var.factor + var.offset
                        
                        # Format output
                        unit_str = f" {var.unit}" if var.unit else ""
                        decoded += f"  {var.name}: {scaled_value:.2f}{unit_str}\n"
            
            return decoded
    
    return f"Unknown message ID: 0x{msg.arbitration_id:X}"


def main():
    """Main demonstration function"""
    print("🚀 QCAN Explorer Virtual CAN Network Demo")
    print("=" * 50)
    
    # Create interface manager
    manager = CANInterfaceManager()
    
    # Load SYM file
    print("📁 Loading SYM file...")
    parser = SymParser()
    sym_path = os.path.join(os.path.dirname(__file__), 'sym', 'virtual_can_network.sym')
    sym_success = parser.parse_file(sym_path)
    
    if sym_success:
        print(f"✅ Loaded {len(parser.messages)} message definitions")
        print(f"   Title: {parser.title}")
    else:
        print("❌ Failed to load SYM file")
        return
    
    # Connect to virtual CAN
    print("\n🔌 Connecting to virtual CAN network...")
    success = manager.connect('virtual', 'virtual0', 500000)
    
    if not success:
        print("❌ Failed to connect to virtual CAN")
        return
    
    print("✅ Connected to virtual CAN network")
    print("📡 Virtual messages are now being generated...")
    
    # Message counter for demo
    message_count = 0
    last_message_time = time.time()
    
    # Set up message callback
    def on_message_received(msg):
        nonlocal message_count, last_message_time
        message_count += 1
        
        # Only show messages every 2 seconds to avoid spam
        if time.time() - last_message_time >= 2.0:
            print(f"\n📨 Message #{message_count}:")
            print(f"   Raw: ID=0x{msg.arbitration_id:X}, Data={msg.data.hex()}")
            
            # Decode with SYM file
            decoded = decode_message_with_sym(parser, msg)
            print(decoded)
            
            last_message_time = time.time()
    
    # Connect the callback
    manager.message_received.connect(on_message_received)
    
    print("\n🎯 Demo running... (Press Ctrl+C to stop)")
    print("   - Virtual CAN messages are being generated")
    print("   - Messages are being decoded using the SYM file")
    print("   - You'll see decoded values every 2 seconds")
    
    try:
        # Run for 30 seconds
        time.sleep(30)
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo stopped by user")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    manager.disconnect()
    
    # Final statistics
    stats = manager.get_statistics()
    print(f"\n📊 Final Statistics:")
    print(f"   Total messages: {stats['message_count']}")
    print(f"   RX messages: {stats['rx_count']}")
    print(f"   TX messages: {stats['tx_count']}")
    print(f"   Uptime: {stats['uptime']:.1f} seconds")
    
    print("\n✅ Demo completed!")
    print("\n💡 To use this in QCAN Explorer:")
    print("   1. Start QCAN Explorer: python main.py")
    print("   2. Select 'virtual' interface and 'virtual0' channel")
    print("   3. Click Connect")
    print("   4. Load the SYM file: examples/sym/virtual_can_network.sym")
    print("   5. Switch to Monitor tab to see decoded messages")


if __name__ == "__main__":
    main()
