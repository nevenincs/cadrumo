import type {
  ComponentProps,
  Dispatch,
  ReactNode,
  RefObject,
  SetStateAction,
} from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { DocsLanguage } from "../ipc/environment";
import { primaryChord, type Action } from "../shell/actions";
import { initialDockLayout, type DockPane } from "../shell/docking";
import type { Host, TerminalKind } from "../shell/host";
import type { Layout, Maximized, PanelTab, Prefs } from "../shell/layout";
import type { useNavigator } from "../shell/navigation/useNavigator";
import type { RecordFilters } from "../shell/records";
import { facts } from "../shell/compose";
import { sessionFailedText } from "../shell/sessionWords";
import type { AccountPhase, SignInController } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import { DARK_TUI, LIGHT_TUI } from "../shell/terminalThemes";
import type { useFullscreen } from "../shell/useFullscreen";
import type { useShellShortcuts } from "../shell/useShellShortcuts";
import type { useShellMenus } from "../shell/useShellMenus";
import type { useWindowSetup } from "../shell/useWindowSetup";
import { WORKSPACE_COLUMNS } from "../shell/useWorkspaceFocus";
import { accountLabel } from "./accountWords";
import { AgentColumn } from "./AgentColumn";
import type { OpenMenu } from "./ContextMenu";
import { DockWorkspace } from "./docking/DockWorkspace";
import { HostRecordList } from "./HostRecordList";
import { PaneHeader, type PaneControl } from "./PaneHeader";
import { SignedOut } from "./SignIn";
import {
  TerminalPane,
  type TerminalApi,
  type TerminalStatus,
} from "./TerminalPane";

type Navigator = ReturnType<typeof useNavigator>;
type Area = Exclude<Maximized, null>;
type Dock = ComponentProps<typeof DockWorkspace>;

/** The exit code of a session that has exited, null when it is unknown. */
const exitCode = (status: TerminalStatus): number | null | undefined =>
  status.phase === "exited" ? status.code : undefined;

/** The host's code for why a session could not start or carry on, when it has
 * failed; `sessionFailedText` words it. */
const failure = (status: TerminalStatus): string | undefined =>
  status.phase === "failed" ? status.message : undefined;

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
  // What a session's header says beside its state: how it ended, or why it
  // could not start.
  const sessionNote = (kind: TerminalKind) => {
    const reason = failure(status[kind]);
    if (reason !== undefined) return sessionFailedText(t, reason);
    const code = exitCode(status[kind]);
    if (code === undefined) return undefined;
    return facts(t, [
      t("desktop.session.exited", { code: code ?? "?" }),
      t("desktop.session.enter_restarts"),
    ]);
  };

  const terminalPane = (
    kind: TerminalKind,
    shown: boolean,
    theme = terminalTheme,
  ) => (
    <TerminalPane
      host={host}
      kind={kind}
      shown={shown}
      theme={theme}
      fontSize={terminalFontSize}
      label={
        kind === "tui"
          ? t("desktop.tui.label")
          : t(
              kind === "console"
                ? "desktop.rail.console"
                : "desktop.rail.python",
            )
      }
      isShellChord={isShellChord}
      onStatus={(k, s) => {
        setStatus((all) => ({ ...all, [k]: s }));
        if (k !== "tui") return;
        // The TUI's session has ended: what it did to the account is read
        // again.
        if (s.phase === "exited" || s.phase === "failed") account.tuiExited();
      }}
      onMenu={terminalMenu}
      register={(k, api) => {
        terminals.current[k] = api;
      }}
      tabPanel={kind !== "tui"}
    />
  );

  const pane = "pane flex min-h-0 min-w-0 flex-1 flex-col bg-background";
  const docsPane = <div className={cn(pane, "pane-docs")}>{main}</div>;
  const tuiPane = (
    <div className={cn(pane, "pane-tui")} data-scheme={scheme}>
      <PaneHeader
        title={t("desktop.pane.tui")}
        // While the account withholds the TUI there is no session: the
        // header says the account's phase, not the last session's.
        status={
          account.gated
            ? {
                phase:
                  phase === "checking" ||
                  phase === "starting" ||
                  account.startingServices
                    ? "starting"
                    : "unavailable",
                note: t(accountLabel(phase) ?? "desktop.account.unknown"),
              }
            : { phase: status.tui.phase, note: sessionNote("tui") }
        }
        onToggleMaximize={() => toggleMaximize("tui")}
        controls={[
          maximizeControl("tui", "desktop.pane.maximize_tui"),
          ...splitControls,
          {
            id: "close",
            icon: "close",
            label: t("desktop.tui.hide"),
            shortcut: primaryChord(byId("tui.toggle")),
            run: () => closeColumn("tui"),
          },
        ]}
      />
      {account.gated ? (
        <SignedOut
          account={account}
          onSignIn={askSignIn}
          signInButton={signInButton}
        />
      ) : (
        terminalPane(
          "tui",
          tuiVisible,
          scheme === "dark" ? DARK_TUI : LIGHT_TUI,
        )
      )}
    </div>
  );
  const agentPane = (
    <div className={cn(pane, "pane-agent")}>
      {/* One bar: the conversation's own actions, then the column's maximize
          and close as every column has them. */}
      <AgentColumn
        control={agentControl}
        agent={host.agent}
        session={host.agentSession}
        providerSettings={host.providerSettings}
        agentAccess={host.agentAccess}
        writeClipboard={(text) => host.writeClipboard(text)}
        // The agent works only for a profile that is signed in here: not
        // for one the shell cannot tell about.
        reader={signedIn ? (account.status?.active_profile ?? null) : null}
        shown={agentVisible}
        locale={locale}
        body={agentBody}
        onToggleMaximize={() => toggleMaximize("agent")}
        onMenu={openMenu}
        onToolRefused={onToolRefused}
        onOpenLink={openLink}
        setupSettled={settledSetups}
        onOpenView={(url, opened) =>
          openViewLink(url, {
            opened: (shown) => opened?.(shown.opened),
          })
        }
        trailing={[
          maximizeControl("agent", "desktop.pane.maximize_agent"),
          {
            id: "close",
            icon: "close",
            label: t("desktop.agent.hide"),
            shortcut: primaryChord(byId("agent.toggle")),
            run: () => closeColumn("agent"),
          } satisfies PaneControl,
        ].map((control) => (
          <IconButton
            key={control.id}
            label={control.label}
            shortcut={control.shortcut}
            aria-pressed={control.pressed}
            onClick={control.run}
          >
            <Icon name={control.icon} />
          </IconButton>
        ))}
      />
    </div>
  );
  // Nothing open above the bottom panel: the main area says so, and offers
  // each column back.
  const canvas = (
    <EmptyState
      className="canvas bg-background"
      icon="canvas"
      heading={t("desktop.canvas.title")}
      description={t("desktop.canvas.lead")}
    >
      <div className="flex flex-wrap justify-center gap-2">
        {(
          [
            [
              "agent.toggle",
              "agent",
              "desktop.agent.show",
              signedIn && !agentVisible,
            ],
            ["tui.toggle", "tui", "desktop.tui.show", true],
            ["docs.toggle", "book", "desktop.docs.show", true],
          ] as const
        ).map(
          ([id, icon, labelKey, offered]) =>
            offered && (
              <Button key={id} variant="outline" onClick={() => runAction(id)}>
                <Icon name={icon} />
                {t(labelKey)}
              </Button>
            ),
        )}
      </div>
    </EmptyState>
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
          status: account.gated
            ? {
                phase:
                  phase === "checking" ||
                  phase === "starting" ||
                  account.startingServices
                    ? "starting"
                    : "unavailable",
                note: t(accountLabel(phase) ?? "desktop.account.unknown"),
              }
            : { phase: status.tui.phase, note: sessionNote("tui") },
        },
        {
          id: "console",
          status: {
            phase: status.console.phase,
            note: sessionNote("console"),
          },
          className: cn(
            "[container:panel/size]",
            layout.tab === "console" && "panel",
          ),
          title: t("desktop.rail.console"),
          content: (
            <div className="relative flex min-h-0 flex-1">
              {terminalPane("console", tabOpen("console"))}
            </div>
          ),
        },
        {
          id: "python",
          status: {
            phase: status.python.phase,
            note: sessionNote("python"),
          },
          className: cn(
            "[container:panel/size]",
            layout.tab === "python" && "panel",
          ),
          title: t("desktop.rail.python"),
          content: (
            <div className="relative flex min-h-0 flex-1">
              {terminalPane("python", tabOpen("python"))}
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
