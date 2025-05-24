# Pydantic models for request and response validation will go here.
# Example:
# from pydantic import BaseModel
#
# class Item(BaseModel):
#     name: str
#     description: str | None = None
#     price: float
#     tax: float | None = None 

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class HistoricalQuery(BaseModel):
    start_time: datetime = Field(..., description="Start of the time range (ISO format string)")
    end_time: datetime = Field(..., description="End of the time range (ISO format string)")
    measurement: Optional[str] = Field(default="modbus_data", description="The InfluxDB measurement name")
    device_name: Optional[str] = Field(default=None, description="Filter by device name")
    slave_id: Optional[str] = Field(default=None, description="Filter by slave ID")
    register_type: Optional[str] = Field(default=None, description="Filter by register type (e.g., holding_registers)")
    address: Optional[str] = Field(default=None, description="Filter by specific register address")
    tags: Optional[Dict[str, str]] = Field(default=None, description="Additional tags to filter by")
    # Add other parameters like aggregation_window if needed

class DataPoint(BaseModel):
    time: datetime
    measurement: str
    tags: Dict[str, str]
    fields: Dict[str, Any]

class HistoricalDataResponse(BaseModel):
    query_params: HistoricalQuery
    count: int
    data: List[DataPoint]

class RealTimeDataUpdate(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    topic: str
    device_name: str
    slave_id: str
    register_type: str
    address: str
    value: Any # Can be bool, int, float, or string representation

class WriteRegisterRequest(BaseModel):
    slave_id: int = Field(..., description="Target Modbus slave ID")
    register_type: str = Field(..., description="Type of register to write (e.g., 'coil', 'holding_register')")
    address: int = Field(..., description="Register address")
    value: Any = Field(..., description="Value to write (boolean for coils, integer for registers)")

class WriteResponse(BaseModel):
    status: str
    message: str
    request_details: WriteRegisterRequest 

# --- JWT and User Models ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    # You can add other fields like scopes/roles here if needed

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None # To deactivate accounts
    # roles: List[str] = [] # Example for role-based access

class UserInDB(User):
    hashed_password: str

# --- Fake User Database (for demonstration) ---
# In a real application, this would be a proper database (SQL, NoSQL, etc.)
# and you'd have functions to fetch users from it.
# Password for 'admin' is 'adminpass', for 'viewer' is 'viewerpass'
# Hashed passwords generated using get_password_hash from security.py:
# from ..auth.security import get_password_hash # Use this path if running from a script in api/
# print(get_password_hash("adminpass"))
# print(get_password_hash("viewerpass"))

FAKE_USERS_DB = {
    "admin": {
        "username": "admin",
        "full_name": "Admin User",
        "email": "admin@example.com",
        "hashed_password": "$2b$12$EIXbN4n2./V5rU9GfSTNl.n5r5oYfJCTOAbqG1rPfXBJzB3zS5v1a", # adminpass
        "disabled": False,
        # "roles": ["admin", "viewer"]
    },
    "viewer": {
        "username": "viewer",
        "full_name": "Viewer User",
        "email": "viewer@example.com",
        "hashed_password": "$2b$12$kGDaJtqZqd9d9G9m5U2/Xua3MZmG8.L0gE7u4K7FwR1kYw2wI5m6W", # viewerpass
        "disabled": False,
        # "roles": ["viewer"]
    }
}

# Helper to get user from our fake DB
def get_user_from_db(username: str) -> Optional[UserInDB]:
    if username in FAKE_USERS_DB:
        user_dict = FAKE_USERS_DB[username]
        return UserInDB(**user_dict)
    return None 