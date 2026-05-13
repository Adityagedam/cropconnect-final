// Composes the AI chat panel inside an error boundary.
import ErrorBoundary from "../ErrorBoundary";
import AiChatPanel from "./AiChatPanel";

export default function AiSection(props) {
  return (
    <ErrorBoundary>
      <AiChatPanel {...props} />
    </ErrorBoundary>
  );
}
