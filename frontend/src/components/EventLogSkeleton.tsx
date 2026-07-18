export function EventLogSkeleton() {
  return (
    <div className="bg-dark-panel rounded-2xl md:rounded-3xl border border-dark-border shadow-lg flex flex-col min-h-0">
      {/* Header Skeleton */}
      <div className="p-4 border-b border-dark-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-dark-border rounded animate-pulse" />
          <div className="h-5 w-24 bg-dark-border rounded animate-pulse" />
        </div>
        <div className="hidden md:block h-6 w-20 bg-dark-border rounded animate-pulse" />
      </div>

      {/* Event List Skeleton */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Skeleton Event Items */}
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="bg-dark p-3 rounded-xl border border-dark-border/50 flex flex-col gap-2 relative overflow-hidden shrink-0"
          >
            {/* Left border indicator skeleton */}
            <div className="absolute top-0 left-0 w-1 h-full bg-dark-border animate-pulse" />
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-dark-border rounded-full animate-pulse" />
                <div className="h-4 w-32 bg-dark-border rounded animate-pulse" />
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-dark-border rounded-full animate-pulse" />
                <div className="h-3 w-16 bg-dark-border rounded animate-pulse" />
              </div>
            </div>

            <div className="flex justify-between text-xs pl-6">
              <div className="h-3 w-12 bg-dark-border rounded animate-pulse" />
              <div className="h-3 w-8 bg-dark-border rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>

      {/* Mobile Modal Toggle Skeleton */}
      <div className="md:hidden p-3 border-t border-dark-border flex items-center justify-center">
        <div className="h-8 w-full bg-dark-border rounded-lg animate-pulse" />
      </div>
    </div>
  );
}