import { useCallback, useEffect, useRef, useState } from "react";

/** Keeps one transient message visible and replaces its expiry on each notice. */
export function useToastMessage(durationMs: number) {
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef(0);
  const say = useCallback(
    (text: string) => {
      setToast(text);
      window.clearTimeout(toastTimer.current);
      toastTimer.current = window.setTimeout(() => setToast(null), durationMs);
    },
    [durationMs],
  );
  useEffect(() => () => window.clearTimeout(toastTimer.current), []);
  return { toast, say };
}
