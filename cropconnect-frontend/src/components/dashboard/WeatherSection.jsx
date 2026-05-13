// Composes the weather panel inside an error boundary.
import ErrorBoundary from "../ErrorBoundary";
import WeatherPanel from "./WeatherPanel";

export default function WeatherSection(props) {
  return (
    <ErrorBoundary>
      <WeatherPanel {...props} />
    </ErrorBoundary>
  );
}
