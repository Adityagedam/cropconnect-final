// Composes the market panel inside an error boundary.
import ErrorBoundary from "../ErrorBoundary";
import MarketPanel from "./MarketPanel";

export default function MarketSection(props) {
  return (
    <ErrorBoundary>
      <MarketPanel {...props} />
    </ErrorBoundary>
  );
}
