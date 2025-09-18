"""
CAN Network and Connection Management
Provides clean separation between logical networks and physical connections
"""

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable
from enum import Enum, auto

import can
from can import Message, Listener
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .messages import CANMessage
from .virtual_can import VirtualCANNetwork, VirtualCANBus


class ConnectionState(Enum):
    """Connection state enumeration"""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()
    RECONNECTING = auto()


class NetworkProtocol(Enum):
    """CAN protocol types"""
    CAN_2_0A = "CAN 2.0A"  # 11-bit identifiers
    CAN_2_0B = "CAN 2.0B"  # 29-bit identifiers
    CAN_FD = "CAN FD"      # CAN with Flexible Data-Rate


@dataclass
class HardwareInterface:
    """Represents a physical CAN hardware interface"""
    interface_type: str  # 'pcan', 'vector', 'kvaser', 'socketcan', 'virtual'
    channel: str         # Hardware channel identifier
    name: str           # Human-readable name
    description: str    # Detailed description
    available: bool = True
    capabilities: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """Initialize capabilities based on interface type"""
        if self.interface_type == 'virtual':
            self.capabilities.update(['error_injection', 'simulation', 'unlimited_channels'])
        elif self.interface_type == 'pcan':
            self.capabilities.update(['hardware_filters', 'timestamp_sync', 'error_frames'])
        elif self.interface_type == 'vector':
            self.capabilities.update(['hardware_filters', 'precise_timing', 'can_fd'])
        elif self.interface_type == 'kvaser':
            self.capabilities.update(['hardware_filters', 'silent_mode', 'error_frames'])
        elif self.interface_type == 'socketcan':
            self.capabilities.update(['native_linux', 'error_frames'])


@dataclass 
class NetworkConfiguration:
    """Configuration for a logical CAN network"""
    network_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Network"
    description: str = ""
    bus_number: int = 1  # Bus number for identification
    bitrate: int = 500000
    sample_point: float = 0.75
    protocol: NetworkProtocol = NetworkProtocol.CAN_2_0B
    listen_only: bool = False
    enable_error_frames: bool = True
    auto_reconnect: bool = True
    reconnect_delay: int = 5  # seconds
    message_filters: List[Dict] = field(default_factory=list)
    symbol_file_path: str = ""  # Path to SYM file for this network
    last_hardware_interface: str = ""  # Last connected hardware interface (type:channel)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'network_id': self.network_id,
            'name': self.name,
            'description': self.description,
            'bus_number': self.bus_number,
            'bitrate': self.bitrate,
            'sample_point': self.sample_point,
            'protocol': self.protocol.value,
            'listen_only': self.listen_only,
            'enable_error_frames': self.enable_error_frames,
            'auto_reconnect': self.auto_reconnect,
            'reconnect_delay': self.reconnect_delay,
            'message_filters': self.message_filters,
            'symbol_file_path': self.symbol_file_path,
            'last_hardware_interface': self.last_hardware_interface
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NetworkConfiguration':
        """Create from dictionary"""
        config = cls()
        config.network_id = data.get('network_id', config.network_id)
        config.name = data.get('name', config.name)
        config.description = data.get('description', config.description)
        config.bus_number = data.get('bus_number', config.bus_number)
        config.bitrate = data.get('bitrate', config.bitrate)
        config.sample_point = data.get('sample_point', config.sample_point)
        config.protocol = NetworkProtocol(data.get('protocol', config.protocol.value))
        config.listen_only = data.get('listen_only', config.listen_only)
        config.enable_error_frames = data.get('enable_error_frames', config.enable_error_frames)
        config.auto_reconnect = data.get('auto_reconnect', config.auto_reconnect)
        config.reconnect_delay = data.get('reconnect_delay', config.reconnect_delay)
        config.message_filters = data.get('message_filters', config.message_filters)
        config.symbol_file_path = data.get('symbol_file_path', config.symbol_file_path)
        config.last_hardware_interface = data.get('last_hardware_interface', config.last_hardware_interface)
        return config


class CANNetworkListener(Listener):
    """CAN message listener for a specific network"""
    
    def __init__(self, network_id: str, callback: Callable[[str, CANMessage], None]):
        self.network_id = network_id
        self.callback = callback
        
    def on_message_received(self, msg: Message):
        """Handle received CAN message"""
        can_msg = CANMessage(
            timestamp=msg.timestamp,
            arbitration_id=msg.arbitration_id,
            data=msg.data,
            is_extended_id=msg.is_extended_id,
            is_remote_frame=msg.is_remote_frame,
            is_error_frame=msg.is_error_frame,
            channel=getattr(msg, 'channel', self.network_id),
            direction='rx',
            bus_number=getattr(self, 'bus_number', 0)  # Will be set by CANConnection
        )
        self.callback(self.network_id, can_msg)


class CANConnection(QObject):
    """Represents a physical connection to a CAN interface"""
    
    # Signals
    state_changed = pyqtSignal(str, object)  # network_id, ConnectionState
    message_received = pyqtSignal(str, object)  # network_id, CANMessage
    message_transmitted = pyqtSignal(str, object)  # network_id, CANMessage
    error_occurred = pyqtSignal(str, str)  # network_id, error_message
    
    def __init__(self, network_id: str, config: NetworkConfiguration, hardware: HardwareInterface):
        super().__init__()
        self.network_id = network_id
        self.config = config
        self.hardware = hardware
        self.state = ConnectionState.DISCONNECTED
        
        # CAN bus components
        self.bus: Optional[can.Bus] = None
        self.notifier: Optional[can.Notifier] = None
        self.listener: Optional[CANNetworkListener] = None
        
        # Virtual CAN support
        self.virtual_network: Optional[VirtualCANNetwork] = None
        
        # Statistics
        self.stats = {
            'message_count': 0,
            'tx_count': 0,
            'rx_count': 0,
            'error_count': 0,
            'start_time': None,
            'last_message_time': None,
            'connection_time': None
        }
        
        # Reconnection timer
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._attempt_reconnect)
        self.reconnect_timer.setSingleShot(True)
        
    def connect(self) -> bool:
        """Connect to the CAN interface"""
        if self.state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
            return True
            
        self._set_state(ConnectionState.CONNECTING)
        
        try:
            # Handle virtual CAN network
            if self.hardware.interface_type.lower() == 'virtual':
                return self._connect_virtual()
            
            # Create bus instance based on interface type
            bus_config = {
                'channel': self.hardware.channel,
                'bustype': self.hardware.interface_type,
                'bitrate': self.config.bitrate
            }
            
            # Add protocol-specific configuration
            if self.config.protocol == NetworkProtocol.CAN_FD:
                bus_config['fd'] = True
                
            if self.config.listen_only:
                bus_config['receive_own_messages'] = False
                
            self.bus = can.interface.Bus(**bus_config)
            
            # Set up message listener
            self.listener = CANNetworkListener(self.network_id, self._on_message_received)
            self.listener.bus_number = self.config.bus_number  # Set bus number for listener
            self.notifier = can.Notifier(self.bus, [self.listener])
            
            # Update statistics
            self.stats['start_time'] = time.time()
            self.stats['connection_time'] = time.time()
            self._reset_counters()
            
            self._set_state(ConnectionState.CONNECTED)
            return True
            
        except Exception as e:
            self.error_occurred.emit(self.network_id, f"Failed to connect: {str(e)}")
            self._set_state(ConnectionState.ERROR)
            
            if self.config.auto_reconnect:
                self._schedule_reconnect()
                
            return False
            
    def _connect_virtual(self) -> bool:
        """Connect to virtual CAN network"""
        try:
            # Create virtual CAN network
            self.virtual_network = VirtualCANNetwork(self._on_virtual_message_received)
            
            # Create virtual bus
            self.bus = VirtualCANBus(channel=self.hardware.channel)
            self.bus.set_virtual_network(self.virtual_network)
            
            # Start virtual network
            self.virtual_network.start()
            
            # Update statistics
            self.stats['start_time'] = time.time()
            self.stats['connection_time'] = time.time()
            self._reset_counters()
            
            self._set_state(ConnectionState.CONNECTED)
            return True
            
        except Exception as e:
            self.error_occurred.emit(self.network_id, f"Failed to connect to virtual CAN: {str(e)}")
            self._set_state(ConnectionState.ERROR)
            return False
            
    def disconnect(self):
        """Disconnect from CAN interface"""
        try:
            # Stop reconnection attempts
            self.reconnect_timer.stop()
            
            # Stop virtual network if active
            if self.virtual_network:
                self.virtual_network.stop()
                self.virtual_network = None
            
            # Clean up notifier
            if self.notifier:
                self.notifier.stop()
                self.notifier = None
                
            # Clean up listener
            self.listener = None
            
            # Close bus
            if self.bus:
                self.bus.shutdown()
                self.bus = None
                
            self._set_state(ConnectionState.DISCONNECTED)
            
        except Exception as e:
            self.error_occurred.emit(self.network_id, f"Error during disconnect: {str(e)}")
            
    def send_message(self, msg_id: int, data: bytes, is_extended: bool = False) -> bool:
        """Send a CAN message"""
        if self.state != ConnectionState.CONNECTED or not self.bus:
            self.error_occurred.emit(self.network_id, "Not connected to CAN interface")
            return False
            
        if self.config.listen_only:
            self.error_occurred.emit(self.network_id, "Cannot send messages in listen-only mode")
            return False
            
        try:
            msg = Message(
                arbitration_id=msg_id,
                data=data,
                is_extended_id=is_extended
            )
            
            self.bus.send(msg)
            
            # Create CANMessage for tracking
            can_msg = CANMessage(
                timestamp=time.time(),
                arbitration_id=msg_id,
                data=data,
                is_extended_id=is_extended,
                is_remote_frame=False,
                is_error_frame=False,
                channel=self.network_id,
                direction='tx',
                bus_number=self.config.bus_number
            )
            
            self.stats['tx_count'] += 1
            self.stats['message_count'] += 1
            self.stats['last_message_time'] = time.time()
            self.message_transmitted.emit(self.network_id, can_msg)
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(self.network_id, f"Failed to send message: {str(e)}")
            self.stats['error_count'] += 1
            return False
            
    def is_connected(self) -> bool:
        """Check if connection is active"""
        return self.state == ConnectionState.CONNECTED
        
    def get_statistics(self) -> Dict:
        """Get connection statistics"""
        stats = self.stats.copy()
        if stats['start_time']:
            stats['uptime'] = time.time() - stats['start_time']
        else:
            stats['uptime'] = 0
            
        if stats['connection_time']:
            stats['connection_uptime'] = time.time() - stats['connection_time']
        else:
            stats['connection_uptime'] = 0
            
        return stats
        
    def _set_state(self, new_state: ConnectionState):
        """Update connection state"""
        if self.state != new_state:
            self.state = new_state
            self.state_changed.emit(self.network_id, new_state)
            
    def _reset_counters(self):
        """Reset message counters"""
        self.stats['message_count'] = 0
        self.stats['tx_count'] = 0
        self.stats['rx_count'] = 0
        self.stats['error_count'] = 0
        
    def _on_message_received(self, network_id: str, msg: CANMessage):
        """Handle received CAN message"""
        self.stats['rx_count'] += 1
        self.stats['message_count'] += 1
        self.stats['last_message_time'] = time.time()
        self.message_received.emit(network_id, msg)
        
    def _on_virtual_message_received(self, msg: CANMessage):
        """Handle virtual CAN message"""
        # Update network ID and bus number for virtual messages
        msg.channel = self.network_id
        msg.bus_number = self.config.bus_number
        self._on_message_received(self.network_id, msg)
        
    def _schedule_reconnect(self):
        """Schedule a reconnection attempt"""
        if self.config.auto_reconnect and self.state == ConnectionState.ERROR:
            self._set_state(ConnectionState.RECONNECTING)
            self.reconnect_timer.start(self.config.reconnect_delay * 1000)
            
    def _attempt_reconnect(self):
        """Attempt to reconnect"""
        if self.state == ConnectionState.RECONNECTING:
            if not self.connect():
                # If reconnection fails, schedule another attempt
                self._schedule_reconnect()


class CANNetwork(QObject):
    """Represents a logical CAN network with its configuration and connection"""
    
    # Signals
    connection_state_changed = pyqtSignal(str, object)  # network_id, ConnectionState
    message_received = pyqtSignal(str, object)  # network_id, CANMessage
    message_transmitted = pyqtSignal(str, object)  # network_id, CANMessage
    error_occurred = pyqtSignal(str, str)  # network_id, error_message
    
    def __init__(self, config: NetworkConfiguration, hardware: Optional[HardwareInterface] = None):
        super().__init__()
        self.config = config
        self.hardware = hardware
        self.connection: Optional[CANConnection] = None
        
        # Symbol file management
        self.sym_parser: Optional[SymParser] = None
        self.load_symbol_file()
        
        # Periodic message tasks
        self.periodic_tasks = []
        self.periodic_timer = QTimer()
        self.periodic_timer.timeout.connect(self._send_periodic_messages)
        
    def set_hardware(self, hardware: HardwareInterface):
        """Set the hardware interface for this network"""
        if self.is_connected():
            raise RuntimeError("Cannot change hardware while connected")
        self.hardware = hardware
        
    def connect(self) -> bool:
        """Connect this network to its hardware interface"""
        if not self.hardware:
            self.error_occurred.emit(self.config.network_id, "No hardware interface assigned")
            return False
            
        if self.connection and self.connection.is_connected():
            return True
            
        # Create new connection
        self.connection = CANConnection(self.config.network_id, self.config, self.hardware)
        
        # Connect signals
        self.connection.state_changed.connect(self.connection_state_changed.emit)
        self.connection.message_received.connect(self.message_received.emit)
        self.connection.message_transmitted.connect(self.message_transmitted.emit)
        self.connection.error_occurred.connect(self.error_occurred.emit)
        
        # Attempt connection
        success = self.connection.connect()
        
        if success:
            # Start periodic message timer
            self.periodic_timer.start(100)  # Check every 100ms
            
        return success
        
    def disconnect(self):
        """Disconnect this network"""
        # Stop periodic timer
        self.periodic_timer.stop()
        
        if self.connection:
            self.connection.disconnect()
            self.connection = None
            
    def is_connected(self) -> bool:
        """Check if network is connected"""
        try:
            return bool(self.connection and self.connection.is_connected())
        except Exception:
            return False
        
    def send_message(self, msg_id: int, data: bytes, is_extended: bool = False) -> bool:
        """Send a message on this network"""
        if self.connection:
            return self.connection.send_message(msg_id, data, is_extended)
        return False
        
    def add_periodic_message(self, msg_id: int, data: bytes, period_ms: int, is_extended: bool = False):
        """Add a periodic message to this network"""
        task = {
            'id': msg_id,
            'data': data,
            'period_ms': period_ms,
            'is_extended': is_extended,
            'last_sent': 0,
            'enabled': True
        }
        self.periodic_tasks.append(task)
        
    def remove_periodic_message(self, msg_id: int):
        """Remove a periodic message"""
        self.periodic_tasks = [task for task in self.periodic_tasks if task['id'] != msg_id]
        
    def set_periodic_message_enabled(self, msg_id: int, enabled: bool):
        """Enable/disable a periodic message"""
        for task in self.periodic_tasks:
            if task['id'] == msg_id:
                task['enabled'] = enabled
                break
                
    def get_statistics(self) -> Dict:
        """Get network statistics"""
        if self.connection:
            return self.connection.get_statistics()
        return {}
        
    def load_symbol_file(self):
        """Load symbol file for this network"""
        if self.config.symbol_file_path and os.path.exists(self.config.symbol_file_path):
            try:
                # Import SymParser when needed to avoid circular imports
                from utils.sym_parser import SymParser
                self.sym_parser = SymParser()
                self.sym_parser.parse_file(self.config.symbol_file_path)
            except Exception as e:
                print(f"Warning: Failed to load symbol file for network {self.config.name}: {e}")
                self.sym_parser = None
        else:
            self.sym_parser = None
    
    def set_symbol_file(self, file_path: str):
        """Set symbol file for this network"""
        self.config.symbol_file_path = file_path
        self.load_symbol_file()
    
    def get_symbol_parser(self):
        """Get the symbol parser for this network"""
        return self.sym_parser
    
    def decode_message(self, msg_id: int, data: bytes) -> Dict:
        """Decode a message using this network's symbol file"""
        if not self.sym_parser:
            return {}
        
        # Find message definition
        for msg_name, msg_def in self.sym_parser.messages.items():
            if msg_def.can_id == msg_id:
                decoded = {}
                for var in msg_def.variables:
                    # Simplified decoding - could be enhanced
                    if var.start_bit + var.bit_length <= len(data) * 8:
                        # Extract and decode variable value
                        # This is a simplified implementation
                        start_byte = var.start_bit // 8
                        if start_byte < len(data):
                            raw_value = data[start_byte]  # Simplified
                            scaled_value = raw_value * var.factor + var.offset
                            decoded[var.name] = {
                                'value': scaled_value,
                                'unit': var.unit,
                                'raw': raw_value
                            }
                return decoded
        return {}
    
    def _send_periodic_messages(self):
        """Send periodic messages that are due"""
        current_time = time.time() * 1000  # Convert to milliseconds
        
        for task in self.periodic_tasks:
            if not task['enabled']:
                continue
                
            if current_time - task['last_sent'] >= task['period_ms']:
                if self.send_message(task['id'], task['data'], task['is_extended']):
                    task['last_sent'] = current_time
