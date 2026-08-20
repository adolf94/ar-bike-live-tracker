import { useEffect, useState, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { LocationData } from '../types';

// Fix Leaflet's default icon path issues in React
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

// Temporary pin icon for clicked locations
const tempPinIcon = L.divIcon({
  className: 'bg-transparent border-none',
  html: `<div class="relative w-10 h-10">
          <div class="absolute inset-0 rounded-full bg-warning/30 animate-ping"></div>
          <div class="absolute inset-2 rounded-full bg-warning border-2 border-warning"></div>
          <div class="absolute inset-3 rounded-full bg-white"></div>
         </div>`,
  iconSize: [40, 40],
  iconAnchor: [20, 40]
});

// Custom vehicle icon
const vehicleIcon = L.divIcon({
  className: 'bg-transparent border-none',
  html: `<div class="relative w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center border-2 border-primary shadow-[0_0_15px_rgba(16,185,129,0.5)]">
          <div class="w-3 h-3 bg-primary rounded-full animate-pulse"></div>
         </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16]
});

function MapUpdater({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom(), { animate: true });
  }, [center, map]);
  return null;
}

function MapResizer() {
  const map = useMap();
  useEffect(() => {
    // Wait for the layout to settle, then invalidate size to fix the grey/missing tiles bug
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 250);
    
    // Also attach a ResizeObserver to the container
    const resizeObserver = new ResizeObserver(() => {
      map.invalidateSize();
    });
    
    resizeObserver.observe(map.getContainer());
    
    return () => {
      clearTimeout(timer);
      resizeObserver.disconnect();
    };
  }, [map]);
  return null;
}

function FlyToMapUpdater({ target, onFlyComplete }: { target: LocationData | null; onFlyComplete?: () => void }) {
  const map = useMap();
  const timeoutRef = useRef<number | null>(null);
  
  useEffect(() => {
    if (target && target.lat && target.lng) {
      map.flyTo([target.lat, target.lng], 18, { animate: true, duration: 1 });
      
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      
      timeoutRef.current = window.setTimeout(() => {
        onFlyComplete?.();
      }, 1200);
    }
    
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [target, map, onFlyComplete]);
  return null;
}

export function MapView({ location, isOnline, theme, targetLocation, showTempPin }: { location: LocationData; isOnline: boolean; theme: 'light' | 'dark'; targetLocation?: LocationData | null; showTempPin?: boolean }) {
  const position: [number, number] = [location.lat || 0, location.lng || 0];
  const [tempPin, setTempPin] = useState<LocationData | null>(null);
  
  useEffect(() => {
    console.log('MapView effect:', { targetLocation, showTempPin });
    // Update temp pin when targetLocation OR showTempPin changes
    if (showTempPin && targetLocation) {
      console.log('Setting temp pin:', targetLocation);
      setTempPin(targetLocation);
    } else {
      console.log('Clearing temp pin');
      setTempPin(null);
    }
  }, [targetLocation, showTempPin]);

  const handleFlyComplete = () => {
    // Animation complete callback - no longer controls temp pin state
  };

  return (
    <div className="absolute inset-0 rounded-2xl md:rounded-3xl overflow-hidden border border-dark-border z-0">
      {(!location.lat || !location.lng) && (
        <div className="absolute inset-0 bg-dark-panel/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
          <div className="w-12 h-12 rounded-full border-4 border-dark border-t-primary animate-spin mb-4"></div>
          <p className="text-slate-300 font-medium">Waiting for GPS lock...</p>
        </div>
      )}
      
      <MapContainer 
        center={position} 
        zoom={16} 
        scrollWheelZoom={true} 
        className="absolute inset-0 w-full h-full z-0"
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url={theme === 'light' 
            ? "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          }
        />
        <MapResizer />
        <MapUpdater center={position} />
        <FlyToMapUpdater target={targetLocation ?? null} onFlyComplete={handleFlyComplete} />
        {tempPin && tempPin.lat && tempPin.lng && (
          <Marker position={[tempPin.lat, tempPin.lng]} icon={tempPinIcon}>
            <Popup className="rounded-xl">
              <div className="font-semibold text-slate-100">Selected Location</div>
              <div className="text-slate-400 text-sm mt-1">Clicked event location</div>
            </Popup>
          </Marker>
        )}
        {location.lat !== 0 && (
          <Marker position={position} icon={vehicleIcon}>
            <Popup className="rounded-xl">
              <div className="font-semibold text-slate-100">Vehicle Position</div>
              <div className="text-slate-400 text-sm mt-1">Status: {isOnline ? "Online" : "Offline"}</div>
            </Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
