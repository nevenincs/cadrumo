import { useId, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { dateFormats } from "../../../shared/dateFormats";
import type {
  ModeloFormAttention,
  ModeloFormNextAction,
  ModeloFormResultView,
  ModeloWorkbenchFormProjectionV1,
} from "../../../shell/modeloContract";
import { useStrings, type Translate } from "../../../shell/strings";
import { AttentionMark, DEADLINE_TONE, GlyphMark } from "./Marks";

/** The views of one declaration, as its tabs name them. */
export type WorkspaceView = "form" | "check" | "file" | "sources" | "history";

/** What the other component lanes put into the workspace. */
export type WorkspaceSlots = {
  /** The form view's column: its toolbar, notice and pages. */
  form: ReactNode;
  /** Beside the form at wide widths: the To do and Outline rail. */
  rail?: ReactNode;
  /** The chosen box's details; placed beside the form, or under it at
   * narrow widths. Content only. */
  details?: ReactNode;
  /** The Export and record view. */
  filing: ReactNode;
  /** The Check, Sources and History views. */
  check: ReactNode;
  sources: ReactNode;
  history: ReactNode;
  /** Dialogs drawn at the workspace's root. */
  dialogs?: ReactNode;
};

/** The view each next action opens; the actions an operation answers open
 * none, and the container runs them. */
const ACTION_VIEW: Partial<Record<ModeloFormNextAction, WorkspaceView>> = {
  fill: "form",
  confirm: "form",
  resolve: "check",
  export: "file",
  export_again: "file",
  record_after_file: "file",
};

/** The attention levels each tab shows, as the read model counted them. */
const TAB_LEVELS: Partial<Record<WorkspaceView, ModeloFormAttention[]>> = {
  form: ["missing", "confirm"],
  check: ["blocks", "check"],
};

function ResultLine({
  result,
  stagedCount,
  t,
}: {
  result: ModeloFormResultView | null;
  stagedCount: number;
  t: Translate;
}) {
  if (!result)
    return (
      <span className="text-sm text-muted-foreground">
        {t("workspace.modelo.header.result.no_result_box")}
      </span>
    );
  const help = result.help.length > 0 && (
    <TooltipContent className="flex max-w-xs flex-col gap-1">
      {result.help.map((line) => (
        <span key={line}>{line}</span>
      ))}
    </TooltipContent>
  );
  const body =
    result.state === "stated" && result.amount_text ? (
      <span className="flex flex-col items-end">
        <span
          className={cn(
            "text-lg font-semibold tabular-nums",
            stagedCount > 0 ? "text-muted-foreground" : "text-foreground",
          )}
        >
          {result.amount_text}
        </span>
        <span className="text-sm text-muted-foreground">
          {result.words}
          {stagedCount > 0
            ? ` · ${t("workspace.modelo.header.result.out_of_date_until_applied")}`
            : result.out_of_date_words && ` · ${result.out_of_date_words}`}
        </span>
      </span>
    ) : (
      <span
        className={cn(
          "text-base",
          result.state === "failed"
            ? "font-medium text-destructive"
            : "text-muted-foreground",
        )}
      >
        {result.short_text}
      </span>
    );
  if (!help) return body;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className="rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {body}
        </span>
      </TooltipTrigger>
      {help}
    </Tooltip>
  );
}

function AboutForm({
  envelope,
  t,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  t: Translate;
}) {
  const form = envelope.form.form;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <IconButton label={t("workspace.modelo.about.title")} size="xs">
          <Icon name="info" />
        </IconButton>
      </PopoverTrigger>
      <PopoverContent className="flex w-80 flex-col gap-2 text-sm">
        <p className="font-medium">{t("workspace.modelo.about.title")}</p>
        <p className="text-muted-foreground">
          {t("workspace.modelo.about.official", { modelo: form.modelo })}
          {form.layout_provenance === "generated" &&
            ` ${t("workspace.modelo.about.generated")}`}
        </p>
        {!form.filing && (
          <p className="text-muted-foreground">
            {t("workspace.modelo.header.own_calculation")}
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}

/**
 * One declaration as a document to work through: its header with the
 * result, the deadline and the one next action the read model names, the
 * views of the declaration as tabs, and the banners that say why it cannot
 * be changed. The views themselves are the slots; this frame decides
 * nothing about the declaration.
 */
export function ModeloWorkspace({
  envelope,
  locale,
  view,
  onViewChange,
  stagedCount,
  detailsOpen,
  busy = false,
  prerequisiteHeld = false,
  notice,
  slots,
  onRun,
  onReview,
  onDiscardStaged,
  onJumpToNext,
  onCorrect,
  onBack,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  locale: string;
  view: WorkspaceView;
  onViewChange(view: WorkspaceView): void;
  /** Edits the form holds unapplied. */
  stagedCount: number;
  detailsOpen: boolean;
  /** An operation the header started has not answered yet. */
  busy?: boolean;
  /** An apply was refused on a prerequisite that still stands. */
  prerequisiteHeld?: boolean;
  /** What the last operation answered, shown under the tabs. */
  notice?: ReactNode;
  slots: WorkspaceSlots;
  /** Runs a next action an operation answers: calculate, recalculate or
   * verify. */
  onRun(action: ModeloFormNextAction): void;
  onReview(): void;
  onDiscardStaged(): void;
  /** Selects the next box that needs the filer, once the form is shown. */
  onJumpToNext(): void;
  /** Opens the correction of a declaration recorded as filed. */
  onCorrect(): void;
  onBack(): void;
}) {
  const t = useStrings();
  // The views share one panel, whose content follows the chosen tab.
  const panel = useId();
  const form = envelope.form.form;
  const header = envelope.header;
  const next = envelope.next_step;
  // Two steps only this window knows: changes it holds unapplied, and an
  // apply's prerequisite that still stands, which the findings name.
  const action: ModeloFormNextAction | null =
    stagedCount > 0
      ? "apply"
      : prerequisiteHeld
        ? "resolve"
        : (next?.action ?? null);
  const findingsLead = prerequisiteHeld || (next?.findings_lead ?? false);
  const target = action ? ACTION_VIEW[action] : undefined;
  const levels = new Map(header.attention.map((a) => [a.level, a]));
  const day = (iso: string | null) =>
    iso ? dateFormats(locale).medium.format(new Date(iso)) : "";

  const runNext = () => {
    if (!action) return;
    if (action === "apply") onReview();
    else if (findingsLead) onViewChange("check");
    else if (target) {
      onViewChange(target);
      if (target === "form") onJumpToNext();
    } else onRun(action);
  };
  const recorded = action === "recorded" && (
    <span className="max-w-xs text-sm text-muted-foreground">
      {t("workspace.modelo.next.recorded", {
        date: day(next?.recorded_at ?? null),
      })}
      {envelope.receipt && ` · ${envelope.receipt.words}`}
    </span>
  );
  const nextShown =
    action === "recorded" ? (
      next?.receipt_to_add && view !== "file" ? (
        <>
          {recorded}
          <Button onClick={() => onViewChange("file")}>
            {t("workspace.modelo.next_button.add_receipt")}
            <Icon name="forward" size="xs" />
          </Button>
        </>
      ) : (
        recorded
      )
    ) : action && !(target && target === view && view !== "form") ? (
      <Button onClick={runNext} disabled={busy} aria-busy={busy}>
        {t(`workspace.modelo.next_button.${action}`)}
        <Icon name={busy ? "loader" : "forward"} size="xs" />
      </Button>
    ) : null;

  const marks = (tab: WorkspaceView) =>
    (TAB_LEVELS[tab] ?? []).map((level) => {
      const entry = levels.get(level);
      return entry ? <AttentionMark key={level} entry={entry} /> : null;
    });
  const tab = (value: WorkspaceView, name: string, extra?: ReactNode) => (
    <TabsTrigger value={value} aria-controls={panel}>
      {name}
      {marks(value)}
      {extra}
    </TabsTrigger>
  );

  const banner = form.edit_closure ? (
    <>
      <span>{t("workspace.modelo.filed.read_only")}</span>
      <Button
        size="xs"
        variant="outline"
        className="ml-auto"
        onClick={onCorrect}
      >
        {t("workspace.modelo.correction.title")}
      </Button>
    </>
  ) : envelope.admission_refusal ? (
    <span>
      {envelope.rules_incomplete
        ? t("workspace.modelo.editor.rules_incomplete")
        : (envelope.admission_refusal_words ??
          t("workspace.modelo.editability.no_admission"))}
    </span>
  ) : null;

  return (
    <div className="@container flex h-full min-h-0 flex-col bg-background">
      <header className="flex flex-wrap items-center gap-x-8 gap-y-3 px-6 pt-3 pb-3">
        <div className="flex min-w-0 flex-col gap-1">
          <Button
            variant="link"
            size="xs"
            className="self-start text-sm text-muted-foreground"
            onClick={onBack}
          >
            <Icon name="back" size="xs" />
            {t("workspace.declarations.destination.overview")}
          </Button>
          <div className="flex items-center gap-3">
            <span className="flex h-8 min-w-12 items-center justify-center rounded-md border border-border-strong px-1.5 font-mono text-md font-semibold">
              {form.modelo}
            </span>
            <h1 className="truncate font-serif text-lg">
              {form.modelo_name ?? form.modelo_title ?? form.modelo}
            </h1>
            {form.period_words && (
              <span className="text-md text-muted-foreground">
                {form.period_words}
              </span>
            )}
            <AboutForm envelope={envelope} t={t} />
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            {header.deadline && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span
                    tabIndex={header.deadline.help ? 0 : -1}
                    className={cn(
                      "flex items-center gap-1.5 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      DEADLINE_TONE[header.deadline.tone],
                    )}
                  >
                    <Icon name="calendar" size="xs" />
                    {header.deadline.text}
                  </span>
                </TooltipTrigger>
                {header.deadline.help && (
                  <TooltipContent className="max-w-xs">
                    {header.deadline.help}
                  </TooltipContent>
                )}
              </Tooltip>
            )}
            {header.file && (
              <span
                className={cn(
                  "flex items-center gap-1.5",
                  header.file.current
                    ? "text-muted-foreground"
                    : "text-warning",
                )}
              >
                <Icon name="page" size="xs" />
                {header.file.words}
              </span>
            )}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-5">
          <ResultLine result={header.result} stagedCount={stagedCount} t={t} />
          {nextShown}
        </div>
      </header>
      <Tabs
        value={view}
        onValueChange={(v) => onViewChange(v as WorkspaceView)}
        className="flex-none border-b border-border px-4"
      >
        <TabsList aria-label={t("desktop.modelo.views.label")}>
          {tab("form", t("desktop.modelo.view.form"))}
          {tab(
            "check",
            t("workspace.modelo.step.review"),
            envelope.verdict.status === "complete" && (
              <GlyphMark
                icon="check"
                words={envelope.verdict.words}
                className="text-success"
              />
            ),
          )}
          {tab(
            "file",
            t("workspace.modelo.filing.title"),
            form.filing && (
              <GlyphMark
                icon="check"
                words={t("workspace.declarations.list.group.recorded")}
                className="text-success"
              />
            ),
          )}
          {tab("sources", t("workspace.modelo.key.sources"))}
          {tab("history", t("workspace.modelo.history.title"))}
        </TabsList>
      </Tabs>
      {banner && (
        <div
          role="status"
          className="flex items-center gap-3 border-b border-border bg-muted px-6 py-2 text-sm"
        >
          <Icon name="lock" size="xs" className="text-muted-foreground" />
          {banner}
        </div>
      )}
      {notice}
      {view === "form" ? (
        <div
          id={panel}
          role="tabpanel"
          className="relative grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] @4xl:grid-cols-[--spacing(60)_minmax(0,1fr)] @6xl:data-[details=true]:grid-cols-[--spacing(64)_minmax(0,1fr)_--spacing(88)]"
          data-details={detailsOpen && slots.details !== undefined}
        >
          <aside className="hidden min-h-0 flex-col border-r border-border bg-chrome @4xl:flex">
            {slots.rail}
          </aside>
          <div className="flex min-h-0 flex-col">
            {slots.form}
            {detailsOpen && slots.details && (
              <div className="h-2/5 flex-none overflow-y-auto border-t border-border bg-card @6xl:hidden">
                {slots.details}
              </div>
            )}
            {stagedCount > 0 && (
              <div className="flex items-center gap-3 border-t border-border bg-card px-6 py-3 shadow-raised">
                <Icon name="edit" size="sm" />
                <span className="text-base font-medium">
                  {t("workspace.modelo.next.apply", { count: stagedCount })}
                </span>
                <div className="ml-auto flex gap-2">
                  <Button variant="ghost" onClick={onDiscardStaged}>
                    {t("workspace.modelo.review.discard")}
                  </Button>
                  <Button onClick={onReview}>
                    {t("workspace.modelo.next_button.apply")}
                  </Button>
                </div>
              </div>
            )}
          </div>
          {detailsOpen && slots.details && (
            <aside className="hidden min-h-0 overflow-y-auto border-l border-border bg-card @6xl:block">
              {slots.details}
            </aside>
          )}
        </div>
      ) : (
        <div
          id={panel}
          role="tabpanel"
          className="@container min-h-0 flex-1 overflow-y-auto px-6 py-6"
        >
          {view === "check" && slots.check}
          {view === "file" && slots.filing}
          {view === "sources" && slots.sources}
          {view === "history" && slots.history}
        </div>
      )}
      {slots.dialogs}
    </div>
  );
}
