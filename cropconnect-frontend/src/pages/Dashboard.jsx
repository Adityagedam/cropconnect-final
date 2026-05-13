import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
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
import ChatPanel from "../components/dashboard/ChatPanel";
import MarketPanel from "../components/dashboard/MarketPanel";
import PumpControl from "../components/dashboard/PumpControl";
import SensorPanel from "../components/dashboard/SensorPanel";
import WeatherPanel from "../components/dashboard/WeatherPanel";
import CropPlanner from "./CropPlanner";
import { toast } from "sonner";
import { API, clearCsrfToken, csrfHeadersAsync } from "../lib/api";

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
const jsonHeaders = () => ({
  "Content-Type": "application/json",
});
const normalizeUserProfile = (user = {}) => ({
  id: user.id || null,
  name: user.name || "",
  email: user.email || "",
  phone: user.phone || "",
  state: user.state || "",
  district: user.district || "",
  locationType: user.locationType || "city",
  city: user.city || user.location || "",
  village: user.village || "",
  landSize: user.landSize || "",
  sensors: user.sensors || "0",
  pumps: user.pumps || "0",
  sensorDeviceId: user.sensorDeviceId || "",
  sensorSetupComplete: Boolean(user.sensorSetupComplete),
  sensorSetupStatus: user.sensorSetupStatus || "waiting",
});
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

// Initial sensor data
const initialSensorData = {
  soilMoisture: null,
  temperature: null,
  humidity: null,
  soilPh: null,
  nitrogen: null,
  phosphorus: null,
  potassium: null,
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
  const navigate = useNavigate();
  const [userData, setUserData] = useState({
    name: "",
    email: "",
    state: "",
    district: "",
    city: "",
    village: "",
    landSize: "",
    cropType: "",
    farmingType: "",
    zoneA: "",
    zoneB: "",
    zoneC: "",
    sensors: "0",
    pumps: "0",
    sensorDeviceId: "",
    sensorSetupComplete: false,
    sensorSetupStatus: "waiting",
  });
  const [language, setLanguage] = useState(
    () => localStorage.getItem("cropconnect-language") || "en"
  );
  const [theme, setTheme] = useState(
    () => localStorage.getItem("cropconnect-theme") || "light"
  );
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [editData, setEditData] = useState({});
  const [userLoaded, setUserLoaded] = useState(false);
  const [activePage, setActivePage] = useState("dashboard");
  const [sensorData, setSensorData] = useState(initialSensorData);
  const [sensorConnection, setSensorConnection] = useState({
    source: "unavailable",
    deviceId: "",
    lastSeen: null,
    error: null,
  });
  const [pumps, setPumps] = useState({
    pump1: { on: false, appliedOn: null, hardwareConfirmed: false, runtime: 0, schedule: {} },
    pump2: { on: false, appliedOn: null, hardwareConfirmed: false, runtime: 0, schedule: {} },
  });
  const [apiLogs, setApiLogs] = useState([]);
  const [telemetryPacket, setTelemetryPacket] = useState({});
  const [weatherData, setWeatherData] = useState(null);
  const [weatherError, setWeatherError] = useState("");
  const [marketData, setMarketData] = useState(emptyMarketData);
  const [marketError, setMarketError] = useState("");
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketInsight, setMarketInsight] = useState(null);
  const [marketInsightError, setMarketInsightError] = useState("");
  const [marketInsightLoading, setMarketInsightLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [speechRecognition, setSpeechRecognition] = useState(null);
  const speechSentRef = useRef(false);
  const [pumpUpdating, setPumpUpdating] = useState({});
  const [scheduledTimers, setScheduledTimers] = useState({ pump1: [], pump2: [] });
  const [showTimerModal, setShowTimerModal] = useState({ show: false, pump: null });
  const [newTimer, setNewTimer] = useState({ hour: "", minute: "00", period: "AM", duration: "", days: [] });
  const [sensorSetupForm, setSensorSetupForm] = useState({
    deviceId: "",
    nodeCount: "1",
  });
  const [setupChecking, setSetupChecking] = useState(false);
  const [setupCheckResult, setSetupCheckResult] = useState(null);
  const [sensorApiKey, setSensorApiKey] = useState("");
  const [sensorApiKeyLoading, setSensorApiKeyLoading] = useState(false);
  const [sensorApiKeyError, setSensorApiKeyError] = useState("");
  const logContainerRef = useRef(null);
  const chatContainerRef = useRef(null);
  const handleSendMessageRef = useRef(null);
  const pumpsRef = useRef(pumps);
  const activeSensorAlertsRef = useRef([]);
  const alertToastIntervalRef = useRef(null);
  const persistedFarmLoadedRef = useRef(false);
  const snapshotSaveInFlightRef = useRef(false);
  const isDark = theme === "dark";
  const colors = isDark ? darkColors : lightColors;
  const copy = dashboardCopy.en;
  const t = (key) => copy[key] || dashboardCopy.en[key] || key;
  const chatText = chatCopy.en;
  const ct = (key) => chatText[key] || chatCopy.en[key] || key;
  const cropZones = useMemo(
    () => [
      { id: "zoneA", name: "Zone A", crop: userData.zoneA, area: "" },
      { id: "zoneB", name: "Zone B", crop: userData.zoneB, area: "" },
      { id: "zoneC", name: "Zone C", crop: userData.zoneC, area: "" },
    ],
    [userData.zoneA, userData.zoneB, userData.zoneC]
  );
  const activeSensorAlerts = useMemo(
    () => buildSensorAlerts(sensorData, sensorConnection),
    [sensorData, sensorConnection]
  );
  const hasSensorReadings = Object.values(sensorData).some(isPresent);

  const requireFreshLogin = useCallback(() => {
    clearCsrfToken();
    toast.error("Please log in again to continue.");
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

  const ownerPayload = useCallback(() => ({}), []);

  const saveTimersToMysql = useCallback(async (nextTimers) => {
    const response = await protectedFetch(`${API}/farm/timers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...ownerPayload(), timers: nextTimers }),
    });
    if (!response.ok) throw new Error("Could not save timers");
  }, [ownerPayload, protectedFetch]);

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

  const getUserWeatherLocation = useCallback(() => {
    const place =
      userData.locationType === "village"
        ? userData.village || userData.city
        : userData.city || userData.village;
    return [place, userData.district, userData.state].filter(Boolean).join(", ");
  }, [userData.city, userData.district, userData.locationType, userData.state, userData.village]);

  const getUserMarketLocation = useCallback(() => {
    const place =
      userData.locationType === "village"
        ? userData.village || userData.city
        : userData.city || userData.village;
    return [place, userData.district, userData.state].filter(Boolean).join(", ");
  }, [userData.city, userData.district, userData.locationType, userData.state, userData.village]);

  const loadMarketPrices = useCallback(async (isCancelled = () => false) => {
    if (!userLoaded) return;
    const locationName = getUserMarketLocation();

    if (!userData.state) {
      if (!isCancelled()) {
        setMarketData(emptyMarketData);
        setMarketError("Please add your state in profile to load local mandi prices.");
      }
      return;
    }

    if (!isCancelled()) {
      setMarketLoading(true);
      setMarketError("");
    }

    try {
      const response = await protectedFetch(`${API}/market/prices`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(marketFriendlyError(payload.detail || `Market prices returned ${response.status}`));
      }

      if (!isCancelled()) {
        setMarketData({
          ...emptyMarketData,
          ...payload,
          requestedLocation: payload.requestedLocation || locationName,
          prices: Array.isArray(payload.prices) ? payload.prices : [],
          mandis: Array.isArray(payload.mandis) ? payload.mandis : [],
        });
        setMarketInsight(null);
        setMarketInsightError("");
      }
    } catch (error) {
      if (!isCancelled()) {
        setMarketData({ ...emptyMarketData, requestedLocation: locationName });
        setMarketError(marketFriendlyError(error.message || "Could not load live mandi prices"));
        setMarketInsight(null);
        setMarketInsightError("");
      }
    } finally {
      if (!isCancelled()) setMarketLoading(false);
    }
  }, [getUserMarketLocation, protectedFetch, userData.state, userLoaded]);

  const loadMarketInsight = useCallback(async () => {
    if (!userLoaded) return;

    setMarketInsightLoading(true);
    setMarketInsightError("");
    try {
      const response = await protectedFetch(`${API}/market/insights`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({
          language,
          objective: "Analyze live mandi records for this user's location and give cautious selling guidance.",
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(marketFriendlyError(payload.detail || `AI market insight returned ${response.status}`));
      }
      setMarketInsight(payload);
      if (payload.market_data) {
        setMarketData({
          ...emptyMarketData,
          ...payload.market_data,
          prices: Array.isArray(payload.market_data.prices) ? payload.market_data.prices : [],
          mandis: Array.isArray(payload.market_data.mandis) ? payload.market_data.mandis : [],
        });
      }
    } catch (error) {
      setMarketInsight(null);
      setMarketInsightError(marketFriendlyError(error.message || "Could not generate AI market insight"));
    } finally {
      setMarketInsightLoading(false);
    }
  }, [language, protectedFetch, userLoaded]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem("cropconnect-theme", theme);
  }, [isDark, theme]);

  useEffect(() => {
    pumpsRef.current = pumps;
  }, [pumps]);

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

  // Load authenticated profile from MySQL instead of browser profile storage.
  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const response = await protectedFetch(`${API}/auth/profile`);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(humanizeApiValue(payload.detail, `Profile returned ${response.status}`));
        const normalizedUser = normalizeUserProfile(payload.user || {});
        if (cancelled) return;
        setUserData(normalizedUser);
        setSensorSetupForm((prev) => ({
          ...prev,
          deviceId: normalizedUser.sensorDeviceId || prev.deviceId,
          nodeCount: normalizedUser.sensors || prev.nodeCount,
        }));
      } catch (error) {
        if (!cancelled && error.message !== "Login expired") {
          toast.error(error.message || "Could not load account profile");
        }
      } finally {
        if (!cancelled) setUserLoaded(true);
      }
    };

    loadProfile();
    return () => {
      cancelled = true;
    };
  }, [protectedFetch]);

  useEffect(() => {
    if (!userLoaded || userData.sensorSetupComplete || !userData.sensorDeviceId || sensorApiKey || sensorApiKeyLoading) return;
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

  // Poll desired/applied pump status so queued commands stop looking like confirmed hardware state.
  useEffect(() => {
    if (!userLoaded) return undefined;
    let cancelled = false;

    const loadPumpStates = async () => {
      try {
        const response = await protectedFetch(`${API}/farm/pump-states`);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !Array.isArray(payload.items) || cancelled) return;
        setPumps((prev) => {
          const next = { ...prev };
          payload.items.forEach((item) => {
            if (!next[item.pump_id]) return;
            const desiredOn = Boolean(item.desired_on ?? item.on);
            const appliedOn = item.applied_on === null || item.applied_on === undefined ? null : Boolean(item.applied_on);
            next[item.pump_id] = {
              ...next[item.pump_id],
              on: desiredOn,
              appliedOn,
              hardwareConfirmed: Boolean(item.hardware_confirmed),
              runtime: item.runtime || next[item.pump_id].runtime || 0,
              schedule: Object.keys(item.schedule || {}).length ? item.schedule : next[item.pump_id].schedule,
            };
          });
          return next;
        });
      } catch {
        // The sensor and auth paths already surface connection/auth problems.
      }
    };

    loadPumpStates();
    const interval = setInterval(loadPumpStates, SENSOR_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
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

  const applyBackendReadings = useCallback((payload) => {
    const readings = Array.isArray(payload?.readings) ? payload.readings : [];
    if (!readings.length) {
      if (payload && !Array.isArray(payload?.readings)) {
        console.warn("Unexpected sensor payload format:", payload);
      }
      setSensorData(initialSensorData);
      setSensorConnection({
        source: "unavailable",
        deviceId: payload?.device_id || userData.sensorDeviceId || "",
        lastSeen: payload?.recorded_at || null,
        error: payload?.message || "Waiting for ESP32 readings",
      });
      return false;
    }

    const byType = readings.reduce((acc, reading) => {
      if (!reading || typeof reading.sensor_type !== "string") return acc;
      const value = Number(reading.value);
      if (!Number.isNaN(value)) {
        acc[reading.sensor_type] = value;
      }
      return acc;
    }, {});

    const updatedData = {
      soilMoisture: Number.isFinite(byType.soil_moisture) ? Math.round(byType.soil_moisture) : null,
      temperature: Number.isFinite(byType.temperature) ? Number(byType.temperature.toFixed(1)) : null,
      humidity: Number.isFinite(byType.humidity) ? Math.round(byType.humidity) : null,
      soilPh: Number.isFinite(byType.ph) ? Number(byType.ph.toFixed(1)) : null,
      nitrogen: Number.isFinite(byType.nitrogen) ? Number(byType.nitrogen.toFixed(1)) : null,
      phosphorus: Number.isFinite(byType.phosphorus) ? Number(byType.phosphorus.toFixed(1)) : null,
      potassium: Number.isFinite(byType.potassium) ? Number(byType.potassium.toFixed(1)) : null,
    };

    const hasValidValue = Object.values(updatedData).some((value) => value !== null);
    if (!hasValidValue) {
      setSensorData(initialSensorData);
      setSensorConnection({
        source: "unavailable",
        deviceId: payload.device_id || userData.sensorDeviceId || "",
        lastSeen: payload.recorded_at || null,
        error: payload.message || "Latest ESP32 packet had no sensor readings",
      });
      return false;
    }

    setSensorData(updatedData);

    setSensorConnection({
      source: payload.source === "esp32" ? "esp32" : "unavailable",
      deviceId: payload.device_id || userData.sensorDeviceId || "",
      lastSeen: payload.recorded_at || new Date().toISOString(),
      error: null,
    });

    return true;
  }, [userData.sensorDeviceId]);

  // Read latest ESP32 data from the backend.
  useEffect(() => {
    let cancelled = false;
    const primaryDeviceId = userData.sensorDeviceId || "";

    const loadLatestReadings = async () => {
      if (!primaryDeviceId) {
        setSensorConnection((prev) => ({
          ...prev,
          source: "unavailable",
          deviceId: "",
          error: "No sensor device configured",
        }));
        return;
      }

      try {
        let payload = null;
        let usedDeviceId = primaryDeviceId;

        const response = await protectedFetch(`${API}/sensors/latest?device_id=${encodeURIComponent(primaryDeviceId)}`);
        if (!response.ok) throw new Error(`Backend returned ${response.status}`);
        payload = await response.json();
        if (cancelled) return;

        if (!payload) {
          throw new Error("No response from sensor backend");
        }

        const applied = applyBackendReadings(payload);
        if (!applied) {
          const errorMessage = payload?.message || "Waiting for ESP32 readings";
          console.warn("ESP32 sensor payload not applied:", payload);
          setSensorConnection((prev) => ({
            ...prev,
            source: "unavailable",
            deviceId: usedDeviceId,
            error: errorMessage,
          }));
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to load latest ESP32 readings:", error);
          setSensorData(initialSensorData);
          setSensorConnection((prev) => ({
            ...prev,
            source: "unavailable",
            error: error.message,
          }));
        }
      }
    };

    loadLatestReadings();
    const interval = setInterval(loadLatestReadings, SENSOR_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [applyBackendReadings, protectedFetch, userData.sensorDeviceId]);

  // Update telemetry packet when sensor data changes
  useEffect(() => {
    setTelemetryPacket({
      timestamp: new Date().toISOString(),
      node_id: sensorConnection.deviceId,
      source: sensorConnection.source,
      soil_moisture: sensorData.soilMoisture,
      temperature: sensorData.temperature,
      humidity: sensorData.humidity,
      ph_level: sensorData.soilPh,
      nitrogen: sensorData.nitrogen,
      phosphorus: sensorData.phosphorus,
      potassium: sensorData.potassium,
    });
  }, [sensorData, sensorConnection.deviceId, sensorConnection.source]);

  // Persist the current dashboard state periodically so refreshes restore from MySQL.
  useEffect(() => {
    if (!userLoaded || !persistedFarmLoadedRef.current) return undefined;
    const interval = setInterval(() => {
      saveDashboardSnapshot().catch(() => {});
    }, SNAPSHOT_SAVE_INTERVAL_MS);
    saveDashboardSnapshot().catch(() => {});
    return () => clearInterval(interval);
  }, [saveDashboardSnapshot, userLoaded]);

  // Load live internet weather data for the user's area.
  useEffect(() => {
    let cancelled = false;
    const locationName = getUserWeatherLocation();

    if (!locationName) {
      setWeatherData(null);
      setWeatherError("Please add your city or village and state in your profile.");
      return undefined;
    }
    const loadWeather = async () => {
      try {
        setWeatherError("");
        const response = await fetch(`${API}/weather/forecast?location=${encodeURIComponent(locationName)}`);
        if (!response.ok) throw new Error(`Weather returned ${response.status}`);
        const payload = await response.json();
        if (!cancelled) setWeatherData(payload);
      } catch (error) {
        if (!cancelled) {
          setWeatherData(null);
          setWeatherError(error.message || "Could not load live weather");
        }
      }
    };

    loadWeather();
    const interval = setInterval(loadWeather, 15 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [getUserWeatherLocation]);

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

  const updatePumpState = useCallback(async (pumpId, nextOn, pumpOverride = null) => {
    const pump = pumpOverride || pumpsRef.current[pumpId] || {};
    const response = await protectedFetch(`${API}/pump/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pump_id: pumpId,
        on: nextOn,
        device_id: sensorConnection.deviceId || userData.sensorDeviceId || "",
        runtime: pump.runtime || 0,
        schedule: pump.schedule || {},
      }),
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.detail || "Could not update pump state");
    }

    return data;
  }, [protectedFetch, sensorConnection.deviceId, userData.sensorDeviceId]);

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

  const togglePump = async (pumpId) => {
    const nextOn = !pumpsRef.current[pumpId].on;
    const pumpName = pumpId === "pump1" ? "Pump 1" : "Pump 2";

    setPumpUpdating((prev) => ({ ...prev, [pumpId]: true }));

    try {
      const data = await updatePumpState(pumpId, nextOn);

      setPumps((prev) => ({
        ...prev,
        [pumpId]: {
          ...prev[pumpId],
          on: nextOn,
          hardwareConfirmed: false,
          runtime: nextOn ? 0 : prev[pumpId].runtime,
        },
      }));

      const stateText = nextOn ? "ON" : "OFF";
      if (data.sent_to_esp32) {
        toast.success(`${pumpName} turned ${stateText} through ESP32`);
      } else {
        toast.info(data.message || `${pumpName} command queued for SIM800L`);
      }
    } catch (error) {
      toast.error(error.message || "Could not reach pump controller");
    } finally {
      setPumpUpdating((prev) => ({ ...prev, [pumpId]: false }));
    }
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API}/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: await csrfHeadersAsync(),
      });
    } catch {
      // Local logout still clears client state if the network is unavailable.
    }
    clearCsrfToken();
    toast.success("Logged out successfully");
    navigate("/login");
  };

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

  const saveUserToMysql = async (updates) => {
    const response = await protectedFetch(`${API}/auth/profile`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        ...updates,
      }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not save data in MySQL");
    }

    return payload.user;
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

  // Get speech recognition language code
  const getSpeechLangCode = (langCode) => {
    const langMap = {
      'en': 'en-US',
      'hi': 'hi-IN',
      'mr': 'mr-IN',
      'te': 'te-IN',
      'ta': 'ta-IN',
      'kn': 'kn-IN',
      'bn': 'bn-IN',
    };
    return langMap[langCode] || 'en-US';
  };

  // Speech recognition setup
  useEffect(() => {
    if (typeof window !== 'undefined' && 'webkitSpeechRecognition' in window) {
      const recognition = new window.webkitSpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = getSpeechLangCode(language);

      recognition.onstart = () => {
        setIsListening(true);
        speechSentRef.current = false;
        const selectedLangName = languages.find(l => l.code === language)?.name || language;
        toast.info(`Listening... Speak your question in ${selectedLangName}`);
      };

      recognition.onresult = (event) => {
        if (speechSentRef.current) return;
        const transcript = event.results[0][0].transcript;
        setChatInput(transcript);

        const detectedLang = detectLanguage(transcript);
        const detectedLangName = languages.find(l => l.code === detectedLang)?.name || detectedLang;
        const selectedLangName = languages.find(l => l.code === language)?.name || language;
        if (detectedLang !== language) {
          toast.info(`Detected ${detectedLangName}; answering in ${selectedLangName}.`);
        } else {
          toast.success(`${detectedLangName} detected! Sending response in ${selectedLangName}...`);
        }

        speechSentRef.current = true;
        setTimeout(() => handleSendMessageRef.current?.(transcript, null, detectedLang), 500);
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'no-speech') {
          toast.error("No speech detected. Please try again.");
        } else if (event.error === 'network') {
          toast.error("Network error. Please check your connection.");
        } else {
          toast.error(`Speech recognition failed: ${event.error}`);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      setSpeechRecognition(recognition);
    }
  }, [detectLanguage, language]);

  const startListening = () => {
    if (speechRecognition && !isListening) {
      try {
        speechRecognition.lang = getSpeechLangCode(language);
        speechRecognition.start();
      } catch (error) {
        console.error('Error starting speech recognition:', error);
        toast.error("Could not start microphone. Please check permissions.");
      }
    } else if (!speechRecognition) {
      toast.error("Speech recognition not supported in your browser. Try Chrome, Edge, or Safari.");
    }
  };

  const stopListening = () => {
    if (speechRecognition && isListening) {
      speechRecognition.stop();
    }
  };

  const handleSendMessage = async (messageOverride, responseKeyOverride = null, detectedLanguage = null) => {
    const messageText = (messageOverride ?? chatInput).trim();
    if (!messageText) return;
    const inputLanguage = detectedLanguage || detectLanguage(messageText);

    const userMessage = { id: Date.now(), type: "user", text: messageText };
    setChatMessages((prev) => [...prev, userMessage]);
    setChatInput("");
    setShowSuggestions(false);
    setIsTyping(true);

    try {
      const response = await protectedFetch(`${API}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...ownerPayload(),
          message: messageText,
          language,
          input_language: inputLanguage,
          device_id: sensorConnection.deviceId || userData.sensorDeviceId || "",
          history: chatMessages.slice(-4).map((msg) => ({
            type: String(msg.type || ""),
            text: humanizeApiValue(msg.text),
          })),
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(humanizeApiValue(payload.detail, `AI returned ${response.status}`));
      const responseText = humanizeApiValue(payload.reply, "");
      if (!responseText) throw new Error("AI returned an empty answer");
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          type: "bot",
          text: responseText,
          relatedToPlantOrSoil: payload.related_to_plant_or_soil,
        },
      ]);
    } catch (error) {
      if (error.message === "Login required" || error.message === "Login expired") {
        return;
      }
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          type: "bot",
          text: error.message || "AI chatbot is unavailable.",
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSuggestionClick = (suggestion, suggestionKey) => {
    handleSendMessage(suggestion, suggestionKey);
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

  // Line chart component
  const LineChart = ({ data, color, height = 120 }) => {
    if (!Array.isArray(data) || data.length < 2) {
      return (
        <div className="flex items-center justify-center text-sm" style={{ height, color: colors.textLight }}>
          {EMPTY_DISPLAY}
        </div>
      );
    }
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const points = data.map((v, i) => ({
      x: (i / (data.length - 1)) * 100,
      y: 100 - ((v - min) / range) * 80 - 10,
    }));
    const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
    const areaD = `${pathD} L 100 100 L 0 100 Z`;

    return (
      <svg viewBox="0 0 100 100" className="w-full" style={{ height }} preserveAspectRatio="none">
        <defs>
          <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <path d={areaD} fill={`url(#gradient-${color})`} />
        <path d={pathD} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
    );
  };

  // Semicircle gauge component
  const SemicircleGauge = ({ value, max = 100, size = 140 }) => {
    const radius = size / 2 - 8;
    const circumference = Math.PI * radius;
    const numericValue = numericOrNull(value);
    const offset = circumference - ((numericValue || 0) / max) * circumference;

    return (
      <div className="relative inline-block" style={{ width: size, height: size / 2 }}>
        <svg width={size} height={size / 2} viewBox={`0 0 ${size} ${size / 2}`}>
          <defs>
            <linearGradient id="gaugeGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={colors.red} />
              <stop offset="50%" stopColor={colors.gold} />
              <stop offset="100%" stopColor={colors.greenLight} />
            </linearGradient>
          </defs>
          <path
            d={`M 8 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 8} ${size / 2}`}
            fill="none"
            stroke={colors.creamDark}
            strokeWidth="8"
          />
          <path
            d={`M 8 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 8} ${size / 2}`}
            fill="none"
            stroke="url(#gaugeGradient)"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute bottom-1 left-1/2 -translate-x-1/2 text-center">
          <span className="text-2xl font-mono font-bold" style={{ color: colors.textDark }}>{displayValue(numericValue)}</span>
          {numericValue !== null && <span className="text-xs" style={{ color: colors.textLight }}>/{max}</span>}
        </div>
      </div>
    );
  };

  // Status chip component
  const StatusChip = ({ status }) => {
    const styles = {
      OK: { bg: "bg-green-100", text: "text-green-700", border: "border-green-200" },
      WARN: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-200" },
      CRIT: { bg: "bg-red-100", text: "text-red-700", border: "border-red-200" },
    };
    const s = styles[status] || styles.OK;
    return (
      <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${s.bg} ${s.text} ${s.border}`}>
        {status}
      </span>
    );
  };

  // Metric card component
  const MetricCard = ({ icon: Icon, title, value, unit, color, trend, trendValue, progress }) => {
    const colorStyles = {
      green: { bg: "bg-green-50", border: "border-green-200", text: "text-green-600", fill: colors.greenLight },
      orange: { bg: "bg-orange-50", border: "border-orange-200", text: "text-orange-600", fill: colors.terracotta },
      blue: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-600", fill: colors.blue },
      gold: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-600", fill: colors.gold },
    };
    const style = colorStyles[color] || colorStyles.green;
    const numericProgress = numericOrNull(progress);

    return (
      <div className={`relative p-4 rounded-xl bg-white border ${style.border} shadow-sm overflow-hidden`}>
        <div className="absolute -right-4 -top-4 w-16 h-16 rounded-full opacity-8" style={{ background: style.fill }} />
        <div className="flex items-start justify-between">
          <div className={`p-2 rounded-lg ${style.bg}`}>
            <Icon className="w-5 h-5" style={{ color: style.fill }} />
          </div>
          {trend && isPresent(trendValue) && (
            <div className={`flex items-center gap-1 text-xs ${trend === "up" ? "text-green-600" : "text-red-600"}`}>
              {trend === "up" ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {trendValue}
            </div>
          )}
        </div>
        <div className="mt-3">
          <p className="text-sm" style={{ color: colors.textLight }}>{title}</p>
          <p className="text-2xl font-mono font-bold mt-1" style={{ color: colors.textDark }}>
            {displayValue(value)}
            {isPresent(value) && <span className="text-sm font-normal ml-1" style={{ color: colors.textLight }}>{unit}</span>}
          </p>
        </div>
        {numericProgress !== null && (
          <div className="mt-3 h-1.5 rounded-full bg-gray-100 overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${Math.max(0, Math.min(100, numericProgress))}%`, background: style.fill }} />
          </div>
        )}
      </div>
    );
  };

  // Field Map Component
  const FieldMap = () => {
    const zoneHasAlert = (zoneName) => activeSensorAlerts.some((alert) => alert.zone === zoneName);

    return (
      <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold" style={{ color: colors.textDark }}>Field Map</h3>
          <span className="text-xs px-2 py-1 rounded-full bg-green-50 text-green-600">{displayValue(userData.landSize, " acres")}</span>
        </div>
        <div className="relative rounded-xl overflow-hidden" style={{ height: 280, background: `linear-gradient(135deg, #1a472a, #2d5a3d)` }}>
          {/* Simulated field map with zones */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="grid grid-cols-3 gap-2 p-4 w-full h-full">
              {/* Zone A */}
              <div className="relative rounded-lg overflow-hidden" style={{ background: "#4a8a5a", gridColumn: "span 2" }}>
                <div className="absolute top-2 left-2 text-white text-xs font-medium">Zone A - {userData.zoneA || "Crop"}</div>
                <div className="absolute bottom-2 left-2 text-white/70 text-xs">{displayValue(cropZones[0]?.area)}</div>
                <div className="absolute top-2 right-2">
                  {zoneHasAlert("Zone A") ? <AlertTriangle className="w-4 h-4 text-amber-300" /> : <Droplets className="w-4 h-4 text-green-200" />}
                </div>
                {/* Simulated crop rows */}
                <div className="absolute inset-0 flex flex-col justify-around p-4">
                  {[88, 92, 84, 90, 86].map((width, i) => (
                    <div key={i} className="h-0.5 bg-green-300/30 rounded-full" style={{ width: `${width}%` }} />
                  ))}
                </div>
              </div>
              {/* Zone B - Vegetables */}
              <div className="relative rounded-lg overflow-hidden" style={{ background: "#3a7a4a" }}>
                <div className="absolute top-2 left-2 text-white text-xs font-medium">Zone B - {userData.zoneB || "Crop"}</div>
                <div className="absolute bottom-2 left-2 text-white/70 text-xs">{displayValue(cropZones[1]?.area)}</div>
                <div className="absolute top-2 right-2">
                  {zoneHasAlert("Zone B") ? <AlertTriangle className="w-4 h-4 text-amber-300" /> : <Droplets className="w-4 h-4 text-green-200" />}
                </div>
              </div>
              {/* Zone C */}
              <div className="relative rounded-lg overflow-hidden" style={{ background: "#5a9a5a" }}>
                <div className="absolute top-2 left-2 text-white text-xs font-medium">Zone C - {userData.zoneC || "Crop"}</div>
                <div className="absolute bottom-2 left-2 text-white/70 text-xs">{displayValue(cropZones[2]?.area)}</div>
                <div className="absolute top-2 right-2">
                  {zoneHasAlert("Zone C") ? <AlertTriangle className="w-4 h-4 text-amber-300" /> : null}
                </div>
              </div>
              {/* Water body */}
              <div className="relative rounded-lg overflow-hidden" style={{ background: "#2a6aaa", gridColumn: "span 2" }}>
                <div className="absolute top-2 left-2 text-white/80 text-xs font-medium">Water Body</div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <Droplets className="w-6 h-6 text-blue-200/50" />
                </div>
              </div>
            </div>
          </div>
          {/* Location badge */}
          <div className="absolute bottom-4 right-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-white/10 backdrop-blur-sm">
            <MapPin className="w-4 h-4 text-white" />
            <span className="text-white text-xs">{userData.locationType === "city" ? userData.city : userData.village}, {userData.state}</span>
          </div>
        </div>
      </div>
    );
  };

  // Render active page content
  const renderPage = () => {
    switch (activePage) {
      case "dashboard":
        return (
          <div className="space-y-6">
            {userData.sensorSetupStatus === "waiting" && (
              <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-start gap-3">
                  <Wifi className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-amber-900">Waiting for first sensor packet</p>
                    <p className="text-sm text-amber-800">Device <span className="font-mono">{userData.sensorDeviceId}</span> is configured. The dashboard will switch to ESP32 Live after readings arrive.</p>
                  </div>
                </div>
                <Button type="button" variant="outline" className="bg-white" onClick={testSensorConnection}>
                  Check now
                </Button>
              </div>
            )}
            {/* Metric Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard icon={Droplets} title="Soil Moisture" value={sensorData.soilMoisture} unit="%" color="green" progress={sensorData.soilMoisture} />
              <MetricCard icon={CloudSun} title="Temperature" value={sensorData.temperature} unit={"\u00b0C"} color="orange" progress={isPresent(sensorData.temperature) ? percentValue(sensorData.temperature, 40) : null} />
              <MetricCard icon={Radio} title="Humidity" value={sensorData.humidity} unit="%" color="blue" progress={sensorData.humidity} />
              <MetricCard icon={Sprout} title="Soil pH" value={displayValue(sensorData.soilPh)} unit="" color="gold" progress={isPresent(sensorData.soilPh) ? percentValue(sensorData.soilPh, 10) : null} />
            </div>

            {/* Field Map and Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <FieldMap />
              <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
                <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Moisture Trend (24h)</h3>
                <LineChart data={[]}  color={colors.greenLight} height={200} />
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
                <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Active Alerts</h3>
                <div className="p-6 text-center text-sm" style={{ color: colors.textLight }}>{EMPTY_DISPLAY}</div>
              </div>

              <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
                <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Crop Health Score</h3>
                <div className="p-6 text-center text-sm" style={{ color: colors.textLight }}>{EMPTY_DISPLAY}</div>
              </div>
            </div>
          </div>
        );

      case "sensors":
        return (
          <SensorPanel
            colors={colors}
            sensorConnection={sensorConnection}
            sensorData={sensorData}
            userData={userData}
          />
        );

      case "pump":
        return (
          <PumpControl
            colors={colors}
            isDark={isDark}
            userData={userData}
            pumps={pumps}
            pumpUpdating={pumpUpdating}
            scheduledTimers={scheduledTimers}
            showTimerModal={showTimerModal}
            newTimer={newTimer}
            setNewTimer={setNewTimer}
            t={t}
            togglePump={togglePump}
            openTimerModal={openTimerModal}
            closeTimerModal={closeTimerModal}
            removeTimer={removeTimer}
            handleAddTimer={handleAddTimer}
            formatTime={formatTime}
            formatTimerStartTime={formatTimerStartTime}
          />
        );

      case "weather":
        return (
          <WeatherPanel
            colors={colors}
            weatherData={weatherData}
            weatherError={weatherError}
            userData={userData}
          />
        );

      case "notifications":
        const notificationItems = [
          ...activeSensorAlerts.map((alert) => ({
            icon: alert.icon,
            title: alert.title,
            body: alert.body,
            tone: alert.tone === "critical" ? colors.red : colors.terracotta,
            time: alert.time,
          })),
        ];

        return (
          <div className="space-y-4">
            {notificationItems.length === 0 && (
              <div className="p-6 rounded-xl bg-white border border-[#e8e3d8] shadow-sm text-center text-sm" style={{ color: colors.textLight }}>
                {EMPTY_DISPLAY}
              </div>
            )}
            {notificationItems.map((item) => (
              <div key={item.title} className="p-4 sm:p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm flex items-start gap-4">
                <span className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: `${item.tone}18`, color: item.tone }}>
                  <item.icon className="w-5 h-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                    <h3 className="font-semibold" style={{ color: colors.textDark }}>{item.title}</h3>
                    <span className="text-xs" style={{ color: colors.textLight }}>{item.time}</span>
                  </div>
                  <p className="mt-1 text-sm" style={{ color: colors.textMid }}>{item.body}</p>
                </div>
              </div>
            ))}
          </div>
        );

      case "market":
        return (
          <MarketPanel
            colors={colors}
            marketData={marketData}
            marketError={marketError}
            marketLoading={marketLoading}
            marketInsight={marketInsight}
            marketInsightError={marketInsightError}
            marketInsightLoading={marketInsightLoading}
            getUserMarketLocation={getUserMarketLocation}
            loadMarketPrices={loadMarketPrices}
            loadMarketInsight={loadMarketInsight}
          />
        );

      case "flow":
        return (
          <div className="space-y-6">
            <div className="p-6 rounded-xl" style={{ background: `linear-gradient(135deg, ${colors.greenDark}, #0f2a1f)` }}>
              <h3 className="font-semibold mb-6" style={{ color: colors.cream }}>Data Pipeline</h3>
              <div className="flex items-center justify-between flex-wrap gap-4">
                {[
                  { icon: Radio, title: "Soil Sensors", desc: "Moisture, pH, NPK and climate readings", note: "Field input" },
                  { icon: Zap, title: "Main ESP32", desc: "SIM800L telemetry and relay polling", note: "Cellular" },
                  { icon: CloudSun, title: "FastAPI + MySQL", desc: "Stores latest sensor rows and pump timers", note: "Backend" },
                  { icon: LayoutDashboard, title: "Web Dashboard", desc: "Shows latest data and queues commands", note: "Browser" },
                  { icon: Radio, title: "Pump ESP32", desc: "Receives relay commands from the main ESP32", note: "Serial link" },
                ].map((node, idx) => (
                  <div key={node.title} className="flex items-center gap-2">
                    <div className={`p-4 rounded-xl ${idx < 2 ? "ring-2 ring-amber-400" : ""}`} style={{ background: idx < 2 ? "rgba(200, 168, 75, 0.2)" : "rgba(255,255,255,0.1)" }}>
                      <node.icon className={`w-6 h-6 ${idx < 2 ? "text-amber-400" : "text-cream"}`} />
                    </div>
                    <div className={idx < 2 ? "text-amber-400" : "text-cream"}>
                      <p className="font-medium text-sm">{node.title}</p>
                      <p className="text-xs opacity-70">{node.desc}</p>
                      <p className="text-xs font-mono opacity-50 mt-1">{node.note}</p>
                    </div>
                    {idx < 4 && <span className="text-2xl text-cream animate-pulse" style={{ animationDuration: "2s" }}>{"->"}</span>}
                  </div>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {Object.entries(telemetryPacket).map(([key, value]) => (
                <div key={key} className="p-3 rounded-lg text-center" style={{ background: "rgba(30, 58, 47, 0.9)" }}>
                  <p className="text-xs font-mono mb-1" style={{ color: colors.textLight }}>{key}</p>
                  <p className="font-mono font-bold" style={{ color: colors.greenLight }}>{isPresent(value) ? value : EMPTY_DISPLAY}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="p-5 rounded-xl" style={{ background: "#0d1f17" }}>
                <h3 className="font-semibold mb-4" style={{ color: colors.greenLight }}>API Endpoint Log</h3>
                <div ref={logContainerRef} className="space-y-2 max-h-64 overflow-y-auto font-mono text-sm">
                  {apiLogs.map((log) => (
                    <div key={log.id} className="flex items-center gap-2">
                      <span className="text-xs" style={{ color: colors.textLight }}>{new Date(log.timestamp).toLocaleTimeString()}</span>
                      <span className={log.method === "GET" ? "text-blue-400" : log.method === "POST" ? "text-green-400" : "text-amber-400"}>{log.method}</span>
                      <span style={{ color: colors.cream }}>{log.path}</span>
                      <span className={log.status === 200 ? "text-green-400" : "text-amber-400"}>{log.status}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="p-5 rounded-xl" style={{ background: "#0d1f17" }}>
                <h3 className="font-semibold mb-4" style={{ color: colors.greenLight }}>Latest Telemetry Packet</h3>
                <pre className="font-mono text-sm overflow-x-auto" style={{ color: colors.cream }}>{JSON.stringify(telemetryPacket, null, 2)}</pre>
              </div>
            </div>
          </div>
        );

      case "ai":
        return (
          <ChatPanel
            colors={colors}
            chatContainerRef={chatContainerRef}
            chatMessages={chatMessages}
            userName={userData.name}
            isTyping={isTyping}
            showSuggestions={showSuggestions}
            suggestionChips={suggestionChips}
            ct={ct}
            handleSuggestionClick={handleSuggestionClick}
            chatInput={chatInput}
            setChatInput={setChatInput}
            handleSendMessage={handleSendMessage}
            isListening={isListening}
            startListening={startListening}
            stopListening={stopListening}
            language={language}
          />
        );

      case "cropPlanner":
        return (
          <div className="-m-3 sm:-m-5 md:-m-6">
            <CropPlanner
              key={language}
              dashboardSensorData={sensorData}
              dashboardSensorConnection={sensorConnection}
              userProfile={userData}
              language={language}
              embedded
            />
          </div>
        );

      case "settings":
        return (
          <div className="space-y-6">
            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>{t("language")}</h3>
              <div className="mb-4 inline-flex rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
                <LanguageSelect value={language} onChange={setLanguage} />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {languages.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => {
                      localStorage.setItem("cropconnect-language", lang.code);
                      setLanguage(lang.code);
                      toast.success(`Language changed to ${lang.name}`);
                    }}
                    className={`p-3 rounded-lg border-2 transition-colors flex flex-col items-center gap-1 ${
                      language === lang.code
                        ? "border-green-500 bg-green-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <Languages className="w-4 h-4" style={{ color: colors.greenDark }} />
                    <span className="text-lg font-medium" style={{ color: colors.textDark }}>{lang.name}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>{t("appearance")}</h3>
              <div className="flex gap-4">
                <button
                  onClick={() => {
                    setTheme("light");
                    toast.success("Light mode enabled");
                  }}
                  className={`flex-1 p-4 rounded-lg border-2 flex flex-col items-center gap-2 ${theme === "light" ? "border-green-500 bg-green-50" : "border-gray-300 hover:border-gray-400"}`}
                >
                  <Sun className="w-8 h-8 text-amber-500" />
                  <span className="font-medium" style={{ color: colors.textDark }}>{t("lightMode")}</span>
                </button>
                <button
                  onClick={() => {
                    setTheme("dark");
                    toast.success("Dark mode enabled");
                  }}
                  className={`flex-1 p-4 rounded-lg border-2 flex flex-col items-center gap-2 transition-colors ${theme === "dark" ? "border-green-500 bg-green-50" : "border-gray-300 hover:border-gray-400"}`}
                >
                  <Moon className="w-8 h-8 text-gray-600" />
                  <span className="font-medium" style={{ color: colors.textDark }}>{t("darkMode")}</span>
                </button>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Contact Us</h3>
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 rounded-lg" style={{ background: colors.cream }}>
                  <Mail className="w-5 h-5" style={{ color: colors.greenDark }} />
                  <div>
                    <p className="font-medium" style={{ color: colors.textDark }}>Email</p>
                    <p className="text-sm" style={{ color: colors.textMid }}>cropconnectco@gmail.com</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 rounded-lg" style={{ background: colors.cream }}>
                  <Phone className="w-5 h-5" style={{ color: colors.greenDark }} />
                  <div>
                    <p className="font-medium" style={{ color: colors.textDark }}>Phone</p>
                    <p className="text-sm" style={{ color: colors.textMid }}>+91 94791 87552</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 rounded-lg" style={{ background: colors.cream }}>
                  <MessageCircle className="w-5 h-5" style={{ color: colors.greenDark }} />
                  <div>
                    <p className="font-medium" style={{ color: colors.textDark }}>WhatsApp</p>
                    <p className="text-sm" style={{ color: colors.textMid }}>+91 94791 87552</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>About</h3>
              <p className="text-sm" style={{ color: colors.textMid }}>
                CropConnect v1.0.0 - Smart Farming Dashboard<br />
                Empowering farmers with IoT and AI technology
              </p>
            </div>
          </div>
        );

      case "profile":
        const handleEditProfile = async () => {
          if (isEditingProfile) {
            const updatedUser = { ...userData, ...editData };
            const location = updatedUser.locationType === "village"
              ? updatedUser.village || updatedUser.city || ""
              : updatedUser.city || updatedUser.village || "";

            setUserData(updatedUser);

            try {
              const mysqlUser = await saveUserToMysql({
                name: updatedUser.name,
                phone: updatedUser.phone,
                state: updatedUser.state,
                district: updatedUser.district || "",
                location,
                location_type: updatedUser.locationType || "city",
                city: updatedUser.city || "",
                village: updatedUser.village || "",
                land_size: updatedUser.landSize ? Number(updatedUser.landSize) : null,
                sensors: updatedUser.sensors || "0",
                pumps: updatedUser.pumps || "0",
              });
              const mergedUser = mysqlUser ? { ...updatedUser, ...mysqlUser } : updatedUser;
              setUserData(mergedUser);
              toast.success("Profile updated in MySQL!");
            } catch (error) {
              toast.error(error.message || "Profile saved locally, but MySQL update failed");
            }
          } else {
            setEditData(userData);
          }
          setIsEditingProfile(!isEditingProfile);
        };

        return (
          <div className="space-y-6">
            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold" style={{ background: colors.greenDark, color: "white" }}>
                    <span data-no-translate="true">{userData.name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)}</span>
                  </div>
                  <div>
                    <h3 data-no-translate="true" className="text-xl font-semibold" style={{ color: colors.textDark }}>{userData.name}</h3>
                    <p data-no-translate="true" className="text-sm" style={{ color: colors.textMid }}>{userData.email}</p>
                  </div>
                </div>
                <button
                  onClick={handleEditProfile}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    isEditingProfile
                      ? "bg-green-600 text-white"
                      : "bg-gray-100 hover:bg-gray-200"
                  }`}
                  style={{ color: isEditingProfile ? "white" : colors.textDark }}
                >
                  {isEditingProfile ? "Save" : "Edit Profile"}
                </button>
              </div>

              <div className="space-y-4">
                {[
                  { label: "Full Name", key: "name", type: "text" },
                  { label: "Email", key: "email", type: "email" },
                  { label: "State", key: "state", type: "text" },
                  { label: "District", key: "district", type: "text" },
                  { label: userData.locationType === "city" ? "City" : "Village", key: userData.locationType === "city" ? "city" : "village", type: "text" },
                  { label: "Land Size (acres)", key: "landSize", type: "text" },
                  { label: "Crop Type", key: "cropType", type: "text" },
                  { label: "Farming Type", key: "farmingType", type: "text" },
                  { label: "Zone A (Crops)", key: "zoneA", type: "text" },
                  { label: "Zone B (Crops)", key: "zoneB", type: "text" },
                  { label: "Zone C (Crops)", key: "zoneC", type: "text" },
                ].map((field) => (
                  <div key={field.key} className="flex justify-between items-center py-3 border-b" style={{ borderColor: colors.creamDark }}>
                    <span className="font-medium" style={{ color: colors.textDark }}>{field.label}</span>
                    {isEditingProfile ? (
                      <input
                        type={field.type}
                        value={editData[field.key] || ""}
                        onChange={(e) => setEditData({ ...editData, [field.key]: e.target.value })}
                        className="px-3 py-1 rounded border border-gray-300 text-right"
                        style={{ color: colors.textMid }}
                      />
                    ) : (
                      <span data-dynamic-value="true" style={{ color: colors.textMid }}>{displayValue(userData[field.key])}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Farm Statistics</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-lg" style={{ background: colors.cream }}>
                  <p className="text-sm" style={{ color: colors.textMid }}>Total Area</p>
                  <p className="text-xl font-bold" style={{ color: colors.textDark }}>{displayValue(userData.landSize, " acres")}</p>
                </div>
                <div className="p-4 rounded-lg" style={{ background: colors.cream }}>
                  <p className="text-sm" style={{ color: colors.textMid }}>Zones</p>
                  <p className="text-xl font-bold" style={{ color: colors.textDark }}>{cropZones.filter((zone) => isPresent(zone.crop)).length || EMPTY_DISPLAY}</p>
                </div>
                <div className="p-4 rounded-lg" style={{ background: colors.cream }}>
                  <p className="text-sm" style={{ color: colors.textMid }}>Active Sensors</p>
                  <p className="text-xl font-bold" style={{ color: colors.textDark }}>{userData.sensors}</p>
                </div>
                <div className="p-4 rounded-lg" style={{ background: colors.cream }}>
                  <p className="text-sm" style={{ color: colors.textMid }}>Irrigation Pumps</p>
                  <p className="text-xl font-bold" style={{ color: colors.textDark }}>{userData.pumps}</p>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Zone Details</h3>
              <div className="space-y-3">
                {[
                  { zone: "Zone A", crops: userData.zoneA, area: "", status: userData.zoneA ? "Active" : "" },
                  { zone: "Zone B", crops: userData.zoneB, area: "", status: userData.zoneB ? "Active" : "" },
                  { zone: "Zone C", crops: userData.zoneC, area: "", status: userData.zoneC ? "Active" : "" },
                ].map((zone) => (
                  <div key={zone.zone} className="flex items-center justify-between p-3 rounded-lg" style={{ background: colors.cream }}>
                    <div>
                      <p className="font-medium" style={{ color: colors.textDark }}>{zone.zone}</p>
                      <p className="text-sm" style={{ color: colors.textMid }}>{zone.crops} - {zone.area}</p>
                    </div>
                    <span className={`px-2 py-1 text-xs rounded-full ${zone.status === "Active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}`}>
                      {displayValue(zone.status)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

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
