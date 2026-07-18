export function MapViewSkeleton() {
  return (
    <div className="flex-1 relative bg-dark-panel rounded-2xl md:rounded-3xl border border-dark-border shadow-lg overflow-hidden min-h-[200px]">
      {/* Skeleton Map Area */}
      <div className="absolute inset-0 bg-dark-border/30 animate-pulse rounded-2xl md:rounded-3xl" />
      
      {/* Overlay Stats Skeleton */}
      <div className="absolute top-2 left-2 md:top-4 md:left-4 z-10 bg-dark-panel/90 backdrop-blur-md border border-dark-border px-3 py-1.5 md:px-4 md:py-2 rounded-xl shadow-lg flex flex-col gap-1 md:gap-1.5">
        <div>
          <div className="h-2 w-16 bg-dark-border rounded animate-pulse mb-1" />
          <div className="h-4 w-32 bg-dark-border rounded animate-pulse flex items-center gap-1.5">
            <div className="w-3 h-3 bg-dark-border rounded-full animate-pulse" />
          </div>
        </div>
        <div className="border-t border-dark-border/50 pt-1">
          <div className="h-2 w-20 bg-dark-border rounded animate-pulse mb-1" />
          <div className="h-4 w-28 bg-dark-border rounded animate-pulse flex items-center gap-1.5">
            <div className="w-3 h-3 bg-dark-border rounded-full animate-pulse" />
          </div>
        </div>
      </div>
      
      {/* Loading Indicator */}
      <div className="absolute inset-0 flex items-center justify-center z-20">
        <div className="w-12 h-12 rounded-full border-4 border-dark-border border-t-primary animate-spin" />
      </div>
    </div>
  );
}