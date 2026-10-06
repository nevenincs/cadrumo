import { useCallback, useEffect, useRef, useState } from "react";
import type {
  SignInRefusal,
  SignInStatus,
  SignOutResult,
} from "../ipc/contract";
import type { Host } from "./host";
import { targetOf, type ProfileList } from "./profiles";
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
  return {
    code: failureCode(error),
    retryAfterSeconds:
      typeof seconds === "number" && Number.isFinite(seconds)
        ? Math.max(0, seconds)
        : null,
  };
}

/**
 * The one reading of the account that every element shows: the sign-in
 * dialog, the TUI pane and its header, settings, the rail and the actions.
 * Nothing else derives a state of its own from the raw status.
 */
export type AccountPhase =
  /** The page runs without a desktop host. */
  | "no-host"
  /** The first status read has not answered yet. */
  | "checking"
  /** This platform signs in inside the TUI; the shell offers nothing. */
  | "unsupported"
  | "signed-in"
  /** The person chose to carry on in the TUI's own flow. */
  | "in-tui"
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
  "services-down",
  "unknown",
  "no-profile",
  "signed-out",
]);

export function phaseOf(
  available: boolean,
  status: SignInStatus | null,
  handover: boolean,
  profiles: ProfileList | null = null,
): AccountPhase {
  if (!available) return "no-host";
  if (!status) return "checking";
  if (!status.supported) return "unsupported";
  if (status.state === "present") return "signed-in";
  if (handover) return "in-tui";
  if (!status.runtimeAvailable) return "services-down";
  if (status.state === "unknown") return "unknown";
  // With none selected, the profiles that exist are still there to choose
  // from: only where none is known is there nothing to sign in to.
  if (status.active_profile === null && !profiles?.profiles.length)
    return "no-profile";
  return "signed-out";
}

/** Refusals a password cannot answer: the way on is the TUI's own flow. */
const HANDED_OVER: ReadonlySet<string> = new Set([
  "PROFILE_LOCKED",
  "KEYRING_UNAVAILABLE",
]);

/** Refusals that outlast the attempt that met them. */
const STANDING: ReadonlySet<string> = new Set([...HANDED_OVER, "THROTTLED"]);

/** Whether a password can settle the account as it stands. Every element
 * that offers sign-in asks this, so none offers a form that is not there. */
export function canSignIn(
  phase: AccountPhase,
  refusal: SignInRefusal | null,
): boolean {
  return (
    (phase === "signed-out" || phase === "unknown") &&
    !(refusal && HANDED_OVER.has(refusal.code.toUpperCase()))
  );
}

const COUNTDOWN_TICK_MS = 250;

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
  const [status, setStatus] = useState<SignInStatus | null>(null);
  const [refusal, setRefusal] = useState<SignInRefusal | null>(null);
  const [busy, setBusy] = useState(false);
  const [handover, setHandover] = useState(false);
  // The profiles to choose from, where the host offers them; the one the
  // person chose; and what became of the last attempt to create one.
  const [profiles, setProfiles] = useState<ProfileList | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [createRefusal, setCreateRefusal] = useState<SignInRefusal | null>(
    null,
  );
  const [created, setCreated] = useState<string | null>(null);
  const [remaining, setRemaining] = useState<SignOutResult | null>(null);
  // A sign-out that failed is its own fact: it is not a sign-in refusal.
  const [signOutFailure, setSignOutFailure] = useState<SignInRefusal | null>(
    null,
  );
  const request = useRef(0);
  const mounted = useRef(true);
  const statusRead = useRef<{
    generation: number;
    promise: Promise<void>;
  } | null>(null);
  const submitting = useRef(false);
  const currentRefusal = refusal ?? status?.refusal ?? null;
  const retrySeconds = useCountdown(currentRefusal);
  const invalidate = useCallback(() => {
    ++request.current;
  }, []);

  const refresh = useCallback(
    async (afterMutation = false) => {
      if (
        !mounted.current ||
        !host.available ||
        (submitting.current && !afterMutation)
      )
        return;
      while (statusRead.current) {
        const pending = statusRead.current;
        await pending.promise;
        if (!mounted.current) return;
        if (pending.generation === request.current) return;
      }
      if (
        !mounted.current ||
        !host.available ||
        (submitting.current && !afterMutation)
      )
        return;
      const generation = ++request.current;
      const promise = Promise.resolve().then(async () => {
        try {
          // Read together, so that the form never shows a status beside
          // a list that is older than it. A list that cannot be read is
          // not an empty one.
          const [next, list] = await Promise.all([
            host.signInStatus(),
            host.profiles ? host.profiles.list().catch(() => null) : null,
          ]);
          if (generation !== request.current) return;
          setStatus(next);
          if (host.profiles)
            setProfiles(
              (held) => list ?? held ?? { profiles: [], complete: false },
            );
        } catch (error) {
          if (generation === request.current)
            setStatus({ ...unknownStatus, refusal: refusalFrom(error) });
        } finally {
          if (statusRead.current?.generation === generation)
            statusRead.current = null;
        }
      });
      statusRead.current = { generation, promise };
      await promise;
    },
    [host],
  );

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const focus = () => void refresh();
    window.addEventListener("focus", focus);
    return () => {
      mounted.current = false;
      invalidate();
      window.removeEventListener("focus", focus);
    };
  }, [refresh, invalidate]);

  const target = targetOf(profiles, chosen);

  const submit = async (password: Uint8Array) => {
    // Where there are several and none is chosen, there is nothing to send
    // a password to.
    if (submitting.current || (profiles?.profiles.length && !target)) {
      password.fill(0);
      return;
    }
    submitting.current = true;
    invalidate();
    setBusy(true);
    setRefusal(null);
    setCreateRefusal(null);
    setCreated(null);
    setRemaining(null);
    setSignOutFailure(null);
    try {
      await statusRead.current?.promise;
      const result = await host.signIn(password, target?.name);
      if (result.kind === "refused") setRefusal(result);
    } catch (error) {
      setRefusal(refusalFrom(error));
    } finally {
      password.fill(0);
      await refresh(true);
      submitting.current = false;
      setBusy(false);
    }
  };

  /** One attempt to create a profile. As with a sign-in, the password is
   * consumed by the one call and nothing is tried again. */
  const create = async (name: string, password: Uint8Array) => {
    const accounts = host.profiles;
    if (!accounts || submitting.current) {
      password.fill(0);
      return false;
    }
    submitting.current = true;
    invalidate();
    setBusy(true);
    setRefusal(null);
    setCreateRefusal(null);
    setCreated(null);
    setRemaining(null);
    setSignOutFailure(null);
    let made = false;
    try {
      await statusRead.current?.promise;
      const result = await accounts.create(name, password);
      if (result.kind === "created") {
        setChosen(result.name);
        setCreated(result.name);
        made = true;
      } else setCreateRefusal(result);
    } catch (error) {
      setCreateRefusal(refusalFrom(error));
    } finally {
      password.fill(0);
      await refresh(true);
      submitting.current = false;
      setBusy(false);
    }
    return made;
  };

  const signOut = async () => {
    if (submitting.current) return;
    submitting.current = true;
    invalidate();
    setBusy(true);
    setRefusal(null);
    setSignOutFailure(null);
    try {
      await statusRead.current?.promise;
      setRemaining(await host.signOut());
      setHandover(false);
    } catch (error) {
      setSignOutFailure(refusalFrom(error));
    } finally {
      await refresh(true);
      submitting.current = false;
      setBusy(false);
    }
  };

  const phase = phaseOf(host.available, status, handover, profiles);
  return {
    status,
    phase,
    /** The profiles on this computer, or null where the host offers none. */
    profiles,
    /** The profile a password would sign in to, where it is known. */
    target,
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
    remaining,
    signOutFailure,
    gated: GATED.has(phase),
    canSignIn: canSignIn(phase, currentRefusal),
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
    },
    /** Read the status again: something else has shown it may be stale. */
    recheck: () => refresh(),
    openTui: () => setHandover(true),
    tuiExited: () => {
      setHandover(false);
      setRefusal(null);
      void refresh();
    },
  };
}

export type SignInController = ReturnType<typeof useSignIn>;
