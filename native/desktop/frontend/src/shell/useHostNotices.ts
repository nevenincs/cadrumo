import { useEffect, useRef, useState } from "react";
import type { Host } from "./host";
import { observeInternalFailures } from "./internalFailures";
import type { SignInController } from "./signIn";
import type { Translate } from "./strings";

/** What the host and the runtime manager report outside any request, said
 * aloud as it happens. */
export function useHostNotices({
  host,
  manager,
  say,
  t,
}: {
  host: Host;
  manager: SignInController["manager"];
  say: (text: string) => void;
  t: Translate;
}) {
  // The previous close ended changes before they reported: say once that
  // their outcome is unknown, so none is repeated blindly. The host gives the
  // answer only once, so it is asked only once.
  const previousClose = host.previousClose;
  const previousCloseAsked = useRef(false);
  const [previousCloseUnknown, setPreviousCloseUnknown] = useState(false);
  useEffect(() => {
    if (!previousClose || previousCloseAsked.current) return;
    previousCloseAsked.current = true;
    previousClose().then(
      (interrupted) => setPreviousCloseUnknown(interrupted > 0),
      () => undefined,
    );
  }, [previousClose]);
  useEffect(() => {
    if (!previousCloseUnknown) return;
    setPreviousCloseUnknown(false);
    say(t("desktop.toast.previous_close_interrupted"));
  }, [previousCloseUnknown, say, t]);

  useEffect(
    () => observeInternalFailures(() => say(t("desktop.error.internal"))),
    [say, t],
  );

  const previousManager = useRef(manager?.state);
  useEffect(() => {
    const state = manager?.state;
    const previous = previousManager.current;
    previousManager.current = state;
    if (!state || state === previous) return;
    if (state === "recovering" || state === "waiting")
      say(t("desktop.signin.recovering_services"));
    else if (state === "failed" || state === "stopped")
      say(t("desktop.signin.refused.manager"));
    else if (
      state === "ready" &&
      (previous === "recovering" || previous === "waiting")
    )
      say(t("desktop.signin.services_recovered"));
  }, [manager, say, t]);
}
