import { useCallback, useMemo, type RefObject } from "react";
import type { DocsSearch } from "../components/CommandPalette";
import type { DocsFrameApi } from "../components/DocsFrame";
import type { useDesktopEnvironment } from "./useDesktopEnvironment";

/** The bundled documentation in the window's language, and the ways to its
 * home, to an address in it and to its search. */
export function useDocsNavigation({
  environment,
  locale,
  docs,
  docsSearchReady,
  showDocs,
}: {
  environment: ReturnType<typeof useDesktopEnvironment>;
  locale: string;
  docs: RefObject<DocsFrameApi | null>;
  docsSearchReady: boolean;
  showDocs: () => void;
}) {
  const docsEntry = useMemo(() => {
    if (environment.state !== "ready") return null;
    const docs = environment.value.docs;
    if (docs.state !== "bundled") return null;
    const { languages: bundled } = docs;
    return (
      bundled.find((language) => language.code === locale) ?? bundled[0] ?? null
    );
  }, [environment, locale]);

  const goHome = useCallback(() => {
    showDocs();
    if (docs.current?.home()) return;
    // A documentation page without the home command still reloads its entry.
    const frame = document.querySelector<HTMLIFrameElement>(".docs-frame");
    if (frame && docsEntry) frame.src = docsEntry.entry;
  }, [docsEntry, showDocs, docs]);

  const openDoc = useCallback(
    (url: string) => {
      showDocs();
      if (docs.current?.navigate(url)) return;
      const frame = document.querySelector<HTMLIFrameElement>(".docs-frame");
      if (
        !frame ||
        environment.state !== "ready" ||
        environment.value.docs.state !== "bundled"
      )
        return;
      // Only a documentation-origin address ever becomes the frame's source.
      let origin: string;
      try {
        origin = new URL(url).origin;
      } catch {
        return;
      }
      if (origin === environment.value.docs.origin) frame.src = url;
    },
    [environment, showDocs, docs],
  );

  const searchDocs: DocsSearch = useMemo(
    () =>
      docsSearchReady && locale
        ? (query: string) =>
            docs.current?.search(query) ??
            Promise.reject(new Error("docs-unmounted"))
        : null,
    [docsSearchReady, locale, docs],
  );
  return { docsEntry, goHome, openDoc, searchDocs };
}
