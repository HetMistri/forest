import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { createLogger, installGlobalErrorLogging } from "./utils/logger";

const logger = createLogger("bootstrap");

logger.info("Frontend startup initiated", {
  mode: import.meta.env.MODE,
  url: window.location.href,
});

installGlobalErrorLogging();

const rootElement = document.getElementById("root");

if (!rootElement) {
  logger.error("Missing root element #root; app cannot mount");
  throw new Error("Missing root element #root");
}

logger.info("Mounting React root");

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

logger.info("React root mounted");
