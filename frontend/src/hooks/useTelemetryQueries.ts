import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../utils/api';
import type { TelemetryDocument } from '../types';

// Query keys for telemetry data
export const telemetryQueryKeys = {
  all: ['telemetry'] as const,
  current: () => [...telemetryQueryKeys.all, 'current'] as const,
  events: (limit?: number) => [...telemetryQueryKeys.all, 'events', ...(limit ? [{ limit }] : [])] as const,
  history: (params?: { startDate?: string; endDate?: string; limit?: number }) => 
    [...telemetryQueryKeys.all, 'history', ...(params ? [params] : [])] as const,
};

// Hook for fetching current telemetry data
export function useCurrentTelemetry() {
  return useQuery({
    queryKey: telemetryQueryKeys.current(),
    queryFn: async (): Promise<TelemetryDocument> => {
      const response = await api.get<TelemetryDocument>('/api/telemetry/current');
      return response.data;
    },
    // Mark this query for persistence in localStorage
    meta: {
      persist: true,
    },
    // Don't retry on 401 errors (auth issues)
    retry: (failureCount, error: any) => {
      if (error?.response?.status === 401) {
        return false; // Don't retry auth errors
      }
      return failureCount < 3; // Retry other errors up to 3 times
    },
  });
}

// Hook for fetching telemetry events
export function useTelemetryEvents(limit: number = 20) {
  return useQuery({
    queryKey: telemetryQueryKeys.events(limit),
    queryFn: async (): Promise<TelemetryDocument[]> => {
      const response = await api.get<TelemetryDocument[]>('/api/telemetry/events', {
        params: { limit },
      });
      return response.data;
    },
    meta: {
      persist: true,
    },
    retry: (failureCount, error: any) => {
      if (error?.response?.status === 401) {
        return false;
      }
      return failureCount <漁;
    },
  });
}

// Hook for fetching historical telemetry data
export function useTelemetryHistory(params?: { startDate?: string; endDate?: string; limit?: number }) {
  return useQuery({
    queryKey: telemetryQueryKeys.history(params),
    queryFn: async (): Promise<TelemetryDocument[]> => {
      const response = await api.get<TelemetryDocument[]>('/api/telemetry/history', {
        params,
      });
      return response.data;
    },
    meta: {
      persist: true,
    },
    // Historical data is less time-sensitive, longer stale time
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: !!params?.startDate, // Only fetch if we have a start date
  });
}

// Hook for manual refresh of all telemetry data
export function useRefreshTelemetry() {
  const queryClient = useQueryClient();

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: telemetryQueryKeys.all });
  };

  const refreshCurrent = () => {
    queryClient.invalidateQueries({ queryKey: telemetryQueryKeys.current() });
  };

  const refreshEvents = () => {
    queryClient.invalidateQueries({ queryKey: telemetryQueryKeys.events() });
  };

  return {
    refreshAll,
    refreshCurrent,
    refreshEvents,
  };
}

// Hook to get cached telemetry data without fetching
export function useCachedTelemetry() {
  const queryClient = useQueryClient();

  const getCachedCurrent = () => {
    return queryClient.getQueryData<TelemetryDocument>(telemetryQueryKeys.current());
  };

  const getCachedEvents = () => {
    return queryClient.getQueryData<TelemetryDocument[]>(telemetryQueryKeys.events());
  };

  return {
    getCachedCurrent,
    getCachedEvents,
  };
}