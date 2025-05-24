import logging
from influxdb_client import InfluxDBClient
from influxdb_client.client.flux_table import FluxStructureEncoder
from typing import List, Dict, Optional
from datetime import datetime

from ..models import DataPoint # Assuming models.py is one level up

logger = logging.getLogger(__name__)

class InfluxDBService:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client: Optional[InfluxDBClient] = None
        self._connect()

    def _connect(self):
        try:
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            if self.client.ping():
                logger.info(f"Successfully connected to InfluxDB at {self.url} for org '{self.org}'")
            else:
                logger.error(f"Failed to ping InfluxDB at {self.url}. Check connection or credentials.")
                self.client = None
        except Exception as e:
            logger.error(f"Exception connecting to InfluxDB: {e}")
            self.client = None

    def query_historical_data(
        self,
        start_time: datetime,
        end_time: datetime,
        measurement: str = "modbus_data",
        device_name: Optional[str] = None,
        slave_id: Optional[str] = None,
        register_type: Optional[str] = None,
        address: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[DataPoint]:
        if not self.client:
            logger.error("InfluxDB client not initialized. Cannot query data.")
            return []

        query_api = self.client.query_api()

        # Construct Flux query dynamically
        flux_query = f'''from(bucket: "{self.bucket}")
          |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
          |> filter(fn: (r) => r._measurement == "{measurement}")
        '''
        if device_name:
            flux_query += f' |> filter(fn: (r) => r.device_name == "{device_name}")\n'
        if slave_id:
            flux_query += f' |> filter(fn: (r) => r.slave_id == "{slave_id}")\n'
        if register_type:
            flux_query += f' |> filter(fn: (r) => r.register_type == "{register_type}")\n'
        if address:
            flux_query += f' |> filter(fn: (r) => r.address == "{address}")\n'
        
        if tags:
            for tag_key, tag_value in tags.items():
                flux_query += f' |> filter(fn: (r) => r["{tag_key}"] == "{tag_value}")\n'
        
        # Add a sort by time, essential for chronological data
        flux_query += ' |> sort(columns: ["_time"], desc: false)\n'
        # flux_query += ' |> yield(name: "results")' # Optional: name the result stream

        logger.info(f"Executing Flux query: \n{flux_query}")

        try:
            tables = query_api.query(query=flux_query, org=self.org)
            results: List[DataPoint] = []
            for table in tables:
                for record in table.records:
                    # Convert FluxRecord to our DataPoint model
                    # Ensure all fields required by DataPoint are present or handled
                    tags_dict = {k: v for k, v in record.values.items() if k not in ['_time', '_start', '_stop', '_value', '_field', '_measurement', 'result', 'table']}
                    
                    # Filter out internal fields if they are not proper tags
                    internal_flux_fields = ['result', 'table']
                    for internal_field in internal_flux_fields:
                        tags_dict.pop(internal_field, None)

                    results.append(
                        DataPoint(
                            time=record.get_time(),
                            measurement=record.get_measurement(),
                            tags=tags_dict,
                            fields={record.get_field(): record.get_value()}
                        )
                    )
            return results
        except Exception as e:
            logger.error(f"Error querying InfluxDB: {e}")
            return []

    def close(self):
        if self.client:
            self.client.close()
            logger.info("InfluxDB client connection closed.")

# Example of how to instantiate (will be done in main.py or a dependency injector)
# influx_service = InfluxDBService(url="..."), token="...", org="...", bucket="...") 