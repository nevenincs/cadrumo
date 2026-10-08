import { useEffect, useState } from "react";
import type { TerminalFontSize } from "./layout";

// Reads canonical length tokens (src/tokens.css) as pixel numbers, for the
// few call sites that need a plain number instead of a CSS value: pointer
// drag math, a popover's own position/size estimate, and xterm's canvas font
// size. WebView2/WebKit apply the OS DPI scale to CSS pixels on their own, so
// nothing here does manual DPI math; a rem token converts through the root
// font size, which the user's own text-size setting can change, so callers
// re-read on resize.

function rootFontSizePx(): number {
  return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
}

/** Resolves a CSS length custom property (rem or px) to a pixel number. */
export function readPx(token: string, fallback: number): number {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(token)
    .trim();
  if (!raw) return fallback;
  const value = parseFloat(raw);
  if (!Number.isFinite(value)) return fallback;
  return raw.endsWith("rem") ? value * rootFontSizePx() : value;
}

/** A metric that tracks its token's pixel value across resize, so it follows
 * the window's effective layout (including the user's text-size setting)
 * without polling. */
export function useMetric(token: string, fallback: number): number {
  const [value, setValue] = useState(() => readPx(token, fallback));
  useEffect(() => {
    const read = () => setValue(readPx(token, fallback));
    read();
    window.addEventListener("resize", read);
    return () => window.removeEventListener("resize", read);
  }, [token, fallback]);
  return value;
}

const TERMINAL_FONT_TOKEN: Record<TerminalFontSize, string> = {
  small: "--term-font-small",
  medium: "--term-font-medium",
  large: "--term-font-large",
  "x-large": "--term-font-xlarge",
};

const TERMINAL_FONT_FALLBACK: Record<TerminalFontSize, number> = {
  small: 12,
  medium: 13,
  large: 14,
  "x-large": 16,
};

/** A terminal font-size step's current pixel value, for labelling the step. */
export function terminalFontPx(step: TerminalFontSize): number {
  return readPx(TERMINAL_FONT_TOKEN[step], TERMINAL_FONT_FALLBACK[step]);
}

/** The chosen terminal font-size step, resolved to the pixel number xterm's
 * own canvas renderer needs. */
export function useTerminalFontSize(step: TerminalFontSize): number {
  return useMetric(TERMINAL_FONT_TOKEN[step], TERMINAL_FONT_FALLBACK[step]);
}
