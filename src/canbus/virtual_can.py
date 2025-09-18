"""
Virtual CAN Network Support
Creates simulated CAN traffic for testing and demonstration
"""

import threading
import time
import random
from typing import Dict, List, Callable
from dataclasses import dataclass
from queue import Queue

from .messages import CANMessage


@dataclass
class VirtualMessage:
    """Configuration for a virtual CAN message"""
    can_id: int
    name: str
    data_generator: Callable[[], bytes]
    period_ms: int
    enabled: bool = True
    last_sent: float = 0.0


class VirtualCANNetwork:
    """Simulates a CAN network with realistic message traffic"""
    
    def __init__(self, message_callback: Callable[[CANMessage], None]):
        self.message_callback = message_callback
        self.is_running = False
        self.thread = None
        self.virtual_messages = []
        self.setup_default_messages()
        
    def setup_default_messages(self):
        """Set up realistic virtual CAN messages"""
        
        # Engine RPM (varies realistically)
        def engine_rpm_data():
            rpm = int(800 + random.gauss(1500, 200))  # Idle to moderate RPM
            rpm = max(600, min(6000, rpm))  # Clamp to realistic range
            return bytes([
                (rpm >> 8) & 0xFF, rpm & 0xFF,  # RPM high/low
                random.randint(20, 80),          # Engine load %
                random.randint(80, 95),          # Coolant temp
                random.randint(10, 90),          # Throttle position
                0x00, 0x00, 0x00
            ])
            
        # Vehicle speed (varies slowly)
        self._current_speed = 0.0
        def vehicle_speed_data():
            # Simulate realistic speed changes
            speed_change = random.gauss(0, 2)  # Small random changes
            self._current_speed = max(0, min(120, self._current_speed + speed_change))
            speed_kmh = int(self._current_speed * 100)  # Convert to 0.01 km/h resolution
            
            return bytes([
                (speed_kmh >> 8) & 0xFF, speed_kmh & 0xFF,  # Speed
                0x12, 0x34, 0x56, 0x78,  # Odometer (static for demo)
                0x00, 0x00
            ])
            
        # Door/window status (changes occasionally)
        self._door_state = 0
        def body_control_data():
            # Occasionally change door/window state
            if random.random() < 0.02:  # 2% chance per message
                self._door_state ^= random.choice([0x01, 0x02, 0x04, 0x08])
                
            return bytes([
                self._door_state,              # Door/window states
                random.randint(20, 100),       # Window position
                random.randint(0, 1) << 4 |    # Headlights
                random.randint(0, 1) << 3,     # High beams
                0x00, 0x00, 0x00, 0x00, 0x00
            ])
            
        # Battery/electrical system
        def electrical_data():
            voltage = 12.0 + random.gauss(2.0, 0.3)  # 12V system with variation
            voltage = max(10.0, min(15.0, voltage))
            voltage_raw = int(voltage * 10)  # 0.1V resolution
            
            return bytes([
                random.randint(10, 100),       # Fuel level %
                voltage_raw,                   # Battery voltage
                random.randint(0, 0xFF),       # Warning lights (random for demo)
                random.randint(0, 0xFF),
                0x00, 0x00, 0x00, 0x00
            ])
            
        # Climate control
        def climate_data():
            return bytes([
                random.randint(18, 25),        # Target temperature
                random.randint(15, 30),        # Actual temperature
                random.randint(0, 3),          # Fan speed
                random.randint(0, 1),          # AC on/off
                random.randint(0, 1),          # Heat on/off
                0x00, 0x00, 0x00
            ])
            
        # Diagnostic/status messages
        def diagnostic_data():
            return bytes([
                0x00,                          # No errors (mostly)
                random.randint(0, 100),        # System health %
                int(time.time()) & 0xFF,       # Timestamp/counter
                0x55, 0xAA,                    # Pattern for identification
                0x00, 0x00, 0x00
            ])
            
        # Add virtual messages with realistic periods (slowed down by factor of 10)
        self.virtual_messages = [
            VirtualMessage(0x100, "Engine_RPM", engine_rpm_data, 500),        # 2Hz (was 20Hz)
            VirtualMessage(0x101, "Vehicle_Speed", vehicle_speed_data, 1000), # 1Hz (was 10Hz)
            VirtualMessage(0x200, "Body_Control", body_control_data, 2000),   # 0.5Hz (was 5Hz)
            VirtualMessage(0x300, "Electrical", electrical_data, 5000),       # 0.2Hz (was 2Hz)
            VirtualMessage(0x400, "Climate", climate_data, 10000),            # 0.1Hz (was 1Hz)
            VirtualMessage(0x7E0, "Diagnostic_Request", diagnostic_data, 20000), # 0.05Hz (was 0.5Hz)
            VirtualMessage(0x7E8, "Diagnostic_Response", diagnostic_data, 20000), # 0.05Hz (was 0.5Hz)
        ]
        
    def add_custom_message(self, can_id: int, name: str, data_gen: Callable[[], bytes], period_ms: int):
        """Add a custom virtual message"""
        msg = VirtualMessage(can_id, name, data_gen, period_ms)
        self.virtual_messages.append(msg)
        
    def remove_message(self, can_id: int):
        """Remove a virtual message by ID"""
        self.virtual_messages = [msg for msg in self.virtual_messages if msg.can_id != can_id]
        
    def set_message_enabled(self, can_id: int, enabled: bool):
        """Enable/disable a virtual message"""
        for msg in self.virtual_messages:
            if msg.can_id == can_id:
                msg.enabled = enabled
                break
                
    def set_message_period(self, can_id: int, period_ms: int):
        """Set the period for a virtual message"""
        for msg in self.virtual_messages:
            if msg.can_id == can_id:
                msg.period_ms = period_ms
                break
                
    def set_all_message_periods(self, factor: float):
        """Scale all message periods by a factor"""
        for msg in self.virtual_messages:
            msg.period_ms = int(msg.period_ms * factor)
                
    def start(self):
        """Start the virtual CAN network"""
        if self.is_running:
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._run_network, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop the virtual CAN network"""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            
    def _run_network(self):
        """Main network simulation loop"""
        print("Virtual CAN network started")
        
        while self.is_running:
            current_time = time.time()
            
            # Check each virtual message
            for msg in self.virtual_messages:
                if not msg.enabled:
                    continue
                    
                # Check if it's time to send this message
                time_since_last = (current_time - msg.last_sent) * 1000  # Convert to ms
                
                if time_since_last >= msg.period_ms:
                    try:
                        # Generate message data
                        data = msg.data_generator()
                        
                        # Create CAN message
                        can_msg = CANMessage(
                            timestamp=current_time,
                            arbitration_id=msg.can_id,
                            data=data,
                            is_extended_id=msg.can_id > 0x7FF,
                            is_remote_frame=False,
                            is_error_frame=False,
                            channel='virtual',
                            direction='rx'  # All virtual messages appear as received
                        )
                        
                        # Send to callback
                        self.message_callback(can_msg)
                        msg.last_sent = current_time
                        
                    except Exception as e:
                        print(f"Error generating virtual message {msg.name}: {e}")
                        
            # Small sleep to prevent excessive CPU usage
            time.sleep(0.01)  # 10ms
            
        print("Virtual CAN network stopped")
        
    def get_message_list(self) -> List[Dict]:
        """Get list of virtual messages with their status"""
        return [
            {
                'id': msg.can_id,
                'name': msg.name,
                'period_ms': msg.period_ms,
                'enabled': msg.enabled
            }
            for msg in self.virtual_messages
        ]
        
    def inject_single_message(self, can_id: int, data: bytes):
        """Inject a single message into the virtual network"""
        can_msg = CANMessage(
            timestamp=time.time(),
            arbitration_id=can_id,
            data=data,
            is_extended_id=can_id > 0x7FF,
            is_remote_frame=False,
            is_error_frame=False,
            channel='virtual',
            direction='rx'
        )
        self.message_callback(can_msg)
        
    def simulate_error_frame(self):
        """Inject an error frame for testing"""
        can_msg = CANMessage(
            timestamp=time.time(),
            arbitration_id=0x000,
            data=b'',
            is_extended_id=False,
            is_remote_frame=False,
            is_error_frame=True,
            channel='virtual',
            direction='rx'
        )
        self.message_callback(can_msg)


class VirtualCANBus:
    """Virtual CAN bus implementation for python-can interface"""
    
    def __init__(self, channel: str = 'virtual', **kwargs):
        self.channel = channel
        self.is_shutdown = False
        self.virtual_network = None
        self.listeners = []
        
    def send(self, msg):
        """Send a message on the virtual bus"""
        if self.virtual_network:
            # Convert python-can Message to our CANMessage format
            can_msg = CANMessage(
                timestamp=time.time(),
                arbitration_id=msg.arbitration_id,
                data=msg.data,
                is_extended_id=msg.is_extended_id,
                is_remote_frame=msg.is_remote_frame,
                is_error_frame=msg.is_error_frame,
                channel=self.channel,
                direction='tx'
            )
            
            # Notify all listeners
            for listener in self.listeners:
                if hasattr(listener, 'on_message_received'):
                    listener.on_message_received(msg)
                    
        return True
        
    def shutdown(self):
        """Shutdown the virtual bus"""
        self.is_shutdown = True
        if self.virtual_network:
            self.virtual_network.stop()
            
    def add_listener(self, listener):
        """Add a message listener"""
        self.listeners.append(listener)
        
    def remove_listener(self, listener):
        """Remove a message listener"""
        if listener in self.listeners:
            self.listeners.remove(listener)
            
    def set_virtual_network(self, network):
        """Set the virtual network for this bus"""
        self.virtual_network = network
