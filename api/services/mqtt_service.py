import logging
import paho.mqtt.client as mqtt
import json
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)

class MQTTService:
    def __init__(self, broker_host: str, broker_port: int, client_id: str, topic_prefix: str):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.topic_prefix = topic_prefix # e.g., "modbus/gateway"
        self.client = mqtt.Client(client_id=self.client_id)
        self.message_callback: Optional[Callable[[str, Any], None]] = None # topic, payload

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Successfully connected to MQTT broker at {self.broker_host}:{self.broker_port} as {self.client_id}")
            # Subscribe to all sub-topics under the gateway's data prefix
            # Example: modbus/gateway/Device1/1/holding_registers/0
            subscription_topic = f"{self.topic_prefix}/#"
            self.client.subscribe(subscription_topic, qos=1)
            logger.info(f"Subscribed to MQTT topic: {subscription_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_message(self, client, userdata, msg):
        logger.debug(f"Received MQTT message on topic {msg.topic}: {msg.payload.decode()}")
        try:
            # Assuming payload is a simple string value, as sent by the gateway
            # If it's JSON, use json.loads(msg.payload.decode())
            payload_data = msg.payload.decode()
            if self.message_callback:
                # We can pass the raw topic and payload, or parse it further here
                # For now, passing topic and raw payload string
                self.message_callback(msg.topic, payload_data)
        except Exception as e:
            logger.error(f"Error processing MQTT message on topic {msg.topic}: {e}", exc_info=True)

    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT broker with result code {rc}. Attempting to reconnect...")
        # Implement reconnection logic if needed, or rely on a wrapper/keepalive mechanism
        # For simplicity, paho-mqtt's loop_start handles some reconnection attempts by default

    def set_message_callback(self, callback: Callable[[str, Any], None]):
        """Set the callback function to be invoked when a message is received."""
        self.message_callback = callback

    def connect(self):
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start() # Start network loop in a background thread
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}", exc_info=True)

    def disconnect(self):
        if self.client.is_connected():
            self.client.loop_stop() # Stop the network loop
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker.")

# Example usage (will be integrated into FastAPI app lifecycle):
# def my_callback(topic, payload):
#     print(f"Data from {topic}: {payload}")
# 
# mqtt_service = MQTTService(
#     broker_host="localhost", 
#     broker_port=1883, 
#     client_id="api_mqtt_listener",
#     topic_prefix="modbus/gateway"
# )
# mqtt_service.set_message_callback(my_callback)
# mqtt_service.connect()
# # Keep main thread alive or integrate into an event loop 