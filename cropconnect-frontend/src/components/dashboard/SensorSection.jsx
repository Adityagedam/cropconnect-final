// Composes the dashboard sensor panel inside an error boundary.
import ErrorBoundary from "../ErrorBoundary";
import SensorPanel from "./SensorPanel";

export default function SensorSection(props) {
  return (
    <ErrorBoundary>
      <SensorPanel {...props} />
    </ErrorBoundary>
  );
}
