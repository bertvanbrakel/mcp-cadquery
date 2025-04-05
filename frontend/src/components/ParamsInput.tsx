import React from 'react';

// Define prop types
interface ParamsInputProps {
  parameters: string;
  setParameters: (value: string) => void;
  isConnected: boolean;
}

const ParamsInput: React.FC<ParamsInputProps> = ({ parameters, setParameters, isConnected }) => {
  return (
    <div className="card">
      <h2>Parameters (JSON)</h2>
      <textarea
        value={parameters}
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setParameters(e.target.value)} // Add event type
        rows={3}
        style={{ width: '90%', fontFamily: 'monospace' }}
        disabled={!isConnected}
      />
    </div>
  );
};

export default ParamsInput;