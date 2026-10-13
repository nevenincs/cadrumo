import { useCallback, useEffect, useRef, useState } from "react";
import type {
  HostFailure,
  ManagerStatus,
  ProfileList,
  SignInRefusal,
  SignInStatus,
  SignOutResult,
} from "../ipc/contract";
import type { Host } from "./host";
import { nameable, targetOf } from "./profiles";
import { failureCode } from "../errors";

const unknownStatus: SignInStatus = {
  supported: true,
  state: "unknown",
  active_profile: null,
  runtimeAvailable: true,
  refusal: null,
};

function refusalFrom(error: unknown): SignInRefusal {
  const seconds = (error as Partial<SignInRefusal> | null)?.retryAfterSeconds;
  const failure = error as Partial<HostFailure> | null;
  return {
    code: failureCode(error),
    retryAfterSeconds:
      typeof seconds === "number" && Number.isFinite(seconds)
        ? Math.max(0, seconds)
        : null,
    ...(failure?.operation ? { operation: failure.operation } : {}),
    ...(failure?.ioKind ? { ioKind: failure.ioKind } : {}),
    ...(Number.isInteger(failure?.osCode) ? { osCode: failure?.osCode } : {}),
  };
}

/**
 * The one reading of the account that every element shows: the sign-in
 * dialog, the TUI pane and its header, the account menu, the rail and the actions.
 * Nothing else derives a state of its own from the raw status.
 */
export type AccountPhase =
  /** The page runs without a desktop host. */
  | "no-host"
  /** The first status read has not answered yet. */
  | "checking"
  /** The desktop is observing the manager's asynchronous startup. */
  | "starting"
  /** This platform signs in inside the TUI; the shell offers nothing. */
  | "unsupported"
  | "signed-in"
  /** There is no runtime to ask. */
  | "services-down"
  /** The status read failed, or the runtime could not say. */
  | "unknown"
  /** There is no profile to sign in to yet, or none the shell can name. */
  | "no-profile"
  | "signed-out";

/** The phases in which the TUI is withheld until the account is settled. */
export const GATED: ReadonlySet<AccountPhase> = new Set([
  "checking",
  "starting",
  "services-down",
  "unknown",
  "no-profile",
  "signed-out",
]);

export function phaseOf(
  available: boolean,
  status: SignInStatus | null,
  profiles: ProfileList | null = null,
  /** The host lists profiles and has not answered yet. */
  listPending = false,
): AccountPhase {
  if (!available) return "no-host";
  if (!status) return "checking";
  if (!status.runtimeAvailable) return "services-down";
  if (!status.supported) return "unsupported";
  if (status.state === "present") return "signed-in";
  if (status.state === "unknown") return "unknown";
  // With none selected, the profiles that exist are still there to choose
  // from: only where none is known is there nothing to sign in to. Until
  // the list has been read that is not known either way.
  // A list that could not be read coherently names nobody.
  const listed = profiles?.complete ? profiles.profiles.length : 0;
  if (status.active_profile === null && listed === 0)
    return listPending ? "checking" : "no-profile";
  return "signed-out";
}

/** Refusals that outlast the attempt that met them. */
const STANDING: ReadonlySet<string> = new Set([
  "PROFILE_LOCKED",
  "KEYRING_UNAVAILABLE",
  "THROTTLED",
]);

/** Whether the account can be signed in to as it stands. Signing in is
 * Cadrumo's and the runtime's, and is always offered here while nobody is
 * signed in: a refusal says why the last try failed, and the next try is
 * the person's to make. Every element that offers sign-in asks this. */
export function canSignIn(phase: AccountPhase): boolean {
  return phase === "signed-out" || phase === "unknown";
}

const COUNTDOWN_TICK_MS = 250;
const STARTUP_WAIT_MS = 90_000;

/** Bound read-only UI waits even if the transport never settles its promise.
 * Late answers are ignored; native process cleanup remains owned by Tauri. */
async function boundedRead<T>(read: Promise<T>): Promise<T> {
  let timer: number | undefined;
  try {
    return await Promise.race([
      read,
      new Promise<never>((_, reject) => {
        timer = window.setTimeout(
          () => reject({ code: "timed_out" }),
          STARTUP_WAIT_MS,
        );
      }),
    ]);
  } finally {
    window.clearTimeout(timer);
  }
}

/** The seconds left of a refusal's wait. No timer runs unless one is owed. */
function useCountdown(refusal: SignInRefusal | null) {
  const total = refusal?.retryAfterSeconds ?? 0;
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (total <= 0) return;
    const until = Date.now() + total * 1000;
    const tick = () => {
      const left = Math.max(0, Math.ceil((until - Date.now()) / 1000));
      setSeconds(left);
      if (left === 0) window.clearInterval(timer);
    };
    const timer = window.setInterval(tick, COUNTDOWN_TICK_MS);
    tick();
    return () => window.clearInterval(timer);
  }, [refusal, total]);
  return total > 0 ? seconds : 0;
}

/** Only public presence and refusals live here; no password or runtime session. */
export function useSignIn(host: Host) {
  const [manager, setManager] = useState<ManagerStatus | null>(null);
  const managerRef = useRef<ManagerStatus | null>(null);
  const awaitingManagerAuth = useRef(false);
  const managerObserved =
    host.observeManager !== undefined || host.managerStatus !== undefined;
  const managerAllows = useCallback(
    () =>
      !managerObserved ||
      managerRef.current?.state === "ready" ||
      managerRef.current?.state === "unsupported",
    [managerObserved],
  );
  const [status, setStatus] = useState<SignInStatus | null>(null);
  const [refusal, setRefusal] = useState<SignInRefusal | null>(null);
  const [busy, setBusy] = useState(false);
  const [startingServices, setStartingServices] = useState(false);
  const [observingStartup, setObservingStartup] = useState(
    host.available && host.startManager !== undefined,
  );
  const startingManager = useRef(false);
  const latestStatus = useRef<SignInStatus | null>(null);
  // The profiles to choose from, where the host offers them; the one the
  // person chose; and what became of the last attempt to create one.
  const [profiles, setProfiles] = useState<ProfileList | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [createRefusal, setCreateRefusal] = useState<SignInRefusal | null>(
    null,
  );
  const [created, setCreated] = useState<string | null>(null);
  // A creation whose answer never came: whether the profile exists is not
  // known, which is not the same as its having been refused.
  const [createUnknown, setCreateUnknown] = useState<SignInRefusal | null>(
    null,
  );
  const [creating, setCreating] = useState(false);
  // The list as the last read left it, for the code that has just asked.
  const listed = useRef<ProfileList | null>(null);
  const [remaining, setRemaining] = useState<SignOutResult | null>(null);
  // A sign-out that failed is its own fact: it is not a sign-in refusal.
  const [signOutFailure, setSignOutFailure] = useState<SignInRefusal | null>(
    null,
  );
  const request = useRef(0);
  const invalidation = useRef(0);
  const transport = useRef(host);
  const statusReadFailed = useRef(false);
  const mounted = useRef(true);
  const statusRead = useRef<{
    generation: number;
    promise: Promise<void>;
  } | null>(null);
  const submitting = useRef(false);
  const currentRefusal = refusal ?? status?.refusal ?? null;
  const retrySeconds = useCountdown(currentRefusal);
  const invalidate = useCallback(() => {
    ++invalidation.current;
    ++request.current;
    // Keep the bounded transport read tracked until settlement. Invalidating
    // its answer does not release the native queue slot it still owns.
  }, []);

  useEffect(() => {
    // Only replacing the host replaces the transport and its queue. Reads on
    // that old host retain their generation fence but cannot block the new one.
    if (transport.current !== host) {
      transport.current = host;
      statusRead.current = null;
      invalidate();
    }
  }, [host, invalidate]);

  const refresh = useCallback(
    async (afterMutation = false) => {
      const epoch = invalidation.current;
      if (
        !mounted.current ||
        !host.available ||
        !managerAllows() ||
        (submitting.current && !afterMutation)
      )
        return;
      while (statusRead.current) {
        const pending = statusRead.current;
        await pending.promise;
        if (!mounted.current || epoch !== invalidation.current) return;
        if (pending.generation === request.current) return;
      }
      if (
        !mounted.current ||
        !host.available ||
        !managerAllows() ||
        (submitting.current && !afterMutation)
      )
        return;
      const generation = ++request.current;
      const promise = Promise.resolve().then(async () => {
        try {
          if (
            !mounted.current ||
            generation !== request.current ||
            !managerAllows()
          )
            return;
          // Show the independent canonical CLI status read before the
          // optional profile list. Read profiles only while there is a
          // sign-in to prepare; an unreadable list is not an empty one.
          const next = await boundedRead(host.signInStatus());
          if (
            !mounted.current ||
            generation !== request.current ||
            !managerAllows()
          )
            return;
          statusReadFailed.current = false;
          awaitingManagerAuth.current = false;
          if (managerObserved) setObservingStartup(false);
          setStatus(next);
          latestStatus.current = next;
          // A list that names another profile as selected than the status
          // does is older than it: not shown beside it, and never a ground
          // for naming the profile a password goes to.
          setProfiles((held) =>
            held &&
            (held.profiles.find((p) => p.active)?.name ?? null) !==
              next.active_profile
              ? null
              : held,
          );
          if (
            !host.profiles ||
            !next.runtimeAvailable ||
            next.state === "present"
          )
            return;
          const list = await boundedRead(host.profiles.list()).catch(
            () => null,
          );
          if (generation !== request.current) return;
          listed.current = list;
          // Unread, the rows that were held are kept as what was last
          // known, and marked as no longer to be relied on.
          setProfiles(
            (held) =>
              list ??
              (held
                ? { ...held, complete: false }
                : { profiles: [], complete: false }),
          );
        } catch (error) {
          if (generation === request.current) {
            statusReadFailed.current = true;
            const refusal = refusalFrom(error);
            const failed = {
              ...unknownStatus,
              runtimeAvailable:
                refusal.operation === "manager"
                  ? false
                  : (latestStatus.current?.runtimeAvailable ??
                    !host.startManager),
              refusal,
            };
            latestStatus.current = failed;
            setStatus(failed);
          }
        } finally {
          if (statusRead.current?.generation === generation)
            statusRead.current = null;
        }
      });
      statusRead.current = { generation, promise };
      await promise;
    },
    [host, managerAllows, managerObserved],
  );

  useEffect(() => {
    if (!managerObserved) return;
    let active = true;
    let revision = -1;
    let close: (() => void) | undefined;
    managerRef.current = null;
    awaitingManagerAuth.current = true;
    invalidate();
    latestStatus.current = null;
    setStatus(null);
    setManager(null);
    const accept = (next: ManagerStatus) => {
      if (!active) return;
      const previous = managerRef.current;
      managerRef.current = next;
      setManager(next);
      if (next.state === "ready" || next.state === "unsupported") {
        if (previous?.state === next.state) return;
        invalidate();
        awaitingManagerAuth.current = true;
        latestStatus.current = null;
        setStatus(null);
        setRefusal(null);
        setObservingStartup(true);
        // Read canonical authentication again. Manager readiness grants none.
        void refresh(true);
        return;
      }
      invalidate();
      awaitingManagerAuth.current = true;
      const unavailable: SignInStatus = {
        ...unknownStatus,
        runtimeAvailable: false,
        refusal: next.failure ? refusalFrom(next.failure) : null,
      };
      latestStatus.current = unavailable;
      setStatus(unavailable);
      setRefusal(null);
      setChosen(null);
      listed.current = null;
      setProfiles(null);
      setObservingStartup(
        ["starting", "recovering", "waiting"].includes(next.state),
      );
    };
    if (host.observeManager) {
      void host
        .observeManager((signal) => {
          if (!active || signal.revision <= revision) return;
          revision = signal.revision;
          accept(
            signal.kind === "manager-state"
              ? signal.status
              : {
                  state: "failed",
                  failure: signal.error,
                },
          );
        })
        .then((unsubscribe) => {
          if (active) close = unsubscribe;
          else unsubscribe();
        })
        .catch((error: unknown) =>
          accept({
            state: "failed",
            failure: {
              ...refusalFrom(error),
              message: "manager-observation-failed",
              operation: "manager",
            } as HostFailure,
          }),
        );
    }
    if (host.managerStatus) {
      void boundedRead(host.managerStatus())
        .then((next) => {
          if (revision < 0) accept(next);
        })
        .catch((error: unknown) => {
          if (revision < 0)
            accept({
              state: "failed",
              failure: {
                ...refusalFrom(error),
                message: "manager-observation-failed",
                operation: "manager",
              } as HostFailure,
            });
        });
    }
    return () => {
      active = false;
      close?.();
      invalidate();
    };
  }, [host, invalidate, managerObserved, refresh]);

  useEffect(() => {
    if (!host.observeSignIn) return;
    let active = true;
    let revision = -1;
    let close: (() => void) | undefined;
    void host
      .observeSignIn((signal) => {
        if (!active || signal.revision <= revision) return;
        revision = signal.revision;
        if (!managerAllows()) return;
        if (awaitingManagerAuth.current) {
          // A new observation can re-arm a failed fresh read. The queued
          // observation itself is never used as recovery authentication.
          void refresh(true);
          return;
        }
        if (submitting.current) return;
        invalidate();
        const next =
          signal.kind === "sign-in-state"
            ? signal.status
            : {
                ...unknownStatus,
                runtimeAvailable: false,
                refusal: refusalFrom(signal.error),
              };
        statusReadFailed.current = signal.kind === "sign-in-observation-failed";
        latestStatus.current = next;
        setStatus(next);
        setRefusal(null);
        setChosen(null);
        if (next.runtimeAvailable) setObservingStartup(false);
        listed.current = null;
        setProfiles(null);
        if (
          host.profiles &&
          next.runtimeAvailable &&
          next.state !== "present"
        ) {
          const generation = request.current;
          const accounts = host.profiles;
          void (async () => {
            while (statusRead.current) {
              await statusRead.current.promise;
              if (!active || generation !== request.current) return;
            }
            if (!active || generation !== request.current || !managerAllows())
              return;
            const promise = Promise.resolve().then(async () => {
              try {
                const list = await boundedRead(accounts.list());
                if (
                  !active ||
                  generation !== request.current ||
                  !managerAllows()
                )
                  return;
                listed.current = list;
                setProfiles(list);
              } catch {
                if (active && generation === request.current)
                  setProfiles({ profiles: [], complete: false });
              } finally {
                if (statusRead.current?.generation === generation)
                  statusRead.current = null;
              }
            });
            statusRead.current = { generation, promise };
            await promise;
          })();
        }
      })
      .then((unsubscribe) => {
        if (active) close = unsubscribe;
        else unsubscribe();
      })
      .catch(() => {
        /* Existing status reads retain their bounded fallback. */
      });
    return () => {
      active = false;
      close?.();
    };
  }, [host, invalidate, managerAllows, refresh]);

  useEffect(() => {
    mounted.current = true;
    let active = true;
    let expired = false;
    const deadline = window.setTimeout(() => {
      expired = true;
      setObservingStartup(false);
      // A missing answer is not readiness. Give a stalled initial read a
      // visible failure instead of leaving a skeleton on screen forever.
      if (!latestStatus.current && host.available) {
        const unavailable = {
          ...unknownStatus,
          runtimeAvailable: false,
          refusal: { code: "runtime_unavailable", retryAfterSeconds: null },
        };
        latestStatus.current = unavailable;
        setStatus(unavailable);
      }
    }, STARTUP_WAIT_MS);
    const observeStartup = async () => {
      do {
        await refresh();
        if (!active) return;
        if (
          !host.startManager ||
          statusReadFailed.current ||
          latestStatus.current?.runtimeAvailable !== false
        ) {
          window.clearTimeout(deadline);
          setObservingStartup(false);
          return;
        }
        await new Promise<void>((resolve) => window.setTimeout(resolve, 1_000));
      } while (active && !expired);
    };
    // Production observations own manager progress; the legacy fixture port
    // retains its existing bounded startup reads.
    if (managerObserved) void refresh();
    else void observeStartup();
    const focus = () => void refresh();
    window.addEventListener("focus", focus);
    return () => {
      active = false;
      window.clearTimeout(deadline);
      mounted.current = false;
      invalidate();
      window.removeEventListener("focus", focus);
    };
  }, [refresh, invalidate, host, managerObserved]);

  const settledPhase = phaseOf(
    host.available,
    status,
    profiles,
    host.profiles !== undefined && profiles === null,
  );
  const phase: AccountPhase =
    managerObserved && managerAllows() && awaitingManagerAuth.current
      ? "starting"
      : (observingStartup || (managerObserved && manager === null)) &&
          (settledPhase === "checking" || settledPhase === "services-down")
        ? "starting"
        : settledPhase;
  const startServices = async (scope?: "user" | "machine") => {
    if (!host.startManager || startingManager.current || submitting.current)
      return;
    startingManager.current = true;
    setStartingServices(true);
    setRefusal(null);
    try {
      const outcome =
        scope && host.installManager
          ? await host.installManager(scope)
          : await host.startManager();
      if (!mounted.current) return;
      if (outcome !== "dispatched") {
        setRefusal({ code: `manager_${outcome}`, retryAfterSeconds: null });
        return;
      }
      if (managerObserved) return;
      const until = performance.now() + 90_000;
      do {
        await refresh();
        if (
          !mounted.current ||
          statusReadFailed.current ||
          latestStatus.current?.runtimeAvailable
        )
          return;
        await new Promise<void>((resolve) => window.setTimeout(resolve, 1_000));
      } while (mounted.current && performance.now() < until);
      if (mounted.current)
        setRefusal({ code: "runtime_unavailable", retryAfterSeconds: null });
    } catch (error) {
      if (mounted.current) setRefusal(refusalFrom(error));
    } finally {
      startingManager.current = false;
      if (mounted.current) setStartingServices(false);
    }
  };
  // Another profile is offered only while nobody is signed in, and known
  // not to be: signing in to one does not sign the other out.
  const offering = phase === "signed-out" || phase === "no-profile";
  const target = offering ? targetOf(profiles, chosen) : null;
  const mustChoose =
    offering &&
    profiles?.complete === true &&
    profiles.profiles.length > 0 &&
    !target;

  const submit = async (password: Uint8Array) => {
    // Where there are several and none is chosen, there is nothing to send
    // a password to; nor to a profile the host would not name as written.
    if (
      submitting.current ||
      !managerAllows() ||
      mustChoose ||
      (target && !target.active && !nameable(target.name))
    ) {
      password.fill(0);
      return;
    }
    submitting.current = true;
    invalidate();
    const generation = request.current;
    setBusy(true);
    setRefusal(null);
    setCreateRefusal(null);
    setCreateUnknown(null);
    setCreated(null);
    setRemaining(null);
    setSignOutFailure(null);
    let signedIn = false;
    try {
      // The selected profile is signed in to unnamed, as it always was: the
      // product knows which it is. Only another one has to be named.
      const result = await host.signIn(
        password,
        target && !target.active ? target.name : undefined,
      );
      if (
        !mounted.current ||
        generation !== request.current ||
        !managerAllows()
      )
        return;
      if (result.kind === "refused") setRefusal(result);
      else {
        // The canonical persisted-login acknowledgement already observes
        // presence and names the authenticated profile. Older reads belong to
        // the invalidated generation; no second CLI call is needed to display it.
        signedIn = true;
        statusReadFailed.current = false;
        latestStatus.current = result.status;
        setStatus(result.status);
        listed.current = null;
        setProfiles(null);
      }
    } catch (error) {
      if (mounted.current && generation === request.current)
        setRefusal(refusalFrom(error));
    } finally {
      password.fill(0);
      if (!signedIn && mounted.current && generation === request.current)
        await refresh(true);
      submitting.current = false;
      if (mounted.current) setBusy(false);
    }
  };

  /** One attempt to create a profile. As with a sign-in, the password is
   * consumed by the one call and nothing is tried again. */
  const create = async (name: string, password: Uint8Array) => {
    const accounts = host.profiles;
    if (!accounts || submitting.current || !managerAllows()) {
      password.fill(0);
      return false;
    }
    submitting.current = true;
    invalidate();
    const generation = request.current;
    const epoch = invalidation.current;
    setBusy(true);
    setCreating(true);
    setRefusal(null);
    setCreateRefusal(null);
    setCreateUnknown(null);
    setCreated(null);
    setRemaining(null);
    setSignOutFailure(null);
    let made: string | null = null;
    let unanswered: SignInRefusal | null = null;
    try {
      const result = await accounts.create(name, password);
      if (
        !mounted.current ||
        generation !== request.current ||
        !managerAllows()
      )
        return false;
      if (result.kind === "created") made = result.name;
      else setCreateRefusal(result);
    } catch (error) {
      // No answer: timed out, stopped, unreadable. Not a refusal.
      if (mounted.current && generation === request.current)
        unanswered = refusalFrom(error);
    } finally {
      password.fill(0);
      // Whatever was held is older than this creation: read again before
      // anything is shown or named.
      if (
        mounted.current &&
        generation === request.current &&
        (made !== null || unanswered)
      ) {
        listed.current = null;
        setProfiles(null);
      }
      if (mounted.current && generation === request.current)
        await refresh(true);
      if (
        mounted.current &&
        epoch === invalidation.current &&
        managerAllows() &&
        unanswered
      ) {
        // The list is the witness: a profile of that name now in it was
        // created, whatever became of the answer.
        const folded = name.toLowerCase();
        const found = listed.current?.complete
          ? listed.current.profiles.find((p) => p.name.toLowerCase() === folded)
          : undefined;
        if (found) made = found.name;
        else setCreateUnknown(unanswered);
      }
      if (
        mounted.current &&
        epoch === invalidation.current &&
        managerAllows() &&
        made !== null
      ) {
        setChosen(made);
        setCreated(made);
      }
      submitting.current = false;
      setCreating(false);
      setBusy(false);
    }
    return made !== null;
  };

  const signOut = async () => {
    if (submitting.current || !managerAllows()) return;
    submitting.current = true;
    invalidate();
    const generation = request.current;
    setBusy(true);
    setRefusal(null);
    setSignOutFailure(null);
    try {
      await statusRead.current?.promise;
      if (
        !mounted.current ||
        generation !== request.current ||
        !managerAllows()
      )
        return;
      const remaining = await host.signOut();
      if (
        !mounted.current ||
        generation !== request.current ||
        !managerAllows()
      )
        return;
      setRemaining(remaining);
    } catch (error) {
      if (mounted.current && generation === request.current)
        setSignOutFailure(refusalFrom(error));
    } finally {
      if (mounted.current && generation === request.current)
        await refresh(true);
      submitting.current = false;
      setBusy(false);
    }
  };

  return {
    manager,
    recoveringServices:
      manager?.state === "recovering" || manager?.state === "waiting",
    status,
    phase,
    /** The profiles on this computer, or null where the host offers none. */
    profiles,
    /** The profile a password would sign in to, where it is known. */
    target,
    /** Whether another profile, or a new one, may be offered now. */
    offering,
    /** Several profiles and none chosen: the choice comes before a password. */
    mustChoose,
    /** A creation is in flight. */
    creating,
    /** A creation that got no answer: its outcome is not known. */
    createUnknown,
    /** Whether this host can create a profile. */
    canCreate: host.profiles !== undefined,
    createRefusal,
    /** The name of a profile created a moment ago and not yet signed in to. */
    created,
    choose: (name: string) => {
      setChosen(name);
      // What another profile's attempt was refused for is not this one's.
      setRefusal(null);
      setCreated(null);
    },
    create,
    refusal: currentRefusal,
    retrySeconds,
    busy,
    startingServices,
    canStartServices: host.startManager !== undefined,
    canInstallServices: host.installManager !== undefined,
    startServices,
    remaining,
    signOutFailure,
    gated: GATED.has(phase),
    canSignIn: canSignIn(phase),
    submit,
    signOut,
    /** The person has seen what was refused: a refusal that came from an
     * attempt is not shown again when its surface is next opened. What is
     * still true stays: a wait that is running, a profile that is locked. */
    settle: () => {
      setRefusal((held) =>
        held && STANDING.has(held.code.toUpperCase()) ? held : null,
      );
      setSignOutFailure(null);
      setCreateRefusal(null);
      setCreateUnknown(null);
    },
    /** Read the status again: something else has shown it may be stale. */
    recheck: () => refresh(),
    /** The TUI's session ended: what it did to the account is read again. */
    tuiExited: () => {
      setRefusal(null);
      void refresh();
    },
  };
}

export type SignInController = ReturnType<typeof useSignIn>;
