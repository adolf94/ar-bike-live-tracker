import { Battery, Key, Wifi, Gauge } from "lucide-react";
import { cn } from "../lib/utils";

interface StatusGridProps {
  speed: number;
  isIgnitionOn: boolean;
  batteryLevel: number;
  isOnline: boolean;
}

export function StatusGrid({ speed, isIgnitionOn, batteryLevel, isOnline }: StatusGridProps) {
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

      {/* Battery */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col md:flex-row items-center justify-center md:justify-start gap-1 md:gap-4 relative overflow-hidden">
        <div className="md:p-3 md:rounded-xl md:bg-dark md:border md:border-dark-border flex items-center justify-center">
          <Battery className={cn("w-5 h-5", batteryLevel > 20 ? "text-success" : "text-danger")} />
        </div>
        <div className="flex flex-col items-center md:items-start">
          <div className="hidden md:block text-sm text-slate-400 font-medium">Battery</div>
          <div className="text-xs md:text-xl font-bold text-slate-100">{batteryLevel > 0 ? `${batteryLevel}%` : "N/A"}</div>
        </div>
      </div>

      {/* Connectivity */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col md:flex-row items-center justify-center md:justify-start gap-1 md:gap-4 relative overflow-hidden">
        <div className="md:p-3 md:rounded-xl md:bg-dark md:border md:border-dark-border flex items-center justify-center">
          <Wifi className={cn("w-5 h-5", isOnline ? "text-primary" : "text-slate-500")} />
        </div>
        <div className="flex flex-col items-center md:items-start">
          <div className="hidden md:block text-sm text-slate-400 font-medium">Network</div>
          <div className="hidden md:block text-xl font-bold text-slate-100">{isOnline ? "Online" : "Offline"}</div>
        </div>
      </div>
    </div>
  );
}
