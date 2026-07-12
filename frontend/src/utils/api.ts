import axios from 'axios';

// Read API base path from window.APP_CONFIG (runtime config) first, then fallback to env
const envApiBase = (window as any).APP_CONFIG?.VITE_API_BASE || import.meta.env.VITE_API_BASE || `http://${window.location.hostname}:7071`;

// Dynamically handle localhost/127.0.0.1 replacement with the window host name
// in case the application is accessed from other devices in the local network.
export const backendBase = envApiBase
  .replace('localhost', window.location.hostname)
  .replace('127.0.0.1', window.location.hostname);

const api = axios.create({
  baseURL: backendBase,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
