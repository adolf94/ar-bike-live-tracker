import { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { hatidkuyaApi } from '../../utils/hatidkuyaApi';
import type { OrderData, OrderLocation } from '../../utils/hatidkuyaApi';
import { useHatidKuyaSignalR } from '../../hooks/useHatidKuyaSignalR';
import {
  Bike,
  Check,
  Share2,
  RefreshCw,
  CheckCircle2,
  ArrowLeft,
  Phone,
  MessageSquare,
  Minimize2,
  Maximize2,
  Navigation,
} from 'lucide-react';

function createMoveItVehicleIcon() {
  return L.divIcon({
    className: 'moveit-vehicle-marker',
    html: `
      <div style="position:relative;display:flex;align-items:center;justify-content:center;">
        <div style="position:absolute;width:38px;height:38px;background:rgba(11,102,68,0.25);border-radius:50%;animation:ping 2s cubic-bezier(0,0,0.2,1) infinite;"></div>
        <div style="background:#0b6644;border:2.5px solid #ffffff;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(0,0,0,0.3);z-index:2;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="18.5" cy="17.5" r="3.5"/><circle cx="5.5" cy="17.5" r="3.5"/><circle cx="15" cy="5" r="1"/>
            <path d="M12 17.5V14l-3-3 4-3 2 3h2"/>
          </svg>
        </div>
      </div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

function createMoveItDestIcon() {
  return L.divIcon({
    className: 'moveit-dest-marker',
    html: `
      <div style="background:#2563eb;border:2.5px solid #ffffff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(37,99,235,0.4);">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="white" stroke="white" stroke-width="1">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
        </svg>
      </div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function createRiderIcon(theme: 'moveit' | 'lalamove' = 'lalamove') {
  if (theme === 'moveit') {
    return createMoveItVehicleIcon();
  }
  return L.divIcon({
    className: 'custom-rider-marker',
    html: `
      <div style="position:relative;display:flex;align-items:center;justify-content:center;">
        <div style="position:absolute;width:42px;height:42px;background:rgba(16,185,129,0.3);border-radius:50%;animation:ping 2s cubic-bezier(0,0,0.2,1) infinite;"></div>
        <div style="background:#10b981;border:3px solid #ffffff;border-radius:50%;width:34px;height:34px;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 14px rgba(16,185,129,0.6);z-index:2;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="18.5" cy="17.5" r="3.5"/><circle cx="5.5" cy="17.5" r="3.5"/><circle cx="15" cy="5" r="1"/>
            <path d="M12 17.5V14l-3-3 4-3 2 3h2"/>
          </svg>
        </div>
      </div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

function createSourceIcon() {
  return L.divIcon({
    className: 'custom-source-marker',
    html: `
      <div style="background:#10b981;border:3px solid #ffffff;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(16,185,129,0.4);">
        <div style="width:7px;height:7px;background:white;border-radius:50%;"></div>
      </div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function createDestIcon(theme: 'moveit' | 'lalamove' = 'lalamove') {
  if (theme === 'moveit') {
    return createMoveItDestIcon();
  }
  return L.divIcon({
    className: 'custom-dest-marker',
    html: `
      <div style="background:#ef4444;border:3px solid #ffffff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(239,68,68,0.5);">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
        </svg>
      </div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

function MapRecenter({ position }: { position: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    if (position && position[0] !== 0 && position[1] !== 0) {
      map.panTo(position, { animate: true, duration: 1.0 });
    }
  }, [position[0], position[1], map]);
  return null;
}

function formatLocalTime(isoOrStr?: string | null): string {
  if (!isoOrStr) return new Date().toLocaleTimeString();
  try {
    let normalized = isoOrStr.trim();
    if (!normalized.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(normalized)) {
      normalized += 'Z';
    }
    const d = new Date(normalized);
    return isNaN(d.getTime()) ? new Date().toLocaleTimeString() : d.toLocaleTimeString();
  } catch {
    return new Date().toLocaleTimeString();
  }
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
  const [copied, setCopied] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const [riderLocation, setRiderLocation] = useState<OrderLocation | null>(null);
  const [pathHistory, setPathHistory] = useState<[number, number][]>([]);
  const [lastPingTime, setLastPingTime] = useState<string | null>(null);

  const theme: 'moveit' | 'lalamove' = (order?.theme as any) === 'moveit' ? 'moveit' : 'lalamove';
  const isMoveIt = theme === 'moveit';

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

  const stage = order?.delivery_stage || 'going_to_pickup';
  const isGoingToPickup = stage === 'going_to_pickup';

  // If going to pickup, active target is pickup coordinates; otherwise drop-off destination
  const activeTargetLocation: [number, number] = useMemo(() => {
    if (isGoingToPickup && sourceLocation) {
      return sourceLocation;
    }
    return destLocation;
  }, [isGoingToPickup, sourceLocation, destLocation]);

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
        const sortedHistory = [...history.value].sort(
          (a, b) => new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime()
        );
        const historyCoords: [number, number][] = sortedHistory.map((pt) => [pt.lat, pt.lng]);
        setPathHistory(historyCoords);
        const lastPt = sortedHistory[sortedHistory.length - 1];
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

  const { isConnected } = useHatidKuyaSignalR(trackingId, {
    onLocationUpdate: (loc) => {
      updateRiderPos(loc.lat, loc.lng, loc.timestamp);
    },
    onStatusUpdate: (statusData: any) => {
      console.log('Received SignalR statusUpdate event:', statusData);
      setOrder((prev) => {
        if (!prev) return prev;
        const newStage = statusData.deliveryStage || statusData.delivery_stage || statusData.stage || prev.delivery_stage;
        const newStatus = statusData.status || prev.status;
        const newTheme = statusData.theme || prev.theme;
        return {
          ...prev,
          status: newStatus as any,
          delivery_stage: newStage as any,
          theme: newTheme as any,
        };
      });
    },
    onOrderCompleted: () => {
      setOrder((prev) => (prev ? { ...prev, status: 'completed', delivery_stage: 'completed' } : null));
      setError('This order has been completed.');
    },
    onReconnected: () => {
      console.log('[SignalR TrackView] Reconnected — refetching order and location history');
      fetchOrder();
    },
  });

  // Fallback HTTP Polling
  useEffect(() => {
    if (!trackingId || order?.status === 'completed' || error || isConnected) {
      return;
    }
    const interval = setInterval(async () => {
      try {
        const data = await hatidkuyaApi.getOrder(trackingId);
        if (data?.status === 'completed') {
          setOrder(data);
          setError('This order has been completed.');
          return;
        }
        if (data) {
          setOrder(data);
          if (data.last_location) {
            updateRiderPos(data.last_location.lat, data.last_location.lng, data.last_location.timestamp);
          }
        }
      } catch (e: any) {
        if (e.response?.status === 404) {
          setError('This order does not exist.');
        }
      }
    }, 120000);
    return () => clearInterval(interval);
  }, [trackingId, order?.status, error, isConnected]);

  const copyTrackingLink = async () => {
    const trackingUrl = window.location.href;
    let shareTitle = '';
    let shareMessage = '';

    if (isMoveIt) {
      const passengerText = order?.recipient_name ? ` (${order.recipient_name})` : '';
      shareTitle = 'HatidKuya Live Ride Tracking';
      shareMessage = `🛵 Track my live HatidKuya ride${passengerText}!\n\nDriver: Kuya AR • PCX Black (Plate: P2637F)\n\nLive Ride Status:\n${trackingUrl}`;
    } else {
      const recipientText = order?.recipient_name ? ` for ${order.recipient_name}` : '';
      const itemText = order?.item_description ? ` (${order.item_description})` : '';
      shareTitle = 'Live Package Tracking';
      shareMessage = `📦 Your package${recipientText}(${itemText}) is on the way!\n\nTrack your live delivery in real-time:\n${trackingUrl}`;
    }

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
          title: shareTitle,
          text: shareMessage,
        });
      } catch {
        // user closed native sheet
      }
    }

    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading && !order) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[70vh] text-slate-400">
        <RefreshCw className={`w-10 h-10 animate-spin mb-4 ${isMoveIt ? 'text-[#e53935]' : 'text-emerald-500'}`} />
        <p className="text-sm font-semibold text-slate-200">Connecting to live rider...</p>
        <span className="text-xs text-slate-500 mt-1">
          {isMoveIt ? 'Move It Live Tracking' : 'Live Delivery Tracking'}
        </span>
      </div>
    );
  }

  if (error || (order && order.status === 'completed')) {
    const errorMsg = error || 'This order has been completed or does not exist.';
    return (
      <div className="flex items-center justify-center min-h-[70vh] px-4">
        <div className={`max-w-md w-full p-6 md:p-8 bg-slate-900/95 backdrop-blur-2xl border ${isMoveIt ? 'border-red-500/30' : 'border-emerald-500/30'} rounded-3xl text-center shadow-2xl`}>
          <div className={`w-16 h-16 ${isMoveIt ? 'bg-red-500/15 border-red-500/30' : 'bg-emerald-500/15 border-emerald-500/30'} border rounded-2xl flex items-center justify-center mx-auto mb-4`}>
            <CheckCircle2 className={`w-8 h-8 ${isMoveIt ? 'text-[#e53935]' : 'text-emerald-500'}`} />
          </div>
          <h2 className="text-xl font-bold text-white mb-2">
            {order?.status === 'completed' ? 'Delivery Completed' : 'Tracking Unavailable'}
          </h2>
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
              className={`px-5 py-2.5 ${isMoveIt ? 'bg-[#e53935] hover:bg-[#d32f2f] shadow-red-500/30' : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/30'} text-white rounded-xl text-xs font-bold transition-all cursor-pointer shadow-lg`}
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
    ? getDistanceKm(riderLocation.lat, riderLocation.lng, activeTargetLocation[0], activeTargetLocation[1])
    : null;

  // Estimated travel time: assuming 25 km/h urban motorcycle speed
  const estMins = distanceKm ? Math.max(2, Math.round((Number(distanceKm) / 25) * 60)) : null;

  // Theme-specific colors and rider details
  const primaryColor = isMoveIt ? '#e53935' : '#10b981';

  return (
    <div className="flex-1 flex flex-col h-full relative w-full overflow-hidden bg-slate-950">
      {/* Full Background Map */}
      <div className="absolute inset-0 z-0">
        <MapContainer
          center={riderPos}
          zoom={16}
          style={{ width: '100%', height: '100%' }}
          zoomControl={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapRecenter position={riderPos} />

          {/* Breadcrumb Traveled Trail */}
          {pathHistory.length > 1 && (
            <Polyline
              positions={pathHistory}
              pathOptions={{
                color: isMoveIt ? '#2563eb' : primaryColor,
                weight: 5,
                opacity: 0.9,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
          )}

          {/* Remaining Path to Active Target (Pickup or Dropoff) */}
          {!isCompleted && (
            <Polyline
              positions={[riderPos, activeTargetLocation]}
              pathOptions={{
                color: isMoveIt ? '#3b82f6' : isGoingToPickup ? '#10b981' : '#f59e0b',
                weight: isMoveIt ? 5 : 3.5,
                opacity: 0.9,
                dashArray: isMoveIt ? undefined : '8, 8',
                lineCap: 'round',
              }}
            />
          )}

          {/* Source Pin */}
          {sourceLocation && (
            <Marker position={sourceLocation} icon={createSourceIcon()}>
              <Popup>
                <div className="p-1 text-slate-900 text-xs">
                  <div className="font-bold text-emerald-600">Pickup Point</div>
                  <div>{order?.from_address}</div>
                </div>
              </Popup>
            </Marker>
          )}

          {/* Destination Pin */}
          <Marker position={destLocation} icon={createDestIcon(theme)}>
            <Popup>
              <div className="p-1 text-slate-900 text-xs">
                <div className={`font-bold ${isMoveIt ? 'text-blue-600' : 'text-rose-600'}`}>Drop-off Destination</div>
                <div>{order?.to_address}</div>
              </div>
            </Popup>
          </Marker>

          {/* Live Rider Marker */}
          {riderLocation && (
            <Marker position={riderPos} icon={createRiderIcon(theme)}>
              <Popup>
                <div className="p-1.5 text-xs">
                  <div className={`font-extrabold text-sm mb-1 ${isMoveIt ? 'text-[#0b6644]' : 'text-emerald-500'}`}>
                    Kuya AR (Live)
                  </div>
                  <div className="text-slate-700 font-mono text-[11px]">
                    Lat: {riderLocation.lat.toFixed(4)}, Lng: {riderLocation.lng.toFixed(4)}
                  </div>
                  {distanceKm && (
                    <div className={`font-medium text-[11px] mt-0.5 ${isMoveIt ? 'text-blue-700' : 'text-emerald-700'}`}>
                      {distanceKm} km away from destination
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          )}
        </MapContainer>
      </div>

      {/* Floating Header UI */}
      {isMoveIt ? (
        /* MOVE IT / SHARED TRIP STATUS TOP APP BAR */
        <div className="relative z-10 w-full bg-[#0b6644] text-white shadow-lg pointer-events-auto">
          <div className="max-w-2xl mx-auto px-4 py-3 sm:py-3.5 flex items-center justify-between">
            <button
              onClick={onBack || (() => window.history.back())}
              className="p-1 -ml-1 text-white hover:bg-white/10 rounded-full transition-colors cursor-pointer"
              title="Back"
            >
              <ArrowLeft className="w-5 h-5 sm:w-6 sm:h-6 stroke-[2.5]" />
            </button>

            <div className="text-center flex-1 mx-2">
              <h1 className="text-xs sm:text-sm font-semibold text-white tracking-tight leading-tight line-clamp-1">
                Live Ride Tracking: {order?.recipient_name ? order.recipient_name.split(' ')[0] : 'Passenger'}
              </h1>
              <p className="text-[11px] text-emerald-100/90 font-normal leading-tight mt-0.5">
                Shared Trip Status
              </p>
            </div>

            <div className="w-5 sm:w-6" />
          </div>
        </div>
      ) : (
        /* DEFAULT APP FLOATING HEADER */
        <div className="relative z-10 p-3 sm:p-4 pointer-events-none flex justify-between items-center">
          {onBack ? (
            <button
              onClick={onBack}
              className="p-2.5 rounded-2xl bg-white/95 text-slate-800 shadow-xl pointer-events-auto hover:bg-slate-100 transition-all cursor-pointer flex items-center gap-1.5 text-xs font-bold"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Back</span>
            </button>
          ) : <div />}

          <div className="bg-white/95 backdrop-blur-xl border border-emerald-200 px-3.5 py-2 rounded-2xl shadow-xl pointer-events-auto flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
            <span className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Order #{order?.tracking_id}
            </span>
            <button
              onClick={copyTrackingLink}
              className="p-1 hover:bg-slate-100 rounded-lg text-slate-500 hover:text-emerald-600 transition-colors cursor-pointer"
              title="Share Tracking Link"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Share2 className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      )}

      {/* Floating Right Map Tool Controls for Move It */}
      {isMoveIt && (
        <div className="relative z-10 flex flex-col items-end gap-2.5 p-3 sm:p-4 pointer-events-none mt-2">
          <div className="flex flex-col gap-2 pointer-events-auto">
            <button
              onClick={() => {
                if (riderLocation) {
                  // Handled by map recenter
                }
              }}
              className="w-10 h-10 rounded-full bg-white text-slate-700 shadow-lg border border-slate-200 flex items-center justify-center hover:bg-slate-50 cursor-pointer transition-transform active:scale-95"
              title="Recenter"
            >
              <Navigation className="w-5 h-5 text-slate-600 rotate-45" />
            </button>
          </div>
        </div>
      )}

      {/* Floating Bottom Sheet */}
      <div className="relative z-10 mt-auto p-3 sm:p-5 pointer-events-none">
        {isMoveIt ? (
          /* ================= MOVE IT / GRAB OFFICIAL BOTTOM CARD ================= */
          <div className="bg-white text-slate-900 rounded-3xl p-4 sm:p-5 shadow-2xl pointer-events-auto max-w-lg mx-auto border border-slate-200/90 flex flex-col gap-3 transition-all duration-300">
            {/* Grab Handle */}
            <div
              className="w-10 h-1 bg-slate-300 hover:bg-slate-400 rounded-full mx-auto -mt-1 cursor-pointer transition-colors"
              onClick={() => setIsMinimized(!isMinimized)}
              title="Toggle card size"
            />

            {/* Top Arriving In & Share Button */}
            <div className="flex items-center justify-between pt-1">
              <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
                {isCompleted
                  ? 'Arrived at Destination'
                  : estMins
                    ? `Arriving in ${estMins} mins`
                    : 'Trip in Progress'}
              </h2>

              <button
                onClick={copyTrackingLink}
                className="px-3.5 py-1.5 bg-blue-50/80 hover:bg-blue-100 text-blue-600 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer border border-blue-200/60 shadow-sm"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Share2 className="w-3.5 h-3.5" />}
                <span>{copied ? 'Link Copied' : 'Share'}</span>
              </button>
            </div>

            {/* Driver Profile, Vehicle Details & Contact Action */}
            <div className="flex items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-3 min-w-0">
                {/* Driver Avatar */}
                <div className="relative w-12 h-12 rounded-full overflow-hidden bg-slate-200 border-2 border-slate-100 shadow-sm flex items-center justify-center shrink-0">
                  <img
                    src="/images/kuya.jpg"
                    alt="Kuya AR"
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                  <div className="absolute inset-0 flex items-center justify-center text-slate-400 font-bold text-lg pointer-events-none -z-10">
                    <Bike className="w-6 h-6" />
                  </div>
                </div>

                {/* Driver Text Info */}
                <div className="min-w-0">
                  <div className="text-xs sm:text-sm font-semibold text-slate-800 truncate">
                    Rider: Kuya AR
                  </div>
                  <div className="text-xs text-slate-500 font-normal truncate">
                    PCX Black
                  </div>
                  <div className="text-xs text-slate-500 font-normal truncate">
                    Plate: P2637F
                  </div>
                </div>
              </div>

              {/* Contact Button */}
              <div className="flex items-center gap-1.5 shrink-0">
                <a
                  href="https://m.me/adolf28"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-blue-50/80 hover:bg-blue-100 text-blue-600 hover:text-blue-700 rounded-xl text-xs font-semibold transition-colors border border-blue-200/60 shadow-sm flex items-center gap-1.5 cursor-pointer"
                  title="Contact Kuya AR"
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>Contact</span>
                </a>
              </div>
            </div>

            {/* Collapsible Trip Addresses */}
            {!isMinimized && (
              <div className="space-y-2 text-xs pt-2 border-t border-slate-100">
                <div className="flex items-start gap-2.5">
                  <div className="mt-1 w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0 shadow-sm" />
                  <div className="min-w-0 flex-1">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Pick-up</span>
                    <span className="font-semibold text-slate-800 truncate block">{order?.from_address}</span>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <div className="mt-1 w-2.5 h-2.5 rounded-full bg-blue-600 shrink-0 shadow-sm" />
                  <div className="min-w-0 flex-1">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Drop-off</span>
                    <span className="font-semibold text-slate-800 truncate block">{order?.to_address}</span>
                  </div>
                </div>

                {(order?.recipient_name || order?.item_description) && (
                  <div className="pt-2 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs">
                    {order.recipient_name && (
                      <div>
                        <span className="text-[10px] uppercase font-bold text-slate-400 block">Passenger</span>
                        <span className="font-bold text-slate-800 truncate block">{order.recipient_name}</span>
                      </div>
                    )}
                    {order.item_description && (
                      <div>
                        <span className="text-[10px] uppercase font-bold text-slate-400 block">Note / Items</span>
                        <span className="font-bold text-slate-800 truncate block">{order.item_description}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Live Updated Footer */}
            {lastPingTime && (
              <div className="pt-1 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span className="text-slate-400">{isMinimized ? 'Tap to expand details' : ''}</span>
                <span>Updated: {formatLocalTime(lastPingTime)}</span>
              </div>
            )}
          </div>
        ) : (
          /* ================= LALAMOVE STYLE (CUSTOM THEME COLOR) ================= */
          <div className="bg-white text-slate-900 rounded-3xl p-4 sm:p-5 shadow-2xl pointer-events-auto max-w-xl mx-auto border border-slate-200/80 flex flex-col gap-3 transition-all duration-300">
            {/* Grab Handle */}
            <div
              className="w-12 h-1.5 bg-slate-200 hover:bg-slate-300 rounded-full mx-auto -mt-1 mb-1 cursor-pointer transition-colors"
              onClick={() => setIsMinimized(!isMinimized)}
              title="Toggle card size"
            />

            {/* Top Status & ETA Header */}
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 cursor-pointer" onClick={() => setIsMinimized(!isMinimized)}>
              <div className="flex items-center gap-3">
                {isMinimized && (
                  <div className="relative w-11 h-11 rounded-2xl overflow-hidden bg-emerald-600 border-2 border-white shadow-md shadow-emerald-500/20 shrink-0 flex items-center justify-center">
                    <img
                      src="/images/kuya.jpg"
                      alt="Kuya AR"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                    <div className="absolute inset-0 flex items-center justify-center text-white font-bold text-lg pointer-events-none -z-10">
                      <Bike className="w-5 h-5" />
                    </div>
                  </div>
                )}

                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-600 flex items-center gap-1">
                    <Bike className="w-3.5 h-3.5" />
                    {isCompleted
                      ? 'Delivery Completed'
                      : isGoingToPickup
                        ? 'Kuya AR is heading to pickup'
                        : 'Kuya AR is heading to drop-off'}
                  </span>
                  <h3 className="text-sm sm:text-base font-extrabold text-slate-900 tracking-tight mt-0.5">
                    {isCompleted
                      ? 'Package Delivered'
                      : estMins
                        ? `Arriving in ~${estMins} mins`
                        : isGoingToPickup
                          ? 'Heading to Pickup Point'
                          : 'Delivering Package'}
                  </h3>
                </div>
              </div>

              <div className="flex items-center gap-1.5 sm:gap-2">
                <a
                  href="https://m.me/adolf28"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="w-8 h-8 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-600 flex items-center justify-center transition-colors border border-emerald-200/60 cursor-pointer"
                  title="Message Kuya AR"
                >
                  <MessageSquare className="w-4 h-4" />
                </a>

                {distanceKm && !isCompleted && (
                  <div className="text-right bg-emerald-50 px-2 py-1 rounded-xl border border-emerald-200/60 hidden xs:block">
                    <span className="text-[9px] uppercase font-bold text-slate-500 block leading-none">
                      {isGoingToPickup ? 'To Pickup' : 'To Drop-off'}
                    </span>
                    <span className="text-xs font-extrabold text-emerald-600 font-mono leading-none">{distanceKm} km</span>
                  </div>
                )}

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsMinimized(!isMinimized);
                  }}
                  className="w-8 h-8 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center transition-colors cursor-pointer border border-slate-200"
                  title={isMinimized ? "Expand card" : "Minimize card"}
                >
                  {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Collapsible Content */}
            {!isMinimized && (
              <>
                {/* Stepper Progress Bar */}
                <div className="grid grid-cols-4 gap-1 items-center pt-1">
                  <div className="flex flex-col items-center gap-1">
                    <div className="w-full h-1.5 rounded-full bg-emerald-600" />
                    <span className="text-[10px] font-bold text-slate-800">Matched</span>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <div className={`w-full h-1.5 rounded-full ${isGoingToPickup ? 'bg-emerald-600 animate-pulse' : 'bg-emerald-600'}`} />
                    <span className={`text-[10px] font-bold ${isGoingToPickup ? 'text-emerald-600' : 'text-slate-800'}`}>Pickup</span>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <div className={`w-full h-1.5 rounded-full ${!isGoingToPickup && !isCompleted ? 'bg-emerald-600 animate-pulse' : isCompleted ? 'bg-emerald-600' : 'bg-slate-200'}`} />
                    <span className={`text-[10px] font-bold ${!isGoingToPickup && !isCompleted ? 'text-emerald-600' : isCompleted ? 'text-slate-800' : 'text-slate-400'}`}>Drop-off</span>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <div className={`w-full h-1.5 rounded-full ${isCompleted ? 'bg-emerald-600' : 'bg-slate-200'}`} />
                    <span className={`text-[10px] font-bold ${isCompleted ? 'text-emerald-600' : 'text-slate-400'}`}>Completed</span>
                  </div>
                </div>

                {/* Driver & Vehicle Contact Card */}
                <div className="bg-slate-50 p-3 rounded-2xl border border-slate-200/60 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="relative w-11 h-11 rounded-2xl overflow-hidden bg-emerald-600 border-2 border-white shadow-md shadow-emerald-500/20 flex items-center justify-center">
                      <img
                        src="/images/kuya.jpg"
                        alt="Kuya AR"
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                        }}
                      />
                      <div className="absolute inset-0 flex items-center justify-center text-white font-bold text-lg pointer-events-none -z-10">
                        <Bike className="w-6 h-6" />
                      </div>
                    </div>
                    <div>
                      <div className="font-bold text-sm text-slate-900">Kuya AR</div>
                      <div className="text-xs text-slate-500 flex items-center gap-1.5">
                        <span className="bg-emerald-100 text-emerald-700 font-bold px-1.5 py-0.2 rounded text-[10px]">Motorcycle</span>
                        <span className="text-[11px] font-mono text-slate-600 font-semibold">P2637F • PCX Black</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <a
                      href="https://m.me/adolf28"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-9 h-9 rounded-xl bg-white border border-slate-200 text-slate-700 flex items-center justify-center hover:bg-emerald-50 hover:border-emerald-200 transition-colors shadow-sm cursor-pointer"
                      title="Call Kuya AR on Messenger"
                    >
                      <Phone className="w-4 h-4 text-emerald-600" />
                    </a>
                    <a
                      href="https://m.me/adolf28"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-9 h-9 rounded-xl bg-white border border-slate-200 text-slate-700 flex items-center justify-center hover:bg-emerald-50 hover:border-emerald-200 transition-colors shadow-sm cursor-pointer"
                      title="Message Kuya AR on Messenger"
                    >
                      <MessageSquare className="w-4 h-4 text-emerald-600" />
                    </a>
                  </div>
                </div>

                {/* Trip Addresses & Package Details */}
                <div className="space-y-2 text-xs">
                  <div className="flex items-start gap-2.5">
                    <div className="mt-1 w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0 shadow-sm" />
                    <div className="min-w-0 flex-1">
                      <span className="text-[10px] uppercase font-bold text-slate-400 block">Pick-up</span>
                      <span className="font-semibold text-slate-800 truncate block">{order?.from_address}</span>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5">
                    <div className="mt-1 w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0 shadow-sm" />
                    <div className="min-w-0 flex-1">
                      <span className="text-[10px] uppercase font-bold text-slate-400 block">Drop-off</span>
                      <span className="font-semibold text-slate-800 truncate block">{order?.to_address}</span>
                    </div>
                  </div>

                  {(order?.recipient_name || order?.item_description) && (
                    <div className="pt-2 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs">
                      {order.recipient_name && (
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-400 block">Recipient</span>
                          <span className="font-bold text-slate-800 truncate block">{order.recipient_name}</span>
                        </div>
                      )}
                      {order.item_description && (
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-400 block">Items</span>
                          <span className="font-bold text-slate-800 truncate block">{order.item_description}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Live Updated Footer */}
            {lastPingTime && (
              <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span className="text-slate-500">{isMinimized ? 'Tap to expand' : 'HatidKuya Live Tracking'}</span>
                <span>Updated: {formatLocalTime(lastPingTime)}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
