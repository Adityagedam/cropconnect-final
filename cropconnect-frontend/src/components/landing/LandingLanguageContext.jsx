import { createContext, useCallback, useContext, useMemo, useRef, useState, useEffect } from "react";
import axios from "axios";
import { translations } from "../../lib/translations";
import { API } from "../../lib/api";
import { publicTranslationEnabled } from "../LanguageSelect";

const LanguageContext = createContext(null);

const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "INPUT", "SELECT", "OPTION", "CODE", "PRE"]);
const TRANSLATABLE_ATTRIBUTES = ["placeholder", "title", "aria-label"];
const BRAND_TEXT = new Set(["CropConnect", "Crop", "Connect"]);
const TRANSLATION_CACHE_MAX_ITEMS = 500;
const TRANSLATION_BATCH_MAX_ITEMS = 35;
const TRANSLATION_BATCH_MAX_CHARS = 10_000;
const TRANSLATION_CACHE_STORAGE_KEY = "cropconnect-cache-v2";
const TRANSLATION_FALLBACK_URL = (import.meta.env.VITE_PUBLIC_TRANSLATION_FALLBACK_URL || "").trim().replace(/\/+$/, "");
const AUTO_TRANSLATE_ROOT = "[data-auto-translate-root='true'], [data-public-translate-root='true']";
const SKIP_TRANSLATE_SELECTOR = [
  "[data-no-translate='true']",
  "[data-private='true']",
  "[data-dynamic-value='true']",
  "[translate='no']",
  ".font-mono",
].join(", ");

const looksPrivateOrDynamic = (text) => {
  const value = String(text || "").trim();
  if (!value) return false;
  return (
    /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(value) ||
    /https?:\/\//i.test(value) ||
    /\b(?:Bearer|X-API-Key|api_key|password|token)\b/i.test(value) ||
    /\bccdev_[A-Za-z0-9_-]+\b/i.test(value) ||
    /\bcc_[A-Za-z0-9_-]{12,}\b/i.test(value) ||
    /\b[A-Za-z0-9_-]{28,}\b/.test(value)
  );
};

const shouldTranslateText = (text) => {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  if (!value || value.length < 2) return false;
  if (BRAND_TEXT.has(value)) return false;
  if (looksPrivateOrDynamic(value)) return false;
  if (/^[\d\s.,:%/+\u00b0-]+$/.test(value)) return false;
  return /[A-Za-z]/.test(value);
};

const boundedLanguageCache = (entries = {}) =>
  Object.fromEntries(Object.entries(entries).slice(-TRANSLATION_CACHE_MAX_ITEMS));

const mergeTranslationCache = (existingCache, targetLang, additions) => ({
  ...existingCache,
  [targetLang]: boundedLanguageCache({
    ...(existingCache[targetLang] || {}),
    ...additions,
  }),
});

const chunkTranslationTexts = (texts = []) => {
  const chunks = [];
  let current = [];
  let currentCharacters = 0;

  texts.forEach((text) => {
    const characters = String(text || "").length;
    if (!text) return;
    if (
      current.length >= TRANSLATION_BATCH_MAX_ITEMS ||
      (current.length > 0 && currentCharacters + characters > TRANSLATION_BATCH_MAX_CHARS)
    ) {
      chunks.push(current);
      current = [];
      currentCharacters = 0;
    }
    current.push(text);
    currentCharacters += characters;
  });

  if (current.length) chunks.push(current);
  return chunks;
};

const readTranslatedItems = (data, sourceTexts) => {
  if (Array.isArray(data?.translations)) return data.translations.map((item) => String(item || ""));
  if (Array.isArray(data?.translatedText)) return data.translatedText.map((item) => String(item || ""));
  if (typeof data?.translated === "string" && sourceTexts.length === 1) return [data.translated];
  if (typeof data?.translatedText === "string" && sourceTexts.length === 1) return [data.translatedText];
  return null;
};

const translateWithFallbackEndpoint = async (texts, targetLang) => {
  if (!TRANSLATION_FALLBACK_URL || !texts?.length) return null;

  try {
    const compatibleResponse = await axios.post(TRANSLATION_FALLBACK_URL, {
      texts,
      target_lang: targetLang,
    });
    const compatibleItems = readTranslatedItems(compatibleResponse.data, texts);
    if (compatibleItems?.length === texts.length) return compatibleItems;
  } catch {
    // Try a LibreTranslate-style payload next.
  }

  try {
    const libreResponse = await axios.post(TRANSLATION_FALLBACK_URL, {
      q: texts,
      source: "auto",
      target: targetLang,
      format: "text",
    });
    const libreItems = readTranslatedItems(libreResponse.data, texts);
    if (libreItems?.length === texts.length) return libreItems;
  } catch {
    return null;
  }

  return null;
};

const nearestSkipsTranslation = (node) => {
  const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
  if (!element) return true;
  if (SKIP_TAGS.has(element.tagName)) return true;
  return Boolean(element.closest(SKIP_TRANSLATE_SELECTOR));
};

function AutoPageTranslator({ language, cache, translateMany }) {
  const textNodeSources = useRef(new WeakMap());
  const pendingTimer = useRef(null);

  useEffect(() => {
    if (typeof document === "undefined") return undefined;

    const textJobs = [];
    const attrJobs = [];
    const requested = new Set();

    const rememberTextSource = (node) => {
      const cachedSource = textNodeSources.current.get(node);
      const currentText = node.textContent;
      if (cachedSource) {
        const knownTranslations = Object.values(cache)
          .map((entries) => entries?.[cachedSource])
          .filter(Boolean);
        if (currentText !== cachedSource && !knownTranslations.includes(currentText)) {
          textNodeSources.current.set(node, currentText);
          return currentText;
        }
        return cachedSource;
      }
      const source = currentText;
      textNodeSources.current.set(node, source);
      return source;
    };

    const collect = () => {
      textJobs.length = 0;
      attrJobs.length = 0;
      requested.clear();

      const root = document.querySelector(AUTO_TRANSLATE_ROOT);
      if (!root) return;

      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          if (nearestSkipsTranslation(node)) return NodeFilter.FILTER_REJECT;
          return shouldTranslateText(rememberTextSource(node))
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_REJECT;
        },
      });

      let current = walker.nextNode();
      while (current) {
        const source = rememberTextSource(current);
        textJobs.push({ node: current, source });
        if (language !== "en" && !cache[language]?.[source] && !requested.has(source)) {
          requested.add(source);
        }
        current = walker.nextNode();
      }

      root.querySelectorAll(TRANSLATABLE_ATTRIBUTES.map((attr) => `[${attr}]`).join(",")).forEach((element) => {
        if (element.closest(`${SKIP_TRANSLATE_SELECTOR}, script, style, noscript, code, pre, select, option`)) return;

        TRANSLATABLE_ATTRIBUTES.forEach((attr) => {
          const originalAttr = `data-translate-source-${attr}`;
          const source = element.getAttribute(originalAttr) || element.getAttribute(attr);
          if (!source || !shouldTranslateText(source)) return;
          if (!element.hasAttribute(originalAttr)) element.setAttribute(originalAttr, source);
          attrJobs.push({ element, attr, source });
          if (language !== "en" && !cache[language]?.[source]) requested.add(source);
        });
      });
    };

    const apply = () => {
      collect();

      if (language === "en") {
        textJobs.forEach(({ node, source }) => {
          if (node.textContent !== source) node.textContent = source;
        });
        attrJobs.forEach(({ element, attr, source }) => {
          if (element.getAttribute(attr) !== source) element.setAttribute(attr, source);
        });
        return;
      }

      textJobs.forEach(({ node, source }) => {
        const translated = cache[language]?.[source];
        if (translated && node.textContent !== translated) node.textContent = translated;
      });
      attrJobs.forEach(({ element, attr, source }) => {
        const translated = cache[language]?.[source];
        if (translated && element.getAttribute(attr) !== translated) element.setAttribute(attr, translated);
      });

      const missing = [...requested];
      if (missing.length) {
        translateMany(missing, language).then((translated) => {
          missing.forEach((source, index) => {
            const value = translated[index];
            if (!value || value === source) return;
            textJobs.forEach((job) => {
              if (job.source === source) job.node.textContent = value;
            });
            attrJobs.forEach((job) => {
              if (job.source === source) job.element.setAttribute(job.attr, value);
            });
          });
        });
      }
    };

    const scheduleApply = () => {
      window.clearTimeout(pendingTimer.current);
      pendingTimer.current = window.setTimeout(apply, 80);
    };

    apply();
    const observer = new MutationObserver(scheduleApply);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: TRANSLATABLE_ATTRIBUTES,
    });

    return () => {
      observer.disconnect();
      window.clearTimeout(pendingTimer.current);
    };
  }, [language, cache, translateMany]);

  return null;
}

export function LandingLanguageProvider({ children }) {
  const [language, setLanguage] = useState(
    () => localStorage.getItem("cropconnect-language") || "en"
  );

  useEffect(() => {
    const handleLanguageChange = (event) => {
      setLanguage(event.detail || localStorage.getItem("cropconnect-language") || "en");
    };
    window.addEventListener("cropconnect-language-change", handleLanguageChange);
    return () => window.removeEventListener("cropconnect-language-change", handleLanguageChange);
  }, []);

  // Cache for AI translations to avoid redundant API calls
  const [cache, setCache] = useState(() => {
    try {
      localStorage.removeItem("cropconnect-cache");
      const storedCache = JSON.parse(localStorage.getItem(TRANSLATION_CACHE_STORAGE_KEY) || "{}");
      return Object.fromEntries(
        Object.entries(storedCache).map(([lang, entries]) => [lang, boundedLanguageCache(entries)])
      );
    } catch {
      return {};
    }
  });

  // Persist cache to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem(TRANSLATION_CACHE_STORAGE_KEY, JSON.stringify(cache));
  }, [cache]);

  const translateText = useCallback(async (text, targetLang = language) => {
    if (!text || targetLang === "en") return text;
    if (!publicTranslationEnabled) return text;

    // Check cache first
    if (cache[targetLang]?.[text]) return cache[targetLang][text];

    try {
      const response = await axios.post(`${API}/utils/translate`, {
        text,
        target_lang: targetLang
      });
      const translated = response.data.translated;

      // Update cache
      setCache((prev) => mergeTranslationCache(prev, targetLang, { [text]: translated }));

      return translated;
    } catch (err) {
      console.error("AI Translation failed:", err);
      const fallbackItems = await translateWithFallbackEndpoint([text], targetLang);
      const translated = fallbackItems?.[0] || text;
      if (translated !== text) {
        setCache((prev) => mergeTranslationCache(prev, targetLang, { [text]: translated }));
      }
      return translated;
    }
  }, [cache, language]);

  const translateTexts = useCallback(async (texts, targetLang = language) => {
    if (!texts?.length || targetLang === "en") return texts;

    const missing = texts.filter((text) => text && !cache[targetLang]?.[text]);
    if (!missing.length) {
      return texts.map((text) => cache[targetLang]?.[text] || text);
    }

    if (!publicTranslationEnabled) return texts;

    try {
      const chunks = chunkTranslationTexts(missing);
      const translatedMaps = await Promise.all(chunks.map(async (chunk) => {
        let translatedItems = [];
        try {
          const response = await axios.post(`${API}/utils/translate`, {
            texts: chunk,
            target_lang: targetLang
          });
          translatedItems = response.data.translations || [];
        } catch (err) {
          console.error("AI batch translation failed:", err);
          translatedItems = await translateWithFallbackEndpoint(chunk, targetLang) || [];
        }
        const chunkMap = {};
        chunk.forEach((source, index) => {
          chunkMap[source] = translatedItems[index] || source;
        });
        setCache((prev) => mergeTranslationCache(prev, targetLang, chunkMap));
        return chunkMap;
      }));

      const translatedMap = Object.assign({}, ...translatedMaps);
      setCache((prev) => mergeTranslationCache(prev, targetLang, translatedMap));

      return texts.map((text) => translatedMap[text] || cache[targetLang]?.[text] || text);
    } catch (err) {
      console.error("AI batch translation failed:", err);
      const fallbackItems = await translateWithFallbackEndpoint(missing, targetLang) || [];
      const fallbackMap = {};
      missing.forEach((source, index) => {
        fallbackMap[source] = fallbackItems[index] || source;
      });
      setCache((prev) => mergeTranslationCache(prev, targetLang, fallbackMap));
      return texts.map((text) => fallbackMap[text] || cache[targetLang]?.[text] || text);
    }
  }, [cache, language]);

  const value = useMemo(() => {
    const t = (key) => {
      const englishValue = translations.en[key] || key;
      return englishValue;
    };

    return {
      language,
      translate: (text, targetLang = language) => translateText(text, targetLang),
      translateMany: (texts, targetLang = language) => translateTexts(texts, targetLang),
      setLanguage: (next) => {
        localStorage.setItem("cropconnect-language", next);
        window.dispatchEvent(new CustomEvent("cropconnect-language-change", { detail: next }));
        setLanguage(next);
      },
      t
    };
  }, [language, translateText, translateTexts]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
      <AutoPageTranslator language={language} cache={cache} translateMany={translateTexts} />
    </LanguageContext.Provider>
  );
}

export function useLandingLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLandingLanguage must be used inside LandingLanguageProvider");
  }
  return context;
}
