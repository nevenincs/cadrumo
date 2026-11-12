import { useId, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/components/ui/cn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { facts, listed } from "../../../shell/compose";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type {
  ModeloFormTypingEffect,
  ModeloWorkbenchFormProjectionV1,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings, type Translate } from "../../../shell/strings";
import { BoxNumber } from "../form/BoxNumber";
import {
  addressKey,
  editKey,
  statementOf,
  type FormSession,
  type StagedEdit,
} from "../form/session";
import { stagedText } from "../form/stagedWords";
import { useEditReview, type ReviewPhase } from "./useEditReview";
import { ScopedWriteHoldNotice } from "../WriteScope";

// The review of every staged edit before anything is applied: each change
// with its box, how it read and how it will read, what the application's
// check found, and what applying does to values nobody is recorded as having
// typed. Apply runs once; an apply whose outcome was not seen is shown as
// unknown and is never sent again.

/** What a staged edit does to its box, in the read model's words: typing a
 * value says what it replaces; clearing and restoring say so. */
function effectWords(
  t: Translate,
  edit: StagedEdit,
  effect: ModeloFormTypingEffect | undefined,
): string | null {
  switch (edit.intent.kind) {
    case "clear_declared_value":
      return t("workspace.modelo.review.effect.clear");
    case "restore_source_value":
      return t(
        edit.intent.change === "remove"
          ? "workspace.modelo.review.effect.remove"
          : "workspace.modelo.review.effect.restore",
      );
    case "remove_override":
      return t("workspace.modelo.review.effect.restore");
    case "attest_no_amount":
      return edit.intent.effect;
    default:
      return effect?.words ?? null;
  }
}

/** Whether a staged value replaces a value a source or the calculation
 * gave, as the read model says of typing over its box. */
const displaces = (
  edit: StagedEdit,
  effect: ModeloFormTypingEffect | undefined,
) =>
  (edit.intent.kind === "set_typed_value" ||
    edit.intent.kind === "set_override_value") &&
  (effect?.displaces === "source" || effect?.displaces === "calculation");

/** Past this many boxes a list of their numbers stops helping. */
const NAMED_BOXES = 20;

/** The boxes holding values nobody is recorded as having typed, named. */
function unattributedText(t: Translate, session: FormSession) {
  const boxes = session.placed
    .filter(
      (p) => p.field.unattributed && !session.staged.has(editKey(p.field)),
    )
    .map((p) => p.field.box ?? p.field.label.text);
  if (!boxes.length)
    return t("workspace.modelo.review.operator_entries_unknown");
  const named =
    boxes.length <= NAMED_BOXES
      ? listed(t, boxes)
      : t("workspace.modelo.review.and_more", {
          shown: listed(t, boxes.slice(0, NAMED_BOXES), "plain"),
          count: boxes.length - NAMED_BOXES,
        });
  return t("workspace.modelo.review.operator_entries_at_risk", {
    count: boxes.length,
    boxes: named,
  });
}

function ChangeLine({
  edit,
  effect: typing,
  changed,
}: {
  edit: StagedEdit;
  effect: ModeloFormTypingEffect | undefined;
  changed: boolean;
}) {
  const t = useStrings();
  const effect = effectWords(t, edit, typing);
  const replaces = displaces(edit, typing);
  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 px-3 py-2">
      <BoxNumber box={edit.field.box} size="sm" />
      <span className="min-w-0 truncate text-base">
        {edit.field.label.text}
      </span>
      <span className="flex items-center gap-2 text-base tabular-nums">
        <span className="text-faint line-through">
          {edit.field.value_text ?? "—"}
        </span>
        <Icon name="forward" size="xs" className="text-faint" />
        <span>{stagedText(t, edit)}</span>
      </span>
      {(effect || changed) && (
        <>
          <span />
          <span
            className={cn(
              "col-span-2 flex items-center gap-1 text-xs",
              changed || replaces ? "text-warning" : "text-muted-foreground",
            )}
          >
            {changed ? (
              <Icon name="alert" size="xs" />
            ) : (
              replaces && <Icon name="swap" size="xs" />
            )}
            {facts(t, [
              effect,
              changed && t("workspace.modelo.review.before_changed"),
            ])}
          </span>
        </>
      )}
    </li>
  );
}

/** The staged edits as the review lists them: each edit on its own line,
 * and every box of one statement, or of one withdrawal, on one line at the
 * place of its first box. */
function lines(edits: readonly StagedEdit[]): StagedEdit[][] {
  const out: StagedEdit[][] = [];
  const grouped = new Map<string, StagedEdit[]>();
  for (const edit of edits) {
    const group = statementOf(edit.intent);
    const held = group ? grouped.get(group) : undefined;
    if (held) {
      held.push(edit);
      continue;
    }
    const line = [edit];
    if (group) grouped.set(group, line);
    out.push(line);
  }
  return out;
}

/** One statement or one withdrawal of it, on every box it covers: the boxes,
 * what the statement says in the form's words, and what staging it does. */
function StatementLine({
  edits,
  changed,
}: {
  edits: StagedEdit[];
  changed: boolean;
}) {
  const t = useStrings();
  const first = edits[0];
  if (!first) return null;
  const { intent } = first;
  const words =
    intent.kind === "attest_no_amount"
      ? intent.words
      : (first.field.origin_words ?? first.field.label.text);
  const effect = intent.kind === "attest_no_amount" ? intent.effect : null;
  return (
    <li
      data-statement-line=""
      className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 gap-y-0.5 px-3 py-2"
    >
      <span className="flex max-w-32 flex-wrap gap-1">
        {edits.map((edit) => (
          <BoxNumber key={edit.key} box={edit.field.box} size="sm" />
        ))}
      </span>
      <span className="min-w-0 text-base">{words}</span>
      <span className="text-base">
        {intent.kind === "attest_no_amount" ? null : stagedText(t, first)}
      </span>
      {(effect || changed) && (
        <>
          <span />
          <span
            className={cn(
              "col-span-2 flex items-center gap-1 text-xs",
              changed ? "text-warning" : "text-muted-foreground",
            )}
          >
            {changed && <Icon name="alert" size="xs" />}
            {facts(t, [
              effect,
              changed && t("workspace.modelo.review.before_changed"),
            ])}
          </span>
        </>
      )}
    </li>
  );
}

function PhaseNotice({ phase }: { phase: ReviewPhase }) {
  const t = useStrings();
  switch (phase.kind) {
    case "checking":
    case "applying":
      return (
        <span className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          {t(
            phase.kind === "checking"
              ? "workspace.modelo.review.checking"
              : "workspace.modelo.review.applying",
          )}
        </span>
      );
    case "check_failed":
      return (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("workspace.modelo.review.check_failed")}
        </Alert>
      );
    case "refused":
      return (
        <Alert tone="danger" icon={<Icon name="refused" />}>
          {phase.words ?? t("workspace.modelo.review.check_failed")}
        </Alert>
      );
    case "not_applied":
      return (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {phase.words ?? t("workspace.modelo.operation.not_done")}
        </Alert>
      );
    case "still_moving":
      return (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("workspace.modelo.rebase.still_moving")}
        </Alert>
      );
    case "unknown":
      return null;
    case "applied":
      return (
        <Alert tone="success" icon={<Icon name="check" />}>
          {t("workspace.modelo.operation.done")}
        </Alert>
      );
    case "checked":
      return null;
  }
}

/**
 * The review and apply of the edits staged on the form. The workspace opens
 * it; `onReread` reads the declaration again, after an apply settles, after
 * a stale baseline is renewed and when the filer asks after an unknown
 * outcome.
 */
export function ReviewDialog({
  open,
  onOpenChange,
  envelope,
  session,
  port,
  language,
  onReread,
  onPrerequisiteHeld,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  port: ModeloPort;
  /** The window's language, in which the check's findings are said. */
  language: OutputLanguage;
  onReread: () => Promise<boolean>;
  /** Whether a refused apply's prerequisite still stands, for the header's
   * next step; only this dialog sees that refusal. */
  onPrerequisiteHeld?: (held: boolean) => void;
}) {
  const t = useStrings();
  const ackId = useId();
  const [acknowledged, setAcknowledged] = useState(false);
  const {
    phase,
    apply,
    recheck,
    prerequisite,
    blocked: writeHeld,
  } = useEditReview({
    open,
    envelope,
    session,
    port,
    language,
    onReread,
    onPrerequisiteHeld,
  });
  const form = envelope.form.form;
  const effects = new Map(
    envelope.typing_effects.map((effect) => [
      addressKey(effect.address),
      effect,
    ]),
  );
  const effectOf = (edit: StagedEdit) =>
    effects.get(addressKey(edit.field.address));
  const replacing = (edit: StagedEdit) => displaces(edit, effectOf(edit));
  const edits = [...session.staged.values()].sort(
    (a, b) => Number(replacing(b)) - Number(replacing(a)),
  );
  // A box that changed under its edit when the baseline was renewed is
  // marked until the filer applies, having looked at it again.
  const changed = new Set(
    edits.filter((edit) => edit.beforeChanged).map((edit) => edit.key),
  );
  const rebased = session.rebased;
  const displacing = edits.filter(replacing).length;
  const findings = phase.kind === "checked" ? phase.findings : [];
  const blocked = findings.some((finding) => finding.blocking);
  // The check says it for the edits as sent; until it answers, the form.
  const entriesUnknown =
    phase.kind === "checked"
      ? phase.operatorEntriesUnknown
      : !form.operator_entries_known;
  const mustAcknowledge = entriesUnknown || changed.size > 0;
  const busy = phase.kind === "checking" || phase.kind === "applying";
  // A renewal's report not yet applied leaves the marks unknown: nothing is
  // applied until the declaration it waits for is read.
  const mayApply =
    !writeHeld &&
    phase.kind === "checked" &&
    !session.rebasePending &&
    edits.length > 0 &&
    !blocked &&
    (acknowledged || !mustAcknowledge);
  const close = (next: boolean) => {
    if (busy && !next) return;
    if (!next) setAcknowledged(false);
    onOpenChange(next);
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent
        className="w-palette"
        closeLabel={t("workspace.modelo.key.close")}
      >
        <DialogHeader>
          <DialogTitle>
            {t("workspace.modelo.review.title", { count: edits.length })}
          </DialogTitle>
          <DialogDescription>
            {t("workspace.modelo.review.nothing_saved")}
          </DialogDescription>
        </DialogHeader>
        {edits.length > 0 ? (
          <ul className="flex max-h-[50vh] flex-col divide-y divide-border overflow-y-auto rounded-lg border border-border">
            {lines(edits).map((line) =>
              line.length === 1 && line[0] ? (
                <ChangeLine
                  key={line[0].key}
                  edit={line[0]}
                  effect={effectOf(line[0])}
                  changed={changed.has(line[0].key)}
                />
              ) : (
                <StatementLine
                  key={line.map((edit) => edit.key).join()}
                  edits={line}
                  changed={line.some((edit) => changed.has(edit.key))}
                />
              ),
            )}
          </ul>
        ) : (
          phase.kind !== "applied" && (
            <p className="text-base text-muted-foreground">
              {t("workspace.modelo.review.none")}
            </p>
          )
        )}
        {displacing > 0 && (
          <Alert tone="warning" icon={<Icon name="swap" />}>
            {t("workspace.modelo.review.displacing", { count: displacing })}
          </Alert>
        )}
        {rebased && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {[
              t("workspace.modelo.rebase.moved"),
              rebased.changed > 0 &&
                t("workspace.modelo.rebase.changed", {
                  count: rebased.changed,
                }),
              rebased.dropped > 0 &&
                t("workspace.modelo.rebase.dropped", {
                  count: rebased.dropped,
                }),
            ]
              .filter(Boolean)
              .join(" ")}
          </Alert>
        )}
        {entriesUnknown && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {unattributedText(t, session)}
          </Alert>
        )}
        {findings.length > 0 && (
          <section
            aria-label={t("workspace.modelo.review.findings_heading")}
            className="flex flex-col gap-1"
          >
            <h3 className="text-sm font-medium text-muted-foreground">
              {t("workspace.modelo.review.findings_heading")}
            </h3>
            <ul className="flex flex-col gap-1">
              {findings.map((finding, i) => {
                const field = finding.address
                  ? session.fieldAt(finding.address)
                  : null;
                const error = finding.blocking;
                return (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <Icon
                      name={error ? "refused" : "info"}
                      size="xs"
                      className={cn(
                        "mt-0.5",
                        error ? "text-destructive" : "text-muted-foreground",
                      )}
                    />
                    {field && <BoxNumber box={field.box} size="sm" />}
                    <span>{finding.words}</span>
                  </li>
                );
              })}
            </ul>
            {blocked && (
              <p className="text-sm text-destructive">
                {t("workspace.modelo.review.blocked")}
              </p>
            )}
          </section>
        )}
        {prerequisite && (
          <Alert tone="danger" icon={<Icon name="refused" />}>
            <span className="flex flex-col items-start gap-1">
              <span className="flex items-center gap-2">
                <BoxNumber box={prerequisite.field.box} size="sm" />
                {prerequisite.field.label.text}
              </span>
              {prerequisite.words?.split("\n").map((line, i) => (
                <span key={i}>{line}</span>
              ))}
              <Button
                size="xs"
                variant="link"
                className="p-0"
                onClick={() => {
                  session.selectAddress(prerequisite.field.address);
                  close(false);
                }}
              >
                {t("workspace.modelo.apply_prerequisite.action")}
              </Button>
            </span>
          </Alert>
        )}
        <PhaseNotice phase={phase} />
        <ScopedWriteHoldNotice />
        {mustAcknowledge && phase.kind === "checked" && !blocked && (
          <label
            htmlFor={ackId}
            className="flex items-center gap-2 text-base text-foreground"
          >
            <Checkbox
              id={ackId}
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            {t("workspace.modelo.review.acknowledge")}
          </label>
        )}
        <DialogFooter>
          <span className="mr-auto text-sm text-muted-foreground">
            {t("workspace.modelo.filing.kept_locally")}
          </span>
          {phase.kind === "applied" ? (
            <Button onClick={() => close(false)}>
              {t("workspace.modelo.key.close")}
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => close(false)}
              >
                {t("workspace.modelo.review.back")}
              </Button>
              <Button
                variant="ghost"
                className="text-destructive"
                disabled={busy || edits.length === 0}
                onClick={() => {
                  session.discardAll();
                  close(false);
                }}
              >
                {t("workspace.modelo.review.discard")}
              </Button>
              {phase.kind === "check_failed" ||
              phase.kind === "not_applied" ||
              phase.kind === "still_moving" ? (
                <Button disabled={writeHeld} onClick={recheck}>
                  {t("workspace.modelo.review.check_again")}
                </Button>
              ) : (
                <Button
                  disabled={!mayApply}
                  onClick={() => {
                    // Applying is the filer's word that the marked boxes
                    // were looked at again.
                    session.acknowledge();
                    void apply();
                  }}
                >
                  {t("workspace.modelo.review.apply")}
                </Button>
              )}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
