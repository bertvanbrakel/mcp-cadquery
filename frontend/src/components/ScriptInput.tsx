import React from 'react';

// Define prop types
interface ScriptInputProps {
  script: string;
  setScript: (value: string) => void; // Function that takes a string and returns void
  isConnected: boolean;
}

const ScriptInput: React.FC<ScriptInputProps> = ({ script, setScript, isConnected }) => {
  return (
    <div className="card">
      <h2>Script Input</h2>
      <textarea
        value={script}
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setScript(e.target.value)} // Add event type
        rows={10}
        style={{ width: '90%', fontFamily: 'monospace' }}
        disabled={!isConnected}
      />
    </div>
  );
};

export default ScriptInput;