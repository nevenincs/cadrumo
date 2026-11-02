import { useEffect, useMemo, useState } from "react";
import type { LedgerPort } from "../../../shell/ledger";
import type {
  InventoryListResult,
  InventoryInspectResult,
  InventoryOptionsResult,
} from "../../../shell/ledgerSetup";
import { useWritePause } from "../WritePause";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { offersOf, NO_OFFERS, vocabularyOf } from "./stockVocabulary";

/** The book a task acts on. */
export type BookKey = { actividad_id: string; year: number };
export const keyOf = (book: BookKey) => `${book.actividad_id}|${book.year}`;

// ---- Reading the books -------------------------------------------------------------

/** Reads the stock books while the pane shows, again after a `reload` or the
 * page's re-read, and drops what it read with the profile. The last answer
 * stays while the next is read. */
export function useBookList(
  port: LedgerPort,
  reader: string | null,
  round: number,
) {
  const [list, setList] = useState<SetupCall<InventoryListResult> | null>(null);
  const { round: reread } = useWritePause();
  useEffect(() => {
    setList(null);
  }, [port, reader]);
  useEffect(() => {
    if (reader === null) return;
    let active = true;
    void (async () => {
      const answer = await setupCall(port, "ledger.inventory.list", {}, false);
      if (active) setList(answer);
    })();
    return () => {
      active = false;
    };
  }, [port, reader, round, reread]);
  return list;
}

/** Reads the chosen book with its movements and history, again after a
 * reload; what it read is the chosen book's alone. */
export function useBookDetail(
  port: LedgerPort,
  reader: string | null,
  book: BookKey | null,
  round: number,
) {
  const [detail, setDetail] = useState<{
    key: string;
    call: SetupCall<InventoryInspectResult>;
  } | null>(null);
  const { round: reread } = useWritePause();
  const name = book?.actividad_id ?? null;
  const year = book?.year ?? null;
  const key =
    name === null || year === null ? null : keyOf({ actividad_id: name, year });
  useEffect(() => {
    setDetail(null);
  }, [port, reader]);
  useEffect(() => {
    if (reader === null || name === null || year === null || key === null)
      return;
    let active = true;
    void (async () => {
      const call = await setupCall(
        port,
        "ledger.inventory.inspect",
        { actividad_id: name, year },
        false,
      );
      if (active) setDetail({ key, call });
    })();
    return () => {
      active = false;
    };
  }, [port, reader, name, year, key, round, reread]);
  return detail && detail.key === key ? detail.call : null;
}

/** Reads the closed choices the forms offer. They are the backend's to
 * serve, so a form offers none until they are read. */
export function useOffers(
  port: LedgerPort,
  reader: string | null,
  round: number,
) {
  const [read, setRead] = useState<SetupCall<InventoryOptionsResult> | null>(
    null,
  );
  useEffect(() => {
    setRead(null);
  }, [port, reader]);
  useEffect(() => {
    if (reader === null) return;
    let active = true;
    void (async () => {
      const answer = await setupCall(
        port,
        "ledger.inventory.options",
        {},
        false,
      );
      if (active) setRead(answer);
    })();
    return () => {
      active = false;
    };
  }, [port, reader, round]);
  const offers = useMemo(
    () => (read?.kind === "done" ? offersOf(read.result) : NO_OFFERS),
    [read],
  );
  const vocabulary = useMemo(() => vocabularyOf(offers), [offers]);
  return { offers, vocabulary, state: read === null ? "loading" : read.kind };
}

export type OfferState = ReturnType<typeof useOffers>;
