import {
  Languages,
  Activity,
  BellRing,
  WifiOff,
  CloudSun,
  Brain,
  Sprout,
  Tractor,
  ShieldCheck,
} from "lucide-react";
import { useLandingLanguage } from "./LandingLanguageContext";

const features = [
  {
    icon: Languages,
    title: "Multilanguage mobile app",
    desc: "English-first UI with AI translation support when the backend translator is enabled.",
    span: "lg:col-span-5 lg:row-span-2",
    tone: "primary",
  },
  {
    icon: Activity,
    title: "Live sensor readings",
    desc: "Soil moisture, temperature, humidity, pH and NPK readings stream from ESP32 packets when the field node is online.",
    span: "lg:col-span-4",
    tone: "accent",
  },
  {
    icon: BellRing,
    title: "Smart threshold alerts",
    desc: "Dashboard alerts appear when live readings cross configured crop and soil thresholds.",
    span: "lg:col-span-3",
    tone: "default",
  },
  {
    icon: Brain,
    title: "AI crop insights",
    desc: "Irrigation, fertilisation and disease hints based on live sensor context plus weather.",
    span: "lg:col-span-4",
    tone: "default",
  },
  {
    icon: WifiOff,
    title: "SIM800L-ready telemetry",
    desc: "The field node can post telemetry over cellular data without depending on farm Wi-Fi.",
    span: "lg:col-span-3",
    tone: "accent",
  },
  {
    icon: CloudSun,
    title: "Live weather",
    desc: "Forecast data is loaded from the backend weather API and shown as unavailable when it cannot be fetched.",
    span: "lg:col-span-4",
    tone: "default",
  },
  {
    icon: Sprout,
    title: "AI crop planner",
    desc: "Crop suggestions come from the backend AI planner using the latest MySQL ESP32 row.",
    span: "lg:col-span-4",
    tone: "default",
  },
  {
    icon: Tractor,
    title: "Farm setup",
    desc: "Track saved farm profile details and hardware setup status in one dashboard.",
    span: "lg:col-span-4",
    tone: "default",
  },
  {
    icon: ShieldCheck,
    title: "Your data, your farm",
    desc: "Per-device API keys protect telemetry writes and relay polling.",
    span: "lg:col-span-4",
    tone: "primary",
  },
];

const toneStyles = {
  primary: "bg-[#1B4332] text-[#FDFBF7] border-[#1B4332]",
  accent: "bg-[#E07A5F] text-white border-[#E07A5F]",
  default: "bg-white text-[#1A201C] border-[#D5D1C5]",
};

export default function FeaturesSection() {
  const { t } = useLandingLanguage();
  return (
    <section
      id="features"
      data-testid="features-section"
      className="relative py-20 sm:py-28 bg-[#FDFBF7]"
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <div className="max-w-2xl">
          <span className="eyebrow">{t("featuresEyebrow")}</span>
          <h2 className="font-display mt-3 text-4xl sm:text-5xl leading-tight text-[#1A201C]">
            {t("featuresTitle")}
            <span className="italic text-[#1B4332]">{t("featuresItalic")}</span>
          </h2>
          <p className="mt-5 text-base text-[#1A201C]/70">
            {t("featuresBody")}
          </p>
        </div>

        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-5 auto-rows-[minmax(180px,auto)]">
          {features.map((f, i) => (
            <div
              key={i}
              data-testid={`feature-${i}`}
              className={`rounded-2xl border p-6 hover-lift ${f.span} ${toneStyles[f.tone]}`}
            >
              <f.icon
                className="w-6 h-6"
                strokeWidth={1.8}
              />
              <h3 className="font-display mt-4 text-xl sm:text-2xl leading-snug">
                {f.title}
              </h3>
              <p className={`mt-3 text-sm leading-relaxed ${f.tone === "default" ? "text-[#1A201C]/70" : "text-white/85"}`}>
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
