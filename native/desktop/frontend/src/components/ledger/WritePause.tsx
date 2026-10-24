// The Ledger page's one write pause. A write whose outcome was not observed
// may have committed: it is never sent again, and every write on the page
// waits until the person reads the ledger again and that read settles what
// is undetermined. Every writer reads the pause and records into it; the
// page owns it, shows it in one banner, and runs the one re-read.

import {
  cloneElement,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent,
  type ReactElement,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { LedgerPort } from "../../shell/ledger";
import type { LedgerPeriod } from "../../shell/ledgerGrammar";
import { readWindow } from "../../shell/ledgerWindow";
import { useStrings } from "../../shell/strings";

/** How a write that was not seen to settle ended as far as the page knows:
 * sent and not observed, or saved with its answer not read. */
export type HeldOutcome = "unknown" | "saved_unread";

/** A write whose outcome the page does not know. */
export type HeldWrite = {
  /** What is undetermined, in words: the movement, invoice or register. */
  what: string;
  outcome: HeldOutcome;
  /** Reads what the write touched and words what it found, one line per
   * thing; null while the ledger could not be read, which keeps it held.
   * Without one, a read of the ledger that answers settles it. */
  settle?: () => Promise<string[] | null>;
  /** Called once the re-read settled it. */
  onSettled?: () => void;
};

type Held = HeldWrite & { id: number };

export type WritePause = {
  /** Why writes wait, in words, or null while they may run. */
  held: string | null;
  /** What is undetermined, in the order it happened. */
  writes: readonly HeldWrite[];
  /** Records a write whose outcome was not observed. */
  hold(write: HeldWrite): void;
  /** Reads the ledger again and settles what it can. */
  reread(): void;
  rereading: boolean;
  /** What the last re-read found, one line each, until dismissed. */
  findings: readonly string[] | null;
  dismissFindings(): void;
  /** Counts the re-reads, so a read keyed on it reads again after one. */
  round: number;
};

const NOT_PAUSED: WritePause = {
  held: null,
  writes: [],
  hold: () => {},
  reread: () => {},
  rereading: false,
  findings: null,
  dismissFindings: () => {},
  round: 0,
};

export const WritePauseContext = createContext<WritePause>(NOT_PAUSED);

/** The page's write pause, as a writer reads it. */
export function useWritePause(): WritePause {
  return useContext(WritePauseContext);
}

/** The page's one write pause. It goes with the profile. */
export function usePagePause({
  port,
  reader,
  period,
  afterReread,
}: {
  port: LedgerPort;
  reader: string | null;
  period: LedgerPeriod | null;
  /** Reads the page's movements again once a re-read ran. */
  afterReread: () => void;
}): WritePause {
  const t = useStrings();
  const [writes, setWrites] = useState<Held[]>([]);
  const [findings, setFindings] = useState<string[] | null>(null);
  const [rereading, setRereading] = useState(false);
  const [round, setRound] = useState(0);
  const next = useRef(0);
  const latest = useRef(writes);
  latest.current = writes;
  useEffect(() => {
    setWrites([]);
    setFindings(null);
  }, [reader]);

  const hold = useCallback((write: HeldWrite) => {
    next.current += 1;
    const id = next.current;
    setFindings(null);
    setWrites((held) => [...held, { ...write, id }]);
  }, []);

  const busy = useRef(false);
  const reread = useCallback(() => {
    if (busy.current) return;
    busy.current = true;
    setRereading(true);
    void (async () => {
      const asked = latest.current;
      const settled = new Set<number>();
      const lines: string[] = [];
      let answered: boolean | null = null;
      for (const write of asked) {
        if (write.settle) {
          const found = await write.settle();
          if (found === null) continue;
          lines.push(...found);
        } else {
          answered ??= (await readWindow(port, period, 1)).kind === "read";
          if (!answered) continue;
          lines.push(
            t(
              write.outcome === "saved_unread"
                ? "desktop.ledger.paused.found_saved"
                : "desktop.ledger.paused.read_again",
              { movement: write.what },
            ),
          );
        }
        settled.add(write.id);
        write.onSettled?.();
      }
      setWrites((held) => held.filter((write) => !settled.has(write.id)));
      if (lines.length) setFindings(lines);
      setRound((value) => value + 1);
      busy.current = false;
      setRereading(false);
      afterReread();
    })();
  }, [port, period, t, afterReread]);

  const unknown = writes.some((write) => write.outcome === "unknown");
  return {
    held:
      writes.length === 0
        ? null
        : unknown
          ? t("desktop.ledger.tray.paused_reason")
          : t("desktop.ledger.paused.saved_unread_reason"),
    writes,
    hold,
    reread,
    rereading,
    findings,
    dismissFindings: () => setFindings(null),
    round,
  };
}

/** The page's banner, in the Alert pattern with its one action at its end:
 * what waits and the re-read that settles it, then what the re-read found
 * until it is dismissed. */
export function PausedBanner({ pause }: { pause: WritePause }) {
  const t = useStrings();
  if (pause.writes.length === 0 && !pause.findings) return null;
  const unknown = pause.writes.some((write) => write.outcome === "unknown");
  const names = [...new Set(pause.writes.map((write) => write.what))];
  // The banner names the first; the rest are counted.
  const named = names.length > 1 ? [names[0]!, `+${names.length - 1}`] : names;
  return (
    <div className="ledger-paused px-3 pt-3">
      {pause.writes.length > 0 ? (
        <Alert tone="warning" role="alert" icon={<Icon name="unknown" />}>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="min-w-0 flex-1" title={names.join(" · ")}>
              {[
                t(
                  unknown
                    ? "desktop.ledger.paused.title"
                    : "desktop.ledger.paused.saved_unread",
                ),
                ...named,
              ].join(" · ")}
            </span>
            <Button
              size="xs"
              variant="outline"
              className="ledger-paused-reread shrink-0"
              aria-disabled={pause.rereading || undefined}
              onClick={() => {
                if (!pause.rereading) pause.reread();
              }}
            >
              <Icon name="sync" />
              {t("desktop.ledger.paused.reread")}
            </Button>
          </div>
        </Alert>
      ) : (
        <Alert
          tone="neutral"
          role="status"
          icon={<Icon name="info" />}
          className="ledger-findings"
        >
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="min-w-0 flex-1">
              {(pause.findings ?? []).join(" · ")}
            </span>
            <Button
              variant="ghost"
              size="xs"
              className="shrink-0"
              onClick={pause.dismissFindings}
            >
              {t("desktop.ledger.paused.dismiss")}
            </Button>
          </div>
        </Alert>
      )}
    </div>
  );
}

type Holdable = ReactElement<{
  "aria-disabled"?: boolean | "true" | "false";
  "aria-describedby"?: string;
  onClick?: (event: MouseEvent<HTMLElement>) => void;
  /** An icon button's own tooltip, which says the reason as its hint. */
  label?: string;
  hint?: string;
}>;

/**
 * A write control that waits while the page's writes are paused: it stays
 * focusable, says why in its tooltip and its description, and does
 * nothing when pressed, a form's own submit included. `when` false leaves
 * a control that does not write, at that moment, as it is.
 */
export function WriteHold({
  children,
  when = true,
}: {
  children: Holdable;
  when?: boolean;
}) {
  const { held } = useWritePause();
  const reason = useId();
  if (held === null || !when) return children;
  const stop = (event: MouseEvent<HTMLElement>) => event.preventDefault();
  // An icon button has its tooltip and name already: the reason is its hint.
  if (children.props.label !== undefined)
    return cloneElement(children, {
      "aria-disabled": true,
      hint: held,
      onClick: stop,
    });
  const described = [children.props["aria-describedby"], reason]
    .filter(Boolean)
    .join(" ");
  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          {cloneElement(children, {
            "aria-disabled": true,
            "aria-describedby": described,
            onClick: stop,
          })}
        </TooltipTrigger>
        <TooltipContent>{held}</TooltipContent>
      </Tooltip>
      <span id={reason} hidden>
        {held}
      </span>
    </>
  );
}
