import { Link } from "react-router-dom";
import { ArrowLeft, Leaf } from "lucide-react";

const COPY = {
  terms: {
    title: "Terms of Service",
    body: [
      "CropConnect is an agricultural IoT and AI assistance tool. It shows farm data when your ESP32 sends readings and may provide AI-generated farming guidance.",
      "Do not treat AI output as certified agronomy, medical, legal, financial or safety advice. Confirm critical crop, chemical, electrical and pump decisions with qualified local experts.",
      "You are responsible for safe wiring, pump hardware, SIM800L connectivity, device keys and account access.",
    ],
  },
  privacy: {
    title: "Privacy Policy",
    body: [
      "CropConnect stores account profile data, sensor device identity, ESP32 readings, pump state, timers and chat history needed to run the dashboard.",
      "Sensitive profile values and ESP32 display keys are encrypted in MySQL when the backend is configured with CROP_DATA_SECRET_KEY.",
      "The browser does not store the dashboard profile in localStorage. Login uses an HTTP-only cookie plus a CSRF token.",
    ],
  },
};

export default function LegalPage({ type = "terms" }) {
  const copy = COPY[type] || COPY.terms;

  return (
    <div className="min-h-screen bg-[#FDFBF7] px-4 py-10">
      <div className="mx-auto max-w-3xl">
        <Link to="/" className="inline-flex items-center gap-2 text-[#1B4332]">
          <Leaf className="h-5 w-5" />
          <span className="font-display text-xl">CropConnect</span>
        </Link>

        <div className="mt-8 rounded-xl border border-[#D5D1C5] bg-white p-6 shadow-sm">
          <h1 className="font-display text-3xl text-[#1A201C]">{copy.title}</h1>
          <div className="mt-6 space-y-4 text-sm leading-6 text-[#1A201C]/75">
            {copy.body.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
          <Link to="/login" className="mt-8 inline-flex items-center gap-2 text-sm font-medium text-[#1B4332]">
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
