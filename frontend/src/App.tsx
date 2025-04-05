import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import StatusBar from './components/StatusBar';
import ScriptInput from './components/ScriptInput';
import ParamsInput from './components/ParamsInput';
import Controls from './components/Controls';
import RenderOutput from './components/RenderOutput'; // Will pass TJS URL to this
import LogDisplay, { LogEntry } from './components/LogDisplay';

type AutoRenderStatus = 'Idle' | 'Debouncing' | 'Executing' | 'Rendering' | 'Error'; // Removed Fetching SVG

function App() {
  // --- State ---
  const [script, setScript] = useState<string>('result = cq.Workplane("XY").box(1, 2, 3)\nshow_object(result)');
  const [parameters, setParameters] = useState<string>('{}');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [latestRenderDataUrl, setLatestRenderDataUrl] = useState<string | null>(null); // State for TJS URL
  const [lastResultId, setLastResultId] = useState<string | null>(null);
  const [autoRenderStatus, setAutoRenderStatus] = useState<AutoRenderStatus>('Idle');
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // --- Tool Execution Functions ---
   const handleExportTjsResult = useCallback(async (resultIdToRender: string | null = null): Promise<void> => { // Renamed handler
    if (!isConnected) return;
    console.log("[handleExportTjsResult] Called. lastResultId:", lastResultId, "resultIdToRender:", resultIdToRender);
    const targetResultId = resultIdToRender || lastResultId;
    if (!targetResultId) {
      setLogs(prev => [...prev, { type: 'error', data: 'No result ID available to render.' }]);
      if (!resultIdToRender) setAutoRenderStatus('Idle'); return;
    }
    if (!resultIdToRender) setAutoRenderStatus('Rendering');

    const filename = `render_${targetResultId}.tjs.json`; // Use .tjs.json extension
    const requestBody: any = {
      request_id: `ui-tjs-${Date.now()}`, // TJS request id prefix
      tool_name: "export_shape_to_tjs", // Use TJS tool name
      arguments: {
        result_id: targetResultId,
        shape_index: 0,
        filename: filename,
        options: { tolerance: 0.1, angularTolerance: 0.1 } // Example TJS options
      }
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
      // Success/failure is handled by SSE listener
    } catch (error: any) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('Error sending TJS export request:', error); // Update log message
      setLogs(prev => [...prev, { type: 'error', data: `Failed to send TJS export request: ${errorMessage}` }]); // Update log message
      setAutoRenderStatus('Error');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, lastResultId]);

  const triggerRender = useCallback((resultId: string): void => {
      handleExportTjsResult(resultId); // Call correct handler
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handleExportTjsResult]);

  // --- SSE Message Handler ---
  const handleSseMessage = useCallback((event: MessageEvent) => {
    console.log("[handleSseMessage] Received raw event data:", event.data);
    try {
      const messageData: LogEntry = JSON.parse(event.data);
      console.log("[handleSseMessage] Parsed messageData:", JSON.stringify(messageData, null, 2));
      setLogs(prev => [...prev, messageData]);

      const isToolResult = messageData.type === 'tool_result';
      const isSuccess = messageData.result?.success;
      const filename = messageData.result?.filename;
      const resultId = messageData.result?.result_id;
      // Check for TJS export result
      const isTjsExportResult = isToolResult && isSuccess && typeof filename === 'string' && filename.startsWith('/renders/') && filename.endsWith('.json');
      const isExecuteResult = isToolResult && isSuccess && typeof resultId === 'string' && !filename;

      console.log(`[handleSseMessage] Checks: isToolResult=${isToolResult}, isSuccess=${isSuccess}, filename=${filename}, resultId=${resultId}, isTjsExportResult=${isTjsExportResult}, isExecuteResult=${isExecuteResult}`);

      if (isTjsExportResult) {
        console.log("[handleSseMessage] TJS Export Result Condition Met! Setting URL:", filename);
        setLatestRenderDataUrl(`${filename}?t=${Date.now()}`); // Set TJS URL state
        setAutoRenderStatus('Idle');
      }
      else if (isExecuteResult) {
        console.log("[handleSseMessage] Execute Result Condition Met! Setting lastResultId:", resultId);
        setLastResultId(resultId);
        console.log("[handleSseMessage] Current autoRenderStatus before trigger check:", autoRenderStatus);
        if (autoRenderStatus === 'Executing') {
           setAutoRenderStatus('Rendering'); // Now means requesting TJS export
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
  }, [autoRenderStatus, triggerRender]);

  // --- SSE Connection Effect ---
  useEffect(() => {
    if (eventSourceRef.current) {
        console.log("SSE connection effect skipped (already exists or setting up).");
        return;
    }
    console.log("Setting up SSE connection...");
    const eventSource = new EventSource('/mcp');
    eventSourceRef.current = eventSource;

    const onOpen = () => {
      console.log("SSE connection opened.");
      setIsConnected(true);
      setLogs(() => [{ type: 'status', data: 'Connected to server.' }]);
      setLatestRenderDataUrl(null); // Use TJS setter
      setLastResultId(null);
      setAutoRenderStatus('Idle');
    };

    const onError = (error: Event) => {
      console.error("SSE connection error:", error);
      if (eventSourceRef.current === eventSource) {
          setIsConnected(false);
          setAutoRenderStatus('Error');
          setLogs(prev => [...prev, { type: 'error', data: 'Connection error. Check server.' }]);
          eventSourceRef.current?.close();
          eventSourceRef.current = null;
      } else {
          console.log("SSE error received for a stale connection, ignoring state update.");
      }
    };

    eventSource.addEventListener("open", onOpen);
    eventSource.addEventListener("error", onError);
    eventSource.addEventListener("mcp_message", handleSseMessage);

    return () => {
      console.log("Running SSE connection cleanup function...");
      eventSource.removeEventListener("open", onOpen);
      eventSource.removeEventListener("error", onError);
      eventSource.removeEventListener("mcp_message", handleSseMessage);
      eventSource.close();
      if (eventSourceRef.current === eventSource) {
          console.log("Clearing eventSourceRef.");
          eventSourceRef.current = null;
          setIsConnected(false);
      } else {
          console.log("Skipping ref clear as it points to a newer instance.");
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once

  // --- Script Execution Handler ---
  const handleExecuteScript = useCallback(async (isAutoTrigger: boolean = false): Promise<void> => {
    if (!isConnected) return;
    if (!isAutoTrigger) {
        if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);
        setAutoRenderStatus('Executing');
    }
    setLatestRenderDataUrl(null); // Use TJS setter
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
  }, [isConnected, parameters, script]);

  // --- Debounce Effect ---
  useEffect(() => {
    if (!isConnected) return;
    setAutoRenderStatus('Debouncing');
    setLatestRenderDataUrl(null); // Use TJS setter
    if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);

    debounceTimeoutRef.current = setTimeout(() => {
      setAutoRenderStatus((currentStatus: AutoRenderStatus): AutoRenderStatus => {
          if (currentStatus === 'Debouncing') {
              handleExecuteScript(true);
              return 'Executing';
          }
          return currentStatus;
      });
    }, 1000);

    return () => { if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [script, isConnected, handleExecuteScript]);


  // --- Render UI ---
  return (
    <>
      <h1>CadQuery MCP Server UI</h1>
      <StatusBar isConnected={isConnected} autoRenderStatus={autoRenderStatus} />
      <ScriptInput script={script} setScript={setScript} isConnected={isConnected} />
      <ParamsInput parameters={parameters} setParameters={setParameters} isConnected={isConnected} />
      <Controls
        onExecute={() => handleExecuteScript(false)}
        onRender={() => { console.log("[Controls] onRender clicked!"); handleExportTjsResult(null); }} // Call TJS handler
        isConnected={isConnected}
        canRender={!!lastResultId}
        isIdle={autoRenderStatus === 'Idle'}
      />
      <RenderOutput renderDataUrl={latestRenderDataUrl} /> {/* Pass TJS URL prop */}
      <LogDisplay logs={logs} />
    </>
  );
} // End of App component

export default App;
