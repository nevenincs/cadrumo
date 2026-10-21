import { useEffect, useState, type RefObject } from "react";

export function useWindowPresentation(
  workspace: RefObject<HTMLElement | null>,
) {
  const [viewportHeight, setViewportHeight] = useState(window.innerHeight);
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);
  const [prefersDark, setPrefersDark] = useState(
    () => matchMedia("(prefers-color-scheme: dark)").matches,
  );
  useEffect(() => {
    const query = matchMedia("(prefers-color-scheme: dark)");
    const change = () => setPrefersDark(query.matches);
    const resize = () => {
      setViewportHeight(
        workspace.current?.getBoundingClientRect().height ?? window.innerHeight,
      );
      setViewportWidth(window.innerWidth);
    };
    query.addEventListener("change", change);
    window.addEventListener("resize", resize);
    const observer = new ResizeObserver(resize);
    if (workspace.current) observer.observe(workspace.current);
    resize();
    return () => {
      query.removeEventListener("change", change);
      window.removeEventListener("resize", resize);
      observer.disconnect();
    };
  }, [workspace]);

  return { viewportHeight, viewportWidth, prefersDark };
}
