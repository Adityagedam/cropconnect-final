import { CircuitBoard, RadioTower, Cloud, Smartphone } from "lucide-react";
import { useLandingLanguage } from "./LandingLanguageContext";

const steps = [
  {
    n: "01",
    icon: CircuitBoard,
    title: "Sensors in the soil",
    desc: "Soil moisture, temperature, humidity, pH and NPK probes send readings through an ESP32 field node.",
  },
  {
    n: "02",
    icon: RadioTower,
    title: "SIM800L uplink",
    desc: "The main ESP32 posts sensor packets over cellular data and polls queued pump commands from the API.",
  },
  {
    n: "03",
    icon: Cloud,
    title: "CropConnect cloud",
    desc: "The FastAPI service stores telemetry in MySQL, protects device calls with per-device keys and exposes the latest row to the dashboard.",
  },
  {
    n: "04",
    icon: Smartphone,
    title: "App and website",
    desc: "Farmers see live data, AI crop planning and pump command status in the web dashboard.",
  },
];

export default function HowItWorks() {
  const { t } = useLandingLanguage();
  return (
    <section
      id="how-it-works"
      data-testid="how-it-works-section"
      className="relative py-20 sm:py-28 bg-[#F4F1EA]"
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <div className="flex items-end justify-between flex-wrap gap-6">
          <div className="max-w-2xl">
            <span className="eyebrow">{t("howEyebrow")}</span>
            <h2 className="font-display mt-3 text-4xl sm:text-5xl leading-tight text-[#1A201C]">
              {t("howTitle")}
              <span className="italic text-[#1B4332]">{t("howItalic")}</span>
            </h2>
          </div>
          <p className="text-sm text-[#1A201C]/60 max-w-sm">
            {t("howBody")}
          </p>
        </div>

        <div className="mt-14 relative grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="hidden md:block absolute left-0 right-0 top-[34px] border-t-2 border-dashed border-[#1B4332]/20" />

          {steps.map((s, i) => (
            <div
              key={i}
              data-testid={`how-step-${i}`}
              className="relative bg-white border border-[#D5D1C5] rounded-2xl p-6 hover-lift"
            >
              <div className="absolute -top-4 left-6 bg-[#1B4332] text-[#FDFBF7] font-mono text-xs px-3 py-1 rounded-full">
                {s.n}
              </div>
              <s.icon className="w-6 h-6 text-[#E07A5F] mt-3" />
              <h3 className="font-display mt-4 text-xl text-[#1A201C]">
                {s.title}
              </h3>
              <p className="mt-2 text-sm text-[#1A201C]/70 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
