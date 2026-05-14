import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Beaker,
  CheckCircle2,
  Cloud,
  Droplets,
  Flower2,
  Leaf,
  Loader2,
  RefreshCw,
  Sprout,
  Thermometer,
  TrendingUp,
  Wheat,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { API, authHeaders, csrfHeadersAsync, readSessionUser } from "../lib/api";

const EMPTY_DISPLAY = "--";
const toNumberOrNull = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};
const displayMetric = (value, suffix = "") => (value === null || value === undefined || value === "" ? EMPTY_DISPLAY : `${value}${suffix}`);

const normalizeSensorData = (value = {}) => ({
  moisture: toNumberOrNull(value.moisture ?? value.soilMoisture ?? value.soil_moisture),
  humidity: toNumberOrNull(value.humidity),
  temperature: toNumberOrNull(value.temperature),
  ph: toNumberOrNull(value.ph ?? value.soilPh ?? value.ph_level),
  nitrogen: toNumberOrNull(value.nitrogen),
  phosphorus: toNumberOrNull(value.phosphorus),
  potassium: toNumberOrNull(value.potassium),
});

const readProfile = async (request = fetch) => {
  const cachedUser = readSessionUser();
  const response = await request(`${API}/auth/profile`, {
    credentials: "include",
    headers: authHeaders(),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (cachedUser && [404, 405].includes(response.status)) return cachedUser;
    throw new Error(payload.detail || `Profile returned ${response.status}`);
  }
  return payload.user || {};
};

const readLatestSensors = async (deviceId, request = fetch) => {
  const response = await request(`${API}/sensors/latest?device_id=${encodeURIComponent(deviceId)}`, {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`Sensor API returned ${response.status}`);
  const data = await response.json();
  const readingMap = (data.readings || []).reduce((acc, reading) => {
    acc[reading.sensor_type] = reading.value;
    return acc;
  }, {});
  return {
    data: normalizeSensorData(readingMap),
    connection: {
      status: data.source === "esp32" ? "connected" : "unavailable",
      lastSeen: data.recorded_at,
      deviceId: data.device_id || deviceId,
      source: data.source || "unavailable",
      message: data.message || "",
    },
  };
};

const formatRange = (range, suffix = "") =>
  Array.isArray(range) && range.length >= 2 ? `${range[0]} - ${range[1]}${suffix}` : EMPTY_DISPLAY;

const missingReadings = (sensorData = {}) =>
  [
    ["soil_moisture", sensorData.moisture],
    ["humidity", sensorData.humidity],
    ["temperature", sensorData.temperature],
    ["ph", sensorData.ph],
    ["nitrogen", sensorData.nitrogen],
    ["phosphorus", sensorData.phosphorus],
    ["potassium", sensorData.potassium],
  ]
    .filter(([, value]) => value === null || value === undefined || value === "")
    .map(([name]) => name);

const hasCoreReadings = (sensorData = {}) =>
  [sensorData.moisture, sensorData.humidity, sensorData.temperature, sensorData.ph].every(
    (value) => value !== null && value !== undefined && value !== ""
  );

export default function CropPlanner({
  embedded = false,
  sensorData: dashboardSensorData,
  sensorConnection: dashboardSensorConnection,
  userProfile: dashboardUserProfile,
  protectedFetch,
}) {
  const [sensorData, setSensorData] = useState(() => normalizeSensorData(dashboardSensorData));
  const [sensorConnection, setSensorConnection] = useState({
    status: "loading",
    lastSeen: null,
    deviceId: "",
    source: "",
  });
  const [userProfile, setUserProfile] = useState(() => dashboardUserProfile || {});
  const [profileLoaded, setProfileLoaded] = useState(() => Boolean(dashboardUserProfile || dashboardSensorData));
  const [selectedGoal, setSelectedGoal] = useState("balanced");
  const [cropRecommendations, setCropRecommendations] = useState([]);
  const [summary, setSummary] = useState("");
  const [loadingSensors, setLoadingSensors] = useState(false);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  const [error, setError] = useState("");

  const acreage = Number(userProfile?.landSize || userProfile?.acreage || 0);
  const location = [userProfile?.village || userProfile?.city || userProfile?.location, userProfile?.district, userProfile?.state]
    .filter(Boolean)
    .join(", ");

  useEffect(() => {
    if (!dashboardUserProfile) return;
    setUserProfile(dashboardUserProfile);
    setProfileLoaded(true);
  }, [dashboardUserProfile]);

  useEffect(() => {
    if (!dashboardSensorData) return;
    setSensorData(normalizeSensorData(dashboardSensorData));
    setProfileLoaded(true);
    setSensorConnection({
      status: dashboardSensorConnection?.source === "esp32" ? "connected" : "unavailable",
      lastSeen: dashboardSensorConnection?.lastSeen,
      error: dashboardSensorConnection?.error,
      deviceId: dashboardSensorConnection?.deviceId,
      source: dashboardSensorConnection?.source,
    });
  }, [dashboardSensorData, dashboardSensorConnection]);

  const refreshSensors = useCallback(async () => {
    if (dashboardSensorData) return sensorConnection.deviceId || dashboardSensorConnection?.deviceId || userProfile?.sensorDeviceId || "";
    setLoadingSensors(true);
    setError("");
    try {
      const request = protectedFetch || fetch;
      const user = userProfile?.sensorDeviceId ? userProfile : await readProfile(request);
      const deviceId = user.sensorDeviceId || "";
      setUserProfile(user);
      setProfileLoaded(true);
      if (!deviceId) {
        setSensorData({});
        setSensorConnection({ status: "unavailable", error: "No sensor device configured", deviceId: "", source: "unavailable" });
        return "";
      }
      const latest = await readLatestSensors(deviceId, request);
      setSensorData(latest.data);
      setSensorConnection(latest.connection);
      return latest.connection.deviceId || deviceId;
    } catch (err) {
      setProfileLoaded(true);
      setError(`Could not load live sensor readings: ${err.message}`);
      setSensorConnection((prev) => ({ ...prev, status: "error", error: err.message }));
      return "";
    } finally {
      setLoadingSensors(false);
    }
  }, [dashboardSensorConnection?.deviceId, dashboardSensorData, protectedFetch, sensorConnection.deviceId, userProfile]);

  const loadRecommendations = useCallback(async (deviceIdOverride = "") => {
    const deviceId = deviceIdOverride || sensorConnection.deviceId || userProfile?.sensorDeviceId || "";
    if (!deviceId) {
      setCropRecommendations([]);
      setSummary(EMPTY_DISPLAY);
      setError("");
      return;
    }

    setLoadingRecommendations(true);
    setError("");
    try {
      const requestBody = JSON.stringify({
        goal: selectedGoal,
        language: localStorage.getItem("cropconnect-language") || "en",
        device_id: deviceId,
        sensor_source: sensorConnection.source || "",
      });
      const request = protectedFetch || fetch;
      let response = await request(`${API}/crops/recommend`, {
        method: "POST",
        credentials: "include",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
          ...(await csrfHeadersAsync()),
        },
        body: requestBody,
      });
      if (response.status === 403 && /csrf/i.test(await response.clone().text().catch(() => ""))) {
        response = await request(`${API}/crops/recommend`, {
          method: "POST",
          credentials: "include",
          headers: {
            ...authHeaders(),
            "Content-Type": "application/json",
            ...(await csrfHeadersAsync({ refresh: true })),
          },
          body: requestBody,
        });
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Crop AI returned ${response.status}`);
      if (data.sensor_context) {
        setSensorData(normalizeSensorData(data.sensor_context.sensor_data || {}));
        setSensorConnection((prev) => ({
          ...prev,
          status: data.sensor_context.source === "esp32" ? "connected" : "unavailable",
          lastSeen: data.sensor_context.recorded_at,
          deviceId: data.sensor_context.device_id || prev.deviceId,
          source: data.sensor_context.source || prev.source,
          message: data.sensor_context.message || "",
        }));
      }
      setCropRecommendations(data.crops || []);
      setSummary(data.summary || (data.source === "no_live_sensor_data" ? EMPTY_DISPLAY : ""));
    } catch (err) {
      setCropRecommendations([]);
      setSummary("");
      setError(err.message);
    } finally {
      setLoadingRecommendations(false);
    }
  }, [protectedFetch, selectedGoal, sensorConnection.deviceId, sensorConnection.source, userProfile?.sensorDeviceId]);

  useEffect(() => {
    refreshSensors();
    const interval = dashboardSensorData ? null : setInterval(refreshSensors, 30000);
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [dashboardSensorData, refreshSensors]);

  useEffect(() => {
    if (!profileLoaded) return;
    const deviceId = sensorConnection.deviceId || userProfile?.sensorDeviceId || "";
    if (!deviceId) {
      setCropRecommendations([]);
      setSummary(EMPTY_DISPLAY);
      setError("");
      return;
    }
    loadRecommendations();
  }, [
    profileLoaded,
    selectedGoal,
    sensorConnection.deviceId,
    userProfile?.sensorDeviceId,
    sensorData.moisture,
    sensorData.humidity,
    sensorData.temperature,
    sensorData.ph,
    loadRecommendations,
  ]);

  const suitableCrops = useMemo(
    () => cropRecommendations.filter((crop) => parseInt(crop.fit || "0", 10) >= 70),
    [cropRecommendations]
  );
  const bestCrop = cropRecommendations[0];
  const liveLabel = sensorConnection.status === "connected" ? "ESP32 live sensor" : "AI waiting for live sensor";
  const missing = missingReadings(sensorData);
  const planningGoals = [
    { id: "balanced", label: "Balanced", description: "Best agronomic fit for current readings" },
    { id: "money", label: "Money", description: "Cash crops and market-friendly choices" },
    { id: "organic", label: "Organic", description: "Crops suited to natural soil programs" },
    { id: "food", label: "Food", description: "Stable family-use and staple crops" },
  ];

  return (
    <div className={`${embedded ? "min-h-0" : "min-h-screen"} bg-gradient-to-br from-[#d8f3dc] via-[#95d5b2] to-[#40916c] p-3 sm:p-6`}>
      <div className="max-w-7xl mx-auto">
        {!embedded && (
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <Leaf className="w-8 h-8 text-green-700" />
              <h1 className="text-4xl font-bold text-gray-900">AI Crop Planner</h1>
            </div>
            <p className="text-gray-700">Live sensor readings go to the backend AI engine. No local crop table is used.</p>
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-semibold">AI planner needs attention</p>
                <p className="text-sm">{error}</p>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 bg-white/95 rounded-lg border border-green-200 shadow-lg p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Sprout className="w-5 h-5 text-green-700" />
                  <h2 className="text-2xl font-bold text-gray-900">AI recommendation engine</h2>
                </div>
                <p className="text-gray-600">The backend AI ranks crops from live farm readings, farm location and your planning goal.</p>
              </div>
              <Button
                type="button"
                onClick={async () => {
                  const refreshedDeviceId = await refreshSensors();
                  await loadRecommendations(refreshedDeviceId);
                }}
                disabled={loadingSensors || loadingRecommendations}
                className="bg-green-700 hover:bg-green-800 text-white"
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${loadingSensors || loadingRecommendations ? "animate-spin" : ""}`} />
                Refresh AI
              </Button>
            </div>

            <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-green-100 px-3 py-1.5 text-xs font-semibold text-green-800 ring-1 ring-green-200">
              <span className={`h-2 w-2 rounded-full ${sensorConnection.status === "connected" ? "bg-green-500" : "bg-amber-500"}`} />
              {liveLabel}
              {sensorConnection.deviceId ? <span data-no-translate="true"> - {sensorConnection.deviceId}</span> : null}
            </div>
            {missing.length > 0 && (
              <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                Missing readings: {missing.join(", ")}. The AI treats these as unknown, not zero.
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 bg-gradient-to-r from-green-100 via-emerald-100 to-lime-100 p-6 rounded-lg border border-green-200">
              <SensorMetric icon={Droplets} label="Moisture" value={displayMetric(sensorData.moisture, "%")} />
              <SensorMetric icon={Cloud} label="Humidity" value={displayMetric(sensorData.humidity, "%")} />
              <SensorMetric icon={Thermometer} label="Temperature" value={displayMetric(sensorData.temperature, "C")} />
              <SensorMetric icon={Beaker} label="pH" value={displayMetric(sensorData.ph)} />
            </div>

            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4 uppercase">Planning goal</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {planningGoals.map((goal) => (
                  <button
                    key={goal.id}
                    onClick={() => setSelectedGoal(goal.id)}
                    className={`p-3 rounded-lg border-2 text-left transition ${
                      selectedGoal === goal.id
                        ? "border-green-700 bg-green-100 shadow-sm"
                        : "border-green-200 bg-white hover:border-green-400 hover:bg-green-50"
                    }`}
                  >
                    <div className="font-semibold text-gray-900">{goal.label}</div>
                    <div className="text-xs text-gray-600">{goal.description}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="bg-gradient-to-br from-[#064e3b] via-[#087f5b] to-[#2b9348] rounded-lg shadow-lg p-6 text-white">
            <h3 className="text-sm font-semibold opacity-90 mb-2 uppercase">Best AI option</h3>
            {loadingRecommendations ? (
              <div className="flex items-center gap-2 py-10">
                <Loader2 className="h-5 w-5 animate-spin" />
                Asking AI...
              </div>
            ) : bestCrop ? (
              <>
                <h2 className="text-4xl font-bold mb-1" data-dynamic-value="true">{bestCrop.name}</h2>
                <div className="text-sm opacity-90 mb-6" data-dynamic-value="true">{bestCrop.category}</div>
                <div className="bg-white bg-opacity-20 rounded-lg p-4 mb-6">
                  <div className="text-5xl font-bold mb-2" data-dynamic-value="true">{bestCrop.fit}</div>
                  <div className="text-sm font-semibold">AI fit</div>
                </div>
                <p className="text-sm mb-4" data-dynamic-value="true">{bestCrop.description}</p>
                <div className="bg-white bg-opacity-10 rounded-lg p-4 mb-6">
                  <div className="text-sm font-semibold mb-2">Suitable crops</div>
                  <div className="text-3xl font-bold">{suitableCrops.length}</div>
                  <div className="text-sm opacity-90 mt-2">Farm acreage</div>
                  <div className="text-2xl font-bold">{acreage || "Profile missing"}</div>
                </div>
                <p className="text-xs opacity-75" data-dynamic-value="true">{summary || bestCrop.status_message}</p>
              </>
            ) : (
              <p className="text-sm opacity-85">{hasCoreReadings(sensorData) ? "No AI recommendation yet. Refresh AI." : EMPTY_DISPLAY}</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {loadingRecommendations
            ? Array.from({ length: 6 }).map((_, index) => <CropSkeleton key={index} />)
            : cropRecommendations.map((crop, index) => <CropCard key={`${crop.name}-${index}`} crop={crop} />)}
        </div>

        {!loadingRecommendations && cropRecommendations.length === 0 && (
          <div className="rounded-lg border border-green-200 bg-white/90 p-8 text-center text-gray-600">
            <span data-dynamic-value="true">{hasCoreReadings(sensorData) ? (summary || EMPTY_DISPLAY) : EMPTY_DISPLAY}</span>
          </div>
        )}

        {!loadingRecommendations && cropRecommendations.length > 0 && (
          <div className="mt-12 grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SeasonPanel title="Kharif crops" icon={Sprout} crops={suitableCrops.filter((crop) => crop.season === "Kharif")} />
            <SeasonPanel title="Rabi crops" icon={Wheat} crops={suitableCrops.filter((crop) => crop.season === "Rabi")} />
          </div>
        )}
      </div>
    </div>
  );
}

function SensorMetric({ icon: Icon, label, value }) {
  return (
    <div className="text-center rounded-lg bg-white/80 p-3 border border-green-100">
      <div className="flex items-center justify-center mb-2">
        <Icon className="w-5 h-5 text-green-700" />
      </div>
      <div className="text-lg font-bold text-gray-900" data-dynamic-value="true">{value}</div>
      <div className="text-xs text-green-800 uppercase tracking-wide">{label}</div>
    </div>
  );
}

function CropCard({ crop }) {
  const fitValue = parseInt(crop.fit || "0", 10);
  return (
    <div className="bg-white/95 rounded-lg border border-green-200 shadow p-6 hover:shadow-lg hover:border-green-400 transition">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-bold text-gray-900" data-dynamic-value="true">{crop.name}</h3>
          <p className="text-sm text-gray-600" data-dynamic-value="true">{crop.category}</p>
        </div>
        <div className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-semibold" data-dynamic-value="true">{crop.fit}</div>
      </div>

      <div className="mb-4">
        <div className="w-full bg-green-100 rounded-full h-2">
          <div className="bg-gradient-to-r from-green-500 to-emerald-700 h-2 rounded-full transition" style={{ width: `${Math.min(100, Math.max(0, fitValue))}%` }} />
        </div>
      </div>

      <div className="space-y-3 mb-4 text-sm">
        <RangeRow label="Moisture" value={formatRange(crop.moisture_range, "%")} />
        <RangeRow label="Temperature" value={formatRange(crop.temp_range, "C")} />
        <RangeRow label="Humidity" value={formatRange(crop.humidity_range, "%")} />
        <RangeRow label="pH" value={formatRange(crop.ph_range)} />
      </div>

      <p className="text-sm text-gray-700 mb-4" data-dynamic-value="true">{crop.description}</p>
      <div className="bg-green-50 border-l-4 border-green-500 p-3 rounded text-sm">
        <div className="flex items-start gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
          <span className="text-gray-700" data-dynamic-value="true">{crop.status_message || "AI recommendation generated from live context."}</span>
        </div>
      </div>
    </div>
  );
}

function RangeRow({ label, value }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-gray-600">{label}:</span>
      <span className="font-semibold text-right" data-dynamic-value="true">{value}</span>
    </div>
  );
}

function SeasonPanel({ title, icon: Icon, crops }) {
  return (
    <div className="bg-white/95 rounded-lg shadow-lg p-6 border-t-4 border-green-600">
      <h3 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
        <Icon className="w-6 h-6 text-green-600" />
        {title}
      </h3>
      <div className="space-y-2">
        {crops.length ? (
          crops.map((crop) => (
            <div key={crop.name} className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
              <div>
                <p className="font-semibold text-gray-900" data-dynamic-value="true">{crop.name}</p>
                <p className="text-xs text-gray-600" data-dynamic-value="true">{crop.cropType || crop.category}</p>
              </div>
              <div className="bg-green-200 text-green-800 px-3 py-1 rounded-full text-sm font-semibold" data-dynamic-value="true">{crop.fit}</div>
            </div>
          ))
        ) : (
          <p className="text-gray-500 text-sm italic">AI did not rank any crops in this season for current readings.</p>
        )}
      </div>
    </div>
  );
}

function CropSkeleton() {
  return (
    <div className="bg-white/80 rounded-lg border border-green-100 shadow p-6">
      <div className="h-6 w-1/2 bg-green-100 rounded mb-3" />
      <div className="h-3 w-1/3 bg-green-50 rounded mb-6" />
      <div className="h-2 w-full bg-green-100 rounded mb-5" />
      <div className="space-y-3">
        <div className="h-3 bg-green-50 rounded" />
        <div className="h-3 bg-green-50 rounded" />
        <div className="h-3 bg-green-50 rounded" />
      </div>
    </div>
  );
}
