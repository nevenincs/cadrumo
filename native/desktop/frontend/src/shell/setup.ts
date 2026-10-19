import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  DesktopSetup,
  SetupCheckMode,
  SetupItemId,
  SetupItemKind,
  SetupRow,
  SetupRun,
  SetupSnapshot,
} from "../ipc/contract";
import { failureCode } from "../errors";
import { useCachedRead, type AgentRead } from "./agentViews";
import type { Setup } from "./host";

// Component setup as the window sees it: one cached read of the signed-in
// profile's setup, kept current by the host's change signal and by the answer
// to every command. Nothing polls; the read is asked once per profile and
// every later state arrives pushed. The newest revision wins, whichever way it
// came.

export type SetupControl = {
  /** Whether this window offers setup now: the host serves it and a profile
   * is signed in. */
  offered: boolean;
  read: AgentRead<DesktopSetup>;
  /** The current snapshot, once the host has one for a signed-in profile. */
  snapshot: SetupSnapshot | null;
  /** A command of this window's is waiting for its answer. */
  pending: boolean;
  /** Why the last command was refused, as its code; null once another one
   * is sent or it is put away. Never shown as it is. */
  refusal: string | null;
  check(mode: SetupCheckMode): void;
  verify(items: SetupItemId[] | null): void;
  /** `resume` after an interruption: a plan unchanged from the one this
   * window approved runs again without a second approval. */
  start(items: SetupItemId[] | null, options?: { resume?: boolean }): void;
  /** Answers the plan on screen, bound to the digest it was shown with. */
  answer(decision: "apply" | "reject"): void;
  cancel(): void;
  /** The profile's Google account, which rides the same session but is not
   * setup: sign in through Google's own page, or remove the sign-in. */
  signInGoogle(): void;
  signOutGoogle(): void;
  clearRefusal(): void;
};

/** A setup that has not settled yet. */
export function liveRun(snapshot: SetupSnapshot | null): SetupRun | null {
  const run = snapshot?.setup ?? null;
  return run && run.stage !== "settled" ? run : null;
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

/** The operator actions that set up one kind of item, as the product names
 * each kind's recovery. */
export const SETUP_ACTION_KINDS: ReadonlyMap<string, SetupItemKind> = new Map([
  ["operator.provision.browser", "browser"],
  ["operator.provision.local_ai", "local_ai"],
]);
/** The operator actions that lead to setup as a whole. */
const GENERAL_SETUP_ACTIONS: ReadonlySet<string> = new Set([
  "operator.provision.setup",
  "operator.provision.status",
]);

/** Where an operator action named as a recovery leads in this window: the
 * row of the item it sets up, setup as a whole (`"general"`), or nowhere
 * (`null`) for an action that is not about setup. A kind with several rows
 * leads to the first that is not ready; a kind the snapshot has no row of
 * leads to setup as a whole. */
export function setupTargetOf(
  action: string,
  rows: readonly SetupRow[],
): SetupRow | "general" | null {
  if (GENERAL_SETUP_ACTIONS.has(action)) return "general";
  const kind = SETUP_ACTION_KINDS.get(action);
  if (kind === undefined) return null;
  const ofKind = rows.filter((row) => row.kind === kind);
  return ofKind.find((row) => row.state !== "ready") ?? ofKind[0] ?? "general";
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
    (value.state === "signed_out" ||
      value.state === "unavailable" ||
      (value.state === "ready" &&
        "snapshot" in value &&
        typeof value.snapshot === "object" &&
        value.snapshot !== null))
  )
    return value as DesktopSetup;
  throw { code: "unavailable" };
}

export function useSetup(
  setup: Setup | undefined,
  owner: string | null,
  signedIn: boolean,
): SetupControl {
  const offered = setup !== undefined && signedIn && owner !== null;
  const readSetup = useMemo(
    () => (setup ? () => setup.read().then(checked) : null),
    [setup],
  );
  const { read: cached } = useCachedRead(readSetup, owner, offered, 0);
  const [pushed, setPushed] = useState<{
    owner: string | null;
    state: DesktopSetup;
  } | null>(null);
  const [commands, setCommands] = useState({
    owner,
    pending: 0,
    refusal: null as string | null,
  });
  if (commands.owner !== owner)
    setCommands({ owner, pending: 0, refusal: null });

  const accept = useCallback(
    (state: DesktopSetup) =>
      setPushed((held) =>
        held && held.owner === owner && held.state.revision > state.revision
          ? held
          : { owner, state },
      ),
    [owner],
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

  const fresh = pushed && pushed.owner === owner ? pushed.state : null;
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
    (act: (served: Setup) => Promise<DesktopSetup>) => {
      if (!setup) return;
      setCommands((held) => ({
        ...held,
        pending: held.pending + 1,
        refusal: null,
      }));
      act(setup)
        .then(checked)
        .then(
          (state) => {
            accept(state);
            setCommands((held) =>
              held.owner === owner
                ? { ...held, pending: Math.max(0, held.pending - 1) }
                : held,
            );
          },
          (error: unknown) =>
            setCommands((held) =>
              held.owner === owner
                ? {
                    ...held,
                    pending: Math.max(0, held.pending - 1),
                    refusal: failureCode(error),
                  }
                : held,
            ),
        );
    },
    [setup, accept, owner],
  );

  const pending = commands.owner === owner && commands.pending > 0;
  const refusal = commands.owner === owner ? commands.refusal : null;
  return useMemo(
    (): SetupControl => ({
      offered,
      read,
      snapshot,
      pending,
      refusal,
      check: (mode) => send((served) => served.check(mode)),
      verify: (items) => send((served) => served.verify(items)),
      start: (items, options) =>
        send((served) =>
          served.start(items, options?.resume ? { resume: true } : undefined),
        ),
      answer: (decision) => {
        const run = current.current?.setup;
        if (!run || run.stage !== "review" || !run.review) return;
        const { operation_id: operationId } = run;
        const { plan_digest: planDigest } = run.review;
        send((served) => served.answer(operationId, planDigest, decision));
      },
      cancel: () => {
        const run = liveRun(current.current);
        if (!run) return;
        send((served) => served.cancel(run.operation_id));
      },
      signInGoogle: () => send((served) => served.signInGoogle()),
      signOutGoogle: () => send((served) => served.signOutGoogle()),
      clearRefusal: () =>
        setCommands((held) =>
          held.refusal === null ? held : { ...held, refusal: null },
        ),
    }),
    [offered, read, snapshot, pending, refusal, send],
  );
}
