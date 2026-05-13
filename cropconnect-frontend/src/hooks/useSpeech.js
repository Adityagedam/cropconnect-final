// Owns browser speech-recognition setup and listening controls.
import { useEffect, useState } from "react";
import { toast } from "sonner";

/**
 * Creates and controls browser speech recognition for multilingual chat input.
 * @param {object} options Hook dependencies.
 * @returns {object} Speech state and controls.
 */
export function useSpeech({ language, languages, onTranscript, detectLanguage }) {
  const [isListening, setIsListening] = useState(false);
  const [speechRecognition, setSpeechRecognition] = useState(null);

  const getSpeechLangCode = (langCode) => {
    const langMap = {
      en: "en-US",
      hi: "hi-IN",
      mr: "mr-IN",
      te: "te-IN",
      ta: "ta-IN",
      kn: "kn-IN",
      bn: "bn-IN",
    };
    return langMap[langCode] || "en-US";
  };

  useEffect(() => {
    if (typeof window !== "undefined" && "webkitSpeechRecognition" in window) {
      const recognition = new window.webkitSpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = getSpeechLangCode(language);

      recognition.onstart = () => {
        setIsListening(true);
        const selectedLangName = languages.find((item) => item.code === language)?.name || language;
        toast.info(`Listening... Speak your question in ${selectedLangName}`);
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const detectedLang = detectLanguage(transcript);
        onTranscript(transcript, detectedLang);
      };

      recognition.onerror = (event) => {
        toast.error(event.error === "no-speech" ? "No speech detected. Please try again." : `Speech recognition failed: ${event.error}`);
        setIsListening(false);
      };
      recognition.onend = () => setIsListening(false);
      setSpeechRecognition(recognition);
    }
  }, [detectLanguage, language, languages, onTranscript]);

  const startListening = () => {
    if (speechRecognition && !isListening) {
      speechRecognition.lang = getSpeechLangCode(language);
      speechRecognition.start();
    } else if (!speechRecognition) {
      toast.error("Speech recognition not supported in your browser. Try Chrome, Edge, or Safari.");
    }
  };

  const stopListening = () => {
    if (speechRecognition && isListening) speechRecognition.stop();
  };

  return { isListening, speechRecognition, getSpeechLangCode, startListening, stopListening };
}
