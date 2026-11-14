import {
  useCallback,
  useEffect,
  useRef,
  type RefObject,
  type SetStateAction,
} from "react";
import type { LeaveGuard } from "../components/ledger/editing/LedgerEditing";
import type { DockPane } from "./docking";
import type { Host } from "./host";
import type { Layout, LedgerSection, Maximized } from "./layout";
import { NAVIGATION } from "./navigation/projection";
import { lineage } from "./navigation/register";
import { useNavigator, type NavigatorWindow } from "./navigation/useNavigator";
import { useWindowCloseGuard } from "./navigation/useWindowCloseGuard";
import { mountedNow, pageViewId, windowView } from "./navigation/windowViews";
import type { SignInController } from "./signIn";
import type { Translate } from "./strings";

/** What the navigator calls back into the window that the window composes
 * after the navigator: applying a view, and asking for the sign-in. */
export type WindowCommands = Pick<
  NavigatorWindow,
  "showInWindow" | "askSignIn"
>;

/** The window's navigation: every navigation passes one guard register and
 * one navigator, from a link, the palette, the rail, a page, sign-out, a
 * profile switch and the window's close; the pages it shows, and where the
 * keyboard goes when one is opened. */
export function useWindowNavigation({
  host,
  t,
  say,
  account,
  layoutNow,
  setMaximized,
  patch,
  showPage,
  activatePane,
}: {
  host: Host;
  t: Translate;
  say: (text: string) => void;
  account: SignInController;
  layoutNow: RefObject<Layout>;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  patch: (change: Partial<Layout>) => void;
  showPage: (page: Layout["page"]) => void;
  activatePane: (pane: DockPane) => void;
}) {
  // What the navigator calls back is read when it runs, after render.
  const accountNow = useRef(account);
  accountNow.current = account;
  const commands = useRef<WindowCommands | null>(null);
  /** Hands the navigator what the window composes after it; called on every
   * render, before any navigation can run. */
  const bindWindow = (bound: WindowCommands) => {
    commands.current = bound;
  };
  const nav = useNavigator({
    register: NAVIGATION,
    t,
    say,
    shown: () => ({
      page: layoutNow.current.page,
      ledgerSection: layoutNow.current.ledgerView.section,
    }),
    hasPort: (port) => host[port] !== undefined,
    signedIn: () => accountNow.current.phase === "signed-in",
    showInWindow: (id, entry) => commands.current?.showInWindow(id, entry),
    askSignIn: () => commands.current?.askSignIn(),
  });
  const guardNavigation = nav.guard;
  // An owner that hands the shell a leave guard of its own is registered as
  // dirty work of the page it was shown on; its guard asks only when it has
  // something staged. `guarded` leaves the page shown.
  const ownerGuard = useRef<(() => void) | null>(null);
  const guardLeave = useCallback(
    (guard: LeaveGuard | null) => {
      ownerGuard.current?.();
      ownerGuard.current = guard
        ? nav.runtime.guards.register({
            owner: layoutNow.current.page,
            state: () => "dirty",
            ask: guard,
          })
        : null;
    },
    [nav.runtime, layoutNow],
  );
  const guarded = useCallback(
    (proceed: () => void, stay?: () => void) =>
      guardNavigation(
        {
          kind: "navigate",
          unmounted: mountedNow(
            layoutNow.current.page,
            layoutNow.current.ledgerView.section,
          ),
        },
        proceed,
        stay,
      ),
    [guardNavigation, layoutNow],
  );
  useWindowCloseGuard(host, guardNavigation);
  // Leaving the page shown takes it down, so its owners are asked first.
  const setPage = useCallback(
    (next: Layout["page"]) => {
      const shown = layoutNow.current;
      if (next === shown.page) {
        activatePane("docs");
        return;
      }
      guardNavigation(
        {
          kind: "navigate",
          unmounted: mountedNow(shown.page, shown.ledgerView.section),
        },
        () => showPage(next),
      );
    },
    [guardNavigation, showPage, activatePane, layoutNow],
  );
  const calendarPage = useRef<HTMLElement>(null);
  const aeatSyncPage = useRef<HTMLElement>(null);
  const profilePage = useRef<HTMLElement>(null);
  const ledgerPage = useRef<HTMLElement>(null);
  // The ledger was asked for: it takes focus once it is laid out.
  const wantsLedger = useRef(false);
  const declarationsPage = useRef<HTMLElement>(null);
  // The declarations, or one declaration, were asked for: the page takes
  // focus once it is laid out.
  const wantsDeclarations = useRef(false);
  const browserPage = useRef<HTMLElement>(null);
  // The browser was asked for: the page takes focus once it is laid out.
  const wantsBrowser = useRef(false);
  // The agent column was asked for: it takes focus once it is laid out.
  const wantsAgent = useRef(false);
  const agentBody = useRef<HTMLElement>(null);
  // Where the keyboard goes when a navigation opens each page or the agent.
  // The window provides the navigation context, so it registers its own
  // targets on the runtime directly; its commits are their mount signal.
  useEffect(() => {
    const focus = nav.runtime.focus;
    const targets: [string, { current: HTMLElement | null }][] = [
      ["profile", profilePage],
      ["calendar", calendarPage],
      ["aeat-sync", aeatSyncPage],
      ["ledger", ledgerPage],
      ["declarations", declarationsPage],
      ["agent", agentBody],
      // The documentation is a frame the window does not hold a ref to.
      [
        "docs",
        {
          get current() {
            return document.querySelector<HTMLElement>(".docs-frame");
          },
        },
      ],
    ];
    const releases = targets.map(([id, ref]) =>
      focus.register(id, () => ref.current),
    );
    return () => releases.forEach((release) => release());
  }, [nav.runtime]);
  // A page the window's back or forward returns to, already let through
  // the guard: applied as the navigator applies the element that opens it,
  // and given the keyboard as it would be.
  const showPagePlace = useCallback(
    (page: Layout["page"], section: LedgerSection | null) => {
      const id = pageViewId(
        page,
        section ?? layoutNow.current.ledgerView.section,
      );
      const entry = id === undefined ? undefined : windowView(id);
      if (id === undefined || !entry) {
        showPage(page);
        return;
      }
      commands.current?.showInWindow(id, entry);
      nav.runtime.focus.request(
        lineage(NAVIGATION, id).map((element) => element.id),
        performance.now(),
      );
    },
    [layoutNow, showPage, nav.runtime],
  );
  // The calendar was asked for: it takes focus once it is laid out.
  const wantsCalendar = useRef(false);
  // The documentation asked for by name: its pane is shown first.
  const showDocs = useCallback(() => {
    setPage("docs");
    setMaximized((area) => (area === "docs" ? area : null));
    patch({ docsShown: true });
  }, [patch, setPage, setMaximized]);
  // A page of the first pane is put away by its own close, back to the
  // documentation where that is shown.
  const closePage = () => {
    setPage("docs");
    setMaximized(null);
  };
  return {
    nav,
    bindWindow,
    guardNavigation,
    guardLeave,
    guarded,
    setPage,
    showPagePlace,
    showDocs,
    closePage,
    calendarPage,
    aeatSyncPage,
    profilePage,
    ledgerPage,
    declarationsPage,
    browserPage,
    agentBody,
    wantsCalendar,
    wantsLedger,
    wantsDeclarations,
    wantsBrowser,
    wantsAgent,
  };
}
