from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Annotated
from datetime import datetime
import logging

from ..models import HistoricalQuery, HistoricalDataResponse, DataPoint, User
from ..services.influx_service import InfluxDBService
from ..main import API_CONFIG
from ..auth.dependencies import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Dependency to get InfluxDB service instance ---
# This is a simple way; for larger apps, consider a more robust dependency injection system.
_influx_service_instance: Optional[InfluxDBService] = None

def get_influx_service():
    global _influx_service_instance
    if _influx_service_instance is None:
        influx_conf = API_CONFIG.get('influxdb')
        if not influx_conf:
            logger.error("InfluxDB configuration not found in API_CONFIG.")
            raise HTTPException(status_code=500, detail="InfluxDB not configured")
        
        _influx_service_instance = InfluxDBService(
            url=influx_conf.get('url'),
            token=influx_conf.get('token'),
            org=influx_conf.get('org'),
            bucket=influx_conf.get('bucket')
        )
        if not _influx_service_instance.client: # Check if connection failed during init
             _influx_service_instance = None # Reset if failed
             raise HTTPException(status_code=503, detail="Could not connect to InfluxDB. Service unavailable.")
    return _influx_service_instance

@router.post("/historical", response_model=HistoricalDataResponse)
async def get_historical_data(
    query_params: HistoricalQuery,
    current_user: Annotated[User, Depends(get_current_active_user)],
    influx_service: InfluxDBService = Depends(get_influx_service)
):
    """
    Query historical Modbus data from InfluxDB based on time range and optional filters.
    Requires authentication.
    """
    try:
        logger.info(f"User {current_user.username} querying historical data: {query_params.model_dump_json(indent=2)}")
        data_points: List[DataPoint] = influx_service.query_historical_data(
            start_time=query_params.start_time,
            end_time=query_params.end_time,
            measurement=query_params.measurement,
            device_name=query_params.device_name,
            slave_id=query_params.slave_id,
            register_type=query_params.register_type,
            address=query_params.address,
            tags=query_params.tags
        )
        return HistoricalDataResponse(
            query_params=query_params,
            count=len(data_points),
            data=data_points
        )
    except HTTPException: # Re-raise HTTPExceptions from dependency
        raise
    except Exception as e:
        logger.error(f"Error processing historical data query for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# Example of how to add more specific query endpoints if needed:
# @router.get("/historical/device/{device_name}")
# async def get_device_historical_data(...):
#     ... 