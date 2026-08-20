import { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { hatidkuyaApi } from '../../utils/hatidkuyaApi';
import type { OrderData, OrderLocation } from '../../utils/hatidkuyaApi';
import { useHatidKuyaSignalR } from '../../hooks/useHatidKuyaSignalR';
import { RefreshCw, ShieldAlert, ArrowLeft } from 'lucide-react';

function createRiderIcon() {
  return L.divIcon({
    className: 'custom-rider-marker',
    html: `<div style="background:#2563eb;border:3px solid #ffffff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 15px rgba(37,99,235,0.8);"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function createSourceIcon() {
  return L.divIcon({
    className: 'custom-source-marker',
    html: `<div style="background:#10b981;border:3px solid #ffffff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(16,185,129,0.8);"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function createDestIcon() {
  return L.divIcon({
    className: 'custom-dest-marker',
    html: `<div style="background:#ef4444;border:3px solid #ffffff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(239,68,68,0.8);"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function MapRecenter({ position }: { position: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(position, map.getZoom(), { animate: true, duration: 1.5 });
  }, [position, map]);
  return null;
}

function getDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): string {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const d = R * c;
  return d.toFixed(2);
}

interface TrackViewProps {
  trackingId: string;
  onBack?: () => void;
}

export function TrackView({ trackingId, onBack }: TrackViewProps) {
  const [order, setOrder] = useState<OrderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [riderLocation, setRiderLocation] = useState<OrderLocation | null>(null);
  const [pathHistory, setPathHistory] = useState<[number, number][]>([]);
  const [lastPingTime, setLastPingTime] = useState<string | null>(null);

  const defaultCenter: [number, number] = useMemo(() => [14.5547, 121.0244], []);
  
  const destLocation: [number, number] = useMemo(() => {
    if (order?.to_coords?.lat && order?.to_coords?.lng) {
      return [order.to_coords.lat, order.to_coords.lng];
    }
    return [14.5500, 121.0500];
  }, [order?.to_coords?.lat, order?.to_coords?.lng]);

  const sourceLocation: [number, number] | null = useMemo(() => {
    if (order?.from_coords?.lat && order?.from_coords?.lng) {
      return [order.from_coords.lat, order.from_coords.lng];
    }
    return null;
  }, [order?.from_coords?.lat, order?.from_coords?.lng]);

  const updateRiderPos = (lat: number, lng: number, timestamp?: string) => {
    setRiderLocation({ lat, lng, timestamp });
    setPathHistory((prev) => {
      const last = prev[prev.length - 1];
      if (last && Math.abs(last[0] - lat) < 0.00001 && Math.abs(last[1] - lng) < 0.00001) {
        return prev;
      }
      return [...prev, [lat, lng]];
    });
    setLastPingTime(timestamp || new Date().toISOString());
  };

  const fetchOrder = async () => {
    try {
      setLoading(true);
      const [data, history] = await Promise.allSettled([
        hatidkuyaApi.getOrder(trackingId),
        hatidkuyaApi.getOrderLocationHistory(trackingId)
      ]);

      if (data.status === 'fulfilled') {
        setOrder(data.value);
        if (data.value.last_location) {
          updateRiderPos(data.value.last_location.lat, data.value.last_location.lng, data.value.last_location.timestamp);
        }
      }

      if (history.status === 'fulfilled' && Array.isArray(history.value) && history.value.length > 0) {
        const historyCoords: [number, number][] = history.value.map((pt) => [pt.lat, pt.lng]);
        setPathHistory(historyCoords);
        const lastPt = history.value[history.value.length - 1];
        if (lastPt) {
          setRiderLocation({ lat: lastPt.lat, lng: lastPt.lng, timestamp: lastPt.timestamp });
          setLastPingTime(lastPt.timestamp);
        }
      }

      if (data.status === 'rejected' || !data.value) {
        setError('This order does not exist or the tracking link is invalid.');
        setOrder(null);
        return;
      }

      if (data.value.status === 'completed') {
        setError('This order has been completed.');
        setOrder(data.value);
        return;
      }

      setError(null);
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('This order does not exist.');
      } else {
        setError(err.response?.data?.error || 'This order has been completed or does not exist.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (trackingId) {
      fetchOrder();
    }
  }, [trackingId]);

  useHatidKuyaSignalR(trackingId, {
    onLocationUpdate: (loc) => {
      updateRiderPos(loc.lat, loc.lng, loc.timestamp);
    },
    onOrderCompleted: () => {
      setOrder((prev) => (prev ? { ...prev, status: 'completed' } : null));
      setError('This order has been completed.');
    },
  });

  // Fallback Polling (every 6 seconds)
  useEffect(() => {
    if (!trackingId || order?.status === 'completed' || error) return;
    const interval = setInterval(async () => {
      try {
        const data = await hatidkuyaApi.getOrder(trackingId);
        if (data?.status === 'completed') {
          setOrder(data);
          setError('This order has been completed.');
          return;
        }
        if (data.last_location) {
          updateRiderPos(data.last_location.lat, data.last_location.lng, data.last_location.timestamp);
        }
        if (data.status) {
          setOrder((prev) => (prev ? { ...prev, status: data.status } : data));
        }
      } catch (e: any) {
        if (e.response?.status === 404) {
          setError('This order does not exist.');
        }
      }
    }, 6000);
    return () => clearInterval(interval);
  }, [trackingId, order?.status, error]);

  if (loading && !order) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-400">
        <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin mb-3" />
        <p className="text-sm">Loading live delivery details...</p>
      </div>
    );
  }

  if (error || (order && order.status === 'completed')) {
    const errorMsg = error || 'This order has been completed or does not exist.';
    return (
      <div className="flex items-center justify-center min-h-[70vh] px-4">
        <div className="max-w-md w-full p-6 md:p-8 bg-slate-900/95 backdrop-blur-2xl border border-rose-500/30 rounded-3xl text-center shadow-2xl">
          <div className="w-14 h-14 bg-rose-500/15 border border-rose-500/30 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <ShieldAlert className="w-7 h-7 text-rose-400" />
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Tracking Unavailable</h2>
          <p className="text-sm text-slate-300 mb-6 leading-relaxed">
            {errorMsg}
          </p>
          <div className="flex gap-3 justify-center">
            {onBack && (
              <button
                onClick={onBack}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold transition-all cursor-pointer"
              >
                Go to Dashboard
              </button>
            )}
            <button
              onClick={fetchOrder}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition-all cursor-pointer"
            >
              Check Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isCompleted = order?.status === 'completed';
  const riderPos: [number, number] = riderLocation ? [riderLocation.lat, riderLocation.lng] : defaultCenter;
  const distanceKm = riderLocation
    ? getDistanceKm(riderLocation.lat, riderLocation.lng, destLocation[0], destLocation[1])
    : null;

  const remainingRoute: [number, number][] = riderLocation ? [riderPos, destLocation] : [];

  return (
    <div className="flex-1 flex flex-col h-full relative w-full overflow-hidden">
      {/* Floating Status Banner */}
      <div className="absolute top-4 left-4 right-4 z-[1000] max-w-xl mx-auto pointer-events-none">
        <div className="bg-slate-900/90 backdrop-blur-xl border border-slate-700/80 rounded-2xl p-4 shadow-2xl pointer-events-auto">
          <div className="flex justify-between items-center mb-3">
            <div className="flex items-center gap-2">
              {onBack && (
                <button
                  onClick={onBack}
                  className="p-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 mr-1 transition-colors cursor-pointer"
                  title="Back"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
              )}
              <span className={`w-2.5 h-2.5 rounded-full ${isCompleted ? 'bg-slate-500' : 'bg-emerald-400 animate-ping'}`} />
              <span className="font-bold text-sm text-white">
                {isCompleted ? 'Delivery Completed' : 'Rider is on the way'}
              </span>
            </div>
            <span
              className={`text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
                isCompleted
                  ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                  : 'bg-blue-500/15 border-blue-500/30 text-blue-400'
              }`}
            >
              {order?.status?.toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-[10px] text-slate-400 font-bold uppercase block">FROM</span>
              <strong className="text-slate-200 truncate block font-medium">
                {order?.from_address}
              </strong>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 font-bold uppercase block">TO</span>
              <strong className="text-slate-200 truncate block font-medium">
                {order?.to_address}
              </strong>
            </div>
            {(order?.recipient_name || order?.item_description) && (
              <div className="col-span-2 pt-2 border-t border-slate-800/80 grid grid-cols-2 gap-3 text-xs">
                {order?.recipient_name && (
                  <div>
                    <span className="text-[10px] text-slate-400 font-bold uppercase block">RECIPIENT</span>
                    <strong className="text-emerald-400 truncate block font-medium">
                      {order.recipient_name}
                    </strong>
                  </div>
                )}
                {order?.item_description && (
                  <div>
                    <span className="text-[10px] text-slate-400 font-bold uppercase block">PACKAGE / ITEMS</span>
                    <strong className="text-slate-200 truncate block font-medium">
                      {order.item_description}
                    </strong>
                  </div>
                )}
              </div>
            )}
          </div>

          {distanceKm && !isCompleted && (
            <div className="mt-3 p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex justify-between items-center text-xs">
              <span className="text-slate-300 font-medium">Distance to Destination</span>
              <strong className="text-emerald-400 font-mono font-bold">{distanceKm} km away</strong>
            </div>
          )}

          {lastPingTime && (
            <div className="mt-2.5 pt-2 border-t border-slate-800 flex justify-between items-center text-[10px] text-slate-400 font-mono">
              <span>Live tracking</span>
              <span>Updated: {new Date(lastPingTime).toLocaleTimeString()}</span>
            </div>
          )}
        </div>
      </div>

      {/* Leaflet Map */}
      <div className="absolute inset-0 z-0">
        <MapContainer
          center={riderPos}
          zoom={14}
          style={{ width: '100%', height: '100%' }}
          zoomControl={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapRecenter position={riderPos} />

          {/* Breadcrumb path history */}
          {pathHistory.length > 1 && (
            <>
              <Polyline
                positions={pathHistory}
                pathOptions={{
                  color: '#3b82f6',
                  weight: 7,
                  opacity: 0.35,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              />
              <Polyline
                positions={pathHistory}
                pathOptions={{
                  color: '#2563eb',
                  weight: 3.5,
                  opacity: 0.9,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              />
            </>
          )}

          {/* Remaining route */}
          {remainingRoute.length === 2 && !isCompleted && (
            <Polyline
              positions={remainingRoute}
              pathOptions={{
                color: '#f59e0b',
                weight: 3,
                opacity: 0.8,
                dashArray: '6, 10',
                lineCap: 'round',
              }}
            />
          )}

          {/* Rider Marker */}
          {riderLocation && (
            <Marker position={riderPos} icon={createRiderIcon()}>
              <Popup>
                <div className="p-1 text-slate-900 text-xs">
                  <div className="font-bold">Kuya Rider (Live)</div>
                  <div>Lat: {riderLocation.lat.toFixed(4)}, Lng: {riderLocation.lng.toFixed(4)}</div>
                  {distanceKm && <div>{distanceKm} km to drop-off</div>}
                </div>
              </Popup>
            </Marker>
          )}

          {/* Source Pin */}
          {sourceLocation && (
            <Marker position={sourceLocation} icon={createSourceIcon()}>
              <Popup>
                <div className="p-1 text-slate-900 text-xs">
                  <div className="font-bold">Pickup Location</div>
                  <div>{order?.from_address}</div>
                </div>
              </Popup>
            </Marker>
          )}

          {/* Destination Marker */}
          <Marker position={destLocation} icon={createDestIcon()}>
            <Popup>
              <div className="p-1 text-slate-900 text-xs">
                <div className="font-bold">Destination</div>
                <div>{order?.to_address}</div>
              </div>
            </Popup>
          </Marker>
        </MapContainer>
      </div>
    </div>
  );
}
