import { useEffect, useState, useRef } from 'react';
import { WebPubSubClient } from '@azure/web-pubsub-client';
import { HubConnection, HubConnectionBuilder } from '@microsoft/signalr';
import type { TelemetryDocument } from '../types';
import api from '../utils/api';

interface NegotiateResponse {
  provider: 'signalr' | 'webpubsub';
  url: string;
}

export function useWebPubSub() {
  const [latestData, setLatestData] = useState<TelemetryDocument | null>(null);
  const [latestEvent, setLatestEvent] = useState<TelemetryDocument | null>(null);
  const [events, setEvents] = useState<TelemetryDocument[]>([]);
  const [isSubscribed, setIsSubscribed] = useState(false);

  const wpsClientRef = useRef<WebPubSubClient | null>(null);
  const srConnectionRef = useRef<HubConnection | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function initConnection() {
      try {
        // 1. Fetch access token from backend using axios client
        const res = await api.get<NegotiateResponse>('/api/pubsub/negotiate');
        const { provider, url } = res.data;
        console.log(`WebSocket Provider: ${provider}`);

        const handleNewMessage = (doc: TelemetryDocument) => {
          if (!isMounted) return;
          setLatestData(doc);

          if (doc.eventTriggered) {
            setLatestEvent(doc);
            setEvents(prev => [doc, ...prev].slice(0, 50));
          } else {
            // Even if routine poll, add to history just to show activity
            setEvents(prev => [doc, ...prev].slice(0, 50));
          }
        };

        if (provider === 'signalr') {
          // Parse connection URL and extract access token
          const urlObj = new URL(url);
          const token = urlObj.searchParams.get("access_token") || "";
          urlObj.searchParams.delete("access_token");

          // Rebuild URL with current hostname in case of localhost/127.0.0.1 replacement
          let serviceUrl = urlObj.toString();
          serviceUrl = serviceUrl.replace('localhost', window.location.hostname).replace('127.0.0.1', window.location.hostname);

          // 2. Init SignalR client with standard negotiation using accessTokenFactory
          const connection = new HubConnectionBuilder()
            .withUrl(serviceUrl, {
              accessTokenFactory: () => Promise.resolve(token)
            })
            .withAutomaticReconnect()
            .build();

          srConnectionRef.current = connection;

          connection.on("SendMessage", (doc: TelemetryDocument) => {
            handleNewMessage(doc);
          });

          await connection.start();
          if (isMounted) setIsSubscribed(true);
          console.log("Connected to Azure SignalR Service/Emulator");
        } else {
          // 2. Init Web PubSub client
          const client = new WebPubSubClient(url);
          wpsClientRef.current = client;

          client.on("group-message", (e) => {
            const doc: TelemetryDocument = e.message.data as any;
            handleNewMessage(doc);
          });

          await client.start();
          await client.joinGroup("telemetry");

          if (isMounted) setIsSubscribed(true);
          console.log("Connected to Azure Web PubSub Service");
        }

      } catch (err) {
        console.error("Websocket Connection Error:", err);
      }
    }

    initConnection();

    return () => {
      isMounted = false;
      if (wpsClientRef.current) {
        wpsClientRef.current.stop();
      }
      if (srConnectionRef.current) {
        srConnectionRef.current.stop();
      }
    };
  }, []);

  return { latestData, latestEvent, events, isSubscribed, setEvents, setLatestData };
}
