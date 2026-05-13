// Owns weather location derivation and live forecast loading state.
import { useCallback, useEffect, useState } from "react";
import { API } from "../lib/api";

/**
 * Polls forecast data for the current profile location.
 * @param {object} userData Farmer profile data.
 * @returns {object} Weather state and derived location helper.
 */
export function useWeatherData(userData) {
  const [weatherData, setWeatherData] = useState(null);
  const [weatherError, setWeatherError] = useState("");

  const getUserWeatherLocation = useCallback(() => {
    const place = userData.locationType === "village"
      ? userData.village || userData.city
      : userData.city || userData.village;
    return [place, userData.district, userData.state].filter(Boolean).join(", ");
  }, [userData.city, userData.district, userData.locationType, userData.state, userData.village]);

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

  return { weatherData, setWeatherData, weatherError, setWeatherError, getUserWeatherLocation };
}
