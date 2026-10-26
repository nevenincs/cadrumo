import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon, type IconName } from "@/components/ui/icon";
import { BoxNumber } from "./FormView";
import {
  ARTEFACTS,
  type AeatSide,
  type HistoryEvent,
  type SourceGroup,
} from "./scenarios";
import type { Attention, FormIssue, ModeloForm } from "./types";
import {
  FAMILY_ICON,
  familyWords,
  money,
  timeWords,
  TONE_TEXT,
  type Tone,
} from "./vocabulary";
import { w } from "./words";

// The views beside the form: what the check found, the file and the filing,
// where values come from, and what happened to the declaration. Each reads
// the application's own state; none decides anything itself.

function Heading({ title, lead }: { title: string; lead?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="font-serif text-lg text-foreground">{title}</h2>
      {lead && <p className="text-base text-muted-foreground">{lead}</p>}
    </div>
  );
}

const LEVELS: { level: Attention; tone: Tone }[] = [
  { level: "blocks", tone: "danger" },
  { level: "missing", tone: "danger" },
  { level: "confirm", tone: "attention" },
  { level: "check", tone: "source" },
  { level: "info", tone: "quiet" },
];

/** Finding facts as a reader says them: a period code in words. */
export const stoppingIssues = (issues: FormIssue[]) =>
  issues.filter((i) => ["blocks", "missing", "confirm"].includes(i.attention));

export function CheckView({
  form,
  locale,
  onGo,
}: {
  form: ModeloForm;
  locale: string;
  onGo: (box: string) => void;
}) {
  const verdict = form.verification;
  const stop = stoppingIssues(form.issues).length;
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading
        title={w("workspace.modelo.issues.title", locale)}
        lead={
          verdict
            ? w(`workspace.modelo.issues.verdict.${verdict}`, locale)
            : w("workspace.modelo.issues.verdict.none", locale)
        }
      />
      {verdict === "complete" && stop === 0 && (
        <Alert tone="success" icon={<Icon name="check" />}>
          {w("workspace.modelo.operation.checked.complete", locale)}
        </Alert>
      )}
      {LEVELS.map(({ level, tone }) => {
        const word = w(`workspace.modelo.level.${level}`, locale);
        const found = form.issues.filter((i) => i.attention === level);
        if (!found.length) return null;
        return (
          <section
            key={level}
            aria-label={word}
            className="flex flex-col gap-2"
          >
            <h3 className={cn("text-sm font-medium", TONE_TEXT[tone])}>
              {word}
            </h3>
            <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
              {found.map((issue, i) => {
                const body = (
                  <>
                    <span className="flex flex-col gap-1">
                      <span className="text-base text-foreground">
                        {(issue.words[locale] ?? issue.words.en)?.message}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {(issue.words[locale] ?? issue.words.en)?.action}
                      </span>
                    </span>
                    {issue.box && (
                      <Icon name="forward" size="xs" className="text-faint" />
                    )}
                  </>
                );
                return (
                  <li key={i}>
                    {issue.box ? (
                      <button
                        type="button"
                        onClick={() => onGo(issue.box!)}
                        className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 text-left hover:bg-accent"
                      >
                        <BoxNumber box={issue.box} />
                        {body}
                      </button>
                    ) : (
                      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 px-4 py-3">
                        {body}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

type Stage = {
  word: string;
  when: string;
  detail: string;
  state: "done" | "stale" | "open";
};

const STAGE_ICON: Record<Stage["state"], IconName> = {
  done: "check",
  stale: "alert",
  open: "clock",
};
const STAGE_TONE: Record<Stage["state"], string> = {
  done: "text-success",
  stale: "text-warning",
  open: "text-faint",
};

const aeatWords = (state: AeatSide["state"], locale: string) =>
  w(`workspace.declarations.calendar.aeat.${state}`, locale);

/** Why an action cannot be taken yet, in the product's words, or null. */
export function exportBlock(form: ModeloForm, locale: string): string | null {
  const hint = (key: string, values: Record<string, string | number> = {}) =>
    w(`workspace.modelo.export.${key}`, locale, values).replace(
      /\s*\[.*?\]/g,
      "",
    );
  const stop = stoppingIssues(form.issues).length;
  const notes = form.calculation_notes.filter(
    (n) => n.attention === "blocks",
  ).length;
  if (stop || notes) return hint("resolve_first", { count: stop + notes });
  if (form.counts.default_to_confirm)
    return hint("confirm_first", { count: form.counts.default_to_confirm });
  if (form.verification !== "complete") return hint("verify_first");
  return null;
}

export function FilingView({
  form,
  aeat,
  locale,
  onCheck,
}: {
  form: ModeloForm;
  aeat: AeatSide | null;
  locale: string;
  onCheck: () => void;
}) {
  const blocked = exportBlock(form, locale);
  const file = form.last_export;
  const recorded = form.filing;
  const result = form.result;
  const stages: Stage[] = [
    {
      word: w("workspace.modelo.origin.calculated", locale),
      when: form.calculation_revision_id
        ? w("workspace.modelo.legend.name.done", locale)
        : w("workspace.modelo.filing.not_yet", locale),
      detail:
        result?.value && result.direction !== "unknown"
          ? `${money(result.value, locale)} · ${w(
              result.direction === "to_pay"
                ? "workspace.modelo.header.result.to_pay"
                : "workspace.modelo.header.result.unknown",
              locale,
            )}`
          : w("workspace.modelo.header.own_calculation", locale),
      state: form.calculation_revision_id ? "done" : "open",
    },
    {
      word: w("workspace.modelo.filing.file_exported", locale),
      when: file
        ? timeWords(file.exported_at, locale)
        : w("workspace.modelo.filing.not_yet", locale),
      detail: file
        ? file.current
          ? w("workspace.modelo.filing.file_current", locale)
          : w("workspace.modelo.filing.file_earlier", locale)
        : w("workspace.modelo.filing.file_local", locale),
      state: file ? (file.current ? "done" : "stale") : "open",
    },
    {
      word: w("workspace.declarations.list.group.recorded", locale),
      when: recorded?.recorded_at
        ? timeWords(recorded.recorded_at, locale)
        : w("workspace.modelo.filing.not_yet", locale),
      detail: recorded
        ? w("workspace.modelo.filing.recorded_here", locale)
        : w("workspace.modelo.filing.after_filing", locale),
      state: recorded ? "done" : "open",
    },
    {
      word: w("workspace.modelo.filing.at_aeat", locale),
      when: aeat?.on
        ? timeWords(aeat.on, locale)
        : recorded
          ? w("workspace.modelo.filing.not_confirmed_yet", locale)
          : "—",
      detail: aeat
        ? aeatWords(aeat.state, locale)
        : w("workspace.modelo.filing.add_receipt_to_confirm", locale),
      state: aeat?.state === "justificante_verified" ? "done" : "open",
    },
  ];
  const canRecord = form.verification === "complete" && !blocked && !recorded;
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading
        title={w("workspace.modelo.filing.title", locale)}
        lead={w("workspace.modelo.filing.lead", locale)}
      />
      <ol className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border @3xl:grid-cols-4">
        {stages.map((s) => (
          <li key={s.word} className="flex flex-col gap-1 bg-card px-4 py-3">
            <span className="flex items-center gap-1.5 text-sm font-medium">
              <Icon
                name={STAGE_ICON[s.state]}
                size="xs"
                className={STAGE_TONE[s.state]}
              />
              {s.word}
            </span>
            <span className="text-sm text-muted-foreground">{s.when}</span>
            <span className="text-xs text-faint">{s.detail}</span>
          </li>
        ))}
      </ol>

      <section className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5">
        <div className="flex items-start gap-3">
          <Icon
            name="page"
            size="lg"
            className="mt-0.5 text-muted-foreground"
          />
          <div className="flex flex-1 flex-col gap-1">
            <h3 className="text-md font-medium">
              {w("workspace.modelo.filing.file_title", locale)}
            </h3>
            <p className="text-base text-muted-foreground">
              {w("workspace.modelo.filing.file_format", locale, {
                modelo: form.modelo,
              })}
            </p>
          </div>
        </div>
        {blocked && !recorded && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            <span>{blocked}</span>
            <Button
              size="xs"
              variant="link"
              className="justify-self-start"
              onClick={onCheck}
            >
              {w("workspace.modelo.filing.open_check", locale)}
            </Button>
          </Alert>
        )}
        {file && !file.current && !recorded && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {w("workspace.modelo.header.file_out_of_date", locale, {
              date: timeWords(file.exported_at, locale),
            })}
          </Alert>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {recorded ? (
            <>
              <Button variant="ghost" size="sm">
                <Icon name="folder" size="xs" />
                {w("workspace.modelo.filing.show_filed_file", locale)}
              </Button>
              <span className="text-sm text-muted-foreground">
                {w("workspace.modelo.filing.export_again_warning", locale)}
              </span>
            </>
          ) : (
            <>
              <Button
                disabled={!!blocked}
                variant={file?.current ? "secondary" : "primary"}
              >
                <Icon name="download" size="xs" />
                {file
                  ? w("workspace.modelo.filing.export_again", locale)
                  : w("workspace.modelo.filing.export_file", locale)}
              </Button>
              {file?.current && (
                <Button variant="ghost">
                  <Icon name="folder" size="xs" />
                  {w("workspace.modelo.filing.show_in_folder", locale)}
                </Button>
              )}
            </>
          )}
          <Button variant="link" className="ml-auto">
            {w("workspace.modelo.filing.how_to_upload", locale)}
            <Icon name="forward" size="xs" />
          </Button>
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5">
        <div className="flex items-start gap-3">
          <Icon
            name="tick"
            size="lg"
            className="mt-0.5 text-muted-foreground"
          />
          <div className="flex flex-1 flex-col gap-1">
            <h3 className="text-md font-medium">
              {w("workspace.modelo.filing.after_filed_title", locale)}
            </h3>
            <p className="text-base text-muted-foreground">
              {w("workspace.modelo.filing.record_lead", locale)}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!recorded && (
            <Button variant="secondary" disabled={!canRecord}>
              {w("workspace.modelo.filing.record_as_filed", locale)}
            </Button>
          )}
          <Button
            variant="outline"
            disabled={!recorded || aeat?.state === "justificante_verified"}
          >
            <Icon name="paste" size="xs" />
            {w("workspace.modelo.filing.add_receipt_pdf", locale)}
          </Button>
          <span className="text-sm text-muted-foreground">
            {!recorded
              ? canRecord
                ? w("workspace.modelo.filing.also_other_way", locale)
                : w("workspace.modelo.filing.check_first", locale)
              : aeat?.state === "justificante_verified"
                ? w("workspace.modelo.filing.receipt_matches", locale)
                : w("workspace.modelo.filing.receipt_missing", locale)}
          </span>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-muted-foreground">
          {w("workspace.modelo.filing.other_copies", locale)}
        </h3>
        <ul className="grid grid-cols-1 gap-3 @3xl:grid-cols-2">
          {ARTEFACTS.map((a) => (
            <li
              key={a.id}
              className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4"
            >
              <div className="flex items-center gap-2">
                <Icon name={a.icon} className="text-muted-foreground" />
                <span className="text-base font-medium">{a.title}</span>
              </div>
              <p className="text-sm text-muted-foreground">{a.detail}</p>
              {a.leaves && <p className="text-xs text-warning">{a.leaves}</p>}
              <div className="mt-auto flex items-center gap-2 pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={form.verification !== "complete"}
                >
                  {a.action}
                </Button>
                {a.needs && (
                  <span className="text-xs text-faint">{a.needs}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

const SOURCE_TONE = {
  ready: "text-success",
  partial: "text-warning",
  missing: "text-destructive",
};

export function SourcesView({
  groups,
  locale,
  onGo,
}: {
  groups: SourceGroup[];
  locale: string;
  onGo: (box: string) => void;
}) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading
        title={w("workspace.modelo.sources.title", locale)}
        lead={w("workspace.modelo.sources.lead", locale)}
      />
      {groups.map((g) => (
        <section
          key={g.family}
          className="flex flex-col gap-2 rounded-xl border border-border bg-card p-5"
        >
          <div className="flex flex-wrap items-center gap-3">
            <Icon
              name={FAMILY_ICON[g.family]}
              size="md"
              className="text-muted-foreground"
            />
            <h3 className="text-md font-medium">
              {familyWords(g.family, locale)}
            </h3>
            <span className={cn("text-sm", SOURCE_TONE[g.state])}>
              {g.stateWords}
            </span>
            {g.open && (
              <Button size="sm" variant="link" className="ml-auto">
                {g.open}
                <Icon name="forward" size="xs" />
              </Button>
            )}
          </div>
          <ul className="flex flex-col divide-y divide-border">
            {g.lines.map((l) => (
              <li
                key={l.name}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 py-2"
              >
                <div className="flex flex-col">
                  <span className="flex items-center gap-1.5 text-base">
                    {l.state === "missing" && (
                      <Icon name="alert" size="xs" className="text-warning" />
                    )}
                    {l.name}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {l.detail}
                  </span>
                </div>
                <span className="flex gap-1">
                  {l.boxes.map((b) => (
                    <button
                      key={b}
                      type="button"
                      onClick={() => onGo(b)}
                      aria-label={w(
                        "workspace.modelo.sources.go_to_box",
                        locale,
                        {
                          box: b,
                        },
                      )}
                    >
                      <BoxNumber box={b} size="sm" />
                    </button>
                  ))}
                </span>
              </li>
            ))}
          </ul>
          {g.bring && (
            <Button size="sm" variant="outline" className="self-start">
              <Icon name="download" size="xs" />
              {g.bring}
            </Button>
          )}
        </section>
      ))}
    </div>
  );
}

const KIND_ICON: Record<HistoryEvent["kind"], IconName> = {
  created: "plus",
  calculated: "sync",
  changed: "edit",
  verified: "check",
  exported: "download",
  filed: "tick",
  amended: "swap",
};

export function HistoryView({
  events,
  form,
  aeat,
  locale,
  correcting,
  onCorrect,
}: {
  events: HistoryEvent[];
  form: ModeloForm;
  aeat: AeatSide | null;
  locale: string;
  correcting: boolean;
  onCorrect: (open: boolean) => void;
}) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading
        title={w("workspace.modelo.history.title", locale)}
        lead={w("workspace.modelo.history.lead", locale)}
      />
      <ol className="flex flex-col">
        {aeat?.on && (
          <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-3 pb-4">
            <span className="flex size-control-sm items-center justify-center rounded-full bg-secondary text-success">
              <Icon name="shield" size="xs" />
            </span>
            <span className="flex flex-col">
              <span className="text-base">{aeatWords(aeat.state, locale)}</span>
              <span className="text-sm text-muted-foreground">
                {w("workspace.modelo.history.read_from_aeat", locale)}
              </span>
            </span>
            <span className="text-sm text-faint tabular-nums">
              {timeWords(aeat.on, locale)}
            </span>
          </li>
        )}
        {events.map((e, i) => (
          <li
            key={i}
            className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-3 pb-4"
          >
            <span className="flex size-control-sm items-center justify-center rounded-full bg-secondary text-muted-foreground">
              <Icon name={KIND_ICON[e.kind]} size="xs" />
            </span>
            <span className="flex flex-col">
              <span className="text-base">
                {e.kind === "changed"
                  ? w("workspace.modelo.history.changes_applied", locale)
                  : w(`workspace.declarations.lifecycle.${e.kind}`, locale)}
              </span>
              <span className="text-sm text-muted-foreground">
                {e.amount
                  ? `${money(e.amount, locale)} · ${w("workspace.modelo.header.result.to_pay", locale)}`
                  : e.detail}
              </span>
            </span>
            <span className="text-sm text-faint tabular-nums">
              {timeWords(e.at, locale)}
            </span>
          </li>
        ))}
      </ol>
      <div className="flex gap-2 border-t border-border pt-4">
        <Button variant="ghost" size="sm">
          <Icon name="edit" size="xs" />
          {w("workspace.modelo.history.rename", locale)}
        </Button>
        {!form.edit_closure && (
          <Button variant="ghost" size="sm" className="text-destructive">
            <Icon name="trash" size="xs" />
            {w("workspace.modelo.history.discard", locale)}
          </Button>
        )}
      </div>
      <Dialog open={correcting} onOpenChange={onCorrect}>
        <DialogContent closeLabel={w("workspace.modelo.key.close", locale)}>
          <DialogHeader>
            <DialogTitle>
              {w("workspace.modelo.correction.title", locale)}
            </DialogTitle>
            <DialogDescription>
              {w("workspace.modelo.correction.lead", locale)}
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {w("workspace.modelo.correction.kind", locale)}
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => onCorrect(false)}>
              {w("workspace.modelo.editor.cancel", locale)}
            </Button>
            <Button onClick={() => onCorrect(false)}>
              {w("workspace.modelo.correction.confirm", locale)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
