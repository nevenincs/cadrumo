import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useViewParams } from "../../shell/navigation/hooks";
import { useStrings } from "../../shell/strings";

/** What a grid tells the reveal of a row a link selects. */
export type RevealGrid = {
  /** Whether the row is drawn now. */
  shown(id: string): boolean;
  /** For a row that is read but not drawn, what shows it by clearing only
   * what the person chose that hides it; null for a row not read. */
  hiding(id: string): (() => void) | null;
  /** Whether what is read is all there is to wait for, so a row not in it
   * is not found here. */
  settled: boolean;
  /** Selects the drawn row, and gives it the keyboard when `focus`. */
  reveal(id: string, focus: boolean): void;
  /** Changes whenever the grid draws other rows. */
  drawn: unknown;
  /** Inside the page: the keyboard is taken only from where the page has
   * it, never from where the person put it meanwhile. */
  within: RefObject<HTMLElement | null>;
};

export type RevealNotice =
  | { readonly kind: "hidden"; readonly show: () => void }
  | { readonly kind: "missing" };

/** The row a navigation's `select` asks of a grid, until it is settled. */
export type LinkedRow = {
  readonly ask: { readonly id: string } | null;
  /** The ask is settled: revealed, announced or dismissed. */
  done(): void;
};

/**
 * Holds the row a navigation to register element `view` selects. The page
 * holds it, not the grid, because the grid may never mount: a ledger that
 * is empty or failed to read draws no grid, and the page must still say
 * the row is not here. Each navigation replaces it.
 */
export function useLinkedRow(view: string): LinkedRow {
  const [ask, setAsk] = useState<{ readonly id: string } | null>(null);
  useViewParams(view, (params) =>
    setAsk(params.select ? { id: params.select } : null),
  );
  const done = useCallback(() => setAsk(null), []);
  return { ask, done };
}

/**
 * Reveals the row `linked` asks for in a grid: once it is drawn, it is
 * scrolled into view, selected and given the keyboard. The grid's own
 * draws settle it, never a delay. A row the person's view hides, or one
 * not found, is said in a notice instead.
 */
export function useRowReveal(linked: LinkedRow, grid: RevealGrid) {
  const { ask, done } = linked;
  const [notice, setNotice] = useState<RevealNotice | null>(null);
  const latest = useRef(grid);
  latest.current = grid;
  const { drawn, settled } = grid;
  useEffect(() => {
    if (!ask) return;
    const now = latest.current;
    if (now.shown(ask.id)) {
      done();
      setNotice(null);
      const held = document.activeElement;
      const page = now.within.current?.closest(".ledger-page");
      now.reveal(
        ask.id,
        !held || held === document.body || !!page?.contains(held),
      );
      return;
    }
    const show = now.hiding(ask.id);
    if (show) setNotice({ kind: "hidden", show });
    else if (now.settled) {
      done();
      setNotice({ kind: "missing" });
    } else setNotice(null);
  }, [ask, done, drawn, settled]);
  return {
    notice,
    dismiss: () => {
      done();
      setNotice(null);
    },
  };
}

/** What `useRowReveal` has to say: a row the person's view hides, with the
 * one action that shows it, or a row that is not found here. */
export function RowRevealNotice({
  notice,
  dismiss,
  hidden,
  missing,
}: {
  notice: RevealNotice | null;
  dismiss(): void;
  hidden: string;
  missing: string;
}) {
  const t = useStrings();
  if (!notice) return null;
  return (
    <div className="ledger-reveal-notice flex flex-wrap items-center gap-2">
      <Alert
        tone={notice.kind === "hidden" ? "warning" : "neutral"}
        icon={<Icon name={notice.kind === "hidden" ? "alert" : "info"} />}
        className="flex-1"
      >
        {notice.kind === "hidden" ? hidden : missing}
      </Alert>
      {notice.kind === "hidden" && (
        <Button
          variant="outline"
          size="sm"
          className="ledger-reveal-show"
          onClick={notice.show}
        >
          {t("desktop.ledger.reveal.show")}
        </Button>
      )}
      <Button variant="ghost" size="sm" onClick={dismiss}>
        {t("desktop.ledger.reveal.dismiss")}
      </Button>
    </div>
  );
}
