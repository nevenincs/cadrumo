import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type { ModeloFormAddressV1 } from "../../../shell/modeloContract/modeloEditWork";
import type {
  ModeloFormIssueLine,
  PublicModeloFormField,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import type { OpenableSurface } from "../details/Details";
import { BoxNumber } from "../form/BoxNumber";
import { addressKey } from "../form/session";
import { BoxLabel } from "./BoxLabel";
import { ORIGIN_LOOK, TONE_TEXT } from "../form/originLook";
import { Heading } from "./CheckView";
import { ATTENTION_ICON, ATTENTION_TONE } from "./Marks";

// The credits a register supplies, as the form served them: each box with
// its figure or, where it has none, the words of why not, never a zero; the
// boxes that read them, which have no figure while a credit has none; and the
// way to the register where a credit is corrected. No box is typed into here.

/** A box's figure, or the words of why it has none. */
function Figure({ field }: { field: PublicModeloFormField }) {
  const look = ORIGIN_LOOK[field.origin];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 text-base",
        TONE_TEXT[look.tone],
      )}
    >
      <Icon name={look.icon} size="xs" />
      {field.value_text ? (
        <span data-figure="" className="font-mono tabular-nums">
          {field.value_text}
        </span>
      ) : (
        <span>{field.origin_words}</span>
      )}
    </span>
  );
}

function Notes({
  lines,
  onAnswer,
}: {
  lines: readonly ModeloFormIssueLine[];
  onAnswer?: ((line: ModeloFormIssueLine) => void) | null;
}) {
  const t = useStrings();
  return (
    <>
      {lines.map((line) => (
        <span
          key={line.technical}
          data-level={line.level}
          className="flex items-start gap-1.5 text-sm text-muted-foreground"
        >
          <Icon
            name={ATTENTION_ICON[line.level]}
            size="xs"
            className={cn("mt-0.5 shrink-0", ATTENTION_TONE[line.level])}
          />
          <span className="flex flex-col items-start gap-1">
            <span>
              {line.message} {line.action}
            </span>
            {onAnswer && line.resolution_answer && (
              <Button
                size="xs"
                variant="link"
                className="h-auto p-0 text-sm"
                data-answer-offered={line.resolution_answer}
                onClick={() => onAnswer(line)}
              >
                {t(
                  line.resolution_answer === "revoke"
                    ? "desktop.modelo.disagreement.revoke"
                    : "desktop.modelo.disagreement.accept",
                )}
              </Button>
            )}
          </span>
        </span>
      ))}
    </>
  );
}

function CreditRow({
  field,
  lines,
  extra,
  onGo,
  onAnswer,
}: {
  field: PublicModeloFormField;
  lines: readonly ModeloFormIssueLine[];
  extra?: ReactNode;
  onGo(address: ModeloFormAddressV1): void;
  onAnswer?: ((line: ModeloFormIssueLine) => void) | null;
}) {
  const t = useStrings();
  return (
    <li
      data-credit={field.box ?? undefined}
      data-origin={field.origin}
      className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 px-4 py-3"
    >
      <BoxNumber box={field.box} />
      <span className="flex min-w-0 flex-col gap-1">
        <span className="text-base">
          <BoxLabel text={field.label} />
        </span>
        {field.value_text && field.origin_words && (
          <span className="text-sm text-muted-foreground">
            {field.origin_words}
          </span>
        )}
        {field.editability_words && (
          <span className="text-sm text-muted-foreground">
            {field.editability_words}
          </span>
        )}
        <Notes lines={lines} onAnswer={onAnswer} />
        {extra}
      </span>
      <span className="flex flex-col items-end gap-1">
        <Figure field={field} />
        {field.box && (
          <Button
            size="xs"
            variant="link"
            className="h-auto p-0 text-sm"
            onClick={() => onGo(field.address)}
          >
            {t("desktop.modelo.credits.show_box", { box: field.box })}
          </Button>
        )}
      </span>
    </li>
  );
}

/**
 * The boxes a register supplies and the boxes that read them. A credit is
 * corrected where it is kept: the way there is offered when this window has
 * the page. The estimate from the quarterly declarations sits under them.
 */
export function Credits({
  heading,
  credits,
  dependents,
  lines,
  onGo,
  onOpenSurface,
  canOpenSurface,
  estimate,
  extraOf,
  onAnswer = null,
}: {
  /** Who withheld these credits, in the words the application served. */
  heading: string;
  credits: readonly PublicModeloFormField[];
  /** The boxes the application works out from a credit, directly or through
   * another figure; null when it could not say which they are. */
  dependents: readonly PublicModeloFormField[] | null;
  lines: readonly ModeloFormIssueLine[];
  onGo(address: ModeloFormAddressV1): void;
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface(surface: OpenableSurface): boolean;
  /** The estimate's panel, drawn under the boxes. */
  estimate?: ReactNode;
  /** What the estimate says of one box, drawn under its words. */
  extraOf?: (field: PublicModeloFormField) => ReactNode;
  /** Opens the answer a disagreement's line offers, or null while none can
   * be sent from here. */
  onAnswer?: ((line: ModeloFormIssueLine) => void) | null;
}) {
  const t = useStrings();
  const linesOf = (field: PublicModeloFormField) =>
    lines.filter((line) => line.box !== null && line.box === field.box);
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading title={heading} lead={t("desktop.modelo.credits.lead")} />
      <section
        aria-label={t("desktop.modelo.credits.list")}
        className="flex flex-col gap-3"
      >
        <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
          {credits.map((field) => (
            <CreditRow
              key={addressKey(field.address)}
              field={field}
              lines={linesOf(field)}
              extra={extraOf?.(field)}
              onGo={onGo}
              onAnswer={onAnswer}
            />
          ))}
        </ul>
        {canOpenSurface("withholding") && (
          <Button
            variant="outline"
            className="self-start"
            data-open-surface="withholding"
            onClick={() => onOpenSurface("withholding")}
          >
            {t("workspace.modelo.surface.open.withholding")}
            <Icon name="forward" size="xs" />
          </Button>
        )}
      </section>
      {dependents === null && (
        <section
          aria-label={t("desktop.modelo.credits.dependents")}
          data-dependents="unknown"
          className="flex flex-col gap-2"
        >
          <h3 className="text-sm font-medium text-muted-foreground">
            {t("desktop.modelo.credits.dependents")}
          </h3>
          <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
            <Icon name="info" size="xs" className="mt-0.5 shrink-0" />
            {t("desktop.modelo.credits.dependents_unknown")}
          </p>
        </section>
      )}
      {dependents !== null && dependents.length > 0 && (
        <section
          aria-label={t("desktop.modelo.credits.dependents")}
          className="flex flex-col gap-2"
        >
          <h3 className="text-sm font-medium text-muted-foreground">
            {t("desktop.modelo.credits.dependents")}
          </h3>
          {[...credits, ...dependents].some((field) => !field.value_text) && (
            <p className="text-sm text-muted-foreground">
              {t("desktop.modelo.credits.dependents_lead")}
            </p>
          )}
          <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
            {dependents.map((field) => (
              <CreditRow
                key={addressKey(field.address)}
                field={field}
                lines={linesOf(field)}
                extra={extraOf?.(field)}
                onGo={onGo}
                onAnswer={onAnswer}
              />
            ))}
          </ul>
        </section>
      )}
      {estimate}
    </div>
  );
}
