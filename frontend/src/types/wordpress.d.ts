/**
 * Type declarations for WordPress / Salient theme globals.
 *
 * These properties are injected into `window` by:
 *   – nectar-frontend-js (NectarFront, nectarOptions, nectarLove, nectar_front_i18n)
 *   – jQuery loaded from the local CDN cache (jQuery, $)
 *   – WP Bakery Visual Composer (wpbCustomElement)
 *   – Ajax Search Lite (ASL)
 *   – WP stats tracker (_stq)
 */

export interface NectarOptions {
  delay_js: string;
  smooth_scroll: string;
  smooth_scroll_strength: string;
  quick_search: string;
  react_compat: string;
  header_entrance: string;
  body_border_func: string;
  ajax_add_to_cart: string;
  [key: string]: string;
}

export interface NectarLove {
  ajaxurl: string;
  postID: string;
  rooturl: string;
  disqusComments: string;
  loveNonce: string;
  mapApiKey: string;
}

export interface NectarFrontI18n {
  menu: string;
  next: string;
  previous: string;
  close: string;
}

export interface NectarFront {
  init: () => void;
  reinit?: () => void;
}

declare global {
  interface Window {
    /** Salient theme front-end controller */
    NectarFront?: NectarFront;
    /** jQuery — loaded globally from the local CDN cache */
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    jQuery?: (...args: any[]) => any;
    /** jQuery shorthand alias */
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    $?: (...args: any[]) => any;
    /** Salient theme options object */
    nectarOptions?: NectarOptions;
    /** Salient like/love widget data */
    nectarLove?: NectarLove;
    /** Salient i18n strings */
    nectar_front_i18n?: NectarFrontI18n;
    /** Ajax Search Lite plugin global */
    ASL?: Record<string, unknown>;
    /** WP stats push queue */
    _stq?: unknown[];
    /** WP Bakery custom element version flag */
    wpbCustomElement?: number;
    /** WP emoji settings */
    _wpemojiSettings?: unknown;
  }
}


export {};
