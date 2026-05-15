import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Leaf,
  LayoutDashboard,
  Radio,
  Droplets,
  CloudSun,
  BarChart3,
  Zap,
  Brain,
  Bell,
  Settings,
  LogOut,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Info,
  Sprout,
  MapPin,
  User,
  Languages,
  Sun,
  Moon,
  HelpCircle,
  Mail,
  Phone,
  MessageCircle,
  ChevronDown,
  CheckCircle2,
  Copy,
  Router,
  ShieldCheck,
  Wifi,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import LanguageSelect, { languages } from "../components/LanguageSelect";
import AiSection from "../components/dashboard/AiSection";
import MarketSection from "../components/dashboard/MarketSection";
import PumpSection from "../components/dashboard/PumpSection";
import SensorSection from "../components/dashboard/SensorSection";
import WeatherSection from "../components/dashboard/WeatherSection";
import { useLandingLanguage } from "../components/landing/LandingLanguageContext";
import DashboardPageContent from "../components/dashboard/DashboardPageContent";
import { toast } from "sonner";
import { API } from "../lib/api";
import { useAiChat } from "../hooks/useAiChat";
import { useAuth } from "../hooks/useAuth";
import { useMarketData } from "../hooks/useMarketData";
import { useProfile } from "../hooks/useProfile";
import { usePumpControl } from "../hooks/usePumpControl";
import { useSensorData } from "../hooks/useSensorData";
import { useSpeech } from "../hooks/useSpeech";
import { useWeatherData } from "../hooks/useWeatherData";

const humanizeApiValue = (value, fallback = "") => {
  if (value == null || value === "") return fallback;
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value
      .map((item) => humanizeApiValue(item))
      .filter(Boolean)
      .join("\n");
  }
  if (typeof value === "object") {
    if (typeof value.msg === "string") return value.msg;
    if (typeof value.message === "string") return value.message;
    if (typeof value.detail === "string") return value.detail;
    return JSON.stringify(value, null, 2);
  }
  return String(value);
};

const EMPTY_DISPLAY = "--";
const isPresent = (value) => value !== null && value !== undefined && value !== "";
const displayValue = (value, suffix = "") => (isPresent(value) ? `${value}${suffix}` : EMPTY_DISPLAY);
const numericOrNull = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};
const marketFriendlyError = (message) => {
  const text = humanizeApiValue(message, "");
  if (/DATA_GOV_API_KEY|market feed is not configured|live mandi price feed/i.test(text)) {
    return "Live market feed unavailable. Add the backend Data.gov API key to enable real mandi prices.";
  }
  return text || "Live market feed unavailable.";
};
const percentValue = (value, max = 100) => {
  const number = numericOrNull(value);
  if (number === null || !max) return 0;
  return Math.max(0, Math.min(100, (number / max) * 100));
};

// Color system
const lightColors = {
  greenDark: "#1e3a2f",
  greenMid: "#2d5a3d",
  greenAccent: "#3a6b4a",
  greenLight: "#4a8a5a",
  terracotta: "#c96a4a",
  terracottaLight: "#d4795c",
  cream: "#f0ece4",
  creamDark: "#e8e3d8",
  gold: "#c8a84b",
  goldLight: "#e8c86b",
  blue: "#3a7ab5",
  blueLight: "#5a9ad5",
  red: "#c94a3a",
  textDark: "#1a2820",
  textMid: "#4a5548",
  textLight: "#8a9488",
  bodyBg: "#f5f2ec",
};

const darkColors = {
  ...lightColors,
  greenDark: "#10261c",
  greenMid: "#1f4633",
  greenAccent: "#2f6a4d",
  cream: "#1c2921",
  creamDark: "#314238",
  textDark: "#f5f2ec",
  textMid: "#cbd6ce",
  textLight: "#91a195",
  bodyBg: "#0d1712",
};

const dashboardCopy = {
  en: {
    dashboard: "Dashboard",
    dashboardSubtitle: "Farm overview and insights",
    sensors: "Sensors",
    sensorsSubtitle: "Live sensor data and readings",
    pump: "Pump Control",
    pumpSubtitle: "Irrigation management",
    weather: "Weather",
    notifications: "Notifications",
    market: "Market Prices",
    cropPlanner: "Crop Planner",
    cropPlannerSubtitle: "Crop suggestions from live sensor readings",
    flow: "System Flow",
    ai: "AI Assistant",
    settings: "Settings",
    profile: "Profile",
    overview: "Overview",
    control: "Control",
    intelligence: "Intelligence",
    farmDashboard: "Farm Dashboard",
    status: "Status",
    running: "Running",
    stopped: "Stopped",
    runtime: "Runtime",
    autoMode: "Auto Mode Active",
    scheduledTimers: "Scheduled Timers",
    addTimer: "+ Add Timer",
    noTimers: "No timers scheduled",
    scheduleTimer: "Schedule Timer",
    startTime: "Start Time",
    duration: "Duration (minutes)",
    days: "Days (leave empty for daily)",
    cancel: "Cancel",
    saveTimer: "Save Timer",
    language: "Language",
    appearance: "Appearance",
    lightMode: "Light Mode",
    darkMode: "Dark Mode",
    live: "Live",
  },
};

const chatCopy = {
  en: {
    chatSuggestionIrrigate: "When should I irrigate?",
    chatSuggestionFertilizer: "Fertilizer recommendations for wheat",
    chatSuggestionSellOnions: "Should I sell onions now?",
    chatSuggestionPhZoneB: "pH level in Zone B",
    chatSuggestionWeather: "7-day weather prediction",
    chatPlaceholder: "Ask about your farm...",
  },
};

const ALERT_TOAST_INTERVAL_MS = 60000;
const SENSOR_POLL_INTERVAL_MS = 15000;
const SNAPSHOT_SAVE_INTERVAL_MS = 5 * 60 * 1000;
const buildSensorAlerts = (data = {}, connection = {}) => {
  if (connection.source !== "esp32") return [];
  const alerts = [];
  const addAlert = (id, title, body) => alerts.push({ id, title, body });

  if (isPresent(data.soilMoisture) && data.soilMoisture < 25) {
    addAlert("soil-moisture-low", "Soil moisture is low", `Latest SIM800L reading is ${data.soilMoisture}%. Check irrigation.`);
  }
  if (isPresent(data.soilMoisture) && data.soilMoisture > 85) {
    addAlert("soil-moisture-high", "Soil moisture is very high", `Latest SIM800L reading is ${data.soilMoisture}%. Check drainage and pump state.`);
  }
  if (isPresent(data.temperature) && data.temperature > 40) {
    addAlert("temperature-high", "Temperature is high", `Latest SIM800L reading is ${data.temperature}\u00b0C. Avoid spraying and check crop stress.`);
  }
  if (isPresent(data.soilPh) && (data.soilPh < 5.5 || data.soilPh > 8.5)) {
    addAlert("ph-out-of-range", "Soil pH needs attention", `Latest SIM800L pH reading is ${data.soilPh}. Confirm with a soil test before treatment.`);
  }
  return alerts;
};
// Market data must come from the backend/API. No client-side demo prices.
const emptyMarketData = {
  prices: [],
  mandis: [],
  source: "",
  sourceUrl: "",
  requestedLocation: "",
  requestedState: "",
  matchedDistrict: "",
  recordsCount: 0,
  updatedAt: "",
  message: "",
};

export default function Dashboard() {
  const { language: appLanguage, setLanguage: setAppLanguage } = useLandingLanguage();
  const [language, setLanguage] = useState(
    () => localStorage.getItem("cropconnect-language") || "en"
  );
  const [theme, setTheme] = useState(
    () => localStorage.getItem("cropconnect-theme") || "light"
  );
  const [activePage, setActivePage] = useState("dashboard");
  const speechSentRef = useRef(false);
  const logContainerRef = useRef(null);
  const chatContainerRef = useRef(null);
  const handleSendMessageRef = useRef(null);
  const activeSensorAlertsRef = useRef([]);
  const alertToastIntervalRef = useRef(null);
  const persistedFarmLoadedRef = useRef(false);
  const snapshotSaveInFlightRef = useRef(false);
  const sensorApiKeyAutoLoadRef = useRef("");
  const isDark = theme === "dark";
  const colors = isDark ? darkColors : lightColors;
  const copy = dashboardCopy.en;
  const t = (key) => copy[key] || dashboardCopy.en[key] || key;
  const chatText = chatCopy.en;
  const ct = (key) => chatText[key] || chatCopy.en[key] || key;
  const { protectedFetch, handleLogout } = useAuth();

  useEffect(() => {
    if (appLanguage && appLanguage !== language) setLanguage(appLanguage);
  }, [appLanguage, language]);

  const handleLanguageChange = useCallback((nextLanguage) => {
    setLanguage(nextLanguage);
    setAppLanguage(nextLanguage);
  }, [setAppLanguage]);

  const {
    userData,
    setUserData,
    isEditingProfile,
    setIsEditingProfile,
    editData,
    setEditData,
    userLoaded,
    sensorSetupForm,
    setSensorSetupForm,
    setupChecking,
    setSetupChecking,
    setupCheckResult,
    setSetupCheckResult,
    sensorApiKey,
    setSensorApiKey,
    sensorApiKeyLoading,
    setSensorApiKeyLoading,
    sensorApiKeyError,
    setSensorApiKeyError,
    saveUserToMysql,
  } = useProfile(protectedFetch);

  const {
    sensorData,
    sensorConnection,
    setSensorConnection,
    telemetryPacket,
    apiLogs,
    applyBackendReadings,
  } = useSensorData({
    protectedFetch,
    sensorDeviceId: userData.sensorDeviceId,
    pollIntervalMs: SENSOR_POLL_INTERVAL_MS,
  });

  const activeSensorAlerts = useMemo(
    () => buildSensorAlerts(sensorData, sensorConnection),
    [sensorData, sensorConnection]
  );

  const cropZones = useMemo(
    () => [
      { id: "zoneA", name: "Zone A", crop: userData.zoneA, area: "" },
      { id: "zoneB", name: "Zone B", crop: userData.zoneB, area: "" },
      { id: "zoneC", name: "Zone C", crop: userData.zoneC, area: "" },
    ],
    [userData.zoneA, userData.zoneB, userData.zoneC]
  );

  const loadSensorApiKey = useCallback(async ({ rotate = false } = {}) => {
    if (!userData.sensorDeviceId) {
      setSensorApiKey("");
      setSensorApiKeyError("No sensor device is configured");
      return "";
    }

    setSensorApiKeyLoading(true);
    setSensorApiKeyError("");
    try {
      let response = await protectedFetch(`${API}/esp32/device-key${rotate ? "/rotate" : ""}`, { method: rotate ? "POST" : "GET" });
      let payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(humanizeApiValue(payload.detail, `Device key returned ${response.status}`));

      if (!rotate && !payload.has_active_key) {
        response = await protectedFetch(`${API}/esp32/device-key`, { method: "POST" });
        payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(humanizeApiValue(payload.detail, `Device key returned ${response.status}`));
      } else if (!rotate && payload.has_active_key && !payload.api_key) {
        setSensorApiKey("");
        setSensorApiKeyError("Active device key is hidden after creation. Rotate only when you are ready to update the ESP32 firmware.");
        return "";
      }

      const nextKey = payload.api_key || "";
      setSensorApiKey(nextKey);
      if (rotate && nextKey) {
        setSensorApiKeyError("New device key created. Flash this key to the ESP32 before it sends the next packet.");
      }
      return nextKey;
    } catch (error) {
      setSensorApiKey("");
      setSensorApiKeyError(error.message || "Could not load ESP32 device key");
      return "";
    } finally {
      setSensorApiKeyLoading(false);
    }
  }, [protectedFetch, userData.sensorDeviceId]);

  const {
    pumps,
    setPumps,
    pumpsRef,
    pumpUpdating,
    pumpControlMode,
    setPumpControlMode,
    pumpDirectHost,
    setPumpDirectHost,
    scheduledTimers,
    setScheduledTimers,
    showTimerModal,
    setShowTimerModal,
    newTimer,
    setNewTimer,
    saveTimersToMysql,
    togglePump,
  } = usePumpControl({
    protectedFetch,
    userLoaded,
    sensorConnection,
    sensorDeviceId: userData.sensorDeviceId,
    pollIntervalMs: SENSOR_POLL_INTERVAL_MS,
  });

  const ownerPayload = useCallback(() => ({
    user_id: userData.id || undefined,
    email: userData.email || undefined,
  }), [userData.email, userData.id]);

  const getUserMarketLocation = useCallback(() => {
    const place =
      userData.locationType === "village"
        ? userData.village || userData.city
      : userData.city || userData.village;
    return [place, userData.district, userData.state].filter(Boolean).join(", ");
  }, [userData.city, userData.district, userData.locationType, userData.state, userData.village]);

  const { weatherData, setWeatherData, weatherError, getUserWeatherLocation } = useWeatherData(userData);
  const {
    marketData,
    setMarketData,
    marketError,
    marketLoading,
    marketInsight,
    marketInsightError,
    marketInsightLoading,
    loadMarketPrices,
    loadMarketInsight,
  } = useMarketData({
    protectedFetch,
    language,
    userLoaded,
    userState: userData.state,
    getUserMarketLocation,
    marketFriendlyError,
    emptyMarketData,
  });

  // Language detection function
  const detectLanguage = useCallback((text) => {
    if (!text || text.trim().length === 0) return language;

    if (/[\u0900-\u097F]/.test(text)) return 'hi';
    if (/[\u0C00-\u0C7F]/.test(text)) return 'te';
    if (/[\u0B80-\u0BFF]/.test(text)) return 'ta';
    if (/[\u0C80-\u0CFF]/.test(text)) return 'kn';
    if (/[\u0980-\u09FF]/.test(text)) return 'bn';
    return 'en';
  }, [language]);

  const {
    chatMessages,
    setChatMessages,
    chatInput,
    setChatInput,
    isTyping,
    showSuggestions,
    handleSendMessage,
    handleSuggestionClick,
  } = useAiChat({
    protectedFetch,
    language,
    sensorConnection,
    sensorDeviceId: userData.sensorDeviceId,
    humanizeApiValue,
    detectLanguage,
  });

  const onSpeechTranscript = useCallback((transcript, detectedLang) => {
    if (speechSentRef.current) return;
    setChatInput(transcript);

    const detectedLangName = languages.find((item) => item.code === detectedLang)?.name || detectedLang;
    const selectedLangName = languages.find((item) => item.code === language)?.name || language;
    if (detectedLang !== language) {
      toast.info(`Detected ${detectedLangName}; answering in ${selectedLangName}.`);
    } else {
      toast.success(`${detectedLangName} detected! Sending response in ${selectedLangName}...`);
    }

    speechSentRef.current = true;
    setTimeout(() => handleSendMessageRef.current?.(transcript, null, detectedLang), 500);
  }, [language, setChatInput]);

  const { isListening, startListening: startSpeechListening, stopListening } = useSpeech({
    language,
    languages,
    onTranscript: onSpeechTranscript,
    detectLanguage,
  });

  const startListening = useCallback(() => {
    speechSentRef.current = false;
    startSpeechListening();
  }, [startSpeechListening]);

  const saveDashboardSnapshot = useCallback(async () => {
    if (snapshotSaveInFlightRef.current) return;
    snapshotSaveInFlightRef.current = true;
    try {
      const response = await protectedFetch(`${API}/farm/snapshot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...ownerPayload(),
          device_id: sensorConnection.deviceId || userData.sensorDeviceId || "",
          source: sensorConnection.source,
          sensor_data: sensorConnection.source === "esp32" ? sensorData : {},
          pump_data: pumps,
          timers: scheduledTimers,
          weather_data: weatherData,
          market_data: marketData,
          telemetry_packet: telemetryPacket,
        }),
      });
      if (!response.ok) throw new Error("Could not save dashboard snapshot");
    } finally {
      snapshotSaveInFlightRef.current = false;
    }
  }, [marketData, ownerPayload, protectedFetch, pumps, scheduledTimers, sensorConnection.deviceId, sensorConnection.source, sensorData, telemetryPacket, userData.sensorDeviceId, weatherData]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem("cropconnect-theme", theme);
  }, [isDark, theme]);

  useEffect(() => {
    activeSensorAlertsRef.current = activeSensorAlerts;
  }, [activeSensorAlerts]);

  useEffect(() => {
    const sendAlertToasts = () => {
      const alerts = activeSensorAlertsRef.current;
      if (!alerts.length) return;

      alerts.slice(0, 3).forEach((alert) => {
        toast.warning(alert.title, {
          description: alert.body,
          id: `${alert.id}-${Math.floor(Date.now() / ALERT_TOAST_INTERVAL_MS)}`,
          duration: 8000,
        });
      });
    };

    alertToastIntervalRef.current = window.setInterval(sendAlertToasts, ALERT_TOAST_INTERVAL_MS);

    return () => {
      if (alertToastIntervalRef.current) {
        window.clearInterval(alertToastIntervalRef.current);
        alertToastIntervalRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!userLoaded || userData.sensorSetupComplete || !userData.sensorDeviceId || sensorApiKey || sensorApiKeyLoading) return;
    if (sensorApiKeyAutoLoadRef.current === userData.sensorDeviceId) return;
    sensorApiKeyAutoLoadRef.current = userData.sensorDeviceId;
    loadSensorApiKey();
  }, [
    loadSensorApiKey,
    sensorApiKey,
    sensorApiKeyLoading,
    userData.sensorDeviceId,
    userData.sensorSetupComplete,
    userLoaded,
  ]);

  // Load saved dashboard data from MySQL.
  useEffect(() => {
    if (!userLoaded || persistedFarmLoadedRef.current) return;

    let cancelled = false;
    const loadPersistedFarmData = async () => {
      try {
        const [pumpResponse, timersResponse, chatResponse, snapshotResponse] = await Promise.all([
          protectedFetch(`${API}/farm/pump-states`),
          protectedFetch(`${API}/farm/timers`),
          protectedFetch(`${API}/farm/chat-history?limit=50`),
          protectedFetch(`${API}/farm/snapshot/latest`),
        ]);

        if (!pumpResponse.ok || !timersResponse.ok || !chatResponse.ok || !snapshotResponse.ok) {
          throw new Error("Could not load saved MySQL farm data");
        }

        const [pumpPayload, timersPayload, chatPayload, snapshotPayload] = await Promise.all([
          pumpResponse.json().catch(() => ({})),
          timersResponse.json().catch(() => ({})),
          chatResponse.json().catch(() => ({})),
          snapshotResponse.json().catch(() => ({})),
        ]);
        if (cancelled) return;

        const snapshot = snapshotPayload.snapshot;
        if (snapshot?.weather_data) setWeatherData(snapshot.weather_data);
        if (snapshot?.market_data) {
          setMarketData({
            ...emptyMarketData,
            ...snapshot.market_data,
            prices: Array.isArray(snapshot.market_data.prices) ? snapshot.market_data.prices : [],
            mandis: Array.isArray(snapshot.market_data.mandis) ? snapshot.market_data.mandis : [],
          });
        }

        if (Array.isArray(pumpPayload.items) && pumpPayload.items.length) {
          setPumps((prev) => {
            const next = { ...prev };
            pumpPayload.items.forEach((item) => {
              if (!next[item.pump_id]) return;
              const desiredOn = Boolean(item.desired_on ?? item.on);
              const appliedOn = item.applied_on === null || item.applied_on === undefined ? null : Boolean(item.applied_on);
              next[item.pump_id] = {
                ...next[item.pump_id],
                on: desiredOn,
                appliedOn,
                hardwareConfirmed: Boolean(item.hardware_confirmed),
                runtime: item.runtime || 0,
                schedule: Object.keys(item.schedule || {}).length ? item.schedule : next[item.pump_id].schedule,
              };
            });
            return next;
          });
        } else if (snapshot?.pump_data && Object.keys(snapshot.pump_data).length) {
          setPumps((prev) => ({ ...prev, ...snapshot.pump_data }));
        }

        if (timersPayload.timers && Object.keys(timersPayload.timers).length) {
          setScheduledTimers((prev) => ({ ...prev, ...timersPayload.timers }));
        } else if (snapshot?.timers && Object.keys(snapshot.timers).length) {
          setScheduledTimers((prev) => ({ ...prev, ...snapshot.timers }));
        }

        if (Array.isArray(chatPayload.items) && chatPayload.items.length) {
          setChatMessages(chatPayload.items);
        }

        persistedFarmLoadedRef.current = true;
      } catch (error) {
        persistedFarmLoadedRef.current = true;
        if (error.message !== "Login required" && error.message !== "Login expired") {
          toast.error(error.message || "Could not load saved MySQL farm data");
        }
      }
    };

    loadPersistedFarmData();
    return () => {
      cancelled = true;
    };
  }, [protectedFetch, userLoaded]);

  // Page configurations
  const pageConfig = {
    dashboard: { title: t("dashboard"), subtitle: t("dashboardSubtitle") },
    sensors: { title: t("sensors"), subtitle: t("sensorsSubtitle") },
    pump: { title: t("pump"), subtitle: t("pumpSubtitle") },
    weather: { title: `${t("weather")} - ${userData.locationType === "city" ? userData.city : userData.village}`, subtitle: `${userData.state} forecast and conditions` },
    notifications: { title: t("notifications"), subtitle: "Alerts, reminders and farm updates" },
    market: { title: t("market"), subtitle: `${getUserMarketLocation() || EMPTY_DISPLAY} mandi prices` },
    cropPlanner: { title: t("cropPlanner"), subtitle: t("cropPlannerSubtitle") },
    flow: { title: t("flow"), subtitle: "Data pipeline visualization" },
    ai: { title: t("ai"), subtitle: "Smart farming recommendations" },
    settings: { title: t("settings"), subtitle: "App preferences and contact" },
    profile: { title: t("profile"), subtitle: "Your farm information" },
  };

  // Persist the current dashboard state periodically so refreshes restore from MySQL.
  useEffect(() => {
    if (!userLoaded || !persistedFarmLoadedRef.current) return undefined;
    const interval = setInterval(() => {
      saveDashboardSnapshot().catch(() => {});
    }, SNAPSHOT_SAVE_INTERVAL_MS);
    saveDashboardSnapshot().catch(() => {});
    return () => clearInterval(interval);
  }, [saveDashboardSnapshot, userLoaded]);

  // Load live mandi prices for the user's saved profile location.
  useEffect(() => {
    if (!userLoaded) return undefined;
    let cancelled = false;
    const isCancelled = () => cancelled;

    loadMarketPrices(isCancelled);
    const interval = setInterval(() => loadMarketPrices(isCancelled), 30 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [loadMarketPrices, userLoaded]);

  // Initialize chat with welcome message
  useEffect(() => {
    if (chatMessages.length === 0) {
      const firstName = userData.name.split(" ")[0] || "there";
      const welcomeText = sensorConnection.source === "esp32"
        ? `Welcome back, ${firstName}. Live ESP32 readings: soil moisture ${displayValue(sensorData.soilMoisture, "%")}, temperature ${displayValue(sensorData.temperature, "\u00b0C")}, humidity ${displayValue(sensorData.humidity, "%")}. How can I help?`
        : `Welcome back, ${firstName}. No ESP32 readings are available yet, so missing values are shown as ${EMPTY_DISPLAY}. How can I help?`;
      setChatMessages([
        {
          id: 1,
          type: "bot",
          text: welcomeText,
        },
      ]);
    }
  }, [chatMessages.length, userData.name, sensorConnection.source, sensorData.soilMoisture, sensorData.temperature, sensorData.humidity]);

  // Auto-scroll API log
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [apiLogs]);

  // Track pump runtime while pumps are running.
  useEffect(() => {
    const interval = setInterval(() => {
      setPumps((prev) =>
        Object.fromEntries(
          Object.entries(prev).map(([pumpId, pump]) => [
            pumpId,
            pump.on ? { ...pump, runtime: pump.runtime + 1 } : pump,
          ])
        )
      );
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  const sensorIngestUrl = `${API.replace(/\/api$/, "")}/api/telemetry/ingest`;
  const sensorDeviceId = sensorSetupForm.deviceId.trim() || userData.sensorDeviceId || "";

  const copyToClipboard = async (text, label = "Copied") => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(label);
    } catch {
      toast.error("Could not copy to clipboard");
    }
  };

  const saveSensorSetup = async (status = "ready") => {
    const updatedUser = {
      ...userData,
      sensorDeviceId,
      sensors: sensorSetupForm.nodeCount || "1",
      sensorSetupComplete: true,
      sensorSetupStatus: status,
      sensorSetupCompletedAt: new Date().toISOString(),
    };
    setUserData(updatedUser);
    setSensorConnection((prev) => ({
      ...prev,
      deviceId: sensorDeviceId,
      source: status === "connected" ? "esp32" : "unavailable",
      error: status === "connected" ? null : "Waiting for first ESP32 reading",
    }));

    try {
      const mysqlUser = await saveUserToMysql({
        sensor_device_id: sensorDeviceId,
        sensors: sensorSetupForm.nodeCount || "1",
        sensor_setup_complete: true,
        sensor_setup_status: status,
      });
      if (mysqlUser) {
        const mergedUser = { ...updatedUser, ...mysqlUser };
        setUserData(mergedUser);
      }
      toast.success(status === "connected" ? "Sensor node connected" : "Sensor setup saved in MySQL");
    } catch (error) {
      toast.error(error.message || "Saved locally, but MySQL update failed");
    }
  };

  const testSensorConnection = async () => {
    setSetupChecking(true);
    setSetupCheckResult(null);
    try {
      const response = await protectedFetch(`${API}/sensors/latest?device_id=${encodeURIComponent(sensorDeviceId)}`);
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);
      const payload = await response.json();
      const hasReadings = applyBackendReadings(payload);
      if (hasReadings) {
        setSetupCheckResult({ type: "success", text: "Live sensor readings found for this device ID." });
        await saveSensorSetup("connected");
      } else {
        setSetupCheckResult({
          type: "waiting",
          text: "Backend is reachable, but this device has not sent readings yet. Flash the ESP32 code with this device ID, then test again.",
        });
      }
    } catch (error) {
      setSetupCheckResult({
        type: "error",
        text: `Could not reach the sensor API: ${error.message}`,
      });
    } finally {
      setSetupChecking(false);
    }
  };
  const getTimerStartTime = (timerInput) => {
    if (!timerInput.hour || !timerInput.minute || !timerInput.period) return "";
    const hour12 = Number(timerInput.hour);
    const minute = Number(timerInput.minute);
    if (!hour12 || Number.isNaN(minute)) return "";

    const hour24 = timerInput.period === "PM"
      ? (hour12 === 12 ? 12 : hour12 + 12)
      : (hour12 === 12 ? 0 : hour12);

    return `${String(hour24).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  };

  const formatTimerStartTime = (startTime) => {
    const [hourText, minuteText] = startTime.split(":");
    const hour24 = Number(hourText);
    if (Number.isNaN(hour24)) return startTime;
    const period = hour24 >= 12 ? "PM" : "AM";
    const hour12 = hour24 % 12 || 12;
    return `${hour12}:${minuteText} ${period}`;
  };

  const resetTimerForm = () => {
    setNewTimer({ hour: "", minute: "00", period: "AM", duration: "", days: [] });
  };

  const getDefaultTimerForm = () => {
    const now = new Date();
    const roundedMinutes = Math.ceil(now.getMinutes() / 5) * 5;
    const defaultDate = new Date(now);
    defaultDate.setMinutes(roundedMinutes === 60 ? 0 : roundedMinutes, 0, 0);
    if (roundedMinutes === 60) defaultDate.setHours(defaultDate.getHours() + 1);
    const hour24 = defaultDate.getHours();
    return {
      hour: String(hour24 % 12 || 12),
      minute: String(defaultDate.getMinutes()).padStart(2, "0"),
      period: hour24 >= 12 ? "PM" : "AM",
      duration: "",
      days: [],
    };
  };

  const openTimerModal = (pumpId) => {
    setNewTimer(getDefaultTimerForm());
    setShowTimerModal({ show: true, pump: pumpId });
  };

  const closeTimerModal = () => {
    setShowTimerModal({ show: false, pump: null });
    resetTimerForm();
  };

  const handleAddTimer = () => {
    const startTime = getTimerStartTime(newTimer);
    const duration = Number(newTimer.duration);

    if (!showTimerModal.pump || !startTime || !duration) {
      toast.error("Please fill in all fields");
      return;
    }

    if (duration < 1 || duration > 480) {
      toast.error("Timer duration must be between 1 and 480 minutes");
      return;
    }

    const timer = {
      id: Date.now(),
      startTime,
      duration,
      days: newTimer.days.length > 0 ? newTimer.days : [0, 1, 2, 3, 4, 5, 6],
    };
    const nextTimers = {
      ...scheduledTimers,
      [showTimerModal.pump]: [
        ...scheduledTimers[showTimerModal.pump],
        timer,
      ],
    };
    setScheduledTimers(nextTimers);
    saveTimersToMysql(nextTimers).catch(() => {});

    closeTimerModal();
    toast.success("Timer scheduled successfully!");
  };

  const removeTimer = (pumpId, timerId) => {
    const nextTimers = {
      ...scheduledTimers,
      [pumpId]: scheduledTimers[pumpId].filter((t) => t.id !== timerId),
    };
    setScheduledTimers(nextTimers);
    saveTimersToMysql(nextTimers).catch(() => {});
    toast.success("Timer removed");
  };

  const formatTime = (minutes) => {
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hrs}h ${mins}m`;
  };

  const navItems = [
    { id: "dashboard", icon: LayoutDashboard, label: t("dashboard") },
    { id: "sensors", icon: Radio, label: t("sensors"), badge: t("live") },
    { id: "pump", icon: Droplets, label: t("pump") },
    { id: "weather", icon: CloudSun, label: t("weather") },
    { id: "notifications", icon: Bell, label: t("notifications"), badge: activeSensorAlerts.length ? String(activeSensorAlerts.length) : null },
    { id: "market", icon: BarChart3, label: t("market") },
    { id: "cropPlanner", icon: Sprout, label: t("cropPlanner") },
    { id: "flow", icon: Zap, label: t("flow") },
    { id: "ai", icon: Brain, label: t("ai"), badge: "New" },
    { id: "settings", icon: Settings, label: t("settings") },
    { id: "profile", icon: User, label: t("profile") },
  ];

  const suggestionChips = [
    "chatSuggestionIrrigate",
    "chatSuggestionFertilizer",
    "chatSuggestionSellOnions",
    "chatSuggestionPhZoneB",
    "chatSuggestionWeather",
  ];

  const dashboardPageContext = {
    EMPTY_DISPLAY,
    activePage,
    activeSensorAlerts,
    apiLogs,
    chatContainerRef,
    chatInput,
    chatMessages,
    closeTimerModal,
    colors,
    copyToClipboard,
    cropZones,
    ct,
    displayValue,
    editData,
    formatTime,
    formatTimerStartTime,
    getUserMarketLocation,
    handleAddTimer,
    handleSendMessage,
    handleSuggestionClick,
    isDark,
    isEditingProfile,
    isListening,
    isPresent,
    isTyping,
    language,
    loadMarketInsight,
    loadMarketPrices,
    loadSensorApiKey,
    logContainerRef,
    marketData,
    marketError,
    marketInsight,
    marketInsightError,
    marketInsightLoading,
    marketLoading,
    newTimer,
    numericOrNull,
    openTimerModal,
    percentValue,
    protectedFetch,
    pumps,
    pumpControlMode,
    pumpDirectHost,
    pumpUpdating,
    removeTimer,
    saveSensorSetup,
    saveUserToMysql,
    scheduledTimers,
    sensorApiKey,
    sensorApiKeyError,
    sensorApiKeyLoading,
    sensorConnection,
    sensorData,
    sensorDeviceId,
    sensorIngestUrl,
    sensorSetupForm,
    setChatInput,
    setEditData,
    setIsEditingProfile,
    setLanguage: handleLanguageChange,
    setNewTimer,
    setPumpControlMode,
    setPumpDirectHost,
    setSensorSetupForm,
    setTheme,
    setUserData,
    setupCheckResult,
    setupChecking,
    showSuggestions,
    showTimerModal,
    startListening,
    stopListening,
    suggestionChips,
    t,
    telemetryPacket,
    testSensorConnection,
    theme,
    togglePump,
    userData,
    weatherData,
    weatherError,
  };

  const renderPage = () => <DashboardPageContent ctx={dashboardPageContext} />;

  // Get user initials
  const getInitials = (name) => {
    return name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2);
  };

  useEffect(() => {
    handleSendMessageRef.current = handleSendMessage;
  });
  const selectedNavItem = navItems.find((item) => item.id === activePage) || navItems[0];
  const SensorSetupWindow = () => {
    const examplePayload = JSON.stringify(
      {
        device_id: sensorDeviceId || "",
        soil_moisture: null,
        humidity: null,
        temperature: null,
        ph: null,
        nitrogen: null,
        phosphorus: null,
        potassium: null,
      },
      null,
      2
    );
    const curlExample = `curl -X POST ${sensorIngestUrl} \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${sensorApiKey || "<DEVICE_API_KEY>"}" \\
  -d '${examplePayload.replace(/\n/g, " ")}'`;

    return (
      <div className="fixed inset-0 z-[70] overflow-y-auto bg-[#0b1510]/70 backdrop-blur-sm">
        <div className="min-h-full px-3 py-5 sm:px-6 sm:py-8 flex items-start justify-center">
          <div className="w-full max-w-5xl rounded-xl bg-[#FDFBF7] border border-[#D5D1C5] shadow-2xl overflow-hidden">
            <div className="grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="p-5 sm:p-8" style={{ background: colors.greenDark }}>
                <div className="flex items-center gap-3">
                  <span className="w-11 h-11 rounded-lg flex items-center justify-center bg-white/10 text-white">
                    <Router className="w-5 h-5" />
                  </span>
                  <div>
                    <p className="text-xs uppercase font-semibold tracking-[0.16em]" style={{ color: colors.goldLight }}>First setup</p>
                    <h2 className="font-display text-2xl text-white">Connect your farm sensors</h2>
                  </div>
                </div>
                <p className="mt-5 text-sm leading-relaxed text-white/75">
                  CropConnect shows live ESP32 readings only. Add this device ID to your farm node and send telemetry to the API endpoint; until readings arrive, fields stay blank.
                </p>
                <div className="mt-7 space-y-3">
                  {[
                    { icon: Wifi, title: "Main ESP32 sends readings", text: "SIM800L posts soil moisture, temperature, humidity, pH and NPK values." },
                    { icon: ShieldCheck, title: "Device key protects SIM800L calls", text: "Telemetry and relay polling must include this farm device key." },
                    { icon: CheckCircle2, title: "Pump commands are queued", text: "The main ESP32 polls commands and forwards them to the pump ESP32." },
                  ].map((item) => (
                    <div key={item.title} className="flex gap-3 rounded-lg bg-white/8 p-3">
                      <item.icon className="w-5 h-5 flex-shrink-0" style={{ color: colors.goldLight }} />
                      <div>
                        <p className="text-sm font-semibold text-white">{item.title}</p>
                        <p className="text-xs text-white/65">{item.text}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="p-5 sm:p-8 space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs uppercase tracking-[0.16em]" style={{ color: colors.textLight }}>Device ID</Label>
                    <Input
                      value={sensorSetupForm.deviceId}
                      readOnly
                      placeholder="Generated by CropConnect"
                      className="mt-2 bg-white border-[#D5D1C5]"
                    />
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-[0.16em]" style={{ color: colors.textLight }}>Sensor nodes</Label>
                    <Input
                      type="number"
                      min="1"
                      value={sensorSetupForm.nodeCount}
                      onChange={(event) => setSensorSetupForm((prev) => ({ ...prev, nodeCount: event.target.value }))}
                      className="mt-2 bg-white border-[#D5D1C5]"
                    />
                  </div>
                </div>

                <div className="rounded-lg border border-[#D5D1C5] bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs uppercase tracking-[0.16em]" style={{ color: colors.textLight }}>Telemetry endpoint</p>
                      <p className="mt-1 font-mono text-sm truncate" style={{ color: colors.textDark }}>{sensorIngestUrl}</p>
                    </div>
                    <Button type="button" variant="outline" size="sm" onClick={() => copyToClipboard(sensorIngestUrl, "Endpoint copied")}>
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="rounded-lg border border-[#D5D1C5] bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs uppercase tracking-[0.16em]" style={{ color: colors.textLight }}>ESP32 device API key</p>
                      <p className="mt-1 font-mono text-xs break-all" style={{ color: colors.textDark }}>
                        {sensorApiKeyLoading ? "Loading..." : sensorApiKey || EMPTY_DISPLAY}
                      </p>
                      <p className="mt-2 text-xs" style={{ color: colors.textMid }}>Flash this key with this farm's device ID. It only works for this device and is not saved in browser storage.</p>
                      {sensorApiKeyError && <p className="mt-2 text-xs text-red-600">{sensorApiKeyError}</p>}
                    </div>
                    <Button type="button" variant="outline" size="sm" disabled={!sensorApiKey || sensorApiKeyLoading} onClick={() => copyToClipboard(sensorApiKey, "Device API key copied")}>
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button type="button" variant="outline" size="sm" disabled={sensorApiKeyLoading} onClick={() => loadSensorApiKey()}>
                      {sensorApiKeyLoading ? "Loading..." : "Load key"}
                    </Button>
                    <Button type="button" variant="outline" size="sm" disabled={sensorApiKeyLoading || !sensorDeviceId} onClick={() => loadSensorApiKey({ rotate: true })}>
                      Rotate key
                    </Button>
                  </div>
                </div>

                <div className="rounded-lg bg-[#101f17] p-4">
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <p className="text-xs uppercase tracking-[0.16em] text-white/60">Test request</p>
                    <Button type="button" size="sm" variant="outline" className="bg-white" onClick={() => copyToClipboard(curlExample, "Test request copied")}>
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                  <pre className="text-xs text-white/80 overflow-x-auto whitespace-pre-wrap">{curlExample}</pre>
                </div>

                {setupCheckResult && (
                  <div className={`rounded-lg border p-3 text-sm ${
                    setupCheckResult.type === "success"
                      ? "border-green-200 bg-green-50 text-green-800"
                      : setupCheckResult.type === "error"
                        ? "border-red-200 bg-red-50 text-red-800"
                        : "border-amber-200 bg-amber-50 text-amber-800"
                  }`}>
                    {setupCheckResult.text}
                  </div>
                )}

                <div className="flex flex-col sm:flex-row gap-3 pt-2">
                  <Button type="button" onClick={testSensorConnection} disabled={setupChecking || !sensorDeviceId} className="bg-[#1B4332] hover:bg-[#0F2A1F] text-white">
                    {setupChecking ? "Checking..." : "Test live connection"}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => saveSensorSetup("waiting")} className="bg-white">
                    Save setup and open dashboard
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`min-h-screen dashboard-shell ${isDark ? "dashboard-dark" : "dashboard-light"}`} style={{ background: colors.bodyBg }}>
      {!userData.sensorSetupComplete && <SensorSetupWindow />}
      {/* Sidebar */}
      <aside className="hidden md:flex fixed left-0 top-0 bottom-0 z-40 overflow-y-auto" style={{ width: 240, background: colors.greenDark }}>
        <div className="relative min-h-full flex flex-col">
          <div className="p-5 border-b" style={{ borderColor: "rgba(255,255,255,0.1)" }}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: colors.greenMid }}>
                <Leaf className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="font-display font-bold text-white">CropConnect</p>
                <p className="text-[10px] uppercase tracking-wider" style={{ color: colors.textLight }}>{t("farmDashboard")}</p>
              </div>
            </div>
          </div>

          <nav className="flex-1 p-3 space-y-1">
            <div className="mb-4">
              <p className="text-[10px] uppercase tracking-wider px-3 mb-2" style={{ color: colors.textLight }}>{t("overview")}</p>
              {navItems.slice(0, 2).map((item) => (
                <button key={item.id} onClick={() => setActivePage(item.id)} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors relative ${activePage === item.id ? "bg-white/12" : "hover:bg-white/5"}`}>
                  {activePage === item.id && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full" style={{ background: colors.gold }} />}
                  <item.icon className={`w-4 h-4 ${activePage === item.id ? "text-white" : "text-white/60"}`} />
                  <span className={`text-sm ${activePage === item.id ? "text-white" : "text-white/70"}`}>{item.label}</span>
                  {item.badge && <span className="ml-auto px-1.5 py-0.5 text-[10px] rounded-full" style={{ background: item.badge === t("live") ? colors.greenLight : colors.terracotta, color: "white" }}>{item.badge}</span>}
                </button>
              ))}
            </div>

            <div className="mb-4">
              <p className="text-[10px] uppercase tracking-wider px-3 mb-2" style={{ color: colors.textLight }}>{t("control")}</p>
              {navItems.slice(2, 4).map((item) => (
                <button key={item.id} onClick={() => setActivePage(item.id)} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors relative ${activePage === item.id ? "bg-white/12" : "hover:bg-white/5"}`}>
                  {activePage === item.id && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full" style={{ background: colors.gold }} />}
                  <item.icon className={`w-4 h-4 ${activePage === item.id ? "text-white" : "text-white/60"}`} />
                  <span className={`text-sm ${activePage === item.id ? "text-white" : "text-white/70"}`}>{item.label}</span>
                </button>
              ))}
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wider px-3 mb-2" style={{ color: colors.textLight }}>{t("intelligence")}</p>
              {navItems.slice(4).map((item) => (
                <button key={item.id} onClick={() => setActivePage(item.id)} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors relative ${activePage === item.id ? "bg-white/12" : "hover:bg-white/5"}`}>
                  {activePage === item.id && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full" style={{ background: colors.gold }} />}
                  <item.icon className={`w-4 h-4 ${activePage === item.id ? "text-white" : "text-white/60"}`} />
                  <span className={`text-sm ${activePage === item.id ? "text-white" : "text-white/70"}`}>{item.label}</span>
                  {item.badge && <span className="ml-auto px-1.5 py-0.5 text-[10px] rounded-full" style={{ background: colors.terracotta, color: "white" }}>{item.badge}</span>}
                </button>
              ))}
            </div>
          </nav>

          <div className="p-3 border-t" style={{ borderColor: "rgba(255,255,255,0.1)" }}>
            <div className="flex items-center gap-3 px-3 py-2">
              <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold" style={{ background: `linear-gradient(135deg, ${colors.greenMid}, ${colors.terracotta})` }}>
                <span data-no-translate="true">{getInitials(userData.name)}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p data-no-translate="true" className="text-sm font-medium text-white truncate">{userData.name}</p>
                <p data-dynamic-value="true" className="text-xs" style={{ color: colors.textLight }}>
                  {displayValue(userData.locationType === "city" ? userData.city : userData.village)} - {displayValue(userData.landSize, " acres")}
                </p>
              </div>
              <button onClick={handleLogout} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors">
                <LogOut className="w-4 h-4 text-white/60" />
              </button>
            </div>
          </div>

          <div className="absolute bottom-0 right-0 w-32 h-32 rounded-full pointer-events-none" style={{ background: `radial-gradient(circle, ${colors.greenAccent}30 0%, transparent 70%)` }} />
        </div>
      </aside>

      <main className="transition-all duration-300 md:ml-[240px]">
        <header className="fixed top-0 left-0 md:left-[240px] right-0 z-30 backdrop-blur-md" style={{ height: 64, background: "rgba(245, 242, 236, 0.92)", borderBottom: "1px solid rgba(213, 209, 197, 0.5)" }}>
          <div className="h-full flex items-center justify-between gap-3 px-3 sm:px-4 md:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <label className="relative flex items-center md:hidden">
                <selectedNavItem.icon className="pointer-events-none absolute left-3 w-4 h-4" style={{ color: colors.greenDark }} />
                <select
                  value={activePage}
                  onChange={(event) => setActivePage(event.target.value)}
                  className="h-10 w-[152px] appearance-none rounded-lg border border-[#d5d1c5] bg-white pl-9 pr-8 text-sm font-medium outline-none focus:ring-2 focus:ring-[#1B4332]/20"
                  style={{ color: colors.textDark }}
                  aria-label="Switch dashboard page"
                >
                  {navItems.map((item) => (
                    <option key={item.id} value={item.id}>{item.label}</option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 w-4 h-4" style={{ color: colors.textLight }} />
              </label>
              <div className="min-w-0">
              <h1 className="font-display text-xl font-bold" style={{ color: colors.textDark }}>{pageConfig[activePage]?.title || t("dashboard")}</h1>
                <p className="hidden sm:block text-xs truncate" style={{ color: colors.textLight }}>{pageConfig[activePage]?.subtitle || "Farm overview"}</p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <div className="hidden sm:inline-flex rounded-lg border border-[#d5d1c5] bg-white px-2 py-1">
                <LanguageSelect value={language} onChange={handleLanguageChange} />
              </div>
              <div className="hidden sm:flex flex-col gap-2 px-3 py-1.5 rounded-full" style={{ background: "rgba(45, 90, 61, 0.1)" }}>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full animate-pulse ${sensorConnection.source === "esp32" ? "bg-green-500" : "bg-amber-500"}`} />
                  <span className="text-xs font-medium" style={{ color: colors.greenDark }}>
                    {sensorConnection.deviceId} - {sensorConnection.source === "esp32" ? "ESP32 Live" : "Unavailable"}
                  </span>
                </div>
                {sensorConnection.source !== "esp32" && sensorConnection.error ? (
                  <span className="text-[10px] uppercase tracking-[0.16em] text-amber-800">{sensorConnection.error}</span>
                ) : null}
              </div>
              <button onClick={() => setActivePage("notifications")} className="p-2 rounded-lg hover:bg-gray-100 transition-colors relative" aria-label="Open notifications">
                <Bell className="w-4 h-4" style={{ color: colors.textMid }} />
                {activeSensorAlerts.length > 0 && <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red-500" />}
              </button>
            </div>
          </div>
        </header>

        <div className="p-3 sm:p-5 md:p-6 pt-[80px] md:pt-[80px]">{renderPage()}</div>
      </main>

    </div>
  );
}
