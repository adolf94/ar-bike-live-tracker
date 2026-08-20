import { useEffect, useState, useMemo } from 'react';
import { MapView } from './components/Map';
import { StatusGrid } from './components/StatusGrid';
import { StatusGridSkeleton } from './components/StatusGridSkeleton';
import { EventLog } from './components/EventLog';
import { EventLogSkeleton } from './components/EventLogSkeleton';
import { MapViewSkeleton } from './components/MapViewSkeleton';
import { NotificationToast } from './components/NotificationToast';
import { useWebPubSub } from './hooks/useWebPubSub';
import { useCurrentTelemetry, useTelemetryEvents, useRefreshTelemetry, useCachedTelemetry } from './hooks/useTelemetryQueries';
import { Bike, Activity, ServerCrash, Clock, Sun, Moon, LogIn, LogOut, RefreshCw, Send, Menu, X } from 'lucide-react';
import { DeviceControls } from './components/DeviceControls';
import { setupAxiosAuth } from './utils/api';
import { formatDisplayDate } from './utils/date';
import { PubSubDebugger } from './components/PubSubDebugger';
import { useAuth } from '@adolf94/ar-auth-client';
import type { LocationData } from './types';
import { RiderConsole } from './components/hatidkuya/RiderConsole';
import { TrackView } from './components/hatidkuya/TrackView';

function App({ theme, setTheme }: { theme: 'light' | 'dark'; setTheme: (val: 'light' | 'dark' | ((prev: 'light' | 'dark') => 'light' | 'dark')) => void }) {
  const { login, logout, isAuthenticated, getAccessToken, isLoading: isAuthLoading } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      setupAxiosAuth(getAccessToken, login);
    }
  }, [isAuthenticated, getAccessToken, login]);

  // Use TanStack Query hooks for data fetching
  const { 
    data: currentData, 
    isLoading: currentLoading, 
    isFetching: currentFetching,
    error: currentError,
  } = useCurrentTelemetry();

  const { 
    data: eventsData = [], 
    isLoading: eventsLoading, 
    isFetching: eventsFetching,
    error: eventsError,
  } = useTelemetryEvents(40);

  const { refreshAll } = useRefreshTelemetry();
  const { getCachedCurrent, getCachedEvents } = useCachedTelemetry();

  // Check if we have cached data to determine if we should show skeletons
  const hasCachedCurrent = !!getCachedCurrent();
  const hasCachedEvents = !!getCachedEvents()?.length;

  // Get data from either fresh query or cache
  const latestData = currentData || getCachedCurrent();
  const events = eventsData.length > 0 ? eventsData : (getCachedEvents() || []);

  // Only initialize WebSocket subscriptions if authenticated
  // WebSocket will update the TanStack Query cache directly
  const { latestEvent, isSubscribed } = useWebPubSub(isAuthenticated ? getAccessToken : undefined);

  // Combine errors
  const apiError = currentError?.message || eventsError?.message || null;

  // Manual refresh function
  const handleManualRefresh = () => {
    refreshAll();
  };

  const [flyToLocation, setFlyToLocation] = useState<LocationData | null>(null);
  const [showTempPin, setShowTempPin] = useState(false);

  // Routing parser helper
  const parseCurrentRoute = () => {
    const pathname = window.location.pathname;
    const urlParams = new URLSearchParams(window.location.search);
    
    // Check path /track/:trackingId or query ?track=trackingId
    const trackMatch = pathname.match(/^\/track\/([^\/]+)/);
    if (trackMatch && trackMatch[1]) {
      return { tab: 'hatidkuya' as const, trackedId: trackMatch[1] };
    }
    if (urlParams.get('track')) {
      return { tab: 'hatidkuya' as const, trackedId: urlParams.get('track') };
    }
    if (pathname === '/hatidkuya') {
      return { tab: 'hatidkuya' as const, trackedId: null };
    }
    return { tab: 'telemetry' as const, trackedId: null };
  };

  const initialRoute = useMemo(() => parseCurrentRoute(), []);

  // Submenu / Navigation Tab ('telemetry' | 'hatidkuya')
  const [activeTab, setActiveTab] = useState<'telemetry' | 'hatidkuya'>(initialRoute.tab);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [trackedOrderId, setTrackedOrderId] = useState<string | null>(initialRoute.trackedId);

  useEffect(() => {
    const handlePopState = () => {
      const route = parseCurrentRoute();
      setActiveTab(route.tab);
      setTrackedOrderId(route.trackedId);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigateToTab = (tab: 'telemetry' | 'hatidkuya') => {
    setActiveTab(tab);
    setTrackedOrderId(null);
    const newPath = tab === 'hatidkuya' ? '/hatidkuya' : '/';
    window.history.pushState({ path: newPath }, '', newPath);
  };

  const handleOpenTrack = (id: string) => {
    setTrackedOrderId(id);
    const newUrl = `/track/${id}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
  };

  const handleBackFromTrack = () => {
    setTrackedOrderId(null);
    const newUrl = activeTab === 'hatidkuya' ? '/hatidkuya' : '/';
    window.history.pushState({ path: newUrl }, '', newUrl);
  };

  // If public tracking URL is requested, show Recipient Track view immediately without requiring login
  if (trackedOrderId) {
    return (
      <div className="h-[100dvh] bg-dark text-slate-200 flex flex-col font-sans overflow-hidden">
        <header className="h-14 border-b border-dark-border bg-dark-panel flex items-center justify-between px-4 md:px-6 shrink-0 z-10">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-primary/20 rounded-lg text-primary">
              <Bike className="w-4 h-4 md:w-5 md:h-5" />
            </div>
            <span className="text-base font-bold text-white tracking-tight">HatidKuya <span className="text-primary font-medium">Live Tracking</span></span>
          </div>
          <button
            onClick={handleBackFromTrack}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer"
          >
            Dashboard
          </button>
        </header>
        <div className="flex-1 w-full h-full min-h-0 relative">
          <TrackView trackingId={trackedOrderId} onBack={handleBackFromTrack} />
        </div>
      </div>
    );
  }

  const handleFlyToLatest = () => {
    if (latestData?.location) {
      setFlyToLocation(latestData.location);
      setShowTempPin(false); // Don't show temp pin for overlay stats
    }
  };

  const handleSelectEvent = (location: LocationData) => {
    console.log('Event log clicked, location:', location);
    setFlyToLocation(location);
    setShowTempPin(true); // Show temp pin for event log clicks
  };

  // Show loading state only while auth is loading
  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-dark flex items-center justify-center">
        <div className="w-12 h-12 rounded-full border-4 border-dark-border border-t-primary animate-spin"></div>
      </div>
    );
  }

  // Show login screen if not authenticated
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

  // Get location and status data with fallbacks
  const locationData = latestData?.location || { lat: 0, lng: 0, course: 0 };
  const statusData = latestData?.status || { speed: 0, batteryLevel: 0, isIgnitionOn: false, isOnline: false };

  // Determine if we should show skeletons
  // Show skeleton if: loading AND no cached data
  const showStatusGridSkeleton = currentLoading && !hasCachedCurrent;
  const showMapSkeleton = currentLoading && !hasCachedCurrent;
  const showEventLogSkeleton = eventsLoading && !hasCachedEvents;

  return (
    <div className="h-[100dvh] bg-dark text-slate-200 flex flex-col font-sans overflow-hidden">
      <NotificationToast latestEvent={latestEvent} />

      {/* Mobile Slide-Out Left Drawer */}
      {isMobileDrawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={() => setIsMobileDrawerOpen(false)}
          />

          {/* Drawer Content */}
          <div className="relative w-72 max-w-[80vw] bg-dark-panel border-r border-dark-border h-full flex flex-col p-5 shadow-2xl z-10 animate-in slide-in-from-left duration-250">
            <div className="flex items-center justify-between pb-4 border-b border-dark-border/80">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-primary/20 rounded-xl text-primary">
                  <Bike className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-base font-extrabold text-white tracking-tight leading-none">BikeTracker</h2>
                  <span className="text-[10px] text-slate-400 font-medium">Telemetry & HatidKuya</span>
                </div>
              </div>
              <button
                onClick={() => setIsMobileDrawerOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Navigation Tabs */}
            <div className="flex flex-col gap-2 mt-5">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 px-2">Navigation</span>
              <button
                onClick={() => {
                  navigateToTab('telemetry');
                  setIsMobileDrawerOpen(false);
                }}
                className={`w-full py-3 px-3.5 rounded-xl text-sm font-semibold flex items-center gap-3 transition-all cursor-pointer ${
                  activeTab === 'telemetry'
                    ? 'bg-primary text-white shadow-lg shadow-primary/30'
                    : 'text-slate-300 hover:bg-slate-800/80'
                }`}
              >
                <Activity className="w-4 h-4" />
                <div className="text-left">
                  <div className="leading-tight">Telemetry Monitor</div>
                  <div className="text-[11px] opacity-75 font-normal">Live GPS & bike telemetry</div>
                </div>
              </button>

              <button
                onClick={() => {
                  navigateToTab('hatidkuya');
                  setIsMobileDrawerOpen(false);
                }}
                className={`w-full py-3 px-3.5 rounded-xl text-sm font-semibold flex items-center gap-3 transition-all cursor-pointer ${
                  activeTab === 'hatidkuya'
                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/30'
                    : 'text-slate-300 hover:bg-slate-800/80'
                }`}
              >
                <Send className="w-4 h-4" />
                <div className="text-left">
                  <div className="leading-tight">HatidKuya Rider</div>
                  <div className="text-[11px] opacity-75 font-normal">Delivery dispatch & console</div>
                </div>
              </button>
            </div>

            {/* Bottom Actions & User Details */}
            <div className="mt-auto pt-4 border-t border-dark-border/80 flex flex-col gap-3">
              <div className="flex items-center justify-between px-2">
                <span className="text-xs text-slate-400">Connection Status</span>
                <span className={`text-xs font-bold ${isSubscribed ? 'text-success' : 'text-warning'}`}>
                  {isSubscribed ? '● Live' : '○ Connecting'}
                </span>
              </div>

              <button
                onClick={() => logout()}
                className="w-full py-2.5 px-3 rounded-xl bg-slate-900 hover:bg-rose-950/40 text-slate-300 hover:text-rose-400 border border-slate-800 hover:border-rose-800/40 text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="h-14 md:h-16 border-b border-dark-border bg-dark-panel flex items-center justify-between px-3 sm:px-4 md:px-6 shrink-0 z-10 relative shadow-md">
        {/* Left: Mobile Drawer Trigger & Desktop Branding */}
        <div className="flex items-center gap-2 sm:gap-3 md:gap-6 min-w-0">
          {/* Mobile Menu Button */}
          <button
            onClick={() => setIsMobileDrawerOpen(true)}
            className="p-2 rounded-xl bg-slate-900 md:hidden text-slate-300 hover:text-white border border-dark-border hover:bg-slate-800 transition-colors cursor-pointer"
            title="Open Navigation Drawer"
          >
            <Menu className="w-4 h-4" />
          </button>

          {/* App Branding */}
          <div className="flex items-center gap-2 md:gap-3 shrink-0">
            <div className="p-1.5 md:p-2 bg-primary/20 rounded-lg text-primary">
              <Bike className="w-4 h-4 md:w-5 md:h-5" />
            </div>
            <h1 className="text-sm sm:text-base md:text-xl font-bold tracking-tight text-white">
              Bike<span className="text-primary font-medium ml-0.5">Tracker</span>
            </h1>
          </div>

          {/* Desktop Submenu Tabs */}
          <nav className="hidden md:flex items-center bg-slate-900/80 p-1 rounded-xl border border-dark-border">
            <button
              onClick={() => navigateToTab('telemetry')}
              className={`px-3 py-1.5 rounded-lg text-xs md:text-sm font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'telemetry'
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Telemetry</span>
            </button>
            <button
              onClick={() => navigateToTab('hatidkuya')}
              className={`px-3 py-1.5 rounded-lg text-xs md:text-sm font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'hatidkuya'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Send className="w-3.5 h-3.5" />
              <span>HatidKuya</span>
            </button>
          </nav>
        </div>

        {/* Right: Quick Action Controls */}
        <div className="flex items-center gap-1.5 sm:gap-2 md:gap-4 shrink-0">
          {apiError && (
            <div className="flex items-center gap-1 text-danger text-xs font-medium bg-danger/10 px-2 py-1 rounded-full">
              <ServerCrash className="w-3 h-3" /> <span className="hidden md:inline">{apiError}</span>
            </div>
          )}
          
          {/* Refresh Button */}
          <button
            onClick={handleManualRefresh}
            disabled={currentFetching || eventsFetching}
            className="p-2 rounded-xl border border-dark-border bg-dark-panel text-slate-300 hover:text-white hover:bg-dark-border cursor-pointer transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            title="Refresh Data"
          >
            <RefreshCw className={`w-3.5 h-3.5 sm:w-4 sm:h-4 md:w-5 md:h-5 ${(currentFetching || eventsFetching) ? 'animate-spin' : ''}`} />
          </button>

          {/* Connection Status Pill */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${isSubscribed ? 'bg-success/10 border-success/20 text-success' : 'bg-warning/10 border-warning/20 text-warning'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${isSubscribed ? 'bg-success animate-pulse' : 'bg-warning'}`}></div>
            <span className="hidden sm:inline">{isSubscribed ? 'Live' : 'Connecting'}</span>
          </div>

          <button
            onClick={() => setTheme(prev => prev === 'light' ? 'dark' : 'light')}
            className="p-2 rounded-xl border border-dark-border bg-dark-panel text-slate-300 hover:text-white hover:bg-dark-border cursor-pointer transition-colors shadow-sm"
            title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          >
            {theme === 'light' ? <Moon className="w-3.5 h-3.5 sm:w-4 sm:h-4 md:w-5 md:h-5" /> : <Sun className="w-3.5 h-3.5 sm:w-4 sm:h-4 md:w-5 md:h-5" />}
          </button>
          
          <DeviceControls />
          
          <button
            onClick={() => logout()}
            className="hidden sm:flex p-2 text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
            title="Sign Out"
          >
            <LogOut className="w-4 h-4 md:w-5 md:h-5" />
          </button>
        </div>
      </header>

      {/* Main Content */}
      {activeTab === 'hatidkuya' ? (
        <main className="flex-1 flex flex-col min-h-0 overflow-hidden p-0 sm:p-2">
          <RiderConsole
            onOpenTrack={handleOpenTrack}
            liveTelemetry={locationData}
          />
        </main>
      ) : (
        <main className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0 p-2 md:p-4 gap-2 md:gap-4">
          {/* Left Sidebar / Top on Mobile */}
          <div className="w-full md:w-80 flex flex-col gap-2 md:gap-4 shrink-0 min-h-0">
            {showStatusGridSkeleton ? (
              <StatusGridSkeleton />
            ) : (
              <StatusGrid {...statusData} course={locationData.course} />
            )}

            {/* Desktop Event Log */}
            <div className="hidden md:flex flex-1 min-h-0">
              {showEventLogSkeleton ? (
                <EventLogSkeleton />
              ) : (
                <EventLog events={events} onSelectEvent={handleSelectEvent} />
              )}
            </div>
          </div>

          {/* Map Area */}
          {showMapSkeleton ? (
            <MapViewSkeleton />
          ) : (
            <div className="flex-1 relative bg-dark-panel rounded-2xl md:rounded-3xl border border-dark-border shadow-lg overflow-hidden min-h-[200px]">
              <MapView location={locationData} isOnline={statusData.isOnline} theme={theme} targetLocation={flyToLocation} showTempPin={showTempPin} />

              {/* Overlay Stats */}
              <div className="absolute top-2 left-2 md:top-4 md:left-4 z-10 bg-dark-panel/90 backdrop-blur-md border border-dark-border px-3 py-1.5 md:px-4 md:py-2 rounded-xl shadow-lg flex flex-col gap-1 md:gap-1.5">
                <button
                  onClick={handleFlyToLatest}
                  className="text-left hover:bg-dark-border/20 rounded-lg p-1 transition-colors cursor-pointer"
                  title="Fly to latest location"
                  disabled={!latestData?.location || (locationData.lat === 0 && locationData.lng === 0)}
                >
                  <div>
                    <div className="text-[9px] md:text-[10px] text-slate-400 font-medium uppercase tracking-wider mb-0.5">Last Checked</div>
                    <div className="text-xs md:text-sm font-semibold text-slate-100 flex items-center gap-1.5">
                      <Activity className="w-3 h-3 md:w-4 md:h-4 text-primary" />
                      {latestData?.last_checked_at ? formatDisplayDate(latestData.last_checked_at) : 'Never'}
                    </div>
                  </div>
                </button>
                <div className="border-t border-dark-border/50 pt-1">
                  <button
                    onClick={handleFlyToLatest}
                    className="text-left hover:bg-dark-border/20 rounded-lg p-1 transition-colors cursor-pointer w-full"
                    title="Fly to latest location"
                    disabled={!latestData?.location || (locationData.lat === 0 && locationData.lng === 0)}
                  >
                    <div className="text-[9px] md:text-[10px] text-slate-400 font-medium uppercase tracking-wider mb-0.5">State Updated</div>
                    <div className="text-xs md:text-sm font-semibold text-slate-100 flex items-center gap-1.5">
                      <Clock className="w-3 h-3 md:w-4 md:h-4 text-slate-400" />
                      {latestData?.status_updated_at ? formatDisplayDate(latestData.status_updated_at) : 'Never'}
                    </div>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Mobile Event Log (shown below map, fixed height, expands on click) */}
          <div className="flex md:hidden h-32 shrink-0">
            {showEventLogSkeleton ? (
              <EventLogSkeleton />
            ) : (
              <EventLog events={events} onSelectEvent={handleSelectEvent} />
            )}
          </div>
        </main>
      )}
      {activeTab === 'telemetry' && (
        <PubSubDebugger
          latestData={latestData || null}
          isSubscribed={isSubscribed}
          setEvents={() => {}}
          setLatestData={() => {}}
        />
      )}
    </div>
  );
}

export default App;