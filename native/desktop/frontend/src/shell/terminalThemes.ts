import type { ITheme } from "@xterm/xterm";

// ANSI palettes for the terminals, tuned to the documentation's warm ink and
// paper hues and checked for legibility on their own backgrounds. The TUI paints
// its own theme, so it always uses the dark palette.
export const DARK_TERMINAL: ITheme = {
  background: "#1c1a17",
  foreground: "#e9e4da",
  cursor: "#e0785c",
  cursorAccent: "#1c1a17",
  selectionBackground: "#4a453c",
  black: "#1c1a17",
  red: "#e08376",
  green: "#7fb494",
  yellow: "#d9a441",
  blue: "#8aa4c8",
  magenta: "#c99ac2",
  cyan: "#7fb8b0",
  white: "#e9e4da",
  brightBlack: "#8f887b",
  brightRed: "#ec8a68",
  brightGreen: "#9cc9ac",
  brightYellow: "#e6bd6a",
  brightBlue: "#a8bedc",
  brightMagenta: "#dcb3d6",
  brightCyan: "#9dcfc8",
  brightWhite: "#ffffff",
};

export const LIGHT_TERMINAL: ITheme = {
  background: "#faf8f4",
  foreground: "#1c1a17",
  cursor: "#9e4029",
  cursorAccent: "#faf8f4",
  selectionBackground: "#e4ded4",
  black: "#1c1a17",
  red: "#b3362a",
  green: "#3a6249",
  yellow: "#7a4f0f",
  blue: "#3b5b8c",
  magenta: "#7d4a78",
  cyan: "#2f6b66",
  white: "#5f594f",
  brightBlack: "#6b655c",
  brightRed: "#9e4029",
  brightGreen: "#2e5039",
  brightYellow: "#5f3d0b",
  brightBlue: "#2d4770",
  brightMagenta: "#643b60",
  brightCyan: "#235450",
  brightWhite: "#1c1a17",
};
