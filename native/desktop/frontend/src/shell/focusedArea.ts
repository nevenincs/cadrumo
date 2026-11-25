import type { TerminalKind } from "./host";
import type { Maximized } from "./layout";

type Area = Exclude<Maximized, null>;

/** The workspace area that holds focus, the documentation frame included. */
export const focusedArea = (): Area | "rail" | null => {
  const element = document.activeElement;
  if (!element || element === document.body) return null;
  if (element.closest(".pane-agent")) return "agent";
  if (element.closest(".pane-docs")) return "docs";
  if (element.closest(".pane-tui")) return "tui";
  if (
    element.closest(
      '[data-dock-pane="console"], [data-dock-pane="python"], [data-dock-pane="logs"]',
    )
  )
    return "panel";
  if (element.closest(".rail")) return "rail";
  return null;
};

export const activeTerminal = (): TerminalKind | null => {
  const owner = document.activeElement?.closest<HTMLElement>("[data-terminal]");
  const kind = owner?.dataset.terminal;
  return kind === "console" || kind === "python" || kind === "tui"
    ? kind
    : null;
};
