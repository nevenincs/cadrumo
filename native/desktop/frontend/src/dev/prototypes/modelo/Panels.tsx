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
  periodWords,
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

const LEVELS: { level: Attention; word: string; tone: Tone }[] = [
  { level: "blocks", word: "Must be fixed before filing", tone: "danger" },
  { level: "missing", word: "Missing", tone: "danger" },
  { level: "confirm", word: "To confirm", tone: "attention" },
  { level: "check", word: "Worth checking", tone: "source" },
  { level: "info", word: "For your information", tone: "quiet" },
];

/** Finding facts as a reader says them: a period code in words. */
function factWords(
  facts: Record<string, string | number>,
  locale: string,
): Record<string, string | number> {
  const out: Record<string, string | number> = { ...facts };
  for (const [key, value] of Object.entries(facts))
    if (key.endsWith("period") && typeof value === "string")
      out[key] = periodWords(value, 0, locale).replace(/\s*0$/, "");
  return out;
}

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
        title={w("tui.modelo.workbench.issues.title", locale)}
        lead={
          verdict
            ? w(`tui.modelo.workbench.issues.verdict.${verdict}`, locale)
            : w("tui.modelo.workbench.issues.verdict.none", locale)
        }
      />
      {verdict === "complete" && stop === 0 && (
        <Alert tone="success" icon={<Icon name="check" />}>
          {w("tui.modelo.workbench.operation.checked.complete", locale)}
        </Alert>
      )}
      {LEVELS.map(({ level, word, tone }) => {
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
                        {w(
                          issue.finding.message_locale_key,
                          locale,
                          factWords(issue.finding.message_facts, locale),
                        )}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {w(issue.action_locale_key, locale)}
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
  w(`tui.declarations.calendar.aeat.${state}`, locale);

/** Why an action cannot be taken yet, in the product's words, or null. */
export function exportBlock(form: ModeloForm, locale: string): string | null {
  const hint = (key: string, values: Record<string, string | number> = {}) =>
    w(`tui.modelo.workbench.export.${key}`, locale, values).replace(
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
      word: "Calculated",
      when: form.calculation_revision_id ? "Done" : "Not yet",
      detail:
        result?.value && result.direction !== "unknown"
          ? `${money(result.value, locale)} · ${result.direction === "to_pay" ? "to pay" : "result"}`
          : "Cadrumo's calculation; the AEAT has not seen it",
      state: form.calculation_revision_id ? "done" : "open",
    },
    {
      word: "File exported",
      when: file ? timeWords(file.exported_at, locale) : "Not yet",
      detail: file
        ? file.current
          ? "Made from the current calculation"
          : "Made from an earlier calculation: do not upload it"
        : "Made on this computer only",
      state: file ? (file.current ? "done" : "stale") : "open",
    },
    {
      word: "Recorded as filed",
      when: recorded?.recorded_at
        ? timeWords(recorded.recorded_at, locale)
        : "Not yet",
      detail: recorded
        ? "Recorded here; nothing was sent from Cadrumo"
        : "After you have filed at the AEAT",
      state: recorded ? "done" : "open",
    },
    {
      word: "At the AEAT",
      when: aeat?.on
        ? timeWords(aeat.on, locale)
        : recorded
          ? "Not confirmed yet"
          : "—",
      detail: aeat
        ? aeatWords(aeat.state, locale)
        : "Add the AEAT receipt to confirm",
      state: aeat?.state === "justificante_verified" ? "done" : "open",
    },
  ];
  const canRecord = form.verification === "complete" && !blocked && !recorded;
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading
        title="Export and record"
        lead="Cadrumo makes the file; you upload it yourself at the AEAT's electronic office. Nothing is sent from here."
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
              The file to upload at the AEAT
            </h3>
            <p className="text-base text-muted-foreground">
              In the official format for modelo {form.modelo}. It is not proof
              of filing; the AEAT's receipt is.
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
              Open Check
            </Button>
          </Alert>
        )}
        {file && !file.current && !recorded && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {w("tui.modelo.workbench.header.file_out_of_date", locale, {
              date: timeWords(file.exported_at, locale),
            })}
          </Alert>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {recorded ? (
            <>
              <Button variant="ghost" size="sm">
                <Icon name="folder" size="xs" />
                Show the filed file
              </Button>
              <span className="text-sm text-muted-foreground">
                Exporting again makes a new file; only do it for a correction.
              </span>
            </>
          ) : (
            <>
              <Button
                disabled={!!blocked}
                variant={file?.current ? "secondary" : "primary"}
              >
                <Icon name="download" size="xs" />
                {file ? "Export again" : "Export file…"}
              </Button>
              {file?.current && (
                <Button variant="ghost">
                  <Icon name="folder" size="xs" />
                  Show in folder
                </Button>
              )}
            </>
          )}
          <Button variant="link" className="ml-auto">
            How to upload it
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
            <h3 className="text-md font-medium">After you have filed</h3>
            <p className="text-base text-muted-foreground">
              Record here that you filed it, so your calendar and later
              declarations know. Then add the AEAT's receipt to confirm it.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!recorded && (
            <Button variant="secondary" disabled={!canRecord}>
              Record as filed…
            </Button>
          )}
          <Button
            variant="outline"
            disabled={!recorded || aeat?.state === "justificante_verified"}
          >
            <Icon name="paste" size="xs" />
            Add the AEAT receipt (PDF)…
          </Button>
          <span className="text-sm text-muted-foreground">
            {!recorded
              ? canRecord
                ? "Also if you filed some other way."
                : "Check the declaration first."
              : aeat?.state === "justificante_verified"
                ? "The receipt matches this declaration."
                : "Not confirmed by a receipt yet."}
          </span>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-muted-foreground">
          Other copies
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
        title={w("tui.modelo.workbench.sources.title", locale)}
        lead="Boxes are filled from these when you calculate. Correct a value where it is kept, then calculate again."
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
                      aria-label={`Go to box ${b}`}
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
        title="History"
        lead="What happened to this declaration, newest first. Kept on this computer."
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
                Read from the AEAT
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
                  ? "Changes applied"
                  : w(`tui.declarations.lifecycle.${e.kind}`, locale)}
              </span>
              <span className="text-sm text-muted-foreground">
                {e.amount
                  ? `${money(e.amount, locale)} · ${w("tui.modelo.workbench.header.result.to_pay", locale)}`
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
          Rename
        </Button>
        {!form.edit_closure && (
          <Button variant="ghost" size="sm" className="text-destructive">
            <Icon name="trash" size="xs" />
            Discard this declaration
          </Button>
        )}
      </div>
      <Dialog open={correcting} onOpenChange={onCorrect}>
        <DialogContent closeLabel="Close">
          <DialogHeader>
            <DialogTitle>Prepare a correction</DialogTitle>
            <DialogDescription>
              A filed declaration is never changed in place. Cadrumo prepares a
              correction from it; you change what was wrong, then export its
              file and file it at the AEAT like any other.
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Whether it is filed as a supplementary return or a rectification
            depends on the modelo and on which way the amount moves. Cadrumo
            works it out and tells you before you export.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => onCorrect(false)}>
              Cancel
            </Button>
            <Button onClick={() => onCorrect(false)}>
              Prepare the correction
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
