import { useMemo, type RefObject } from "react";
import type { DocsLanguage } from "@/ipc/environment";
import type { DocsFrameApi } from "../components/DocsFrame";
import type { Action } from "./actions";
import type { Layout } from "./layout";
import type { Translate } from "./strings";

/** The documentation's: its search, home, history and zoom. */
export function useDocsActions({
  t,
  docsSearchReady,
  docsEntry,
  docs,
  goHome,
  pageOn,
  patch,
  layout,
}: {
  t: Translate;
  docsSearchReady: boolean;
  docsEntry: DocsLanguage | null;
  docs: RefObject<DocsFrameApi | null>;
  goHome: () => void;
  pageOn: boolean;
  patch: (change: Partial<Layout>) => void;
  layout: Layout;
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "docs.search",
        label: t("desktop.palette.documentation"),
        group: "docs",
        icon: "book",
        enabled: () => !docsSearchReady && docsEntry !== null,
        run: () => docs.current?.openSearch(),
      },
      {
        id: "docs.home",
        label: t("desktop.rail.docs_home"),
        group: "docs",
        icon: "book",
        chords: [{ alt: true, code: "Home", key: "Home", scope: "docs" }],
        run: goHome,
      },
      {
        id: "docs.back",
        label: t("desktop.action.docs_back"),
        group: "docs",
        icon: "back",
        chords: [{ alt: true, code: "ArrowLeft", key: "←", scope: "docs" }],
        enabled: () => !pageOn,
        run: () => docs.current?.back(),
      },
      {
        id: "docs.forward",
        label: t("desktop.action.docs_forward"),
        group: "docs",
        icon: "forward",
        chords: [{ alt: true, code: "ArrowRight", key: "→", scope: "docs" }],
        enabled: () => !pageOn,
        run: () => docs.current?.forward(),
      },
      {
        id: "docs.zoomIn",
        label: t("desktop.action.zoom_in"),
        group: "docs",
        icon: "zoomIn",
        chords: [{ mod: true, code: "Equal", key: "=", scope: "docs" }],
        enabled: () => !pageOn,
        run: () =>
          patch({
            zoom: Math.min(2, Math.round((layout.zoom + 0.1) * 10) / 10),
          }),
      },
      {
        id: "docs.zoomOut",
        label: t("desktop.action.zoom_out"),
        group: "docs",
        icon: "zoomOut",
        chords: [{ mod: true, code: "Minus", key: "-", scope: "docs" }],
        enabled: () => !pageOn,
        run: () =>
          patch({
            zoom: Math.max(0.5, Math.round((layout.zoom - 0.1) * 10) / 10),
          }),
      },
      {
        id: "docs.zoomReset",
        label: t("desktop.action.zoom_reset"),
        group: "docs",
        icon: "reset",
        chords: [{ mod: true, code: "Digit0", key: "0", scope: "docs" }],
        enabled: () => !pageOn,
        run: () => patch({ zoom: 1 }),
      },
    ],
    [t, docsSearchReady, docsEntry, docs, goHome, pageOn, patch, layout.zoom],
  );
}
