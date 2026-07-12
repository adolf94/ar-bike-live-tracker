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

let authInterceptorId: number | null = null;

export const setupAxiosAuth = (getAccessToken: () => Promise<string | null>) => {
  if (authInterceptorId !== null) {
    api.interceptors.request.eject(authInterceptorId);
  }

  authInterceptorId = api.interceptors.request.use(async (config) => {
    try {
      const token = await getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (err) {
      console.warn('Failed to get access token for API request', err);
    }
    return config;
  });
};

export default api;
