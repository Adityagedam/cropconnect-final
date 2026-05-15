// Owns pump desired/applied state, timers, and pump command actions.
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { API } from "../lib/api";

/**
 * Manages irrigation pump state and timer persistence.
 * @param {object} options Hook dependencies.
 * @returns {object} Pump state and actions.
 */
export function usePumpControl({ protectedFetch, userLoaded, sensorConnection, sensorDeviceId, pollIntervalMs }) {
  const [pumps, setPumps] = useState({
    pump1: { on: false, appliedOn: null, hardwareConfirmed: false, runtime: 0, schedule: {} },
    pump2: { on: false, appliedOn: null, hardwareConfirmed: false, runtime: 0, schedule: {} },
  });
  const [pumpUpdating, setPumpUpdating] = useState({});
  const [pumpControlMode, setPumpControlMode] = useState(() => localStorage.getItem("cropconnect-pump-control-mode") || "direct");
  const [pumpDirectHost, setPumpDirectHost] = useState(() => localStorage.getItem("cropconnect-pump-esp32-host") || "");
  const [scheduledTimers, setScheduledTimers] = useState({ pump1: [], pump2: [] });
  const [showTimerModal, setShowTimerModal] = useState({ show: false, pump: null });
  const [newTimer, setNewTimer] = useState({ hour: "", minute: "00", period: "AM", duration: "", days: [] });
  const pumpsRef = useRef(pumps);

  useEffect(() => {
    pumpsRef.current = pumps;
  }, [pumps]);

  useEffect(() => {
    localStorage.setItem("cropconnect-pump-control-mode", pumpControlMode);
  }, [pumpControlMode]);

  useEffect(() => {
    localStorage.setItem("cropconnect-pump-esp32-host", pumpDirectHost.trim());
  }, [pumpDirectHost]);

  const pumpCommandUrl = useCallback((pumpId, nextOn) => {
    const relayNumber = pumpId === "pump2" ? 2 : 1;
    const command = `${relayNumber}${nextOn ? "on" : "off"}`;
    const cleanedHost = pumpDirectHost.trim().replace(/^https?:\/\//i, "").replace(/\/+$/g, "");
    if (!cleanedHost) throw new Error("Add the pump ESP32 IP address first");
    return `http://${cleanedHost}/${command}`;
  }, [pumpDirectHost]);

  const sendDirectPumpCommand = useCallback(async (pumpId, nextOn) => {
    const url = pumpCommandUrl(pumpId, nextOn);
    try {
      await fetch(url, { method: "GET", mode: "no-cors", cache: "no-store" });
      return { message: `Direct command sent to pump ESP32 at ${url}`, usedBrowserFallback: false };
    } catch {
      const beacon = new Image();
      beacon.src = `${url}?t=${Date.now()}`;
      window.open(url, "_blank", "noopener,noreferrer");
      return { message: `Opened direct pump URL: ${url}`, usedBrowserFallback: true };
    }
  }, [pumpCommandUrl]);

  const saveTimersToMysql = useCallback(async (nextTimers) => {
    const response = await protectedFetch(`${API}/farm/timers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timers: nextTimers }),
    });
    if (!response.ok) throw new Error("Could not save timers");
  }, [protectedFetch]);

  const updatePumpState = useCallback(async (pumpId, nextOn, pumpOverride = null) => {
    const pump = pumpOverride || pumpsRef.current[pumpId] || {};
    const response = await protectedFetch(`${API}/pump/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pump_id: pumpId,
        on: nextOn,
        device_id: sensorConnection.deviceId || sensorDeviceId || "",
        runtime: pump.runtime || 0,
        schedule: pump.schedule || {},
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not update pump state");
    return data;
  }, [protectedFetch, sensorConnection.deviceId, sensorDeviceId]);

  const togglePump = useCallback(async (pumpId) => {
    const nextOn = !pumpsRef.current[pumpId].on;
    const pumpName = pumpId === "pump1" ? "Pump 1" : "Pump 2";
    setPumpUpdating((prev) => ({ ...prev, [pumpId]: true }));
    try {
      const data = pumpControlMode === "direct"
        ? await sendDirectPumpCommand(pumpId, nextOn)
        : await updatePumpState(pumpId, nextOn);
      setPumps((prev) => ({
        ...prev,
        [pumpId]: {
          ...prev[pumpId],
          on: nextOn,
          appliedOn: pumpControlMode === "direct" ? nextOn : prev[pumpId].appliedOn,
          hardwareConfirmed: pumpControlMode === "direct",
          runtime: nextOn ? 0 : prev[pumpId].runtime,
        },
      }));
      const stateText = nextOn ? "ON" : "OFF";
      if (pumpControlMode === "direct" && data.usedBrowserFallback) toast.info(data.message);
      else if (pumpControlMode === "direct") toast.success(`${pumpName} ${stateText} command sent directly to ESP32`);
      else if (data.sent_to_esp32) toast.success(`${pumpName} turned ${stateText} through ESP32`);
      else toast.info(data.message || `${pumpName} command queued for SIM800L`);
    } catch (error) {
      toast.error(error.message || "Could not reach pump controller");
    } finally {
      setPumpUpdating((prev) => ({ ...prev, [pumpId]: false }));
    }
  }, [pumpControlMode, sendDirectPumpCommand, updatePumpState]);

  useEffect(() => {
    if (!userLoaded || pumpControlMode === "direct") return undefined;
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
        // Auth and sensor hooks surface connection failures.
      }
    };

    loadPumpStates();
    const interval = setInterval(loadPumpStates, pollIntervalMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollIntervalMs, protectedFetch, pumpControlMode, userLoaded]);

  return {
    pumps,
    setPumps,
    pumpsRef,
    pumpUpdating,
    setPumpUpdating,
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
    updatePumpState,
    togglePump,
  };
}
