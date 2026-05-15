// Renders the active dashboard page content and local page widgets.
import {
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle2,
  CloudSun,
  Droplets,
  HelpCircle,
  Languages,
  LayoutDashboard,
  Mail,
  MapPin,
  MessageCircle,
  Moon,
  Phone,
  Radio,
  ShieldCheck,
  Sprout,
  Sun,
  TrendingDown,
  TrendingUp,
  Wifi,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { INDIA_STATES, getDistrictOptions, getPlaceOptions } from "../../lib/indiaLocations";
import CropPlanner from "../../pages/CropPlanner";
import LanguageSelect, { languages } from "../LanguageSelect";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import AiSection from "./AiSection";
import MarketSection from "./MarketSection";
import PumpSection from "./PumpSection";
import SensorSection from "./SensorSection";
import WeatherSection from "./WeatherSection";

const profileSelectClass = "min-w-[190px] max-w-[260px] rounded border border-gray-300 bg-white px-3 py-1 text-right";

export default function DashboardPageContent({ ctx }) {
  const {
    EMPTY_DISPLAY,
    activePage,
    activeSensorAlerts,
    apiLogs,
    chatContainerRef,
    chatInput,
    chatMessages,
    closeTimerModal,
    colors,
    copyToClipboard,
    cropZones,
    ct,
    displayValue,
    editData,
    formatTime,
    formatTimerStartTime,
    getUserMarketLocation,
    handleAddTimer,
    handleSendMessage,
    handleSuggestionClick,
    isDark,
    isEditingProfile,
    isListening,
    isPresent,
    isTyping,
    language,
    loadMarketInsight,
    loadMarketPrices,
    loadSensorApiKey,
    logContainerRef,
    marketData,
    marketError,
    marketInsight,
    marketInsightError,
    marketInsightLoading,
    marketLoading,
    newTimer,
    numericOrNull,
    openTimerModal,
    percentValue,
    protectedFetch,
    pumps,
    pumpControlMode,
    pumpDirectHost,
    pumpUpdating,
    removeTimer,
    saveSensorSetup,
    saveUserToMysql,
    scheduledTimers,
    sensorApiKey,
    sensorApiKeyError,
    sensorApiKeyLoading,
    sensorConnection,
    sensorData,
    sensorDeviceId,
    sensorIngestUrl,
    sensorSetupForm,
    setChatInput,
    setEditData,
    setIsEditingProfile,
    setLanguage,
    setNewTimer,
    setPumpControlMode,
    setPumpDirectHost,
    setSensorSetupForm,
    setTheme,
    setUserData,
    setupCheckResult,
    setupChecking,
    showSuggestions,
    showTimerModal,
    startListening,
    stopListening,
    suggestionChips,
    t,
    telemetryPacket,
    testSensorConnection,
    theme,
    togglePump,
    userData,
    weatherData,
    weatherError,
  } = ctx;

  // Line chart component
  const LineChart = ({ data, color, height = 120 }) => {
    if (!Array.isArray(data) || data.length < 2) {
      return (
        <div className="flex items-center justify-center text-sm" style={{ height, color: colors.textLight }}>
          {EMPTY_DISPLAY}
        </div>
      );
    }
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const points = data.map((v, i) => ({
      x: (i / (data.length - 1)) * 100,
      y: 100 - ((v - min) / range) * 80 - 10,
    }));
    const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
    const areaD = `${pathD} L 100 100 L 0 100 Z`;

    return (
      <svg viewBox="0 0 100 100" className="w-full" style={{ height }} preserveAspectRatio="none">
        <defs>
          <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <path d={areaD} fill={`url(#gradient-${color})`} />
        <path d={pathD} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
    );
  };

  // Semicircle gauge component
  const SemicircleGauge = ({ value, max = 100, size = 140 }) => {
    const radius = size / 2 - 8;
    const circumference = Math.PI * radius;
    const numericValue = numericOrNull(value);
    const offset = circumference - ((numericValue || 0) / max) * circumference;

    return (
      <div className="relative inline-block" style={{ width: size, height: size / 2 }}>
        <svg width={size} height={size / 2} viewBox={`0 0 ${size} ${size / 2}`}>
          <defs>
            <linearGradient id="gaugeGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={colors.red} />
              <stop offset="50%" stopColor={colors.gold} />
              <stop offset="100%" stopColor={colors.greenLight} />
            </linearGradient>
          </defs>
          <path
            d={`M 8 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 8} ${size / 2}`}
            fill="none"
            stroke={colors.creamDark}
            strokeWidth="8"
          />
          <path
            d={`M 8 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 8} ${size / 2}`}
            fill="none"
            stroke="url(#gaugeGradient)"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute bottom-1 left-1/2 -translate-x-1/2 text-center">
          <span className="text-2xl font-mono font-bold" style={{ color: colors.textDark }}>{displayValue(numericValue)}</span>
          {numericValue !== null && <span className="text-xs" style={{ color: colors.textLight }}>/{max}</span>}
        </div>
      </div>
    );
  };

  // Status chip component
  const StatusChip = ({ status }) => {
    const styles = {
      OK: { bg: "bg-green-100", text: "text-green-700", border: "border-green-200" },
      WARN: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-200" },
      CRIT: { bg: "bg-red-100", text: "text-red-700", border: "border-red-200" },
    };
    const s = styles[status] || styles.OK;
    return (
      <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${s.bg} ${s.text} ${s.border}`}>
        {status}
      </span>
    );
  };

  // Metric card component
  const MetricCard = ({ icon: Icon, title, value, unit, color, trend, trendValue, progress }) => {
    const colorStyles = {
      green: { bg: "bg-green-50", border: "border-green-200", text: "text-green-600", fill: colors.greenLight },
      orange: { bg: "bg-orange-50", border: "border-orange-200", text: "text-orange-600", fill: colors.terracotta },
      blue: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-600", fill: colors.blue },
      gold: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-600", fill: colors.gold },
    };
    const style = colorStyles[color] || colorStyles.green;
    const numericProgress = numericOrNull(progress);

    return (
      <div className={`relative p-4 rounded-xl bg-white border ${style.border} shadow-sm overflow-hidden`}>
        <div className="absolute -right-4 -top-4 w-16 h-16 rounded-full opacity-8" style={{ background: style.fill }} />
        <div className="flex items-start justify-between">
          <div className={`p-2 rounded-lg ${style.bg}`}>
            <Icon className="w-5 h-5" style={{ color: style.fill }} />
          </div>
          {trend && isPresent(trendValue) && (
            <div className={`flex items-center gap-1 text-xs ${trend === "up" ? "text-green-600" : "text-red-600"}`}>
              {trend === "up" ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {trendValue}
            </div>
          )}
        </div>
        <div className="mt-3">
          <p className="text-sm" style={{ color: colors.textLight }}>{title}</p>
          <p className="text-2xl font-mono font-bold mt-1" style={{ color: colors.textDark }}>
            {displayValue(value)}
            {isPresent(value) && <span className="text-sm font-normal ml-1" style={{ color: colors.textLight }}>{unit}</span>}
          </p>
        </div>
        {numericProgress !== null && (
          <div className="mt-3 h-1.5 rounded-full bg-gray-100 overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${Math.max(0, Math.min(100, numericProgress))}%`, background: style.fill }} />
          </div>
        )}
      </div>
    );
  };

  // Field Map Component
  const FieldMap = () => {
    const zoneHasAlert = (zoneName) => activeSensorAlerts.some((alert) => alert.zone === zoneName);

    return (
      <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold" style={{ color: colors.textDark }}>Field Map</h3>
          <span className="text-xs px-2 py-1 rounded-full bg-green-50 text-green-600">{displayValue(userData.landSize, " acres")}</span>
        </div>
        <div className="relative rounded-xl overflow-hidden" style={{ height: 280, background: `linear-gradient(135deg, #1a472a, #2d5a3d)` }}>
          {/* Simulated field map with zones */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="grid grid-cols-3 gap-2 p-4 w-full h-full">
              {/* Zone A */}
              <div className="relative rounded-lg overflow-hidden" style={{ background: "#4a8a5a", gridColumn: "span 2" }}>
                <div className="absolute top-2 left-2 text-white text-xs font-medium">Zone A - {userData.zoneA || "Crop"}</div>
                <div className="absolute bottom-2 left-2 text-white/70 text-xs">{displayValue(cropZones[0]?.area)}</div>
                <div className="absolute top-2 right-2">
                  {zoneHasAlert("Zone A") ? <AlertTriangle className="w-4 h-4 text-amber-300" /> : <Droplets className="w-4 h-4 text-green-200" />}
                </div>
                {/* Simulated crop rows */}
                <div className="absolute inset-0 flex flex-col justify-around p-4">
                  {[88, 92, 84, 90, 86].map((width, i) => (
                    <div key={i} className="h-0.5 bg-green-300/30 rounded-full" style={{ width: `${width}%` }} />
                  ))}
                </div>
              </div>
              {/* Zone B - Vegetables */}
              <div className="relative rounded-lg overflow-hidden" style={{ background: "#3a7a4a" }}>
                <div className="absolute top-2 left-2 text-white text-xs font-medium">Zone B - {userData.zoneB || "Crop"}</div>
                <div className="absolute bottom-2 left-2 text-white/70 text-xs">{displayValue(cropZones[1]?.area)}</div>
                <div className="absolute top-2 right-2">
                  {zoneHasAlert("Zone B") ? <AlertTriangle className="w-4 h-4 text-amber-300" /> : <Droplets className="w-4 h-4 text-green-200" />}
                </div>
              </div>
              {/* Zone C */}
              <div className="relative rounded-lg overflow-hidden" style={{ background: "#5a9a5a" }}>
                <div className="absolute top-2 left-2 text-white text-xs font-medium">Zone C - {userData.zoneC || "Crop"}</div>
                <div className="absolute bottom-2 left-2 text-white/70 text-xs">{displayValue(cropZones[2]?.area)}</div>
                <div className="absolute top-2 right-2">
                  {zoneHasAlert("Zone C") ? <AlertTriangle className="w-4 h-4 text-amber-300" /> : null}
                </div>
              </div>
              {/* Water body */}
              <div className="relative rounded-lg overflow-hidden" style={{ background: "#2a6aaa", gridColumn: "span 2" }}>
                <div className="absolute top-2 left-2 text-white/80 text-xs font-medium">Water Body</div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <Droplets className="w-6 h-6 text-blue-200/50" />
                </div>
              </div>
            </div>
          </div>
          {/* Location badge */}
          <div className="absolute bottom-4 right-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-white/10 backdrop-blur-sm">
            <MapPin className="w-4 h-4 text-white" />
            <span className="text-white text-xs">{userData.locationType === "city" ? userData.city : userData.village}, {userData.state}</span>
          </div>
        </div>
      </div>
    );
  };

  // Render active page content
  const renderPage = () => {
    switch (activePage) {
      case "dashboard":
        return (
          <div className="space-y-6">
            {userData.sensorSetupStatus === "waiting" && (
              <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-start gap-3">
                  <Wifi className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-amber-900">Waiting for first sensor packet</p>
                    <p className="text-sm text-amber-800">Device <span className="font-mono">{userData.sensorDeviceId}</span> is configured. The dashboard will switch to ESP32 Live after readings arrive.</p>
                  </div>
                </div>
                <Button type="button" variant="outline" className="bg-white" onClick={testSensorConnection}>
                  Check now
                </Button>
              </div>
            )}
            {/* Metric Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard icon={Droplets} title="Soil Moisture" value={sensorData.soilMoisture} unit="%" color="green" progress={sensorData.soilMoisture} />
              <MetricCard icon={CloudSun} title="Temperature" value={sensorData.temperature} unit={"\u00b0C"} color="orange" progress={isPresent(sensorData.temperature) ? percentValue(sensorData.temperature, 40) : null} />
              <MetricCard icon={Radio} title="Humidity" value={sensorData.humidity} unit="%" color="blue" progress={sensorData.humidity} />
              <MetricCard icon={Sprout} title="Soil pH" value={displayValue(sensorData.soilPh)} unit="" color="gold" progress={isPresent(sensorData.soilPh) ? percentValue(sensorData.soilPh, 10) : null} />
            </div>

            {/* Field Map and Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <FieldMap />
              <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
                <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Moisture Trend (24h)</h3>
                <LineChart data={[]}  color={colors.greenLight} height={200} />
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
                <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Active Alerts</h3>
                <div className="p-6 text-center text-sm" style={{ color: colors.textLight }}>{EMPTY_DISPLAY}</div>
              </div>

              <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
                <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Crop Health Score</h3>
                <div className="p-6 text-center text-sm" style={{ color: colors.textLight }}>{EMPTY_DISPLAY}</div>
              </div>
            </div>
          </div>
        );

      case "sensors":
        return (
          <SensorSection
            colors={colors}
            sensorConnection={sensorConnection}
            sensorData={sensorData}
            userData={userData}
          />
        );

      case "pump":
        return (
          <PumpSection
            colors={colors}
            isDark={isDark}
            userData={userData}
            pumps={pumps}
            pumpControlMode={pumpControlMode}
            pumpDirectHost={pumpDirectHost}
            pumpUpdating={pumpUpdating}
            setPumpControlMode={setPumpControlMode}
            setPumpDirectHost={setPumpDirectHost}
            scheduledTimers={scheduledTimers}
            showTimerModal={showTimerModal}
            newTimer={newTimer}
            setNewTimer={setNewTimer}
            t={t}
            togglePump={togglePump}
            openTimerModal={openTimerModal}
            closeTimerModal={closeTimerModal}
            removeTimer={removeTimer}
            handleAddTimer={handleAddTimer}
            formatTime={formatTime}
            formatTimerStartTime={formatTimerStartTime}
          />
        );

      case "weather":
        return (
          <WeatherSection
            colors={colors}
            weatherData={weatherData}
            weatherError={weatherError}
            userData={userData}
          />
        );

      case "notifications":
        const notificationItems = [
          ...activeSensorAlerts.map((alert) => ({
            icon: alert.icon,
            title: alert.title,
            body: alert.body,
            tone: alert.tone === "critical" ? colors.red : colors.terracotta,
            time: alert.time,
          })),
        ];

        return (
          <div className="space-y-4">
            {notificationItems.length === 0 && (
              <div className="p-6 rounded-xl bg-white border border-[#e8e3d8] shadow-sm text-center text-sm" style={{ color: colors.textLight }}>
                No notifications yet.
              </div>
            )}
            {notificationItems.map((item) => (
              <div key={item.title} className="p-4 sm:p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm flex items-start gap-4">
                <span className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: `${item.tone}18`, color: item.tone }}>
                  <item.icon className="w-5 h-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                    <h3 className="font-semibold" style={{ color: colors.textDark }}>{item.title}</h3>
                    <span className="text-xs" style={{ color: colors.textLight }}>{item.time}</span>
                  </div>
                  <p className="mt-1 text-sm" style={{ color: colors.textMid }}>{item.body}</p>
                </div>
              </div>
            ))}
          </div>
        );

      case "market":
        return (
          <MarketSection
            colors={colors}
            marketData={marketData}
            marketError={marketError}
            marketLoading={marketLoading}
            marketInsight={marketInsight}
            marketInsightError={marketInsightError}
            marketInsightLoading={marketInsightLoading}
            getUserMarketLocation={getUserMarketLocation}
            loadMarketPrices={loadMarketPrices}
            loadMarketInsight={loadMarketInsight}
          />
        );

      case "flow":
        return (
          <div className="space-y-6">
            <div className="p-6 rounded-xl" style={{ background: `linear-gradient(135deg, ${colors.greenDark}, #0f2a1f)` }}>
              <h3 className="font-semibold mb-6" style={{ color: colors.cream }}>Data Pipeline</h3>
              <div className="flex items-center justify-between flex-wrap gap-4">
                {[
                  { icon: Radio, title: "Soil Sensors", desc: "Moisture, pH, NPK and climate readings", note: "Field input" },
                  { icon: Zap, title: "Main ESP32", desc: "SIM800L telemetry and relay polling", note: "Cellular" },
                  { icon: CloudSun, title: "FastAPI + MySQL", desc: "Stores latest sensor rows and pump timers", note: "Backend" },
                  { icon: LayoutDashboard, title: "Web Dashboard", desc: "Shows latest data and queues commands", note: "Browser" },
                  { icon: Radio, title: "Pump ESP32", desc: "Receives relay commands from the main ESP32", note: "Serial link" },
                ].map((node, idx) => (
                  <div key={node.title} className="flex items-center gap-2">
                    <div className={`p-4 rounded-xl ${idx < 2 ? "ring-2 ring-amber-400" : ""}`} style={{ background: idx < 2 ? "rgba(200, 168, 75, 0.2)" : "rgba(255,255,255,0.1)" }}>
                      <node.icon className={`w-6 h-6 ${idx < 2 ? "text-amber-400" : "text-cream"}`} />
                    </div>
                    <div className={idx < 2 ? "text-amber-400" : "text-cream"}>
                      <p className="font-medium text-sm">{node.title}</p>
                      <p className="text-xs opacity-70">{node.desc}</p>
                      <p className="text-xs font-mono opacity-50 mt-1">{node.note}</p>
                    </div>
                    {idx < 4 && <span className="text-2xl text-cream animate-pulse" style={{ animationDuration: "2s" }}>{"->"}</span>}
                  </div>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {Object.entries(telemetryPacket).map(([key, value]) => (
                <div key={key} className="p-3 rounded-lg text-center" style={{ background: "rgba(30, 58, 47, 0.9)" }}>
                  <p className="text-xs font-mono mb-1" style={{ color: colors.textLight }}>{key}</p>
                  <p className="font-mono font-bold" style={{ color: colors.greenLight }}>{isPresent(value) ? value : EMPTY_DISPLAY}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="p-5 rounded-xl" style={{ background: "#0d1f17" }}>
                <h3 className="font-semibold mb-4" style={{ color: colors.greenLight }}>API Endpoint Log</h3>
                <div ref={logContainerRef} className="space-y-2 max-h-64 overflow-y-auto font-mono text-sm">
                  {apiLogs.map((log) => (
                    <div key={log.id} className="flex items-center gap-2">
                      <span className="text-xs" style={{ color: colors.textLight }}>{new Date(log.timestamp).toLocaleTimeString()}</span>
                      <span className={log.method === "GET" ? "text-blue-400" : log.method === "POST" ? "text-green-400" : "text-amber-400"}>{log.method}</span>
                      <span style={{ color: colors.cream }}>{log.path}</span>
                      <span className={log.status === 200 ? "text-green-400" : "text-amber-400"}>{log.status}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="p-5 rounded-xl" style={{ background: "#0d1f17" }}>
                <h3 className="font-semibold mb-4" style={{ color: colors.greenLight }}>Latest Telemetry Packet</h3>
                <pre className="font-mono text-sm overflow-x-auto" style={{ color: colors.cream }}>{JSON.stringify(telemetryPacket, null, 2)}</pre>
              </div>
            </div>
          </div>
        );

      case "ai":
        return (
          <AiSection
            colors={colors}
            chatContainerRef={chatContainerRef}
            chatMessages={chatMessages}
            userName={userData.name}
            isTyping={isTyping}
            showSuggestions={showSuggestions}
            suggestionChips={suggestionChips}
            ct={ct}
            handleSuggestionClick={handleSuggestionClick}
            chatInput={chatInput}
            setChatInput={setChatInput}
            handleSendMessage={handleSendMessage}
            isListening={isListening}
            startListening={startListening}
            stopListening={stopListening}
            language={language}
          />
        );

      case "cropPlanner":
        return (
          <div className="-m-3 sm:-m-5 md:-m-6">
            <CropPlanner
              key={language}
              sensorData={sensorData}
              sensorConnection={sensorConnection}
              userProfile={userData}
              protectedFetch={protectedFetch}
              language={language}
              embedded
            />
          </div>
        );

      case "settings":
        return (
          <div className="space-y-6">
            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>{t("language")}</h3>
              <div className="mb-4 inline-flex rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
                <LanguageSelect value={language} onChange={setLanguage} />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {languages.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => {
                      localStorage.setItem("cropconnect-language", lang.code);
                      setLanguage(lang.code);
                      toast.success(`Language changed to ${lang.name}`);
                    }}
                    className={`p-3 rounded-lg border-2 transition-colors flex flex-col items-center gap-1 ${
                      language === lang.code
                        ? "border-green-500 bg-green-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <Languages className="w-4 h-4" style={{ color: colors.greenDark }} />
                    <span className="text-lg font-medium" style={{ color: colors.textDark }}>{lang.name}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>{t("appearance")}</h3>
              <div className="flex gap-4">
                <button
                  onClick={() => {
                    setTheme("light");
                    toast.success("Light mode enabled");
                  }}
                  className={`flex-1 p-4 rounded-lg border-2 flex flex-col items-center gap-2 ${theme === "light" ? "border-green-500 bg-green-50" : "border-gray-300 hover:border-gray-400"}`}
                >
                  <Sun className="w-8 h-8 text-amber-500" />
                  <span className="font-medium" style={{ color: colors.textDark }}>{t("lightMode")}</span>
                </button>
                <button
                  onClick={() => {
                    setTheme("dark");
                    toast.success("Dark mode enabled");
                  }}
                  className={`flex-1 p-4 rounded-lg border-2 flex flex-col items-center gap-2 transition-colors ${theme === "dark" ? "border-green-500 bg-green-50" : "border-gray-300 hover:border-gray-400"}`}
                >
                  <Moon className="w-8 h-8 text-gray-600" />
                  <span className="font-medium" style={{ color: colors.textDark }}>{t("darkMode")}</span>
                </button>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Contact Us</h3>
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 rounded-lg" style={{ background: colors.cream }}>
                  <Mail className="w-5 h-5" style={{ color: colors.greenDark }} />
                  <div>
                    <p className="font-medium" style={{ color: colors.textDark }}>Email</p>
                    <p className="text-sm" style={{ color: colors.textMid }}>cropconnectco@gmail.com</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 rounded-lg" style={{ background: colors.cream }}>
                  <Phone className="w-5 h-5" style={{ color: colors.greenDark }} />
                  <div>
                    <p className="font-medium" style={{ color: colors.textDark }}>Phone</p>
                    <p className="text-sm" style={{ color: colors.textMid }}>+91 94791 87552</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 rounded-lg" style={{ background: colors.cream }}>
                  <MessageCircle className="w-5 h-5" style={{ color: colors.greenDark }} />
                  <div>
                    <p className="font-medium" style={{ color: colors.textDark }}>WhatsApp</p>
                    <p className="text-sm" style={{ color: colors.textMid }}>+91 94791 87552</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>About</h3>
              <p className="text-sm" style={{ color: colors.textMid }}>
                CropConnect v1.0.0 - Smart Farming Dashboard<br />
                Empowering farmers with IoT and AI technology
              </p>
            </div>
          </div>
        );

      case "profile":
        const editLocationType = (editData.locationType || userData.locationType || "city") === "village" ? "village" : "city";
        const editState = editData.state || userData.state || "";
        const editDistrict = editData.district || userData.district || "";
        const profileDistrictOptions = getDistrictOptions(editState);
        const profilePlaceOptions = getPlaceOptions(editState, editDistrict);
        const handleProfileFieldChange = (key, value) => {
          setEditData((prev) => {
            const next = { ...prev, [key]: value };
            if (key === "state") {
              next.district = "";
              next.city = "";
              next.village = "";
            }
            if (key === "district" || key === "locationType") {
              next.city = "";
              next.village = "";
            }
            return next;
          });
        };

        const handleEditProfile = async () => {
          if (isEditingProfile) {
            const updatedUser = { ...userData, ...editData };
            const location = updatedUser.locationType === "village"
              ? updatedUser.village || updatedUser.city || ""
              : updatedUser.city || updatedUser.village || "";

            setUserData(updatedUser);

            try {
              const mysqlUser = await saveUserToMysql({
                name: updatedUser.name,
                phone: updatedUser.phone,
                state: updatedUser.state,
                district: updatedUser.district || "",
                location,
                location_type: updatedUser.locationType || "city",
                city: updatedUser.city || "",
                village: updatedUser.village || "",
                land_size: updatedUser.landSize ? Number(updatedUser.landSize) : null,
                sensors: updatedUser.sensors || "0",
                pumps: updatedUser.pumps || "0",
              });
              const mergedUser = mysqlUser ? { ...updatedUser, ...mysqlUser } : updatedUser;
              setUserData(mergedUser);
              toast.success("Profile updated in MySQL!");
            } catch (error) {
              toast.error(error.message || "Profile saved locally, but MySQL update failed");
            }
          } else {
            setEditData(userData);
          }
          setIsEditingProfile(!isEditingProfile);
        };

        return (
          <div className="space-y-6">
            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold" style={{ background: colors.greenDark, color: "white" }}>
                    <span data-no-translate="true">{userData.name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)}</span>
                  </div>
                  <div>
                    <h3 data-no-translate="true" className="text-xl font-semibold" style={{ color: colors.textDark }}>{userData.name}</h3>
                    <p data-no-translate="true" className="text-sm" style={{ color: colors.textMid }}>{userData.email}</p>
                  </div>
                </div>
                <button
                  onClick={handleEditProfile}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    isEditingProfile
                      ? "bg-green-600 text-white"
                      : "bg-gray-100 hover:bg-gray-200"
                  }`}
                  style={{ color: isEditingProfile ? "white" : colors.textDark }}
                >
                  {isEditingProfile ? "Save" : "Edit Profile"}
                </button>
              </div>

              <div className="space-y-4">
                {[
                  { label: "Full Name", key: "name", type: "text" },
                  { label: "Email", key: "email", type: "email" },
                  { label: "State", key: "state", type: "state" },
                  { label: "Location Type", key: "locationType", type: "locationType" },
                  { label: "District", key: "district", type: "district" },
                  { label: editLocationType === "city" ? "City" : "Village", key: editLocationType === "city" ? "city" : "village", type: "place" },
                  { label: "Land Size (acres)", key: "landSize", type: "text" },
                  { label: "Crop Type", key: "cropType", type: "text" },
                  { label: "Farming Type", key: "farmingType", type: "text" },
                  { label: "Zone A (Crops)", key: "zoneA", type: "text" },
                  { label: "Zone B (Crops)", key: "zoneB", type: "text" },
                  { label: "Zone C (Crops)", key: "zoneC", type: "text" },
                ].map((field) => (
                  <div key={field.key} className="flex justify-between items-center py-3 border-b" style={{ borderColor: colors.creamDark }}>
                    <span className="font-medium" style={{ color: colors.textDark }}>{field.label}</span>
                    {isEditingProfile ? (
                      field.type === "state" ? (
                        <select
                          value={editData.state || ""}
                          onChange={(event) => handleProfileFieldChange("state", event.target.value)}
                          className={profileSelectClass}
                          style={{ color: colors.textMid }}
                        >
                          <option value="">Select state</option>
                          {INDIA_STATES.map((state) => (
                            <option key={state.code} value={state.name}>
                              {state.name}
                            </option>
                          ))}
                        </select>
                      ) : field.type === "locationType" ? (
                        <select
                          value={editLocationType}
                          onChange={(event) => handleProfileFieldChange("locationType", event.target.value)}
                          className={profileSelectClass}
                          style={{ color: colors.textMid }}
                        >
                          <option value="city">City</option>
                          <option value="village">Village</option>
                        </select>
                      ) : field.type === "district" ? (
                        <select
                          value={editData.district || ""}
                          onChange={(event) => handleProfileFieldChange("district", event.target.value)}
                          disabled={!editState}
                          className={`${profileSelectClass} disabled:opacity-50`}
                          style={{ color: colors.textMid }}
                        >
                          <option value="">{editState ? "Select district" : "Select state first"}</option>
                          {profileDistrictOptions.map((district) => (
                            <option key={district} value={district}>
                              {district}
                            </option>
                          ))}
                        </select>
                      ) : field.type === "place" ? (
                        <select
                          value={editData[field.key] || ""}
                          onChange={(event) => handleProfileFieldChange(field.key, event.target.value)}
                          disabled={!editDistrict}
                          className={`${profileSelectClass} disabled:opacity-50`}
                          style={{ color: colors.textMid }}
                        >
                          <option value="">{editDistrict ? `Select ${field.label.toLowerCase()}` : "Select district first"}</option>
                          {profilePlaceOptions.map((place) => (
                            <option key={place} value={place}>
                              {place}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type={field.type}
                          value={editData[field.key] || ""}
                          onChange={(e) => setEditData({ ...editData, [field.key]: e.target.value })}
                          className="px-3 py-1 rounded border border-gray-300 text-right"
                          style={{ color: colors.textMid }}
                        />
                      )
                    ) : (
                      <span data-dynamic-value="true" style={{ color: colors.textMid }}>{displayValue(userData[field.key])}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Farm Statistics</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-lg" style={{ background: colors.cream }}>
                  <p className="text-sm" style={{ color: colors.textMid }}>Total Area</p>
                  <p className="text-xl font-bold" style={{ color: colors.textDark }}>{displayValue(userData.landSize, " acres")}</p>
                </div>
                <div className="p-4 rounded-lg" style={{ background: colors.cream }}>
                  <p className="text-sm" style={{ color: colors.textMid }}>Zones</p>
                  <p className="text-xl font-bold" style={{ color: colors.textDark }}>{cropZones.filter((zone) => isPresent(zone.crop)).length || EMPTY_DISPLAY}</p>
                </div>
                <div className="p-4 rounded-lg" style={{ background: colors.cream }}>
                  <p className="text-sm" style={{ color: colors.textMid }}>Active Sensors</p>
                  <p className="text-xl font-bold" style={{ color: colors.textDark }}>{userData.sensors}</p>
                </div>
                <div className="p-4 rounded-lg" style={{ background: colors.cream }}>
                  <p className="text-sm" style={{ color: colors.textMid }}>Irrigation Pumps</p>
                  <p className="text-xl font-bold" style={{ color: colors.textDark }}>{userData.pumps}</p>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
              <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Zone Details</h3>
              <div className="space-y-3">
                {[
                  { zone: "Zone A", crops: userData.zoneA, area: "", status: userData.zoneA ? "Active" : "" },
                  { zone: "Zone B", crops: userData.zoneB, area: "", status: userData.zoneB ? "Active" : "" },
                  { zone: "Zone C", crops: userData.zoneC, area: "", status: userData.zoneC ? "Active" : "" },
                ].map((zone) => (
                  <div key={zone.zone} className="flex items-center justify-between p-3 rounded-lg" style={{ background: colors.cream }}>
                    <div>
                      <p className="font-medium" style={{ color: colors.textDark }}>{zone.zone}</p>
                      <p className="text-sm" style={{ color: colors.textMid }}>{zone.crops} - {zone.area}</p>
                    </div>
                    <span className={`px-2 py-1 text-xs rounded-full ${zone.status === "Active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}`}>
                      {displayValue(zone.status)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return renderPage();
}
