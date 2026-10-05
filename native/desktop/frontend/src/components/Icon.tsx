import type { ReactNode } from "react";

// Bundled inline icons: the webview CSP admits no icon font or CDN.
// 20px grid, 1.6 stroke, currentColor.
const PATHS: Record<string, ReactNode> = {
  search: (
    <>
      <circle cx="9" cy="9" r="5.5" />
      <path d="m13 13 4 4" />
    </>
  ),
  book: (
    <>
      <path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H15v12H5.5A1.5 1.5 0 0 0 4 16.5z" />
      <path d="M4 16.5A1.5 1.5 0 0 0 5.5 18H15v-3" />
      <path d="M7.5 6.5h4.5" />
    </>
  ),
  tui: (
    <>
      <rect x="2.5" y="3.5" width="15" height="13" rx="1.5" />
      <path d="M2.5 7h15" />
      <path d="M7 7v9.5" />
    </>
  ),
  console: (
    <>
      <rect x="2.5" y="3.5" width="15" height="13" rx="1.5" />
      <path d="m6 8 2.5 2L6 12" />
      <path d="M10 12.5h4" />
    </>
  ),
  python: (
    <>
      <path d="M10 2.8c-3 0-3.2 1.3-3.2 2.4v1.7H10v.6H5.4c-1.4 0-2.6 1-2.6 3.2s1.1 3.2 2.4 3.2h1.3v-1.8c0-1.4 1.2-2.6 2.6-2.6h3.1c1.2 0 2.1-1 2.1-2.2V5.2c0-1.2-1-2.4-3.2-2.4z" />
      <path d="M10 17.2c3 0 3.2-1.3 3.2-2.4v-1.7H10v-.6h4.6c1.4 0 2.6-1 2.6-3.2s-1.1-3.2-2.4-3.2h-1.3v1.8" />
      <circle cx="8.4" cy="4.8" r=".5" fill="currentColor" />
      <circle cx="11.6" cy="15.2" r=".5" fill="currentColor" />
    </>
  ),
  logs: <path d="M4 5h12M4 8.5h12M4 12h8M4 15.5h10" />,
  settings: (
    <>
      <circle cx="10" cy="10" r="2.5" />
      <path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4" />
    </>
  ),
  splitRow: (
    <>
      <rect x="2.5" y="3.5" width="15" height="13" rx="1.5" />
      <path d="M10 3.5v13" />
    </>
  ),
  splitColumn: (
    <>
      <rect x="2.5" y="3.5" width="15" height="13" rx="1.5" />
      <path d="M2.5 10h15" />
    </>
  ),
  swap: (
    <>
      <path d="M5 7h10l-3-3" />
      <path d="M15 13H5l3 3" />
    </>
  ),
  maximize: (
    <>
      <path d="M11.5 3.5h5v5" />
      <path d="M8.5 16.5h-5v-5" />
      <path d="m16.5 3.5-5 5M3.5 16.5l5-5" />
    </>
  ),
  restore: (
    <>
      <path d="M8.5 3.5v5h-5" />
      <path d="M11.5 16.5v-5h5" />
      <path d="m3.5 3.5 5 5M16.5 16.5l-5-5" />
    </>
  ),
  chevronDown: <path d="m6 8 4 4 4-4" />,
  close: <path d="m5.5 5.5 9 9m0-9-9 9" />,
  back: <path d="M12 5 7 10l5 5" />,
  forward: <path d="m8 5 5 5-5 5" />,
  copy: (
    <>
      <rect x="7" y="7" width="9" height="9" rx="1.5" />
      <path d="M4 13V5.5A1.5 1.5 0 0 1 5.5 4H13" />
    </>
  ),
  arrow: <path d="M4 10h11m-4-4 4 4-4 4" />,
  page: (
    <>
      <path d="M5.5 2.5h6l3 3v12h-9z" />
      <path d="M11.5 2.5v3h3" />
    </>
  ),
  term: <path d="M4 5h12M4 10h12M4 15h7" />,
  zoom: (
    <>
      <circle cx="9" cy="9" r="5.5" />
      <path d="m13 13 4 4M7 9h4M9 7v4" />
    </>
  ),
};

export type IconSize = "xs" | "s" | "m" | "l";

export function Icon({ name, size = "l" }: { name: string; size?: IconSize }) {
  return (
    <svg
      className={`icon icon-${size}`}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}
