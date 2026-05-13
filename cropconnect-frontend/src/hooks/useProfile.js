// Owns authenticated farmer profile loading, editing state, and persistence.
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { API } from "../lib/api";

export const normalizeUserProfile = (user = {}) => ({
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

const humanizeApiValue = (value, fallback = "") => {
  if (value == null || value === "") return fallback;
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map((item) => humanizeApiValue(item)).filter(Boolean).join("\n");
  if (typeof value === "object") {
    if (typeof value.msg === "string") return value.msg;
    if (typeof value.message === "string") return value.message;
    if (typeof value.detail === "string") return value.detail;
    return JSON.stringify(value, null, 2);
  }
  return String(value);
};

/**
 * Loads and persists the authenticated farmer profile.
 * @param {Function} protectedFetch Authenticated fetch helper.
 * @returns {object} Profile state and persistence actions.
 */
export function useProfile(protectedFetch) {
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
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [editData, setEditData] = useState({});
  const [userLoaded, setUserLoaded] = useState(false);
  const [sensorSetupForm, setSensorSetupForm] = useState({
    deviceId: "",
    nodeCount: "1",
  });

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

  const saveUserToMysql = useCallback(async (updates) => {
    const response = await protectedFetch(`${API}/auth/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...updates }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not save data in MySQL");
    }

    return payload.user;
  }, [protectedFetch]);

  return {
    userData,
    setUserData,
    isEditingProfile,
    setIsEditingProfile,
    editData,
    setEditData,
    userLoaded,
    sensorSetupForm,
    setSensorSetupForm,
    saveUserToMysql,
  };
}
