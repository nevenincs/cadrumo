import { useState, type RefObject } from "react";
import type { CalendarMemory } from "../components/FilingCalendar";
import type { LedgerMemory } from "../components/ledger/LedgerPage";
import type { DeclarationsMemory } from "../components/modelo/declarations/DeclarationsPage";

/** What the pages keep of themselves while they are put away, for one
 * profile and one sign-in, in memory only. */
export function usePageMemories({
  reader,
  browserOn,
  wantsDeclarations,
}: {
  reader: string | null;
  browserOn: boolean;
  wantsDeclarations: RefObject<boolean>;
}) {
  // The browser's view goes on while its page is put aside: the page stays
  // mounted, hidden, for the profile that opened it, until the person closes
  // it or that profile is no longer the one signed in.
  const [browserKeptFor, setBrowserKeptFor] = useState<string | null>(null);
  const browserReader = browserOn
    ? reader
    : reader === browserKeptFor
      ? browserKeptFor
      : null;
  if (browserReader !== browserKeptFor) setBrowserKeptFor(browserReader);
  const browserMounted = browserOn || browserReader !== null;
  // Raised to send an open view to its home page, the Sede.
  const [browserHome, setBrowserHome] = useState(0);
  // What the reader has made of the calendar, kept while its page is away:
  // the page is taken down when it is put away, and comes back as it was.
  // A calendar belongs to its profile, and so does what was made of it: a
  // new memory for each profile, and for each time one is signed in.
  const [calendarKept, setCalendarKept] = useState(() => ({
    reader,
    memory: { current: {} as CalendarMemory },
  }));
  if (calendarKept.reader !== reader)
    setCalendarKept({ reader, memory: { current: {} } });
  const calendarMemory = calendarKept.memory;
  // The ledger's period, kept while its page is away, for one profile and
  // one sign-in, in memory only.
  const [ledgerKept, setLedgerKept] = useState(() => ({
    reader,
    memory: { current: {} as LedgerMemory },
  }));
  if (ledgerKept.reader !== reader)
    setLedgerKept({ reader, memory: { current: {} } });
  // The declaration open in the workspace, and what the list keeps of
  // itself meanwhile, for one profile and one sign-in, in memory only; no
  // declaration shows the list.
  const [openDeclaration, setOpenDeclaration] = useState(() => ({
    reader,
    workUnitId: null as string | null,
    memory: { current: {} as DeclarationsMemory },
  }));
  if (openDeclaration.reader !== reader)
    setOpenDeclaration({ reader, workUnitId: null, memory: { current: {} } });
  const openWorkUnit = (workUnitId: string | null) => {
    wantsDeclarations.current = true;
    setOpenDeclaration((held) => ({ ...held, workUnitId }));
  };
  return {
    setBrowserKeptFor,
    browserMounted,
    browserHome,
    setBrowserHome,
    calendarMemory,
    ledgerMemory: ledgerKept.memory,
    openDeclaration,
    openWorkUnit,
  };
}
