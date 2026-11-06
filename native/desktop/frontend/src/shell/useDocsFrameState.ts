import { useRef, useState } from "react";
import type { DocsFrameApi } from "../components/DocsFrame";
import type { DocsTheme } from "../ipc/docsBridge";

/** The documentation frame as the window holds it: its handle, the theme it
 * reports, and whether it offers its own search. */
export function useDocsFrameState() {
  const docs = useRef<DocsFrameApi>(null);
  const [docsTheme, setDocsTheme] = useState<DocsTheme>("auto");
  const [docsSearchReady, setDocsSearchReady] = useState(false);
  return {
    docs,
    docsTheme,
    setDocsTheme,
    docsSearchReady,
    setDocsSearchReady,
  };
}
