import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import StatusBar from './components/StatusBar'; // Corrected import
import ScriptInput from './components/ScriptInput'; // Corrected import
import ParamsInput from './components/ParamsInput'; // Corrected import
import Controls from './components/Controls';       // Corrected import
import RenderOutput from './components/RenderOutput'; // Corrected import
import LogDisplay, { LogEntry } from './components/LogDisplay'; // Corrected import

// Define type for AutoRenderStatus
type AutoRenderStatus = 'Idle' | 'Debouncing' | 'Executing' | 'Rendering' | 'Error';

function App() { // Corrected: Removed explicit JSX.Element return type
  // --- State ---
  const [script, setScript] = useState<string>('result = cq.Workplane("XY").box(1, 2, 3)\nshow_object(result)');
  const [parameters, setParameters] = useState<string>('{}');
  const [logs, setLogs] = useState<LogEntry[]>([]); // Use imported LogEntry type
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [latestRenderUrl, setLatestRenderUrl] = useState<string | null>(null); // Renamed state
  const [lastResultId, setLastResultId] = useState<string | null>(null);
  const [autoRenderStatus, setAutoRenderStatus] = useState<AutoRenderStatus>('Idle'); // Use defined type
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null); // Use NodeJS type
  const eventSourceRef = useRef<EventSource | null>(null);

  // --- SSE Connection ---
  useEffect(() => {
    console.log("Setting up SSE connection...");
    const eventSource = new EventSource('/mcp');
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log("SSE connection opened.");
      setIsConnected(true);
      setLogs(() => [{ type: 'status', data: 'Connected to server.' }]);
      setLatestRenderUrl(null); // Use renamed state setter
      setLastResultId(null);
      setAutoRenderStatus('Idle');
    };

    eventSource.onerror = (error: Event) => { // Typed event
      console.error("SSE connection error:", error);
      setIsConnected(false);
      setAutoRenderStatus('Error');
      setLogs(prev => [...prev, { type: 'error', data: 'Connection error. Check server.' }]);
      if (eventSourceRef.current) {
          eventSourceRef.current.close();
      }
    };

    eventSource.onmessage = (event: MessageEvent) => { // Typed event
      console.log("SSE message received:", event.data);
      try {
        const messageData: LogEntry = JSON.parse(event.data); // Use LogEntry type
        setLogs(prev => [...prev, messageData]);

        // --- START DEBUG LOGGING for SVG result ---
        const isToolResult = messageData.type === 'tool_result';
        const isSuccess = messageData.result?.success;
        const filename = messageData.result?.filename;
        const isSvgRenderResult = isToolResult && isSuccess && typeof filename === 'string' && filename.startsWith('/renders/') && filename.endsWith('.svg');

        console.log(`[onmessage] isToolResult: ${isToolResult}, isSuccess: ${isSuccess}, filename: ${filename}, isSvgRenderResult: ${isSvgRenderResult}`);
        // --- END DEBUG LOGGING ---

        // Handle successful render result (SVG)
        if (isSvgRenderResult) {
          console.log("[onmessage] Condition met! Setting latestRenderUrl to:", filename); // DEBUG LOG
          setLatestRenderUrl(`${filename}?t=${Date.now()}`);
          setAutoRenderStatus('Idle');
        }
        // Handle successful script execution result
        else if (messageData.type === 'tool_result' && messageData.result?.success && messageData.result?.result_id && !messageData.result?.filename) {
          const newResultId = messageData.result.result_id;
          setLastResultId(newResultId);
          console.log("[onmessage] setLastResultId called with:", newResultId); // Keep debug log
          if (autoRenderStatus === 'Executing') {
             setAutoRenderStatus('Rendering');
             triggerRender(newResultId); // Call correct trigger function
          } else {
             setAutoRenderStatus('Idle');
          }
        }
        // Handle errors during auto-render
        else if (messageData.type === 'tool_error' && autoRenderStatus !== 'Idle' && autoRenderStatus !== 'Error') {
           setAutoRenderStatus('Error');
        }
      } catch (e: any) { // Typed error
        console.error("Failed to parse SSE message data:", e);
        setLogs(prev => [...prev, { type: 'error', data: `Failed to parse message: ${event.data}` }]);
        if (autoRenderStatus !== 'Idle') setAutoRenderStatus('Error');
      }
    };

    return () => {
      console.log("Closing SSE connection...");
      if (eventSourceRef.current) eventSourceRef.current.close();
      setIsConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once

  // --- Debounce and Auto-Execute/Render ---
  useEffect(() => {
    if (!isConnected) return;
    setAutoRenderStatus('Debouncing');
    setLatestRenderUrl(null); // Use renamed state setter
    if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);

    debounceTimeoutRef.current = setTimeout(() => {
      setAutoRenderStatus((currentStatus: AutoRenderStatus): AutoRenderStatus => { // Typed function
          if (currentStatus === 'Debouncing') {
              triggerExecute(true);
              return 'Executing';
          }
          return currentStatus;
      });
    }, 1000);

    return () => { if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [script, isConnected]); // Rerun on script change or connection change

  // --- Tool Execution Functions ---
  const triggerExecute = (isAuto: boolean): void => { // Typed function
      handleExecuteScript(isAuto);
  };

  const triggerRender = (resultId: string): void => { // Typed function
      handleExportSvgResult(resultId); // Call renamed handler
  };

  const handleExecuteScript = async (isAutoTrigger: boolean = false): Promise<void> => { // Typed function
    if (!isConnected) return;
    if (!isAutoTrigger) {
        if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);
        setAutoRenderStatus('Executing');
    }
    setLatestRenderUrl(null); // Use renamed state setter
    setLastResultId(null);
    setLogs(prev => [...prev, { type: 'info', data: `(${isAutoTrigger ? 'Auto' : 'Manual'}) Sending script execution request...` }]);

    let paramsObj: Record<string, any> = {};
    try { paramsObj = JSON.parse(parameters); } catch (e: any) { // Typed error
      // Use type assertion for error message if needed, or keep as 'any'
      const errorMessage = e instanceof Error ? e.message : String(e);
      setLogs(prev => [...prev, { type: 'error', data: `Invalid JSON in parameters: ${errorMessage}` }]);
      setAutoRenderStatus('Error'); return;
    }

    const requestBody: any = {
      request_id: `ui-exec-${Date.now()}`, tool_name: "execute_cadquery_script",
      arguments: { script: script, parameters: paramsObj }
    };
    setLogs(prev => [...prev, { type: 'info', data: `Sending request (ID: ${requestBody.request_id}): ${JSON.stringify(requestBody, null, 2)}` }]);

    try {
      const response = await fetch('/mcp/execute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestBody) });
      if (!response.ok) {
        let errorDetail = `HTTP error! status: ${response.status}`;
        try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e: any) { /* Ignore */ } // eslint-disable-line no-empty, no-unused-vars
        throw new Error(errorDetail);
      }
      const result: any = await response.json();
      setLogs(prev => [...prev, { type: 'info', data: `Request acknowledged: ${JSON.stringify(result)}` }]);
    } catch (error: any) { // Typed error
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('Error sending execution request:', error);
      setLogs(prev => [...prev, { type: 'error', data: `Failed to send request: ${errorMessage}` }]);
      setAutoRenderStatus('Error');
    }
  };

  const handleExportSvgResult = async (resultIdToRender: string | null = null): Promise<void> => { // Renamed handler, typed
    if (!isConnected) return;
    console.log("[handleRenderResult] Called. lastResultId:", lastResultId, "resultIdToRender:", resultIdToRender); // Keep debug log
    const targetResultId = resultIdToRender || lastResultId;
    if (!targetResultId) {
      setLogs(prev => [...prev, { type: 'error', data: 'No result ID available to render.' }]);
      if (!resultIdToRender) setAutoRenderStatus('Idle'); return;
    }
    if (!resultIdToRender) setAutoRenderStatus('Rendering');

    const filename = `render_${targetResultId}.svg`; // Change extension
    const requestBody: any = {
      request_id: `ui-svg-${Date.now()}`, tool_name: "export_shape_to_svg", // Change tool name
      arguments: { result_id: targetResultId, shape_index: 0, filename: filename, options: {} }
    };
    setLogs(prev => [...prev, { type: 'info', data: `Sending request (ID: ${requestBody.request_id}): ${JSON.stringify(requestBody, null, 2)}` }]);

    try {
      const response = await fetch('/mcp/execute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestBody) });
      if (!response.ok) {
        let errorDetail = `HTTP error! status: ${response.status}`;
        try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; } catch (e: any) { /* Ignore */ } // eslint-disable-line no-empty, no-unused-vars
        throw new Error(errorDetail);
      }
      const result: any = await response.json();
      setLogs(prev => [...prev, { type: 'info', data: `Request acknowledged: ${JSON.stringify(result)}` }]);
    } catch (error: any) { // Typed error
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('Error sending SVG export request:', error);
      setLogs(prev => [...prev, { type: 'error', data: `Failed to send SVG export request: ${errorMessage}` }]);
      setAutoRenderStatus('Error');
    }
  };

  // --- Render UI ---
  return (
    <>
      <h1>CadQuery MCP Server UI</h1>
      <StatusBar isConnected={isConnected} autoRenderStatus={autoRenderStatus} />
      <ScriptInput script={script} setScript={setScript} isConnected={isConnected} />
      <ParamsInput parameters={parameters} setParameters={setParameters} isConnected={isConnected} />
      <Controls
        onExecute={() => handleExecuteScript(false)}
        onRender={() => { console.log("[Controls] onRender clicked!"); handleExportSvgResult(null); }} // Call renamed handler
        isConnected={isConnected}
        canRender={!!lastResultId}
        isIdle={autoRenderStatus === 'Idle'}
      />
      <RenderOutput renderUrl={latestRenderUrl} /> {/* Pass renamed prop */}
      <LogDisplay logs={logs} />
    </>
  );
} // End of App component

export default App;
