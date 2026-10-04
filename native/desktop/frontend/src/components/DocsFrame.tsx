import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import type {
  BridgeChord,
  BridgeFeature,
  DocsLink,
  DocsSearchResult,
  DocsTheme,
} from "../ipc/contract";

const CHANNEL = "cadrumo-desktop";
const VERSION = 1;
const SEARCH_LIMIT = 8;
const SEARCH_TIMEOUT_MS = 4000;
const EXTERNAL_BURST = 3;
const EXTERNAL_WINDOW_MS = 10000;
const MAX_SELECTION = 65536;
// The page's own bounds; a request beyond them is refused without an answer.
const MAX_QUERY = 256;
const MAX_URL = 4096;
const LINK_SCHEMES = new Set(["http:", "https:", "mailto:"]);

function hasLinkScheme(href: string): boolean {
  try {
    return LINK_SCHEMES.has(new URL(href).protocol);
  } catch {
    return false;
  }
}

export type DocsMenuRequest = {
  /** Shell viewport coordinates. */
  x: number;
  y: number;
  /** False when the menu key opened it, so it belongs at x, y. */
  pointer: boolean;
  selection: string;
  link: DocsLink | null;
};

export type DocsFrameApi = {
  focus(): void;
  back(): void;
  forward(): void;
  /** Returns false when the documentation cannot navigate on request. */
  home(): boolean;
  navigate(url: string): boolean;
  openSearch(): void;
  hasFeature(feature: BridgeFeature): boolean;
  search(query: string): Promise<DocsSearchResult[]>;
};

type Props = {
  origin: string;
  entry: string;
  title: string;
  chords: BridgeChord[];
  zoom: number;
  /** A forced appearance, or null to leave the documentation's own toggle in charge. */
  appearance: DocsTheme | null;
  onReady: (info: { theme: DocsTheme; features: BridgeFeature[] }) => void;
  onTheme: (theme: DocsTheme) => void;
  onShortcut: (id: string) => void;
  onOpenExternal: (url: string) => void;
  onMenu: (request: DocsMenuRequest) => void;
};

function readTheme(value: unknown): DocsTheme {
  return value === "light" || value === "dark" ? value : "auto";
}

function readResults(
  value: unknown,
  origin: string,
): DocsSearchResult[] | null {
  if (!Array.isArray(value)) return null;
  const out: DocsSearchResult[] = [];
  for (const item of value as unknown[]) {
    if (!item || typeof item !== "object") return null;
    const r = item as Record<string, unknown>;
    const kind = r.kind;
    if (typeof kind !== "string" || !kind) return null;
    if (
      typeof r.title !== "string" ||
      typeof r.url !== "string" ||
      typeof r.excerpt !== "string"
    )
      return null;
    let url: URL;
    try {
      url = new URL(r.url);
    } catch {
      return null;
    }
    // A result may only point back into the documentation.
    if (url.origin !== origin) return null;
    const ranges = Array.isArray(r.ranges)
      ? (r.ranges as unknown[]).filter(
          (range): range is [number, number] =>
            Array.isArray(range) &&
            range.length === 2 &&
            range.every((n) => Number.isInteger(n)),
        )
      : [];
    out.push({
      kind,
      title: r.title,
      url: url.href,
      excerpt: r.excerpt,
      ranges,
      ...(typeof r.crumb === "string" && r.crumb ? { crumb: r.crumb } : {}),
    });
  }
  return out;
}

// The documentation runs on its own origin inside this frame; this component
// is the shell's end of the postMessage bridge. A message counts only when its
// source is this frame's window and its origin is exactly the docs origin.
// Features beyond the first bridge version are used only once the page
// announces them in `ready`.
export const DocsFrame = forwardRef<DocsFrameApi, Props>(
  function DocsFrame(props, ref) {
    const { origin, entry, title, chords, zoom, appearance } = props;
    const frame = useRef<HTMLIFrameElement>(null);
    const features = useRef<BridgeFeature[]>([]);
    const pending = useRef(
      new Map<string, (results: DocsSearchResult[] | null) => void>(),
    );
    const nextId = useRef(1);
    const externals = useRef<number[]>([]);
    const live = useRef(props);
    live.current = props;

    // Nothing is posted until a page has announced itself: before that the
    // frame may still hold a document on another origin. `ready` sends the
    // current keymap, zoom and appearance, so no earlier message is lost.
    const ready = useRef(false);
    const post = useCallback(
      (type: string, fields: Record<string, unknown> = {}) => {
        if (!ready.current) return;
        frame.current?.contentWindow?.postMessage(
          { channel: CHANNEL, version: VERSION, type, ...fields },
          origin,
        );
      },
      [origin],
    );

    useEffect(() => {
      const searches = pending.current;
      const receive = (event: MessageEvent) => {
        if (
          !frame.current ||
          event.source !== frame.current.contentWindow ||
          event.origin !== origin
        )
          return;
        const data = event.data as Record<string, unknown> | null;
        if (
          !data ||
          typeof data !== "object" ||
          data.channel !== CHANNEL ||
          data.version !== VERSION
        )
          return;
        const p = live.current;
        switch (data.type) {
          case "ready": {
            ready.current = true;
            const announced: unknown[] = Array.isArray(data.features)
              ? data.features
              : [];
            features.current = announced.filter(
              (f): f is BridgeFeature => typeof f === "string",
            );
            post("keymap", { chords: p.chords });
            post("zoom", { factor: p.zoom });
            if (p.appearance && features.current.includes("appearance"))
              post("appearance", { theme: p.appearance });
            p.onReady({
              theme: readTheme(data.theme),
              features: [...features.current],
            });
            break;
          }
          case "theme":
            p.onTheme(readTheme(data.theme));
            break;
          case "shortcut":
            // A page may only hand back a chord this shell published to it.
            // Any other id is refused: the documentation runs third-party
            // script and must not reach terminal or host actions by naming
            // them.
            if (
              typeof data.id === "string" &&
              p.chords.some((chord) => chord.id === data.id)
            )
              p.onShortcut(data.id);
            break;
          case "open-external": {
            // Only a link the person has just activated, and never a burst.
            const now = Date.now();
            externals.current = externals.current.filter(
              (at) => now - at < EXTERNAL_WINDOW_MS,
            );
            if (
              typeof data.url !== "string" ||
              !navigator.userActivation?.isActive
            )
              break;
            if (externals.current.length >= EXTERNAL_BURST) break;
            externals.current.push(now);
            p.onOpenExternal(data.url);
            break;
          }
          case "context-menu": {
            const element = frame.current;
            if (typeof data.x !== "number" || typeof data.y !== "number") break;
            const rect = element.getBoundingClientRect();
            const link = data.link as {
              href?: unknown;
              external?: unknown;
            } | null;
            p.onMenu({
              x: rect.left + element.clientLeft + data.x,
              y: rect.top + element.clientTop + data.y,
              // Pages built before the bridge reported it were pointer-opened.
              pointer: data.pointer !== false,
              // Bounded here as well as in the bridge: a hostile script can
              // post without the bridge.
              selection:
                typeof data.selection === "string"
                  ? data.selection.slice(0, MAX_SELECTION)
                  : "",
              link:
                link &&
                typeof link.href === "string" &&
                typeof link.external === "boolean" &&
                hasLinkScheme(link.href)
                  ? { href: link.href, external: link.external }
                  : null,
            });
            break;
          }
          case "search-results": {
            if (typeof data.id !== "string") break;
            const resolve = searches.get(data.id);
            if (!resolve) break;
            searches.delete(data.id);
            resolve(readResults(data.results, origin));
            break;
          }
          default:
        }
      };
      window.addEventListener("message", receive);
      return () => {
        window.removeEventListener("message", receive);
        for (const resolve of searches.values()) resolve(null);
        searches.clear();
      };
    }, [origin, post]);

    useEffect(() => {
      post("keymap", { chords });
    }, [chords, post]);

    useEffect(() => {
      post("zoom", { factor: zoom });
    }, [zoom, post]);

    useEffect(() => {
      if (appearance && features.current.includes("appearance"))
        post("appearance", { theme: appearance });
    }, [appearance, post]);

    useImperativeHandle(
      ref,
      () => ({
        focus: () => frame.current?.focus(),
        back: () => post("command", { name: "back" }),
        forward: () => post("command", { name: "forward" }),
        home: () => {
          if (!features.current.includes("home")) return false;
          post("command", { name: "home" });
          return true;
        },
        navigate: (url: string) => {
          if (!features.current.includes("navigate")) return false;
          // The page refuses anything else without answering, so check here.
          let target: URL;
          try {
            target = new URL(url);
          } catch {
            return false;
          }
          if (target.origin !== origin || target.href.length > MAX_URL)
            return false;
          post("command", { name: "navigate", url: target.href });
          return true;
        },
        openSearch: () => {
          frame.current?.focus();
          post("command", { name: "open-search" });
        },
        hasFeature: (feature) => features.current.includes(feature),
        search: (query: string) =>
          new Promise<DocsSearchResult[]>((resolve, reject) => {
            if (!features.current.includes("search")) {
              reject(new Error("docs-search-unavailable"));
              return;
            }
            const id = `search-${nextId.current++}`;
            const timer = window.setTimeout(() => {
              pending.current.delete(id);
              reject(new Error("docs-search-timeout"));
            }, SEARCH_TIMEOUT_MS);
            pending.current.set(id, (results) => {
              window.clearTimeout(timer);
              if (results) resolve(results);
              else reject(new Error("docs-search-malformed"));
            });
            post("search", {
              id,
              query: query.slice(0, MAX_QUERY),
              limit: SEARCH_LIMIT,
            });
          }),
      }),
      [post, origin],
    );

    return (
      <iframe ref={frame} className="docs-frame" title={title} src={entry} />
    );
  },
);
