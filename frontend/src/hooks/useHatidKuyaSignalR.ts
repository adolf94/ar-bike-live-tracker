import { useEffect, useRef, useState } from 'react';
import * as signalR from '@microsoft/signalr';
import { hatidkuyaApi } from '../utils/hatidkuyaApi';
import type { OrderLocation } from '../utils/hatidkuyaApi';

interface UseHatidKuyaSignalROptions {
  onLocationUpdate?: (locationData: OrderLocation) => void;
  onOrderCompleted?: () => void;
}

export function useHatidKuyaSignalR(
  trackingId: string | null | undefined,
  { onLocationUpdate, onOrderCompleted }: UseHatidKuyaSignalROptions
) {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const connectionRef = useRef<signalR.HubConnection | null>(null);

  useEffect(() => {
    if (!trackingId) return;

    let isMounted = true;

    async function startConnection() {
      try {
        const negotiation = await hatidkuyaApi.negotiate(trackingId!);
        if (!isMounted) return;

        const connection = new signalR.HubConnectionBuilder()
          .withUrl(negotiation.url, {
            accessTokenFactory: () => negotiation.accessToken,
          })
          .withAutomaticReconnect()
          .configureLogging(signalR.LogLevel.Warning)
          .build();

        connection.on('locationUpdate', (locationData: OrderLocation) => {
          if (onLocationUpdate) {
            onLocationUpdate(locationData);
          }
        });

        connection.on('orderCompleted', () => {
          if (onOrderCompleted) {
            onOrderCompleted();
          }
        });

        await connection.start();
        if (isMounted) {
          connectionRef.current = connection;
          setIsConnected(true);
          setConnectionError(null);
        }
      } catch (err: any) {
        if (isMounted) {
          console.warn('SignalR delivery subscription notice (falling back to interval polling):', err.message);
          setConnectionError(err.message);
        }
      }
    }

    startConnection();

    return () => {
      isMounted = false;
      if (connectionRef.current) {
        connectionRef.current.stop();
      }
    };
  }, [trackingId]);

  return { isConnected, connectionError };
}
