import { useCallback, useEffect, useRef, useState } from "react";
import type {
  SignInRefusal,
  SignInStatus,
  SignOutResult,
} from "../ipc/contract";
import type { Host } from "./host";
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

function useCountdown(refusal: SignInRefusal | null) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const until = Date.now() + (refusal?.retryAfterSeconds ?? 0) * 1000;
    const tick = () =>
      setSeconds(Math.max(0, Math.ceil((until - Date.now()) / 1000)));
    tick();
    const timer = window.setInterval(tick, 250);
    return () => window.clearInterval(timer);
  }, [refusal]);
  return seconds;
}

/** Only public presence and refusals live here; no password or runtime session. */
export function useSignIn(host: Host) {
  const [status, setStatus] = useState<SignInStatus | null>(null);
  const [refusal, setRefusal] = useState<SignInRefusal | null>(null);
  const [busy, setBusy] = useState(false);
  const [handover, setHandover] = useState(false);
  const [remaining, setRemaining] = useState<SignOutResult | null>(null);
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
          const next = await host.signInStatus();
          if (generation === request.current) setStatus(next);
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

  const submit = async (password: Uint8Array) => {
    if (submitting.current) {
      password.fill(0);
      return;
    }
    submitting.current = true;
    invalidate();
    setBusy(true);
    setRefusal(null);
    setRemaining(null);
    try {
      await statusRead.current?.promise;
      const result = await host.signIn(password);
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

  const signOut = async () => {
    if (submitting.current) return;
    submitting.current = true;
    invalidate();
    setBusy(true);
    setRefusal(null);
    try {
      await statusRead.current?.promise;
      setRemaining(await host.signOut());
      setHandover(false);
    } catch (error) {
      setRefusal(refusalFrom(error));
    } finally {
      await refresh(true);
      submitting.current = false;
      setBusy(false);
    }
  };

  return {
    status,
    refusal: currentRefusal,
    retrySeconds,
    busy,
    remaining,
    gated:
      host.available &&
      !handover &&
      (!status || (status.supported && status.state !== "present")),
    submit,
    signOut,
    openTui: () => setHandover(true),
    tuiExited: () => {
      setHandover(false);
      setRefusal(null);
      void refresh();
    },
  };
}

export type SignInController = ReturnType<typeof useSignIn>;
