import { useEffect, useRef, useState } from 'react';
import * as signalR from '@microsoft/signalr';
import { hatidkuyaApi } from '../utils/hatidkuyaApi';
import type { OrderLocation } from '../utils/hatidkuyaApi';

interface UseHatidKuyaSignalROptions {
  onLocationUpdate?: (locationData: OrderLocation) => void;
  onStatusUpdate?: (statusData: { deliveryStage?: string; status?: string }) => void;
  onOrderCompleted?: () => void;
}

export function useHatidKuyaSignalR(
  trackingId: string | null | undefined,
  { onLocationUpdate, onStatusUpdate, onOrderCompleted }: UseHatidKuyaSignalROptions
) {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const connectionRef = useRef<signalR.HubConnection | null>(null);

  const onLocationUpdateRef = useRef(onLocationUpdate);
  onLocationUpdateRef.current = onLocationUpdate;

  const onStatusUpdateRef = useRef(onStatusUpdate);
  onStatusUpdateRef.current = onStatusUpdate;

  const onOrderCompletedRef = useRef(onOrderCompleted);
  onOrderCompletedRef.current = onOrderCompleted;

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
            skipNegotiation: true,
            transport: signalR.HttpTransportType.WebSockets,
          })
          .withAutomaticReconnect()
          .configureLogging(signalR.LogLevel.Warning)
          .build();

        connection.on('locationUpdate', (locationData: OrderLocation) => {
          if (onLocationUpdateRef.current) {
            onLocationUpdateRef.current(locationData);
          }
        });

        connection.on('statusUpdate', (statusData: { deliveryStage?: string; status?: string }) => {
          if (onStatusUpdateRef.current) {
            onStatusUpdateRef.current(statusData);
          }
        });

        connection.on('orderCompleted', () => {
          if (onOrderCompletedRef.current) {
            onOrderCompletedRef.current();
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
