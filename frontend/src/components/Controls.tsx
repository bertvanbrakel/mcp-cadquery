import React from 'react';

// Define prop types
interface ControlsProps {
  onExecute: () => void; // Function that returns void
  onRender: () => void;  // Function that returns void
  isConnected: boolean;
  canRender: boolean;
  isIdle: boolean;
}

const Controls: React.FC<ControlsProps> = ({ onExecute, onRender, isConnected, canRender, isIdle }) => {
  return (
    <div className="card">
      <button onClick={onExecute} disabled={!isConnected || !isIdle}>
        Execute Script Manually
      </button>
      <button
        onClick={onRender}
        disabled={!isConnected || !canRender || !isIdle}
        style={{ marginLeft: '10px' }}
      >
        Render Last Result (3JS)
      </button>
    </div>
  );
};

export default Controls;