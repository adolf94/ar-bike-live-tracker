import { ReactNode, useEffect } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { queryClient, clearUserCache } from '../lib/queryClient';
import { useAuth } from '@adolf94/ar-auth-client';

interface QueryProviderProps {
  children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const { isAuthenticated, isLoading: isAuthLoading, logout } = useAuth();

  // Clear cache when user logs out
  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      clearUserCache();
    }
  }, [isAuthenticated, isAuthLoading]);

  // Listen for logout events and clear cache
  useEffect(() => {
    // We can't directly listen to logout from useAuth, but we can
    // clear cache whenever authentication state changes to false
    // This handles the case where user logs out from another tab/window
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key?.includes('oidc.user') && !event.newValue) {
        // OIDC token was cleared (logout)
        clearUserCache();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV && (
        <ReactQueryDevtools 
          initialIsOpen={false}
          position="bottom-right"
          buttonPosition="bottom-left"
        />
      )}
    </QueryClientProvider>
  );
}