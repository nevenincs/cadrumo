import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import type {
  LedgerDefinitionId,
  LedgerPort,
  LedgerRequest,
  LedgerResult,
} from "../../../shell/ledger";
import type { AssetListRow } from "../../../shell/ledgerSetup";
import { useWritePause } from "../WritePause";
import { setupCall, type SetupCall } from "../setup/setupModel";
import type { FormDraft } from "./assetFormValues";

// ---- Reading --------------------------------------------------------------------

/**
 * Reads one operation while the form shows, again when `key` changes, on
 * `reload` or after the page re-reads a write it held, and drops what it read
 * with the account. A null `payload` reads nothing; an omitted `reader` reads
 * the port's own ledger; a read that a later one replaced is never shown.
 */
export function useLedgerRead<D extends LedgerDefinitionId>(
  port: LedgerPort,
  reader: string | null | undefined,
  id: D,
  payload: LedgerRequest<D> | null,
  key: string,
): { read: SetupCall<LedgerResult<D>> | null; reload(): void } {
  const [read, setRead] = useState<SetupCall<LedgerResult<D>> | null>(null);
  const [round, setRound] = useState(0);
  const { round: reread } = useWritePause();
  const latest = useRef(payload);
  latest.current = payload;
  useEffect(() => {
    const asked = latest.current;
    if (reader === null || asked === null) return;
    let active = true;
    void setupCall(port, id, asked, false).then((answered) => {
      if (active) setRead(answered);
    });
    return () => {
      active = false;
      setRead(null);
    };
  }, [port, reader, id, key, round, reread]);
  const reload = useCallback(() => setRound((value) => value + 1), []);
  return { read, reload };
}

/** The element a form acts on, as the register lists it now. */
export function useAssetRow(
  port: LedgerPort,
  reader: string | null | undefined,
  assetId: string | null,
): { row: AssetListRow | null; reload(): void } {
  const { read, reload } = useLedgerRead(
    port,
    reader,
    "ledger.actividad-asset.list",
    assetId === null ? null : {},
    assetId ?? "",
  );
  const row =
    assetId !== null && read?.kind === "done"
      ? ((read.result.rows ?? []).find((found) => found.asset_id === assetId) ??
        null)
      : null;
  return { row, reload };
}

// ---- The form's text -----------------------------------------------------------

/** The text of a form, started from what the record states. It starts again
 * only when what the record states changes, never when the same fields are
 * drawn again, and what was typed is kept through a re-read and through a
 * change of what the record states. */
export function useFieldsDraft(initial: FormDraft) {
  const [held, setHeld] = useState<{
    signature: string;
    initial: FormDraft;
  } | null>(null);
  const [draft, setDraft] = useState<FormDraft>({});
  const signature = JSON.stringify(initial);
  if (held === null || signature !== held.signature) {
    const before = held?.initial ?? {};
    setHeld({ signature, initial });
    setDraft((current) => ({
      ...initial,
      ...Object.fromEntries(
        Object.entries(current).filter(
          ([key, typed]) => typed !== (before[key] ?? ""),
        ),
      ),
    }));
  }
  const set = useCallback((changes: FormDraft) => {
    setDraft((current) => ({ ...current, ...changes }));
  }, []);
  return {
    draft,
    initial: held?.initial ?? initial,
    /** Anything typed that is not what the record states. */
    dirty: Object.keys(draft).some(
      (key) => draft[key] !== ((held?.initial ?? initial)[key] ?? ""),
    ),
    set,
  };
}

/** Brings a form into view and puts the cursor in its first field, when it
 * opens and when `ready` becomes true. */
export function useFocusOnOpen(
  form: RefObject<HTMLElement | null>,
  ready: boolean,
) {
  useEffect(() => {
    const element = form.current;
    if (!ready || element === null) return;
    element.scrollIntoView?.({ block: "nearest" });
    element
      .querySelector<HTMLElement>(
        "input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
      )
      ?.focus({ preventScroll: true });
  }, [form, ready]);
}
