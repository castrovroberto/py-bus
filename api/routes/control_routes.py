from fastapi import APIRouter, Depends, HTTPException, Body
import logging
import json
import paho.mqtt.client as mqtt
from datetime import datetime

from ..models import WriteRegisterRequest, WriteResponse
from ..main import MQTT_SERVICE_INSTANCE # Import the shared MQTT service instance
from ..main import API_CONFIG # To get MQTT topic for commands

router = APIRouter()
logger = logging.getLogger(__name__)

# Define the MQTT topic for control commands
# This could also come from config if it needs to be more dynamic
CONTROL_COMMAND_TOPIC_TEMPLATE = "modbus/control/command/{slave_id}/{register_type}/{address}"
# Or a single topic for all commands, with details in payload:
CONTROL_COMMAND_GENERAL_TOPIC = "modbus/gateway/control/command"

@router.post("/write_register", response_model=WriteResponse)
async def write_modbus_register(request: WriteRegisterRequest = Body(...)):
    """
    Sends a command to the Gateway via MQTT to write a value to a Modbus register/coil.
    The Gateway is expected to listen on the specified MQTT topic, execute the write,
    and (optionally) publish a result.
    This API endpoint currently sends the command and confirms it was sent to MQTT.
    It does not wait for a response from the Gateway.
    """
    if not MQTT_SERVICE_INSTANCE or not MQTT_SERVICE_INSTANCE.client.is_connected():
        logger.error("MQTT service is not available or not connected. Cannot send write command.")
        raise HTTPException(status_code=503, detail="MQTT service unavailable. Cannot send command.")

    try:
        # Validate register_type (simple validation)
        valid_register_types = ["coil", "holding_register"] # Extend as needed
        if request.register_type not in valid_register_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid register_type. Allowed: {valid_register_types}"
            )
        
        # Validate value type based on register type
        if request.register_type == "coil" and not isinstance(request.value, bool):
            raise HTTPException(status_code=400, detail="Value for coil must be boolean (true/false).")
        if request.register_type == "holding_register" and not isinstance(request.value, int):
            # We could also allow lists of ints for writing multiple registers, but keeping it simple for now
            if not isinstance(request.value, int):
                 raise HTTPException(status_code=400, detail="Value for holding_register must be a single integer.")
        
        # Construct the payload. The Gateway will need to know how to parse this.
        # Using a structured payload like JSON is recommended.
        command_payload = {
            "slave_id": request.slave_id,
            "register_type": request.register_type,
            "address": request.address,
            "value": request.value,
            "timestamp_api_sent": datetime.utcnow().isoformat() # Optional: for tracing
        }
        payload_str = json.dumps(command_payload)

        # Determine the MQTT topic
        # For this example, using a general command topic. The gateway will parse the payload for specifics.
        mqtt_topic_config = API_CONFIG.get('mqtt_broker', {})
        mqtt_topic = mqtt_topic_config.get('control_command_topic', CONTROL_COMMAND_GENERAL_TOPIC)
        
        # Publish the command to MQTT
        # The MQTTService's client is paho.mqtt.Client
        result = MQTT_SERVICE_INSTANCE.client.publish(mqtt_topic, payload_str, qos=1) # QoS 1 for at least once
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Successfully published write command to MQTT topic '{mqtt_topic}': {payload_str}")
            return WriteResponse(
                status="success",
                message="Write command successfully sent to MQTT broker.",
                request_details=request
            )
        else:
            # Log the error and include MID if available (result.mid might not always be set for errors)
            logger.error(f"Failed to publish write command to MQTT. RC: {result.rc}{f' (MID: {result.mid})' if hasattr(result, 'mid') else ''}")
            raise HTTPException(status_code=500, detail=f"Failed to send command to MQTT broker. Error code: {result.rc}")

    except HTTPException: # Re-raise FastAPIs HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing write register request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# To make this more complete, the Gateway would need to:
# 1. Subscribe to `CONTROL_COMMAND_GENERAL_TOPIC`.
# 2. Parse the JSON payload.
# 3. Perform the Modbus write operation (e.g., client.write_coil, client.write_register).
# 4. Optionally, publish a response/acknowledgment to another topic (e.g., modbus/control/response/<correlation_id>)
#    The API could then (optionally) subscribe to this response topic for more synchronous behavior,
#    though that adds complexity (request-response correlation over MQTT). 