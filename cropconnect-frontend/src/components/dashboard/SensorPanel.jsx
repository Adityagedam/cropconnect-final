import { CloudSun, Droplets, Flower2, Leaf, Radio, Sprout, Wheat } from "lucide-react";

const EMPTY_DISPLAY = "--";
const isPresent = (value) => value !== null && value !== undefined && value !== "";
const displayValue = (value, suffix = "") => (isPresent(value) ? `${value}${suffix}` : EMPTY_DISPLAY);
const numericOrNull = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const StatusChip = ({ status }) => (
  <span className="px-2 py-1 rounded-md bg-green-50 text-green-700 text-xs font-semibold">{status}</span>
);

const SensorCard = ({ colors, icon: Icon, title, value, unit, color, min, max, barValue }) => {
  const colorStyles = {
    green: colors.greenLight,
    orange: colors.terracotta,
    blue: colors.blue,
    gold: colors.gold,
  };
  const fill = colorStyles[color] || colors.greenLight;
  const numericBarValue = numericOrNull(barValue);

  return (
    <div className="p-4 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-1.5 rounded-lg" style={{ background: `${fill}20` }}>
          <Icon className="w-4 h-4" style={{ color: fill }} />
        </div>
        <span className="text-sm font-medium" style={{ color: colors.textDark }}>{title}</span>
      </div>
      <p className="text-3xl font-mono font-bold" style={{ color: colors.textDark }}>
        {displayValue(value)}
        {isPresent(value) && <span className="text-base font-normal ml-1" style={{ color: colors.textLight }}>{unit}</span>}
      </p>
      <div className="mt-3">
        <div className="flex justify-between text-xs mb-1" style={{ color: colors.textLight }}>
          <span>{min}</span>
          <span>{max}</span>
        </div>
        <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${numericBarValue === null ? 0 : Math.max(0, Math.min(100, numericBarValue))}%`,
              background: `linear-gradient(90deg, ${fill}, ${fill}80)`,
            }}
          />
        </div>
      </div>
    </div>
  );
};

const SensorPanel = ({ colors, sensorConnection = {}, sensorData = {}, userData = {} }) => (
  <div className="space-y-6">
    <div className="p-4 rounded-xl border border-[#d5d1c5] bg-[#f7f5ef] shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p className="text-sm font-semibold" style={{ color: colors.textDark }}>Sensor connection</p>
          <p className="text-xs text-slate-600">Device: <span className="font-mono">{displayValue(sensorConnection.deviceId)}</span></p>
          <p className="text-xs text-slate-600">Status: <span className="font-semibold">{sensorConnection.source === "esp32" ? "ESP32 Live" : "Unavailable"}</span></p>
          {sensorConnection.error ? <p className="text-xs text-amber-800 mt-1">{sensorConnection.error}</p> : null}
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-600">Last seen</p>
          <p className="text-sm font-medium" style={{ color: colors.textDark }}>{sensorConnection.lastSeen ? new Date(sensorConnection.lastSeen).toLocaleTimeString() : "No packet yet"}</p>
        </div>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <SensorCard colors={colors} icon={Droplets} title="Soil Moisture" value={sensorData.soilMoisture} unit="%" color="green" min="0%" max="100%" barValue={sensorData.soilMoisture} />
      <SensorCard colors={colors} icon={CloudSun} title="Temperature" value={sensorData.temperature} unit={"\u00b0C"} color="orange" min={"10\u00b0C"} max={"45\u00b0C"} barValue={isPresent(sensorData.temperature) ? ((sensorData.temperature - 10) / 35) * 100 : null} />
      <SensorCard colors={colors} icon={Radio} title="Humidity" value={sensorData.humidity} unit="%" color="blue" min="0%" max="100%" barValue={sensorData.humidity} />
      <SensorCard colors={colors} icon={Sprout} title="Soil pH" value={displayValue(sensorData.soilPh)} unit="" color="gold" min="4" max="10" barValue={isPresent(sensorData.soilPh) ? ((sensorData.soilPh - 4) / 6) * 100 : null} />
      <SensorCard colors={colors} icon={Leaf} title="Nitrogen" value={sensorData.nitrogen} unit="mg/kg" color="green" min="0" max="100" barValue={isPresent(sensorData.nitrogen) ? Math.min(sensorData.nitrogen, 100) : null} />
      <SensorCard colors={colors} icon={Wheat} title="Phosphorus" value={sensorData.phosphorus} unit="mg/kg" color="orange" min="0" max="100" barValue={isPresent(sensorData.phosphorus) ? Math.min(sensorData.phosphorus, 100) : null} />
      <SensorCard colors={colors} icon={Flower2} title="Potassium" value={sensorData.potassium} unit="mg/kg" color="blue" min="0" max="100" barValue={isPresent(sensorData.potassium) ? Math.min(sensorData.potassium, 100) : null} />
    </div>

    <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm overflow-x-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
        <h3 className="font-semibold" style={{ color: colors.textDark }}>Crop Sensor Alert Ranges</h3>
      </div>
      <div className="p-6 text-center text-sm" style={{ color: colors.textLight }}>{EMPTY_DISPLAY}</div>
    </div>

    <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm overflow-x-auto">
      <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Sensor Nodes</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b" style={{ borderColor: colors.creamDark }}>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>Node ID</th>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>Zone</th>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>Moisture</th>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>Temp</th>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>Humidity</th>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>pH</th>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>NPK</th>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>Status</th>
            <th className="text-left py-3 px-3 font-medium" style={{ color: colors.textMid }}>Last Seen</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b" style={{ borderColor: colors.creamDark }}>
            <td className="py-3 px-3 font-mono" style={{ color: colors.textDark }}>{displayValue(userData.sensorDeviceId)}</td>
            <td className="py-3 px-3" style={{ color: colors.textMid }}>Zone A</td>
            <td className="py-3 px-3 font-mono" style={{ color: colors.textDark }}>{displayValue(sensorData.soilMoisture, "%")}</td>
            <td className="py-3 px-3 font-mono" style={{ color: colors.textDark }}>{displayValue(sensorData.temperature, "\u00b0C")}</td>
            <td className="py-3 px-3 font-mono" style={{ color: colors.textDark }}>{displayValue(sensorData.humidity, "%")}</td>
            <td className="py-3 px-3 font-mono" style={{ color: colors.textDark }}>{displayValue(sensorData.soilPh)}</td>
            <td className="py-3 px-3 font-mono" style={{ color: colors.textDark }}>{[sensorData.nitrogen, sensorData.phosphorus, sensorData.potassium].every(isPresent) ? `${sensorData.nitrogen}/${sensorData.phosphorus}/${sensorData.potassium}` : EMPTY_DISPLAY}</td>
            <td className="py-3 px-3">{sensorConnection.source === "esp32" ? <StatusChip status="OK" /> : EMPTY_DISPLAY}</td>
            <td className="py-3 px-3 text-xs" style={{ color: colors.textLight }}>
              {sensorConnection.lastSeen ? new Date(sensorConnection.lastSeen).toLocaleTimeString() : userData.sensorSetupStatus === "waiting" ? "Waiting for first packet" : EMPTY_DISPLAY}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
);

export default SensorPanel;
