import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  SetupItemId,
  SetupItemProgress,
  SetupPartProgress,
  SetupRow,
  SetupRun,
  SetupSnapshot,
} from "../ipc/contract";
import {
  anyLive,
  liveRunOf,
  runOf,
  setupTargetOf,
  type SetupControl,
} from "./setup";

// The window's one provisioning store: the host's pushed setup snapshot, as
// every surface that shows or starts a setup reads it, and the one
// provisioning panel's open state. The panel, the rail, Settings, the agent's
// local AI controls and every recovery offer subscribe to it; none of them
// keeps a setup state of its own or is handed one through its parent. The
// rows are the engine's: nothing here lists items, kinds, sizes or states.

/** What the panel shows now: closed, or open, focused on one item's row or
 * on none. */
export type PanelState = {
  open: boolean;
  focus: SetupItemId | null;
  /** False leaves the keyboard where the person is typing: the panel opens
   * without taking it. */
  takeFocus: boolean;
  /** Grows with every request to open, so a second request for the same
   * row scrolls to it again. */
  request: number;
};

export type ProvisioningStore = {
  /** Whether this window offers setup now. */
  offered: boolean;
  /** The setup reads and commands, as the host serves them. */
  control: SetupControl;
  snapshot: SetupSnapshot | null;
  rows: readonly SetupRow[];
  /** Whether any item is setting up now. */
  anyLive: boolean;
  /** The snapshot says some row is not usable yet. */
  incomplete: boolean;
  /** The row of the local AI, whose program and models are its parts. */
  localAiRow: SetupRow | null;
  runOf(item: SetupItemId): SetupRun | null;
  liveRunOf(item: SetupItemId): SetupRun | null;
  /** The progress of `item`'s latest setup, once setup knows it. */
  progressOf(item: SetupItemId): SetupItemProgress | null;
  /** The local AI's part that pulls `model` in its latest setup. */
  modelPart(model: string): SetupPartProgress | null;
  /** The local AI's program part in its latest setup. */
  programPart(): SetupPartProgress | null;
  /** A row's own button: check it again, or set it up. */
  act(row: SetupRow): void;
  /** Downloads one model of a local lane's list through the local AI's
   * setup; false where it cannot start now. */
  downloadModel(lane: string, model: string): boolean;
  /** Removes one model from this computer, answering the refusal's code or
   * null once it is removed. */
  removeModel(model: string): Promise<string | null>;
  panel: PanelState;
  /** Opens the panel, on `item`'s row when one is named. */
  open(item?: SetupItemId | null, options?: { takeFocus?: boolean }): void;
  close(): void;
  /** Where a recovery `action` leads now: the row it recovers, setup as a
   * whole, or nowhere while this window offers no setup or the engine reports
   * the row's item ready, which setup cannot improve. */
  targetOf(action: string): SetupRow | "general" | null;
  /** Opens the panel on the row `action` recovers, or on every row; false
   * where it leads nowhere. */
  offer(action: string): boolean;
  /** Offers `action` once the rows are read, if they are not yet: a refusal
   * that arrives before this window can say where it leads. */
  raise(action: string): void;
};

const CLOSED: PanelState = {
  open: false,
  focus: null,
  takeFocus: true,
  request: 0,
};

const NO_CONTROL: SetupControl = {
  offered: false,
  read: { kind: "unavailable" },
  snapshot: null,
  pending: false,
  refusal: null,
  check: () => undefined,
  verify: () => undefined,
  start: () => undefined,
  answer: () => undefined,
  cancel: () => undefined,
  removeModel: () => Promise.resolve("unavailable"),
  remove: () => Promise.resolve("unavailable"),
  signInGoogle: () => undefined,
  signOutGoogle: () => undefined,
  clearRefusal: () => undefined,
};

/** The store of a window that offers no setup: nothing to show, and every
 * request leads nowhere. */
const NO_PROVISIONING: ProvisioningStore = {
  offered: false,
  control: NO_CONTROL,
  snapshot: null,
  rows: [],
  anyLive: false,
  incomplete: false,
  localAiRow: null,
  runOf: () => null,
  liveRunOf: () => null,
  progressOf: () => null,
  modelPart: () => null,
  programPart: () => null,
  act: () => undefined,
  downloadModel: () => false,
  removeModel: () => Promise.resolve("unavailable"),
  panel: CLOSED,
  open: () => undefined,
  close: () => undefined,
  targetOf: () => null,
  offer: () => false,
  raise: () => undefined,
};

/** Where a refusal's recovery `action` leads: the row it recovers unless the
 * engine reports that item ready, since a refusal then lacks something setup
 * does not supply; setup as a whole; or nowhere. */
function recoveryTarget(
  action: string,
  rows: readonly SetupRow[],
): SetupRow | "general" | null {
  const target = setupTargetOf(action, rows);
  return target !== "general" && target?.state === "ready" ? null : target;
}

export const ProvisioningContext =
  createContext<ProvisioningStore>(NO_PROVISIONING);

/** The window's provisioning store, wherever it is read. */
export function useProvisioning(): ProvisioningStore {
  return useContext(ProvisioningContext);
}

/** Whether keystrokes now go into text the person is writing, a terminal's
 * included. */
export const typingInto = (element: Element | null): boolean =>
  element instanceof HTMLElement &&
  (element.isContentEditable ||
    element.matches("input, textarea, select") ||
    element.closest("[data-terminal]") !== null);

/** The row whose setup carries the program and the models as its parts:
 * the one item the engine reports as the local AI. */
function localAiOf(rows: readonly SetupRow[]): SetupRow | null {
  return rows.find((row) => row.kind === "local_ai") ?? null;
}

/**
 * The store over `control`, for `owner`'s profile. The panel opens once per
 * launch while the snapshot says setup is not complete, and on every
 * recovery; `onOpen` is told each time it opens, so a surface it would
 * cover can make way. While `held` -- another modal dialog owns the window --
 * the launch's own opening waits for it to close; a recovery opens at once.
 */
export function useProvisioningStore(
  control: SetupControl,
  owner: string | null,
  onOpen?: () => void,
  held = false,
): ProvisioningStore {
  const { offered, snapshot } = control;
  const rows = useMemo(() => snapshot?.rows ?? [], [snapshot]);
  const [panel, setPanel] = useState<PanelState>(CLOSED);
  const opened = useRef(onOpen);
  opened.current = onOpen;
  // The launch's opening, decided by the first status read and still owed
  // while another dialog holds the window; any opening settles it.
  const owed = useRef(false);
  const open = useCallback(
    (item: SetupItemId | null = null, options?: { takeFocus?: boolean }) => {
      owed.current = false;
      opened.current?.();
      setPanel((held) => ({
        open: true,
        focus: item,
        takeFocus: options?.takeFocus ?? true,
        request: held.request + 1,
      }));
    },
    [],
  );
  const close = useCallback(
    () => setPanel((held) => ({ ...held, open: false })),
    [],
  );

  // Read through refs by the callbacks, so a recovery wired once into a
  // port routes by the rows read since.
  const rowsRef = useRef<readonly SetupRow[]>(rows);
  rowsRef.current = rows;
  const offeredRef = useRef(offered);
  offeredRef.current = offered;
  const snapshotRef = useRef(snapshot);
  snapshotRef.current = snapshot;

  const offer = useCallback(
    (action: string): boolean => {
      if (!offeredRef.current) return false;
      const target = recoveryTarget(action, rowsRef.current);
      if (target === null) return false;
      // Raised while the person types, it leaves the keyboard where it is.
      open(target === "general" ? null : target.item, {
        takeFocus: !typingInto(document.activeElement),
      });
      return true;
    },
    [open],
  );

  // A refusal that arrives before the rows are read is offered once they
  // are: the latest such refusal, for the profile it arrived for.
  const deferred = useRef<string | null>(null);
  const raise = useCallback(
    (action: string) => {
      if (
        offeredRef.current &&
        (rowsRef.current.length > 0 || setupTargetOf(action, []) !== null)
      )
        offer(action);
      else deferred.current = action;
    },
    [offer],
  );
  useEffect(() => {
    deferred.current = null;
  }, [owner]);
  useEffect(() => {
    const action = deferred.current;
    if (action === null || !offered || rows.length === 0) return;
    deferred.current = null;
    offer(action);
  }, [offered, rows, offer]);

  // Setup incomplete is never treated as optional, but it never holds the
  // window either: the panel opens once per launch and closes at any time.
  // Whether it opens is decided by the first status read: a setup the person
  // starts later from elsewhere -- a model's download in the agent's
  // settings -- is answered where it was asked for.
  const incomplete = offered && snapshot?.complete === false;
  const decided = useRef(false);
  useEffect(() => {
    // A snapshot served before that read settles says nothing yet.
    if (!offered || snapshot === null || snapshot.complete === null) return;
    if (!decided.current) {
      decided.current = true;
      // A refusal waiting on this same read opens the panel on its own row.
      owed.current = snapshot.complete === false && deferred.current === null;
    }
    if (owed.current && !held) open(null);
  }, [offered, snapshot, held, open]);

  const localAiRow = useMemo(() => localAiOf(rows), [rows]);
  const live = anyLive(snapshot);
  const { start, verify, removeModel } = control;

  return useMemo((): ProvisioningStore => {
    const progressOf = (item: SetupItemId) =>
      runOf(snapshot, item)?.items.find((entry) => entry.item === item) ?? null;
    const localParts = () =>
      localAiRow ? (progressOf(localAiRow.item)?.parts ?? []) : [];
    return {
      offered,
      control,
      snapshot,
      rows,
      anyLive: live,
      incomplete,
      localAiRow,
      runOf: (item) => runOf(snapshot, item),
      liveRunOf: (item) => liveRunOf(snapshot, item),
      progressOf,
      modelPart: (model) =>
        localParts().find((part) => part.model === model) ?? null,
      programPart: () => localParts().find((part) => !part.model) ?? null,
      act: (row) => {
        control.clearRefusal();
        if (row.recovery === "check_again") verify([row.item]);
        else if (row.recovery !== null)
          start(row.item, { resume: row.recovery === "resume" });
      },
      downloadModel: (lane, model) => {
        const row = localAiOf(rowsRef.current);
        // A start while the local AI sets up joins that setup, which would
        // not pull this model: it waits until that one settles.
        if (!row || liveRunOf(snapshotRef.current, row.item)) return false;
        control.clearRefusal();
        start(row.item, { download: { lane, model } });
        return true;
      },
      removeModel,
      panel,
      open,
      close,
      targetOf: (action) => (offered ? recoveryTarget(action, rows) : null),
      offer,
      raise,
    };
  }, [
    offered,
    control,
    snapshot,
    rows,
    live,
    incomplete,
    localAiRow,
    start,
    verify,
    removeModel,
    panel,
    open,
    close,
    offer,
    raise,
  ]);
}
