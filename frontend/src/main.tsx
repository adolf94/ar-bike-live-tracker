import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthProvider } from '@adolf94/ar-auth-client'
import './index.css'
import App from './App.tsx'

const appConfig = (window as any).APP_CONFIG || {};

const authConfig = {
  authority: appConfig.VITE_OIDC_AUTHORITY || import.meta.env.VITE_OIDC_AUTHORITY || 'https://auth.example.com',
  clientId: appConfig.VITE_OIDC_CLIENT_ID || import.meta.env.VITE_OIDC_CLIENT_ID || 'ar-bike-tracker-ui',
  audience: appConfig.VITE_OIDC_AUDIENCE || import.meta.env.VITE_OIDC_AUDIENCE || 'bike-tracker-api',
  redirectUri: appConfig.VITE_OIDC_REDIRECT_URI || import.meta.env.VITE_OIDC_REDIRECT_URI || window.location.origin + '/callback',
  scope: appConfig.VITE_OIDC_SCOPE || import.meta.env.VITE_OIDC_SCOPE || 'openid profile email offline_access api://bike-tracker-api/user'
};

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider config={authConfig}>
      <App />
    </AuthProvider>
  </StrictMode>,
)
