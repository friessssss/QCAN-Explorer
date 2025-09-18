"""
CAN Interface Manager (DEPRECATED)
This module is deprecated and replaced by the multi_network_manager.py system.
Use MultiNetworkManager for new development.

Legacy module kept for backward compatibility only.
"""

import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from queue import Queue, Empty

import can
from can import Message, Listener
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .messages import CANMessage
from .virtual_can import VirtualCANNetwork, VirtualCANBus


class MessageListener(Listener):
    """Custom CAN message listener"""
    
    def __init__(self, callback: Callable[[CANMessage], None]):
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
            channel=getattr(msg, 'channel', 'unknown'),
            direction='rx'
        )
        self.callback(can_msg)


class CANInterfaceManager(QObject):
    """Manages CAN interface connections and message handling"""
    
    # Signals
    message_received = pyqtSignal(object)  # CANMessage
    message_transmitted = pyqtSignal(object)  # CANMessage
    error_occurred = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.bus: Optional[can.Bus] = None
        self.notifier: Optional[can.Notifier] = None
        self.listener: Optional[MessageListener] = None
        self.is_connected_flag = False
        
        # Virtual CAN support
        self.virtual_network: Optional[VirtualCANNetwork] = None
        self.is_virtual = False
        
        # Statistics
        self.stats = {
            'message_count': 0,
            'tx_count': 0,
            'rx_count': 0,
            'error_count': 0,
            'start_time': None
        }
        
        # Message queues for different purposes
        self.message_queue = Queue()
        self.periodic_tasks = []
        
        # Timer for periodic message sending
        self.periodic_timer = QTimer()
        self.periodic_timer.timeout.connect(self._send_periodic_messages)
        
    def connect(self, interface_type: str, channel: str, bitrate: int = 500000) -> bool:
        """Connect to CAN interface"""
        try:
            # Disconnect if already connected
            if self.is_connected_flag:
                self.disconnect()
                
            # Handle virtual CAN network
            if interface_type.lower() == 'virtual':
                return self._connect_virtual(channel, bitrate)
                
            # Create bus instance based on interface type
            if interface_type.lower() == 'socketcan':
                self.bus = can.interface.Bus(channel=channel, bustype='socketcan', bitrate=bitrate)
            elif interface_type.lower() == 'pcan':
                self.bus = can.interface.Bus(channel=channel, bustype='pcan', bitrate=bitrate)
            elif interface_type.lower() == 'vector':
                self.bus = can.interface.Bus(channel=channel, bustype='vector', bitrate=bitrate)
            elif interface_type.lower() == 'kvaser':
                self.bus = can.interface.Bus(channel=channel, bustype='kvaser', bitrate=bitrate)
            else:
                # Try to create a virtual bus for testing
                self.bus = can.interface.Bus(channel=channel, bustype='virtual', bitrate=bitrate)
                
            # Set up message listener
            self.listener = MessageListener(self._on_message_received)
            self.notifier = can.Notifier(self.bus, [self.listener])
            
            # Update connection state
            self.is_connected_flag = True
            self.is_virtual = False
            self.stats['start_time'] = time.time()
            self.stats['message_count'] = 0
            self.stats['tx_count'] = 0
            self.stats['rx_count'] = 0
            self.stats['error_count'] = 0
            
            # Start periodic message timer
            self.periodic_timer.start(100)  # Check every 100ms
            
            self.connection_changed.emit(True)
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to connect: {str(e)}")
            return False
            
    def _connect_virtual(self, channel: str, bitrate: int) -> bool:
        """Connect to virtual CAN network"""
        try:
            # Create virtual CAN network
            self.virtual_network = VirtualCANNetwork(self._on_virtual_message_received)
            
            # Create virtual bus
            self.bus = VirtualCANBus(channel=channel)
            self.bus.set_virtual_network(self.virtual_network)
            
            # Update connection state
            self.is_connected_flag = True
            self.is_virtual = True
            self.stats['start_time'] = time.time()
            self.stats['message_count'] = 0
            self.stats['tx_count'] = 0
            self.stats['rx_count'] = 0
            self.stats['error_count'] = 0
            
            # Start virtual network
            self.virtual_network.start()
            
            # Start periodic message timer
            self.periodic_timer.start(100)  # Check every 100ms
            
            self.connection_changed.emit(True)
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to connect to virtual CAN: {str(e)}")
            return False
            
    def disconnect(self):
        """Disconnect from CAN interface"""
        try:
            # Stop periodic timer
            self.periodic_timer.stop()
            
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
                
            # Clear periodic tasks
            self.periodic_tasks.clear()
            
            self.is_connected_flag = False
            self.is_virtual = False
            self.connection_changed.emit(False)
            
        except Exception as e:
            self.error_occurred.emit(f"Error during disconnect: {str(e)}")
            
    def is_connected(self) -> bool:
        """Check if interface is connected"""
        return self.is_connected_flag
        
    def send_message(self, msg_id: int, data: bytes, is_extended: bool = False) -> bool:
        """Send a single CAN message"""
        if not self.is_connected_flag or not self.bus:
            self.error_occurred.emit("Not connected to CAN interface")
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
                channel=getattr(self.bus, 'channel_info', 'unknown'),
                direction='tx'
            )
            
            self.stats['tx_count'] += 1
            self.stats['message_count'] += 1
            self.message_transmitted.emit(can_msg)
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to send message: {str(e)}")
            self.stats['error_count'] += 1
            return False
            
    def add_periodic_message(self, msg_id: int, data: bytes, period_ms: int, is_extended: bool = False):
        """Add a message to be sent periodically"""
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
        """Get interface statistics"""
        stats = self.stats.copy()
        if stats['start_time']:
            stats['uptime'] = time.time() - stats['start_time']
        else:
            stats['uptime'] = 0
        return stats
        
    def _on_message_received(self, msg: CANMessage):
        """Handle received CAN message"""
        self.stats['rx_count'] += 1
        self.stats['message_count'] += 1
        self.message_received.emit(msg)
        
    def _on_virtual_message_received(self, msg: CANMessage):
        """Handle virtual CAN message"""
        self.stats['rx_count'] += 1
        self.stats['message_count'] += 1
        # Use QueuedConnection to ensure thread-safe signal emission
        self.message_received.emit(msg)
        
    def _send_periodic_messages(self):
        """Send periodic messages that are due"""
        current_time = time.time() * 1000  # Convert to milliseconds
        
        for task in self.periodic_tasks:
            if not task['enabled']:
                continue
                
            if current_time - task['last_sent'] >= task['period_ms']:
                self.send_message(task['id'], task['data'], task['is_extended'])
                task['last_sent'] = current_time
                
    def get_available_interfaces(self) -> List[str]:
        """Get list of available CAN interfaces"""
        interfaces = []
        
        # Always add virtual for testing (first in list)
        interfaces.append('virtual')
        
        # Check for common interface types
        try:
            import can.interfaces.socketcan
            interfaces.append('socketcan')
        except ImportError:
            pass
            
        try:
            import can.interfaces.pcan
            interfaces.append('pcan')
        except ImportError:
            pass
            
        try:
            import can.interfaces.vector
            interfaces.append('vector')
        except ImportError:
            pass
            
        try:
            import can.interfaces.kvaser
            interfaces.append('kvaser')
        except ImportError:
            pass
        
        return interfaces
        
    def get_virtual_network(self) -> Optional[VirtualCANNetwork]:
        """Get the virtual CAN network instance"""
        return self.virtual_network
        
    def inject_virtual_message(self, can_id: int, data: bytes):
        """Inject a message into the virtual network"""
        if self.virtual_network:
            self.virtual_network.inject_single_message(can_id, data)
            
    def simulate_error_frame(self):
        """Simulate an error frame"""
        if self.virtual_network:
            self.virtual_network.simulate_error_frame()
