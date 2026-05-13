import { BarChart3, Brain, RefreshCw } from "lucide-react";
import { Button } from "../ui/button";

const EMPTY_DISPLAY = "--";

const numericOrNull = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const displayRupees = (value) => {
  const number = numericOrNull(value);
  return number === null ? EMPTY_DISPLAY : `Rs ${number.toLocaleString("en-IN")}`;
};

const isPresent = (value) => value !== null && value !== undefined && value !== "";
const displayValue = (value, suffix = "") => (isPresent(value) ? `${value}${suffix}` : EMPTY_DISPLAY);

const MarketSkeleton = () => (
  <div className="space-y-3" aria-label="Loading market prices">
    {Array.from({ length: 4 }).map((_, index) => (
      <div key={index} className="flex items-center justify-between gap-4 rounded-lg p-3">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 animate-pulse rounded-lg bg-slate-100" />
          <div>
            <div className="h-4 w-28 animate-pulse rounded bg-slate-200" />
            <div className="mt-2 h-3 w-44 animate-pulse rounded bg-slate-100" />
          </div>
        </div>
        <div className="h-5 w-20 animate-pulse rounded bg-slate-100" />
      </div>
    ))}
  </div>
);

export default function MarketPanel({
  colors,
  marketData,
  marketError,
  marketLoading,
  marketInsight,
  marketInsightError,
  marketInsightLoading,
  getUserMarketLocation,
  loadMarketPrices,
  loadMarketInsight,
}) {
  const prices = Array.isArray(marketData?.prices) ? marketData.prices : [];
  const mandis = Array.isArray(marketData?.mandis) ? marketData.mandis : [];
  const marketLocation = marketData?.requestedLocation || getUserMarketLocation() || EMPTY_DISPLAY;
  const marketMessage = marketError || marketData?.message || "";

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div>
              <h3 className="font-semibold" style={{ color: colors.textDark }}>Latest Mandi Prices</h3>
              <p className="text-xs mt-1" style={{ color: colors.textLight }} data-dynamic-value>
                {marketLocation}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {marketLoading && <span className="text-xs" style={{ color: colors.textLight }}>Loading</span>}
              <Button
                type="button"
                onClick={() => loadMarketPrices()}
                disabled={marketLoading}
                className="h-9 px-3"
                style={{ background: colors.greenMid, color: colors.cream }}
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${marketLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>
          </div>
          {marketLoading && !prices.length ? (
            <MarketSkeleton />
          ) : (
          <div className="space-y-3">
            {prices.map((crop, index) => (
              <div key={`${crop.market || "market"}-${crop.commodity || "commodity"}-${crop.arrivalDate || index}`} className="flex items-center justify-between gap-4 p-3 rounded-lg hover:bg-gray-50 transition-colors">
                <div className="flex items-center gap-3">
                  <span className="p-2 rounded-lg bg-green-50 text-green-700">
                    <BarChart3 className="w-5 h-5" />
                  </span>
                  <div>
                    <p className="font-medium" style={{ color: colors.textDark }}>
                      {crop.commodity || EMPTY_DISPLAY}
                    </p>
                    <p className="text-xs" style={{ color: colors.textLight }} data-dynamic-value>
                      {[crop.market, crop.district, crop.state].filter(Boolean).join(", ") || EMPTY_DISPLAY}
                    </p>
                    <p className="text-xs" style={{ color: colors.textLight }}>
                      Variety: {crop.variety || EMPTY_DISPLAY} | Grade: {crop.grade || EMPTY_DISPLAY}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-mono font-bold" style={{ color: colors.textDark }} data-dynamic-value>
                    {displayRupees(crop.modalPrice)}
                  </p>
                  <p className="text-xs" style={{ color: colors.textLight }} data-dynamic-value>
                    {displayRupees(crop.minPrice)} - {displayRupees(crop.maxPrice)}
                  </p>
                  <p className="text-xs" style={{ color: colors.textLight }} data-dynamic-value>
                    {crop.arrivalDate || EMPTY_DISPLAY}
                  </p>
                </div>
              </div>
            ))}
            {!prices.length && (
              <div className="p-6 text-center text-sm" style={{ color: colors.textLight }}>
                {marketLoading ? "Loading live mandi prices..." : (marketMessage || EMPTY_DISPLAY)}
              </div>
            )}
          </div>
          )}
        </div>

        <div className="space-y-4">
          {mandis.map((mandi, idx) => (
            <div key={`${mandi.name || "mandi"}-${mandi.district || idx}`} className="p-5 rounded-xl" style={{ background: idx === 0 ? `linear-gradient(135deg, ${colors.greenDark}, #0f2a1f)` : `linear-gradient(135deg, ${colors.terracotta}, #a0522d)` }}>
              <h3 className="font-semibold mb-3" style={{ color: colors.cream }}>{mandi.name || EMPTY_DISPLAY}</h3>
              <p className="text-sm mb-3" style={{ color: colors.creamDark }} data-dynamic-value>
                {[mandi.district, mandi.state].filter(Boolean).join(", ") || EMPTY_DISPLAY}
              </p>
              <div className="flex flex-wrap gap-2">
                {(Array.isArray(mandi.commodities) ? mandi.commodities : []).map((item, itemIndex) => (
                  <span key={`${item.commodity || "commodity"}-${itemIndex}`} className="px-2 py-1 text-xs rounded-full" style={{ background: "rgba(255,255,255,0.15)", color: colors.cream }} data-dynamic-value>
                    {item.commodity || EMPTY_DISPLAY}: {displayRupees(item.modalPrice)}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {!mandis.length && (
            <div className="p-6 rounded-xl bg-white border border-[#e8e3d8] text-center text-sm" style={{ color: colors.textLight }}>
              {marketLoading ? "Loading nearby mandis..." : EMPTY_DISPLAY}
            </div>
          )}
        </div>
      </div>

      <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold" style={{ color: colors.textDark }}>AI Market Advice</h3>
            <p className="text-xs mt-1" style={{ color: colors.textLight }}>
              Uses live mandi records plus your profile and latest ESP32 context.
            </p>
          </div>
          <Button
            type="button"
            onClick={loadMarketInsight}
            disabled={marketInsightLoading}
            className="h-9 px-3"
            style={{ background: colors.terracotta, color: colors.cream }}
          >
            <Brain className="w-4 h-4 mr-2" />
            {marketInsightLoading ? "Analyzing" : "Use AI"}
          </Button>
        </div>
        <div className="p-4 rounded-lg bg-green-50 text-sm" style={{ color: colors.textDark }} data-dynamic-value>
          {marketInsightLoading
            ? "AI is checking the live market feed..."
            : marketInsight?.summary || marketInsightError || EMPTY_DISPLAY}
        </div>
        {(marketInsight?.recommendations || []).length > 0 && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
            {marketInsight.recommendations.map((item, index) => (
              <div key={`${item.title || "recommendation"}-${index}`} className="p-4 rounded-lg border border-[#e8e3d8] bg-gray-50">
                <div className="flex items-start justify-between gap-3">
                  <h4 className="font-medium" style={{ color: colors.textDark }}>{item.title || EMPTY_DISPLAY}</h4>
                  <span className="text-[11px] px-2 py-1 rounded-full bg-white" style={{ color: colors.textMid }}>
                    {item.confidence || "low"}
                  </span>
                </div>
                <p className="mt-2 text-sm" style={{ color: colors.textMid }} data-dynamic-value>{item.action || EMPTY_DISPLAY}</p>
                <p className="mt-2 text-xs" style={{ color: colors.textLight }} data-dynamic-value>{item.reason || EMPTY_DISPLAY}</p>
              </div>
            ))}
          </div>
        )}
        {(marketInsight?.watch || []).length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {marketInsight.watch.map((item, index) => (
              <span key={`${item}-${index}`} className="px-3 py-1 rounded-full text-xs bg-amber-50 text-amber-800" data-dynamic-value>
                {item}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
        <h3 className="font-semibold mb-4" style={{ color: colors.textDark }}>Market Source</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="p-3 rounded-lg bg-gray-50">
            <p className="text-xs" style={{ color: colors.textLight }}>Source</p>
            <p style={{ color: colors.textDark }}>{marketData?.source || EMPTY_DISPLAY}</p>
          </div>
          <div className="p-3 rounded-lg bg-gray-50">
            <p className="text-xs" style={{ color: colors.textLight }}>Records</p>
            <p className="font-mono" style={{ color: colors.textDark }} data-dynamic-value>{displayValue(marketData?.recordsCount)}</p>
          </div>
          <div className="p-3 rounded-lg bg-gray-50">
            <p className="text-xs" style={{ color: colors.textLight }}>Updated</p>
            <p className="font-mono text-xs" style={{ color: colors.textDark }} data-dynamic-value>{marketData?.updatedAt || EMPTY_DISPLAY}</p>
          </div>
        </div>
        <div className="mt-4 p-4 rounded-lg bg-amber-50 text-sm text-amber-800" data-dynamic-value>
          {marketMessage || "Prices are pulled from the live government mandi feed for your saved profile location."}
        </div>
      </div>
    </div>
  );
}
