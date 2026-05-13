import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProtectedPage } from "./App";

describe("ProtectedPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("redirects to login when the session is denied", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/login" element={<div>Login screen</div>} />
          <Route path="/dashboard" element={<ProtectedPage><div>Private dashboard</div></ProtectedPage>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Checking session...")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Login screen")).toBeInTheDocument());
    expect(screen.queryByText("Private dashboard")).not.toBeInTheDocument();
  });

  it("renders children when the profile request succeeds", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<ProtectedPage><div>Private dashboard</div></ProtectedPage>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Private dashboard")).toBeInTheDocument());
  });
});
