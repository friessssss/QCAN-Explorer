"""
Shared message decoding utilities for CAN message symbol parsing
"""

from typing import Optional, List, Tuple, Dict, Any
from canbus.messages import CANMessage


class MessageDecoder:
    """Shared utility for decoding CAN messages using symbol parsers"""
    
    @staticmethod
    def extract_bits_can_format(data: bytes, start_bit: int, bit_length: int) -> int:
        """Extract bits from CAN message data using proper bit ordering"""
        if not data or bit_length <= 0:
            return 0
            
        # CAN messages use big-endian bit ordering within bytes
        # Bit 0 is the MSB of byte 0, bit 7 is LSB of byte 0, bit 8 is MSB of byte 1, etc.
        
        value = 0
        for i in range(bit_length):
            bit_pos = start_bit + i
            if bit_pos >= len(data) * 8:
                break
                
            byte_index = bit_pos // 8
            bit_index = 7 - (bit_pos % 8)  # MSB is bit 7, LSB is bit 0
            
            if byte_index < len(data):
                bit_value = (data[byte_index] >> bit_index) & 1
                value |= bit_value << (bit_length - 1 - i)
                
        return value
    
    @staticmethod
    def decode_signal_value(sym_parser, data: bytes, start_bit: int, bit_length: int, 
                          factor: float = 1.0, offset: float = 0.0, 
                          enum_name: Optional[str] = None, unit: str = "") -> str:
        """Decode a signal value from CAN data and return formatted string"""
        try:
            # Extract bits using proper CAN bit ordering
            raw_value = MessageDecoder.extract_bits_can_format(data, start_bit, bit_length)
            
            # Apply scaling
            scaled_value = raw_value * factor + offset
            unit_str = f" {unit}" if unit else ""
            
            # Handle enum values
            if enum_name and sym_parser and enum_name in sym_parser.enums:
                enum = sym_parser.enums[enum_name]
                if int(raw_value) in enum.values:  # Use raw_value for enum lookup, not scaled
                    return enum.values[int(raw_value)]
                else:
                    return f"{scaled_value:.2f}{unit_str} (enum value {int(raw_value)} not found)"
            else:
                # Format based on whether it's a whole number or has decimals
                if scaled_value == int(scaled_value):
                    return f"{int(scaled_value)}{unit_str}"
                else:
                    return f"{scaled_value:.2f}{unit_str}"
                    
        except Exception as e:
            return f"Decode error: {str(e)}"
    
    @staticmethod
    def decode_signal_value_float(sym_parser, data: bytes, start_bit: int, bit_length: int, 
                                factor: float = 1.0, offset: float = 0.0) -> Optional[float]:
        """Decode a signal value from CAN data and return as float (for plotting)"""
        try:
            # Extract bits using proper CAN bit ordering
            raw_value = MessageDecoder.extract_bits_can_format(data, start_bit, bit_length)
            
            # Apply scaling
            scaled_value = raw_value * factor + offset
            return float(scaled_value)
                    
        except Exception:
            return None
    
    @staticmethod
    def decode_message_signals(msg: CANMessage, sym_parser) -> List[Tuple[str, str]]:
        """Decode all signals in a message and return as list of (name, value) tuples"""
        if not sym_parser or not sym_parser.messages:
            return []
        
        # Find matching message definition
        for msg_name, msg_def in sym_parser.messages.items():
            if msg_def.can_id == msg.arbitration_id:
                signals = []
                
                # Decode each variable (Var= entries)
                for var in msg_def.variables:
                    try:
                        value_str = MessageDecoder.decode_signal_value(
                            sym_parser, msg.data, var.start_bit, var.bit_length, 
                            var.factor, var.offset, var.enum_name, var.unit
                        )
                        signals.append((var.name, value_str))
                    except Exception:
                        signals.append((var.name, "Error decoding"))
                
                # Decode signal assignments (Sig= entries)
                for signal_name, start_bit in msg_def.signals:
                    if signal_name in sym_parser.signals:
                        signal_def = sym_parser.signals[signal_name]
                        try:
                            value_str = MessageDecoder.decode_signal_value(
                                sym_parser, msg.data, start_bit, signal_def.bit_length, 
                                signal_def.factor, signal_def.offset, signal_def.enum_name, signal_def.unit
                            )
                            signals.append((signal_name, value_str))
                        except Exception:
                            signals.append((signal_name, "Error decoding"))
                
                return signals
        
        return []
    
    @staticmethod
    def get_message_name(msg_id: int, bus_number: int, network_manager) -> str:
        """Get message name from appropriate network's symbol parser"""
        if not network_manager:
            return f"Unknown_0x{msg_id:X}"
            
        # Find the network for this bus number
        networks = network_manager.get_all_networks()
        for network in networks.values():
            if network.config.bus_number == bus_number:
                sym_parser = network.get_symbol_parser()
                if sym_parser and sym_parser.messages:
                    for msg_name, msg_def in sym_parser.messages.items():
                        if msg_def.can_id == msg_id:
                            return msg_name
        
        return f"Unknown_0x{msg_id:X}"
