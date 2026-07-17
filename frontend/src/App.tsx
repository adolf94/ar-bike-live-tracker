import { useEffect, useState } from 'react';
import { MapView } from './components/Map';
import { StatusGrid } from './components/StatusGrid';
import { EventLog } from './components/EventLog';
import { NotificationToast } from './components/NotificationToast';
import { useWebPubSub } from './hooks/useWebPubSub';
import { Bike, Activity, ServerCrash, Clock, Sun, Moon, LogIn, LogOut } from 'lucide-react';
import type { TelemetryDocument } from './types';
import { DeviceControls } from './components/DeviceControls';
import api, { setupAxiosAuth } from './utils/api';
import { formatDisplayDate } from './utils/date';
import { PubSubDebugger } from './components/PubSubDebugger';
import { useAuth } from '@adolf94/ar-auth-client';

function App({ theme, setTheme }: { theme: 'light' | 'dark'; setTheme: (val: 'light' | 'dark' | ((prev: 'light' | 'dark') => 'light' | 'dark')) => void }) {
  const { login, logout, isAuthenticated, getAccessToken, isLoading: isAuthLoading } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      setupAxiosAuth(getAccessToken, login);
    }
  }, [isAuthenticated, getAccessToken, login]);

  // Only initialize subscriptions if authenticated
  const { latestData, latestEvent, events, isSubscribed, setEvents, setLatestData } = useWebPubSub(isAuthenticated ? getAccessToken : undefined);
  const [isDataLoading, setIsDataLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  // Initial fetch of history and current state
  useEffect(() => {
    async function loadInitialData() {
      if (!isAuthenticated) return;

      try {
        setIsDataLoading(true);

        const [currentRes, eventsRes] = await Promise.all([
          api.get<TelemetryDocument>('/api/telemetry/current'),
          api.get<TelemetryDocument[]>('/api/telemetry/events', { params: { limit: 20 } })
        ]);

        setLatestData(prev => prev || currentRes.data); // Only set if PubSub hasn't already fired
        setEvents(prev => prev.length > 0 ? prev : eventsRes.data);
      } catch (error) {
        console.error("Failed to load initial data", error);
        setApiError("Cannot connect to backend API");
      } finally {
        setIsDataLoading(false);
      }
    }

    loadInitialData();
  }, [isAuthenticated, getAccessToken, setLatestData, setEvents]);

  // Fallback HTTP polling loop: runs every 20 seconds only if Web PubSub is not subscribed/connected
  useEffect(() => {
    if (!isAuthenticated || isSubscribed) return;

    console.log("Web PubSub disconnected. Starting fallback telemetry polling (20s interval)...");

    const pollInterval = setInterval(async () => {
      try {
        const res = await api.get<TelemetryDocument>('/api/telemetry/current');
        setLatestData(res.data);
      } catch (error) {
        console.error("Fallback telemetry polling failed:", error);
      }
    }, 20000); // 20 seconds

    return () => {
      console.log("Clearing fallback telemetry polling interval.");
      clearInterval(pollInterval);
    };
  }, [isAuthenticated, isSubscribed, setLatestData]);

  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-dark flex items-center justify-center">
        <div className="w-12 h-12 rounded-full border-4 border-dark-border border-t-primary animate-spin"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-dark flex flex-col items-center justify-center text-slate-200">
        <div className="bg-dark-panel p-8 rounded-2xl border border-dark-border shadow-xl flex flex-col items-center max-w-md w-full mx-4 text-center">
          <div className="p-4 bg-primary/20 rounded-full text-primary mb-6">
            <Bike className="w-12 h-12" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Antigravity Tracker</h1>
          <p className="text-slate-400 mb-8">Secure access required to view real-time telemetry and control devices.</p>
          <button
            onClick={() => login()}
            className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-primary-hover text-white py-3 px-6 rounded-xl font-medium transition-colors"
          >
            <LogIn className="w-5 h-5" />
            Sign In with AR ID
          </button>
        </div>
      </div>
    );
  }

  if (isDataLoading) {
    return (
      <div className="min-h-screen bg-dark flex items-center justify-center">
        <div className="w-12 h-12 rounded-full border-4 border-dark-border border-t-primary animate-spin"></div>
      </div>
    );
  }

  const locationData = latestData?.location || { lat: 0, lng: 0, course: 0 };
  const statusData = latestData?.status || { speed: 0, batteryLevel: 0, isIgnitionOn: false, isOnline: false };

  return (
    <div className="h-[100dvh] bg-dark text-slate-200 flex flex-col font-sans overflow-hidden">
      <NotificationToast latestEvent={latestEvent} />

      {/* Header */}
      <header className="h-14 md:h-16 border-b border-dark-border bg-dark-panel flex items-center justify-between px-4 md:px-6 shrink-0 z-10 relative shadow-md">
        <div className="flex items-center gap-2 md:gap-3">
          <div className="p-1.5 md:p-2 bg-primary/20 rounded-lg text-primary">
            <Bike className="w-4 h-4 md:w-5 md:h-5" />
          </div>
          <h1 className="text-lg md:text-xl font-bold tracking-tight text-white">Bike<span className="text-primary font-medium ml-1">Tracker</span></h1>
        </div>

        <div className="flex items-center gap-3 md:gap-4">
          {apiError && (
            <div className="flex items-center gap-2 text-danger text-xs md:text-sm font-medium bg-danger/10 px-2 md:px-3 py-1 md:py-1.5 rounded-full">
              <ServerCrash className="w-3 h-3 md:w-4 md:h-4" /> <span className="hidden md:inline">{apiError}</span>
            </div>
          )}
          <div className={`flex items-center gap-1.5 md:gap-2 px-2 md:px-3 py-1 md:py-1.5 rounded-full text-xs md:text-sm font-medium border ${isSubscribed ? 'bg-success/10 border-success/20 text-success' : 'bg-warning/10 border-warning/20 text-warning'}`}>
            <div className={`w-1.5 h-1.5 md:w-2 md:h-2 rounded-full ${isSubscribed ? 'bg-success animate-pulse' : 'bg-warning'}`}></div>
            {isSubscribed ? <span className="hidden md:inline">Live Connection</span> : <span className="hidden md:inline">Connecting...</span>}
            {isSubscribed ? <span className="md:hidden">Live</span> : <span className="md:hidden">Wait...</span>}
          </div>
          <button
            onClick={() => setTheme(prev => prev === 'light' ? 'dark' : 'light')}
            className="p-1.5 md:p-2 rounded-xl border border-dark-border bg-dark-panel text-slate-300 hover:text-white hover:bg-dark-border cursor-pointer transition-colors shadow-sm"
            title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          >
            {theme === 'light' ? <Moon className="w-4 h-4 md:w-5 md:h-5" /> : <Sun className="w-4 h-4 md:w-5 md:h-5" />}
          </button>
          <DeviceControls />
          <button
            onClick={() => logout()}
            className="p-1.5 md:p-2 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
            title="Sign Out"
          >
            <LogOut className="w-4 h-4 md:w-5 md:h-5" />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0 p-2 md:p-4 gap-2 md:gap-4">
        {/* Left Sidebar / Top on Mobile */}
        <div className="w-full md:w-80 flex flex-col gap-2 md:gap-4 shrink-0 min-h-0">
          <StatusGrid {...statusData} course={locationData.course} />

          {/* Desktop Event Log */}
          <div className="hidden md:flex flex-1 min-h-0">
            <EventLog events={events} />
          </div>
        </div>

        {/* Map Area */}
        <div className="flex-1 relative bg-dark-panel rounded-2xl md:rounded-3xl border border-dark-border shadow-lg overflow-hidden min-h-[200px]">
          <MapView location={locationData} isOnline={statusData.isOnline} theme={theme} />

          {/* Overlay Stats */}
          <div className="absolute top-2 left-2 md:top-4 md:left-4 z-10 bg-dark-panel/90 backdrop-blur-md border border-dark-border px-3 py-1.5 md:px-4 md:py-2 rounded-xl shadow-lg flex flex-col gap-1 md:gap-1.5">
            <div>
              <div className="text-[9px] md:text-[10px] text-slate-400 font-medium uppercase tracking-wider mb-0.5">Last Checked</div>
              <div className="text-xs md:text-sm font-semibold text-slate-100 flex items-center gap-1.5">
                <Activity className="w-3 h-3 md:w-4 md:h-4 text-primary" />
                {latestData?.last_checked_at ? formatDisplayDate(latestData.last_checked_at) : 'Never'}
              </div>
            </div>
            <div className="border-t border-dark-border/50 pt-1">
              <div className="text-[9px] md:text-[10px] text-slate-400 font-medium uppercase tracking-wider mb-0.5">State Updated</div>
              <div className="text-xs md:text-sm font-semibold text-slate-100 flex items-center gap-1.5">
                <Clock className="w-3 h-3 md:w-4 md:h-4 text-slate-400" />
                {latestData?.status_updated_at ? formatDisplayDate(latestData.status_updated_at) : 'Never'}
              </div>
            </div>
          </div>
        </div>

        {/* Mobile Event Log (shown below map, fixed height, expands on click) */}
        <div className="flex md:hidden h-32 shrink-0">
          <EventLog events={events} />
        </div>
      </main>
      <PubSubDebugger
        latestData={latestData}
        isSubscribed={isSubscribed}
        setEvents={setEvents}
        setLatestData={setLatestData}
      />
    </div>
  );
}

export default App;
