const LOCAL_API_BASE_URL = "http://localhost:8001/api";

const getDefaultApiBaseUrl = () => {
  if (typeof window === "undefined") {
    return LOCAL_API_BASE_URL;
  }
  if (typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return LOCAL_API_BASE_URL;
  }
  return "";
};

export const API = (() => {
  const rawBaseUrl = import.meta.env.VITE_BACKEND_URL || getDefaultApiBaseUrl();
  if (!rawBaseUrl) {
    throw new Error("VITE_BACKEND_URL is required outside local development.");
  }
  const baseUrl = rawBaseUrl.trim().replace(/\/+$/, "");

  return baseUrl.endsWith("/api") ? baseUrl : `${baseUrl}/api`;
})();

export const getCookieValue = (name) => {
  if (typeof document === "undefined") return "";
  const cookie = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
};

export const csrfHeaders = () => {
  const csrfToken = sessionStorage.getItem("cropconnect-csrf-token") || getCookieValue("cropconnect_csrf");
  return csrfToken ? { "X-CSRF-Token": csrfToken } : {};
};

export const csrfHeadersAsync = async ({ refresh = false } = {}) => {
  const existingToken = sessionStorage.getItem("cropconnect-csrf-token") || getCookieValue("cropconnect_csrf");
  if (existingToken && !refresh) return { "X-CSRF-Token": existingToken };

  try {
    const response = await fetch(`${API}/auth/csrf`, { credentials: "include" });
    const payload = await response.json().catch(() => ({}));
    if (response.ok && payload.csrfToken) {
      storeCsrfToken(payload.csrfToken);
      return { "X-CSRF-Token": payload.csrfToken };
    }
  } catch {
    return {};
  }

  return {};
};

export const storeCsrfToken = (token) => {
  if (token) sessionStorage.setItem("cropconnect-csrf-token", token);
};

export const clearCsrfToken = () => {
  sessionStorage.removeItem("cropconnect-csrf-token");
};

export const AUTH_CACHE_KEY = "cc_auth_ok";
export const SESSION_USER_KEY = "cc_user";

export const storeSessionUser = (user) => {
  if (!user) return;
  sessionStorage.setItem(SESSION_USER_KEY, JSON.stringify(user));
  sessionStorage.setItem(AUTH_CACHE_KEY, JSON.stringify({ ok: true, ts: Date.now() }));
};

export const readSessionUser = () => {
  const raw = sessionStorage.getItem(SESSION_USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    sessionStorage.removeItem(SESSION_USER_KEY);
    return null;
  }
};

export const clearSessionUser = () => {
  sessionStorage.removeItem(SESSION_USER_KEY);
  sessionStorage.removeItem(AUTH_CACHE_KEY);
};
