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
  const [scheduledTimers, setScheduledTimers] = useState({ pump1: [], pump2: [] });
  const [showTimerModal, setShowTimerModal] = useState({ show: false, pump: null });
  const [newTimer, setNewTimer] = useState({ hour: "", minute: "00", period: "AM", duration: "", days: [] });
  const pumpsRef = useRef(pumps);

  useEffect(() => {
    pumpsRef.current = pumps;
  }, [pumps]);

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
      if (data.sent_to_esp32) toast.success(`${pumpName} turned ${stateText} through ESP32`);
      else toast.info(data.message || `${pumpName} command queued for SIM800L`);
    } catch (error) {
      toast.error(error.message || "Could not reach pump controller");
    } finally {
      setPumpUpdating((prev) => ({ ...prev, [pumpId]: false }));
    }
  }, [updatePumpState]);

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
        // Auth and sensor hooks surface connection failures.
      }
    };

    loadPumpStates();
    const interval = setInterval(loadPumpStates, pollIntervalMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollIntervalMs, protectedFetch, userLoaded]);

  return {
    pumps,
    setPumps,
    pumpsRef,
    pumpUpdating,
    setPumpUpdating,
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
