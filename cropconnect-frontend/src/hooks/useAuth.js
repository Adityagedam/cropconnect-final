// Owns authenticated dashboard API access and profile persistence helpers.
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { API, authHeaders, clearCsrfToken, clearSessionUser, csrfHeadersAsync } from "../lib/api";

/**
 * Provides auth-aware fetch helpers, profile state, logout, and profile save behavior.
 * @returns {object} Auth state and actions for dashboard screens.
 */
export function useAuth() {
  const navigate = useNavigate();

  const requireFreshLogin = useCallback(() => {
    clearCsrfToken();
    clearSessionUser();
    toast.error("Please log in again to continue.", { id: "auth-expired" });
    navigate("/login");
  }, [navigate]);

  const protectedFetch = useCallback(async (url, options = {}) => {
    const method = String(options.method || "GET").toUpperCase();
    const needsCsrf = !["GET", "HEAD", "OPTIONS"].includes(method);
    const csrf = needsCsrf ? await csrfHeadersAsync() : {};
    const requestOptions = {
      ...options,
      credentials: "include",
      headers: {
        ...authHeaders(),
        ...(options.headers || {}),
        ...csrf,
      },
    };
    let response = await fetch(url, requestOptions);

    if (needsCsrf && response.status === 403) {
      const forbiddenText = await response.clone().text().catch(() => "");
      if (!/csrf/i.test(forbiddenText)) return response;
      clearCsrfToken();
      const retryCsrf = await csrfHeadersAsync({ refresh: true });
      response = await fetch(url, {
        ...requestOptions,
        headers: {
          ...authHeaders(),
          ...(options.headers || {}),
          ...retryCsrf,
        },
      });
    }

    if (response.status === 401) {
      requireFreshLogin();
      throw new Error("Login expired");
    }

    return response;
  }, [requireFreshLogin]);

  const handleLogout = useCallback(async () => {
    try {
      await fetch(`${API}/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: {
          ...authHeaders(),
          ...(await csrfHeadersAsync()),
        },
      });
    } catch {
      // Local logout still clears client state if the network is unavailable.
    }
    clearCsrfToken();
    clearSessionUser();
    toast.success("Logged out successfully");
    navigate("/login");
  }, [navigate]);

  return {
    requireFreshLogin,
    protectedFetch,
    handleLogout,
  };
}
