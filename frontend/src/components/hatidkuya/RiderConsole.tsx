import { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { hatidkuyaApi } from '../../utils/hatidkuyaApi';
import type { OrderData } from '../../utils/hatidkuyaApi';
import { LocationSearchInput } from './LocationSearchInput';
import { Send, CheckCircle2, Copy, Check, Play, Square, ExternalLink } from 'lucide-react';

function createRiderIcon() {
  return L.divIcon({
    className: 'rider-marker',
    html: `<div style="background:#2563eb;border:2.5px solid #ffffff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 12px rgba(37,99,235,0.8);"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

function createSourceIcon() {
  return L.divIcon({
    className: 'source-marker',
    html: `<div style="background:#10b981;border:2.5px solid #ffffff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(16,185,129,0.8);"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function createDestIcon() {
  return L.divIcon({
    className: 'dest-marker',
    html: `<div style="background:#ef4444;border:2.5px solid #ffffff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(239,68,68,0.8);"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function MapAutoBounds({ bounds }: { bounds: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (bounds.length > 0) {
      if (bounds.length === 1) {
        map.flyTo(bounds[0], 14, { animate: true });
      } else {
        const leafletBounds = L.latLngBounds(bounds.map((b) => L.latLng(b[0], b[1])));
        map.fitBounds(leafletBounds, { padding: [40, 40], maxZoom: 15 });
      }
    }
  }, [bounds, map]);
  return null;
}

interface RiderConsoleProps {
  onOpenTrack?: (trackingId: string) => void;
  liveTelemetry?: { lat: number; lng: number };
}

export function RiderConsole({ liveTelemetry }: RiderConsoleProps) {
  const [fromAddress, setFromAddress] = useState('Ayala Ave, Makati, Metro Manila');
  const [toAddress, setToAddress] = useState('BGC High Street, Taguig, Metro Manila');
  const [recipientName, setRecipientName] = useState('');
  const [itemDescription, setItemDescription] = useState('');
  const [fromCoords, setFromCoords] = useState<{ lat: number; lng: number }>({
    lat: liveTelemetry?.lat && liveTelemetry.lat !== 0 ? liveTelemetry.lat : 14.5547,
    lng: liveTelemetry?.lng && liveTelemetry.lng !== 0 ? liveTelemetry.lng : 121.0244,
  });
  const [toCoords, setToCoords] = useState<{ lat: number; lng: number }>({ lat: 14.5500, lng: 121.0500 });
  const [order, setOrder] = useState<OrderData | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  // GPS Streaming State
  const [isStreaming, setIsStreaming] = useState(false);
  const [coords, setCoords] = useState<{ lat: number; lng: number }>({
    lat: liveTelemetry?.lat && liveTelemetry.lat !== 0 ? liveTelemetry.lat : 14.5547,
    lng: liveTelemetry?.lng && liveTelemetry.lng !== 0 ? liveTelemetry.lng : 121.0244,
  });
  const [breadcrumbTrail, setBreadcrumbTrail] = useState<[number, number][]>([
    [
      liveTelemetry?.lat && liveTelemetry.lat !== 0 ? liveTelemetry.lat : 14.5547,
      liveTelemetry?.lng && liveTelemetry.lng !== 0 ? liveTelemetry.lng : 121.0244,
    ],
  ]);
  const [statusLog, setStatusLog] = useState<string[]>([]);
  const streamIntervalRef = useRef<any>(null);

  // React to incoming live bike telemetry movement
  useEffect(() => {
    if (liveTelemetry && liveTelemetry.lat !== 0 && liveTelemetry.lng !== 0) {
      setCoords({ lat: liveTelemetry.lat, lng: liveTelemetry.lng });
      setBreadcrumbTrail((prev) => {
        const last = prev[prev.length - 1];
        if (last && Math.abs(last[0] - liveTelemetry.lat) < 0.00001 && Math.abs(last[1] - liveTelemetry.lng) < 0.00001) {
          return prev;
        }
        return [...prev, [liveTelemetry.lat, liveTelemetry.lng]];
      });
      setStatusLog((prev) => [
        `[${new Date().toLocaleTimeString()}] Live Telemetry GPS: ${liveTelemetry.lat.toFixed(5)}, ${liveTelemetry.lng.toFixed(5)}`,
        ...prev.slice(0, 8),
      ]);
    }
  }, [liveTelemetry?.lat, liveTelemetry?.lng]);

  // Check for active uncompleted order on initial module load
  useEffect(() => {
    async function loadActiveOrder() {
      try {
        const active = await hatidkuyaApi.getActiveOrder();
        if (active && active.status === 'active') {
          setOrder(active);
          setFromAddress(active.from_address);
          setToAddress(active.to_address);
          if (active.recipient_name) setRecipientName(active.recipient_name);
          if (active.item_description) setItemDescription(active.item_description);
          if (active.from_coords) setFromCoords({ lat: active.from_coords.lat, lng: active.from_coords.lng });
          if (active.to_coords) setToCoords({ lat: active.to_coords.lat, lng: active.to_coords.lng });
          if (active.last_location) {
            setCoords({ lat: active.last_location.lat, lng: active.last_location.lng });
            setBreadcrumbTrail([[active.last_location.lat, active.last_location.lng]]);
          }
          addLog(`Resumed active delivery: ${active.tracking_id}`);
        }
      } catch (err) {
        console.warn('No active order to resume:', err);
      }
    }
    loadActiveOrder();
  }, []);

  const addLog = (msg: string) => {
    setStatusLog((prev) => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev.slice(0, 8)]);
  };

  const handleCreateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fromAddress.trim() || !toAddress.trim()) return;
    setLoading(true);
    try {
      const data = await hatidkuyaApi.createOrder(
        fromAddress,
        toAddress,
        recipientName.trim() || undefined,
        itemDescription.trim() || undefined,
        fromCoords,
        toCoords
      );
      setOrder({
        id: data.orderId,
        tracking_id: data.trackingId,
        from_address: data.fromAddress,
        to_address: data.toAddress,
        from_coords: data.fromCoords || { lat: fromCoords.lat, lng: fromCoords.lng },
        to_coords: data.toCoords || { lat: toCoords.lat, lng: toCoords.lng },
        recipient_name: data.recipientName || recipientName,
        item_description: data.itemDescription || itemDescription,
        status: data.status,
        created_at: data.createdAt,
      });
      setBreadcrumbTrail([[fromCoords.lat, fromCoords.lng]]);
      setCoords(fromCoords);
      addLog(`Order created! Tracking Code: ${data.trackingId}`);
    } catch (err: any) {
      alert(`Failed to create order: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const copyTrackingLink = async () => {
    if (!order?.tracking_id) return;
    const trackingUrl = `${window.location.origin}/track/${order.tracking_id}`;
    const recipientText = order.recipient_name ? ` for ${order.recipient_name}` : '';
    const itemText = order.item_description ? ` (${order.item_description})` : '';
    const shareMessage = `📦 Your package${recipientText}${itemText} is on the way via Kuya AR!\n\nTrack your live delivery in real-time:\n${trackingUrl}`;

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(shareMessage);
      }
    } catch {
      // fallback
    }

    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Live Delivery Tracking - Kuya AR',
          text: shareMessage,
        });
      } catch {
        // user closed native sheet
      }
    }

    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const toggleStreaming = () => {
    if (isStreaming) {
      stopStreaming();
    } else {
      startStreaming();
    }
  };

  const startStreaming = () => {
    if (!order?.id) return;
    setIsStreaming(true);
    addLog('Started manual GPS broadcast simulation...');

    let currentLat = coords.lat;
    let currentLng = coords.lng;

    streamIntervalRef.current = setInterval(async () => {
      currentLat += (Math.random() - 0.48) * 0.0008;
      currentLng += (Math.random() - 0.45) * 0.0008;
      const nextPos = { lat: currentLat, lng: currentLng };
      setCoords(nextPos);
      setBreadcrumbTrail((prev) => [...prev, [currentLat, currentLng]]);

      try {
        await hatidkuyaApi.updateLocation(order.id, currentLat, currentLng);
        addLog(`Broadcasted GPS: ${currentLat.toFixed(5)}, ${currentLng.toFixed(5)}`);
      } catch (err: any) {
        addLog(`GPS send warning: ${err.message}`);
      }
    }, 4000);
  };

  const stopStreaming = () => {
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
    setIsStreaming(false);
    addLog('Stopped manual GPS simulation.');
  };

  const handleSetStage = async (stage: 'going_to_pickup' | 'going_to_dropoff') => {
    if (!order?.id) return;
    try {
      await hatidkuyaApi.updateDeliveryStage(order.id, stage);
      setOrder((prev) => (prev ? { ...prev, delivery_stage: stage } : null));
      const label = stage === 'going_to_pickup' ? 'Going to Pickup' : 'Going to Dropoff';
      addLog(`Status updated: ${label}`);
    } catch (err: any) {
      alert(`Failed to update delivery stage: ${err.message}`);
    }
  };

  const handleCompleteOrder = async () => {
    stopStreaming();
    if (!order?.id) return;
    try {
      await hatidkuyaApi.completeOrder(order.id);
      setOrder((prev) => (prev ? { ...prev, status: 'completed', delivery_stage: 'completed' } : null));
      addLog('Delivery successfully completed!');
    } catch (err: any) {
      alert(`Failed to complete order: ${err.message}`);
    }
  };

  useEffect(() => {
    return () => {
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
      }
    };
  }, []);

  const trackingFullUrl = order ? `${window.location.origin}/track/${order.tracking_id}` : '';

  const activeBounds: [number, number][] = useMemo(() => {
    const list: [number, number][] = [];
    if (fromCoords) list.push([fromCoords.lat, fromCoords.lng]);
    if (toCoords) list.push([toCoords.lat, toCoords.lng]);
    if (order && coords) list.push([coords.lat, coords.lng]);
    return list.length > 0 ? list : [[14.5547, 121.0244]];
  }, [fromCoords, toCoords, order, coords]);

  return (
    <div className="w-full h-full flex-1 flex flex-col min-h-0">
      {!order ? (
        /* ================= PRE-ORDER: IMMERSIVE FULLSCREEN APP LAYOUT ================= */
        <div className="relative w-full h-full flex-1 min-h-0 rounded-none sm:rounded-2xl overflow-hidden border-0 sm:border border-slate-800/80 shadow-2xl bg-slate-950 flex flex-col">
          {/* Full Background Map */}
          <div className="absolute inset-0 z-0">
            <MapContainer
              center={[fromCoords.lat, fromCoords.lng]}
              zoom={13}
              style={{ width: '100%', height: '100%' }}
              zoomControl={false}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapAutoBounds bounds={activeBounds} />

              {/* Trajectory Polyline */}
              <Polyline
                positions={[
                  [fromCoords.lat, fromCoords.lng],
                  [toCoords.lat, toCoords.lng],
                ]}
                pathOptions={{
                  color: '#10b981',
                  weight: 4,
                  opacity: 0.85,
                  dashArray: '8, 8',
                  lineCap: 'round',
                }}
              />

              {/* Source Marker */}
              <Marker position={[fromCoords.lat, fromCoords.lng]} icon={createSourceIcon()}>
                <Popup>
                  <div className="text-slate-900 text-xs p-0.5">
                    <strong className="text-emerald-700">Origin / Pickup</strong>
                    <div className="mt-0.5 text-slate-700">{fromAddress}</div>
                  </div>
                </Popup>
              </Marker>

              {/* Destination Marker */}
              <Marker position={[toCoords.lat, toCoords.lng]} icon={createDestIcon()}>
                <Popup>
                  <div className="text-slate-900 text-xs p-0.5">
                    <strong className="text-rose-700">Destination / Drop-off</strong>
                    <div className="mt-0.5 text-slate-700">{toAddress}</div>
                  </div>
                </Popup>
              </Marker>
            </MapContainer>
          </div>

          {/* Top Floating Map Legend (Minimal, Compact) */}
          <div className="relative z-10 p-3 pointer-events-none flex justify-end items-center">
            <div className="bg-slate-900/90 backdrop-blur-xl border border-slate-700/60 py-1 px-2.5 rounded-xl shadow-xl pointer-events-auto flex items-center gap-2.5 text-[11px]">
              <span className="flex items-center gap-1 text-emerald-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-400" /> Pickup
              </span>
              <span className="flex items-center gap-1 text-rose-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-rose-400" /> Drop-off
              </span>
            </div>
          </div>

          {/* Floating Bottom Drawer Card (Compact Grab/Uber style) */}
          <div className="relative z-10 mt-auto p-2.5 sm:p-4 pointer-events-none">
            <div className="bg-slate-900/95 backdrop-blur-2xl border border-slate-800 rounded-2xl p-3.5 sm:p-4 shadow-2xl pointer-events-auto max-w-lg mx-auto">
              <form onSubmit={handleCreateOrder} className="flex flex-col gap-2">
                <LocationSearchInput
                  label="Pickup"
                  placeholder="Enter pickup point..."
                  value={fromAddress}
                  onChange={setFromAddress}
                  onSelectLocation={(loc) => {
                    setFromAddress(loc.address);
                    setFromCoords({ lat: loc.lat, lng: loc.lng });
                    setCoords({ lat: loc.lat, lng: loc.lng });
                  }}
                />

                <LocationSearchInput
                  label="Drop-off"
                  placeholder="Enter destination point..."
                  value={toAddress}
                  onChange={setToAddress}
                  onSelectLocation={(loc) => {
                    setToAddress(loc.address);
                    setToCoords({ lat: loc.lat, lng: loc.lng });
                  }}
                />

                <div className="grid grid-cols-2 gap-2">
                  <div className="flex flex-col gap-0.5">
                    <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                      Recipient
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Maria"
                      value={recipientName}
                      onChange={(e) => setRecipientName(e.target.value)}
                      className="bg-slate-950/80 border border-slate-800 focus:border-emerald-500/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none transition-all"
                    />
                  </div>

                  <div className="flex flex-col gap-0.5">
                    <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                      Items
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Package"
                      value={itemDescription}
                      onChange={(e) => setItemDescription(e.target.value)}
                      className="bg-slate-950/80 border border-slate-800 focus:border-emerald-500/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none transition-all"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full mt-1 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 text-white font-bold py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-emerald-600/20 cursor-pointer text-xs sm:text-sm"
                >
                  <Send className="w-3.5 h-3.5" />
                  {loading ? 'Creating Trip...' : 'Create Order & Start Delivery'}
                </button>
              </form>
            </div>
          </div>
        </div>
      ) : (
        /* ================= ACTIVE DELIVERY: FULLSCREEN MOBILE RIDER APP ================= */
        <div className="relative w-full h-full flex-1 min-h-0 rounded-none sm:rounded-2xl overflow-hidden border-0 sm:border border-slate-800/80 shadow-2xl bg-slate-950 flex flex-col">
          {/* Full Interactive Background Map */}
          <div className="absolute inset-0 z-0">
            <MapContainer
              center={[coords.lat, coords.lng]}
              zoom={14}
              style={{ width: '100%', height: '100%' }}
              zoomControl={false}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapAutoBounds bounds={activeBounds} />

              {/* Traveled Breadcrumb Path */}
              {breadcrumbTrail.length > 1 && (
                <Polyline
                  positions={breadcrumbTrail}
                  pathOptions={{
                    color: '#3b82f6',
                    weight: 5,
                    opacity: 0.95,
                    lineCap: 'round',
                    lineJoin: 'round',
                  }}
                />
              )}

              {/* Remaining Path */}
              {order.status !== 'completed' && (
                <Polyline
                  positions={[
                    [coords.lat, coords.lng],
                    [toCoords.lat, toCoords.lng],
                  ]}
                  pathOptions={{
                    color: '#f59e0b',
                    weight: 3.5,
                    opacity: 0.85,
                    dashArray: '8, 8',
                    lineCap: 'round',
                  }}
                />
              )}

              {/* Source Pin */}
              <Marker position={[fromCoords.lat, fromCoords.lng]} icon={createSourceIcon()}>
                <Popup>
                  <div className="text-slate-900 text-xs">
                    <strong>Pickup:</strong> {order.from_address}
                  </div>
                </Popup>
              </Marker>

              {/* Destination Pin */}
              <Marker position={[toCoords.lat, toCoords.lng]} icon={createDestIcon()}>
                <Popup>
                  <div className="text-slate-900 text-xs">
                    <strong>Drop-off:</strong> {order.to_address}
                  </div>
                </Popup>
              </Marker>

              {/* Live Kuya Rider Marker */}
              <Marker position={[coords.lat, coords.lng]} icon={createRiderIcon()}>
                <Popup>
                  <div className="text-slate-900 text-xs">
                    <strong>Kuya Rider (You)</strong>
                    <div>Lat: {coords.lat.toFixed(4)}, Lng: {coords.lng.toFixed(4)}</div>
                  </div>
                </Popup>
              </Marker>
            </MapContainer>
          </div>

          {/* Floating Top Nav: Single Ultra-Compact Combined Status & Share Pill */}
          <div className="relative z-10 p-2.5 sm:p-3 pointer-events-none flex justify-center items-center">
            <div className="bg-slate-900/95 backdrop-blur-xl border border-slate-700/70 p-1.5 rounded-2xl shadow-2xl pointer-events-auto flex items-center justify-between gap-2 max-w-lg w-full">
              {/* Left Status Pill */}
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-slate-950/80 border border-slate-800/80 shrink-0">
                <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-emerald-400 animate-ping' : 'bg-slate-400'}`} />
                <span className="text-[11px] font-bold text-white uppercase tracking-wider">
                  {order.status === 'completed' ? 'Done' : isStreaming ? 'Live GPS' : 'Paused'}
                </span>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 font-bold ml-0.5">
                  #{order.tracking_id}
                </span>
              </div>

              {/* Right Share Actions */}
              <div className="flex items-center gap-1 min-w-0">
                <button
                  onClick={copyTrackingLink}
                  className="bg-slate-800 hover:bg-slate-700 text-white text-[11px] font-semibold px-2.5 py-1.5 rounded-xl flex items-center gap-1 transition-all cursor-pointer shadow-sm"
                  title="Copy Tracking Message"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? 'Copied' : 'Share'}</span>
                </button>
                <a
                  href={trackingFullUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 p-1.5 rounded-xl transition-all cursor-pointer flex items-center justify-center border border-emerald-500/30"
                  title="Open Recipient View (New Tab)"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          </div>

          {/* Floating Bottom Drawer Controls (Compact) */}
          <div className="relative z-10 mt-auto p-2.5 sm:p-4 pointer-events-none">
            <div className="bg-slate-900/95 backdrop-blur-2xl border border-slate-800 rounded-2xl p-3 sm:p-4 shadow-2xl pointer-events-auto max-w-lg mx-auto flex flex-col gap-2">
              {/* Trip Points & Package Details */}
              <div className="grid grid-cols-2 gap-1.5 bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 text-[11px]">
                <div className="min-w-0">
                  <div className="text-[10px] uppercase font-bold text-emerald-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Pickup
                  </div>
                  <div className="text-slate-200 font-semibold truncate mt-0.5">{order.from_address}</div>
                </div>
                <div className="min-w-0">
                  <div className="text-[10px] uppercase font-bold text-rose-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400" /> Drop-off
                  </div>
                  <div className="text-slate-200 font-semibold truncate mt-0.5">{order.to_address}</div>
                </div>
                {(order.recipient_name || order.item_description) && (
                  <div className="col-span-2 pt-1.5 border-t border-slate-800/60 grid grid-cols-2 gap-1.5">
                    {order.recipient_name && (
                      <div className="truncate">
                        <span className="text-[9px] uppercase font-bold text-slate-500 mr-1">Recipient:</span>
                        <span className="text-slate-300 font-medium">{order.recipient_name}</span>
                      </div>
                    )}
                    {order.item_description && (
                      <div className="truncate">
                        <span className="text-[9px] uppercase font-bold text-slate-500 mr-1">Items:</span>
                        <span className="text-slate-300 font-medium">{order.item_description}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Delivery Stage Controls */}
              {order.status !== 'completed' && (
                <div className="flex flex-col gap-1.5">
                  <div className="grid grid-cols-2 gap-1 bg-slate-950/90 p-1 rounded-xl border border-slate-800/80">
                    <button
                      type="button"
                      onClick={() => handleSetStage('going_to_pickup')}
                      className={`py-1.5 px-2 rounded-lg font-bold text-[11px] flex items-center justify-center gap-1 transition-all cursor-pointer ${
                        (order.delivery_stage || 'going_to_pickup') === 'going_to_pickup'
                          ? 'bg-[#ff6b00] text-white shadow-sm'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      To Pickup
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSetStage('going_to_dropoff')}
                      className={`py-1.5 px-2 rounded-lg font-bold text-[11px] flex items-center justify-center gap-1 transition-all cursor-pointer ${
                        order.delivery_stage === 'going_to_dropoff'
                          ? 'bg-[#ff6b00] text-white shadow-sm'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                      To Drop-off
                    </button>
                  </div>

                  {/* Primary Action Buttons */}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={toggleStreaming}
                      className={`flex-1 py-2 px-3 rounded-xl font-bold text-xs flex items-center justify-center gap-1.5 transition-all shadow-md cursor-pointer ${
                        isStreaming
                          ? 'bg-amber-600/20 text-amber-300 border border-amber-500/30 hover:bg-amber-600/30'
                          : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-emerald-600/20'
                      }`}
                    >
                      {isStreaming ? (
                        <>
                          <Square className="w-3.5 h-3.5 fill-current" />
                          Pause GPS
                        </>
                      ) : (
                        <>
                          <Play className="w-3.5 h-3.5 fill-current" />
                          Simulate GPS
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={handleCompleteOrder}
                      className="flex-1 py-2 px-3 rounded-xl font-bold text-xs bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center gap-1.5 transition-all shadow-md shadow-emerald-600/20 cursor-pointer"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Complete Delivery
                    </button>
                  </div>
                </div>
              )}

              {order.status === 'completed' && (
                <div className="flex items-center justify-between gap-3 bg-emerald-950/40 border border-emerald-800/40 p-3 rounded-2xl">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                    <CheckCircle2 className="w-4 h-4" /> Delivery Completed
                  </div>
                  <button
                    onClick={() => setOrder(null)}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-1.5 px-4 rounded-xl text-xs transition-all cursor-pointer"
                  >
                    New Delivery
                  </button>
                </div>
              )}

              {/* Mini Log Feed */}
              {statusLog.length > 0 && (
                <div className="bg-slate-950/40 rounded-xl px-3 py-1.5 border border-slate-800/40 flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span className="truncate">{statusLog[0]}</span>
                  <span className="text-emerald-400 text-[10px] shrink-0 ml-2">Live 4s</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
