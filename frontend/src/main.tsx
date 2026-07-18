import { StrictMode, useState, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthProvider } from '@adolf94/ar-auth-client'
import { QueryProvider } from './providers/QueryProvider'
import './index.css'
import App from './App.tsx'

const appConfig = (window as any).APP_CONFIG || {};

function Main() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('theme') as 'light' | 'dark') || 'dark';
  });

  useEffect(() => {
    if (theme === 'light') {
      document.documentElement.classList.add('light');
    } else {
      document.documentElement.classList.remove('light');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const authConfig = {
    authority: appConfig.VITE_OIDC_AUTHORITY || import.meta.env.VITE_OIDC_AUTHORITY || 'https://auth.example.com',
    clientId: appConfig.VITE_OIDC_CLIENT_ID || import.meta.env.VITE_OIDC_CLIENT_ID || 'ar-bike-tracker-ui',
    audience: appConfig.VITE_OIDC_AUDIENCE || import.meta.env.VITE_OIDC_AUDIENCE || 'bike-tracker-api',
    redirectUri: appConfig.VITE_OIDC_REDIRECT_URI || import.meta.env.VITE_OIDC_REDIRECT_URI || window.location.origin + '/callback',
    scope: appConfig.VITE_OIDC_SCOPE || import.meta.env.VITE_OIDC_SCOPE || 'openid profile email offline_access api://bike-tracker-api/user',
    theme: theme
  };

  return (
    <AuthProvider config={authConfig}>
      <QueryProvider>
        <App theme={theme} setTheme={setTheme} />
      </QueryProvider>
    </AuthProvider>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Main />
  </StrictMode>,
)
