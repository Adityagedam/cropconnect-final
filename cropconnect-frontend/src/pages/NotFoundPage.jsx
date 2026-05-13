import { Link } from "react-router-dom";
import { Home, ArrowLeft, Search } from "lucide-react";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-[#F7F3EA] flex items-center justify-center px-4">
      <div className="text-center max-w-lg">
        {/* Animated 404 Number */}
        <div className="relative mb-6">
          <h1
            className="text-[10rem] sm:text-[12rem] font-display font-bold leading-none text-[#1B4332]/10 select-none"
            style={{ letterSpacing: "-0.04em" }}
          >
            404
          </h1>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-24 h-24 rounded-full bg-[#1B4332]/5 flex items-center justify-center animate-pulse">
              <Search className="w-10 h-10 text-[#1B4332]/40" />
            </div>
          </div>
        </div>

        {/* Message */}
        <h2 className="font-display text-2xl sm:text-3xl text-[#1A201C] mb-3">
          Page not found
        </h2>
        <p className="text-[#1A201C]/60 text-base mb-8 max-w-sm mx-auto">
          The page you're looking for doesn't exist or has been moved.
          Let's get you back on track.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-2 bg-[#1B4332] hover:bg-[#0F2A1F] text-[#FDFBF7] rounded-full h-11 px-6 text-sm font-medium transition-colors"
          >
            <Home className="w-4 h-4" />
            Back to Home
          </Link>
          <button
            onClick={() => window.history.back()}
            className="inline-flex items-center gap-2 bg-white hover:bg-[#F4F1EA] text-[#1A201C] border border-[#D5D1C5] rounded-full h-11 px-6 text-sm font-medium transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Go Back
          </button>
        </div>
      </div>
    </div>
  );
}
