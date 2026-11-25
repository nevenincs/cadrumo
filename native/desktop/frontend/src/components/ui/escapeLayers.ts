import * as React from "react";

// The foundation gives Escape to its newest layer, and it counts a layer as
// long as the layer is on screen: a tooltip takes the key from what is under
// it, and a layer still fading takes it and does nothing. Who gets the key is
// decided here instead, ahead of the foundation, from the layers that can still
// be closed.

type Layer = {
  /** What is marked, a direct child of the layer's surface. */
  mark: HTMLElement;
  /** Takes the press, and says whether the layer used it. */
  escape(event: KeyboardEvent): boolean;
};

/** Oldest first: a layer opened over another mounts after it. */
const layers: Layer[] = [];

function pressed(event: KeyboardEvent) {
  if (event.key !== "Escape" || event.isComposing) return;
  const top = [...layers]
    .reverse()
    .find(({ mark }) => mark.parentElement?.dataset.state !== "closed");
  if (top?.escape(event)) {
    event.preventDefault();
    event.stopPropagation();
  }
}

function enrol(layer: Layer) {
  if (layers.length === 0) window.addEventListener("keydown", pressed, true);
  layers.push(layer);
  return () => {
    layers.splice(layers.indexOf(layer), 1);
    if (layers.length === 0)
      window.removeEventListener("keydown", pressed, true);
  };
}

/**
 * Makes a surface a layer that Escape closes when it is the topmost one still
 * open. Put the ref on the hidden close button directly inside the surface,
 * whose click is how the surface closes; `button` holds that button.
 *
 * `onEscape` runs first. Calling `preventDefault` there leaves the layer open
 * and sends the key on to what it was pressed in, for a layer whose field
 * decides what Escape does. Otherwise the press ends here: nothing under the
 * layer sees it.
 */
function useEscapeLayer(onEscape?: (event: KeyboardEvent) => void) {
  const button = React.useRef<HTMLButtonElement | null>(null);
  const latest = React.useRef(onEscape);
  React.useLayoutEffect(() => {
    latest.current = onEscape;
  });
  const ref = React.useCallback((mark: HTMLButtonElement) => {
    button.current = mark;
    const leave = enrol({
      mark,
      escape: (event) => {
        latest.current?.(event);
        if (event.defaultPrevented) return false;
        mark.click();
        return true;
      },
    });
    return () => {
      button.current = null;
      leave();
    };
  }, []);
  return { ref, button };
}

/** For the ref of a hidden element directly inside a layer that closes itself
 * on Escape: the key is left to it while it is the topmost open layer, and
 * passes under it once it is going. */
const ownEscapeLayer = (mark: HTMLElement) =>
  enrol({ mark, escape: () => false });

export { ownEscapeLayer, useEscapeLayer };
