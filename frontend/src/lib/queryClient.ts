import { QueryClient } from '@tanstack/react-query';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import { persistQueryClient } from '@tanstack/react-query-persist-client';

// Calculate 7 days in milliseconds
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Data stays fresh for 10 seconds, then becomes stale
      staleTime: 10 * 1000, // 10 seconds
      // Cache data for 7 days in memory
      gcTime: SEVEN_DAYS_MS,
      // Retry failed requests 3 times
      retry: 3,
      // Retry delay with exponential backoff
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      // Refetch on window focus
      refetchOnWindowFocus: true,
      // Don't refetch on mount if data is fresh
      refetchOnMount: false,
      // Don't refetch on reconnect
      refetchOnReconnect: false,
      // Throw errors instead of returning them
      throwOnError: false,
    },
    mutations: {
      retry: 2,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
    },
  },
});

// Create localStorage persister
const localStoragePersister = createSyncStoragePersister({
  storage: window.localStorage,
  key: 'obd2-query-cache',
  // Optional: Add compression if cache size becomes an issue
  // serialize: (data) => compress(JSON.stringify(data)),
  // deserialize: (str) => JSON.parse(decompress(str)),
});

// Persist query client to localStorage
persistQueryClient({
  queryClient,
  persister: localStoragePersister,
  maxAge: SEVEN_DAYS_MS,
  // Only persist queries that have a `persist` meta tag
  dehydrateOptions: {
    shouldDehydrateQuery: (query) => {
      // Persist all queries by default, but we could filter by query key
      // For example: only persist telemetry-related queries
      const queryKey = query.queryKey;
      if (Array.isArray(queryKey) && queryKey[0] === 'telemetry') {
        return true;
      }
      return false;
    },
  },
});

// Function to clear user-specific cache on logout
export const clearUserCache = () => {
  // Remove all telemetry-related queries from cache
  queryClient.removeQueries({ queryKey: ['telemetry'], exact: false });
  
  // Optionally clear all queries
  // queryClient.clear();
};

// Function to manually refresh all telemetry data
export const refreshAllTelemetry = () => {
  queryClient.invalidateQueries({ queryKey: ['telemetry'], exact: false });
};

// Export a function to get the query client instance
export const getQueryClient = () => queryClient;