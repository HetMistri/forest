/**
 * Utilities for parsing and processing WordPress HTTrack-mirrored HTML pages.
 * Handles head CSS injection, body content extraction, and link rewriting
 * for React SPA integration.
 *
 * Architecture: fully dynamic — any URL path maps to
 *   `/wp-pages${pathname}/index.html`  (or `/wp-pages/index.html` for root)
 * No hardcoded route map needed.
 */

// ---------------------------------------------------------------------------
// Path helpers
// ---------------------------------------------------------------------------

/**
 * Convert a React Router pathname to the static WP HTML file URL.
 *   "/"               → "/wp-pages/index.html"
 *   "/about-us"       → "/wp-pages/about-us/index.html"
 *   "/industries/agriculture" → "/wp-pages/industries/agriculture/index.html"
 */
export function pathToWpFile(pathname: string): string {
  const clean = pathname.replace(/\/$/, '');
  if (!clean || clean === '/') return '/wp-pages/index.html';
  return `/wp-pages${clean}/index.html`;
}

/**
 * Attempt to convert a WP/HTTrack href into a React SPA path.
 * Returns the SPA path string if it is an internal page link,
 * or null if the href should be left unchanged.
 */
function wpHrefToSpaPath(href: string, currentPathname?: string): string | null {
  if (!href) return null;

  if (
    href.startsWith('#') ||
    href.startsWith('mailto:') ||
    href.startsWith('tel:') ||
    href.startsWith('javascript:') ||
    href.startsWith('data:')
  ) return null;

  let path = href;

  // Absolute amnex.com URLs → strip domain
  if (/^https?:\/\/(www\.)?amnex\.com/i.test(path)) {
    path = path.replace(/^https?:\/\/(www\.)?amnex\.com/i, '');
  } else if (path.startsWith('http') || path.startsWith('//')) {
    return null; // truly external
  }

  // Skip WP asset paths (served as static files, not React routes)
  if (
    path.startsWith('/wp-content/') ||
    path.startsWith('/wp-includes/') ||
    path.startsWith('/wp-json/') ||
    path.startsWith('/feed/') ||
    /\.(css|js|png|jpg|jpeg|gif|svg|ico|webp|woff|woff2|ttf|eot|pdf|zip|xml|json|mp4|webm|ogg|mp3|txt)(\?|#|$)/i.test(path)
  ) return null;

  // Resolve HTTrack relative paths against current pathname
  if (!path.startsWith('/')) {
    if (currentPathname) {
      const base = `http://x${currentPathname.endsWith('/') ? currentPathname : currentPathname + '/'}`;
      try {
        path = new URL(path, base).pathname;
      } catch {
        return null;
      }
    } else {
      return null;
    }
  }

  // Normalize: remove trailing /index.html and trailing slash
  path = path.replace(/\/index\.html$/, '').replace(/\/$/, '') || '/';

  // Reject paths that look like files with extensions (missed above)
  if (path.split('/').pop()?.includes('.')) return null;

  return path;
}

// ---------------------------------------------------------------------------
// HTML rewriting
// ---------------------------------------------------------------------------

/** Rewrite internal WP hrefs to React SPA paths */
export function rewriteLinks(html: string, currentPathname?: string): string {
  return html.replace(/href="([^"]+)"/g, (_match, href) => {
    const spa = wpHrefToSpaPath(href, currentPathname);
    return spa !== null ? `href="${spa}"` : `href="${href}"`;
  });
}

// ---------------------------------------------------------------------------
// Head parsing
// ---------------------------------------------------------------------------

/** Extract all <link rel="stylesheet"> / <link rel="preconnect"> tags from <head> */
export function extractHeadStyleLinks(html: string): string[] {
  const headMatch = html.match(/<head[^>]*>([\s\S]*?)<\/head>/i);
  if (!headMatch) return [];
  const head = headMatch[1];
  const links: string[] = [];
  const linkRe = /<link[^>]+>/gi;
  let m: RegExpExecArray | null;
  while ((m = linkRe.exec(head)) !== null) {
    if (
      /rel=["']stylesheet["']/i.test(m[0]) ||
      /rel=["']preconnect["']/i.test(m[0])
    ) {
      links.push(m[0]);
    }
  }
  return links;
}

/** Extract all inline <style> blocks from <head> */
export function extractHeadInlineStyles(html: string): string {
  const headMatch = html.match(/<head[^>]*>([\s\S]*?)<\/head>/i);
  if (!headMatch) return '';
  const head = headMatch[1];
  const styles: string[] = [];
  const styleRe = /<style([^>]*)>([\s\S]*?)<\/style>/gi;
  let m: RegExpExecArray | null;
  while ((m = styleRe.exec(head)) !== null) {
    styles.push(`<style${m[1]}>${m[2]}</style>`);
  }
  return styles.join('\n');
}

// ---------------------------------------------------------------------------
// Body parsing
// ---------------------------------------------------------------------------

/** Parse all attributes from the <body> opening tag */
export function extractBodyAttributes(html: string): Record<string, string> {
  const bodyMatch = html.match(/<body([^>]*)>/i);
  if (!bodyMatch) return {};
  const attrsStr = bodyMatch[1];
  const attrs: Record<string, string> = {};
  const attrRe = /([\w-]+)(?:=(?:"([^"]*?)"|'([^']*?)'|(\S+)))?/g;
  let m: RegExpExecArray | null;
  while ((m = attrRe.exec(attrsStr)) !== null) {
    if (m[1]) attrs[m[1]] = m[2] ?? m[3] ?? m[4] ?? '';
  }
  return attrs;
}

/** Extract the inner HTML of the <body> element */
export function extractBodyContent(html: string): string {
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  return bodyMatch ? bodyMatch[1] : html;
}

// ---------------------------------------------------------------------------
// Artifact cleanup
// ---------------------------------------------------------------------------

/**
 * Strip HTTrack comment markers, rewrite absolute amnex.com URLs to
 * root-relative paths, and fix broken logo image references.
 *
 * HTTrack mirrored the animated SVG logos as empty .html files.
 * We replace them with the real logo PNG placed at /amnex-logo.png.
 */
export function cleanHttrackArtifacts(html: string): string {
  let result = html
    .replace(/<!-- Mirrored from[^>]+-->/gi, '')
    .replace(/<!-- Added by HTTrack[^>]+-->/gi, '')
    .replace(/<!-- \/Added by HTTrack -->/gi, '')
    .replace(/<!-- Page cached by[^>]+-->/gi, '');

  // Rewrite all absolute amnex.com URLs to root-relative.
  // Covers src, href, data-src, data-menu-img-src, background, url() etc.
  result = result.replace(/https?:\/\/(www\.)?amnex\.com\//gi, '/');

  // Fix broken logo images: HTTrack saved the animated SVG logos as empty
  // .html files. Replace both variants with the real logo PNG.
  result = result
    .replace(/\/wp-content\/uploads\/2025\/08\/Amnex-GPW-3\.html/gi, '/amnex-logo.png')
    .replace(/\/wp-content\/uploads\/2025\/08\/Amnex-GPW-White-2\.html/gi, '/amnex-logo.png')
    // Also handle relative paths (without leading slash) that appear in
    // pages at different nesting depths
    .replace(/wp-content\/uploads\/2025\/08\/Amnex-GPW-3\.html/gi, '/amnex-logo.png')
    .replace(/wp-content\/uploads\/2025\/08\/Amnex-GPW-White-2\.html/gi, '/amnex-logo.png');

  return result;
}

// ---------------------------------------------------------------------------
// Full pipeline
// ---------------------------------------------------------------------------

export interface ParsedWPPage {
  bodyContent: string;
  bodyAttrs: Record<string, string>;
  headStyleLinks: string[];
  headInlineStyles: string;
}

/**
 * Fetch a WP HTML file, clean HTTrack artefacts, rewrite links, and return
 * structured page data ready for React injection.
 *
 * @param fileUrl      e.g. "/wp-pages/about-us/index.html"
 * @param spaPathname  current React Router pathname (used for relative-link resolution)
 */
export async function fetchAndParsePage(
  fileUrl: string,
  spaPathname?: string,
): Promise<ParsedWPPage> {
  const response = await fetch(fileUrl);
  if (!response.ok) throw new Error(`HTTP ${response.status} — ${fileUrl}`);
  let html = await response.text();
  html = cleanHttrackArtifacts(html);
  html = rewriteLinks(html, spaPathname);

  return {
    bodyContent: extractBodyContent(html),
    bodyAttrs: extractBodyAttributes(html),
    headStyleLinks: extractHeadStyleLinks(html),
    headInlineStyles: extractHeadInlineStyles(html),
  };
}


