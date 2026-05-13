import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearCsrfToken, csrfHeaders, csrfHeadersAsync, getCookieValue, storeCsrfToken } from "./api";

describe("api CSRF helpers", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.cookie = "cropconnect_csrf=; Max-Age=0; path=/";
    vi.restoreAllMocks();
  });

  it("reads cookie values safely", () => {
    document.cookie = "cropconnect_csrf=cookie-token";
    expect(getCookieValue("cropconnect_csrf")).toBe("cookie-token");
  });

  it("prefers stored CSRF tokens over cookies", () => {
    document.cookie = "cropconnect_csrf=cookie-token";
    storeCsrfToken("session-token");
    expect(csrfHeaders()).toEqual({ "X-CSRF-Token": "session-token" });
    clearCsrfToken();
    expect(csrfHeaders()).toEqual({ "X-CSRF-Token": "cookie-token" });
  });

  it("refreshes CSRF tokens from the backend when requested", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ csrfToken: "fresh-token" }),
      })
    );

    await expect(csrfHeadersAsync({ refresh: true })).resolves.toEqual({ "X-CSRF-Token": "fresh-token" });
    expect(sessionStorage.getItem("cropconnect-csrf-token")).toBe("fresh-token");
  });
});
