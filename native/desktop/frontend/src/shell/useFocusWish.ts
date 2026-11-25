import { useCallback, useEffect, useRef, type RefObject } from "react";
import settings from "virtual:operational-settings";
import type { TerminalApi } from "../components/TerminalPane";
import type { TerminalKind } from "./host";

export function useFocusWish({
  signInButton,
  terminals,
}: {
  signInButton: RefObject<HTMLButtonElement | null>;
  terminals: RefObject<Partial<Record<TerminalKind, TerminalApi>>>;
}) {
  // Focus asked for a view that may not be on screen yet: showing it is a
  // state change, and that commits later than the request does. The wish is
  // kept and granted after the commit that shows the view, or dropped when
  // none does in time. Granted, it is kept for the rest of its life: a view
  // that is rebuilt as it starts takes its focus with it, and the commit
  // that follows gives it back, unless focus has gone somewhere by then.
  const wanted = useRef<{
    view: TerminalKind | "logs";
    since: number;
    granted?: boolean;
    waitingForTerminal?: boolean;
  } | null>(null);
  const grantFocus = useCallback(() => {
    const wish = wanted.current;
    if (!wish) return;
    if (
      !wish.waitingForTerminal &&
      performance.now() > wish.since + settings.focus_wish_ms
    ) {
      wanted.current = null;
      return;
    }
    if (wish.granted && document.activeElement !== document.body) return;
    // The sign-in dialog holds the keyboard while it is up: nothing behind
    // it is given focus, whatever was wished for before it opened. On its
    // way out it holds nothing, and a wish made then is granted at once.
    if (document.querySelector('.sign-in[data-state="open"]')) return;
    // A closing Radix menu keeps its focus scope until the exit animation
    // unmounts it. Retain the wish until the menu reports that it has closed.
    if (document.querySelector("[data-dock-menu]")) return;
    // Withheld, the TUI's pane holds the way in instead of a terminal.
    const wayIn = signInButton.current;
    if (wish.view === "tui" && wayIn && wayIn.offsetParent !== null) {
      wayIn.focus();
      wish.granted = true;
      return;
    }
    const target = document.querySelector<HTMLElement>(
      wish.view === "logs"
        ? ".logview .filter-text"
        : `[data-terminal="${wish.view}"]`,
    );
    // Laid out means shown: a hidden pane's content has no offset parent.
    if (!target || target.offsetParent === null) return;
    if (wish.view === "logs") target.focus();
    else if (
      terminals.current[wish.view] &&
      target.getAttribute("aria-busy") !== "true"
    )
      terminals.current[wish.view]?.focus();
    else {
      // Fonts and the first usable TUI frame can both delay focus. Later
      // user input cancels this wish; loading time alone must not lose it.
      wish.waitingForTerminal = true;
      return;
    }
    wish.waitingForTerminal = false;
    wish.granted = true;
  }, [signInButton, terminals]);
  useEffect(grantFocus);
  useEffect(() => {
    // Whatever the person presses next decides where focus is: a wish from
    // before that press is dropped, never granted over it. The press that
    // made the wish is older than the wish and leaves it alone.
    const drop = (event: Event) => {
      if (wanted.current && wanted.current.since < event.timeStamp)
        wanted.current = null;
    };
    window.addEventListener("pointerdown", drop, true);
    window.addEventListener("keydown", drop, true);
    return () => {
      window.removeEventListener("pointerdown", drop, true);
      window.removeEventListener("keydown", drop, true);
    };
  }, []);
  const focusView = useCallback(
    (view: TerminalKind | "logs") => {
      wanted.current = { view, since: performance.now() };
      grantFocus();
    },
    [grantFocus],
  );
  const focusRail = useCallback(
    () => document.querySelector<HTMLElement>(".rail [role=toolbar]")?.focus(),
    [],
  );
  return { grantFocus, focusView, focusRail };
}
