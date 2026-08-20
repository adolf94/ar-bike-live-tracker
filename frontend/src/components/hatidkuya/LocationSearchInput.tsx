import React, { useState, useEffect, useRef } from 'react';
import { hatidkuyaApi } from '../../utils/hatidkuyaApi';
import type { LocationSearchResult } from '../../utils/hatidkuyaApi';
import { MapPin, Loader2, X, ChevronDown, Crosshair, Navigation } from 'lucide-react';

const DEFAULT_PRESETS = [
  { name: 'Ayala Ave, Makati', address: 'Ayala Avenue, Makati, Metro Manila, Philippines', lat: 14.5547, lon: 121.0244 },
  { name: 'BGC High Street, Taguig', address: 'Bonifacio High Street, BGC, Taguig, Metro Manila, Philippines', lat: 14.5500, lon: 121.0500 },
  { name: 'Ortigas Center, Pasig', address: 'Ortigas Center, Pasig, Metro Manila, Philippines', lat: 14.5866, lon: 121.0610 },
  { name: 'SM Mall of Asia, Pasay', address: 'SM Mall of Asia, Pasay, Metro Manila, Philippines', lat: 14.5353, lon: 120.9822 },
  { name: 'Quezon City Hall', address: 'Quezon City Hall, Diliman, Quezon City, Metro Manila, Philippines', lat: 14.6477, lon: 121.0494 },
];

interface LocationSearchInputProps {
  label: string;
  placeholder: string;
  value: string;
  onChange: (val: string) => void;
  onSelectLocation?: (loc: { address: string; lat: number; lng: number }) => void;
}

export function LocationSearchInput({
  label,
  placeholder,
  value,
  onChange,
  onSelectLocation,
}: LocationSearchInputProps) {
  const [query, setQuery] = useState(value || '');
  const [suggestions, setSuggestions] = useState<LocationSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const debounceTimerRef = useRef<any>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setQuery(value || '');
  }, [value]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    onChange(val);
    setIsOpen(true);

    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);

    if (!val || val.trim().length < 2) {
      setSuggestions([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceTimerRef.current = setTimeout(async () => {
      try {
        const data = await hatidkuyaApi.searchLocations(val);
        setSuggestions(data || []);
      } catch (err) {
        console.warn('Location search error:', err);
      } finally {
        setLoading(false);
      }
    }, 350);
  };

  const handleSelect = async (item: { place_id?: string; display_name?: string; address?: string; lat: number; lon: number }) => {
    const address = item.display_name || item.address || '';
    setQuery(address);
    onChange(address);
    setIsOpen(false);
    setSuggestions([]);

    let finalLat = Number(item.lat);
    let finalLng = Number(item.lon);

    // If coordinates are not yet resolved (Google Place Autocomplete), fetch details once on selection
    if ((finalLat === 0 && finalLng === 0) || item.place_id) {
      try {
        const details = await hatidkuyaApi.getLocationDetails(item.place_id, address);
        if (details.lat && details.lng) {
          finalLat = details.lat;
          finalLng = details.lng;
        }
      } catch (err) {
        console.warn('Failed to resolve place coordinates:', err);
      }
    }

    if (onSelectLocation) {
      onSelectLocation({
        address,
        lat: finalLat,
        lng: finalLng,
      });
    }
  };

  const [isLocating, setIsLocating] = useState(false);

  const handleUseCurrentLocation = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser');
      return;
    }

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const fallbackAddress = `My Current Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;

        let resolvedAddress = fallbackAddress;
        try {
          // Attempt reverse geocode through OpenStreetMap / Nominatim
          const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`);
          if (res.ok) {
            const data = await res.json();
            if (data.display_name) {
              resolvedAddress = data.display_name;
            }
          }
        } catch {
          // keep fallback
        }

        setQuery(resolvedAddress);
        onChange(resolvedAddress);
        setIsOpen(false);
        setIsLocating(false);

        if (onSelectLocation) {
          onSelectLocation({
            address: resolvedAddress,
            lat,
            lng,
          });
        }
      },
      (err) => {
        setIsLocating(false);
        console.warn('Geolocation error:', err.message);
        alert(`Could not fetch current location: ${err.message}`);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  };

  const handleClear = () => {
    setQuery('');
    onChange('');
    setSuggestions([]);
    setIsOpen(true);
    inputRef.current?.focus();
  };

  const displayList = query.trim().length >= 2 ? suggestions : (DEFAULT_PRESETS as any[]);

  return (
    <div className="flex flex-col gap-1 mb-1.5 relative" ref={wrapperRef}>
      <div className="flex items-center justify-between">
        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{label}</label>
        <button
          type="button"
          onClick={handleUseCurrentLocation}
          disabled={isLocating}
          className="text-[10px] font-bold text-emerald-400 hover:text-emerald-300 flex items-center gap-1 cursor-pointer transition-colors"
          title="Detect and use current device location"
        >
          {isLocating ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Crosshair className="w-2.5 h-2.5" />}
          {isLocating ? 'Locating...' : 'Use Current'}
        </button>
      </div>

      <div className="relative flex items-center">
        <input
          ref={inputRef}
          type="text"
          className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 pr-16 text-slate-100 text-xs focus:outline-none focus:border-emerald-500/80 focus:ring-1 focus:ring-emerald-500/40 transition-all placeholder:text-slate-600"
          placeholder={placeholder}
          value={query}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          required
        />

        <div className="absolute right-2.5 flex items-center gap-1">
          {loading && (
            <Loader2 className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
          )}
          {query && !loading && (
            <button
              type="button"
              onClick={handleClear}
              className="text-slate-400 hover:text-slate-200 p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setIsOpen((prev: boolean) => !prev)}
            className="text-slate-400 hover:text-slate-200 p-0.5"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="absolute top-[calc(100%+4px)] left-0 right-0 z-50 bg-slate-900/95 backdrop-blur-xl border border-slate-700/80 rounded-xl shadow-2xl max-h-64 overflow-y-auto">
          {/* Quick Action: Use GPS Location */}
          <div
            onClick={handleUseCurrentLocation}
            className="px-3.5 py-2.5 bg-emerald-950/40 hover:bg-emerald-900/50 border-b border-slate-800/80 cursor-pointer text-sm flex items-center gap-3 transition-colors text-emerald-300"
          >
            <div className="bg-emerald-500/20 p-2 rounded-lg text-emerald-400 shrink-0">
              {isLocating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Navigation className="w-4 h-4" />}
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-bold text-xs flex items-center gap-1.5">
                Use Current Location {isLocating && <span className="text-[10px] font-normal text-emerald-400 animate-pulse">(Acquiring GPS...)</span>}
              </div>
              <div className="text-[11px] text-emerald-400/70 truncate">
                Detect location via device GPS
              </div>
            </div>
          </div>

          {query.trim().length < 2 && (
            <div className="px-3.5 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800">
              Quick Suggestions
            </div>
          )}

          {displayList.length === 0 && !loading && (
            <div className="p-4 text-center text-xs text-slate-400">
              No matching locations found
            </div>
          )}

          {displayList.map((item: any, index: number) => {
            const displayName = item.display_name || item.address || '';
            const title = item.name || displayName.split(',')[0];
            const sub = displayName;

            return (
              <div
                key={index}
                onClick={() => handleSelect(item)}
                className="px-3.5 py-2.5 border-b border-slate-800/60 last:border-0 cursor-pointer text-sm flex items-center gap-3 hover:bg-emerald-500/10 transition-colors"
              >
                <div className="bg-emerald-500/15 p-2 rounded-lg text-emerald-400 shrink-0">
                  <MapPin className="w-4 h-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-slate-100 truncate text-xs">
                    {title}
                  </div>
                  <div className="text-[11px] text-slate-400 truncate">
                    {sub}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
