// Composes pump controls and timer UI inside an error boundary.
import ErrorBoundary from "../ErrorBoundary";
import PumpControlPanel from "./PumpControlPanel";

export default function PumpSection(props) {
  return (
    <ErrorBoundary>
      <PumpControlPanel {...props} />
    </ErrorBoundary>
  );
}
