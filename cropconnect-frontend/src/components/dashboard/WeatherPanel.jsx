import { MapPin } from "lucide-react";

const EMPTY_DISPLAY = "--";
const isPresent = (value) => value !== null && value !== undefined && value !== "";
const displayValue = (value, suffix = "") => (isPresent(value) ? `${value}${suffix}` : EMPTY_DISPLAY);

const WeatherPanel = ({ colors, weatherData, weatherError, userData = {} }) => {
  const weather = weatherData || {};
  const weatherCond = {
    icon: EMPTY_DISPLAY,
    condition: weather.condition || EMPTY_DISPLAY,
    advice: weather.advice || EMPTY_DISPLAY,
  };
  const rainfallSeries = (weatherData?.rainfall || []).filter((item) => isPresent(item.value));
  const rainfallPoints = rainfallSeries.map((item, index) => {
    const x = rainfallSeries.length <= 1 ? 20 : 20 + (index * 260) / (rainfallSeries.length - 1);
    const y = 100 - Math.max(0, Math.min(100, item.value || 0)) * 0.8;
    return { ...item, x, y };
  });
  const rainfallLine = rainfallPoints.map((point) => `${point.x},${point.y}`).join(" ");
  const rainfallArea = rainfallPoints.length
    ? `20,108 ${rainfallLine} ${rainfallPoints[rainfallPoints.length - 1].x},108`
    : "";
  const peakRainfall = rainfallSeries.reduce((peak, item) => Math.max(peak, item.value || 0), 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-6 rounded-xl" style={{ background: `linear-gradient(135deg, ${colors.greenDark}, #0f2a1f)` }}>
          <div className="flex items-center gap-2 mb-2">
            <MapPin className="w-4 h-4 text-white/70" />
            <p className="text-sm" style={{ color: colors.creamDark }}>{userData.locationType === "city" ? userData.city : userData.village}, {userData.state}</p>
          </div>
          <div className="flex items-center gap-4 mb-4">
            <span className="text-5xl">{weatherCond.icon || EMPTY_DISPLAY}</span>
            <div>
              <p className="text-4xl font-mono font-bold" style={{ color: colors.cream }}>{displayValue(weather.temp, "\u00b0C")}</p>
              <p className="text-lg" style={{ color: colors.creamDark }}>{weatherCond.condition || EMPTY_DISPLAY}</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.1)" }}>
              <p className="text-xs" style={{ color: colors.creamDark }}>Humidity</p>
              <p className="text-lg font-mono" style={{ color: colors.cream }}>{displayValue(weather.humidity, "%")}</p>
            </div>
            <div className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.1)" }}>
              <p className="text-xs" style={{ color: colors.creamDark }}>Wind</p>
              <p className="text-lg font-mono" style={{ color: colors.cream }}>{displayValue(weather.wind, " km/h")}</p>
            </div>
            <div className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.1)" }}>
              <p className="text-xs" style={{ color: colors.creamDark }}>Pressure</p>
              <p className="text-lg font-mono" style={{ color: colors.cream }}>{displayValue(weather.pressure, " hPa")}</p>
            </div>
          </div>
          <div className="p-4 rounded-lg" style={{ background: "rgba(255,255,255,0.08)" }}>
            <p className="text-sm" style={{ color: colors.creamDark }}>Advice: {weatherCond.advice || EMPTY_DISPLAY}</p>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <h3 className="font-semibold" style={{ color: colors.textDark }}>7-Day Rainfall Prediction</h3>
              <p className="text-xs mt-1" style={{ color: colors.textLight }}>Live internet probability forecast</p>
            </div>
            {rainfallSeries.length > 0 && (
              <span className="px-2 py-1 rounded-md bg-blue-50 text-xs font-mono text-blue-700">
                Peak {peakRainfall}%
              </span>
            )}
          </div>

          {rainfallSeries.length > 0 ? (
            <div>
              <div className="h-40">
                <svg viewBox="0 0 300 126" className="h-full w-full" role="img" aria-label="7 day rainfall probability graph">
                  {[20, 40, 60, 80, 100].map((value) => (
                    <g key={value}>
                      <line x1="20" x2="285" y1={108 - value * 0.8} y2={108 - value * 0.8} stroke="#E5E7EB" strokeWidth="1" />
                      <text x="0" y={112 - value * 0.8} fontSize="8" fill="#8A9488">{value}</text>
                    </g>
                  ))}
                  <polygon points={rainfallArea} fill="rgba(59, 130, 246, 0.14)" />
                  <polyline points={rainfallLine} fill="none" stroke="#2563EB" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                  {rainfallPoints.map((point) => (
                    <g key={point.date || point.day}>
                      <circle cx={point.x} cy={point.y} r="4" fill="#2563EB" stroke="#FFFFFF" strokeWidth="2" />
                      <text x={point.x} y={point.y - 9} textAnchor="middle" fontSize="9" fill="#1A201C">{point.value}%</text>
                    </g>
                  ))}
                </svg>
              </div>
              <div className="grid grid-cols-7 gap-1 mt-2">
                {rainfallSeries.map((item) => (
                  <div key={item.date || item.day} className="text-center">
                    <p className="text-[11px] font-medium" style={{ color: colors.textDark }}>{item.day}</p>
                    <p className="text-[10px]" style={{ color: colors.textLight }}>{displayValue(item.mm, " mm")}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-center text-sm" style={{ color: colors.textLight }}>
              {weatherError ? "Live rainfall probability unavailable" : "Loading live rainfall probability..."}
            </div>
          )}
          <p className="text-xs text-center" style={{ color: colors.textLight }}>
            Live internet source: {weatherData?.source || (weatherError ? "Unavailable" : "Loading")}
          </p>
          {weatherData?.location && (
            <p className="mt-1 text-xs text-center" style={{ color: colors.textLight }}>
              Location: {[weatherData.location.name, weatherData.location.admin1].filter(Boolean).join(", ")}
            </p>
          )}
        </div>
      </div>

      <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
        <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>7-Day Forecast</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-4">
          {(weatherData?.forecast || []).map((item) => (
            <div key={item.day} className="p-4 rounded-xl bg-gray-50 text-center">
              <p className="text-sm font-medium mb-2" style={{ color: colors.textDark }}>{item.day}</p>
              <span className="text-3xl">{item.icon}</span>
              <div className="mt-2">
                <p className="font-mono font-bold" style={{ color: colors.textDark }}>{displayValue(item.high, "\u00b0")}</p>
                <p className="text-sm" style={{ color: colors.textLight }}>{displayValue(item.low, "\u00b0")}</p>
              </div>
            </div>
          ))}
          {!(weatherData?.forecast || []).length && (
            <div className="col-span-full p-6 text-center text-sm" style={{ color: colors.textLight }}>{EMPTY_DISPLAY}</div>
          )}
        </div>
      </div>

      <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
        <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Crop Weather Impact</h3>
        <div className="p-6 text-center text-sm" style={{ color: colors.textLight }}>{EMPTY_DISPLAY}</div>
      </div>
    </div>
  );
};

export default WeatherPanel;
