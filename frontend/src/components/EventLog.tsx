import { useState } from "react";
import { Clock, AlertTriangle, Play, Square, Activity, Maximize2, X } from "lucide-react";
import type { TelemetryDocument } from "../types";

interface EventLogProps {
  events: TelemetryDocument[];
}

export function EventLog({ events }: EventLogProps) {
  const [isMobileModalOpen, setIsMobileModalOpen] = useState(false);

  const getEventIcon = (type: string | null) => {
    switch (type) {
      case "movement_started":
        return <Play className="w-4 h-4 text-warning" />;
      case "movement_stopped":
        return <Square className="w-4 h-4 text-slate-400" />;
      case "unauthorized_movement":
        return <AlertTriangle className="w-4 h-4 text-danger" />;
      default:
        return <Activity className="w-4 h-4 text-primary" />;
    }
  };

  const getEventLabel = (type: string | null) => {
    switch (type) {
      case "movement_started":
        return "Movement Started";
      case "movement_stopped":
        return "Movement Stopped";
      case "unauthorized_movement":
        return "Unauthorized Movement";
      default:
        return "Routine Update";
    }
  };

  const EventList = () => (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {events.length === 0 ? (
        <div className="text-center text-slate-500 mt-8 text-sm">
          Waiting for telemetry events...
        </div>
      ) : (
        events.map((event) => (
          <div
            key={event.id}
            className="bg-dark p-3 rounded-xl border border-dark-border/50 flex flex-col gap-2 relative overflow-hidden shrink-0"
          >
            {event.eventTriggered === "unauthorized_movement" && (
              <div className="absolute top-0 left-0 w-1 h-full bg-danger"></div>
            )}
            {event.eventTriggered === "movement_started" && (
              <div className="absolute top-0 left-0 w-1 h-full bg-warning"></div>
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {getEventIcon(event.eventTriggered)}
                <span className="text-sm font-semibold text-slate-200">
                  {getEventLabel(event.eventTriggered)}
                </span>
              </div>
              <div className="flex items-center gap-1 text-xs text-slate-500">
                <Clock className="w-3 h-3" />
                {new Date(event.status_updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </div>
            </div>

            <div className="flex justify-between text-xs text-slate-400 pl-6">
              <span>{event.status.speed.toFixed(1)} km/h</span>
            </div>
          </div>
        ))
      )}
    </div>
  );

  return (
    <>
      {/* Desktop View & Mobile collapsed view */}
      <div
        className="flex flex-col w-full h-full overflow-hidden bg-dark-panel rounded-2xl border border-dark-border cursor-pointer md:cursor-default"
        onClick={() => {
          // Only open modal on mobile
          if (window.innerWidth < 768) setIsMobileModalOpen(true);
        }}
      >
        <div className="p-3 md:p-4 border-b border-dark-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-slate-300" />
            <h3 className="font-semibold text-slate-100 text-sm md:text-base">Live Event Feed</h3>
          </div>
          <Maximize2 className="w-4 h-4 text-slate-500 md:hidden" />
        </div>
        <EventList />
      </div>

      {/* Mobile Modal View */}
      {isMobileModalOpen && (
        <div className="fixed inset-0 z-50 bg-dark/90 backdrop-blur-sm flex items-end md:hidden animate-in fade-in">
          <div className="bg-dark-panel w-full h-[85vh] rounded-t-3xl border-t border-dark-border flex flex-col shadow-2xl animate-in slide-in-from-bottom-full duration-300">
            <div className="p-4 border-b border-dark-border flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-slate-300" />
                <h3 className="font-semibold text-slate-100">Live Event Feed</h3>
              </div>
              <button
                onClick={() => setIsMobileModalOpen(false)}
                className="p-2 bg-dark rounded-full text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <EventList />
          </div>
        </div>
      )}
    </>
  );
}
