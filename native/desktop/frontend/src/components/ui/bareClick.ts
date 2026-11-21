import * as React from "react";

/**
 * Tells a click nothing else started from one a pointer press or a key
 * already answered. An assistive technology's or automation's activation (UI
 * Automation's Invoke, a screen reader's default action) sends only a click,
 * with no press, no key and perhaps no focus before it, so a control that
 * acts on press must also act on such a click, and only on it.
 *
 * A pointer click carries a click count (`detail` of one or more); a click a
 * key produced lands between that key's keydown and keyup, wherever the
 * focus went in between. Everything else is bare.
 */
export function useBareClick() {
  const keyHeld = React.useRef(false);
  const onKeyDown = React.useCallback((event: React.KeyboardEvent) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    keyHeld.current = true;
    window.addEventListener(
      "keyup",
      () => {
        // A Space's click follows its keyup handlers in the same task.
        window.setTimeout(() => {
          keyHeld.current = false;
        }, 0);
      },
      { capture: true, once: true },
    );
  }, []);
  const isBare = React.useCallback(
    (event: React.MouseEvent) =>
      event.detail === 0 && !keyHeld.current && !event.defaultPrevented,
    [],
  );
  return { onKeyDown, isBare };
}
