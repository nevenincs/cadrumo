import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { Button } from "@/components/ui/button";
import {
  exactly,
  isPrintable,
  type CommitKey,
} from "@/components/ui/dataGridModel";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tabs, TabsList } from "@/components/ui/tabs";
import type { SourceSurface } from "../../../shell/modeloContract/modeloWork";
import type {
  ModeloFormCounts,
  ModeloFormText,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../../shell/modeloContract/modeloWorkForm";
import type { PublicModeloWorkForm } from "../../../shell/modeloContract/modeloWorkFormPart2";
import type { RefusalIntent, WindowPlace } from "../../../shell/refusal";
import { useStrings, type Translate } from "../../../shell/strings";
import { WorkspacePaneToggles } from "../workspace/WorkspacePanes";
import { boxNotes } from "./boxNotes";
import {
  FormContext,
  type FormContextValue,
  type OpenableSurface,
} from "./formContext";
import { SectionView, type DrawnSection, type Shown } from "./SectionView";
import { PageTab } from "./PageTab";
import { PriorValuesOffer } from "./PriorValuesOffer";
import { StatementsOffer } from "./StatementsOffer";
import {
  clearIntent,
  editKey,
  editsAdmitted,
  fieldKey,
  ANSWERS_PAGE,
  UNPLACED_PAGE,
  WORKING_FIGURES_PAGE,
  type FormSession,
} from "./session";
import type { EditRequest } from "./ValueCell";

// The form as a document, one page at a time: the official sections in
// order, each box on one line with its printed number, its words, its value
// and where the value comes from; grids keep the official rows and columns;
// repeated records are tables. It is generated from the read of whatever
// declaration it is given, and decides nothing about a box: the application's
// fields say how each one reads and whether it may be changed. Sections far
// from the view wait to be drawn.

/** A page as the form draws it: an official page, or one of the lists the
 * read keeps apart from the pages. */
type DrawnPage = {
  id: string;
  heading: ModeloFormText;
  applies: boolean | null;
  appliesWords: string | null;
  sections: DrawnSection[];
  counts: ModeloFormCounts | null;
};

function drawnPages(form: PublicModeloWorkForm, t: Translate): DrawnPage[] {
  const pages: DrawnPage[] = form.pages.map((page) => ({
    id: page.id,
    heading: page.heading,
    applies: page.applies,
    appliesWords: page.applicability_words,
    sections: page.sections.map((section) => ({
      id: section.id,
      heading: section.heading,
      official_heading: section.official_heading,
      blocks: section.blocks,
      counts: section.counts,
    })),
    counts: page.counts,
  }));
  const apart = (
    id: string,
    heading: string,
    fields: PublicModeloFormField[],
  ): DrawnPage => {
    return {
      id,
      heading: { text: heading, disclosure: "localized" },
      applies: true,
      appliesWords: null,
      sections: [
        {
          id,
          heading: { text: heading, disclosure: "localized" },
          official_heading: null,
          blocks: fields.map((field, index) => ({
            kind: "field" as const,
            id: `${id}-${index}`,
            field,
          })),
          counts: null,
        },
      ],
      counts: null,
    };
  };
  if (form.unplaced.length)
    pages.push(
      apart(
        UNPLACED_PAGE,
        t("workspace.modelo.page.unplaced"),
        form.unplaced.map((unplaced) => unplaced.field),
      ),
    );
  if (form.working_figures.length)
    pages.push(
      apart(
        WORKING_FIGURES_PAGE,
        t("workspace.modelo.page.calculation_details"),
        form.working_figures,
      ),
    );
  // The answers are headed as the read's outline heads them.
  const answers = form.outline.find((group) => group.kind === "answers");
  if (answers && form.answers.length)
    pages.push(apart(ANSWERS_PAGE, answers.heading.text, form.answers));
  return pages;
}

function Keys() {
  const t = useStrings();
  const lines: [string[], string][] = [
    [["↑", "↓"], "desktop.modelo.keys.move"],
    [["Enter"], "desktop.modelo.keys.change"],
    [["Esc"], "desktop.modelo.keys.leave"],
    [["Delete"], "desktop.modelo.keys.delete"],
    [["N"], "desktop.modelo.keys.next_attention"],
  ];
  return (
    <Popover>
      <PopoverTrigger asChild>
        <IconButton label={t("workspace.modelo.legend.group.keys")} size="sm">
          <Icon name="keyboard" />
        </IconButton>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="grid w-72 grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm"
      >
        {lines.map(([keys, key]) => (
          <div key={key} className="contents">
            <span className="flex gap-1">
              {keys.map((name) => (
                <Kbd key={name}>{name}</Kbd>
              ))}
            </span>
            <span>{t(key)}</span>
          </div>
        ))}
      </PopoverContent>
    </Popover>
  );
}

export type FormViewProps = {
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  /** Opens the place a source-fed value is corrected at. */
  onOpenSurface?: (surface: SourceSurface) => void;
  /** Whether the window can open an area; every area is taken as openable
   * when this is not given. */
  canOpenSurface?: (surface: OpenableSurface) => boolean;
  /** Opens the place a refused statement's served way out leads to; no way
   * out is followed when this is not given. */
  onRefusalAction?: (intent: RefusalIntent) => void;
  /** Whether this host opens a place a served way out leads to. */
  opensRefusalPlace?: (place: WindowPlace) => boolean;
};

export function FormView({
  envelope,
  session,
  onOpenSurface,
  canOpenSurface,
  onRefusalAction,
  opensRefusalPlace,
}: FormViewProps) {
  const t = useStrings();
  const form = envelope.form.form;
  const pages = useMemo(() => drawnPages(form, t), [form, t]);
  const notes = useMemo(
    () => boxNotes(envelope.issue_lines),
    [envelope.issue_lines],
  );
  const page =
    pages.find((candidate) => candidate.id === session.pageId) ?? pages[0];
  const [mine, setMine] = useState(false);
  const [query, setQuery] = useState("");
  const [editing, setEditingState] = useState<{
    key: string;
    request: EditRequest;
  } | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const pageTabs = useRef<HTMLDivElement>(null);
  // The page tabs control the one scroller the chosen page is drawn in.
  const panel = useId();
  const admitted = editsAdmitted(envelope);

  const onPage = useMemo(
    () => session.placed.filter((placed) => placed.pageId === page?.id),
    [session.placed, page?.id],
  );
  const searching = mine || query.trim() !== "";
  const shown: Shown = useMemo(() => {
    if (!searching) return null;
    const words = query.trim().toLowerCase();
    const box = words.replace(/^\[|\]$/g, "");
    return new Set(
      onPage
        .filter(
          ({ field }) =>
            (!mine || field.filers_own) &&
            (!words ||
              (field.box ?? "") === box ||
              field.label.text.toLowerCase().includes(words)),
        )
        .map((placed) => placed.key),
    );
  }, [searching, mine, query, onPage]);
  const order = useMemo(
    () =>
      onPage
        .filter((placed) => shown === null || shown.has(placed.key))
        .map((placed) => placed.key),
    [onPage, shown],
  );
  const byKey = useMemo(
    () => new Map(session.placed.map((placed) => [placed.key, placed])),
    [session.placed],
  );
  const chosen = session.selectedKey ? byKey.get(session.selectedKey) : null;
  const forcedSection =
    chosen?.pageId === page?.id ? chosen?.sectionId : undefined;

  const focusBox = useCallback((key: string, scroll: boolean) => {
    requestAnimationFrame(() => {
      const element = scroller.current?.querySelector<HTMLElement>(
        `[data-key="${CSS.escape(key)}"]`,
      );
      if (!element) return;
      if (scroll) element.scrollIntoView({ block: "center" });
      element.focus({ preventScroll: true });
    });
  }, []);

  const pageId = page?.id;
  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = 0;
    // A page chosen from outside the tabs still shows its tab in the row.
    pageTabs.current
      ?.querySelector('[data-state="active"]')
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [pageId]);

  const { reveal } = session;
  useEffect(() => {
    if (!reveal) return;
    if (reveal.key) focusBox(reveal.key, true);
    else
      requestAnimationFrame(() =>
        document
          .getElementById(`section-${reveal.sectionId}`)
          ?.scrollIntoView({ block: "start" }),
      );
  }, [reveal, focusBox]);

  const move = useCallback(
    (key: string) => {
      session.select(key);
      focusBox(key, true);
    },
    [session, focusBox],
  );
  const step = (from: string | null, by: number) => {
    const at = from ? order.indexOf(from) : -1;
    const next =
      order[Math.min(Math.max(at + by, 0), Math.max(order.length - 1, 0))];
    if (next) move(next);
  };

  const setEditing = useCallback(
    (key: string | null, request: EditRequest = {}) =>
      setEditingState(key && admitted ? { key, request } : null),
    [admitted],
  );
  const onDone = useCallback(
    (field: PublicModeloFormField, how: CommitKey | "cancel") => {
      const key = fieldKey(field);
      const at = order.indexOf(key);
      const to =
        how === "enter" || how === "tab"
          ? order[at + 1]
          : how === "shift-tab"
            ? order[at - 1]
            : undefined;
      if (to) move(to);
      else focusBox(key, false);
    },
    [order, move, focusBox],
  );

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (editing || event.defaultPrevented || event.nativeEvent.isComposing)
      return;
    const target = event.target as HTMLElement;
    if (
      target.closest(
        "input, textarea, select, button, a, [contenteditable=true]",
      )
    )
      return;
    const key = session.selectedKey;
    const field = chosen?.field ?? null;
    const editable = field ? session.editable(field) : false;
    const plain = exactly(event);
    const handled = (() => {
      if (plain && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        step(key, event.key === "ArrowDown" ? 1 : -1);
        return true;
      }
      if (plain && (event.key === "Home" || event.key === "End")) {
        const edge = event.key === "Home" ? order[0] : order.at(-1);
        if (edge) move(edge);
        return true;
      }
      if (!key || !field) {
        if (plain && !key && order[0] && event.key !== "Tab") {
          move(order[0]);
          return true;
        }
        return false;
      }
      if (plain && (event.key === "Enter" || event.key === "F2")) {
        if (editable) setEditing(key);
        return true;
      }
      if (plain && (event.key === "Delete" || event.key === "Backspace")) {
        if (!editable) return true;
        const held = session.staged.get(editKey(field));
        if (held && "value" in held.intent) session.unstage(held.key);
        else if (!held && field.stated_absent !== null) session.withdraw(field);
        // Emptying a figure stated for earlier returns withdraws its family.
        else if (!held && field.stated_prior_value?.family_id)
          void session.enter(field, "");
        else if (!held && field.filers_own)
          session.stage(field, clearIntent(field));
        return true;
      }
      if (plain && event.key === "Escape") {
        session.select(null);
        scroller.current?.focus({ preventScroll: true });
        return true;
      }
      if (isPrintable(event)) {
        if (editable) {
          setEditing(key, { seed: event.key });
          return true;
        }
        if (event.key.toLowerCase() === "n") {
          session.jumpToNext("todo");
          return true;
        }
      }
      return false;
    })();
    if (handled) {
      event.preventDefault();
      event.stopPropagation();
    }
  };

  const context: FormContextValue = {
    envelope,
    session,
    editing,
    setEditing,
    onDone,
    onOpenSurface,
    canOpenSurface: canOpenSurface ?? (() => true),
    notes,
    translated: form.language !== "es",
  };

  return (
    <FormContext.Provider value={context}>
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-none flex-wrap items-center gap-2 border-b border-border px-6 py-2">
          <div className="relative w-64 max-w-full min-w-0">
            <Icon
              name="search"
              size="xs"
              className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-faint"
            />
            <Input
              controlSize="sm"
              type="search"
              placeholder={t("workspace.modelo.search.placeholder")}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="pl-7"
              aria-label={t("desktop.modelo.search.label")}
            />
          </div>
          <Button
            size="sm"
            variant="ghost"
            aria-pressed={mine}
            onClick={() => setMine(!mine)}
          >
            {t("workspace.modelo.filter.only_mine")}
          </Button>
          <span className="ml-auto" />
          {admitted && <Keys />}
          <WorkspacePaneToggles />
        </div>
        {/* What is said about the whole form can run longer than the
            window; it scrolls on its own and gives way first, so the boxes
            keep their room. */}
        <div
          data-form-gives-way=""
          className="max-h-1/3 min-h-0 overflow-y-auto"
        >
          {/* The rung of authority this year reaches, as the registry named
              it, and, below filing grade, the sentence saying why it cannot be
              filed. */}
          <p
            data-year-projection={form.year_projection.direction}
            data-reachable-grade={form.year_projection.reachable_grade}
            className="flex flex-none flex-wrap gap-x-2 border-b border-border px-4 py-1.5 text-sm text-muted-foreground"
          >
            <span data-year-projection-grade className="font-medium">
              {form.year_projection.reachable_grade_words}
            </span>
            {form.year_projection.words && (
              <span data-year-projection-words>
                {form.year_projection.words}
              </span>
            )}
          </p>
          <StatementsOffer
            key={`${envelope.work_unit_id}:${session.statements
              .map(
                (statement) =>
                  `${statement.family}:${statement.row_identity ?? ""}`,
              )
              .join()}`}
            session={session}
          />
          <PriorValuesOffer
            key={`${envelope.work_unit_id}:prior`}
            session={session}
            onRefusalAction={onRefusalAction}
            opensRefusalPlace={opensRefusalPlace}
          />
        </div>
        {pages.length > 1 && page && (
          <Tabs
            value={page.id}
            onValueChange={(id) => session.setPageId(id)}
            className="flex-none border-b border-border px-4"
          >
            <TabsList
              ref={pageTabs}
              aria-label={t("desktop.modelo.form.pages")}
              className="overflow-x-auto"
            >
              {pages.map((candidate) => (
                <PageTab key={candidate.id} page={candidate} panel={panel} />
              ))}
            </TabsList>
          </Tabs>
        )}
        <div
          ref={scroller}
          id={panel}
          data-modelo-form=""
          role="region"
          aria-label={page?.heading.text ?? t("desktop.modelo.view.form")}
          tabIndex={session.selectedKey ? -1 : 0}
          onKeyDown={onKeyDown}
          className="@container min-h-40 flex-1 overflow-y-auto px-6 py-5 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
        >
          {page && (
            <div
              key={page.id}
              className="mx-auto flex max-w-4xl flex-col gap-8"
            >
              {page.applies === false ? (
                <p className="rounded-lg border border-dashed border-border p-4 text-base text-muted-foreground">
                  {page.appliesWords}
                </p>
              ) : (
                <>
                  {page.applies === null && (
                    <p className="text-sm text-faint">
                      {t("workspace.modelo.page.only_if_it_applies")}
                    </p>
                  )}
                  {page.sections.map((section) => (
                    <SectionView
                      key={section.id}
                      section={section}
                      shown={shown}
                      forced={
                        shown !== null ||
                        section.id === forcedSection ||
                        section.id === reveal?.sectionId
                      }
                    />
                  ))}
                  {shown !== null && shown.size === 0 && (
                    <p className="text-base text-muted-foreground">
                      {t("workspace.modelo.filter.empty")}
                    </p>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </FormContext.Provider>
  );
}
