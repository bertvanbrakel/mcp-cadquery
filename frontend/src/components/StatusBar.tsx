import React from 'react';

// Define prop types
interface StatusBarProps {
  isConnected: boolean;
  autoRenderStatus: string; // Could be a specific enum/union type later
}

const StatusBar: React.FC<StatusBarProps> = ({ isConnected, autoRenderStatus }) => {
  console.log("[StatusBar] Rendering. isConnected:", isConnected); // DEBUG LOG
  return (
    <p>
      Status: <span style={{ color: isConnected ? 'green' : 'red' }}>**{isConnected ? 'ONLINE' : 'OFFLINE'}**</span> | Auto-Render: <span style={{ fontStyle: 'italic' }}>{autoRenderStatus}</span>
    </p>
  );
};

export default StatusBar;