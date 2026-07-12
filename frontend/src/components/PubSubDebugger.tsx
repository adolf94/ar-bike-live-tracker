import { useState, useEffect } from 'react';
import { Terminal, Bug, Play, Copy, Check, Trash2, Wifi, WifiOff } from 'lucide-react';
import type { TelemetryDocument } from '../types';

interface PubSubDebuggerProps {
  latestData: TelemetryDocument | null;
  isSubscribed: boolean;
  setEvents: React.Dispatch<React.SetStateAction<TelemetryDocument[]>>;
  setLatestData: React.Dispatch<React.SetStateAction<TelemetryDocument | null>>;
}

export function PubSubDebugger({ latestData, isSubscribed, setEvents, setLatestData }: PubSubDebuggerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [logs, setLogs] = useState<Array<{ time: string; data: TelemetryDocument }>>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Simulation form states
  const [simEvent, setSimEvent] = useState<string>('movement_started');
  const [simSpeed, setSimSpeed] = useState<number>(45);
  const [simLat, setSimLat] = useState<number>(14.5504);
  const [simLng, setSimLng] = useState<number>(121.0797);
  const [simIgnition, setSimIgnition] = useState<boolean>(true);

  // Capture real incoming events into the debug logs
  useEffect(() => {
    if (latestData) {
      setLogs(prev => [
        { time: new Date().toLocaleTimeString(), data: latestData },
        ...prev
      ].slice(0, 10)); // Keep last 10
    }
  }, [latestData]);

  // Check if we are running in local or dev mode
  const isLocalOrDev = 
    window.location.hostname === 'localhost' || 
    window.location.hostname === '127.0.0.1' ||
    import.meta.env.DEV;

  if (!isLocalOrDev) return null;

  const handleSimulate = () => {
    const mockDoc: TelemetryDocument = {
      id: `sim-${Date.now()}`,
      deviceId: latestData?.deviceId || '17026310059',
      status_updated_at: new Date().toISOString(),
      last_checked_at: new Date().toISOString(),
      location: {
        lat: simLat,
        lng: simLng,
        course: Math.floor(Math.random() * 360),
        position_time: new Date().toISOString().replace('T', ' ').substring(0, 19),
      },
      status: {
        speed: simSpeed,
        isIgnitionOn: simIgnition,
        batteryLevel: 92,
        isOnline: true,
      },
      eventTriggered: simEvent || null,
      ttl: 5184000,
    };

    // Update frontend states locally to simulate the real-time websocket message receipt
    setLatestData(mockDoc);
    setEvents(prev => [mockDoc, ...prev].slice(0, 50));

    // Also add to logs list directly
    setLogs(prev => [
      { time: `[Simulated] ${new Date().toLocaleTimeString()}`, data: mockDoc },
      ...prev
    ].slice(0, 10));
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <>
      {/* Floating Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-40 p-3.5 bg-primary text-white rounded-full shadow-2xl hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer flex items-center justify-center border border-white/10"
        title="Web PubSub Debugger"
      >
        <Bug className="w-5 h-5 animate-pulse" />
        <span className={`absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full border-2 border-dark ${isSubscribed ? 'bg-success' : 'bg-warning'}`} />
      </button>

      {/* Floating Debugger Panel */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 w-96 max-h-[500px] bg-dark-panel/95 backdrop-blur-xl border border-dark-border rounded-3xl shadow-2xl z-40 flex flex-col overflow-hidden animate-in slide-in-from-bottom-5 fade-in duration-200">
          {/* Header */}
          <div className="p-4 border-b border-dark-border flex justify-between items-center bg-dark/40">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-bold text-white tracking-wide">Web PubSub Dev Tools</h3>
            </div>
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-dark border border-dark-border text-[10px] font-semibold text-slate-300">
              {isSubscribed ? (
                <>
                  <Wifi className="w-3 h-3 text-success" />
                  <span className="text-success">Connected</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3 h-3 text-warning" />
                  <span className="text-warning">Connecting</span>
                </>
              )}
            </div>
          </div>

          {/* Scrollable Content */}
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-5">
            {/* Event Simulator Section */}
            <div className="flex flex-col gap-2.5">
              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Event Simulator
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-slate-400 font-semibold">Event Type</label>
                  <select
                    value={simEvent}
                    onChange={e => setSimEvent(e.target.value)}
                    className="bg-dark border border-dark-border rounded-lg px-2.5 py-1 text-xs text-white outline-none focus:border-primary transition-colors cursor-pointer"
                  >
                    <option value="">(None / Heartbeat)</option>
                    <option value="movement_started">Movement Started</option>
                    <option value="movement_stopped">Movement Stopped</option>
                    <option value="overspeed_alert">Overspeed Alert</option>
                    <option value="sos_alert">SOS Alert</option>
                    <option value="ignition_on">Ignition On</option>
                    <option value="ignition_off">Ignition Off</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-slate-400 font-semibold">Speed (km/h)</label>
                  <input
                    type="number"
                    value={simSpeed}
                    onChange={e => setSimSpeed(Number(e.target.value))}
                    className="bg-dark border border-dark-border rounded-lg px-2.5 py-1 text-xs text-white outline-none focus:border-primary transition-colors"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-slate-400 font-semibold">Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={simLat}
                    onChange={e => setSimLat(Number(e.target.value))}
                    className="bg-dark border border-dark-border rounded-lg px-2.5 py-1 text-xs text-white outline-none focus:border-primary transition-colors"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-slate-400 font-semibold">Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={simLng}
                    onChange={e => setSimLng(Number(e.target.value))}
                    className="bg-dark border border-dark-border rounded-lg px-2.5 py-1 text-xs text-white outline-none focus:border-primary transition-colors"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between mt-1">
                <label className="flex items-center gap-2 text-xs text-slate-300 font-medium cursor-pointer">
                  <input
                    type="checkbox"
                    checked={simIgnition}
                    onChange={e => setSimIgnition(e.target.checked)}
                    className="rounded border-dark-border bg-dark text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                  />
                  Engine Ignition On
                </label>
                <button
                  onClick={handleSimulate}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 bg-primary/20 hover:bg-primary border border-primary/30 hover:border-primary text-primary hover:text-white rounded-xl text-xs font-semibold transition-all duration-200 cursor-pointer active:scale-95 shadow-sm"
                >
                  <Play className="w-3.5 h-3.5" />
                  Inject Event
                </button>
              </div>
            </div>

            {/* Live Message Logs Section */}
            <div className="flex flex-col gap-2.5 flex-1 min-h-[200px]">
              <div className="flex justify-between items-center">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                  Live Message Log
                </span>
                {logs.length > 0 && (
                  <button
                    onClick={() => setLogs([])}
                    className="text-slate-400 hover:text-danger flex items-center gap-1 text-[10px] font-bold cursor-pointer transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Clear
                  </button>
                )}
              </div>

              <div className="flex-1 bg-dark border border-dark-border rounded-2xl p-2.5 overflow-y-auto max-h-[220px] flex flex-col gap-2 font-mono text-[10px]">
                {logs.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-slate-500 italic py-8">
                    Listening for incoming messages...
                  </div>
                ) : (
                  logs.map((log, index) => {
                    const stringified = JSON.stringify(log.data, null, 2);
                    const logId = `log-${index}`;
                    return (
                      <div key={index} className="border-b border-dark-border/40 pb-2 last:border-0 last:pb-0">
                        <div className="flex justify-between items-center text-slate-400 mb-1">
                          <span className="font-semibold text-slate-300">{log.time}</span>
                          <button
                            onClick={() => copyToClipboard(stringified, logId)}
                            className="p-1 hover:bg-dark-border rounded text-slate-400 hover:text-white transition-colors cursor-pointer"
                            title="Copy payload"
                          >
                            {copiedId === logId ? (
                              <Check className="w-3 h-3 text-success" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                        <pre className="text-slate-300 overflow-x-auto max-w-full bg-dark-panel/40 p-2 rounded-lg leading-relaxed whitespace-pre">
                          {stringified}
                        </pre>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
