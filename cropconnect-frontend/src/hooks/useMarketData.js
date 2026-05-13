// Owns live mandi prices and AI market insight loading state.
import { useCallback, useState } from "react";
import { API } from "../lib/api";

/**
 * Loads market prices and market insights for the authenticated farmer.
 * @param {object} options Hook dependencies.
 * @returns {object} Market data state and load actions.
 */
export function useMarketData({ protectedFetch, language, userLoaded, userState, getUserMarketLocation, marketFriendlyError, emptyMarketData }) {
  const [marketData, setMarketData] = useState(emptyMarketData);
  const [marketError, setMarketError] = useState("");
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketInsight, setMarketInsight] = useState(null);
  const [marketInsightError, setMarketInsightError] = useState("");
  const [marketInsightLoading, setMarketInsightLoading] = useState(false);

  const loadMarketPrices = useCallback(async (isCancelled = () => false) => {
    if (!userLoaded) return;
    const locationName = getUserMarketLocation();
    if (!userState) {
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
      if (!response.ok) throw new Error(marketFriendlyError(payload.detail || `Market prices returned ${response.status}`));
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
  }, [emptyMarketData, getUserMarketLocation, marketFriendlyError, protectedFetch, userLoaded, userState]);

  const loadMarketInsight = useCallback(async () => {
    if (!userLoaded) return;
    setMarketInsightLoading(true);
    setMarketInsightError("");
    try {
      const response = await protectedFetch(`${API}/market/insights`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          language,
          objective: "Analyze live mandi records for this user's location and give cautious selling guidance.",
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(marketFriendlyError(payload.detail || `AI market insight returned ${response.status}`));
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
  }, [emptyMarketData, language, marketFriendlyError, protectedFetch, userLoaded]);

  return {
    marketData,
    setMarketData,
    marketError,
    setMarketError,
    marketLoading,
    marketInsight,
    setMarketInsight,
    marketInsightError,
    setMarketInsightError,
    marketInsightLoading,
    loadMarketPrices,
    loadMarketInsight,
  };
}
