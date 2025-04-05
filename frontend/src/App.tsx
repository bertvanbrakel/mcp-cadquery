import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import StatusBar from './components/StatusBar';
import ScriptInput from './components/ScriptInput';
import ParamsInput from './components/ParamsInput';
import Controls from './components/Controls';
import RenderOutput from './components/RenderOutput';
import LogDisplay, { LogEntry } from './components/LogDisplay';

type AutoRenderStatus = 'Idle' | 'Debouncing' | 'Executing' | 'Rendering' | 'Error';

function App() {
  // --- State ---
  const [script, setScript] = useState<string>('result = cq.Workplane("XY").box(1, 2, 3)\nshow_object(result)');
  const [parameters, setParameters] = useState<string>('{}');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [latestRenderUrl, setLatestRenderUrl] = useState<string | null>(null);
  const [lastResultId, setLastResultId] = useState<string | null>(null);
  const [autoRenderStatus, setAutoRenderStatus] = useState<AutoRenderStatus>('Idle');
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null); // Ref to hold the single EventSource instance

  // --- Tool Execution Functions (defined before useEffect that uses them) ---
   // Define handleExportSvgResult *before* triggerRender which depends on it via useCallback
   const handleExportSvgResult = useCallback(async (resultIdToRender: string | null = null): Promise<void> => {
    if (!isConnected) return;
    console.log("[handleRenderResult] Called. lastResultId:", lastResultId, "resultIdToRender:", resultIdToRender);
    const targetResultId = resultIdToRender || lastResultId;
    if (!targetResultId) {
      setLogs(prev => [...prev, { type: 'error', data: 'No result ID available to render.' }]);
      if (!resultIdToRender) setAutoRenderStatus('Idle'); return;
    }
    // Set status only if manually triggered (resultIdToRender is null)
    if (!resultIdToRender) {
        setAutoRenderStatus('Rendering');
    }

    const filename = `render_${targetResultId}.svg`;
    const requestBody: any = {
      request_id: `ui-svg-${Date.now()}`, tool_name: "export_shape_to_svg",
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
    } catch (error: any) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('Error sending SVG export request:', error);
      setLogs(prev => [...prev, { type: 'error', data: `Failed to send SVG export request: ${errorMessage}` }]);
      setAutoRenderStatus('Error');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, lastResultId]); // Dependencies for this handler

  const triggerRender = useCallback((resultId: string): void => {
      handleExportSvgResult(resultId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handleExportSvgResult]); // Dependency is the memoized handler

  // --- SSE Message Handler (using useCallback) ---
  const handleSseMessage = useCallback((event: MessageEvent) => {
    console.log("[handleSseMessage] Received raw event data:", event.data);
    try {
      const messageData: LogEntry = JSON.parse(event.data);
      console.log("[handleSseMessage] Parsed messageData:", messageData);
      setLogs(prev => [...prev, messageData]);

      const isToolResult = messageData.type === 'tool_result';
      const isSuccess = messageData.result?.success;
      const filename = messageData.result?.filename;
      const resultId = messageData.result?.result_id;
      const isSvgRenderResult = isToolResult && isSuccess && typeof filename === 'string' && filename.startsWith('/renders/') && filename.endsWith('.svg');
      const isExecuteResult = isToolResult && isSuccess && typeof resultId === 'string' && !filename;

      console.log(`[handleSseMessage] Checks: isToolResult=${isToolResult}, isSuccess=${isSuccess}, filename=${filename}, resultId=${resultId}, isSvgRenderResult=${isSvgRenderResult}, isExecuteResult=${isExecuteResult}`);

      if (isSvgRenderResult) {
        console.log("[handleSseMessage] SVG Result Condition Met! Setting URL:", filename);
        setLatestRenderUrl(`${filename}?t=${Date.now()}`);
        setAutoRenderStatus('Idle');
      }
      else if (isExecuteResult) {
        console.log("[handleSseMessage] Execute Result Condition Met! Setting lastResultId:", resultId);
        setLastResultId(resultId);
        console.log("[handleSseMessage] Current autoRenderStatus before trigger check:", autoRenderStatus);
        if (autoRenderStatus === 'Executing') {
           setAutoRenderStatus('Rendering');
           triggerRender(resultId);
        } else {
           setAutoRenderStatus('Idle');
        }
      }
      else if (messageData.type === 'tool_error' && autoRenderStatus !== 'Idle' && autoRenderStatus !== 'Error') {
         console.log("[handleSseMessage] Tool Error detected during auto-render sequence.");
         setAutoRenderStatus('Error');
      } else {
         console.log("[handleSseMessage] Message did not match expected result types.");
      }
    } catch (e: any) {
      console.error("[handleSseMessage] Failed to parse SSE message data:", e);
      setLogs(prev => [...prev, { type: 'error', data: `Failed to parse message: ${event.data}` }]);
      if (autoRenderStatus !== 'Idle') setAutoRenderStatus('Error');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRenderStatus, triggerRender]); // Dependencies: autoRenderStatus, triggerRender

  // --- SSE Connection Effect ---
  useEffect(() => {
    // Only run if not already connected/connecting
    if (eventSourceRef.current) {
        console.log("SSE connection effect skipped (already exists or setting up).");
        return;
    }
    console.log("Setting up SSE connection...");
    // Create the instance within the effect scope
    const eventSource = new EventSource('/mcp');
    eventSourceRef.current = eventSource; // Store the instance immediately

    const onOpen = () => {
      console.log("SSE connection opened.");
      setIsConnected(true);
      setLogs(() => [{ type: 'status', data: 'Connected to server.' }]);
      setLatestRenderUrl(null);
      setLastResultId(null);
      setAutoRenderStatus('Idle');
    };

    const onError = (error: Event) => {
      console.error("SSE connection error:", error);
      // Check if it's the current instance before closing and resetting state
      if (eventSourceRef.current === eventSource) {
          setIsConnected(false);
          setAutoRenderStatus('Error');
          setLogs(prev => [...prev, { type: 'error', data: 'Connection error. Check server.' }]);
          eventSourceRef.current?.close();
          eventSourceRef.current = null; // Clear ref on error
      } else {
          console.log("SSE error received for a stale connection, ignoring state update.");
      }
    };

    // Attach listeners to the current instance
    eventSource.addEventListener("open", onOpen);
    eventSource.addEventListener("error", onError);
    eventSource.addEventListener("mcp_message", handleSseMessage);

    // Cleanup function
    return () => {
      console.log("Running SSE connection cleanup function...");
      // Ensure we remove listeners and close the specific instance created by this effect run
      eventSource.removeEventListener("open", onOpen);
      eventSource.removeEventListener("error", onError);
      eventSource.removeEventListener("mcp_message", handleSseMessage);
      eventSource.close();
      // Only clear the ref if it's still pointing to the instance we created
      if (eventSourceRef.current === eventSource) {
          console.log("Clearing eventSourceRef.");
          eventSourceRef.current = null;
          setIsConnected(false); // Ensure disconnected state on cleanup
      } else {
          console.log("Skipping ref clear as it points to a newer instance.");
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // <--- REMOVED handleSseMessage dependency, run only once on mount

  const handleExecuteScript = useCallback(async (isAutoTrigger: boolean = false): Promise<void> => {
    if (!isConnected) return;
    if (!isAutoTrigger) {
        if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);
        setAutoRenderStatus('Executing');
    }
    setLatestRenderUrl(null);
    setLastResultId(null);
    setLogs(prev => [...prev, { type: 'info', data: `(${isAutoTrigger ? 'Auto' : 'Manual'}) Sending script execution request...` }]);

    let paramsObj: Record<string, any> = {};
    try { paramsObj = JSON.parse(parameters); } catch (e: any) {
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
    } catch (error: any) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('Error sending execution request:', error);
      setLogs(prev => [...prev, { type: 'error', data: `Failed to send request: ${errorMessage}` }]);
      setAutoRenderStatus('Error');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, parameters, script]); // Dependencies for this handler


  // --- Debounce Effect (defined after handlers) ---
  useEffect(() => {
    if (!isConnected) return;
    setAutoRenderStatus('Debouncing');
    setLatestRenderUrl(null);
    if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);

    debounceTimeoutRef.current = setTimeout(() => {
      setAutoRenderStatus((currentStatus: AutoRenderStatus): AutoRenderStatus => {
          if (currentStatus === 'Debouncing') {
              handleExecuteScript(true); // Call handler directly
              return 'Executing';
          }
          return currentStatus;
      });
    }, 1000);

    return () => { if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [script, isConnected, handleExecuteScript]); // Add handleExecuteScript to dependencies


  // --- Render UI ---
  return (
    <>
      <h1>CadQuery MCP Server UI</h1>
      <StatusBar isConnected={isConnected} autoRenderStatus={autoRenderStatus} />
      <ScriptInput script={script} setScript={setScript} isConnected={isConnected} />
      <ParamsInput parameters={parameters} setParameters={setParameters} isConnected={isConnected} />
      <Controls
        onExecute={() => handleExecuteScript(false)}
        onRender={() => { console.log("[Controls] onRender clicked!"); handleExportSvgResult(null); }}
        isConnected={isConnected}
        canRender={!!lastResultId}
        isIdle={autoRenderStatus === 'Idle'}
      />
      <RenderOutput renderUrl={latestRenderUrl} />
      <LogDisplay logs={logs} />
    </>
  );
} // End of App component

export default App;
