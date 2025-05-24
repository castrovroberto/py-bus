import argparse
import yaml
import time
import random
import math
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer, ModbusAsciiFramer

# Global store for device configurations
DEVICE_CONFIGS = {}
# Global store for datastore
DATASTORE = {}

def load_config(config_file):
    """Loads device configurations from a YAML file."""
    global DEVICE_CONFIGS
    try:
        with open(config_file, 'r') as f:
            DEVICE_CONFIGS = yaml.safe_load(f)
        print(f"Loaded configuration from {config_file}")
        if not DEVICE_CONFIGS or 'devices' not in DEVICE_CONFIGS:
            print("Error: 'devices' key not found in configuration.")
            DEVICE_CONFIGS = {'devices': []} # Ensure it's an empty list
            return False
        return True
    except FileNotFoundError:
        print(f"Error: Configuration file {config_file} not found.")
        DEVICE_CONFIGS = {'devices': []}
        return False
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {config_file}: {e}")
        DEVICE_CONFIGS = {'devices': []}
        return False


def initialize_datastore():
    """Initializes the Modbus datastore based on loaded configurations."""
    global DATASTORE
    global DEVICE_CONFIGS

    if not DEVICE_CONFIGS.get('devices'):
        print("No devices found in configuration. Initializing empty datastore.")
        # Initialize with empty blocks if no devices are configured
        DATASTORE = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [False]*100), # Discrete Inputs
            co=ModbusSequentialDataBlock(0, [False]*100), # Coils
            hr=ModbusSequentialDataBlock(0, [0]*100),     # Holding Registers
            ir=ModbusSequentialDataBlock(0, [0]*100)      # Input Registers
        )
        return

    # Determine max addresses for each register type to size the blocks
    # These are just examples, in a real scenario you'd calculate this more precisely
    # or allow for dynamic sizing if the library supports it well.
    # For simplicity here, using fixed large enough sizes or deriving from config.
    max_coils = 0
    max_discrete_inputs = 0
    max_holding_registers = 0
    max_input_registers = 0

    for device in DEVICE_CONFIGS.get('devices', []):
        registers = device.get('registers', {})
        for reg_list in registers.get('coils', []):
            max_coils = max(max_coils, reg_list.get('address', -1) + 1)
        for reg_list in registers.get('discrete_inputs', []):
            max_discrete_inputs = max(max_discrete_inputs, reg_list.get('address', -1) + 1)
        for reg_list in registers.get('holding_registers', []):
            max_holding_registers = max(max_holding_registers, reg_list.get('address', -1) + 1)
        for reg_list in registers.get('input_registers', []):
            max_input_registers = max(max_input_registers, reg_list.get('address', -1) + 1)

    # Ensure minimum size of 1 if no registers of a type are defined
    # Pymodbus DataBlock address 0, count N means addresses 0 to N-1
    # So if max_coils is 0 (meaning no coils defined or highest addr is -1), count should be 0.
    # But pymodbus might need at least 1 for block initialization.
    # Let's default to 100 if 0, for safety, or you can make it 0 if pymodbus handles it.
    
    di_block = ModbusSequentialDataBlock(0, [False] * (max_discrete_inputs or 100))
    co_block = ModbusSequentialDataBlock(0, [False] * (max_coils or 100))
    hr_block = ModbusSequentialDataBlock(0, [0] * (max_holding_registers or 100))
    ir_block = ModbusSequentialDataBlock(0, [0] * (max_input_registers or 100))

    # Populate initial values
    for device in DEVICE_CONFIGS.get('devices', []):
        registers = device.get('registers', {})
        for reg_def in registers.get('holding_registers', []):
            hr_block.setValues(reg_def['address'], int(reg_def['value']))
        for reg_def in registers.get('input_registers', []):
            ir_block.setValues(reg_def['address'], int(reg_def['value']))
        for reg_def in registers.get('coils', []):
            co_block.setValues(reg_def['address'], bool(reg_def['value']))
        for reg_def in registers.get('discrete_inputs', []):
            di_block.setValues(reg_def['address'], bool(reg_def['value']))

    DATASTORE = ModbusSlaveContext(di=di_block, co=co_block, hr=hr_block, ir=ir_block)


def update_simulated_values(context):
    """Updates register values based on simulation trends."""
    global DEVICE_CONFIGS
    if not DEVICE_CONFIGS or 'devices' not in DEVICE_CONFIGS:
        return

    for device in DEVICE_CONFIGS['devices']:
        registers = device.get('registers', {})
        
        for reg_def in registers.get('holding_registers', []):
            addr = reg_def['address']
            current_val_list = context[0x01].getValues(3, addr, count=1) # slave_id=1, fc=3 (HR)
            if not current_val_list: continue # Should not happen if initialized
            current_val = current_val_list[0]

            new_val = current_val
            trend = reg_def.get('trend', 'static')
            params = reg_def.get('params', {})

            if trend == 'linear':
                slope = params.get('slope', 1)
                new_val = current_val + slope
            elif trend == 'random':
                min_val = params.get('min', current_val - 5)
                max_val = params.get('max', current_val + 5)
                new_val = random.uniform(min_val, max_val)
            elif trend == 'sinusoidal':
                amplitude = params.get('amplitude', 10)
                frequency = params.get('frequency', 0.1)
                offset = params.get('offset', current_val) # Offset around initial value or a specific one
                new_val = offset + amplitude * math.sin(frequency * time.time())
            
            context[0x01].setValues(3, addr, [int(new_val)]) # FC3 for HR

        # Similar logic for input_registers if they also need to be dynamic
        for reg_def in registers.get('input_registers', []):
            addr = reg_def['address']
            current_val_list = context[0x01].getValues(4, addr, count=1) # FC4 for IR
            if not current_val_list: continue
            current_val = current_val_list[0]
            
            new_val = current_val
            trend = reg_def.get('trend', 'static')
            params = reg_def.get('params', {})

            if trend == 'linear':
                new_val = current_val + params.get('slope', 1)
            elif trend == 'random':
                new_val = random.uniform(params.get('min', current_val - 5), params.get('max', current_val + 5))
            elif trend == 'sinusoidal':
                new_val = params.get('offset', current_val) + params.get('amplitude', 10) * math.sin(params.get('frequency', 0.1) * time.time())
            
            context[0x01].setValues(4, addr, [int(new_val)]) # FC4 for IR
        
        # Coils and Discrete Inputs are typically not updated by trends in this manner,
        # but can be toggled or set based on other logic if needed.


def run_server(config_file, host, port):
    """Main function to run the Modbus TCP server."""
    if not load_config(config_file):
        print("Failed to load configuration. Exiting.")
        return

    initialize_datastore()
    
    # The ModbusServerContext maps slave contexts to slave IDs.
    # For a single slave device, we can map it to ID 0x01 or any other.
    # If your config supports multiple slave IDs on the same IP/port, you'd iterate here.
    # For now, assuming all configured registers belong to a single slave unit (e.g., ID 1)
    context = ModbusServerContext(slaves={0x01: DATASTORE}, single=False)


    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Pymodbus'
    identity.ProductCode = 'PM'
    identity.VendorUrl = 'http://github.com/riptideio/pymodbus/'
    identity.ProductName = 'Pymodbus Server'
    identity.ModelName = 'Pymodbus Server'
    identity.MajorMinorRevision = '3.0.0'

    print(f"Starting Modbus TCP server on {host}:{port}")

    # Start the server in a new thread or use asyncio variant for non-blocking updates
    # For simplicity, using StartTcpServer which is blocking.
    # For data updates, you'd typically run the update_simulated_values in a separate thread/task.
    
    # Quick and dirty way to update values periodically alongside a blocking server
    # This is NOT ideal for production. Proper way is threaded updates or asyncio server.
    class UpdatingServerContext:
        def __init__(self, server_context):
            self.server_context = server_context
            self.last_update_time = time.time()

        def __getitem__(self, slave_id):
            # Update values if 1 second has passed
            if time.time() - self.last_update_time > 1.0:
                # print("Updating simulated values...")
                update_simulated_values(self.server_context)
                self.last_update_time = time.time()
            return self.server_context[slave_id]

        def __setitem__(self, key, value):
            self.server_context[key] = value


    updating_context = UpdatingServerContext(context)

    StartTcpServer(
        context=updating_context,  # use the custom context
        identity=identity,
        address=(host, port),
        # framer=ModbusRtuFramer, # For RTU over TCP
        # framer=ModbusAsciiFramer, # For ASCII over TCP
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modbus TCP Simulator")
    parser.add_argument(
        "--config",
        type=str,
        default="config/example_device_map.yaml",
        help="Path to the device configuration YAML file."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind the server to."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5020,
        help="Port to bind the server to."
    )
    args = parser.parse_args()

    run_server(args.config, args.host, args.port) 