import { Clock, Droplets, XCircle } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

const EMPTY_DISPLAY = "--";
const isPresent = (value) => value !== null && value !== undefined && value !== "";
const displayValue = (value, suffix = "") => (isPresent(value) ? `${value}${suffix}` : EMPTY_DISPLAY);

function PumpCard({
  id,
  name,
  zone,
  pump,
  colors,
  pumpUpdating,
  scheduledTimers,
  t,
  togglePump,
  openTimerModal,
  removeTimer,
  formatTime,
  formatTimerStartTime,
}) {
  const appliedKnown = pump.appliedOn !== null && pump.appliedOn !== undefined;
  const appliedText = appliedKnown ? (pump.appliedOn ? "ON" : "OFF") : EMPTY_DISPLAY;
  const desiredText = pump.on ? "ON" : "OFF";

  return (
    <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold" style={{ color: colors.textDark }}>{name}</h3>
          <p className="text-sm" style={{ color: colors.textLight }}>{zone}</p>
        </div>
        <button
          onClick={() => togglePump(id)}
          disabled={pumpUpdating[id]}
          className={`relative w-12 h-6 rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${pump.on ? "bg-green-500" : "bg-gray-300"}`}
          aria-label={`Turn ${name} ${pump.on ? "off" : "on"}`}
        >
          <div className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${pump.on ? "translate-x-7" : "translate-x-1"}`} />
        </button>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${pump.on ? "bg-green-50 animate-pulse" : "bg-gray-100"}`} style={pump.on ? { boxShadow: `0 0 20px ${colors.greenLight}40` } : {}}>
          {pump.on ? (
            <Droplets className="w-6 h-6 animate-spin" style={{ color: colors.greenLight, animationDuration: "3s" }} />
          ) : (
            <span className="text-2xl">OFF</span>
          )}
        </div>
        <div>
          <p className="text-sm" style={{ color: colors.textLight }}>{t("status")}</p>
          <p className="font-medium" style={{ color: colors.textDark }}>Desired: {desiredText}</p>
          <p className="text-sm" style={{ color: pump.hardwareConfirmed ? colors.greenLight : colors.textLight }}>
            Hardware: {appliedText}
          </p>
          {pump.on && <p className="text-sm" style={{ color: colors.greenLight }}>{t("runtime")}: {formatTime(pump.runtime)}</p>}
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        <span className="px-2 py-1 text-xs rounded-md bg-gray-100" style={{ color: colors.textMid }}>ON: {displayValue(pump.schedule.on)}</span>
        <span className="px-2 py-1 text-xs rounded-md bg-gray-100" style={{ color: colors.textMid }}>OFF: {displayValue(pump.schedule.off)}</span>
        <span className="px-2 py-1 text-xs rounded-md bg-gray-100" style={{ color: colors.textMid }}>{displayValue(pump.schedule.flow)}</span>
      </div>

      <div className="h-2 rounded-full bg-gray-100 overflow-hidden mb-3">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: pump.on ? "65%" : "0%", background: `linear-gradient(90deg, ${colors.greenLight}, ${colors.greenAccent})` }} />
      </div>

      <p className="text-xs text-center" style={{ color: colors.textLight }}>{t("autoMode")}</p>

      <div className="mt-4 pt-4 border-t border-gray-100">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium" style={{ color: colors.textDark }}>{t("scheduledTimers")}</p>
          <button onClick={() => openTimerModal(id)} className="text-xs px-2 py-1 rounded-md bg-green-50 hover:bg-green-100 transition-colors" style={{ color: colors.greenLight }}>
            {t("addTimer")}
          </button>
        </div>
        <p className="mb-2 text-[11px]" style={{ color: colors.textLight }}>
          Timers are saved to MySQL and applied when the main ESP32 polls relay commands.
        </p>
        <div className="space-y-1">
          {scheduledTimers[id]?.map((timer) => (
            <div key={timer.id} className="flex items-center justify-between px-2 py-1.5 rounded-md bg-gray-50">
              <div className="flex items-center gap-2">
                <Clock className="w-3 h-3" style={{ color: colors.textLight }} />
                <span className="text-xs font-mono" style={{ color: colors.textDark }}>{formatTimerStartTime(timer.startTime)} ({timer.duration}min)</span>
              </div>
              <button onClick={() => removeTimer(id, timer.id)} className="text-gray-400 hover:text-red-500">
                <XCircle className="w-3 h-3" />
              </button>
            </div>
          ))}
          {(!scheduledTimers[id] || scheduledTimers[id].length === 0) && (
            <p className="text-xs text-center py-2" style={{ color: colors.textLight }}>{t("noTimers")}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function TimerModal({
  colors,
  isDark,
  showTimerModal,
  closeTimerModal,
  newTimer,
  setNewTimer,
  handleAddTimer,
  t,
}) {
  if (!showTimerModal.show) return null;
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold" style={{ color: colors.textDark }}>
            {t("scheduleTimer")} - {showTimerModal.pump === "pump1" ? "Pump 1" : "Pump 2"}
          </h3>
          <button onClick={closeTimerModal}>
            <XCircle className="w-5 h-5" style={{ color: colors.textLight }} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1 block" style={{ color: colors.textDark }}>{t("startTime")}</label>
            <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
              <select
                value={newTimer.hour}
                onChange={(event) => setNewTimer((prev) => ({ ...prev, hour: event.target.value }))}
                className="h-11 rounded-md border px-3 text-sm"
                style={{ borderColor: colors.creamDark, color: colors.textDark, background: isDark ? "#0f1d16" : "white" }}
              >
                <option value="">Hour</option>
                {Array.from({ length: 12 }, (_, index) => String(index + 1)).map((hour) => (
                  <option key={hour} value={hour}>{hour}</option>
                ))}
              </select>
              <select
                value={newTimer.minute}
                onChange={(event) => setNewTimer((prev) => ({ ...prev, minute: event.target.value }))}
                className="h-11 rounded-md border px-3 text-sm"
                style={{ borderColor: colors.creamDark, color: colors.textDark, background: isDark ? "#0f1d16" : "white" }}
              >
                {Array.from({ length: 12 }, (_, index) => String(index * 5).padStart(2, "0")).map((minute) => (
                  <option key={minute} value={minute}>{minute}</option>
                ))}
              </select>
              <div className="inline-flex rounded-md border overflow-hidden" style={{ borderColor: colors.creamDark }}>
                {["AM", "PM"].map((period) => (
                  <button
                    key={period}
                    type="button"
                    onClick={() => setNewTimer((prev) => ({ ...prev, period }))}
                    className={`px-3 text-sm font-medium ${newTimer.period === period ? "bg-green-600 text-white" : ""}`}
                    style={newTimer.period === period ? {} : { color: colors.textMid, background: isDark ? "#0f1d16" : "white" }}
                  >
                    {period}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block" style={{ color: colors.textDark }}>{t("duration")}</label>
            <Input type="number" min="1" max="480" placeholder="e.g., 30" value={newTimer.duration} onChange={(event) => setNewTimer((prev) => ({ ...prev, duration: event.target.value }))} className="w-full" />
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block" style={{ color: colors.textDark }}>{t("days")}</label>
            <div className="flex gap-2 flex-wrap">
              {days.map((day, index) => (
                <button
                  key={day}
                  type="button"
                  onClick={() => {
                    setNewTimer((prev) => ({
                      ...prev,
                      days: prev.days.includes(index) ? prev.days.filter((value) => value !== index) : [...prev.days, index],
                    }));
                  }}
                  className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${newTimer.days.includes(index) ? "bg-green-500 text-white border-green-500" : "bg-white border-gray-200 hover:border-gray-300"}`}
                  style={newTimer.days.includes(index) ? {} : { color: colors.textMid }}
                >
                  {day}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <Button variant="outline" onClick={closeTimerModal} className="flex-1">{t("cancel")}</Button>
          <Button onClick={handleAddTimer} className="flex-1 bg-green-600 hover:bg-green-700">{t("saveTimer")}</Button>
        </div>
      </div>
    </div>
  );
}

export default function PumpControlPanel({
  colors,
  isDark,
  userData,
  pumps,
  pumpUpdating,
  scheduledTimers,
  showTimerModal,
  newTimer,
  setNewTimer,
  t,
  togglePump,
  openTimerModal,
  closeTimerModal,
  removeTimer,
  handleAddTimer,
  formatTime,
  formatTimerStartTime,
}) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PumpCard
          id="pump1"
          name="Pump 1"
          zone={`Zone A - ${displayValue(userData.zoneA)}`}
          pump={pumps.pump1}
          colors={colors}
          pumpUpdating={pumpUpdating}
          scheduledTimers={scheduledTimers}
          t={t}
          togglePump={togglePump}
          openTimerModal={openTimerModal}
          removeTimer={removeTimer}
          formatTime={formatTime}
          formatTimerStartTime={formatTimerStartTime}
        />
        <PumpCard
          id="pump2"
          name="Pump 2"
          zone={`Zone B - ${displayValue(userData.zoneB)}`}
          pump={pumps.pump2}
          colors={colors}
          pumpUpdating={pumpUpdating}
          scheduledTimers={scheduledTimers}
          t={t}
          togglePump={togglePump}
          openTimerModal={openTimerModal}
          removeTimer={removeTimer}
          formatTime={formatTime}
          formatTimerStartTime={formatTimerStartTime}
        />
      </div>
      <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
        <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Weekly Irrigation Log</h3>
        <div className="h-44 flex items-center justify-center text-sm" style={{ color: colors.textLight }}>
          {EMPTY_DISPLAY}
        </div>
      </div>
      <TimerModal
        colors={colors}
        isDark={isDark}
        showTimerModal={showTimerModal}
        closeTimerModal={closeTimerModal}
        newTimer={newTimer}
        setNewTimer={setNewTimer}
        handleAddTimer={handleAddTimer}
        t={t}
      />
    </div>
  );
}
