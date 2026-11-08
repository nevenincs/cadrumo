import settings from "virtual:operational-settings";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AccountDialogs } from "./components/AccountDialogs";
import { AttendanceRequests } from "./components/AttendanceRequests";
import { MainPane } from "./components/MainPane";
import { Rail } from "./components/Rail";
import { railItems } from "./components/railItems";
import { ShellDock } from "./components/ShellDock";
import { WindowOverlays } from "./components/WindowOverlays";
import { WindowTitlebar } from "./components/WindowTitlebar";
import { useAbout } from "./shell/about";
import type { Host } from "./shell/host";
import { paneControls } from "./shell/paneControls";
import { ShellContexts } from "./shell/ShellContexts";
import { useSignIn } from "./shell/signIn";
import { useActionRunner } from "./shell/useActionRunner";
import { useColumnCommands } from "./shell/useColumnCommands";
import { useDesktopEnvironment } from "./shell/useDesktopEnvironment";
import { useDocsFrameState } from "./shell/useDocsFrameState";
import { useDocsNavigation } from "./shell/useDocsNavigation";
import { useFocusCycle } from "./shell/useFocusCycle";
import { useFocusWish } from "./shell/useFocusWish";
import { useGateFocus } from "./shell/useGateFocus";
import { useHostClipboard } from "./shell/useHostClipboard";
import { useHostNotices } from "./shell/useHostNotices";
import { useLogControls } from "./shell/useLogControls";
import { useOpenExternal } from "./shell/useOpenExternal";
import { usePageArrival } from "./shell/usePageArrival";
import { usePageMemories } from "./shell/usePageMemories";
import { usePastedLink } from "./shell/usePastedLink";
import { usePersistedLayout } from "./shell/usePersistedLayout";
import { useProfilePageAsks } from "./shell/useProfilePageAsks";
import { useReadingModelPicker } from "./shell/useReadingModelPicker";
import { useShellActions } from "./shell/useShellActions";
import { useShellMenus } from "./shell/useShellMenus";
import { useShellShortcuts } from "./shell/useShellShortcuts";
import { useSignInFlow } from "./shell/useSignInFlow";
import { useTerminalSessions } from "./shell/useTerminalSessions";
import { useToastMessage } from "./shell/useToastMessage";
import { useWindowAppearance } from "./shell/useWindowAppearance";
import { useWindowLanguage } from "./shell/useWindowLanguage";
import { useWindowNavigation } from "./shell/useWindowNavigation";
import { useWindowOverlays } from "./shell/useWindowOverlays";
import { useWindowReads } from "./shell/useWindowReads";
import { useWindowSetup } from "./shell/useWindowSetup";
import { useWorkspaceArrangement } from "./shell/useWorkspaceArrangement";
import { useWorkspaceFocus } from "./shell/useWorkspaceFocus";
import { useWorkspaceMetrics } from "./shell/useWorkspaceMetrics";
import { useWorkspaceVisibility } from "./shell/useWorkspaceVisibility";
import { windowViewApplication } from "./shell/windowViewApplication";

/** The desktop window: composes the hooks that own its state and behaviour
 * and the components that draw it. Hooks run in call order, and so do their
 * effects: the order below is part of the window's behaviour. */
export function App({ host }: { host: Host }) {
  const { toast, say } = useToastMessage(settings.shell_toast_ms);
  const account = useSignIn(host);
  const environment = useDesktopEnvironment(host);
  const { language, locale, languages, languageControl, t } = useWindowLanguage(
    host,
    environment,
    account,
  );

  const arrangement = useWorkspaceArrangement({
    host,
    phase: account.phase,
    say,
    t,
  });
  const {
    prefs,
    setPrefs,
    layout,
    setLayout,
    layoutNow,
    maximized,
    setMaximized,
    fullscreen,
    patch,
    showPage,
    changeLedgerView,
  } = arrangement;
  const navigation = useWindowNavigation({
    host,
    t,
    say,
    account,
    layoutNow,
    setMaximized,
    patch,
    showPage,
    activatePane: arrangement.activatePane,
  });
  const { nav, guardNavigation, guarded, setPage, closePage } = navigation;
  const { openView, openLink: openViewLink, resolve: resolveView } = nav;
  const pageAsks = useProfilePageAsks({
    page: layout.page,
    layoutNow,
    setLayout,
    guardNavigation,
  });
  const about = useAbout(host);
  const overlays = useWindowOverlays();
  const { setSettingsOpen } = overlays;
  const docsFrame = useDocsFrameState();
  const { docs } = docsFrame;
  const sessions = useTerminalSessions();
  const { terminals } = sessions;
  const metrics = useWorkspaceMetrics(prefs.fontSize);
  usePersistedLayout(prefs, layout, settings.layout_save_delay_ms);

  const signIn = useSignInFlow({
    host,
    account,
    guardNavigation,
    setSettingsOpen,
  });
  const { gated, phase, signedIn, reader, signInButton } = signIn;
  const views = host.views;
  const visibility = useWorkspaceVisibility({
    host,
    layout,
    docking: arrangement.docking,
    maximized,
    fullscreenPane: fullscreen.pane,
    signedIn,
    viewportWidth: arrangement.viewportWidth,
    railWidth: metrics.railWidth,
    splitMinA: metrics.splitMinA,
    splitMinBRow: metrics.splitMinBRow,
    agentMin: metrics.agentMin,
    docsMin: metrics.docsMin,
    panelMin: metrics.panelMin,
    ledgerFloor: arrangement.ledgerFloor,
  });
  const {
    pageOn,
    firstPaneShown,
    activePanes,
    docsVisible,
    calendarVisible,
    ledgerVisible,
    declarationsVisible,
    browserVisible,
    tuiVisible,
    panelVisible,
    agentVisible,
  } = visibility;
  const memories = usePageMemories({
    reader,
    browserOn: visibility.browserOn,
    wantsDeclarations: navigation.wantsDeclarations,
  });
  const reads = useWindowReads({
    host,
    reader,
    calendarVisible,
    recheckAccount: signIn.recheckAccount,
    locale,
  });
  const { messages } = reads;
  const { showBrowser, showSede } = usePageArrival({
    calendarVisible,
    ledgerVisible,
    declarationsVisible,
    browserVisible,
    firstPaneShown,
    openDeclaration: memories.openDeclaration,
    calendarPage: navigation.calendarPage,
    ledgerPage: navigation.ledgerPage,
    declarationsPage: navigation.declarationsPage,
    browserPage: navigation.browserPage,
    wantsCalendar: navigation.wantsCalendar,
    wantsLedger: navigation.wantsLedger,
    wantsDeclarations: navigation.wantsDeclarations,
    wantsBrowser: navigation.wantsBrowser,
    docs,
    browserMounted: memories.browserMounted,
    setBrowserHome: memories.setBrowserHome,
    setMaximized,
    setPage,
  });
  const { scheme, terminalTheme } = useWindowAppearance({
    docsTheme: docsFrame.docsTheme,
    prefersDark: arrangement.prefersDark,
    prefs,
    locale,
  });

  const { docsEntry, goHome, openDoc, searchDocs } = useDocsNavigation({
    environment,
    locale,
    docs,
    docsSearchReady: docsFrame.docsSearchReady,
    showDocs: navigation.showDocs,
  });
  useHostNotices({ host, manager: account.manager, say, t });
  const openLink = useOpenExternal(host, say, t);
  const { copy, paste } = useHostClipboard({ host, terminals, say, t });
  const setup = useWindowSetup({
    host,
    reader,
    signedIn,
    locale,
    held: signIn.dialogHeld,
    setSettingsOpen,
    say,
    t,
  });
  const logs = useLogControls({
    host,
    environment,
    logLevel: layout.logLevel,
    setLayout,
    say,
    t,
  });
  const { grantFocus, focusView, focusRail } = useFocusWish({
    signInButton,
    terminals,
  });
  useGateFocus({
    gated,
    phase,
    signInDismissed: signIn.signInDismissed,
    focusView,
  });

  const columns = useColumnCommands({
    layout,
    maximized,
    setMaximized,
    patch,
    focusView,
    guarded,
    showPage,
    showDocs: navigation.showDocs,
    pageOn,
    panelVisible,
    activePanes,
    agentVisible,
    agentFits: visibility.agentFits,
    tuiVisible,
    docsVisible,
    mainOccupied: visibility.mainOccupied,
    wantsAgent: navigation.wantsAgent,
  });
  const { showTui, openTab, toggleMaximize } = columns;
  const cycleFocus = useFocusCycle({
    agentVisible,
    firstPaneShown,
    tuiVisible,
    panelVisible,
    activePanes,
    gated,
    status: sessions.status,
    focusView,
    focusRail,
    profilePage: navigation.profilePage,
    ledgerPage: navigation.ledgerPage,
    declarationsPage: navigation.declarationsPage,
    calendarPage: navigation.calendarPage,
    aeatSyncPage: navigation.aeatSyncPage,
    docs,
    signInButton,
    agentBody: navigation.agentBody,
  });

  const { agentControl, modelList } = useReadingModelPicker(
    host.agentSession,
    openView,
  );
  const pastedLink = usePastedLink(t, resolveView, openViewLink);

  const actions = useShellActions({
    t,
    fullscreen,
    enterFullscreen: arrangement.enterFullscreen,
    setPaletteExtra: overlays.setPaletteExtra,
    setPaletteOpen: overlays.setPaletteOpen,
    contributed: overlays.contributed,
    docsSearchReady: docsFrame.docsSearchReady,
    docsEntry,
    docs,
    goHome,
    pageOn,
    patch,
    layout,
    prefs,
    maximized,
    setMaximized,
    toggleMaximize,
    agentVisible,
    tuiVisible,
    docsVisible,
    firstPaneShown,
    panelVisible,
    activePanes,
    narrowedPanes: arrangement.narrowedPanes,
    changeDocking: arrangement.changeDocking,
    setPrefs,
    selectLogLevel: logs.selectLogLevel,
    openTab,
    setFilters: logs.setFilters,
    defaultFilters: logs.defaultFilters,
    host,
    revealLogs: logs.revealLogs,
    setSettingsOpen,
    about,
    setAboutOpen: overlays.setAboutOpen,
    setup: setup.setup,
    setupOffered: setup.setupOffered,
    setupSnapshot: setup.setupSnapshot,
    setupLive: setup.setupLive,
    setupRetryable: setup.setupRetryable,
    setupCancellable: setup.setupCancellable,
    openSetup: setup.openSetup,
    calendarVisible,
    ledgerVisible,
    declarationsVisible,
    browserVisible,
    wantsCalendar: navigation.wantsCalendar,
    wantsLedger: navigation.wantsLedger,
    wantsDeclarations: navigation.wantsDeclarations,
    setPage,
    showBrowser,
    toggleColumn: columns.toggleColumn,
    resolveView,
    openView,
    copy,
    views,
    messages,
    say,
    showTui,
    openLink,
    driveUrl: setup.driveUrl,
    mayEnterPassword: signIn.mayEnterPassword,
    askSignIn: signIn.askSignIn,
    canCreateProfile: signIn.canCreateProfile,
    offersProfiles: signIn.offersProfiles,
    askNewProfile: signIn.askNewProfile,
    signedIn,
    signOut: signIn.signOut,
    setSignInDismissed: signIn.setSignInDismissed,
    setManagingProfiles: signIn.setManagingProfiles,
    switchProfile: signIn.switchProfile,
    askCenso: pageAsks.askCenso,
    cycleFocus,
    terminals,
    paste,
  });
  const { actionsRef, byId, runAction, profileAccountActions } =
    useActionRunner(actions);
  navigation.bindWindow({
    showInWindow: windowViewApplication({
      tab: layout.tab,
      agentFits: visibility.agentFits,
      mainOccupied: visibility.mainOccupied,
      setMaximized,
      patch,
      showPage,
      changeLedgerView,
      setAeatAsked: pageAsks.setAeatAsked,
      showTui,
      openTab,
    }),
    askSignIn: signIn.askSignIn,
  });
  const { isShellChord, chords, runShortcut } = useShellShortcuts(
    actions,
    actionsRef,
    overlays.paletteOpen,
    overlays.menu !== null ||
      (signIn.signInAsked &&
        !signIn.signInDismissed &&
        account.status !== null),
  );
  const { docsMenu, aeatMenu, terminalMenu, recordMenu } = useShellMenus({
    actionsRef,
    terminals,
    openMenu: overlays.openMenu,
    t,
    copy,
    copyLogs: logs.copyLogs,
    paste,
    runAction,
    setFilters: logs.setFilters,
    selectLogLevel: logs.selectLogLevel,
  });
  const panelMaximized = useWorkspaceFocus({
    agentVisible,
    tuiVisible,
    firstPaneShown,
    maximized,
    gated,
    tuiPhase: sessions.status.tui.phase,
    tab: layout.tab,
    focusView,
    focusRail,
    signInButton,
    profilePage: navigation.profilePage,
    ledgerPage: navigation.ledgerPage,
    declarationsPage: navigation.declarationsPage,
    calendarPage: navigation.calendarPage,
    aeatSyncPage: navigation.aeatSyncPage,
    docs,
    agentBody: navigation.agentBody,
    wantsAgent: navigation.wantsAgent,
  });

  const { maximizeControl, splitControls } = paneControls({
    t,
    maximized,
    firstPaneShown,
    tuiVisible,
    prefs,
    byId,
    runAction,
    toggleMaximize,
  });
  const { top: railTop, bottom: railBottom } = railItems({
    t,
    byId,
    runAction,
    host,
    views,
    layout,
    setLayout,
    setPage,
    paletteOpen: overlays.paletteOpen,
    settingsOpen: overlays.settingsOpen,
    setSettingsOpen,
    signedIn,
    phase,
    reader,
    messages,
    agentVisible,
    tuiVisible,
    docsVisible,
    firstPaneShown,
    profileOn: visibility.profileOn,
    aeatSyncOn: visibility.aeatSyncOn,
    ledgerVisible,
    declarationsVisible,
    calendarVisible,
    browserVisible,
    panelVisible,
    showSede,
    aeatMenu,
    driveUrl: setup.driveUrl,
    errorCount: logs.errorCount,
    provisioning: setup.provisioning,
    setupIncomplete: setup.setupIncomplete,
  });

  const docsPane = (
    <MainPane
      host={host}
      reader={reader}
      account={account}
      t={t}
      locale={locale}
      signedIn={signedIn}
      layout={layout}
      prefs={prefs}
      maximized={maximized}
      pageOn={pageOn}
      firstPaneShown={firstPaneShown}
      declarationsOn={visibility.declarationsOn}
      ledgerOn={visibility.ledgerOn}
      browserOn={visibility.browserOn}
      browserMounted={memories.browserMounted}
      profileOn={visibility.profileOn}
      aeatSyncOn={visibility.aeatSyncOn}
      calendarOn={visibility.calendarOn}
      openDeclaration={memories.openDeclaration}
      openWorkUnit={memories.openWorkUnit}
      guarded={guarded}
      askCenso={pageAsks.askCenso}
      askProfileStep={pageAsks.askProfileStep}
      askSignIn={signIn.askSignIn}
      runAction={runAction}
      openView={openView}
      openViewLink={openViewLink}
      ledgerMemory={memories.ledgerMemory}
      setPage={setPage}
      showPage={showPage}
      setMaximized={setMaximized}
      openLink={openLink}
      guardLeave={navigation.guardLeave}
      declarationsPage={navigation.declarationsPage}
      ledgerPage={navigation.ledgerPage}
      browserPage={navigation.browserPage}
      profilePage={navigation.profilePage}
      aeatSyncPage={navigation.aeatSyncPage}
      calendarPage={navigation.calendarPage}
      toggleMaximize={toggleMaximize}
      maximizeControl={maximizeControl}
      splitControls={splitControls}
      closePage={closePage}
      routedLedger={setup.routedLedger}
      modelList={modelList}
      changeLedgerView={changeLedgerView}
      changeProfileView={arrangement.changeProfileView}
      contribute={overlays.contribute}
      setLedgerFloor={arrangement.setLedgerFloor}
      browserHome={memories.browserHome}
      isShellChord={isShellChord}
      setBrowserKeptFor={memories.setBrowserKeptFor}
      byId={byId}
      openMenu={overlays.openMenu}
      profileAccountActions={profileAccountActions}
      copy={copy}
      say={say}
      profileHost={setup.profileHost}
      aeatAsked={pageAsks.aeatAsked}
      aeatHandled={pageAsks.aeatHandled}
      censoAsked={pageAsks.censoAsked}
      censoHandled={pageAsks.censoHandled}
      profileStep={pageAsks.profileStep}
      profileStepHandled={pageAsks.profileStepHandled}
      calendar={reads.calendar}
      calendarProfile={reads.calendarProfile}
      calendarMemory={memories.calendarMemory}
      patch={patch}
      environment={environment}
      docsEntry={docsEntry}
      docs={docs}
      languages={languages}
      language={language}
      chords={chords}
      setDocsTheme={docsFrame.setDocsTheme}
      setDocsSearchReady={docsFrame.setDocsSearchReady}
      runShortcut={runShortcut}
      docsMenu={docsMenu}
    />
  );

  return (
    <ShellContexts
      t={t}
      navigation={nav.runtime}
      provisioning={setup.provisioning}
    >
      <TooltipProvider>
        <div className="desktop-window flex h-dvh min-w-0 flex-col bg-chrome">
          <WindowTitlebar
            host={host}
            t={t}
            account={account}
            signIn={signIn}
            setup={setup}
            fullscreen={fullscreen}
            guardNavigation={guardNavigation}
            say={say}
            about={about}
            setSettingsOpen={setSettingsOpen}
            setAboutOpen={overlays.setAboutOpen}
            setPage={setPage}
            setLayout={setLayout}
          />
          <div
            ref={arrangement.workspace}
            className="shell grid min-h-0 flex-1 grid-cols-[auto_1fr] grid-rows-[minmax(0,1fr)] bg-chrome"
          >
            <Rail
              label={t("desktop.rail.label")}
              top={railTop}
              bottom={railBottom}
            />
            <ShellDock
              host={host}
              t={t}
              locale={locale}
              account={account}
              phase={phase}
              signedIn={signedIn}
              scheme={scheme}
              terminalTheme={terminalTheme}
              terminalFontSize={metrics.terminalFontSize}
              status={sessions.status}
              setStatus={sessions.setStatus}
              terminals={terminals}
              isShellChord={isShellChord}
              terminalMenu={terminalMenu}
              recordMenu={recordMenu}
              signInButton={signInButton}
              askSignIn={signIn.askSignIn}
              agentControl={agentControl}
              agentBody={navigation.agentBody}
              openMenu={overlays.openMenu}
              onToolRefused={setup.onToolRefused}
              openLink={openLink}
              openViewLink={openViewLink}
              settledSetups={setup.settledSetups}
              byId={byId}
              runAction={runAction}
              maximizeControl={maximizeControl}
              splitControls={splitControls}
              layout={layout}
              prefs={prefs}
              setLayout={setLayout}
              maximized={maximized}
              setMaximized={setMaximized}
              patch={patch}
              docking={arrangement.docking}
              changeDocking={arrangement.changeDocking}
              setNarrowedPanes={arrangement.setNarrowedPanes}
              dockMinimumWidths={visibility.dockMinimumWidths}
              dockBesideWidths={visibility.dockBesideWidths}
              dockMinimumHeights={visibility.dockMinimumHeights}
              dockOffered={visibility.dockOffered}
              expandedPane={visibility.expandedPane}
              fullscreen={fullscreen}
              enterFullscreen={arrangement.enterFullscreen}
              revealPane={arrangement.revealPane}
              grantFocus={grantFocus}
              focusView={focusView}
              focusRail={focusRail}
              toggleMaximize={toggleMaximize}
              closeColumn={columns.closeColumn}
              guarded={guarded}
              showPage={showPage}
              closePage={closePage}
              setBrowserKeptFor={memories.setBrowserKeptFor}
              agentVisible={agentVisible}
              tuiVisible={tuiVisible}
              panelVisible={panelVisible}
              activePanes={activePanes}
              pageOn={pageOn}
              profileOn={visibility.profileOn}
              calendarOn={visibility.calendarOn}
              ledgerOn={visibility.ledgerOn}
              declarationsOn={visibility.declarationsOn}
              browserOn={visibility.browserOn}
              aeatSyncOn={visibility.aeatSyncOn}
              docsEntry={docsEntry}
              setErrorCount={logs.setErrorCount}
              filters={logs.filters}
              defaultFilters={logs.defaultFilters}
              setFilters={logs.setFilters}
              selectLogLevel={logs.selectLogLevel}
              copyLogs={logs.copyLogs}
              exportLogs={logs.exportLogs}
              revealLogs={logs.revealLogs}
              main={docsPane}
            />
            <WindowOverlays
              host={host}
              t={t}
              locale={locale}
              account={account}
              signedIn={signedIn}
              reader={reader}
              overlays={overlays}
              prefs={prefs}
              setPrefs={setPrefs}
              setLayout={setLayout}
              setMaximized={setMaximized}
              languageControl={languageControl}
              about={about}
              actions={actions}
              pastedLink={pastedLink}
              searchDocs={searchDocs}
              openDoc={openDoc}
              focusRail={focusRail}
              copy={copy}
              say={say}
              toast={toast}
              askSignIn={signIn.askSignIn}
              prompt={nav.prompt}
              setupOffered={setup.setupOffered}
            />
            <AccountDialogs
              host={host}
              account={account}
              accountRef={signIn.accountRef}
              signInAsked={signIn.signInAsked}
              signInDismissed={signIn.signInDismissed}
              setSignInDismissed={signIn.setSignInDismissed}
              creatingProfile={signIn.creatingProfile}
              setCreatingProfile={signIn.setCreatingProfile}
              managingProfiles={signIn.managingProfiles}
              setManagingProfiles={signIn.setManagingProfiles}
              askNewProfile={signIn.askNewProfile}
              signInOpener={signIn.signInOpener}
              signInButton={signInButton}
              calendarPage={navigation.calendarPage}
              docs={docs}
              grantFocus={grantFocus}
              focusView={focusView}
              focusRail={focusRail}
              panelMaximized={panelMaximized}
              tab={layout.tab}
              tuiVisible={tuiVisible}
            />
          </div>
        </div>
        <AttendanceRequests
          attendance={host.attendance}
          profile={signedIn ? (account.status?.active_profile ?? null) : null}
          locale={locale}
        />
      </TooltipProvider>
    </ShellContexts>
  );
}
