import { useCallback, useEffect, useRef, useState } from "react";
import type { DesktopLanguage } from "../ipc/contract";
import type { Host } from "./host";
import type { AccountPhase } from "./signIn";
import { OUTPUT_LANGUAGES } from "./strings";

type LanguageState = {
  host: Host;
  identity: string;
  value: DesktopLanguage;
};

/** The host owns profile persistence; a browser choice lasts only this mount. */
export function useLanguage(
  host: Host,
  fallback: string,
  account: { phase: AccountPhase; profile: string | null },
) {
  const identity = JSON.stringify([account.phase, account.profile]);
  const profile = account.phase === "signed-in" ? account.profile : null;
  const [state, setState] = useState<LanguageState | null>(null);
  const accepted = useRef<LanguageState | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const generation = useRef(0);
  const accept = useCallback(
    (next: DesktopLanguage) => {
      if (
        next.profile !== profile ||
        !OUTPUT_LANGUAGES.includes(next.language) ||
        !Number.isSafeInteger(next.revision)
      )
        return;
      const current = accepted.current;
      if (
        current?.host === host &&
        current.identity === identity &&
        current.value.revision >= next.revision
      )
        return;
      const updated = { host, identity, value: next };
      accepted.current = updated;
      setState(updated);
      setFailed(false);
    },
    [host, identity, profile],
  );
  useEffect(() => {
    let current = true;
    let stop: (() => void) | undefined;
    const mine = ++generation.current;
    setPending(false);
    if (host.language) {
      // Subscribe before reading: a newer observation wins over an older answer.
      void host.language
        .observe((next) => current && accept(next))
        .then((close) => {
          if (current) stop = close;
          else close();
        })
        .catch(() => current && setFailed(true));
      void host.language
        .read()
        .then((next) => current && accept(next))
        .catch(() => current && setFailed(true));
    }
    return () => {
      current = false;
      stop?.();
      generation.current = mine + 1;
    };
  }, [host, identity, accept]);
  const change = useCallback(
    async (language: string) => {
      if (!OUTPUT_LANGUAGES.includes(language)) return;
      const mine = generation.current;
      setPending(true);
      setFailed(false);
      try {
        const next = host.language
          ? await host.language.set(language)
          : {
              language,
              persisted: false,
              profile: null,
              revision: (state?.value.revision ?? 0) + 1,
            };
        if (generation.current === mine) accept(next);
      } catch {
        if (generation.current === mine) setFailed(true);
      } finally {
        if (generation.current === mine) setPending(false);
      }
    },
    [host, state?.value.revision, accept],
  );
  // Account changes must hide the previous profile before effects resubscribe.
  const value =
    state?.host === host && state.identity === identity ? state.value : null;
  return { locale: value?.language ?? fallback, pending, failed, change };
}
