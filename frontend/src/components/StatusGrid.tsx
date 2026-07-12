import { Compass, Key, Wifi, Gauge } from "lucide-react";
import { cn } from "../lib/utils";

interface StatusGridProps {
  speed: number;
  isIgnitionOn: boolean;
  isOnline: boolean;
  course?: number;
}

const getCompassDirection = (course: number) => {
  const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const index = Math.round(((course % 360) / 45)) % 8;
  return directions[index];
};

export function StatusGrid({ speed, isIgnitionOn, isOnline, course = 0 }: StatusGridProps) {
  return (
    <div className="grid grid-cols-4 md:grid-cols-2 gap-2 md:gap-4">
      {/* Speed */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col items-center justify-center relative overflow-hidden group">
        <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity" />
        <Gauge className="w-5 h-5 md:w-6 md:h-6 text-primary mb-1 md:mb-2" />
        <span className="text-sm md:text-3xl font-bold text-slate-100 tracking-tight">
          {speed.toFixed(0)}<span className="md:hidden text-[10px] ml-0.5 text-slate-400 font-normal">km/h</span>
        </span>
        <span className="hidden md:block text-xs text-slate-400 font-medium uppercase tracking-wider mt-1">km/h</span>
      </div>

      {/* Ignition */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col items-center justify-center relative overflow-hidden group">
        <div className={cn("absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity", isIgnitionOn ? "bg-success/5" : "bg-danger/5")} />
        <Key className={cn("w-5 h-5 md:w-6 md:h-6 md:mb-2", isIgnitionOn ? "text-success" : "text-danger")} />
        <span className="hidden md:block text-sm font-bold text-slate-100 mt-1">{isIgnitionOn ? "Engine ON" : "Engine OFF"}</span>
      </div>

      {/* Compass / Heading */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col md:flex-row items-center justify-center md:justify-start gap-1 md:gap-4 relative overflow-hidden">
        <div className="md:p-3 md:rounded-xl md:bg-dark md:border md:border-dark-border flex items-center justify-center shrink-0">
          <Compass 
            className="w-5 h-5 text-primary transition-transform duration-500" 
            style={{ transform: `rotate(${course}deg)` }}
          />
        </div>
        <div className="flex flex-col items-center md:items-start min-w-0">
          <div className="hidden md:block text-sm text-slate-400 font-medium">Heading</div>
          <div className="text-xs md:text-base lg:text-lg font-bold text-slate-100 truncate w-full">
            {course}° {getCompassDirection(course)}
          </div>
        </div>
      </div>

      {/* Connectivity */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col md:flex-row items-center justify-center md:justify-start gap-1 md:gap-4 relative overflow-hidden">
        <div className="md:p-3 md:rounded-xl md:bg-dark md:border md:border-dark-border flex items-center justify-center shrink-0">
          <Wifi className={cn("w-5 h-5", isOnline ? "text-primary" : "text-slate-500")} />
        </div>
        <div className="flex flex-col items-center md:items-start min-w-0">
          <div className="hidden md:block text-sm text-slate-400 font-medium">Network</div>
          <div className="hidden md:block text-xl font-bold text-slate-100 truncate">{isOnline ? "Online" : "Offline"}</div>
          <div className="md:hidden text-[10px] font-bold text-slate-400">{isOnline ? "Online" : "Offline"}</div>
        </div>
      </div>
    </div>
  );
}
