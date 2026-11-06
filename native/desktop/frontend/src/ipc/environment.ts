// The host's account of itself and of the desktop it runs in, as the
// `about_info` and `desktop_environment` commands answer them. Field names
// and casing follow the host's serde output exactly.

import type { LogLevel } from "./contract";

// ---------------------------------------------------------------------------
// about_info
// ---------------------------------------------------------------------------

/** One name with its version, ordered by name. */
export type AboutNamed = { name: string; version: string };

/** A native binary of the installed package. Every field the package does
 * not state is null. */
export type AboutComponent = {
  name: string | null;
  role: string | null;
  path: string | null;
  version: string | null;
  build_id: string | null;
  build_type: string | null;
};

/** What this installation is: the installed package manifest's statement,
 * plus the desktop binary's own compile-time identity. A null is a value the
 * package or the build did not state; the shell says it is unavailable. */
export type AboutInfo = {
  product: string | null;
  display_version: string | null;
  version: string | null;
  build_id: string | null;
  build_type: string | null;
  build_date: string | null;
  channel: string | null;
  target: string | null;
  /** The bundled CPython runtime's version. */
  python: string | null;
  desktop: {
    version: string | null;
    build_id: string | null;
    build_type: "debug" | "release";
  };
  components: AboutComponent[];
  /** Null when the package does not bundle the agent. */
  agent: { version: string | null; dependencies: AboutNamed[] } | null;
  /** Bundled tools by name, for example `node`. */
  tools: Record<string, string>;
  distributions: AboutNamed[];
};

// ---------------------------------------------------------------------------
// desktop_environment
// ---------------------------------------------------------------------------

export type DocsLanguage = {
  /** Language code, for example `en`, `es`, `ca`, `hu`. */
  code: string;
  /**
   * The language's entry page from the docs manifest, as an absolute URL on
   * the documentation origin with its path segments percent-encoded. Use it
   * as given; do not rebuild it from `origin`.
   */
  entry: string;
};

export type DesktopLanguage = {
  language: string;
  persisted: boolean;
  profile: string | null;
  /** Monotonic host revision shared by reads, writes and observations. */
  revision: number;
};

export type DesktopEnvironment = {
  /** The output language Settings resolved for this profile. */
  outputLanguage: string;
  /** Initial minimum severity selected by the host; defaults to INFO. */
  logLevel: LogLevel;
  /** The package's statement of whether it carries the documentation. */
  docs: DesktopDocs;
};

export type DesktopDocs =
  | {
      state: "bundled";
      /** The documentation origin, computed by the host for this platform. */
      origin: string;
      languages: DocsLanguage[];
    }
  | { state: "notBundled" }
  /** Bundled, but this launch could not open it; everything else still works. */
  | { state: "unavailable" };
