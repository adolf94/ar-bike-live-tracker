import { useEffect, useState } from 'react';
import { AlertCircle, X } from 'lucide-react';
import type { TelemetryDocument } from '../types';

interface NotificationToastProps {
  latestEvent: TelemetryDocument | null;
}

export function NotificationToast({ latestEvent }: NotificationToastProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (latestEvent && latestEvent.eventTriggered) {
      setIsVisible(true);
      const timer = setTimeout(() => setIsVisible(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [latestEvent]);

  if (!isVisible || !latestEvent) return null;

  const isDanger = latestEvent.eventTriggered === "unauthorized_movement" || latestEvent.eventTriggered === "conn_lost";
  const isSuccess = latestEvent.eventTriggered === "conn_restore";

  return (
    <div className="fixed top-6 right-6 z-50 animate-in slide-in-from-top-5 fade-in duration-300">
      <div className={`p-4 rounded-xl shadow-2xl border flex items-start gap-4 min-w-[320px] 
        ${isDanger
          ? 'bg-danger/10 border-danger/50 text-danger-foreground'
          : isSuccess
            ? 'bg-success/10 border-success/50 text-success-foreground'
            : 'bg-dark-panel border-dark-border text-slate-200'}`}>

        <AlertCircle className={`w-6 h-6 shrink-0 mt-0.5 ${isDanger ? 'text-danger animate-pulse' : isSuccess ? 'text-success' : 'text-warning'}`} />

        <div className="flex-1">
          <h4 className={`font-semibold ${isDanger ? 'text-danger' : isSuccess ? 'text-success' : 'text-slate-100'}`}>
            {latestEvent.eventTriggered === 'unauthorized_movement' ? 'UNAUTHORIZED MOVEMENT!' :
              latestEvent.eventTriggered === 'conn_lost' ? 'Connection Lost' :
                latestEvent.eventTriggered === 'conn_restore' ? 'Connection Restored' :
                  latestEvent.eventTriggered === 'movement_started' ? 'Movement Started' :
                    latestEvent.eventTriggered === 'engine_off' ? 'Engine Off' :
                      latestEvent.eventTriggered === 'movement_stopped' ? 'Movement Stopped' :
                        'Routine Update'}
          </h4>
          <p className="text-sm mt-1 opacity-90">
            Speed: {latestEvent.status.speed.toFixed(1)} km/h<br />
            Time: {new Date(latestEvent.status_updated_at).toLocaleTimeString()}
          </p>
        </div>

        <button
          onClick={() => setIsVisible(false)}
          className="text-slate-500 hover:text-slate-300 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
