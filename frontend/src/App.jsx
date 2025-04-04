import { useState, useEffect, useRef } from 'react';
import './App.css'; // Keep default styling for now

function App() {
  const [script, setScript] = useState('result = cq.Workplane("XY").box(1, 2, 3)\nshow_object(result)'); // Default script includes show_object
  const [parameters, setParameters] = useState('{}'); // Expect JSON string
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [latestImageUrl, setLatestImageUrl] = useState(null);
  const [lastResultId, setLastResultId] = useState(null); // Store the ID of the last successful script execution
  const [autoRenderStatus, setAutoRenderStatus] = useState('Idle'); // Idle, Debouncing, Executing, Rendering, Error
  const debounceTimeoutRef = useRef(null); // Ref to store debounce timeout ID
  const eventSourceRef = useRef(null);

  // --- SSE Connection ---
  useEffect(() => {
    console.log("Setting up SSE connection...");
    const eventSource = new EventSource('/mcp');
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log("SSE connection opened.");
      setIsConnected(true);
      setLogs(() => [{ type: 'status', data: 'Connected to server.' }]); // Clear previous logs on connect
      setLatestImageUrl(null); // Clear image on reconnect
      setLastResultId(null);
      setAutoRenderStatus('Idle');
    };

    eventSource.onerror = (error) => {
      console.error("SSE connection error:", error);
      setIsConnected(false);
      setAutoRenderStatus('Error');
      setLogs(prev => [...prev, { type: 'error', data: 'Connection error. Check server.' }]);
      if (eventSourceRef.current) {
          eventSourceRef.current.close();
      }
    };

    eventSource.onmessage = (event) => {
      console.log("SSE message received:", event.data);
      try {
        const messageData = JSON.parse(event.data);
        setLogs(prev => [...prev, messageData]); // Add full message object to logs

        // Check if it's a successful render result and update image URL
        if (messageData.type === 'tool_result' &&
            messageData.result?.success &&
            messageData.result?.filename?.startsWith('/renders/')) {
          // Add timestamp to force reload if filename is the same
          setLatestImageUrl(`${messageData.result.filename}?t=${Date.now()}`);
          setAutoRenderStatus('Idle'); // Render finished successfully
        }

        // Check if it's a successful script execution result
        else if (messageData.type === 'tool_result' &&
            messageData.result?.success &&
            messageData.result?.result_id && // result_id is unique to execute_script result
            !messageData.result?.filename) { // Differentiate from render/export results
              const newResultId = messageData.result.result_id;
              setLastResultId(newResultId);
              // If auto-render was executing, trigger render automatically
              if (autoRenderStatus === 'Executing') {
                 setAutoRenderStatus('Rendering');
                 triggerRender(newResultId); // Trigger render immediately
              } else {
                 // If manual execution succeeded, just go back to Idle
                 setAutoRenderStatus('Idle');
              }
        }
        // Check for errors during auto-render sequence
        else if (messageData.type === 'tool_error' && autoRenderStatus !== 'Idle') {
           setAutoRenderStatus('Error'); // Auto-render sequence failed
        }

      } catch (e) {
        console.error("Failed to parse SSE message data:", e);
        setLogs(prev => [...prev, { type: 'error', data: `Failed to parse message: ${event.data}` }]);
        if (autoRenderStatus !== 'Idle') setAutoRenderStatus('Error');
      }
    };

    // Cleanup function
    return () => {
      console.log("Closing SSE connection...");
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      setIsConnected(false);
    };
  }, []); // Run only once on mount

  // --- Debounce and Auto-Execute/Render ---
  useEffect(() => {
    // Don't debounce if not connected
    if (!isConnected) return;

    setAutoRenderStatus('Debouncing');
    setLatestImageUrl(null); // Clear image while typing

    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    debounceTimeoutRef.current = setTimeout(() => {
      // Only proceed if still in Debouncing state (prevents race conditions)
      setAutoRenderStatus(currentStatus => {
          if (currentStatus === 'Debouncing') {
              triggerExecute(true); // Pass flag indicating auto-trigger
              return 'Executing'; // Update status
          }
          return currentStatus; // Otherwise, keep current status
      });
    }, 1000); // 1 second debounce time

    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
    };
  }, [script, isConnected]); // Re-run effect when script or connection status changes

  // --- Tool Execution Functions ---

  // Wrapper functions to call async handlers from effects/handlers
  const triggerExecute = (isAuto) => {
      handleExecuteScript(isAuto);
  };

  const triggerRender = (resultId) => {
      handleRenderResult(resultId);
  };

  const handleExecuteScript = async (isAutoTrigger = false) => {
    if (!isConnected) return;

    // If manually triggered, clear debounce and set status
    if (!isAutoTrigger) {
        if (debounceTimeoutRef.current) {
            clearTimeout(debounceTimeoutRef.current);
        }
        setAutoRenderStatus('Executing');
    }
    // Reset image and last result ID for new execution
    setLatestImageUrl(null);
    setLastResultId(null);

    setLogs(prev => [...prev, { type: 'info', data: `(${isAutoTrigger ? 'Auto' : 'Manual'}) Sending script execution request...` }]);
    let paramsObj = {};
    try {
      paramsObj = JSON.parse(parameters);
    } catch (e) {
      setLogs(prev => [...prev, { type: 'error', data: `Invalid JSON in parameters: ${e.message}` }]);
      setAutoRenderStatus('Error');
      return;
    }

    const requestBody = {
      request_id: `ui-exec-${Date.now()}`,
      tool_name: "execute_cadquery_script",
      arguments: {
        script: script,
        parameters: paramsObj,
      }
    };

    setLogs(prev => [
      ...prev,
      { type: 'info', data: `Sending request (ID: ${requestBody.request_id}): ${JSON.stringify(requestBody, null, 2)}` }
    ]);

    try {
      const response = await fetch('/mcp/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        let errorDetail = `HTTP error! status: ${response.status}`;
        try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore if response body isn't JSON */ } // eslint-disable-line no-empty, no-unused-vars
        throw new Error(errorDetail);
      }

      const result = await response.json();
      setLogs(prev => [...prev, { type: 'info', data: `Request acknowledged: ${JSON.stringify(result)}` }]);
      // Success/failure and next steps handled by SSE listener
    } catch (error) {
      console.error('Error sending execution request:', error);
      setLogs(prev => [...prev, { type: 'error', data: `Failed to send request: ${error.message}` }]);
      setAutoRenderStatus('Error');
    }
  };

  const handleRenderResult = async (resultIdToRender = null) => {
     if (!isConnected) return;
    const targetResultId = resultIdToRender || lastResultId;

    if (!targetResultId) {
      setLogs(prev => [...prev, { type: 'error', data: 'No result ID available to render.' }]);
      if (!resultIdToRender) setAutoRenderStatus('Idle'); // Only reset if manually triggered
      return;
    }

    // If manually triggered, set status
    if (!resultIdToRender) {
        setAutoRenderStatus('Rendering');
    }

    const filename = `render_${targetResultId}.png`;
    const requestBody = {
      request_id: `ui-render-${Date.now()}`,
      tool_name: "render_shape_to_png",
      arguments: {
        result_id: targetResultId,
        shape_index: 0,
        filename: filename,
        options: { width: 400, height: 300, marginLeft: 50, marginTop: 50, showAxes: true }
      }
    };

    setLogs(prev => [
      ...prev,
      { type: 'info', data: `Sending request (ID: ${requestBody.request_id}): ${JSON.stringify(requestBody, null, 2)}` }
    ]);

    try {
      const response = await fetch('/mcp/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        let errorDetail = `HTTP error! status: ${response.status}`;
        try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e) { /* Ignore if response body isn't JSON */ } // eslint-disable-line no-empty, no-unused-vars
        throw new Error(errorDetail);
      }

      const result = await response.json();
      setLogs(prev => [...prev, { type: 'info', data: `Request acknowledged: ${JSON.stringify(result)}` }]);
      // Success (image display) and status reset handled by SSE listener
    } catch (error) {
      console.error('Error sending render request:', error);
      setLogs(prev => [...prev, { type: 'error', data: `Failed to send render request: ${error.message}` }]);
      setAutoRenderStatus('Error');
    }
  };

  // --- Render JSX ---
  return (
    <>
      <h1>CadQuery MCP Server UI</h1>
      <p>Status: <span style={{ color: isConnected ? 'green' : 'red' }}>{isConnected ? 'Connected' : 'Disconnected'}</span> | Auto-Render: <span style={{ fontStyle: 'italic' }}>{autoRenderStatus}</span></p>

      <div className="card">
        <h2>Script Input</h2>
        <textarea
          value={script}
          onChange={(e) => setScript(e.target.value)}
          rows={10}
          style={{ width: '90%', fontFamily: 'monospace' }}
          disabled={!isConnected}
        />
      </div>

      <div className="card">
        <h2>Parameters (JSON)</h2>
        <textarea
          value={parameters}
          onChange={(e) => setParameters(e.target.value)}
          rows={3}
          style={{ width: '90%', fontFamily: 'monospace' }}
          disabled={!isConnected}
        />
      </div>

      <div className="card">
        <button onClick={() => handleExecuteScript(false)} disabled={!isConnected || autoRenderStatus !== 'Idle'}>
          Execute Script Manually
        </button>
        <button
          onClick={() => handleRenderResult(null)}
          disabled={!isConnected || !lastResultId || autoRenderStatus !== 'Idle'}
          style={{ marginLeft: '10px' }}
        >
          Render Last Result (PNG)
        </button>
     </div>

     <div className="card">
       <h2>Rendered Output</h2>
       {latestImageUrl ? (
         <img src={latestImageUrl} alt="Latest Rendered Output" style={{ maxWidth: '100%', border: '1px solid #ccc' }} />
       ) : (
         <p>No image rendered yet. Type in the script area to trigger auto-render.</p>
       )}
      </div>

      <div className="card">
        <h2>Logs & Results</h2>
        <pre style={{ textAlign: 'left', maxHeight: '400px', overflowY: 'auto', background: '#f0f0f0', padding: '10px', border: '1px solid #ccc' }}>
          {logs.map((log, index) => (
            <div key={index} style={{ color: log.type === 'error' ? 'red' : log.type === 'tool_error' ? 'red' : 'inherit', borderBottom: '1px dashed #eee', marginBottom: '5px', paddingBottom: '5px' }}>
              <strong>{log.type?.toUpperCase() || 'MESSAGE'}:</strong>
              {typeof log.data === 'object' ? <pre style={{margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all'}}>{JSON.stringify(log.data, null, 2)}</pre> : log.data?.toString()}
              {log.type === 'tool_result' && log.result && (
                <div style={{ marginLeft: '15px', fontSize: '0.9em' }}>
                  <p>Request ID: {log.request_id}</p>
                  <p>Message: {log.result.message}</p>
                  {log.result.result_id && <p>Result ID: {log.result.result_id}</p>}
                  {log.result.filename && <p>Filename/URL: {log.result.filename}</p>}
                </div>
              )}
               {log.type === 'tool_error' && (
                <div style={{ marginLeft: '15px', fontSize: '0.9em' }}>
                   <p>Request ID: {log.request_id}</p>
                   <p>Error: {log.error}</p>
                </div>
              )}
            </div>
          ))}
        </pre>
      </div>
    </>
  );
} // End of App component

export default App;
