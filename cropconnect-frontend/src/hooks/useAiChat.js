// Owns AI chat messages, suggestions, typing state, and send behavior.
import { useCallback, useState } from "react";
import { API } from "../lib/api";

/**
 * Manages AI assistant conversation state.
 * @param {object} options Hook dependencies.
 * @returns {object} Chat state and handlers.
 */
export function useAiChat({ protectedFetch, language, sensorConnection, sensorDeviceId, humanizeApiValue, detectLanguage }) {
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);

  const handleSendMessage = useCallback(async (messageOverride, responseKeyOverride = null, detectedLanguage = null) => {
    void responseKeyOverride;
    const messageText = (messageOverride ?? chatInput).trim();
    if (!messageText) return;
    const inputLanguage = detectedLanguage || detectLanguage(messageText);
    setChatMessages((prev) => [...prev, { id: Date.now(), type: "user", text: messageText }]);
    setChatInput("");
    setShowSuggestions(false);
    setIsTyping(true);
    try {
      const response = await protectedFetch(`${API}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          language,
          input_language: inputLanguage,
          device_id: sensorConnection.deviceId || sensorDeviceId || "",
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
      setChatMessages((prev) => [...prev, { id: Date.now() + 1, type: "bot", text: responseText, relatedToPlantOrSoil: payload.related_to_plant_or_soil }]);
    } catch (error) {
      if (error.message !== "Login required" && error.message !== "Login expired") {
        setChatMessages((prev) => [...prev, { id: Date.now() + 1, type: "bot", text: error.message || "AI chatbot is unavailable." }]);
      }
    } finally {
      setIsTyping(false);
    }
  }, [chatInput, chatMessages, detectLanguage, humanizeApiValue, language, protectedFetch, sensorConnection.deviceId, sensorDeviceId]);

  const handleSuggestionClick = useCallback((suggestion, suggestionKey) => {
    handleSendMessage(suggestion, suggestionKey);
  }, [handleSendMessage]);

  return {
    chatMessages,
    setChatMessages,
    chatInput,
    setChatInput,
    isTyping,
    showSuggestions,
    setShowSuggestions,
    handleSendMessage,
    handleSuggestionClick,
  };
}
