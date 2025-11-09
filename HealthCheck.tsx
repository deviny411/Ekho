// ekho-frontend/src/components/HealthCheck.tsx

import React, { useState, useEffect } from 'react';
import { getHealthStatus } from '../services/apiService';
import type { HealthCheckResponse } from '../types/api';

const HealthCheck: React.FC = () => {
  const [status, setStatus] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        setLoading(true);
        const data = await getHealthStatus();
        setStatus(data);
        setError(null);
      } catch (err: any) {
        console.error("Health check failed:", err);
        // The error object might be complex, so capture the message
        setError(err.message || "Failed to connect to the backend.");
      } finally {
        setLoading(false);
      }
    };
    fetchStatus();
  }, []);

  if (loading) return <p>Checking backend status...</p>;
  if (error) return <p style={{ color: 'red', fontWeight: 'bold' }}>❌ BACKEND CONNECTION ERROR: {error}</p>;

  const isHealthy = status?.status === "healthy";
  const statusColor = isHealthy ? 'green' : 'orange';

  return (
    <div style={{ padding: '20px', border: '1px solid #ccc', margin: '20px' }}>
      <h2>API Health Check</h2>
      <p>Service: <strong>{status?.service}</strong></p>
      <p>Status: <span style={{ color: statusColor, fontWeight: 'bold' }}>{status?.status.toUpperCase()}</span></p>
      <p>Cloud Connection: {status?.google_cloud_connected ? '✅ Connected' : '⚠️ Degraded'}</p>
      <p>Timestamp: {new Date(status?.timestamp || '').toLocaleTimeString()}</p>
      {isHealthy ? (
          <p style={{ color: 'green', fontWeight: 'bold' }}>✅ **SUCCESS:** Frontend successfully communicating with FastAPI.</p>
      ) : (
          <p style={{ color: 'orange', fontWeight: 'bold' }}>⚠️ Backend is running but reported degraded status.</p>
      )}
    </div>
  );
};

export default HealthCheck;