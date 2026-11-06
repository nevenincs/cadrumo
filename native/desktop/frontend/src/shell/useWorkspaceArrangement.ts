import { useCallback, useRef, useState } from "react";
import { activateDockPane, type DockPane } from "./docking";
import type { Host } from "./host";
import type { Layout, LedgerView, ProfileView } from "./layout";
import type { AccountPhase } from "./signIn";
import type { Translate } from "./strings";
import { useFullscreen } from "./useFullscreen";
import { useShellLayout } from "./useShellLayout";
import { useWindowPresentation } from "./useWindowPresentation";

/** How the workspace is arranged and how the window changes it: the saved
 * layout and preferences, the dock, full screen, what is maximized while
 * the account allows it, and the updates that show a pane or a page. */
export function useWorkspaceArrangement({
  host,
  phase,
  say,
  t,
}: {
  host: Host;
  phase: AccountPhase;
  say: (text: string) => void;
  t: Translate;
}) {
  const workspace = useRef<HTMLDivElement>(null);
  const { viewportWidth, prefersDark } = useWindowPresentation(workspace);
  const {
    prefs,
    setPrefs,
    layout,
    setLayout,
    docking,
    changeDocking,
    setMaximized,
  } = useShellLayout();
  // Panes whose side-by-side split the window is too narrow to draw.
  const [narrowedPanes, setNarrowedPanes] = useState<readonly DockPane[]>([]);
  const fullscreen = useFullscreen(host, () =>
    say(t("desktop.titlebar.failed")),
  );
  const enterFullscreen = fullscreen.toggle;
  const revealPane = fullscreen.reveal;
  const activatePane = useCallback(
    (pane: DockPane) => {
      revealPane(pane);
      changeDocking((current) => activateDockPane(current, pane));
    },
    [changeDocking, revealPane],
  );
  // The least width the Ledger page asks beside the agent, while it shows.
  const [ledgerFloor, setLedgerFloor] = useState<number | null>(null);
  // Account gating affects presentation without erasing the saved arrangement.
  const maximized =
    layout.maximized === "agent" && phase !== "signed-in"
      ? null
      : layout.maximized;
  // What navigation callbacks read when they run, after render.
  const layoutNow = useRef(layout);
  layoutNow.current = layout;
  // Shows a page through the layout store; only the navigator, past the
  // guards, calls it directly.
  const showPage = useCallback(
    (page: Layout["page"]) => {
      revealPane("docs");
      setLayout((current) => ({
        ...current,
        page,
        docking: current.docking
          ? activateDockPane(current.docking, "docs")
          : null,
      }));
    },
    [revealPane, setLayout],
  );
  const patch = useCallback(
    (change: Partial<Layout>) => {
      const pane =
        change.tab ??
        (change.agentShown
          ? "agent"
          : change.tuiShown
            ? "tui"
            : change.docsShown
              ? "docs"
              : change.panelOpen
                ? layoutNow.current.tab
                : null);
      if (pane) revealPane(pane);
      setLayout((current) => {
        let docking = current.docking;
        if (docking && pane) docking = activateDockPane(docking, pane);
        return { ...current, docking, ...change };
      });
    },
    [revealPane, setLayout],
  );
  const changeProfileView = useCallback(
    (update: (current: ProfileView) => ProfileView) =>
      setLayout((current) => ({
        ...current,
        profileView: update(current.profileView),
      })),
    [setLayout],
  );
  const changeLedgerView = useCallback(
    (update: (current: LedgerView) => LedgerView) =>
      setLayout((current) => ({
        ...current,
        ledgerView: update(current.ledgerView),
      })),
    [setLayout],
  );
  return {
    workspace,
    viewportWidth,
    prefersDark,
    prefs,
    setPrefs,
    layout,
    setLayout,
    layoutNow,
    docking,
    changeDocking,
    maximized,
    setMaximized,
    narrowedPanes,
    setNarrowedPanes,
    fullscreen,
    enterFullscreen,
    revealPane,
    activatePane,
    ledgerFloor,
    setLedgerFloor,
    showPage,
    patch,
    changeProfileView,
    changeLedgerView,
  };
}
