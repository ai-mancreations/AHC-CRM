import axios from "axios";

// In local dev, "/api" goes through Vite's dev-server proxy (see vite.config.ts).
// In production on Render, VITE_API_BASE_URL is set at build time to the
// backend's full URL (e.g. https://ahc-crm.onrender.com/api) — this avoids
// relying on the static site's rewrite rules to proxy cross-origin requests,
// which Render's static hosting doesn't reliably support for external targets.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ahc_access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

function redirectToLogin() {
  localStorage.removeItem("ahc_access_token");
  localStorage.removeItem("ahc_refresh_token");
  // Never force-navigate if we're already on the login page — that's what
  // was causing the reload loop: a 401 on the login page itself (before
  // any token exists) kept re-triggering a hard redirect back to /login.
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem("ahc_refresh_token");
      if (refreshToken && !error.config._retry) {
        error.config._retry = true;
        try {
          const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken });
          localStorage.setItem("ahc_access_token", data.access_token);
          localStorage.setItem("ahc_refresh_token", data.refresh_token);
          error.config.headers.Authorization = `Bearer ${data.access_token}`;
          return api.request(error.config);
        } catch {
          redirectToLogin();
        }
      } else {
        redirectToLogin();
      }
    }
    return Promise.reject(error);
  }
);
