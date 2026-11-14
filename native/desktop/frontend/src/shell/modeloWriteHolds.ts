import type { TerminalOperationFailure } from "./ledger";

/** Session-owned operation state. No request body, form value or financial
 * operand is retained here. The declarations memory owns this store and is
 * replaced with the signed-in reader. */
export type ModeloWriteOwner = {
  readonly workUnitId: string;
  readonly label: string;
  readonly filingYear: number;
  /** The served form's `offers_iva_wallet`: whether this declaration reads the
   * profile's IVA wallet. Absent before the form is read. */
  readonly readsIvaWallet?: boolean;
};
export type ModeloWriteLease = {
  readonly key: string;
  readonly id: number;
  readonly owner?: ModeloWriteOwner;
};
export type ModeloWriteHold = ModeloWriteLease &
  (
    | { readonly phase: "running" }
    | {
        readonly phase: "unknown";
        readonly operationId: string | null;
        readonly terminalFailure?: TerminalOperationFailure;
      }
    | {
        readonly phase: "refresh";
        readonly savedUnread: boolean;
        readonly words: string | null;
      }
  );

export const creationWriteKey = (target: {
  modelo: string;
  filing_year: number;
  period_code: string;
}) =>
  JSON.stringify([
    "create",
    target.modelo,
    target.filing_year,
    target.period_code,
  ]);
export const declarationWriteKey = (workUnitId: string) =>
  JSON.stringify(["work", workUnitId]);
export const isCreationWriteKey = (key: string) => key.startsWith('["create",');
export const walletWriteKey = JSON.stringify(["wallet"]);
const isDeclarationWriteKey = (key: string) => key.startsWith('["work",');
/** A settled, refused or journal-stopped operation is no longer in flight; what
 * stays unresolved belongs to its own declaration. */
const mayStillRun = (hold: ModeloWriteHold) =>
  hold.phase === "running" ||
  (hold.phase === "unknown" && hold.terminalFailure === undefined);
/** A declaration's hold reaches the shared wallet only while its operation may
 * still run and only when its served form reads the wallet. A wallet hold keeps
 * every declaration held until the wallet's own recovery. */
export const modeloWriteConflicts = (target: string, held: ModeloWriteHold) =>
  target === held.key ||
  (target === walletWriteKey &&
    isDeclarationWriteKey(held.key) &&
    held.owner?.readsIvaWallet !== false &&
    mayStillRun(held)) ||
  (held.key === walletWriteKey && isDeclarationWriteKey(target));

/** Only an observed, stopped calculation can be reviewed as a new work
 * decision. This never claims that its earlier effects were rolled back. */
export function reviewableFailedCalculation(hold: ModeloWriteHold): boolean {
  return (
    hold.phase === "unknown" &&
    hold.key.startsWith('["work",') &&
    hold.terminalFailure?.definition_id === "modelo.work.calculate" &&
    hold.terminalFailure.operation_id === hold.operationId
  );
}

export function createModeloWriteHolds() {
  let sequence = 0;
  let declarationVersion = 0;
  const holds = new Map<string, ModeloWriteHold>();
  const versions = new Map<string, number>();
  const reviewed = new Map<string, TerminalOperationFailure>();
  const listeners = new Set<() => void>();
  // Refresh holds the window is reading itself, by hold id: how many reads.
  const reading = new Map<number, number>();
  let snapshot: readonly ModeloWriteHold[] = [];
  const publish = () => {
    snapshot = [...holds.values()];
    listeners.forEach((listener) => listener());
  };
  const owns = (lease: ModeloWriteLease) =>
    holds.get(lease.key)?.id === lease.id;
  const blocking = (key: string) => {
    const own = holds.get(key);
    if (own) return own;
    for (const hold of holds.values())
      if (modeloWriteConflicts(key, hold)) return hold;
    return undefined;
  };
  return {
    get: (key: string) => holds.get(key),
    /** Wallet writes affect the shared basis read by existing declarations. */
    blocking,
    reviewedFailure: (key: string) => reviewed.get(key),
    /** A completed write still invalidates reads started before admission. */
    version: (key: string) => versions.get(key) ?? 0,
    /** Also retires a read when a conflicting write began and already ended. */
    admissionVersion: (key: string) =>
      Math.max(
        versions.get(key) ?? 0,
        isDeclarationWriteKey(key)
          ? (versions.get(walletWriteKey) ?? 0)
          : key === walletWriteKey
            ? declarationVersion
            : 0,
      ),
    snapshot: () => snapshot,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    /** Admission is synchronous, before the first await or render. */
    begin(key: string, owner?: ModeloWriteOwner): ModeloWriteLease | null {
      if (blocking(key)) return null;
      const lease = { key, id: ++sequence, ...(owner ? { owner } : {}) };
      versions.set(key, lease.id);
      if (isDeclarationWriteKey(key)) declarationVersion = lease.id;
      holds.set(key, { ...lease, phase: "running" });
      reviewed.delete(key);
      publish();
      return lease;
    },
    unknown(
      lease: ModeloWriteLease,
      operationId: string | null,
      terminalFailure?: TerminalOperationFailure,
    ) {
      if (!owns(lease)) return;
      holds.set(lease.key, {
        ...lease,
        phase: "unknown",
        operationId,
        ...(terminalFailure?.operation_id === operationId
          ? { terminalFailure }
          : {}),
      });
      publish();
    },
    needsRead(
      lease: ModeloWriteLease,
      savedUnread = false,
      words: string | null = null,
    ) {
      if (!owns(lease)) return;
      holds.set(lease.key, {
        ...lease,
        phase: "refresh",
        savedUnread,
        words,
      });
      publish();
    },
    /** Called only by the person's explicit Review current declaration
     * action. The operation remains failed with unresolved effects in its
     * journal. A successful current form read permits a separate new intent. */
    async reviewCalculation(
      hold: ModeloWriteHold,
      readCurrent: () => Promise<boolean>,
      current: () => boolean,
    ): Promise<boolean> {
      if (
        !current() ||
        holds.get(hold.key) !== hold ||
        !reviewableFailedCalculation(hold)
      )
        return false;
      let read: boolean;
      try {
        read = await readCurrent();
      } catch {
        return false;
      }
      if (
        !read ||
        !current() ||
        holds.get(hold.key) !== hold ||
        !reviewableFailedCalculation(hold) ||
        hold.phase !== "unknown" ||
        !hold.terminalFailure
      )
        return false;
      reviewed.set(hold.key, hold.terminalFailure);
      holds.delete(hold.key);
      publish();
      return true;
    },
    /** The person started a new attempt on this declaration, which may ask
     * for more before any write is admitted. The reviewed failure belonged to
     * the earlier attempt, so its words go; nothing is admitted or released. */
    newAttempt(key: string) {
      if (!reviewed.delete(key)) return;
      publish();
    },
    /** Only a definitive refusal/no-send path may release without a read. */
    notWritten(lease: ModeloWriteLease) {
      if (!owns(lease)) return;
      holds.delete(lease.key);
      publish();
    },
    /** The window began its own read of a refresh hold; nobody needs to be
     * asked to read again while it runs. False when nothing was marked. */
    readBegan(hold: ModeloWriteHold): boolean {
      if (hold.phase !== "refresh" || holds.get(hold.key) !== hold)
        return false;
      reading.set(hold.id, (reading.get(hold.id) ?? 0) + 1);
      publish();
      return true;
    },
    /** A read marked by `readBegan` ended, read or failed. */
    readEnded(hold: ModeloWriteHold) {
      const count = reading.get(hold.id) ?? 0;
      if (count === 0) return;
      if (count > 1) reading.set(hold.id, count - 1);
      else reading.delete(hold.id);
      publish();
    },
    /** Whether the window is reading the refresh hold on `key` itself. */
    isReading(key: string) {
      const hold = holds.get(key);
      return hold?.phase === "refresh" && reading.has(hold.id);
    },
    /** Capture before starting the read. Completion cannot release a hold
     * that was unknown then, or that changed while the read was in flight. */
    readCompleted(before: ModeloWriteHold) {
      if (before.phase !== "refresh" || holds.get(before.key) !== before)
        return;
      holds.delete(before.key);
      publish();
    },
  };
}

export type ModeloWriteHolds = ReturnType<typeof createModeloWriteHolds>;
export type ModeloWriteMemory = { writes?: ModeloWriteHolds };
export const modeloWritesFor = (memory: ModeloWriteMemory): ModeloWriteHolds =>
  (memory.writes ??= createModeloWriteHolds());
