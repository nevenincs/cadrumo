import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  DesktopSetup,
  SetupCheckMode,
  SetupItemId,
  SetupModelDownload,
  SetupRemoval,
  SetupRow,
  SetupRun,
  SetupSnapshot,
} from "../ipc/contract";
import { failureCode } from "../errors";
import { useCachedRead, type AgentRead } from "./agentViews";
import type { Setup } from "./host";

// Component setup as the window sees it: one cached read of this
// installation's setup, kept current by the host's change signal and by the
// answer to every command. The components are the installation's, not a
// profile's, so setup is offered signed in or not; the host refuses only what
// is a profile's (its Google account, a model of its person's list) while
// nobody is signed in. Nothing polls; the read is asked at launch and again
// whenever the signed-in profile changes, and every later state arrives
// pushed. The host numbers every state of the window in one sequence across
// sign-in and sign-out, so the newest revision wins, whichever way it came,
// and a sign-in keeps every setup on screen.

export type SetupControl = {
  /** Whether this window offers setup now: the host serves it. */
  offered: boolean;
  read: AgentRead<DesktopSetup>;
  /** The current snapshot, once the host has one. */
  snapshot: SetupSnapshot | null;
  /** A command of this window's that names no item, a check or the Google
   * account's, is waiting for its answer. */
  pending: boolean;
  /** Whether `item`'s controls wait: a command naming it, such as its start
   * while its plan is worked out, or one naming no item, is waiting for its
   * answer. Another item's command leaves them free. */
  busy(item: SetupItemId): boolean;
  /** Why the last command was refused, as its code; null once another one
   * is sent or it is put away. Never shown as it is. */
  refusal: string | null;
  check(mode: SetupCheckMode): void;
  verify(items: SetupItemId[] | null): void;
  /** Sets up one item, beside any other item's setup. `resume` after an
   * interruption: a plan unchanged from the one this window approved runs
   * again without a second approval. */
  start(
    item: SetupItemId,
    options?: { resume?: boolean; download?: SetupModelDownload },
  ): void;
  /** Answers the plan `item`'s setup shows, bound to the digest it was shown
   * with. */
  answer(item: SetupItemId, decision: "apply" | "reject"): void;
  /** Cancels `item`'s setup while it has not settled. */
  cancel(item: SetupItemId): void;
  /** Removes one local model no role selects; resolves with the refusal's
   * code, or null once it is removed. */
  removeModel(model: string): Promise<string | null>;
  /** Removes the browser, or the local AI or its program alone; resolves
   * with the refusal's code, or null once it is removed. */
  remove(removal: SetupRemoval): Promise<string | null>;
  /** The profile's Google account, which rides the same session but is not
   * setup: sign in through Google's own page, or remove the sign-in. Refused
   * while nobody is signed in. */
  signInGoogle(): void;
  signOutGoogle(): void;
  clearRefusal(): void;
};

/** The latest setup of `item`, settled or not. */
export function runOf(
  snapshot: SetupSnapshot | null,
  item: SetupItemId,
): SetupRun | null {
  return snapshot?.runs.find((run) => run.item === item) ?? null;
}

/** The setup of `item` that has not settled yet. */
export function liveRunOf(
  snapshot: SetupSnapshot | null,
  item: SetupItemId,
): SetupRun | null {
  const run = runOf(snapshot, item);
  return run && run.stage !== "settled" ? run : null;
}

/** Every setup that has not settled yet, in the rows' item order. */
export function liveRuns(snapshot: SetupSnapshot | null): SetupRun[] {
  return (snapshot?.runs ?? []).filter((run) => run.stage !== "settled");
}

/** Whether any item is setting up now. */
export function anyLive(snapshot: SetupSnapshot | null): boolean {
  return liveRuns(snapshot).length > 0;
}

/** The rows a person can set up from here: neither usable nor waiting on
 * something outside Cadrumo. */
export function needsSetup(row: SetupRow): boolean {
  return (
    row.recovery === "set_up" ||
    row.recovery === "update" ||
    row.recovery === "try_again" ||
    row.recovery === "resume"
  );
}

/** The operator actions that lead to setup as a whole. */
const GENERAL_SETUP_ACTIONS: ReadonlySet<string> = new Set([
  "operator.provision.setup",
  "operator.provision.status",
]);
const PROVISION_PREFIX = "operator.provision.";

/** Whether `action` is the recovery that sets up `row`'s item: the row
 * names it while it offers a recovery, and a row that offers none (ready,
 * or waiting on something outside Cadrumo) is still the one its item's own
 * action leads to, the item's id following the action's prefix. */
function recoversRow(action: string, row: SetupRow): boolean {
  return row.recovery_action_id !== null
    ? row.recovery_action_id === action
    : action === `${PROVISION_PREFIX}${row.item}`;
}

/** Where an operator action named as a recovery leads in this window: the
 * row it recovers, setup as a whole (`"general"`) for an action about setup
 * as a whole, or nowhere (`null`). An action no row of the snapshot names
 * leads nowhere: while the status is loading or cannot be read, nothing
 * says whether setup could act, so nothing is offered. */
export function setupTargetOf(
  action: string,
  rows: readonly SetupRow[],
): SetupRow | "general" | null {
  if (GENERAL_SETUP_ACTIONS.has(action)) return "general";
  return rows.find((row) => recoversRow(action, row)) ?? null;
}

/** A host answer that is a setup state at all; anything else is treated as
 * the host failing to carry the command. */
function checked(value: unknown): DesktopSetup {
  if (
    typeof value === "object" &&
    value !== null &&
    "revision" in value &&
    typeof value.revision === "number" &&
    "state" in value &&
    (value.state === "unavailable" ||
      (value.state === "ready" &&
        "snapshot" in value &&
        typeof value.snapshot === "object" &&
        value.snapshot !== null))
  )
    return value as DesktopSetup;
  throw { code: "unavailable" };
}

/** The one key the installation's setup is cached under, whoever is signed
 * in. */
const INSTALLATION = "installation";

/**
 * The setup `setup` serves. `owner` is the signed-in profile, or null: a
 * change of it reads the setup again, under the same cache, so the newer
 * revision still wins and nothing on screen is dropped meanwhile.
 */
export function useSetup(
  setup: Setup | undefined,
  owner: string | null,
): SetupControl {
  const offered = setup !== undefined;
  const readSetup = useMemo(
    () => (setup ? () => setup.read().then(checked) : null),
    [setup],
  );
  const [asked, setAsked] = useState({ owner, count: 0 });
  if (asked.owner !== owner) setAsked({ owner, count: asked.count + 1 });
  const { read: cached } = useCachedRead(
    readSetup,
    INSTALLATION,
    offered,
    asked.count,
  );
  const [pushed, setPushed] = useState<DesktopSetup | null>(null);
  const [commands, setCommands] = useState({
    pending: 0,
    items: {} as Partial<Record<SetupItemId, number>>,
    refusal: null as string | null,
  });

  const accept = useCallback(
    (state: DesktopSetup) =>
      setPushed((held) =>
        held && held.revision > state.revision ? held : state,
      ),
    [],
  );

  useEffect(() => {
    if (!setup || !offered) return;
    let live = true;
    let stop: (() => void) | null = null;
    setup
      .observe((state) => {
        if (!live) return;
        try {
          accept(checked(state));
        } catch {
          // A malformed push changes nothing on screen.
        }
      })
      .then(
        (unsubscribe) => {
          if (typeof unsubscribe !== "function") return;
          if (live) stop = unsubscribe;
          else unsubscribe();
        },
        // Without the signal the cached read still stands, and every
        // command's answer still brings the state up to date.
        () => undefined,
      );
    return () => {
      live = false;
      stop?.();
    };
  }, [setup, offered, accept]);

  const fresh = pushed;
  const read = useMemo(
    (): AgentRead<DesktopSetup> =>
      !offered
        ? { kind: "unavailable" }
        : fresh &&
            (cached.kind !== "ready" || cached.value.revision <= fresh.revision)
          ? { kind: "ready", value: fresh }
          : cached,
    [offered, fresh, cached],
  );
  const snapshot =
    read.kind === "ready" && read.value.state === "ready"
      ? read.value.snapshot
      : null;
  const current = useRef(snapshot);
  current.current = snapshot;

  const send = useCallback(
    (
      act: (served: Setup) => Promise<DesktopSetup>,
      item: SetupItemId | null = null,
    ) => {
      if (!setup) return;
      // A command naming an item holds that item's controls alone, so a
      // setup still working out its plan never holds another row's.
      const counted = (
        held: typeof commands,
        by: number,
      ): Pick<typeof commands, "pending" | "items"> =>
        item === null
          ? { pending: Math.max(0, held.pending + by), items: held.items }
          : {
              pending: held.pending,
              items: {
                ...held.items,
                [item]: Math.max(0, (held.items[item] ?? 0) + by),
              },
            };
      setCommands((held) => ({ ...held, ...counted(held, 1), refusal: null }));
      act(setup)
        .then(checked)
        .then(
          (state) => {
            accept(state);
            setCommands((held) => ({ ...held, ...counted(held, -1) }));
          },
          (error: unknown) =>
            setCommands((held) => ({
              ...held,
              ...counted(held, -1),
              refusal: failureCode(error),
            })),
        );
    },
    [setup, accept],
  );

  // A removal answers its own refusal to the control that asked, not the
  // panel's shared one.
  const removal = useCallback(
    (removed: Promise<DesktopSetup> | undefined): Promise<string | null> =>
      removed
        ? removed.then(
            (state) => {
              accept(checked(state));
              return null;
            },
            (error: unknown) => failureCode(error),
          )
        : Promise.resolve("unavailable"),
    [accept],
  );

  const pending = commands.pending > 0;
  const { items: waiting, refusal } = commands;
  return useMemo(
    (): SetupControl => ({
      offered,
      read,
      snapshot,
      pending,
      busy: (item) => pending || (waiting[item] ?? 0) > 0,
      refusal,
      check: (mode) => send((served) => served.check(mode)),
      verify: (items) => send((served) => served.verify(items)),
      start: (item, options) =>
        send((served) => served.start(item, options), item),
      answer: (item, decision) => {
        const run = runOf(current.current, item);
        if (!run || run.stage !== "review" || !run.review) return;
        const { operation_id: operationId } = run;
        const { plan_digest: planDigest } = run.review;
        send(
          (served) => served.answer(operationId, planDigest, decision),
          item,
        );
      },
      cancel: (item) => {
        const run = liveRunOf(current.current, item);
        if (!run) return;
        send((served) => served.cancel(run.operation_id), item);
      },
      removeModel: (model) => removal(setup?.removeModel(model)),
      remove: (what) => removal(setup?.remove(what)),
      signInGoogle: () => send((served) => served.signInGoogle()),
      signOutGoogle: () => send((served) => served.signOutGoogle()),
      clearRefusal: () =>
        setCommands((held) =>
          held.refusal === null ? held : { ...held, refusal: null },
        ),
    }),
    [offered, read, snapshot, pending, waiting, refusal, send, setup, removal],
  );
}
