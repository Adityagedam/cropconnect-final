import "@/App.css";
import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import SignInPage from "./pages/SignInPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import Dashboard from "./pages/Dashboard";
import CropPlanner from "./pages/CropPlanner";
import LegalPage from "./pages/LegalPage";
import { API } from "./lib/api";

import { LandingLanguageProvider } from "./components/landing/LandingLanguageContext";

export function ProtectedPage({ children }) {
  const location = useLocation();
  const [authState, setAuthState] = useState("checking");

  useEffect(() => {
    let cancelled = false;

    fetch(`${API}/auth/profile`, { credentials: "include" })
      .then((response) => {
        if (!cancelled) setAuthState(response.ok ? "allowed" : "denied");
      })
      .catch(() => {
        if (!cancelled) setAuthState("denied");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (authState === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F7F3EA] px-4 text-sm font-semibold text-[#31572C]">
        Checking session...
      </div>
    );
  }

  if (authState === "denied") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}

function App() {
  return (
    <div className="App grain" data-auto-translate-root="true">
      <LandingLanguageProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signin" element={<SignInPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/terms" element={<LegalPage type="terms" />} />
            <Route path="/privacy" element={<LegalPage type="privacy" />} />
            <Route path="/dashboard" element={<ProtectedPage><Dashboard /></ProtectedPage>} />
            <Route path="/crop-planner" element={<ProtectedPage><CropPlanner /></ProtectedPage>} />
          </Routes>
        </BrowserRouter>
      </LandingLanguageProvider>
      <Toaster
        position="top-right"
        richColors
        closeButton
        toastOptions={{
          style: {
            background: "#FDFBF7",
            color: "#1A201C",
            border: "1px solid #D5D1C5",
            fontFamily: "DM Sans, sans-serif",
          },
        }}
      />
    </div>
  );
}

export default App;
