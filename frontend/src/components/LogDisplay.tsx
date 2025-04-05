import React from 'react';

// Define and export a more specific type for log entries
// This could be further refined based on actual message structures
export interface LogEntry { // Add export keyword
  type: string;
  data?: any; // Data can be anything initially
  result?: {
    success?: boolean;
    message?: string;
    result_id?: string;
    filename?: string;
    // Add other potential result fields here
  };
  error?: string;
  request_id?: string;
}

// Define prop types
interface LogDisplayProps {
  logs: LogEntry[];
}

const LogDisplay: React.FC<LogDisplayProps> = ({ logs }) => {
  return (
    <div className="card">
      <h2>Logs & Results</h2>
      <pre style={{ textAlign: 'left', maxHeight: '400px', overflowY: 'auto', background: '#f0f0f0', padding: '10px', border: '1px solid #ccc' }}>
        {logs.map((log: LogEntry, index: number) => ( // Add types here
          <div key={index} style={{ color: log.type === 'error' || log.type === 'tool_error' ? 'red' : 'inherit', borderBottom: '1px dashed #eee', marginBottom: '5px', paddingBottom: '5px' }}>
            <strong>{log.type?.toUpperCase() || 'MESSAGE'}:</strong>
            {/* Nicer display for objects */}
            {typeof log.data === 'object' ? <pre style={{margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all'}}>{JSON.stringify(log.data, null, 2)}</pre> : log.data?.toString()}
            {log.type === 'tool_result' && log.result && (
              <div style={{ marginLeft: '15px', fontSize: '0.9em' }}>
                <p>Request ID: {log.request_id ?? 'N/A'}</p>
                <p>Message: {log.result.message ?? 'N/A'}</p>
                {log.result.result_id && <p>Result ID: {log.result.result_id}</p>}
                {log.result.filename && <p>Filename/URL: {log.result.filename}</p>}
              </div>
            )}
             {log.type === 'tool_error' && (
              <div style={{ marginLeft: '15px', fontSize: '0.9em' }}>
                 <p>Request ID: {log.request_id ?? 'N/A'}</p>
                 <p>Error: {log.error ?? 'Unknown error'}</p>
              </div>
            )}
          </div>
        ))}
      </pre>
    </div>
  );
};

export default LogDisplay;