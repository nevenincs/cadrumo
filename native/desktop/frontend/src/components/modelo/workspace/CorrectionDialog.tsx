import { useId, useState, type ReactNode } from "react";
import { TextEditor } from "@/components/editors/TextEditor";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { facts } from "../../../shell/compose";
import type {
  CalculationRevisionAmendmentKind,
  M303RectificativaMotive,
  ModeloAmendmentCorrectionContextV1,
  ModeloAmendmentCorrectionRowV1,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import { BoxNumber } from "../form/BoxNumber";

/** The person's answer to a correction: the kind, the motive where it
 * applies, the reason, and each corrected box's text as typed, which the
 * application reads. */
export type CorrectionAnswer = {
  kind: CalculationRevisionAmendmentKind;
  motive: M303RectificativaMotive | null;
  reason: string;
  entries: { row: ModeloAmendmentCorrectionRowV1; lexeme: string }[];
};

/** What sending a correction came to. `done` committed it, whether or not
 * its answer was read; `entries` names, by casilla, each figure the
 * application could not read; `said` carries the application's own words for
 * a refusal; `refused` settled without changing anything; `not_sent` never
 * reached the runtime; `unknown` may have committed and is never sent again
 * until the declaration is read again. */
export type CorrectionResult =
  | { kind: "done" }
  | { kind: "entries"; entries: Record<string, string> }
  | { kind: "said"; words: string }
  | { kind: "refused"; code: string }
  | { kind: "not_sent"; code: string }
  | { kind: "unknown" };

/** One labelled control. */
export function Labelled({
  label,
  children,
}: {
  label: string;
  children: (id: string) => ReactNode;
}) {
  const id = useId();
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children(id)}
    </Field>
  );
}

/**
 * Prepares a correction of a declaration recorded as filed, on what the
 * application offers for it: the kinds the period permits, the motive where
 * the chosen kind states one, and the filed boxes with their filed figures.
 * Corrected figures are sent as typed; the application reads them.
 */
export function CorrectionDialog({
  open,
  onOpenChange,
  context,
  onCorrect,
}: {
  open: boolean;
  onOpenChange(open: boolean): void;
  /** Null while it is being read or cannot be. */
  context: ModeloAmendmentCorrectionContextV1 | null;
  /** Null while the correction cannot be sent from here. */
  onCorrect: ((answer: CorrectionAnswer) => Promise<CorrectionResult>) | null;
}) {
  const t = useStrings();
  const [kind, setKind] = useState<CalculationRevisionAmendmentKind | null>(
    null,
  );
  const [motive, setMotive] = useState<M303RectificativaMotive | null>(null);
  const [reason, setReason] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [refusals, setRefusals] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<CorrectionResult | null>(null);
  const ids = useId();
  const chosen = kind ?? context?.kinds[0]?.kind ?? null;
  const help = context?.kinds.find((option) => option.kind === chosen)?.help;
  // The motive is asked only for the kind the application says states one.
  const asksMotive =
    context !== null &&
    context.motive_applies &&
    chosen !== null &&
    chosen === context.motive_kind;
  const entries = (context?.rows ?? []).flatMap((row) => {
    const lexeme = values[row.casilla_id]?.trim();
    return lexeme ? [{ row, lexeme }] : [];
  });
  const ready =
    onCorrect !== null &&
    chosen !== null &&
    reason.trim() !== "" &&
    entries.length > 0 &&
    (!asksMotive || motive !== null);
  const submit = async () => {
    if (!ready || !onCorrect || !chosen) return;
    setBusy(true);
    const result = await onCorrect({
      kind: chosen,
      motive: asksMotive ? motive : null,
      reason: reason.trim(),
      entries,
    });
    setBusy(false);
    if (result.kind === "done") onOpenChange(false);
    else if (result.kind === "entries") setRefusals(result.entries);
    setOutcome(result);
  };
  // An outcome nobody saw may have committed: the dialog sends nothing more.
  const held = outcome?.kind === "unknown";
  const said =
    outcome === null
      ? null
      : outcome.kind === "said"
        ? outcome.words
        : outcome.kind === "refused"
          ? t("workspace.modelo.outcome.refused")
          : outcome.kind === "not_sent"
            ? t("workspace.modelo.outcome.failed")
            : outcome.kind === "unknown"
              ? t("workspace.modelo.outcome.unknown")
              : null;
  const type = (casillaId: string, text: string) => {
    setValues((held) => ({ ...held, [casillaId]: text }));
    setRefusals((held) => {
      const rest = { ...held };
      delete rest[casillaId];
      return rest;
    });
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-palette"
        closeLabel={t("workspace.modelo.key.close")}
      >
        <DialogHeader>
          <DialogTitle>{t("workspace.modelo.correction.title")}</DialogTitle>
          <DialogDescription>
            {t("workspace.modelo.correction.lead")}
          </DialogDescription>
        </DialogHeader>
        {context && (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              {facts(t, [
                context.filed.modelo_title,
                context.filed.period_words,
                context.filed.declaration_kind_words,
                context.filed.filed_on,
              ])}
            </p>
            <Field>
              <FieldLabel id={`${ids}-kind`}>
                {t("desktop.modelo.correction.kind_label")}
              </FieldLabel>
              <SegmentedControl
                aria-labelledby={`${ids}-kind`}
                value={chosen ?? ""}
                onValueChange={(v) =>
                  setKind(v as CalculationRevisionAmendmentKind)
                }
              >
                {context.kinds.map((option) => (
                  <SegmentedControlItem key={option.kind} value={option.kind}>
                    {option.words}
                  </SegmentedControlItem>
                ))}
              </SegmentedControl>
              {help && <FieldDescription>{help}</FieldDescription>}
            </Field>
            {asksMotive && (
              <Field>
                <FieldLabel id={`${ids}-motive`}>
                  {t("desktop.modelo.correction.motive_label")}
                </FieldLabel>
                <SegmentedControl
                  aria-labelledby={`${ids}-motive`}
                  value={motive ?? ""}
                  onValueChange={(v) => setMotive(v as M303RectificativaMotive)}
                >
                  {context.motives.map((option) => (
                    <SegmentedControlItem
                      key={option.motive}
                      value={option.motive}
                    >
                      {option.words}
                    </SegmentedControlItem>
                  ))}
                </SegmentedControl>
                {context.motive_help && (
                  <FieldDescription>{context.motive_help}</FieldDescription>
                )}
              </Field>
            )}
            <Labelled label={context.reason_prompt}>
              {(id) => (
                <TextEditor id={id} value={reason} onChange={setReason} />
              )}
            </Labelled>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">
                {t("desktop.modelo.correction.values_label")}
              </span>
              <ul className="flex max-h-72 flex-col divide-y divide-border overflow-y-auto rounded-lg border border-border">
                {context.rows.map((row) => {
                  const refused = refusals[row.casilla_id];
                  return (
                    <li
                      key={row.casilla_id}
                      className="grid grid-cols-[auto_minmax(0,1fr)_auto_--spacing(36)] items-center gap-x-3 gap-y-1 px-3 py-1.5"
                    >
                      <BoxNumber box={row.box} size="sm" />
                      <span
                        className="truncate text-base"
                        title={row.help ?? undefined}
                      >
                        {row.label}
                      </span>
                      <span className="text-sm text-muted-foreground tabular-nums">
                        {row.filed_value_text}
                      </span>
                      <Input
                        controlSize="sm"
                        aria-invalid={refused ? true : undefined}
                        aria-label={t(
                          "workspace.modelo.editor.new_value_for_box",
                          { box: row.box ?? row.label },
                        )}
                        value={values[row.casilla_id] ?? ""}
                        onChange={(e) => type(row.casilla_id, e.target.value)}
                      />
                      {refused && (
                        <span className="col-span-4 text-sm text-destructive">
                          {refused}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        )}
        {said && (
          <Alert
            tone={held ? "danger" : "warning"}
            role="alert"
            icon={<Icon name={held ? "unknown" : "alert"} />}
          >
            {said}
          </Alert>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t("workspace.modelo.editor.cancel")}
          </Button>
          <Button disabled={!ready || busy || held} onClick={submit}>
            {t("workspace.modelo.correction.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
