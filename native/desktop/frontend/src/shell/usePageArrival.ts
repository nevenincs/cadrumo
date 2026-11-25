import {
  useCallback,
  useEffect,
  useRef,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import type { DocsFrameApi } from "../components/DocsFrame";
import type { Layout, Maximized } from "./layout";
import type { usePageMemories } from "./usePageMemories";

type PageRef = RefObject<HTMLElement | null>;

/** A page asked for takes the keyboard once it is laid out; the calendar
 * put away hands focus on when it held it. Also opens the browser page, at
 * the Sede when asked to. */
export function usePageArrival({
  calendarVisible,
  ledgerVisible,
  declarationsVisible,
  browserVisible,
  firstPaneShown,
  openDeclaration,
  calendarPage,
  ledgerPage,
  declarationsPage,
  browserPage,
  wantsCalendar,
  wantsLedger,
  wantsDeclarations,
  wantsBrowser,
  docs,
  browserMounted,
  setBrowserHome,
  setMaximized,
  setPage,
}: {
  calendarVisible: boolean;
  ledgerVisible: boolean;
  declarationsVisible: boolean;
  browserVisible: boolean;
  firstPaneShown: boolean;
  openDeclaration: ReturnType<typeof usePageMemories>["openDeclaration"];
  calendarPage: PageRef;
  ledgerPage: PageRef;
  declarationsPage: PageRef;
  browserPage: PageRef;
  wantsCalendar: RefObject<boolean>;
  wantsLedger: RefObject<boolean>;
  wantsDeclarations: RefObject<boolean>;
  wantsBrowser: RefObject<boolean>;
  docs: RefObject<DocsFrameApi | null>;
  browserMounted: boolean;
  setBrowserHome: Dispatch<SetStateAction<number>>;
  setMaximized: (update: SetStateAction<Maximized>) => void;
  setPage: (next: Layout["page"]) => void;
}) {
  // The keyboard goes to the calendar when it was asked for and is laid
  // out. Put away, focus stays where it is, unless it was in the page: then
  // it goes to what the pane shows instead.
  const calendarWas = useRef(calendarVisible);
  useEffect(() => {
    if (calendarVisible && wantsCalendar.current) {
      wantsCalendar.current = false;
      calendarPage.current?.focus();
    } else if (
      !calendarVisible &&
      calendarWas.current &&
      firstPaneShown &&
      document.activeElement === document.body
    )
      (
        docs.current ??
        document.querySelector<HTMLElement>(".rail [role=toolbar]")
      )?.focus();
    calendarWas.current = calendarVisible;
  }, [calendarVisible, firstPaneShown, wantsCalendar, calendarPage, docs]);
  useEffect(() => {
    if (ledgerVisible && wantsLedger.current) {
      wantsLedger.current = false;
      ledgerPage.current?.focus();
    }
  }, [ledgerVisible, wantsLedger, ledgerPage]);
  useEffect(() => {
    if (declarationsVisible && wantsDeclarations.current) {
      wantsDeclarations.current = false;
      // The page may already have put the keyboard on a row of its own, the
      // one a declaration was opened from; that is more specific than the
      // page and is kept.
      const page = declarationsPage.current;
      if (!page?.contains(document.activeElement)) page?.focus();
    }
  }, [
    declarationsVisible,
    openDeclaration,
    wantsDeclarations,
    declarationsPage,
  ]);
  useEffect(() => {
    if (browserVisible && wantsBrowser.current) {
      wantsBrowser.current = false;
      browserPage.current?.focus();
    }
  }, [browserVisible, wantsBrowser, browserPage]);
  // The page asks for the Sede itself, so opening it names no address; shown
  // already, it only takes the keyboard.
  const showBrowser = useCallback(() => {
    if (browserVisible) {
      browserPage.current?.focus();
      return;
    }
    wantsBrowser.current = true;
    setMaximized((area) => (area === "docs" ? area : null));
    setPage("browser");
  }, [browserVisible, setMaximized, setPage, browserPage, wantsBrowser]);
  // The AEAT shortcut: the browser at the Sede. A view already open is sent
  // back there; a new one starts there.
  const showSede = useCallback(() => {
    if (browserMounted) setBrowserHome((count) => count + 1);
    showBrowser();
  }, [browserMounted, showBrowser, setBrowserHome]);
  return { showBrowser, showSede };
}
