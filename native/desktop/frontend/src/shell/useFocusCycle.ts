import { useCallback, type RefObject } from "react";
import type { DocsFrameApi } from "../components/DocsFrame";
import type { TerminalStatus } from "../components/TerminalPane";
import type { DockPane } from "./docking";
import { focusedArea } from "./focusedArea";
import type { TerminalKind } from "./host";

type PageRef = RefObject<HTMLElement | null>;

export function useFocusCycle({
  agentVisible,
  firstPaneShown,
  tuiVisible,
  panelVisible,
  activePanes,
  gated,
  status,
  focusView,
  focusRail,
  profilePage,
  ledgerPage,
  declarationsPage,
  calendarPage,
  aeatSyncPage,
  docs,
  signInButton,
  agentBody,
}: {
  agentVisible: boolean;
  firstPaneShown: boolean;
  tuiVisible: boolean;
  panelVisible: boolean;
  activePanes: DockPane[];
  gated: boolean;
  status: Record<TerminalKind, TerminalStatus>;
  focusView: (view: TerminalKind | "logs") => void;
  focusRail: () => void;
  profilePage: PageRef;
  ledgerPage: PageRef;
  declarationsPage: PageRef;
  calendarPage: PageRef;
  aeatSyncPage: PageRef;
  docs: RefObject<DocsFrameApi | null>;
  signInButton: RefObject<HTMLButtonElement | null>;
  agentBody: PageRef;
}) {
  // The keyboard's way between the areas of the window, in the order they
  // are laid out. A focused terminal keeps Tab for itself, so this is how
  // focus leaves one.
  const cycleFocus = useCallback(
    (step: 1 | -1) => {
      type Stop = [DockPane | "rail", boolean, () => void];
      const docsStop: Stop = [
        "docs",
        firstPaneShown &&
          (profilePage.current !== null ||
            ledgerPage.current !== null ||
            declarationsPage.current !== null ||
            calendarPage.current !== null ||
            aeatSyncPage.current !== null ||
            !!docs.current),
        () =>
          (
            profilePage.current ??
            ledgerPage.current ??
            declarationsPage.current ??
            calendarPage.current ??
            aeatSyncPage.current ??
            docs.current
          )?.focus(),
      ];
      const tuiStop: Stop = [
        "tui",
        // Only where the pane holds something to focus: the way in while
        // signed out, or a session.
        tuiVisible &&
          (signInButton.current !== null ||
            (!gated && status.tui.phase !== "unavailable")),
        () => focusView("tui"),
      ];
      const stops: Stop[] = [
        ["agent", agentVisible, () => agentBody.current?.focus()],
        tuiStop,
        docsStop,
        ...(["console", "python", "logs"] as const).map((tab): Stop => [
          tab,
          panelVisible && activePanes.includes(tab),
          () => {
            if (tab === "logs")
              document
                .querySelector<HTMLElement>(".logview .filter-text")
                ?.focus();
            // Without a session there is no terminal to focus; its tab is.
            else if (status[tab].phase === "unavailable")
              document.getElementById(`tab-${tab}`)?.focus();
            else focusView(tab);
          },
        ]),
      ];
      const shown: Stop[] = activePanes.flatMap((pane) =>
        stops.filter(([id, on]) => id === pane && on),
      );
      shown.push(["rail", true, focusRail]);
      const focused =
        document.activeElement?.closest<HTMLElement>("[data-dock-pane]")
          ?.dataset.dockPane ?? focusedArea();
      const at = shown.findIndex(([area]) => area === focused);
      const to =
        at === -1
          ? step === 1
            ? 0
            : shown.length - 1
          : (at + step + shown.length) % shown.length;
      shown[to]?.[2]();
    },
    [
      agentVisible,
      firstPaneShown,
      tuiVisible,
      panelVisible,
      activePanes,
      gated,
      status,
      focusView,
      focusRail,
      profilePage,
      ledgerPage,
      declarationsPage,
      calendarPage,
      aeatSyncPage,
      docs,
      signInButton,
      agentBody,
    ],
  );
  return cycleFocus;
}
