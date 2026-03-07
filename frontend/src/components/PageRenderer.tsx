import React, { useEffect, useRef, useReducer } from "react";
import { useNavigate } from "react-router-dom";
import { fetchAndParsePage, type ParsedWPPage } from "../utils/wordpressParser";

interface PageRendererProps {
  /** Full URL of the WP HTML file, e.g. "/wp-pages/about-us/index.html" */
  fileUrl: string;
  /** Current React Router pathname — used for relative-link resolution */
  spaPathname?: string;
  /** Optional additional body CSS classes for this page */
  extraBodyClass?: string;
}

const injectedStyleIds = new Set<string>();

/** Inject a <link> or <style> tag into document.head, deduplicated by id/href */
function injectStyle(tag: string): void {
  const idMatch = tag.match(/\bid="([^"]+)"/i);
  const hrefMatch = tag.match(/\bhref="([^"]+)"/i);
  const key = idMatch?.[1] ?? hrefMatch?.[1] ?? tag.slice(0, 80);
  if (injectedStyleIds.has(key)) return;
  injectedStyleIds.add(key);
  const temp = document.createElement("div");
  temp.innerHTML = tag;
  const el = temp.firstElementChild;
  if (el) document.head.appendChild(el);
}

/** Re-execute inline <script> tags inside a container after HTML injection */
function rerunScripts(container: HTMLElement): void {
  const scripts = container.querySelectorAll<HTMLScriptElement>("script");
  scripts.forEach((oldScript) => {
    if (oldScript.src) return; // External scripts already loaded globally — skip
    const newScript = document.createElement("script");
    Array.from(oldScript.attributes).forEach((attr) => {
      newScript.setAttribute(attr.name, attr.value);
    });
    newScript.textContent = oldScript.textContent;
    oldScript.parentNode?.replaceChild(newScript, oldScript);
  });
}

/** Trigger Salient/nectar theme re-initialization after React render */
function reinitWordPress(): void {
  try {
    if (typeof window.NectarFront !== "undefined") {
      if (typeof window.NectarFront.reinit === "function") {
        window.NectarFront.reinit();
      } else if (typeof window.NectarFront.init === "function") {
        window.NectarFront.init();
      }
    }
    if (typeof window.jQuery === "function") {
      const $ = window.jQuery as CallableFunction;
      $(document).trigger("nectar_reinit");
      $(window).trigger("resize");
    }
  } catch {
    // Silently ignore if WP scripts aren't loaded yet
  }
}

// ---------------------------------------------------------------------------
// Fetch state reducer (avoids setState calls inside useEffect bodies)
// ---------------------------------------------------------------------------
type FetchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; page: ParsedWPPage }
  | { status: "error"; message: string };

type FetchAction =
  | { type: "fetch" }
  | { type: "success"; page: ParsedWPPage }
  | { type: "error"; message: string };

function fetchReducer(_state: FetchState, action: FetchAction): FetchState {
  switch (action.type) {
    case "fetch":
      return { status: "loading" };
    case "success":
      return { status: "success", page: action.page };
    case "error":
      return { status: "error", message: action.message };
  }
}

const PageRenderer: React.FC<PageRendererProps> = ({
  fileUrl,
  spaPathname,
  extraBodyClass,
}) => {
  const [state, dispatch] = useReducer(fetchReducer, { status: "idle" });
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Fetch and parse the WP page HTML
  useEffect(() => {
    let cancelled = false;
    dispatch({ type: "fetch" });
    fetchAndParsePage(fileUrl, spaPathname)
      .then((page) => {
        if (!cancelled) dispatch({ type: "success", page });
      })
      .catch((err: Error) => {
        if (!cancelled) dispatch({ type: "error", message: err.message });
      });
    return () => {
      cancelled = true;
    };
  }, [fileUrl, spaPathname]);

  // Apply body attributes after page data loads
  useEffect(() => {
    if (state.status !== "success") return;
    const { page } = state;
    const { bodyAttrs } = page;

    // Save original body state
    const originalClass = document.body.className;
    const originalAttrs: Record<string, string> = {};

    Object.entries(bodyAttrs).forEach(([key, value]) => {
      originalAttrs[key] = document.body.getAttribute(key) ?? "";
      if (key === "class") {
        document.body.className =
          value + (extraBodyClass ? " " + extraBodyClass : "");
      } else {
        document.body.setAttribute(key, value);
      }
    });

    // Inject head CSS from this page (deduped)
    page.headStyleLinks.forEach(injectStyle);

    // Inject inline styles from this page
    if (page.headInlineStyles) {
      const styleId = `wp-page-styles-${fileUrl.replace(/[^a-z0-9]/gi, "-")}`;
      if (!document.getElementById(styleId)) {
        const styleEl = document.createElement("style");
        styleEl.id = styleId;
        styleEl.textContent = page.headInlineStyles.replace(
          /<\/?style[^>]*>/gi,
          "",
        );
        document.head.appendChild(styleEl);
      }
    }

    return () => {
      // Restore original body state on unmount
      document.body.className = originalClass;
      Object.keys(bodyAttrs).forEach((key) => {
        if (key !== "class") {
          const orig = originalAttrs[key];
          if (orig) {
            document.body.setAttribute(key, orig);
          } else {
            document.body.removeAttribute(key);
          }
        }
      });
    };
  }, [state, extraBodyClass, fileUrl]);

  // After HTML is injected: re-run inline scripts and WP reinit
  useEffect(() => {
    if (state.status !== "success" || !containerRef.current) return;
    rerunScripts(containerRef.current);
    // Small delay to let DOM settle before WP reinit
    const timer = setTimeout(reinitWordPress, 100);
    return () => clearTimeout(timer);
  }, [state]);

  // Intercept internal link clicks → React Router navigation
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleClick = (e: MouseEvent): void => {
      const target = e.target as HTMLElement;
      const link = target.closest("a");
      if (!link) return;
      const href = link.getAttribute("href");
      if (!href) return;
      // Intercept root-relative paths that are page routes (not asset/external links)
      if (
        href.startsWith("/") &&
        !href.startsWith("//") &&
        !href.startsWith("/wp-content/") &&
        !href.startsWith("/wp-static/") &&
        !href.startsWith("/wp-includes/") &&
        !href.startsWith("/wp-json/") &&
        !href.startsWith("/wp-cdn/") &&
        !href.match(
          /\.(css|js|png|jpg|jpeg|gif|svg|ico|webp|woff|woff2|ttf|eot|pdf|zip|xml)$/i,
        )
      ) {
        e.preventDefault();
        navigate(href);
      }
    };

    container.addEventListener("click", handleClick);
    return () => container.removeEventListener("click", handleClick);
  }, [navigate, state]);

  if (state.status === "loading" || state.status === "idle") {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "sans-serif",
          background: "#fff",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              width: 48,
              height: 48,
              border: "3px solid #401c86",
              borderTopColor: "transparent",
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
              margin: "0 auto 16px",
            }}
          />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <p style={{ color: "#666" }}>Loading…</p>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div
        style={{
          padding: "2rem",
          textAlign: "center",
          fontFamily: "sans-serif",
        }}
      >
        <h2>Page Load Error</h2>
        <p style={{ color: "#c00" }}>{state.message}</p>
        <button
          onClick={() => navigate("/")}
          style={{ marginTop: "1rem", cursor: "pointer" }}
        >
          Return Home
        </button>
      </div>
    );
  }

  if (state.status !== "success") return null;

  return (
    <div
      ref={containerRef}
      id="wp-page-root"
      // biome-ignore lint/security/noDangerouslySetInnerHtml: intentional WP HTML injection
      dangerouslySetInnerHTML={{ __html: state.page.bodyContent }}
    />
  );
};

export default PageRenderer;
