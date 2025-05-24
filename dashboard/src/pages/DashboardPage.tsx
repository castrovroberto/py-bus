import React from 'react';

const DashboardPage: React.FC = () => {
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <p className="mt-2">Real-time data and charts will be displayed here.</p>
      {/* Implement WebSocket connection and data display */}
    </div>
  );
};

export default DashboardPage; 