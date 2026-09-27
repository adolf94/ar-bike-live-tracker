import { useEffect, useRef, useState } from 'react';
import { backendBase } from '../utils/api';
import type { OrderLocation } from '../utils/hatidkuyaApi';

interface UseHatidKuyaSignalROptions {
  onLocationUpdate?: (locationData: OrderLocation) => void;
  onStatusUpdate?: (statusData: { deliveryStage?: string; status?: string }) => void;
  onOrderCompleted?: () => void;
  onReconnected?: (connectionId?: string | null) => void;
}

/** Envelope pushed by the self-hosted hub for order groups. */
type OrderEvent =
  | { type: 'locationUpdated'; data: OrderLocation }
  | { type: 'orderStatus'; data: any }
  | { type: 'orderCompleted' };

/**
 * Native WebSocket subscription to the self-hosted hub
 * (`/ws/order-{trackingId}`).
 *
 * Replaces the old Azure SignalR negotiate + HubConnection flow. The server
 * joins every socket to the order group straight from the URL (no
 * negotiate/joinGroup round-trips) and pushes JSON envelopes:
 *   { type: 'locationUpdated', data } | { type: 'orderStatus', data } | { type: 'orderCompleted' }
 *
 * The hook keeps its original name/signature so consumers (TrackView) are
 * unchanged; `onReconnected` fires after every successful (re)open so the
 * view can refetch order state that was missed while disconnected.
 */
export function useHatidKuyaSignalR(
  trackingId: string | null | undefined,
  { onLocationUpdate, onStatusUpdate, onOrderCompleted, onReconnected }: UseHatidKuyaSignalROptions
) {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const onLocationUpdateRef = useRef(onLocationUpdate);
  onLocationUpdateRef.current = onLocationUpdate;

  const onStatusUpdateRef = useRef(onStatusUpdate);
  onStatusUpdateRef.current = onStatusUpdate;

  const onOrderCompletedRef = useRef(onOrderCompleted);
  onOrderCompletedRef.current = onOrderCompleted;

  const onReconnectedRef = useRef(onReconnected);
  onReconnectedRef.current = onReconnected;

  useEffect(() => {
    if (!trackingId) return;

    let disposed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let pingTimer: number | undefined;
    let attempt = 0;

    const wsUrl = () =>
      `${backendBase.replace(/^http/, 'ws')}/ws/${encodeURIComponent(`order-${trackingId}`)}`;

    const handleEvent = (event: OrderEvent) => {
      switch (event.type) {
        case 'locationUpdated':
          onLocationUpdateRef.current?.(event.data);
          break;
        case 'orderStatus':
          console.log('[WS useHatidKuyaSignalR] orderStatus payload received:', event.data);
          onStatusUpdateRef.current?.(event.data);
          break;
        case 'orderCompleted':
          console.log('[WS useHatidKuyaSignalR] orderCompleted payload received');
          onOrderCompletedRef.current?.();
          break;
      }
    };

    const clearTimers = () => {
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      if (pingTimer !== undefined) window.clearInterval(pingTimer);
      reconnectTimer = undefined;
      pingTimer = undefined;
    };

    const connect = () => {
      if (disposed) return;

      try {
        socket = new WebSocket(wsUrl());
      } catch (err: any) {
        console.warn('[WS] connection notice (falling back to interval polling):', err.message);
        setConnectionError(err.message);
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        if (disposed) return;
        const isReconnect = attempt > 0;
        attempt = 0;
        setIsConnected(true);
        setConnectionError(null);
        console.log(`Connected to order WebSocket hub for ${trackingId}`);
        // Keepalive so idle proxies don't drop the connection; the server
        // consumes (and ignores) these frames.
        pingTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send('ping');
        }, 30_000);
        if (isReconnect) {
          // Notify the view to refetch order/location data missed while down.
          onReconnectedRef.current?.(null);
        }
      };

      socket.onmessage = (message) => {
        try {
          handleEvent(JSON.parse(message.data) as OrderEvent);
        } catch (err) {
          console.error('Failed to parse order WebSocket message:', err);
        }
      };

      socket.onclose = () => {
        if (disposed) return;
        setIsConnected(false);
        scheduleReconnect();
      };

      socket.onerror = () => {
        // onclose follows and handles the retry
        socket?.close();
      };
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      clearTimers();
      const delay = Math.min(1_000 * 2 ** attempt, 15_000);
      attempt += 1;
      reconnectTimer = window.setTimeout(connect, delay);
    };

    connect();

    return () => {
      disposed = true;
      clearTimers();
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
    };
  }, [trackingId]);

  return { isConnected, connectionError };
}
