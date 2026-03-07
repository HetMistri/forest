export type LogLevel = "debug" | "info" | "warn" | "error";

const SHOULD_LOG =
  import.meta.env.DEV || import.meta.env.VITE_FRONTEND_DEBUG === "true";

function isoTimestamp(): string {
  return new Date().toISOString();
}

function callConsole(
  level: LogLevel,
  message: string,
  payload?: unknown,
): void {
  if (!SHOULD_LOG) {
    return;
  }

  if (payload !== undefined) {
    console[level](message, payload);
    return;
  }

  console[level](message);
}

export function logWithScope(
  scope: string,
  level: LogLevel,
  message: string,
  payload?: unknown,
): void {
  callConsole(level, `[${isoTimestamp()}] [${scope}] ${message}`, payload);
}

export function createLogger(scope: string) {
  return {
    debug: (message: string, payload?: unknown) =>
      logWithScope(scope, "debug", message, payload),
    info: (message: string, payload?: unknown) =>
      logWithScope(scope, "info", message, payload),
    warn: (message: string, payload?: unknown) =>
      logWithScope(scope, "warn", message, payload),
    error: (message: string, payload?: unknown) =>
      logWithScope(scope, "error", message, payload),
  };
}

let globalHandlersInstalled = false;

export function installGlobalErrorLogging(): void {
  if (globalHandlersInstalled || !SHOULD_LOG) {
    return;
  }

  globalHandlersInstalled = true;
  const logger = createLogger("global");

  window.addEventListener("error", (event) => {
    logger.error("Uncaught error", {
      message: event.message,
      fileName: event.filename,
      line: event.lineno,
      column: event.colno,
      error: event.error,
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    logger.error("Unhandled promise rejection", {
      reason: event.reason,
    });
  });
}
