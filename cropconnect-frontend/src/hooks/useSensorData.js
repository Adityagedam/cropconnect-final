// Owns sensor readings, connection status, telemetry packet shaping, and polling.
import { useCallback, useEffect, useState } from "react";
import { API } from "../lib/api";

export const initialSensorData = {
  soilMoisture: null,
  temperature: null,
  humidity: null,
  soilPh: null,
  nitrogen: null,
  phosphorus: null,
  potassium: null,
};

/**
 * Polls latest sensor readings and maps backend payloads into dashboard state.
 * @param {object} options Hook dependencies.
 * @returns {object} Sensor state and payload mapping actions.
 */
export function useSensorData({ protectedFetch, sensorDeviceId, pollIntervalMs }) {
  const [sensorData, setSensorData] = useState(initialSensorData);
  const [sensorConnection, setSensorConnection] = useState({
    source: "unavailable",
    deviceId: "",
    lastSeen: null,
    error: null,
  });
  const [telemetryPacket, setTelemetryPacket] = useState({});

  const applyBackendReadings = useCallback((payload) => {
    const readings = Array.isArray(payload?.readings) ? payload.readings : [];
    if (!readings.length) {
      if (payload && !Array.isArray(payload?.readings)) {
        console.warn("Unexpected sensor payload format:", payload);
      }
      setSensorData(initialSensorData);
      setSensorConnection({
        source: "unavailable",
        deviceId: payload?.device_id || sensorDeviceId || "",
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
        deviceId: payload.device_id || sensorDeviceId || "",
        lastSeen: payload.recorded_at || null,
        error: payload.message || "Latest ESP32 packet had no sensor readings",
      });
      return false;
    }

    setSensorData(updatedData);
    setSensorConnection({
      source: payload.source === "esp32" ? "esp32" : "unavailable",
      deviceId: payload.device_id || sensorDeviceId || "",
      lastSeen: payload.recorded_at || new Date().toISOString(),
      error: null,
    });

    return true;
  }, [sensorDeviceId]);

  useEffect(() => {
    let cancelled = false;
    const primaryDeviceId = sensorDeviceId || "";

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
        const response = await protectedFetch(`${API}/sensors/latest?device_id=${encodeURIComponent(primaryDeviceId)}`);
        if (!response.ok) throw new Error(`Backend returned ${response.status}`);
        const payload = await response.json();
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
            deviceId: primaryDeviceId,
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
    const interval = setInterval(loadLatestReadings, pollIntervalMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [applyBackendReadings, pollIntervalMs, protectedFetch, sensorDeviceId]);

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

  return {
    sensorData,
    setSensorData,
    sensorConnection,
    setSensorConnection,
    telemetryPacket,
    applyBackendReadings,
  };
}
