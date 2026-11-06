import { useCallback, type RefObject } from "react";
import type { TerminalApi } from "../components/TerminalPane";
import { failureCode } from "../errors";
import type { Host, TerminalKind } from "./host";
import type { Translate } from "./strings";

/** Copying to and pasting from the host's clipboard, a terminal's paste
 * included; each refusal is said aloud. */
export function useHostClipboard({
  host,
  terminals,
  say,
  t,
}: {
  host: Host;
  terminals: RefObject<Partial<Record<TerminalKind, TerminalApi>>>;
  say: (text: string) => void;
  t: Translate;
}) {
  const copy = useCallback(
    (text: string) => {
      if (!text) return;
      // A refused write, including one over the host's size cap, is said
      // aloud: the person must not believe a copy happened when it did not.
      host.writeClipboard(text).then(
        () => say(t("desktop.toast.copied")),
        () => say(t("desktop.toast.copy_failed")),
      );
    },
    [host, say, t],
  );

  const paste = useCallback(
    (kind: TerminalKind | null) => {
      if (!kind) return;
      host.readClipboard().then(
        (text) => terminals.current[kind]?.paste(text),
        // The host refuses rather than truncates an oversized clipboard, so
        // say why nothing arrived.
        (error: unknown) =>
          say(
            t(
              failureCode(error) === "output_limit"
                ? "desktop.toast.paste_too_large"
                : "desktop.toast.paste_failed",
            ),
          ),
      );
    },
    [host, say, t, terminals],
  );
  return { copy, paste };
}
