// The postMessage bridge between the shell document and the documentation
// frame: the envelopes each side posts and what they carry.

// ---------------------------------------------------------------------------
// Documentation bridge
// ---------------------------------------------------------------------------

/**
 * Every bridge message is a `window.postMessage` envelope addressed to the
 * peer's exact origin. Each side reads a message only when its `source` is the
 * peer window and its `origin` is the peer origin. An unknown `type` is
 * ignored; another `version` or a malformed known type is refused. The
 * envelope never carries the launch token.
 */
export type BridgeEnvelope<Type extends string> = {
  channel: "cadrumo-desktop";
  version: 1;
  type: Type;
};

export type DocsTheme = "auto" | "light" | "dark";

/**
 * Optional page bridge capabilities a page announces in `ready`. Send a
 * message that needs one only when the page lists it in `ready.features`.
 */
export type BridgeFeature =
  "search" | "navigate" | "home" | "appearance" | (string & {});

export type DocsLink = {
  /** Absolute URL. */
  href: string;
  /** True when the link leaves the documentation origin. */
  external: boolean;
};

/**
 * Documentation result kinds from the docs search controller. Open:
 * the index also carries `legal` records, and a navigation title with no
 * kind of its own arrives as `page`.
 */
export type DocsResultKind =
  "concept" | "cli" | "casilla" | "page" | (string & {});

/**
 * One documentation search result. Results arrive in the docs search
 * controller's own ranking: term, casilla and command cards above pages.
 */
export type DocsSearchResult = {
  kind: DocsResultKind;
  title: string;
  /** An absolute documentation-origin URL; the page never sends another origin. */
  url: string;
  /** Plain text, never HTML; empty when the result has no excerpt. */
  excerpt: string;
  /**
   * Match ranges into `excerpt` as sorted, non-overlapping `[start, end)`
   * offsets in UTF-16 code units, the indices `String.prototype.slice` takes.
   */
  ranges: Array<readonly [start: number, end: number]>;
  /**
   * The controller's localized category line, such as
   * `Casilla · Modelo 200 · 00562`; empty when it has none. Every page that
   * answers `search` sends it.
   */
  crumb?: string;
};

// Documentation page to shell.

export type DocsReady = BridgeEnvelope<"ready"> & {
  url: string;
  title: string;
  lang: string;
  theme: DocsTheme;
  /**
   * Absent on pages that predate the optional capabilities; enable a
   * feature only when listed.
   */
  features?: BridgeFeature[];
};

export type DocsLocation = BridgeEnvelope<"location"> & {
  url: string;
  title: string;
};

export type DocsThemeReport = BridgeEnvelope<"theme"> & { theme: DocsTheme };

/** A relayed shell chord; `id` is the chord id the shell sent in `keymap`. */
export type DocsShortcut = BridgeEnvelope<"shortcut"> & { id: string };

/**
 * A link leaving the documentation origin. Act on it only while
 * `navigator.userActivation.isActive`, under a rate limit, and only through
 * `open_external`.
 */
export type DocsOpenExternal = BridgeEnvelope<"open-external"> & {
  url: string;
};

/** Coordinates are in the frame's viewport CSS pixels, whatever the zoom. */
export type DocsContextMenu = BridgeEnvelope<"context-menu"> & {
  x: number;
  y: number;
  /** At most 65,536 characters. */
  selection: string;
  link: DocsLink | null;
  /**
   * False when the keyboard opened the menu (Shift+F10 or the menu key),
   * true for a pointer. Absent on pages that predate keyboard menus; read
   * `pointer !== false` as pointer-opened.
   */
  pointer?: boolean;
};

/**
 * The answer to a `search` request with the same `id`; sent only by a page
 * that lists `search` in `ready.features`.
 */
export type DocsSearchResults = BridgeEnvelope<"search-results"> & {
  id: string;
  results: DocsSearchResult[];
};

/** The accepted search is still running; the final answer remains search-results. */
export type DocsSearchProgress = BridgeEnvelope<"search-progress"> & {
  id: string;
};

export type DocsToShell =
  | (BridgeEnvelope<"language-change"> & { language: string })
  | DocsReady
  | DocsLocation
  | DocsThemeReport
  | DocsShortcut
  | DocsOpenExternal
  | DocsContextMenu
  | DocsSearchProgress
  | DocsSearchResults;

// Shell to documentation page.

/** Matched on `KeyboardEvent.code`; an omitted modifier means not pressed. */
export type BridgeChord = {
  /** At most 64 characters. */
  id: string;
  /** A `KeyboardEvent.code`, at most 32 characters. */
  code: string;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  metaKey?: boolean;
};

/** Replaces the page's chord list; at most 64 chords. */
export type ShellKeymap = BridgeEnvelope<"keymap"> & { chords: BridgeChord[] };

export type ShellCommand = BridgeEnvelope<"command"> &
  (
    | { name: "back" }
    | { name: "forward" }
    | { name: "open-search" }
    /**
     * An absolute URL on the documentation origin, at most 4,096 characters;
     * anything else is refused. Optional; send only when the page lists
     * `navigate` in `ready.features`.
     */
    | { name: "navigate"; url: string }
    /**
     * The root of the language the shown page belongs to: the target of the
     * page's own brand link, which is the docs manifest's entry for that
     * language. Optional; send only when the page lists `home` in
     * `ready.features`.
     */
    | { name: "home" }
  );

/** Documentation zoom, 0.5 to 2.0; 1 restores the page's own size. */
export type ShellZoom = BridgeEnvelope<"zoom"> & { factor: number };

/**
 * A bounded search, answered by one `search-results` with the same `id`. A
 * refused request is never answered. A blank query is answered with no
 * results. Optional; send only when the page lists `search` in
 * `ready.features`.
 */
export type ShellSearch = BridgeEnvelope<"search"> & {
  /** At most 64 characters; at most one request in flight per `id`. */
  id: string;
  /** At most 256 characters. At most eight searches are in flight at once. */
  query: string;
  /** An integer from 1 to 50. */
  limit: number;
};

/**
 * Applied the way Furo's own toggle applies a theme, and persisted the same
 * way for later pages; answered by one `theme` report. `auto` hands the
 * choice back to the page's toggle. Optional; send only when the page lists
 * `appearance` in `ready.features`.
 */
export type ShellAppearance = BridgeEnvelope<"appearance"> & {
  theme: DocsTheme;
};

export type ShellToDocs =
  ShellKeymap | ShellCommand | ShellZoom | ShellSearch | ShellAppearance;

export type BridgeMessage = DocsToShell | ShellToDocs;
