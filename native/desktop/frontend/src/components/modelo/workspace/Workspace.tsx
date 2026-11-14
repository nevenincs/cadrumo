import {
  useEffect,
  useId,
  useRef,
  useState,
  type PointerEvent,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatInstantDay } from "../../../shared/dateFormats";
import { facts } from "../../../shell/compose";
import type {
  ModeloFormAttention,
  ModeloFormNextAction,
  ModeloFormResultView,
  ModeloWorkbenchFormProjectionV1,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings, type Translate } from "../../../shell/strings";
import { JourneySteps } from "./JourneySteps";
import { AttentionMark, DEADLINE_TONE, GlyphMark } from "./Marks";
import { useReservedSize } from "./useReservedSize";
import { FormPanes, type WorkspacePanes } from "./WorkspacePanes";

/** The views of one declaration, as its tabs name them. */
export type WorkspaceView =
  "form" | "check" | "credits" | "compare" | "file" | "sources" | "history";

/** What the other component lanes put into the workspace. */
export type WorkspaceSlots = {
  /** The form view's column: its toolbar, notice and pages. */
  form: ReactNode;
  /** Beside the form: the To do and Outline rail. */
  rail?: ReactNode;
  /** The chosen box's details; placed beside the form, or under it at
   * narrow widths. Content only. */
  details?: ReactNode;
  /** The Export and record view. */
  filing: ReactNode;
  /** The Check, Sources and History views. */
  check: ReactNode;
  /** Credits, estimates, and the IVA wallet entry where the declaration uses it. */
  credits?: ReactNode;
  /** The comparisons the declaration asks for; the view is offered only
   * where it has one. */
  compare?: ReactNode;
  creditsLabel?: string;
  sources: ReactNode;
  history: ReactNode;
  /** Dialogs drawn at the workspace's root. */
  dialogs?: ReactNode;
};

/** The view each next action opens; the actions an operation answers open
 * none, and the container runs them. */
export const ACTION_VIEW: Partial<Record<ModeloFormNextAction, WorkspaceView>> =
  {
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
  check: ["blocks", "check", "limitation"],
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
          {facts(t, [
            result.words,
            stagedCount > 0
              ? t("workspace.modelo.header.result.out_of_date_until_applied")
              : result.out_of_date_words,
          ])}
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
  panes,
  busy = false,
  reading = false,
  writeHeld = false,
  prerequisiteHeld = false,
  notice,
  slots,
  onRun,
  onReview,
  onDiscardStaged,
  onJumpToFirstAttention,
  onCorrect,
  onBack,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  locale: string;
  view: WorkspaceView;
  onViewChange(view: WorkspaceView): void;
  /** Edits the form holds unapplied. */
  stagedCount: number;
  /** The viewer's arrangement of the panes around the form. */
  panes: WorkspacePanes;
  /** An operation the header started has not answered yet. */
  busy?: boolean;
  /** The window is reading the declaration again after its own settled
   * write: the step served before it is not offered until the read answers. */
  reading?: boolean;
  writeHeld?: boolean;
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
  /** Selects the box the read model serves as the first that needs the
   * filer, once the form is shown. */
  onJumpToFirstAttention(): void;
  /** Opens the correction of a declaration recorded as filed. */
  onCorrect(): void;
  onBack(): void;
}) {
  const t = useStrings();
  // The views share one panel, whose content follows the chosen tab.
  const panel = useId();
  // Where the form view draws its pane controls: at the end of the view
  // bar, which keeps its width whatever the panes do.
  const [paneControls, setPaneControls] = useState<HTMLElement | null>(null);
  const form = envelope.form.form;
  const header = envelope.header;
  const journey = envelope.form.journey;
  // The read model serves the answer for each state only this window knows:
  // changes it holds unapplied (the steps while they are held, and applying
  // them before anything else), and an apply's prerequisite that still
  // stands (resolving it, from the findings).
  const next = prerequisiteHeld
    ? journey.held_prerequisite_next_step
    : envelope.next_step;
  const steps =
    stagedCount > 0 ? journey.steps_while_changes_held : journey.steps;
  const action: ModeloFormNextAction | null =
    stagedCount > 0 ? "apply" : (next?.action ?? null);
  const findingsLead = next?.findings_lead ?? false;
  const target = action ? ACTION_VIEW[action] : undefined;
  const writesNext =
    action === "calculate" || action === "recalculate" || action === "verify";
  const levels = new Map(header.attention.map((a) => [a.level, a]));
  const day = (iso: string | null) =>
    iso ? formatInstantDay(locale, iso) : "";

  // A next action that opens another view puts the keyboard in it, on its
  // first finding where it lists one: the button pressed is not drawn on the
  // view it opened, and the keyboard would otherwise fall to the document.
  const arriving = useRef(false);
  useEffect(() => {
    if (!arriving.current) return;
    arriving.current = false;
    const shown = document.getElementById(panel);
    (
      shown?.querySelector<HTMLElement>("[data-attention-level]") ?? shown
    )?.focus();
  }, [view, panel]);
  const openView = (next: WorkspaceView) => {
    if (next !== view && next !== "form") arriving.current = true;
    onViewChange(next);
  };

  const runNext = () => {
    if (!action) return;
    if (action === "apply") onReview();
    else if (findingsLead) {
      // Already on the check, the step is its first listed finding.
      if (view === "check")
        document
          .getElementById(panel)
          ?.querySelector<HTMLElement>("[data-attention-level]")
          ?.focus();
      else openView("check");
    } else if (target) {
      openView(target);
      if (target === "form") onJumpToFirstAttention();
    } else onRun(action);
  };
  const recorded = action === "recorded" && (
    <span className="max-w-xs text-sm text-muted-foreground">
      {facts(t, [
        t("workspace.modelo.next.recorded", {
          date: day(next?.recorded_at ?? null),
        }),
        envelope.receipt?.words,
      ])}
    </span>
  );
  const step =
    action === "recorded" ? (
      next?.receipt_to_add && view !== "file" ? (
        <>
          {recorded}
          <Button onClick={() => openView("file")}>
            {t("workspace.modelo.next_button.add_receipt")}
            <Icon name="forward" size="xs" />
          </Button>
        </>
      ) : (
        recorded
      )
    ) : action && !(target && target === view && view !== "form") ? (
      <Button
        onClick={runNext}
        disabled={(busy || writeHeld) && writesNext}
        aria-busy={busy && writesNext}
      >
        {t(`workspace.modelo.next_button.${action}`)}
        <Icon name={busy && writesNext ? "loader" : "forward"} size="xs" />
      </Button>
    ) : null;
  // The step served before the window's own write is not offered while the
  // read that replaces it runs.
  const nextShown = reading ? (
    <span
      role="status"
      className="flex items-center gap-1.5 text-sm text-muted-foreground"
    >
      <Spinner />
      {t("desktop.navigation.busy")}
    </span>
  ) : (
    step
  );

  const marks = (tab: WorkspaceView) =>
    (TAB_LEVELS[tab] ?? []).map((level) => {
      const entry = levels.get(level);
      return entry ? <AttentionMark key={level} entry={entry} /> : null;
    });
  // The result and the step are swapped for each other as the declaration is
  // calculated, written and read again; the room they have needed is kept so
  // that the tabs below do not move under a press.
  const reserved = useReservedSize<HTMLDivElement>();
  // A tab opens its view on the first pointer event that reaches it, and
  // again on the click that completes the press, so a press whose mouse
  // events are not all delivered to the tab still opens it. Opening the view
  // already shown does nothing.
  const press = (value: WorkspaceView, event: PointerEvent<HTMLElement>) => {
    if (event.button === 0 && !event.ctrlKey) onViewChange(value);
  };
  const tab = (value: WorkspaceView, name: string, extra?: ReactNode) => (
    <TabsTrigger
      value={value}
      aria-controls={panel}
      onPointerDown={(event) => press(value, event)}
      onClick={() => onViewChange(value)}
    >
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
    // Too short for the header, the tabs and the form's least room, the
    // workspace scrolls as a whole rather than clipping what does not fit.
    <div className="@container flex h-full min-h-0 flex-col overflow-y-auto bg-background">
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
          <JourneySteps steps={steps} />
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
        <div
          ref={reserved.ref}
          style={reserved.style}
          className="ml-auto flex items-center justify-end gap-5"
        >
          <ResultLine result={header.result} stagedCount={stagedCount} t={t} />
          {nextShown}
        </div>
      </header>
      <div className="flex min-w-0 flex-none items-center gap-2 border-b border-border px-4">
        <Tabs
          value={view}
          onValueChange={(v) => onViewChange(v as WorkspaceView)}
          className="min-w-0 flex-1"
        >
          <TabsList
            aria-label={t("desktop.modelo.views.label")}
            className="overflow-x-auto"
          >
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
            {slots.credits !== undefined &&
              tab(
                "credits",
                slots.creditsLabel ?? t("desktop.modelo.view.credits"),
              )}
            {slots.compare !== undefined &&
              tab("compare", t("desktop.modelo.view.compare"))}
            {tab("sources", t("workspace.modelo.key.sources"))}
            {tab("history", t("workspace.modelo.history.title"))}
          </TabsList>
        </Tabs>
        {view === "form" && (
          <div
            ref={setPaneControls}
            data-pane-controls=""
            className="flex-none"
          />
        )}
      </div>
      {banner && (
        <div
          role="status"
          className="flex items-center gap-3 border-b border-border bg-muted px-6 py-2 text-sm"
        >
          <Icon name="lock" size="xs" className="text-muted-foreground" />
          {banner}
        </div>
      )}
      {notice && (
        // What the last operation answered can run long; it scrolls on its
        // own so the form under it keeps its room at any window height.
        <div
          data-workspace-notice=""
          className="max-h-1/3 shrink-0 overflow-y-auto"
        >
          {notice}
        </div>
      )}
      {view === "form" ? (
        <FormPanes
          panes={panes}
          panelId={panel}
          rail={slots.rail}
          form={slots.form}
          details={slots.details ?? null}
          controls={paneControls}
          staged={
            stagedCount > 0 && (
              <div className="flex shrink-0 flex-wrap items-center gap-3 border-t border-border bg-card px-6 py-3 shadow-raised">
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
            )
          }
        />
      ) : (
        <div
          id={panel}
          role="tabpanel"
          tabIndex={-1}
          className="@container min-h-0 flex-1 overflow-y-auto px-6 py-6 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
        >
          {view === "check" && slots.check}
          {view === "credits" && slots.credits}
          {view === "compare" && slots.compare}
          {view === "file" && slots.filing}
          {view === "sources" && slots.sources}
          {view === "history" && slots.history}
        </div>
      )}
      {slots.dialogs}
    </div>
  );
}
