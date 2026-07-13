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

let requestInterceptorId: number | null = null;
let responseInterceptorId: number | null = null;

export const setupAxiosAuth = (
  getAccessToken: () => Promise<string | null>,
  login: () => void
) => {
  if (requestInterceptorId !== null) {
    api.interceptors.request.eject(requestInterceptorId);
  }
  if (responseInterceptorId !== null) {
    api.interceptors.response.eject(responseInterceptorId);
  }

  requestInterceptorId = api.interceptors.request.use(async (config) => {
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

  responseInterceptorId = api.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error.response && error.response.status === 401) {
        console.warn('Unauthorized API call (401), redirecting to login...');
        login();
      }
      return Promise.reject(error);
    }
  );
};

export default api;
