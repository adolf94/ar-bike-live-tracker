import React, { useState, useEffect, useRef } from 'react';
import { hatidkuyaApi } from '../../utils/hatidkuyaApi';
import type { LocationSearchResult } from '../../utils/hatidkuyaApi';
import { MapPin, Loader2, X, ChevronDown } from 'lucide-react';

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

  const handleClear = () => {
    setQuery('');
    onChange('');
    setSuggestions([]);
    setIsOpen(true);
    inputRef.current?.focus();
  };

  const displayList = query.trim().length >= 2 ? suggestions : (DEFAULT_PRESETS as any[]);

  return (
    <div className="flex flex-col gap-1.5 mb-4 relative" ref={wrapperRef}>
      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</label>
      <div className="relative flex items-center">
        <input
          ref={inputRef}
          type="text"
          className="w-full bg-slate-900/60 border border-slate-700/60 rounded-xl px-4 py-2.5 pr-20 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all placeholder:text-slate-500"
          placeholder={placeholder}
          value={query}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          required
        />

        <div className="absolute right-3 flex items-center gap-1.5">
          {loading && (
            <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
          )}
          {query && !loading && (
            <button
              type="button"
              onClick={handleClear}
              className="text-slate-400 hover:text-slate-200 p-1"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setIsOpen((prev: boolean) => !prev)}
            className="text-slate-400 hover:text-slate-200 p-1"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="absolute top-[calc(100%+4px)] left-0 right-0 z-50 bg-slate-900/95 backdrop-blur-xl border border-slate-700/80 rounded-xl shadow-2xl max-h-64 overflow-y-auto">
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
