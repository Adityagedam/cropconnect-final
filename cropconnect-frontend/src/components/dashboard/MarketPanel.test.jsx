import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MarketPanel from "./MarketPanel";

const colors = {
  textDark: "#111",
  textLight: "#666",
  textMid: "#444",
  greenMid: "#286",
  greenDark: "#173",
  terracotta: "#b65",
  cream: "#fff",
  creamDark: "#eee",
};

describe("MarketPanel", () => {
  it("renders live mandi prices and triggers refresh", () => {
    const loadMarketPrices = vi.fn();

    render(
      <MarketPanel
        colors={colors}
        marketData={{
          requestedLocation: "Pune, Maharashtra",
          source: "Data.gov.in live Agmarknet mandi prices",
          recordsCount: 1,
          updatedAt: "2026-05-13T00:00:00Z",
          prices: [
            {
              commodity: "Tomato",
              market: "Pune",
              district: "Pune",
              state: "Maharashtra",
              variety: "Local",
              grade: "FAQ",
              modalPrice: 1500,
              minPrice: 1200,
              maxPrice: 1800,
              arrivalDate: "13/05/2026",
            },
          ],
          mandis: [],
        }}
        marketError=""
        marketLoading={false}
        marketInsight={null}
        marketInsightError=""
        marketInsightLoading={false}
        getUserMarketLocation={() => "Fallback"}
        loadMarketPrices={loadMarketPrices}
        loadMarketInsight={vi.fn()}
      />
    );

    expect(screen.getByText("Latest Mandi Prices")).toBeInTheDocument();
    expect(screen.getByText("Tomato")).toBeInTheDocument();
    expect(screen.getByText("Rs 1,500")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));
    expect(loadMarketPrices).toHaveBeenCalledTimes(1);
  });
});
