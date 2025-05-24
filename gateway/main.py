import yaml
import time
import logging
import argparse
import json # For parsing control commands
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ConnectionException
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import paho.mqtt.client as mqtt

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG = {}
# Global Modbus client instance for access by MQTT command handler
# This is a simple approach; in more complex scenarios, consider passing it around
# or using a class structure that encapsulates both MQTT and Modbus clients.
GLOBAL_MODBUS_CLIENT: ModbusTcpClient = None

def load_gateway_config(config_file):
    """Loads gateway configuration from a YAML file."""
    global CONFIG
    try:
        with open(config_file, 'r') as f:
            CONFIG = yaml.safe_load(f)
        logger.info(f"Gateway configuration loaded from {config_file}")
        return True
    except FileNotFoundError:
        logger.error(f"Error: Gateway configuration file {config_file} not found.")
        return False
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {config_file}: {e}")
        return False

def connect_modbus_client(host, port):
    """Establishes a connection to the Modbus server."""
    global GLOBAL_MODBUS_CLIENT
    client = ModbusTcpClient(host, port)
    try:
        if client.connect():
            logger.info(f"Successfully connected to Modbus server at {host}:{port}")
            GLOBAL_MODBUS_CLIENT = client # Store the connected client globally
            return client
        else:
            logger.error(f"Failed to connect to Modbus server at {host}:{port}")
            GLOBAL_MODBUS_CLIENT = None
            return None
    except Exception as e: # Catch potential pymodbus or network errors
        logger.error(f"Exception during Modbus connection to {host}:{port}: {e}")
        GLOBAL_MODBUS_CLIENT = None
        return None

def connect_influxdb_client(url, token, org):
    """Establishes a connection to InfluxDB."""
    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        if client.ping(): # Check health
             logger.info(f"Successfully connected to InfluxDB at {url}")
             return client
        else:
            logger.error(f"Failed to ping InfluxDB at {url}. Check connection or credentials.")
            return None
    except Exception as e:
        logger.error(f"Exception connecting to InfluxDB: {e}")
        return None

# --- MQTT Control Command Handler ---
def on_control_command(client, userdata, msg):
    """Callback for handling control commands received via MQTT."""
    global GLOBAL_MODBUS_CLIENT
    topic = msg.topic
    payload_str = msg.payload.decode()
    logger.info(f"Received control command on topic '{topic}': {payload_str}")

    if not GLOBAL_MODBUS_CLIENT or not GLOBAL_MODBUS_CLIENT.is_socket_open():
        logger.error("Modbus client is not connected. Cannot execute control command.")
        # Optionally, publish a failure response back to MQTT here
        return

    try:
        command_data = json.loads(payload_str)
        slave_id = command_data.get('slave_id')
        register_type = command_data.get('register_type')
        address = command_data.get('address')
        value = command_data.get('value')

        if None in [slave_id, register_type, address, value]:
            logger.error(f"Invalid command payload from {topic}: missing required fields. Payload: {payload_str}")
            return

        logger.info(f"Executing Modbus write: Slave ID={slave_id}, Type={register_type}, Addr={address}, Value={value}")
        
        response = None
        if register_type == "coil":
            if not isinstance(value, bool):
                logger.error(f"Invalid value type for coil: {type(value)}. Must be boolean.")
                return
            response = GLOBAL_MODBUS_CLIENT.write_coil(address, value, slave=slave_id)
        elif register_type == "holding_register":
            if not isinstance(value, int):
                logger.error(f"Invalid value type for holding_register: {type(value)}. Must be integer.")
                return
            # For writing a single holding register
            response = GLOBAL_MODBUS_CLIENT.write_register(address, value, slave=slave_id)
        else:
            logger.error(f"Unsupported register_type for write operation: {register_type}")
            return

        if response is None: # Should not happen if type is valid but as a safeguard
            logger.error(f"Modbus write operation did not return a response object for {register_type}")
        elif response.isError():
            logger.error(f"Modbus write error for {register_type} at {address} (Slave {slave_id}): {response}")
            # Optionally, publish a failure response back to MQTT
        else:
            logger.info(f"Successfully wrote {register_type} at {address} (Slave {slave_id}) with value {value}. Response: {response}")
            # Optionally, publish a success response back to MQTT

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON payload from {topic}: {e}. Payload: {payload_str}")
    except ModbusIOException as e:
        logger.error(f"Modbus IO Exception during write: {e}. Reconnecting Modbus client might be needed.")
        # Potentially trigger a reconnect for GLOBAL_MODBUS_CLIENT here if connection is lost
    except ConnectionException as e:
        logger.error(f"Modbus Connection Exception during write: {e}. Modbus server might be down.")
    except Exception as e:
        logger.error(f"Unexpected error processing control command from {topic}: {e}", exc_info=True)

def connect_mqtt_client(broker_host, broker_port, client_id="modbus_gateway"):
    """Establishes a connection to the MQTT broker and subscribes to topics."""
    client = mqtt.Client(client_id=client_id)
    mqtt_config = CONFIG.get('mqtt', {})
    control_topic = mqtt_config.get('control_command_topic')

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Successfully connected to MQTT broker at {broker_host}:{broker_port}")
            # Default subscription for data publishing (already handled by gateway logic)
            # No, gateway *publishes* data, API *subscribes*. Gateway does not subscribe to its own data topics.
            
            # Subscribe to the control command topic
            if control_topic:
                client.subscribe(control_topic, qos=1)
                logger.info(f"Gateway subscribed to MQTT control topic: {control_topic}")
            else:
                logger.warning("MQTT control_command_topic not defined in config. Gateway will not listen for write commands.")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    client.on_connect = on_connect
    # client.on_message = on_message # Default on_message if needed for other topics, otherwise remove if not used

    # Add specific callback for the control topic
    if control_topic:
        client.message_callback_add(control_topic, on_control_command)

    try:
        client.connect(broker_host, broker_port, 60)
        client.loop_start() # Start a background thread for network traffic
        logger.info(f"MQTT client '{client_id}' attempting to connect to {broker_host}:{broker_port}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
        client.loop_stop()
        return None

def poll_modbus_data(modbus_client, slave_config):
    """Polls data from a Modbus slave device according to its configuration."""
    if not modbus_client or not modbus_client.is_socket_open():
        logger.warning("Modbus client is not connected or socket closed during poll. Skipping poll cycle.")
        return None # Indicate failure or inability to poll
        
    slave_id = slave_config['id']
    polled_data = {"device_name": slave_config['name'], "slave_id": slave_id, "registers": {}}
    logger.info(f"Polling data from slave {slave_id} ({slave_config['name']})")

    registers_to_poll = slave_config.get('registers_to_poll', {})
    connection_error_occurred = False

    # Holding Registers (FC=0x03)
    for hr_poll in registers_to_poll.get('holding_registers', []):
        address = hr_poll['address']
        count = hr_poll['count']
        try:
            rr = modbus_client.read_holding_registers(address, count, slave=slave_id)
            if rr.isError():
                logger.warning(f"Modbus error reading holding registers from slave {slave_id} at {address}: {rr}")
                if isinstance(rr, (ModbusIOException, ConnectionException)):
                    connection_error_occurred = True; break
            else:
                polled_data["registers"].setdefault("holding_registers", {})[address] = rr.registers
                logger.debug(f"Read HR from {slave_id} @{address}: {rr.registers}")
        except (ModbusIOException, ConnectionException) as e:
            logger.error(f"Modbus Connection/IO Exception (HR) for slave {slave_id} at {address}: {e}")
            connection_error_occurred = True; break
        except Exception as e:
            logger.error(f"Exception reading holding registers from slave {slave_id} at {address}: {e}")
    if connection_error_occurred: return None # Signal to attempt reconnect
    
    # Input Registers (FC=0x04)
    for ir_poll in registers_to_poll.get('input_registers', []):
        address = ir_poll['address']
        count = ir_poll['count']
        try:
            rr = modbus_client.read_input_registers(address, count, slave=slave_id)
            if rr.isError():
                logger.warning(f"Modbus error reading input registers from slave {slave_id} at {address}: {rr}")
                if isinstance(rr, (ModbusIOException, ConnectionException)):
                    connection_error_occurred = True; break
            else:
                polled_data["registers"].setdefault("input_registers", {})[address] = rr.registers
                logger.debug(f"Read IR from {slave_id} @{address}: {rr.registers}")
        except (ModbusIOException, ConnectionException) as e:
            logger.error(f"Modbus Connection/IO Exception (IR) for slave {slave_id} at {address}: {e}")
            connection_error_occurred = True; break
        except Exception as e:
            logger.error(f"Exception reading input registers from slave {slave_id} at {address}: {e}")
    if connection_error_occurred: return None

    # Coils (FC=0x01)
    for coil_poll in registers_to_poll.get('coils', []):
        address = coil_poll['address']
        count = coil_poll['count']
        try:
            rr = modbus_client.read_coils(address, count, slave=slave_id)
            if rr.isError():
                logger.warning(f"Modbus error reading coils from slave {slave_id} at {address}: {rr}")
                if isinstance(rr, (ModbusIOException, ConnectionException)):
                    connection_error_occurred = True; break
            else:
                polled_data["registers"].setdefault("coils", {})[address] = rr.bits[:count] # Only take requested bits
                logger.debug(f"Read Coils from {slave_id} @{address}: {rr.bits[:count]}")
        except (ModbusIOException, ConnectionException) as e:
            logger.error(f"Modbus Connection/IO Exception (Coils) for slave {slave_id} at {address}: {e}")
            connection_error_occurred = True; break
        except Exception as e:
            logger.error(f"Exception reading coils from slave {slave_id} at {address}: {e}")
    if connection_error_occurred: return None

    # Discrete Inputs (FC=0x02)
    for di_poll in registers_to_poll.get('discrete_inputs', []):
        address = di_poll['address']
        count = di_poll['count']
        try:
            rr = modbus_client.read_discrete_inputs(address, count, slave=slave_id)
            if rr.isError():
                logger.warning(f"Modbus error reading discrete inputs from slave {slave_id} at {address}: {rr}")
                if isinstance(rr, (ModbusIOException, ConnectionException)):
                    connection_error_occurred = True; break
            else:
                polled_data["registers"].setdefault("discrete_inputs", {})[address] = rr.bits[:count]
                logger.debug(f"Read DI from {slave_id} @{address}: {rr.bits[:count]}")
        except (ModbusIOException, ConnectionException) as e:
            logger.error(f"Modbus Connection/IO Exception (DI) for slave {slave_id} at {address}: {e}")
            connection_error_occurred = True; break
        except Exception as e:
            logger.error(f"Exception reading discrete inputs from slave {slave_id} at {address}: {e}")
    if connection_error_occurred: return None

    return polled_data

def send_to_influxdb(influx_client, data, bucket, org):
    """Sends polled data to InfluxDB."""
    if not influx_client:
        logger.warning("InfluxDB client not available. Skipping data send.")
        return
    
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)
    device_name = data['device_name']
    slave_id = data['slave_id']
    # Ensure timestamp is created when data is actually polled, or use InfluxDB server time.
    # For consistency, if data dict has a timestamp, use it. Otherwise, generate now.
    timestamp = data.get('timestamp', int(time.time() * 1e9)) # Nanosecond precision

    points = []
    for reg_type, registers_at_start_addr in data.get('registers', {}).items():
        for start_addr, values_list in registers_at_start_addr.items():
            if isinstance(values_list, list):
                for i, value_item in enumerate(values_list):
                    current_addr = start_addr + i
                    point = (
                        Point("modbus_data")
                        .tag("device_name", device_name)
                        .tag("slave_id", str(slave_id))
                        .tag("register_type", reg_type)
                        .tag("address", str(current_addr))
                        .field("value", value_item) # Ensure value_item is of appropriate type for InfluxDB
                        .time(timestamp, WritePrecision.NS)
                    )
                    points.append(point)
            else: 
                logger.warning(f"Unexpected data format for InfluxDB (values not a list): {values_list} for {reg_type} @ {start_addr}")

    if points:
        try:
            write_api.write(bucket=bucket, org=org, record=points)
            logger.info(f"Successfully wrote {len(points)} points to InfluxDB for {device_name} (Slave ID: {slave_id})")
        except Exception as e:
            logger.error(f"Error writing to InfluxDB: {e}")
    else:
        logger.debug("No data points to send to InfluxDB.")

def send_to_mqtt(mqtt_client, data, topic_prefix):
    """Sends polled data to MQTT."""
    if not mqtt_client or not mqtt_client.is_connected():
        logger.warning("MQTT client not connected. Skipping data send.")
        return

    device_name = data['device_name']
    slave_id = data['slave_id']

    for reg_type, registers_at_start_addr in data.get('registers', {}).items():
        for start_addr, values_list in registers_at_start_addr.items():
            if isinstance(values_list, list):
                for i, value_item in enumerate(values_list):
                    current_addr = start_addr + i
                    topic = f"{topic_prefix}/{device_name}/{slave_id}/{reg_type}/{current_addr}"
                    try:
                        # Ensure payload is string. Bools and numbers need conversion.
                        if isinstance(value_item, bool):
                            payload = str(value_item).lower() # true/false
                        else:
                            payload = str(value_item)
                        
                        mqtt_client.publish(topic, payload, qos=1)
                        logger.debug(f"Published to MQTT topic {topic}: {payload}")
                    except Exception as e:
                        logger.error(f"Error publishing to MQTT topic {topic}: {e}")
            else:
                logger.warning(f"Unexpected data format for MQTT (values not a list): {values_list} for {reg_type} @ {start_addr}")
    logger.info(f"Data for {device_name} (Slave ID: {slave_id}) processed for MQTT.")

def main_loop(modbus_client_conn, influx_client, mqtt_client):
    """Main polling loop for the gateway."""
    global GLOBAL_MODBUS_CLIENT # Ensure we update this if reconnecting
    GLOBAL_MODBUS_CLIENT = modbus_client_conn # Initial assignment

    modbus_config = CONFIG.get('modbus_server', {})
    slaves = modbus_config.get('slaves', [])
    influx_config = CONFIG.get('influxdb', {})
    mqtt_config = CONFIG.get('mqtt', {})

    if not slaves:
        logger.warning("No Modbus slaves configured to poll. Exiting loop.")
        return

    last_poll_times = {slave['id']: 0 for slave in slaves}

    try:
        while True:
            current_time = time.time()
            for slave_cfg in slaves:
                slave_id = slave_cfg['id']
                polling_interval = slave_cfg.get('polling_interval_seconds', 10)
                if current_time - last_poll_times.get(slave_id, 0) >= polling_interval:
                    if not GLOBAL_MODBUS_CLIENT or not GLOBAL_MODBUS_CLIENT.is_socket_open():
                        logger.warning("Modbus client disconnected. Attempting to reconnect...")
                        # Reassign to GLOBAL_MODBUS_CLIENT as well
                        GLOBAL_MODBUS_CLIENT = connect_modbus_client(modbus_config.get('host'), modbus_config.get('port'))
                        if not GLOBAL_MODBUS_CLIENT:
                            logger.error("Modbus reconnection failed. Will retry in next cycle.")
                            time.sleep(polling_interval) # Wait before retrying connection for this slave
                            continue # Skip this poll cycle for this slave
                    
                    polled_data = poll_modbus_data(GLOBAL_MODBUS_CLIENT, slave_cfg)
                    
                    if polled_data is None: # Indicates a connection error during poll
                        logger.warning(f"Polling slave {slave_id} failed due to connection issue. Attempting Modbus reconnect.")
                        if GLOBAL_MODBUS_CLIENT: GLOBAL_MODBUS_CLIENT.close() # Close faulty client
                        GLOBAL_MODBUS_CLIENT = connect_modbus_client(modbus_config.get('host'), modbus_config.get('port'))
                        if not GLOBAL_MODBUS_CLIENT:
                             logger.error("Modbus reconnection attempt failed. Will retry later.")
                             time.sleep(polling_interval) 
                        continue # Move to next slave or wait for next global cycle

                    if polled_data and polled_data.get('registers'):
                        polled_data['timestamp'] = int(current_time * 1e9) # Add timestamp to data dict
                        if influx_client and influx_config:
                            send_to_influxdb(influx_client, polled_data, influx_config['bucket'], influx_config['org'])
                        if mqtt_client and mqtt_config:
                            send_to_mqtt(mqtt_client, polled_data, mqtt_config['topic_prefix'])
                    last_poll_times[slave_id] = current_time
            
            time.sleep(1) 
    except KeyboardInterrupt:
        logger.info("Gateway shutting down by user request.")
    finally:
        if GLOBAL_MODBUS_CLIENT:
            GLOBAL_MODBUS_CLIENT.close()
            logger.info("Modbus client connection closed.")
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            logger.info("MQTT client connection closed.")
        if influx_client:
            influx_client.close()
            logger.info("InfluxDB client connection closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modbus Gateway Service")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to the gateway configuration YAML file."
    )
    args = parser.parse_args()

    if not load_gateway_config(args.config):
        exit(1)

    modbus_conf = CONFIG.get('modbus_server', {})
    influx_conf = CONFIG.get('influxdb', {})
    mqtt_conf = CONFIG.get('mqtt', {})

    # Initial Modbus connection attempt - result stored in GLOBAL_MODBUS_CLIENT by connect_modbus_client
    initial_modbus_client = connect_modbus_client(modbus_conf.get('host'), modbus_conf.get('port'))
    influx_client = connect_influxdb_client(influx_conf.get('url'), influx_conf.get('token'), influx_conf.get('org'))
    mqtt_client = connect_mqtt_client(mqtt_conf.get('broker_host'), mqtt_conf.get('broker_port'), mqtt_conf.get('client_id', 'modbus_gateway_client'))

    if not initial_modbus_client:
        logger.warning("Initial Modbus connection failed. Main loop will attempt to reconnect.")

    main_loop(initial_modbus_client, influx_client, mqtt_client)
