import { Globe } from "lucide-react";

export const publicTranslationEnabled = import.meta.env.VITE_PUBLIC_TRANSLATION_ENABLED === "true";

export const languages = [
  { code: "en", name: "English" },
  { code: "hi", name: "Hindi" },
  { code: "mr", name: "Marathi" },
  { code: "te", name: "Telugu" },
  { code: "ta", name: "Tamil" },
  { code: "bn", name: "Bengali" },
  { code: "kn", name: "Kannada" },
];

export default function LanguageSelect({ value, onChange, className = "" }) {
  const availableLanguages = publicTranslationEnabled ? languages : languages.filter((lang) => lang.code === "en");
  const selectedValue = publicTranslationEnabled ? value : "en";

  return (
    <div className={`relative inline-flex items-center gap-2 ${className}`}>
      <Globe className="w-4 h-4 text-[#1A201C]/60" />
      <select
        value={selectedValue}
        disabled={!publicTranslationEnabled}
        onChange={(event) => {
          const nextLanguage = event.target.value;
          localStorage.setItem("cropconnect-language", nextLanguage);
          window.dispatchEvent(new CustomEvent("cropconnect-language-change", { detail: nextLanguage }));
          onChange(nextLanguage);
        }}
        className="bg-transparent text-sm text-[#1A201C]/80 border-none focus:ring-0 cursor-pointer pr-6 disabled:cursor-not-allowed disabled:opacity-60"
        aria-label={publicTranslationEnabled ? "Select language" : "Translation disabled"}
        title={publicTranslationEnabled ? "Select language" : "Translation disabled"}
      >
        {availableLanguages.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.name}
          </option>
        ))}
      </select>
    </div>
  );
}
