/** Session-owned operation state. No request body, form value or financial
 * operand is retained here. The declarations memory owns this store and is
 * replaced with the signed-in reader. */
export type ModeloWriteLease = { readonly key: string; readonly id: number };
export type ModeloWriteHold = ModeloWriteLease &
  (
    | { readonly phase: "running" }
    | { readonly phase: "unknown"; readonly operationId: string | null }
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

export function createModeloWriteHolds() {
  let sequence = 0;
  const holds = new Map<string, ModeloWriteHold>();
  const versions = new Map<string, number>();
  const listeners = new Set<() => void>();
  const publish = () => listeners.forEach((listener) => listener());
  const owns = (lease: ModeloWriteLease) =>
    holds.get(lease.key)?.id === lease.id;
  return {
    get: (key: string) => holds.get(key),
    /** A completed write still invalidates reads started before admission. */
    version: (key: string) => versions.get(key) ?? 0,
    snapshot: () => [...holds.values()],
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    /** Admission is synchronous, before the first await or render. */
    begin(key: string): ModeloWriteLease | null {
      if (holds.has(key)) return null;
      const lease = { key, id: ++sequence };
      versions.set(key, lease.id);
      holds.set(key, { ...lease, phase: "running" });
      publish();
      return lease;
    },
    unknown(lease: ModeloWriteLease, operationId: string | null) {
      if (!owns(lease)) return;
      holds.set(lease.key, { ...lease, phase: "unknown", operationId });
      publish();
    },
    needsRead(
      lease: ModeloWriteLease,
      savedUnread = false,
      words: string | null = null,
    ) {
      if (!owns(lease)) return;
      holds.set(lease.key, { ...lease, phase: "refresh", savedUnread, words });
      publish();
    },
    /** Only a definitive refusal/no-send path may release without a read. */
    notWritten(lease: ModeloWriteLease) {
      if (!owns(lease)) return;
      holds.delete(lease.key);
      publish();
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
