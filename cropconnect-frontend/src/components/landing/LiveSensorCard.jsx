import { useEffect, useMemo, useState } from "react";
import {
  Droplets,
  Thermometer,
  CloudRain,
  FlaskConical,
  Sun,
  Zap,
} from "lucide-react";
import { API } from "../../lib/api";

const META = {
  soil_moisture: { label: "Soil moisture", icon: Droplets, accent: "#1B4332" },
  temperature: { label: "Temperature", icon: Thermometer, accent: "#E07A5F" },
  humidity: { label: "Humidity", icon: CloudRain, accent: "#2D6A4F" },
  ph: { label: "Soil pH", icon: FlaskConical, accent: "#52796F" },
  light: { label: "Light", icon: Sun, accent: "#C97B5C" },
  ec: { label: "Conductivity", icon: Zap, accent: "#1B4332" },
};

const ORDER = ["soil_moisture", "temperature", "humidity", "ph"];
const DEMO_READINGS = [
  { sensor_type: "soil_moisture", value: 42, unit: "%" },
  { sensor_type: "temperature", value: 28, unit: "C" },
  { sensor_type: "humidity", value: 64, unit: "%" },
  { sensor_type: "ph", value: 6.7, unit: "" },
];

export default function LiveSensorCard() {
  const [sensorPayload, setSensorPayload] = useState({
    device_id: "",
    source: "unavailable",
    readings: [],
    recorded_at: null,
    message: "",
  });

  useEffect(() => {
    let cancelled = false;

    const loadLatestPublicSensor = async () => {
      try {
        const response = await fetch(`${API}/public/sensors/latest`);
        const payload = await response.json().catch(() => ({}));
        if (cancelled) return;
        if (!response.ok) {
          setSensorPayload({
            device_id: "",
            source: "unavailable",
            readings: [],
            recorded_at: null,
            message: payload.detail || "Sensor data unavailable",
          });
          return;
        }
        setSensorPayload({
          device_id: payload.device_id || "",
          source: payload.source || "unavailable",
          readings: Array.isArray(payload.readings) ? payload.readings : [],
          recorded_at: payload.recorded_at || null,
          message: payload.message || "",
        });
      } catch {
        if (!cancelled) {
          setSensorPayload({
            device_id: "",
            source: "unavailable",
            readings: [],
            recorded_at: null,
            message: "Sensor data unavailable",
          });
        }
      }
    };

    loadLatestPublicSensor();
    const intervalId = window.setInterval(loadLatestPublicSensor, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  const visible = useMemo(() => {
    const readings = Array.isArray(sensorPayload.readings) ? sensorPayload.readings : [];
    const sourceReadings = readings.length ? readings : DEMO_READINGS;
    return ORDER
      .map((sensorType) => sourceReadings.find((reading) => reading.sensor_type === sensorType))
      .filter(Boolean);
  }, [sensorPayload.readings]);
  const hasPublicReadings = Array.isArray(sensorPayload.readings) && sensorPayload.readings.length > 0;
  const isLive = sensorPayload.source === "esp32" && hasPublicReadings;
  const updatedAt = sensorPayload.recorded_at
    ? new Date(sensorPayload.recorded_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "demo";

  return (
    <div
      data-testid="live-sensor-card"
      className="bg-white/95 backdrop-blur-md border border-[#D5D1C5] rounded-2xl p-5 shadow-[0_20px_60px_-25px_rgba(15,42,31,0.35)]"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {isLive && <span className="live-dot" />}
          <span className="eyebrow">{isLive ? "Live sensor node" : "Demo field snapshot"}</span>
        </div>
        <span className="font-mono text-[10px] text-[#1A201C]/50" data-testid="sensor-updated-at">
          {updatedAt}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {visible.map((reading) => {
          const meta = META[reading.sensor_type] || { label: reading.sensor_type, icon: Droplets, accent: "#1B4332" };
          const Icon = meta.icon;
          return (
            <div
              key={reading.sensor_type}
              data-testid={`sensor-${reading.sensor_type}`}
              className="rounded-xl border border-[#E8E4D7] bg-[#FDFBF7] p-3"
            >
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-white"
                  style={{ backgroundColor: meta.accent }}
                >
                  <Icon className="w-3.5 h-3.5" />
                </span>
                <span className="text-[11px] uppercase tracking-wider text-[#1A201C]/60 font-semibold">
                  {meta.label}
                </span>
              </div>
              <div className="flex items-baseline gap-1">
                <span
                  className="font-display text-2xl text-[#1A201C]"
                  data-testid={`sensor-${reading.sensor_type}-value`}
                >
                  {reading.value ?? "pending"}
                </span>
                <span className="text-xs text-[#1A201C]/60">{reading.value == null ? "" : reading.unit}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 pt-3 border-t border-dashed border-[#D5D1C5] flex items-center justify-between text-[11px] text-[#1A201C]/60">
        <span className="font-mono">device: {sensorPayload.device_id || "ESP32-DEMO-01"}</span>
        <span>{isLive ? "latest MySQL ESP32 reading" : "sample values until public sensor is connected"}</span>
      </div>
    </div>
  );
}
