export interface DataPoint {
  time: string; // ISO string
  value: number | boolean | string;
  [key: string]: any; // For other tags/fields
}

export interface HistoricalQuery {
  start_time: string;    // ISO datetime string
  end_time: string;      // ISO datetime string
  measurement?: string;  // e.g., "modbus_data"
  device_name?: string;  // As configured in gateway
  slave_id?: string;     // Modbus slave ID
  register_name?: string; // Descriptive name of the register
  // The API might expect specific tags, so we can be more specific or use a general tags object
  tags?: {
    device_name?: string;
    slave_id?: string;
    register_name?: string;
    register_type?: string; // "coil", "discrete_input", "holding_register", "input_register"
    address?: string; // Address of the register as a string
    [key: string]: string | undefined; // Allow other dynamic tags
  };
  fields?: string[]; // Optional: specific fields to select, e.g., ["value"]
}

export interface HistoricalDataResponse {
  query: HistoricalQuery;
  data: DataPoint[];
}

export interface RealTimeDataUpdate {
  topic: string;
  payload: {
    timestamp: string; // ISO string
    value: number | boolean;
    tags: {
      device_name: string;
      slave_id: string;
      register_name: string;
      address: string;
      register_type: string; // "holding_register", "coil", etc.
    };
  };
  // Derived fields for easier use in UI
  deviceName?: string;
  slaveId?: string;
  registerName?: string;
  address?: string;
  registerType?: string;
}

export interface WriteRegisterRequest {
  slave_id: number;
  address: number;
  value: number | boolean;
  register_type: 'coil' | 'holding_register';
}

export interface WriteResponse {
  status: string;
  message: string;
  slave_id?: number;
  address?: number;
  value?: number | boolean;
} 