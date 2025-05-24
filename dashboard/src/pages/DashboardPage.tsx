import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getHistoricalData, isAuthenticated, logoutUser } from '../services/apiService';
import type { HistoricalQuery, DataPoint, RealTimeDataUpdate } from '../models';

const API_WS_URL = import.meta.env.VITE_API_WS_URL || 'ws://localhost:8000/ws/realtime';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [historicalData, setHistoricalData] = useState<DataPoint[]>([]);
  const [realTimeData, setRealTimeData] = useState<RealTimeDataUpdate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingHistorical, setIsLoadingHistorical] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);

  // Check authentication status
  useEffect(() => {
    if (!isAuthenticated()) {
      navigate('/login');
    }
  }, [navigate]);

  const fetchHistorical = useCallback(async () => {
    setIsLoadingHistorical(true);
    setError(null);
    try {
      const query: HistoricalQuery = {
        start_time: new Date(Date.now() - 3600 * 1000).toISOString(), // Last hour
        end_time: new Date().toISOString(),
        // Add other query parameters as needed, e.g., specific device or register
        tags: { device_name: "SimDevice1" } // Example filter
      };
      const response = await getHistoricalData(query);
      setHistoricalData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch historical data.");
      if (err instanceof Error && err.message.includes("Unauthorized")) {
        navigate('/login');
      }
    } finally {
      setIsLoadingHistorical(false);
    }
  }, [navigate]);

  // Effect for WebSocket connection
  useEffect(() => {
    if (!isAuthenticated()) return; // Don't connect if not authenticated

    const socket = new WebSocket(API_WS_URL);
    setWs(socket);

    socket.onopen = () => {
      console.log('WebSocket connection established');
      setError(null);
    };

    socket.onmessage = (event) => {
      try {
        const message: RealTimeDataUpdate = JSON.parse(event.data as string);
        // console.log('WebSocket message received:', message);
        setRealTimeData(prevData => [
          message, 
          ...prevData.slice(0, 49) // Keep last 50 messages
        ]);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    socket.onerror = (err) => {
      console.error('WebSocket error:', err);
      setError('WebSocket connection error. Attempting to reconnect...');
      // Implement more robust reconnection logic if needed
    };

    socket.onclose = () => {
      console.log('WebSocket connection closed');
      // Optionally attempt to reconnect here
      // setWs(null); // Clear ws state if needed
    };

    return () => {
      socket.close();
      setWs(null);
    };
  }, []); // Empty dependency array: runs once on mount and cleans up on unmount

  const handleLogout = () => {
    logoutUser();
    if (ws) {
      ws.close();
    }
    navigate('/login');
  };

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Dashboard</h1>
        <button
          onClick={handleLogout}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition duration-150"
        >
          Logout
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 border border-red-400 rounded">
          <p>Error: {error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Historical Data Section */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-700 mb-4">Historical Data (Last Hour for SimDevice1)</h2>
          <button
            onClick={fetchHistorical}
            disabled={isLoadingHistorical}
            className="mb-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 transition duration-150"
          >
            {isLoadingHistorical ? 'Loading...' : 'Refresh Historical Data'}
          </button>
          {historicalData.length > 0 ? (
            <ul className="max-h-96 overflow-y-auto space-y-2">
              {historicalData.map((point, index) => (
                <li key={index} className="p-2 border rounded bg-gray-50 text-sm">
                  <strong>Time:</strong> {new Date(point.time).toLocaleString()}<br/>
                  <strong>Value:</strong> {String(point.value)}
                  {/* Render other tags/fields if needed */}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500">No historical data loaded or device has no data for the period.</p>
          )}
        </div>

        {/* Real-time Data Section */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-700 mb-4">Real-time Updates</h2>
          {ws && ws.readyState === WebSocket.OPEN ? (
            <p className="text-green-600 mb-2">WebSocket Connected</p>
          ) : (
            <p className="text-yellow-600 mb-2">WebSocket Disconnected or Connecting...</p>
          )}
          {realTimeData.length > 0 ? (
            <ul className="max-h-96 overflow-y-auto space-y-2">
              {realTimeData.map((update, index) => (
                <li key={index} className="p-2 border rounded bg-gray-50 text-sm">
                  <strong>{update.payload.tags.register_name || 'N/A'} ({update.payload.tags.address}): </strong> 
                  {String(update.payload.value)} 
                  <span className="text-xs text-gray-500 block">({new Date(update.payload.timestamp).toLocaleTimeString()})</span>
                  <span className="text-xs text-gray-400 block">{update.topic}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500">Waiting for real-time data...</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage; 