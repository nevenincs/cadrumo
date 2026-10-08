import type { FocusEvent } from "react";

/**
 * Brings what has just taken focus into view inside the surface that
 * scrolls it. A focus trap carries the keyboard from the last control of a
 * surface round to the first without scrolling to it, so on a surface taller
 * than its room the keyboard would otherwise be on something out of sight.
 * What is already in view is left where it is.
 */
export function revealFocused(event: FocusEvent<HTMLElement>): void {
  const taken = event.target;
  if (!(taken instanceof HTMLElement)) return;
  const room = event.currentTarget.getBoundingClientRect();
  const at = taken.getBoundingClientRect();
  if (at.top < room.top || at.bottom > room.bottom)
    taken.scrollIntoView({ block: "nearest" });
}
