import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type {
  ModeloFormIssueLine,
  ModeloFormVerdict,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import type { OpenableSurface } from "../details/Details";
import { BoxNumber } from "../form/BoxNumber";
import { ATTENTION_ICON, ATTENTION_TONE } from "./Marks";

export function Heading({ title, lead }: { title: string; lead?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="font-serif text-lg text-foreground">{title}</h2>
      {lead && <p className="text-base text-muted-foreground">{lead}</p>}
    </div>
  );
}

function Line({
  line,
  onGo,
  onOpenSurface,
  canOpenSurface,
  onRecalculate,
  onAnswer,
  onOpenInvoice,
}: {
  line: ModeloFormIssueLine;
  onGo(line: ModeloFormIssueLine): void;
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface(surface: OpenableSurface): boolean;
  onRecalculate: (() => void) | null;
  onAnswer: ((line: ModeloFormIssueLine) => void) | null;
  onOpenInvoice: ((invoiceId: string) => void) | null;
}) {
  const t = useStrings();
  const invoice = onOpenInvoice ? (line.invoice_id ?? null) : null;
  const surface =
    line.surface && line.surface !== "none" && canOpenSurface(line.surface)
      ? line.surface
      : null;
  const body = (
    <>
      <BoxNumber box={line.box} />
      <span className="flex flex-col gap-1">
        {line.where && <span className="text-xs text-faint">{line.where}</span>}
        <span className="text-base text-foreground">{line.message}</span>
        <span className="text-sm text-muted-foreground">{line.action}</span>
        {line.detail && (
          <span className="text-sm text-muted-foreground">{line.detail}</span>
        )}
      </span>
      {line.address && <Icon name="forward" size="xs" className="text-faint" />}
    </>
  );
  // The answer a line offers is the application's: accept its
  // disagreement, or revoke the acceptance that covers it.
  const offered = onAnswer ? (line.resolution_answer ?? null) : null;
  const actions = (surface ||
    invoice ||
    (line.recalculates && onRecalculate) ||
    offered) && (
    <div className="flex flex-wrap gap-3 px-4 pb-3">
      {invoice && onOpenInvoice && (
        <Button
          size="sm"
          variant="link"
          data-line-door="open_invoice"
          onClick={() => onOpenInvoice(invoice)}
        >
          {t("workspace.modelo.open_invoice")}
          <Icon name="forward" size="xs" />
        </Button>
      )}
      {surface && (
        <Button size="sm" variant="link" onClick={() => onOpenSurface(surface)}>
          {t(`workspace.modelo.surface.open.${surface}`)}
          <Icon name="forward" size="xs" />
        </Button>
      )}
      {line.recalculates && onRecalculate && (
        <Button size="sm" variant="link" onClick={onRecalculate}>
          {t("workspace.modelo.next_button.recalculate")}
          <Icon name="forward" size="xs" />
        </Button>
      )}
      {offered && onAnswer && (
        <Button
          size="sm"
          variant="link"
          data-answer-offered={offered}
          onClick={() => onAnswer(line)}
        >
          {t(
            offered === "revoke"
              ? "desktop.modelo.disagreement.revoke"
              : "desktop.modelo.disagreement.accept",
          )}
        </Button>
      )}
    </div>
  );
  const grid =
    "grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 text-left";
  return (
    <li>
      {line.address ? (
        <button
          type="button"
          onClick={() => onGo(line)}
          className={cn(
            grid,
            "hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset",
          )}
        >
          {body}
        </button>
      ) : (
        <div className={grid}>{body}</div>
      )}
      {actions}
    </li>
  );
}

/**
 * What the check and the calculation found, as the read model words it,
 * grouped by how much each line asks of the filer. A line that leads to a
 * box or a table opens it in the form; one whose value is kept in another
 * area opens that area.
 */
export function CheckView({
  verdict,
  lines,
  stagedCount,
  onGo,
  onOpenSurface,
  canOpenSurface,
  onRecalculate,
  onAnswer = null,
  onOpenInvoice = null,
  answers,
  recoveries,
}: {
  verdict: ModeloFormVerdict;
  lines: ModeloFormIssueLine[];
  /** Edits the form holds unapplied, which the verdict does not include. */
  stagedCount: number;
  onGo(line: ModeloFormIssueLine): void;
  onOpenSurface(surface: OpenableSurface): void;
  /** Whether this window can open an area; a link that cannot is not drawn. */
  canOpenSurface(surface: OpenableSurface): boolean;
  /** Calculates again, or null while that cannot be done from here. */
  onRecalculate: (() => void) | null;
  /** Opens the answer a disagreement's line offers, or null while none can
   * be sent from here. */
  onAnswer?: ((line: ModeloFormIssueLine) => void) | null;
  /** Opens the invoice a line asks a document for, or null while this window
   * has no Libro de facturas. */
  onOpenInvoice?: ((invoiceId: string) => void) | null;
  /** The answers given to the declaration's disagreements, drawn under the
   * lines. */
  answers?: ReactNode;
  /** The ways out the calculation's notes serve, drawn under the lines. */
  recoveries?: ReactNode;
}) {
  const t = useStrings();
  // The read model lists the lines most urgent first; the sections follow
  // that order.
  const levels = [...new Set(lines.map((line) => line.level))];
  const words =
    stagedCount > 0 && verdict.unapplied_words
      ? verdict.unapplied_words
      : verdict.words;
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading title={t("workspace.modelo.issues.title")} />
      {verdict.status === "complete" && lines.length === 0 ? (
        <Alert tone="success" icon={<Icon name="check" />}>
          {words}
        </Alert>
      ) : (
        <p className="-mt-4 text-base text-muted-foreground">{words}</p>
      )}
      {levels.map((level) => {
        const found = lines.filter((line) => line.level === level);
        const word = t(`workspace.modelo.level.${level}`);
        return (
          <section
            key={level}
            aria-label={word}
            data-attention-level={level}
            tabIndex={-1}
            className="flex flex-col gap-2 outline-none"
          >
            <h3
              className={cn(
                "flex items-center gap-1.5 text-sm font-medium",
                ATTENTION_TONE[level],
              )}
            >
              <Icon name={ATTENTION_ICON[level]} size="xs" />
              {word}
            </h3>
            <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
              {found.map((line, i) => (
                <Line
                  key={`${level}-${i}`}
                  line={line}
                  onGo={onGo}
                  onOpenSurface={onOpenSurface}
                  canOpenSurface={canOpenSurface}
                  onRecalculate={onRecalculate}
                  onAnswer={onAnswer}
                  onOpenInvoice={onOpenInvoice}
                />
              ))}
            </ul>
          </section>
        );
      })}
      {recoveries}
      {answers}
    </div>
  );
}
