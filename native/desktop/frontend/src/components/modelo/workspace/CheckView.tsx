import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type {
  ModeloFormAttention,
  ModeloFormIssueLine,
  ModeloFormVerdict,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import type { OpenableSurface } from "../details/Details";
import { BoxNumber } from "../form/BoxNumber";
import { ATTENTION_ICON, ATTENTION_TONE } from "./Marks";

/** The order the scale reads in, most urgent first. */
const LEVELS: ModeloFormAttention[] = [
  "blocks",
  "missing",
  "confirm",
  "check",
  "info",
];

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
}: {
  line: ModeloFormIssueLine;
  onGo(line: ModeloFormIssueLine): void;
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface(surface: OpenableSurface): boolean;
  onRecalculate: (() => void) | null;
}) {
  const t = useStrings();
  const surface =
    line.surface && line.surface !== "none" && canOpenSurface(line.surface)
      ? line.surface
      : null;
  const body = (
    <>
      <BoxNumber box={line.box} />
      <span className="flex flex-col gap-1">
        <span className="text-xs text-faint">{line.where}</span>
        <span className="text-base text-foreground">{line.message}</span>
        <span className="text-sm text-muted-foreground">{line.action}</span>
        {line.detail && (
          <span className="text-sm text-muted-foreground">{line.detail}</span>
        )}
      </span>
      {line.address && <Icon name="forward" size="xs" className="text-faint" />}
    </>
  );
  const actions = (surface || (line.recalculates && onRecalculate)) && (
    <div className="flex flex-wrap gap-3 px-4 pb-3">
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
      {/* The codes are for the filer who asks for them, as in the TUI; they
          stay outside the line's button, which leads to the box. */}
      <details className="px-4 pb-3 text-sm">
        <summary className="cursor-pointer text-muted-foreground">
          {t("workspace.modelo.issues.technical")}
        </summary>
        <p className="mt-1 font-mono text-xs text-muted-foreground [overflow-wrap:anywhere]">
          {line.technical}
        </p>
      </details>
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
}) {
  const t = useStrings();
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
      {LEVELS.map((level) => {
        const found = lines.filter((line) => line.level === level);
        if (!found.length) return null;
        const word = t(`workspace.modelo.level.${level}`);
        return (
          <section
            key={level}
            aria-label={word}
            className="flex flex-col gap-2"
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
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
