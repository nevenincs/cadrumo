import type {
  ComponentProps,
  Dispatch,
  ReactNode,
  RefObject,
  SetStateAction,
} from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { DocsLanguage } from "../ipc/environment";
import { primaryChord, type Action } from "../shell/actions";
import { initialDockLayout, type DockPane } from "../shell/docking";
import type { Host, TerminalKind } from "../shell/host";
import type { Layout, Maximized, PanelTab, Prefs } from "../shell/layout";
import type { useNavigator } from "../shell/navigation/useNavigator";
import type { RecordFilters } from "../shell/records";
import type { AccountPhase, SignInController } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import type { useFullscreen } from "../shell/useFullscreen";
import type { useShellShortcuts } from "../shell/useShellShortcuts";
import type { useShellMenus } from "../shell/useShellMenus";
import type { useWindowSetup } from "../shell/useWindowSetup";
import { WORKSPACE_COLUMNS } from "../shell/useWorkspaceFocus";
import type { AgentColumn } from "./AgentColumn";
import { AgentPane } from "./AgentPane";
import type { OpenMenu } from "./ContextMenu";
import { DockWorkspace } from "./docking/DockWorkspace";
import { HostRecordList } from "./HostRecordList";
import type { PaneControl } from "./PaneHeader";
import { PANE_SURFACE } from "./paneSurface";
import { sessionNote, tuiStatus } from "./sessionStatus";
import { ShellTerminal, type TerminalWiring } from "./ShellTerminal";
import type { TerminalApi, TerminalPane, TerminalStatus } from "./TerminalPane";
import { TuiPane } from "./TuiPane";
import { WorkspaceCanvas } from "./WorkspaceCanvas";

type Navigator = ReturnType<typeof useNavigator>;
type Area = Exclude<Maximized, null>;
type Dock = ComponentProps<typeof DockWorkspace>;

/** The workspace's dock and every pane it holds: the agent, the first pane
 * with `main` in it, the TUI, the terminals and the log; and what closing,
 * expanding or activating one does to the layout. */
export function ShellDock({
  host,
  t,
  locale,
  account,
  phase,
  signedIn,
  scheme,
  terminalTheme,
  terminalFontSize,
  status,
  setStatus,
  terminals,
  isShellChord,
  terminalMenu,
  recordMenu,
  signInButton,
  askSignIn,
  agentControl,
  agentBody,
  openMenu,
  onToolRefused,
  openLink,
  openViewLink,
  settledSetups,
  byId,
  runAction,
  maximizeControl,
  splitControls,
  layout,
  prefs,
  setLayout,
  maximized,
  setMaximized,
  patch,
  docking,
  changeDocking,
  setNarrowedPanes,
  dockMinimumWidths,
  dockBesideWidths,
  dockMinimumHeights,
  dockOffered,
  expandedPane,
  fullscreen,
  enterFullscreen,
  revealPane,
  grantFocus,
  focusView,
  focusRail,
  toggleMaximize,
  closeColumn,
  guarded,
  showPage,
  closePage,
  setBrowserKeptFor,
  agentVisible,
  tuiVisible,
  panelVisible,
  activePanes,
  pageOn,
  profileOn,
  calendarOn,
  ledgerOn,
  declarationsOn,
  browserOn,
  aeatSyncOn,
  docsEntry,
  main,
  setErrorCount,
  filters,
  defaultFilters,
  setFilters,
  selectLogLevel,
  copyLogs,
  exportLogs,
  revealLogs,
}: {
  host: Host;
  t: Translate;
  locale: string;
  account: SignInController;
  phase: AccountPhase;
  signedIn: boolean;
  scheme: "light" | "dark";
  terminalTheme: ComponentProps<typeof TerminalPane>["theme"];
  terminalFontSize: ComponentProps<typeof TerminalPane>["fontSize"];
  status: Record<TerminalKind, TerminalStatus>;
  setStatus: Dispatch<SetStateAction<Record<TerminalKind, TerminalStatus>>>;
  terminals: RefObject<Partial<Record<TerminalKind, TerminalApi>>>;
  isShellChord: ReturnType<typeof useShellShortcuts>["isShellChord"];
  terminalMenu: ReturnType<typeof useShellMenus>["terminalMenu"];
  recordMenu: ReturnType<typeof useShellMenus>["recordMenu"];
  signInButton: RefObject<HTMLButtonElement | null>;
  askSignIn: () => void;
  agentControl: ComponentProps<typeof AgentColumn>["control"];
  agentBody: ComponentProps<typeof AgentColumn>["body"];
  openMenu: OpenMenu;
  onToolRefused: ReturnType<typeof useWindowSetup>["onToolRefused"];
  openLink: (url: string) => void;
  openViewLink: Navigator["openLink"];
  settledSetups: string | null;
  byId: (id: string) => Action | undefined;
  runAction: (id: string) => void;
  maximizeControl: (area: Area, labelKey: string) => PaneControl;
  splitControls: PaneControl[];
  layout: Layout;
  prefs: Prefs;
  setLayout: Dispatch<SetStateAction<Layout>>;
  maximized: Maximized;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  patch: (change: Partial<Layout>) => void;
  docking: Dock["layout"];
  changeDocking: Dock["onChange"];
  setNarrowedPanes: Dock["onNarrowed"];
  dockMinimumWidths: Dock["minimumWidths"];
  dockBesideWidths: Dock["besideWidths"];
  dockMinimumHeights: Dock["minimumHeights"];
  dockOffered: DockPane[];
  expandedPane: DockPane | null;
  fullscreen: ReturnType<typeof useFullscreen>;
  enterFullscreen: ReturnType<typeof useFullscreen>["toggle"];
  revealPane: ReturnType<typeof useFullscreen>["reveal"];
  grantFocus: () => void;
  focusView: (view: TerminalKind | "logs") => void;
  focusRail: () => void;
  toggleMaximize: (area: Area) => void;
  closeColumn: (column: (typeof WORKSPACE_COLUMNS)[number]) => void;
  guarded: (proceed: () => void) => void;
  showPage: (page: Layout["page"]) => void;
  closePage: () => void;
  setBrowserKeptFor: (reader: string | null) => void;
  agentVisible: boolean;
  tuiVisible: boolean;
  panelVisible: boolean;
  activePanes: DockPane[];
  pageOn: boolean;
  profileOn: boolean;
  calendarOn: boolean;
  ledgerOn: boolean;
  declarationsOn: boolean;
  browserOn: boolean;
  aeatSyncOn: boolean;
  docsEntry: DocsLanguage | null;
  main: ReactNode;
  setErrorCount: (count: number) => void;
  filters: RecordFilters;
  defaultFilters: RecordFilters;
  setFilters: (update: SetStateAction<RecordFilters>) => void;
  selectLogLevel: (minLevel: number) => void;
  copyLogs: (text: string) => void;
  exportLogs: (text: string) => Promise<void>;
  revealLogs: () => void;
}) {
  const tabOpen = (tab: PanelTab) => panelVisible && activePanes.includes(tab);
  const wiring: TerminalWiring = {
    host,
    t,
    account,
    fontSize: terminalFontSize,
    isShellChord,
    setStatus,
    terminalMenu,
    terminals,
  };

  const docsPane = <div className={cn(PANE_SURFACE, "pane-docs")}>{main}</div>;
  const tuiPane = (
    <TuiPane
      wiring={wiring}
      phase={phase}
      status={status.tui}
      scheme={scheme}
      shown={tuiVisible}
      maximizeControl={maximizeControl("tui", "desktop.pane.maximize_tui")}
      splitControls={splitControls}
      byId={byId}
      toggleMaximize={() => toggleMaximize("tui")}
      close={() => closeColumn("tui")}
      askSignIn={askSignIn}
      signInButton={signInButton}
    />
  );
  const agentPane = (
    <AgentPane
      host={host}
      t={t}
      locale={locale}
      account={account}
      signedIn={signedIn}
      shown={agentVisible}
      agentControl={agentControl}
      body={agentBody}
      openMenu={openMenu}
      onToolRefused={onToolRefused}
      openLink={openLink}
      openViewLink={openViewLink}
      settledSetups={settledSetups}
      maximizeControl={maximizeControl("agent", "desktop.pane.maximize_agent")}
      byId={byId}
      toggleMaximize={() => toggleMaximize("agent")}
      close={() => closeColumn("agent")}
    />
  );
  const canvas = (
    <WorkspaceCanvas
      t={t}
      offersAgent={signedIn && !agentVisible}
      runAction={runAction}
    />
  );

  return (
    <DockWorkspace
      layout={docking}
      minimumWidths={dockMinimumWidths}
      besideWidths={dockBesideWidths}
      minimumHeights={dockMinimumHeights}
      visible={dockOffered}
      expanded={expandedPane}
      fullscreen={fullscreen.fullscreen}
      onChange={changeDocking}
      onMenuClosed={grantFocus}
      onFocusPane={(pane) => {
        if (
          pane === "console" ||
          pane === "python" ||
          pane === "logs" ||
          pane === "tui"
        )
          focusView(pane);
      }}
      onActivate={(pane) => {
        if (pane === "console" || pane === "python" || pane === "logs")
          patch({ panelOpen: true, tab: pane });
        else if (pane === "agent") patch({ agentShown: true });
        else if (pane === "tui") patch({ tuiShown: true });
        else patch({ docsShown: true });
      }}
      onClose={(pane) => {
        if (fullscreen.pane === pane) enterFullscreen();
        if (pane === "docs") {
          if (browserOn) {
            guarded(() => {
              setBrowserKeptFor(null);
              showPage("docs");
            });
            setMaximized(null);
          } else if (pageOn) closePage();
          else closeColumn("docs");
          return;
        }
        if (pane === "agent" || pane === "tui") {
          closeColumn(pane);
          return;
        }
        setLayout((current) => {
          const dock = current.docking ?? initialDockLayout(prefs, current);
          const closed = [...new Set([...dock.closed, pane])];
          return {
            ...current,
            docking: { ...dock, closed },
            panelOpen: ["console", "python", "logs"].some(
              (id) => !closed.some((pane) => pane === id),
            ),
          };
        });
        if (maximized === "panel") setMaximized(null);
        focusRail();
      }}
      onExpand={(pane) => {
        if (fullscreen.pane) {
          revealPane(null);
          setMaximized(null);
          return;
        }
        if (pane === "console" || pane === "python" || pane === "logs") {
          patch({ tab: pane });
          toggleMaximize("panel");
        } else toggleMaximize(pane);
      }}
      onFullscreen={(pane) => enterFullscreen(pane)}
      onNarrowed={setNarrowedPanes}
      empty={canvas}
      panes={[
        {
          id: "agent",
          className: "agent-column",
          title: t("desktop.pane.agent"),
          content: agentPane,
        },
        {
          id: "docs",
          className: "main-area",
          title: t(
            profileOn
              ? "desktop.profile.title"
              : calendarOn
                ? "desktop.calendar.title"
                : ledgerOn
                  ? "desktop.ledger.title"
                  : declarationsOn
                    ? "workspace.declarations.destination.overview"
                    : browserOn
                      ? "desktop.browser.title"
                      : aeatSyncOn
                        ? "desktop.aeat_sync.title"
                        : "desktop.pane.docs",
          ),
          content: docsPane,
          pageActions:
            !pageOn && docsEntry ? (
              <>
                <IconButton
                  label={t("desktop.action.docs_back")}
                  shortcut={primaryChord(byId("docs.back"))}
                  onClick={() => runAction("docs.back")}
                >
                  <Icon name="back" />
                </IconButton>
                <IconButton
                  label={t("desktop.action.docs_forward")}
                  shortcut={primaryChord(byId("docs.forward"))}
                  onClick={() => runAction("docs.forward")}
                >
                  <Icon name="forward" />
                </IconButton>
              </>
            ) : undefined,
        },
        {
          id: "tui",
          title: t("desktop.pane.tui"),
          content: tuiPane,
          status: tuiStatus(t, account, phase, status.tui),
        },
        {
          id: "console",
          status: {
            phase: status.console.phase,
            note: sessionNote(t, status.console),
          },
          className: cn(
            "[container:panel/size]",
            layout.tab === "console" && "panel",
          ),
          title: t("desktop.rail.console"),
          content: (
            <div className="relative flex min-h-0 flex-1">
              <ShellTerminal
                kind="console"
                shown={tabOpen("console")}
                theme={terminalTheme}
                wiring={wiring}
              />
            </div>
          ),
        },
        {
          id: "python",
          status: {
            phase: status.python.phase,
            note: sessionNote(t, status.python),
          },
          className: cn(
            "[container:panel/size]",
            layout.tab === "python" && "panel",
          ),
          title: t("desktop.rail.python"),
          content: (
            <div className="relative flex min-h-0 flex-1">
              <ShellTerminal
                kind="python"
                shown={tabOpen("python")}
                theme={terminalTheme}
                wiring={wiring}
              />
            </div>
          ),
        },
        {
          id: "logs",
          className: cn(
            "[container:panel/size]",
            layout.tab === "logs" && "panel",
          ),
          title: t("desktop.rail.logs"),
          content: (
            <div className="relative flex min-h-0 flex-1">
              <HostRecordList
                host={host}
                onErrors={setErrorCount}
                filters={filters}
                defaultFilters={defaultFilters}
                setFilters={setFilters}
                onLevelChange={selectLogLevel}
                onMenu={recordMenu}
                onCopy={copyLogs}
                onExport={(text) => void exportLogs(text)}
                onReveal={host.revealLogs ? revealLogs : undefined}
                shown={tabOpen("logs")}
              />
            </div>
          ),
        },
      ]}
    />
  );
}
