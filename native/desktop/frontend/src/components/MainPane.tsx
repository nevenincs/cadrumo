import {
  useCallback,
  type ComponentProps,
  type RefObject,
  type SetStateAction,
} from "react";
import { EmptyState } from "@/components/ui/empty";
import type { DocsLanguage } from "../ipc/environment";
import type { Action } from "../shell/actions";
import { ModelListContext, type ModelList } from "../shell/agentModelList";
import type { useFilingCalendar } from "../shell/calendar";
import type { Host } from "../shell/host";
import type { LedgerProfileStep } from "../shell/ledger";
import type {
  Layout,
  LedgerView,
  Maximized,
  Prefs,
  ProfileView,
} from "../shell/layout";
import type { OutputLanguage } from "../shell/modeloContract/modelo";
import type { useNavigator } from "../shell/navigation/useNavigator";
import type { SignInController } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import type { useDesktopEnvironment } from "../shell/useDesktopEnvironment";
import type { useLanguage } from "../shell/useLanguage";
import type { useShellMenus } from "../shell/useShellMenus";
import type { useShellShortcuts } from "../shell/useShellShortcuts";
import type { useUserProfile } from "../shell/userProfile";
import type { useWindowSetup } from "../shell/useWindowSetup";
import { AeatSyncPage } from "./aeatSync/AeatSyncPage";
import { BrowserPage } from "./browser/BrowserPage";
import type { OpenMenu } from "./ContextMenu";
import { DocsFrame, type DocsFrameApi } from "./DocsFrame";
import { FilingCalendarView, type CalendarMemory } from "./FilingCalendar";
import type { LeaveGuard } from "./ledger/editing/LedgerEditing";
import { LedgerPage, type LedgerMemory } from "./ledger/LedgerPage";
import { DeclarationsPane } from "./modelo/declarations/DeclarationsPane";
import type { DeclarationsMemory } from "./modelo/declarations/DeclarationsPage";
import type { PaneControl } from "./PaneHeader";
import { UserProfilePage } from "./profile/UserProfilePage";
import { SignedOut } from "./SignIn";

type Navigator = ReturnType<typeof useNavigator>;
type PageRef = RefObject<HTMLElement | null>;
type Area = Exclude<Maximized, null>;

/** What the first pane holds: the page of the profile asked for, or the
 * documentation, which stays loaded underneath a page. */
export function MainPane({
  host,
  reader,
  account,
  t,
  locale,
  signedIn,
  layout,
  prefs,
  maximized,
  pageOn,
  firstPaneShown,
  declarationsOn,
  ledgerOn,
  browserOn,
  browserMounted,
  profileOn,
  aeatSyncOn,
  calendarOn,
  openDeclaration,
  openWorkUnit,
  guarded,
  askCenso,
  askProfileStep,
  askSignIn,
  runAction,
  openView,
  openViewLink,
  ledgerMemory,
  setPage,
  showPage,
  setMaximized,
  openLink,
  guardLeave,
  declarationsPage,
  ledgerPage,
  browserPage,
  profilePage,
  aeatSyncPage,
  calendarPage,
  toggleMaximize,
  maximizeControl,
  splitControls,
  closePage,
  routedLedger,
  modelList,
  changeLedgerView,
  changeProfileView,
  contribute,
  setLedgerFloor,
  browserHome,
  isShellChord,
  setBrowserKeptFor,
  byId,
  openMenu,
  profileAccountActions,
  copy,
  say,
  profileHost,
  aeatAsked,
  aeatHandled,
  censoAsked,
  censoHandled,
  profileStep,
  profileStepHandled,
  calendar,
  calendarProfile,
  calendarMemory,
  patch,
  environment,
  docsEntry,
  docs,
  languages,
  language,
  chords,
  setDocsTheme,
  setDocsSearchReady,
  runShortcut,
  docsMenu,
}: {
  host: Host;
  reader: string | null;
  account: SignInController;
  t: Translate;
  locale: string;
  signedIn: boolean;
  layout: Layout;
  prefs: Prefs;
  maximized: Maximized;
  pageOn: boolean;
  firstPaneShown: boolean;
  declarationsOn: boolean;
  ledgerOn: boolean;
  browserOn: boolean;
  browserMounted: boolean;
  profileOn: boolean;
  aeatSyncOn: boolean;
  calendarOn: boolean;
  openDeclaration: {
    workUnitId: string | null;
    memory: { current: DeclarationsMemory };
  };
  openWorkUnit: (workUnitId: string | null) => void;
  guarded: (proceed: () => void) => void;
  askCenso: () => void;
  askProfileStep: (step: LedgerProfileStep) => void;
  askSignIn: () => void;
  runAction: (id: string) => void;
  openView: Navigator["openView"];
  openViewLink: Navigator["openLink"];
  ledgerMemory: { current: LedgerMemory };
  setPage: (next: Layout["page"]) => void;
  showPage: (page: Layout["page"]) => void;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  openLink: (url: string) => void;
  guardLeave: (guard: LeaveGuard | null) => void;
  declarationsPage: PageRef;
  ledgerPage: PageRef;
  browserPage: PageRef;
  profilePage: PageRef;
  aeatSyncPage: PageRef;
  calendarPage: PageRef;
  toggleMaximize: (area: Area) => void;
  maximizeControl: (area: Area, labelKey: string) => PaneControl;
  splitControls: PaneControl[];
  closePage: () => void;
  routedLedger: ReturnType<typeof useWindowSetup>["routedLedger"];
  modelList: ModelList | null;
  changeLedgerView: (update: (current: LedgerView) => LedgerView) => void;
  changeProfileView: (update: (current: ProfileView) => ProfileView) => void;
  contribute: (actions: (() => Action[]) | null) => void;
  setLedgerFloor: (floor: number | null) => void;
  browserHome: number;
  isShellChord: ReturnType<typeof useShellShortcuts>["isShellChord"];
  setBrowserKeptFor: (reader: string | null) => void;
  byId: (id: string) => Action | undefined;
  openMenu: OpenMenu;
  profileAccountActions: () => Action[];
  copy: (text: string) => void;
  say: (text: string) => void;
  profileHost: ReturnType<typeof useWindowSetup>["profileHost"];
  aeatAsked: boolean;
  aeatHandled: () => void;
  censoAsked: boolean;
  censoHandled: () => void;
  profileStep: LedgerProfileStep | null;
  profileStepHandled: () => void;
  calendar: ReturnType<typeof useFilingCalendar>;
  calendarProfile: ReturnType<typeof useUserProfile>;
  calendarMemory: { current: CalendarMemory };
  patch: (change: Partial<Layout>) => void;
  environment: ReturnType<typeof useDesktopEnvironment>;
  docsEntry: DocsLanguage | null;
  docs: RefObject<DocsFrameApi | null>;
  languages: ComponentProps<typeof DocsFrame>["languages"];
  language: ReturnType<typeof useLanguage>;
  chords: ReturnType<typeof useShellShortcuts>["chords"];
  setDocsTheme: ComponentProps<typeof DocsFrame>["onTheme"];
  setDocsSearchReady: (ready: boolean) => void;
  runShortcut: ReturnType<typeof useShellShortcuts>["runShortcut"];
  docsMenu: ReturnType<typeof useShellMenus>["docsMenu"];
}) {
  // The profile page is large: what it is given stays the same object from
  // one render of the window to the next, so it draws only when it changes.
  const toggleProfileMaximized = useCallback(
    () => toggleMaximize("docs"),
    [toggleMaximize],
  );
  return (
    <>
      {declarationsOn && host.modelo ? (
        <DeclarationsPane
          port={host.modelo}
          reader={reader}
          workUnitId={openDeclaration.workUnitId}
          onOpen={openWorkUnit}
          onOpenWork={(id) => guarded(() => openWorkUnit(id))}
          // The one census flow, as the palette offers it.
          onCensus={
            signedIn && host.censo && host.userProfile ? askCenso : undefined
          }
          // The door a readiness refusal here names; only the window that has
          // a profile page can offer it.
          onProfileStep={
            signedIn && host.userProfile ? askProfileStep : undefined
          }
          // The movement a calculation refusal names; only a window with a
          // Libro can open it.
          onOpenMovement={
            host.ledger
              ? (transactionId) =>
                  guarded(() =>
                    openView(
                      "ledger/movements",
                      { select: transactionId },
                      null,
                    ),
                  )
              : undefined
          }
          // The invoice a check line asks a document for.
          onOpenInvoice={
            host.ledger
              ? (invoiceId) =>
                  guarded(() =>
                    openView("ledger/invoices", { select: invoiceId }, null),
                  )
              : undefined
          }
          onBack={() => guarded(() => openWorkUnit(null))}
          onOpenSurface={(surface) => {
            if (surface === "declarations") guarded(() => openWorkUnit(null));
            else if (surface === "ledger") runAction("view.ledger");
            else if (surface === "withholding")
              // The Ledger page opens on the area asked for, once shown.
              openView("ledger/registers", {}, null, {
                opened: () => {
                  ledgerMemory.current.registersArea = "withholding";
                },
              });
            else if (surface === "profile") setPage("profile");
          }}
          // Only an area this window has a page for is linked.
          canOpenSurface={(surface) =>
            surface === "declarations" ||
            (surface === "ledger" && host.ledger !== undefined) ||
            (surface === "withholding" && host.ledger !== undefined) ||
            (surface === "profile" && host.userProfile !== undefined)
          }
          openLink={openLink}
          guardLeave={guardLeave}
          memory={openDeclaration.memory}
          withheld={
            <SignedOut
              account={account}
              lead={t("desktop.declarations.signed_out")}
              quiet
              onSignIn={askSignIn}
            />
          }
          // The desktop's locales are the read models' output languages.
          language={locale as OutputLanguage}
          locale={locale}
          shown={firstPaneShown}
          page={declarationsPage}
          profileCompanions={
            host.profileCompanions && host.userProfile
              ? {
                  reads: host.profileCompanions,
                  change: host.userProfile.change,
                }
              : undefined
          }
          borrador={host.borrador}
          pane={{
            title: t("workspace.declarations.destination.overview"),
            onToggleMaximize: () => toggleMaximize("docs"),
            controls: [
              maximizeControl("docs", "desktop.declarations.maximize"),
              ...splitControls.map((control) => ({
                ...control,
                yields: true,
              })),
              {
                id: "close",
                icon: "close",
                label: t("desktop.declarations.close"),
                run: closePage,
              },
            ],
          }}
        />
      ) : ledgerOn && routedLedger ? (
        <ModelListContext.Provider value={modelList}>
          <LedgerPage
            key={reader ?? ""}
            port={routedLedger}
            reader={reader}
            withheld={
              <SignedOut
                account={account}
                lead={t("desktop.ledger.signed_out")}
                quiet
                onSignIn={askSignIn}
              />
            }
            locale={locale}
            shown={firstPaneShown}
            page={ledgerPage}
            view={layout.ledgerView}
            onViewChange={changeLedgerView}
            memory={ledgerMemory}
            contribute={contribute}
            copy={(text) => host.writeClipboard(text)}
            onOpenLink={openLink}
            onFloor={setLedgerFloor}
            pane={{
              title: t("desktop.ledger.title"),
              onToggleMaximize: () => toggleMaximize("docs"),
              controls: [
                maximizeControl("docs", "desktop.ledger.maximize"),
                ...splitControls.map((control) => ({
                  ...control,
                  yields: true,
                })),
                {
                  id: "close",
                  icon: "close",
                  label: t("desktop.ledger.close"),
                  run: closePage,
                },
              ],
            }}
          />
        </ModelListContext.Provider>
      ) : null}
      {browserMounted && host.sedeView && (
        // A view the runtime refuses for a missing component offers its setup.
        <BrowserPage
          key={reader ?? ""}
          port={host.sedeView}
          withheld={
            reader === null ? (
              <SignedOut
                account={account}
                lead={t("desktop.browser.failure.not_signed_in")}
                quiet
                onSignIn={askSignIn}
              />
            ) : undefined
          }
          page={browserPage}
          shown={browserOn && firstPaneShown}
          home={browserHome}
          isShellChord={isShellChord}
          pane={{
            title: t("desktop.browser.title"),
            onToggleMaximize: () => toggleMaximize("docs"),
            controls: [
              maximizeControl("docs", "desktop.browser.maximize"),
              ...splitControls.map((control) => ({
                ...control,
                yields: true,
              })),
              {
                id: "close",
                icon: "close",
                label: t("desktop.browser.close"),
                // Closing the page, unlike leaving it, ends the view.
                run: () => {
                  guarded(() => {
                    setBrowserKeptFor(null);
                    showPage("docs");
                  });
                  setMaximized(null);
                },
              },
            ],
          }}
        />
      )}
      {profileOn &&
        (reader !== null ? (
          <UserProfilePage
            maximized={maximized === "docs"}
            onToggleMaximize={toggleProfileMaximized}
            maximizeChord={byId("view.maximize")?.chords?.[0]}
            contribute={contribute}
            openMenu={openMenu}
            accountActions={profileAccountActions}
            onCopy={copy}
            onNotice={say}
            view={layout.profileView}
            onViewChange={changeProfileView}
            page={profilePage}
            key={reader}
            host={profileHost}
            reader={reader}
            sessionEnded={account.sessionEnded}
            language={locale}
            shown={firstPaneShown}
            aeatAsked={aeatAsked}
            onAeatHandled={aeatHandled}
            censoAsked={censoAsked}
            onCensoHandled={censoHandled}
            profileStep={profileStep}
            onProfileStepHandled={profileStepHandled}
          />
        ) : (
          <SignedOut
            account={account}
            lead={t("desktop.profile.signed_out")}
            quiet
            onSignIn={askSignIn}
          />
        ))}
      {aeatSyncOn &&
        host.aeatSync &&
        (reader !== null ? (
          <AeatSyncPage
            key={reader}
            port={host.aeatSync}
            reader={reader}
            language={locale}
            shown={firstPaneShown}
            page={aeatSyncPage}
            results={host.aeatSyncResults}
            run={host.aeatSyncRun}
            prepare={host.aeatSyncPrepare}
            onOpenAccess={() => openView("profile/aeat-access")}
            onOpenAeat={() => openView("browser")}
            onReviewCensus={askCenso}
          />
        ) : (
          <SignedOut
            account={account}
            lead={t("desktop.aeat_sync.signed_out")}
            quiet
            onSignIn={askSignIn}
          />
        ))}
      {calendarOn && (
        <FilingCalendarView
          page={calendarPage}
          state={calendar.state}
          profile={
            calendarProfile.loading || calendarProfile.error
              ? null
              : calendarProfile.data
          }
          onNavigate={openViewLink}
          attempt={calendar.attempt}
          today={calendar.today}
          memory={calendarMemory}
          defaultView={layout.calendarView}
          onViewChange={(calendarView) => patch({ calendarView })}
          // Withheld, it says what the TUI pane says of the account, with
          // the same ways on.
          withheld={
            <SignedOut
              account={account}
              lead={t("desktop.calendar.signed_out")}
              quiet
              onSignIn={askSignIn}
            />
          }
          locale={locale}
          refreshing={calendar.refreshing}
          onRefresh={calendar.refresh}
        />
      )}
      {/* Put aside, not unloaded: the page it was on is there on return. */}
      <div className={pageOn ? "hidden" : "contents"}>
        {environment.state === "ready" &&
        environment.value.docs.state === "bundled" &&
        docsEntry ? (
          <DocsFrame
            ref={docs}
            origin={environment.value.docs.origin}
            entry={docsEntry.entry}
            language={docsEntry.code}
            languages={languages}
            onLanguage={(code) => void language.change(code)}
            title={t("desktop.docs.frame_title")}
            chords={chords}
            zoom={layout.zoom}
            appearance={prefs.appearance === "follow" ? null : prefs.appearance}
            onReady={({ theme, features }) => {
              setDocsTheme(theme);
              setDocsSearchReady(features.includes("search"));
            }}
            onTheme={setDocsTheme}
            onShortcut={runShortcut}
            onOpenExternal={(url) =>
              void host.openExternal(url).catch(() => undefined)
            }
            onMenu={docsMenu}
          />
        ) : environment.state === "ready" &&
          environment.value.docs.state !== "bundled" ? (
          <EmptyState
            role="status"
            icon="book"
            description={t(
              environment.value.docs.state === "notBundled"
                ? "desktop.docs.not_bundled"
                : "desktop.docs.unavailable",
            )}
          />
        ) : environment.state === "unavailable" ? (
          <EmptyState
            role="status"
            icon="unplug"
            description={t("desktop.host.unavailable")}
          />
        ) : environment.state === "failed" ? (
          <EmptyState
            role="alert"
            icon="alert"
            description={t("desktop.host.failed")}
          />
        ) : (
          <EmptyState
            role="status"
            busy
            description={t("desktop.docs.loading")}
          />
        )}
      </div>
    </>
  );
}
