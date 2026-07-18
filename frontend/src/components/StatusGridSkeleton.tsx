export function StatusGridSkeleton() {
  return (
    <div className="grid grid-cols-4 md:grid-cols-2 gap-2 md:gap-4">
      {/* Speed Skeleton */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col items-center justify-center relative overflow-hidden">
        <div className="w-5 h-5 md:w-6 md:h-6 bg-dark-border rounded-full mb-1 md:mb-2 animate-pulse" />
        <div className="h-7 md:h-12 w-16 md:w-24 bg-dark-border rounded-lg animate-pulse" />
        <div className="hidden md:block h-3 w-10 bg-dark-border rounded mt-1 animate-pulse" />
      </div>

      {/* Ignition Skeleton */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col items-center justify-center relative overflow-hidden">
        <div className="w-5 h-5 md:w-6 md:h-6 bg-dark-border rounded-full mb-1 md:mb-2 animate-pulse" />
        <div className="h-5 md:h-6 w-12 md:w-16 bg-dark-border rounded animate-pulse" />
      </div>

      {/* Compass Skeleton */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col md:flex-row items-center justify-center md:justify-start gap-1 md:gap-4 relative overflow-hidden">
        <div className="md:p-3 md:rounded-xl md:bg-dark md:border md:border-dark-border flex items-center justify-center shrink-0">
          <div className="w-5 h-5 bg-dark-border rounded-full animate-pulse" />
        </div>
        <div className="flex flex-col items-center md:items-start min-w-0">
          <div className="hidden md:block h-3 w-12 bg-dark-border rounded animate-pulse mb-1" />
          <div className="h-4 md:h-6 w-20 bg-dark-border rounded animate-pulse" />
        </div>
      </div>

      {/* Connectivity Skeleton */}
      <div className="bg-dark-panel p-2 md:p-4 rounded-xl md:rounded-2xl border border-dark-border flex flex-col md:flex-row items-center justify-center md:justify-start gap-1 md:gap-4 relative overflow-hidden">
        <div className="md:p-3 md:rounded-xl md:bg-dark md:border md:border-dark-border flex items-center justify-center shrink-0">
          <div className="w-5 h-5 bg-dark-border rounded-full animate-pulse" />
        </div>
        <div className="flex flex-col items-center md:items-start min-w-0">
          <div className="hidden md:block h-3 w-16 bg-dark-border rounded animate-pulse mb-1" />
          <div className="hidden md:block h-5 w-12 bg-dark-border rounded animate-pulse" />
          <div className="md:hidden h-3 w-10 bg-dark-border rounded animate-pulse" />
        </div>
      </div>
    </div>
  );
}