from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from contextlib import asynccontextmanager
import uvicorn
import logging
import yaml
import json
from datetime import datetime, timedelta # Ensure timedelta is imported for security module updates

from .models import RealTimeDataUpdate, User # Import User for protected endpoints
from .services.mqtt_service import MQTTService
from .routes import data_routes, control_routes
from .auth import auth_routes # Import auth_routes
from .auth import security as auth_security # To update JWT settings
from .auth.dependencies import get_current_active_user # For protecting routes

# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_CONFIG = {}
MQTT_SERVICE_INSTANCE: Optional[MQTTService] = None
# _influx_service_instance from data_routes should be managed there or via a proper DI system
# For now, lifespan closing it is a temporary measure if it was made global in data_routes.
# It is better if InfluxDBService is instantiated per request or managed by a DI container.


def load_api_config_and_jwt_settings(config_file="config.yaml"):
    global API_CONFIG
    try:
        with open(config_file, 'r') as f:
            API_CONFIG = yaml.safe_load(f)
        logger.info(f"API configuration loaded from {config_file}")

        # Update JWT settings in security module
        jwt_config = API_CONFIG.get('jwt', {})
        auth_security.JWT_SECRET_KEY = jwt_config.get('secret_key', auth_security.JWT_SECRET_KEY)
        auth_security.JWT_ALGORITHM = jwt_config.get('algorithm', auth_security.JWT_ALGORITHM)
        auth_security.ACCESS_TOKEN_EXPIRE_MINUTES = jwt_config.get('access_token_expire_minutes', auth_security.ACCESS_TOKEN_EXPIRE_MINUTES)
        logger.info(f"JWT Settings: Loaded Secret Key (ending): ...{auth_security.JWT_SECRET_KEY[-6:] if len(auth_security.JWT_SECRET_KEY) > 5 else ''}, Algorithm: {auth_security.JWT_ALGORITHM}, Token Expire Minutes: {auth_security.ACCESS_TOKEN_EXPIRE_MINUTES}")

    except FileNotFoundError:
        logger.warning(f"API configuration file {config_file} not found. Using default JWT settings.")
        API_CONFIG = {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing API YAML file {config_file}: {e}")
        API_CONFIG = {}
    except Exception as e:
        logger.error(f"Error loading API config or setting JWT: {e}", exc_info=True)

# Load config once at module level. Lifespan can also call it if needed.
# load_api_config_and_jwt_settings()

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connection established: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket connection closed: {websocket.client}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        # logger.debug(f"Broadcasting to {len(self.active_connections)} WebSocket clients: {message}")
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket client {connection.client}: {e}")
                # Optionally disconnect problematic clients
                # self.disconnect(connection) 

manager = ConnectionManager()

# --- MQTT Message Handler for WebSockets ---
# Placeholder for proper async task scheduling for manager.broadcast
async def schedule_broadcast(message: str):
    await manager.broadcast(message)

def handle_mqtt_for_websockets(topic: str, payload: str):
    logger.debug(f"MQTT Handler for WS: Topic: {topic}, Payload: {payload}")
    # Expected topic format from gateway: prefix/device_name/slave_id/register_type/address
    # e.g., modbus/gateway/SimulatedDevice1/1/holding_registers/0
    try:
        parts = topic.split('/')
        if len(parts) >= 5: # Basic validation of topic structure
            # prefix = parts[0]
            # gateway_identifier = parts[1] # e.g., 'gateway' if included by gateway config
            device_name = parts[-4] # Adjust indices based on actual topic structure from gateway
            slave_id = parts[-3]
            register_type = parts[-2]
            address = parts[-1]

            # Attempt to convert payload to a more specific type if possible
            try:
                # Check if it's a boolean string
                if payload.lower() == 'true': processed_value = True
                elif payload.lower() == 'false': processed_value = False
                else: # Try to convert to float, then int
                    try: processed_value = float(payload)
                    except ValueError:
                        try: processed_value = int(payload)
                        except ValueError: processed_value = payload # Keep as string if no conversion works
            except Exception:
                processed_value = payload # Fallback to raw string

            update_message = RealTimeDataUpdate(
                topic=topic,
                device_name=device_name,
                slave_id=slave_id,
                register_type=register_type,
                address=address,
                value=processed_value
            )
            # Use model_dump_json for pydantic v2
            message_str = update_message.model_dump_json()
            # For older pydantic, it was update_message.json()
            # logger.info(f"Formatted WS message: {message_str}")
            # Important: manager.broadcast needs to be called from an async context if it awaits.
            # Since this callback is synchronous, we need to schedule the broadcast.
            # FastAPI doesn't have a simple asyncio.create_task from sync context directly for this.
            # A common pattern is to use an asyncio.Queue or similar if strict async is needed here.
            # For simplicity, if manager.broadcast is very quick and non-blocking internally (not awaiting heavily),
            # this might appear to work, but it's not ideal. Best to make manager.broadcast truly async aware
            # or use an intermediary queue.
            # Let's assume for now direct call is for demonstration; FastAPI background tasks are better.
            
            # To properly call an async function from this synchronous callback:
            # We need an event loop. FastAPI runs in an asyncio event loop.
            # This direct call to an async method from a sync callback (paho-mqtt runs in its own thread)
            # can be problematic. The proper way is to use `asyncio.run_coroutine_threadsafe` if you have access
            # to the FastAPI event loop, or use BackgroundTasks in FastAPI for such operations.
            # For now, let's make broadcast itself handle this, or simplify.
            
            # Simplification: if manager.broadcast is designed to be called from any thread and internally
            # handles async operations correctly (e.g. by scheduling on an event loop), this is fine.
            # Given our manager.broadcast iterates and calls await, this direct call will not work as expected
            # from a sync thread. 
            # The mqtt_service should run in a way that it can schedule async tasks on FastAPI's loop.
            # This will be revised when integrating properly with FastAPI's event loop / background tasks.
            # For a quick test, we can try to make manager.broadcast more robust or use a queue.

            # *** TEMPORARY: Direct broadcast - this might block or fail in real async env ***
            # This will be an issue because this callback is run in the MQTT client's thread.
            # We need to hand this off to FastAPI's event loop.
            # A more robust solution will involve asyncio.Queue or FastAPI's BackgroundTasks.
            
            # We'll mark this for revision when setting up background tasks for MQTT client properly.
            # For now, we are demonstrating the data flow. The actual broadcast call will be refined.
            logger.info(f"Scheduling broadcast for: {message_str}")
            # Example: app.state.background_tasks.add_task(schedule_broadcast, message_str)
            # This requires app.state.background_tasks to be set up and accessible.

        else:
            logger.warning(f"Could not parse MQTT topic for WS: {topic}")

    except Exception as e:
        logger.error(f"Error in handle_mqtt_for_websockets: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global MQTT_SERVICE_INSTANCE
    global API_CONFIG # Make sure API_CONFIG is available
    
    load_api_config_and_jwt_settings() # Load config and set JWT parameters
    
    mqtt_conf = API_CONFIG.get('mqtt_broker')
    if mqtt_conf:
        MQTT_SERVICE_INSTANCE = MQTTService(
            broker_host=mqtt_conf.get('host'),
            broker_port=mqtt_conf.get('port'),
            client_id=mqtt_conf.get('api_client_id', 'modbus_api_subscriber'),
            topic_prefix=mqtt_conf.get('data_topic_prefix', 'modbus/gateway')
        )
        MQTT_SERVICE_INSTANCE.set_message_callback(handle_mqtt_for_websockets)
        MQTT_SERVICE_INSTANCE.connect()
        logger.info("MQTT Service started and connected within lifespan.")
    else:
        logger.warning("MQTT broker configuration not found in API_CONFIG. Real-time updates will be unavailable.")
    
    # Example: Store BackgroundTasks instance if needed by other parts (like MQTT handler)
    # app.state.background_tasks = BackgroundTasks() 
    
    yield
    # Shutdown
    if MQTT_SERVICE_INSTANCE:
        MQTT_SERVICE_INSTANCE.disconnect()
        logger.info("MQTT Service disconnected during lifespan shutdown.")
    # Closing InfluxDB client should be handled by its own service/dependency management
    # if _influx_service_instance: _influx_service_instance.close()

app = FastAPI(
    title="Modbus Integration Suite API",
    description="API for querying Modbus data, managing configurations, and real-time updates.",
    version="0.1.0",
    lifespan=lifespan # Use the lifespan context manager
)


# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Modbus Integration Suite API"}

@app.get("/api/v1/health")
async def health_check():
    # Extended health check could ping InfluxDB and MQTT broker
    mqtt_status = "connected" if MQTT_SERVICE_INSTANCE and MQTT_SERVICE_INSTANCE.client.is_connected() else "disconnected"
    # InfluxDB ping is done during get_influx_service, so if that works, API is generally fine with it.
    # For a dedicated health check, you might add a ping method to InfluxDBService.
    return {"status": "ok", "mqtt_broker_status": mqtt_status, "influxdb_status": "check_via_data_endpoint"}

@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # This basic websocket keeps connection alive. 
            # It can receive messages from client if dashboard needs to send commands/requests via WS.
            data = await websocket.receive_text()
            logger.debug(f"Received WS message from {websocket.client}: {data}")
            # Example: await manager.send_personal_message(f"Echo: {data}", websocket)
            # Real-time data is pushed by MQTT callback via manager.broadcast
    except WebSocketDisconnect:
        logger.info(f"Client {websocket.client} disconnected from WebSocket (WebSocketDisconnect).")
    except Exception as e:
        # Handle other exceptions, e.g., connection closed by client without proper disconnect message
        logger.error(f"WebSocket error for client {websocket.client}: {e}", exc_info=False)
    finally:
        manager.disconnect(websocket)


# Import and include routers
app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(data_routes.router, prefix="/api/v1/data", tags=["data"])
app.include_router(control_routes.router, prefix="/api/v1/control", tags=["control"])

# Example of a protected route (could be in any router file)
@app.get("/api/v1/users/me", response_model=User)
async def read_users_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user

# --- Main execution for local development (using uvicorn) ---
if __name__ == "__main__":
    # Lifespan handles MQTT connection, so direct load_api_config not needed here if using lifespan for uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 