import { useCallback } from "react";
import type { Host } from "./host";
import type { Translate } from "./strings";

/** An address opened in the system browser. A refusal is said aloud: the
 * person must not wait for a page that is not coming. */
export function useOpenExternal(
  host: Host,
  say: (text: string) => void,
  t: Translate,
) {
  return useCallback(
    (url: string) => {
      host.openExternal(url).catch(() => say(t("desktop.toast.open_failed")));
    },
    [host, say, t],
  );
}
