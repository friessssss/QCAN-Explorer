"""
PCAN Symbol File (.sym) Parser
Parses PCAN Symbol Editor format files for CAN message definitions
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class SymEnum:
    """Represents an enumeration definition"""
    name: str
    values: Dict[int, str]


@dataclass
class SymSignal:
    """Represents a signal definition"""
    name: str
    data_type: str
    bit_length: int
    unit: str = ""
    factor: float = 1.0
    offset: float = 0.0
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    enum_name: Optional[str] = None
    comment: str = ""


@dataclass
class SymVariable:
    """Represents a variable in a message"""
    name: str
    data_type: str
    start_bit: int
    bit_length: int
    unit: str = ""
    factor: float = 1.0
    offset: float = 0.0
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    enum_name: Optional[str] = None
    is_hex: bool = False


@dataclass
class SymMessage:
    """Represents a CAN message definition"""
    name: str
    can_id: int
    length: int
    cycle_time: Optional[int] = None
    variables: List[SymVariable] = None
    signals: List[str] = None  # Signal names and their bit positions
    comment: str = ""
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = []
        if self.signals is None:
            self.signals = []


class SymParser:
    """Parser for PCAN Symbol (.sym) files"""
    
    def __init__(self):
        self.enums: Dict[str, SymEnum] = {}
        self.signals: Dict[str, SymSignal] = {}
        self.messages: Dict[str, SymMessage] = {}
        self.version: str = ""
        self.title: str = ""
        
    def parse_file(self, file_path: str) -> bool:
        """Parse a .sym file and populate the internal structures"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            return self.parse_content(content)
            
        except Exception as e:
            print(f"Error parsing .sym file: {e}")
            return False
            
    def parse_content(self, content: str) -> bool:
        """Parse .sym file content"""
        try:
            # Split content into sections
            sections = self._split_into_sections(content)
            
            # Parse header information
            self._parse_header(content)
            
            # Parse each section
            if 'ENUMS' in sections:
                self._parse_enums(sections['ENUMS'])
                
            if 'SIGNALS' in sections:
                self._parse_signals(sections['SIGNALS'])
                
            if 'SENDRECEIVE' in sections:
                self._parse_messages(sections['SENDRECEIVE'])
                
            return True
            
        except Exception as e:
            print(f"Error parsing .sym content: {e}")
            return False
            
    def _split_into_sections(self, content: str) -> Dict[str, str]:
        """Split content into major sections"""
        sections = {}
        
        # Find section markers
        enum_match = re.search(r'{ENUMS}(.*?){SIGNALS}', content, re.DOTALL)
        if enum_match:
            sections['ENUMS'] = enum_match.group(1)
            
        signals_match = re.search(r'{SIGNALS}(.*?){SENDRECEIVE}', content, re.DOTALL)
        if signals_match:
            sections['SIGNALS'] = signals_match.group(1)
            
        sendreceive_match = re.search(r'{SENDRECEIVE}(.*?)$', content, re.DOTALL)
        if sendreceive_match:
            sections['SENDRECEIVE'] = sendreceive_match.group(1)
            
        return sections
        
    def _parse_header(self, content: str):
        """Parse header information"""
        version_match = re.search(r'FormatVersion=(.+)', content)
        if version_match:
            self.version = version_match.group(1).strip()
            
        title_match = re.search(r'Title="(.+)"', content)
        if title_match:
            self.title = title_match.group(1).strip()
            
    def _parse_enums(self, enum_section: str):
        """Parse enumeration definitions"""
        # Pattern to match enum definitions
        enum_pattern = r'Enum=(\w+)\((.*?)\)'
        
        for match in re.finditer(enum_pattern, enum_section, re.DOTALL):
            enum_name = match.group(1)
            enum_content = match.group(2)
            
            # Parse enum values
            values = {}
            value_pattern = r'(\d+)="([^"]*)"'
            
            for value_match in re.finditer(value_pattern, enum_content):
                value = int(value_match.group(1))
                description = value_match.group(2)
                values[value] = description
                
            self.enums[enum_name] = SymEnum(name=enum_name, values=values)
            
    def _parse_signals(self, signals_section: str):
        """Parse signal definitions"""
        # Pattern to match signal definitions
        signal_pattern = r'Sig=(\w+)\s+(\w+)\s+(\d+)(?:\s+(.+?))?(?:\s*//\s*(.+?))?$'
        
        for line in signals_section.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
                
            match = re.match(signal_pattern, line)
            if match:
                name = match.group(1)
                data_type = match.group(2)
                bit_length = int(match.group(3))
                attributes = match.group(4) or ""
                comment = match.group(5) or ""
                
                # Parse attributes
                signal = SymSignal(
                    name=name,
                    data_type=data_type,
                    bit_length=bit_length,
                    comment=comment
                )
                
                # Parse additional attributes
                self._parse_signal_attributes(signal, attributes)
                
                self.signals[name] = signal
                
    def _parse_signal_attributes(self, signal: SymSignal, attributes: str):
        """Parse signal attributes like /u:, /f:, /o:, /max:, /e:"""
        if not attributes:
            return
            
        # Unit
        unit_match = re.search(r'/u:(\w+)', attributes)
        if unit_match:
            signal.unit = unit_match.group(1)
            
        # Factor/scale
        factor_match = re.search(r'/f:([\d.]+)', attributes)
        if factor_match:
            signal.factor = float(factor_match.group(1))
            
        # Offset
        offset_match = re.search(r'/o:([-\d.]+)', attributes)
        if offset_match:
            signal.offset = float(offset_match.group(1))
            
        # Maximum
        max_match = re.search(r'/max:([\d.]+)', attributes)
        if max_match:
            signal.maximum = float(max_match.group(1))
            
        # Enum reference
        enum_match = re.search(r'/e:(\w+)', attributes)
        if enum_match:
            signal.enum_name = enum_match.group(1)
            
    def _parse_messages(self, sendreceive_section: str):
        """Parse message definitions"""
        # Split into individual message blocks
        message_blocks = re.split(r'\n\[([^\]]+)\]', sendreceive_section)
        
        for i in range(1, len(message_blocks), 2):
            if i + 1 >= len(message_blocks):
                break
                
            message_name = message_blocks[i]
            message_content = message_blocks[i + 1]
            
            message = self._parse_single_message(message_name, message_content)
            if message:
                self.messages[message_name] = message
                
    def _parse_single_message(self, name: str, content: str) -> Optional[SymMessage]:
        """Parse a single message definition"""
        try:
            message = SymMessage(name=name, can_id=0, length=8)
            
            lines = content.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                    
                # Parse message properties
                if line.startswith('ID='):
                    # Extract CAN ID (may be in hex)
                    id_match = re.search(r'ID=([0-9A-Fa-f]+)h?', line)
                    if id_match:
                        message.can_id = int(id_match.group(1), 16)
                        print(f"Parsed message {name}: ID={id_match.group(1)} -> 0x{message.can_id:X}")
                        
                elif line.startswith('Len='):
                    len_match = re.search(r'Len=(\d+)', line)
                    if len_match:
                        message.length = int(len_match.group(1))
                        
                elif line.startswith('CycleTime='):
                    cycle_match = re.search(r'CycleTime=(\d+)', line)
                    if cycle_match:
                        message.cycle_time = int(cycle_match.group(1))
                        
                elif line.startswith('Var='):
                    # Parse variable definition
                    var = self._parse_variable_line(line)
                    if var:
                        message.variables.append(var)
                        
                elif line.startswith('Sig='):
                    # Parse signal assignment
                    sig_assignment = self._parse_signal_assignment(line)
                    if sig_assignment:
                        message.signals.append(sig_assignment)
                        
            return message
            
        except Exception as e:
            print(f"Error parsing message {name}: {e}")
            return None
            
    def _parse_variable_line(self, line: str) -> Optional[SymVariable]:
        """Parse a Var= line"""
        # Pattern: Var=name datatype start_bit,bit_length [attributes] [comment]
        var_pattern = r'Var=(\w+)\s+(\w+)\s+(\d+),(\d+)(?:\s+(.+?))?(?:\s*//\s*(.+?))?$'
        
        match = re.match(var_pattern, line)
        if match:
            name = match.group(1)
            data_type = match.group(2)
            start_bit = int(match.group(3))
            bit_length = int(match.group(4))
            attributes = match.group(5) or ""
            
            var = SymVariable(
                name=name,
                data_type=data_type,
                start_bit=start_bit,
                bit_length=bit_length
            )
            
            # Parse attributes
            self._parse_variable_attributes(var, attributes)
            
            return var
            
        return None
        
    def _parse_variable_attributes(self, var: SymVariable, attributes: str):
        """Parse variable attributes"""
        if not attributes:
            return
            
        # Check for hex flag
        if '-h' in attributes:
            var.is_hex = True
            
        # Unit
        unit_match = re.search(r'/u:(\w+)', attributes)
        if unit_match:
            var.unit = unit_match.group(1)
            
        # Factor/scale
        factor_match = re.search(r'/f:([\d.]+)', attributes)
        if factor_match:
            var.factor = float(factor_match.group(1))
            
        # Offset
        offset_match = re.search(r'/o:([-\d.]+)', attributes)
        if offset_match:
            var.offset = float(offset_match.group(1))
            
        # Maximum
        max_match = re.search(r'/max:([\d.]+)', attributes)
        if max_match:
            var.maximum = float(max_match.group(1))
            
        # Enum reference
        enum_match = re.search(r'/e:(\w+)', attributes)
        if enum_match:
            var.enum_name = enum_match.group(1)
            
    def _parse_signal_assignment(self, line: str) -> Optional[Tuple[str, int]]:
        """Parse a Sig= line that assigns a signal to a bit position"""
        # Pattern: Sig=signal_name start_bit
        sig_pattern = r'Sig=(\w+)\s+(\d+)'
        
        match = re.match(sig_pattern, line)
        if match:
            signal_name = match.group(1)
            start_bit = int(match.group(2))
            return (signal_name, start_bit)
            
        return None
        
    def decode_message(self, can_id: int, data: bytes) -> Optional[Dict[str, Any]]:
        """Decode a CAN message using the loaded symbol definitions"""
        # Find message by CAN ID
        message = None
        for msg in self.messages.values():
            if msg.can_id == can_id:
                message = msg
                break
                
        if not message:
            return None
            
        decoded = {}
        
        # Decode variables
        for var in message.variables:
            try:
                # Extract bits from data
                value = self._extract_bits(data, var.start_bit, var.bit_length)
                
                # Apply scaling
                if var.factor != 1.0 or var.offset != 0.0:
                    scaled_value = (value * var.factor) + var.offset
                else:
                    scaled_value = value
                    
                # Get enum text if available
                enum_text = None
                if var.enum_name and var.enum_name in self.enums:
                    enum_text = self.enums[var.enum_name].values.get(value, f"Unknown({value})")
                    
                decoded[var.name] = {
                    'raw_value': value,
                    'scaled_value': scaled_value,
                    'unit': var.unit,
                    'enum_text': enum_text,
                    'minimum': var.minimum,
                    'maximum': var.maximum
                }
                
            except Exception as e:
                print(f"Error decoding variable {var.name}: {e}")
                
        # Decode signal assignments
        for signal_name, start_bit in message.signals:
            if signal_name in self.signals:
                signal = self.signals[signal_name]
                try:
                    # Extract bits from data
                    value = self._extract_bits(data, start_bit, signal.bit_length)
                    
                    # Apply scaling
                    if signal.factor != 1.0 or signal.offset != 0.0:
                        scaled_value = (value * signal.factor) + signal.offset
                    else:
                        scaled_value = value
                        
                    # Get enum text if available
                    enum_text = None
                    if signal.enum_name and signal.enum_name in self.enums:
                        enum_text = self.enums[signal.enum_name].values.get(value, f"Unknown({value})")
                        
                    decoded[signal_name] = {
                        'raw_value': value,
                        'scaled_value': scaled_value,
                        'unit': signal.unit,
                        'enum_text': enum_text,
                        'minimum': signal.minimum,
                        'maximum': signal.maximum
                    }
                    
                except Exception as e:
                    print(f"Error decoding signal {signal_name}: {e}")
                    
        return decoded if decoded else None
        
    def _extract_bits(self, data: bytes, start_bit: int, bit_length: int) -> int:
        """Extract bits from byte array"""
        if not data:
            return 0
            
        # Convert bytes to bit array
        bit_array = []
        for byte in data:
            for i in range(8):
                bit_array.append((byte >> i) & 1)
                
        # Extract the specified bits
        if start_bit + bit_length > len(bit_array):
            # Pad with zeros if needed
            while len(bit_array) < start_bit + bit_length:
                bit_array.append(0)
                
        value = 0
        for i in range(bit_length):
            if start_bit + i < len(bit_array):
                value |= bit_array[start_bit + i] << i
                
        return value
        
    def get_message_by_id(self, can_id: int) -> Optional[SymMessage]:
        """Get message definition by CAN ID"""
        for message in self.messages.values():
            if message.can_id == can_id:
                return message
        return None
        
    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about the loaded symbol file"""
        return {
            'enums': len(self.enums),
            'signals': len(self.signals), 
            'messages': len(self.messages),
            'total_variables': sum(len(msg.variables) for msg in self.messages.values())
        }
