import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { TelemetryDocument } from '../types';
import { backendBase } from '../utils/api';
import { telemetryQueryKeys } from './useTelemetryQueries';

/**
 * Native WebSocket subscription to the self-hosted hub (`/ws/telemetry`).
 *
 * Replaces the old Azure Web PubSub / SignalR negotiate flow. The server
 * pushes each persisted telemetry document as a plain JSON message
 * (`TelemetryDocument.to_cosmos_dict()` shape) to every client in the
 * "telemetry" group.
 *
 * The `getAccessToken` callback is no longer used for the socket itself
 * (the WS endpoint is unauthenticated) but is kept as a gate: pass it only
 * when the user is authenticated, matching the previous behavior.
 */
export function useWebPubSub(getAccessToken?: () => Promise<string | null>) {
  const [latestEvent, setLatestEvent] = useState<TelemetryDocument | null>(null);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!getAccessToken) return; // Do not connect if unauthenticated

    let disposed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let pingTimer: number | undefined;
    let attempt = 0;

    const wsUrl = () => `${backendBase.replace(/^http/, 'ws')}/ws/telemetry`;

    const handleNewMessage = (doc: TelemetryDocument) => {
      if (disposed) return;

      // Update current telemetry cache
      queryClient.setQueryData(telemetryQueryKeys.current(), doc);

      if (doc.eventTriggered) {
        // Set latest event for notification toast
        setLatestEvent(doc);

        // Update events list in cache
        queryClient.setQueryData<TelemetryDocument[]>(
          telemetryQueryKeys.events(),
          (oldEvents = []) => {
            // Add new event to the beginning, keep only last 50
            return [doc, ...oldEvents].slice(0, 50);
          }
        );
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
      } catch (err) {
        console.error('WebSocket URL error:', err);
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        if (disposed) return;
        attempt = 0;
        setIsSubscribed(true);
        console.log('Connected to telemetry WebSocket hub');
        // Keepalive so idle proxies don't drop the connection; the server
        // consumes (and ignores) these frames.
        pingTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send('ping');
        }, 30_000);
      };

      socket.onmessage = (event) => {
        try {
          handleNewMessage(JSON.parse(event.data) as TelemetryDocument);
        } catch (err) {
          console.error('Failed to parse telemetry WebSocket message:', err);
        }
      };

      socket.onclose = () => {
        if (disposed) return;
        setIsSubscribed(false);
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
  }, [getAccessToken, queryClient]);

  return { latestEvent, isSubscribed };
}
