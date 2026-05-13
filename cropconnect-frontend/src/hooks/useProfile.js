// Owns authenticated farmer profile loading, editing state, and persistence.
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { API, readSessionUser, storeSessionUser } from "../lib/api";

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
  const cachedUser = readSessionUser();
  const [userData, setUserData] = useState(() => cachedUser ? normalizeUserProfile(cachedUser) : {
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
  const [userLoaded, setUserLoaded] = useState(() => Boolean(cachedUser));
  const [sensorSetupForm, setSensorSetupForm] = useState({
    deviceId: "",
    nodeCount: "1",
  });
  const [setupChecking, setSetupChecking] = useState(false);
  const [setupCheckResult, setSetupCheckResult] = useState(null);
  const [sensorApiKey, setSensorApiKey] = useState("");
  const [sensorApiKeyLoading, setSensorApiKeyLoading] = useState(false);
  const [sensorApiKeyError, setSensorApiKeyError] = useState("");

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
        storeSessionUser(normalizedUser);
        setSensorSetupForm((prev) => ({
          ...prev,
          deviceId: normalizedUser.sensorDeviceId || prev.deviceId,
          nodeCount: normalizedUser.sensors || prev.nodeCount,
        }));
      } catch (error) {
        const fallbackUser = readSessionUser();
        if (!cancelled && fallbackUser && /405|404|profile/i.test(error.message || "")) {
          const normalizedUser = normalizeUserProfile(fallbackUser);
          setUserData(normalizedUser);
          setSensorSetupForm((prev) => ({
            ...prev,
            deviceId: normalizedUser.sensorDeviceId || prev.deviceId,
            nodeCount: normalizedUser.sensors || prev.nodeCount,
          }));
        } else if (!cancelled && error.message !== "Login expired") {
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
      body: JSON.stringify({ user_id: userData.id, email: userData.email, ...updates }),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "Could not save data in MySQL");
    }

    if (payload.user) storeSessionUser(payload.user);
    return payload.user;
  }, [protectedFetch, userData.email, userData.id]);

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
  };
}
