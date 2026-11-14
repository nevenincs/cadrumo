import * as React from "react";

/** Whether an element scrolls at the size it is drawn: it overflows and its
 * overflow is auto or scroll. The element is state, taken as a callback ref,
 * so one that mounts late is watched; its children are watched too, so the
 * answer follows its size and what it holds. */
export function useScrolls(pane: HTMLElement | null): boolean {
  const [scrolls, setScrolls] = React.useState(false);
  React.useLayoutEffect(() => {
    if (!pane) return;
    const measure = () => {
      const style = getComputedStyle(pane);
      const scrolling = (overflow: string) =>
        overflow === "auto" || overflow === "scroll";
      setScrolls(
        (scrolling(style.overflowY) &&
          pane.scrollHeight - pane.clientHeight > 1) ||
          (scrolling(style.overflowX) &&
            pane.scrollWidth - pane.clientWidth > 1),
      );
    };
    const resize = new ResizeObserver(measure);
    const watch = () => {
      resize.disconnect();
      resize.observe(pane);
      for (const child of pane.children) resize.observe(child);
    };
    const mutation = new MutationObserver(() => {
      watch();
      measure();
    });
    mutation.observe(pane, { childList: true });
    watch();
    measure();
    return () => {
      resize.disconnect();
      mutation.disconnect();
    };
  }, [pane]);
  return scrolls;
}
