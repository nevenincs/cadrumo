import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type Ref,
  type RefObject,
} from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { chordAria, chordText } from "@/shared/chords";
import { INSPECTOR_CHORD } from "../ledgerChords";
import { facts, listed, noted } from "../../../shell/compose";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import type { ClassifySelection } from "../../../shell/ledgerCommands";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import {
  actionRows,
  type StageEvent,
  type StageState,
} from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import {
  amountText,
  dateText,
  directionLabel,
  lifecycleLabel,
  statusLabel,
  statusWord,
} from "../movements/movementWords";
import type { ActionRequest } from "./ActionDialog";
import { ClassifySection } from "./ClassifySection";
import { DetailsSection } from "./DetailsSection";
import { DocumentsSection } from "./DocumentsSection";
import { HistorySection } from "./HistorySection";
import { InvoiceSection } from "./InvoiceSection";
import {
  INSPECTOR_SECTIONS,
  currentSection,
  lifecycleTakes,
  type InspectorSection,
} from "./inspectorModel";
import {
  declarationName,
  lifecycleName,
  revisionStateLabel,
  seals,
  sectionNames,
} from "./inspectorWords";
import { JumpIndex } from "./JumpIndex";
import { useLedgerRead } from "./useInspectorReads";

/** How far below the top of the scroll a section's heading counts as
 * reached, in CSS pixels. */
const SPY_OFFSET = 24;

/** Where the inspector was asked to open, each time it is asked. */
export type InspectorFocus = {
  section: InspectorSection | null;
  /** Focus the jump index once drawn. */
  index: boolean;
  /** Tells one request from the next. */
  tick: number;
};

/** Reports when `element` first scrolls into the inspector's view. */
function useSeen(
  root: RefObject<HTMLElement | null>,
  key: string,
): [Ref<HTMLElement>, boolean] {
  const [seen, setSeen] = useState<string | null>(null);
  const [element, setElement] = useState<HTMLElement | null>(null);
  useEffect(() => {
    if (!element || seen === key) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setSeen(key);
      },
      { root: root.current, rootMargin: "50%" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [element, root, key, seen]);
  return [setElement, seen === key];
}

/**
 * The inspector of one movement: its stored state in the header, the
 * actions behind ⋯, and one scroll of sections with a jump index that
 * follows the reading. A section's reads are made when it first comes
 * into view. Every change it makes is staged into the page's changes; the
 * header and the counts show what is stored.
 */
export function MovementInspector({
  port,
  row,
  rows,
  generation,
  stage,
  onStage,
  classify,
  issues,
  checked,
  duplicate = false,
  accounts,
  focus,
  locale,
  onClose,
  onShow,
  onOpenInvoice,
  onAction,
  onSplit,
  onSelectCohort,
  say,
}: {
  port: LedgerPort;
  row: LedgerRow;
  /** The window's movements. */
  rows: readonly LedgerRow[];
  /** Which read of the window `row` comes from. */
  generation: number | string;
  stage: StageState;
  onStage: (event: StageEvent) => void;
  classify: ClassifySelection | null;
  issues: readonly string[];
  /** Whether readiness has been measured: until it has, a reviewed
   * movement is not measured, never done. */
  checked: boolean;
  /** An import flagged it as a likely duplicate of a stored movement. */
  duplicate?: boolean;
  accounts: readonly OwnAccountChoice[] | null;
  focus: InspectorFocus;
  locale: string;
  onClose: () => void;
  onShow: (id: string) => void;
  onOpenInvoice: (invoiceId: string) => void;
  onAction: (request: ActionRequest) => void;
  onSplit: (row: LedgerRow) => void;
  onSelectCohort: (ids: string[]) => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const tx = row.transaction;
  const id = tx.transaction_id;
  const key = `${id}:${generation}`;
  const scroll = useRef<HTMLDivElement>(null);
  const indexFirst = useRef<HTMLButtonElement>(null);
  const names = useMemo(() => sectionNames(t), [t]);
  const byId = useMemo(
    () =>
      new Map(rows.map((entry) => [entry.transaction.transaction_id, entry])),
    [rows],
  );
  const changes = stage.content.rows[id];
  const actions = useMemo(
    () =>
      stage.content.actions.filter((action) => actionRows(action).includes(id)),
    [stage.content.actions, id],
  );

  // ---- Reads -----------------------------------------------------------------
  const [documentsRef, documentsSeen] = useSeen(scroll, key);
  const [invoiceRef, invoiceSeen] = useSeen(scroll, key);
  const [historyRef, historySeen] = useSeen(scroll, key);
  const prefix = { transaction_prefix: id };
  const track = useLedgerRead(port, "ledger.track", prefix, key, true);
  const view = useLedgerRead(port, "ledger.view", prefix, key, true);
  const history = useLedgerRead(
    port,
    "ledger.history.typed",
    { transaction_prefix: id, include_split_siblings: true },
    key,
    historySeen,
  );
  const evidence = useLedgerRead(
    port,
    "ledger.evidence.list",
    {},
    `evidence:${generation}`,
    documentsSeen,
  );
  const invoices = useLedgerRead(
    port,
    "ledger.invoice.list",
    {},
    `invoices:${generation}`,
    invoiceSeen,
  );

  const tracked = track?.kind === "ready" ? track.result : null;
  const sealing = (tracked?.participated_in ?? []).filter(seals);
  const sealed = sealing.length > 0;
  const scope = {
    t,
    locale,
    row,
    changes,
    sealed,
    accounts,
    onStage,
  };

  // ---- The jump index --------------------------------------------------------
  const [current, setCurrent] = useState<InspectorSection | null>("classify");
  const spy = useCallback(() => {
    const element = scroll.current;
    if (!element) return;
    const tops = INSPECTOR_SECTIONS.flatMap((section) => {
      const found = element.querySelector<HTMLElement>(
        `[data-section-body="${section}"]`,
      );
      return found ? [{ id: section, top: found.offsetTop }] : [];
    });
    setCurrent(
      currentSection(
        tops,
        {
          top: element.scrollTop,
          height: element.clientHeight,
          content: element.scrollHeight,
        },
        SPY_OFFSET,
      ),
    );
  }, []);
  useEffect(() => {
    const element = scroll.current;
    if (!element) return;
    spy();
    element.addEventListener("scroll", spy, { passive: true });
    return () => element.removeEventListener("scroll", spy);
  }, [spy, id]);
  const jump = useCallback((section: InspectorSection, focusHeading = true) => {
    const element = scroll.current;
    const target = element?.querySelector<HTMLElement>(
      `[data-section-body="${section}"]`,
    );
    if (!element || !target) return;
    element.scrollTop = target.offsetTop;
    if (focusHeading)
      target.querySelector<HTMLElement>("h3")?.focus({ preventScroll: true });
  }, []);
  // A movement to classify opens on Classify; a request names its own
  // section, and Alt+I focuses the index.
  const opening = useRef({ focus, pending: row.review_status === "pending" });
  useLayoutEffect(() => {
    opening.current = { focus, pending: row.review_status === "pending" };
  });
  // Only a new movement or a new request moves the scroll.
  useLayoutEffect(() => {
    const { focus: asked, pending } = opening.current;
    const wanted = asked.section ?? (pending ? "classify" : null);
    if (wanted) jump(wanted, false);
    if (asked.index) indexFirst.current?.focus();
  }, [id, focus.tick, jump]);

  const focusField = (field: string) => {
    const target = scroll.current?.querySelector<HTMLElement>(
      `[data-field="${field}"]`,
    );
    if (!target) return;
    target.scrollIntoView({ block: "nearest" });
    target.focus();
  };

  // ---- The header ------------------------------------------------------------
  const issueCount = checked ? issues.length : null;
  const word = statusWord(row.review_status, issueCount);
  const staged = Object.keys(changes ?? {}).length + actions.length;
  const lifecycleItems = (
    ["archive", "stash", "restore", "exclude"] as const
  ).map((kind) => (
    <DropdownMenuItem
      key={kind}
      disabled={!lifecycleTakes(kind, row, sealed ? new Set([id]) : new Set())}
      onSelect={() => onAction({ kind, ids: [id] })}
    >
      {lifecycleName(t, kind)}…
    </DropdownMenuItem>
  ));
  const cohort = useMemo(() => {
    if (history?.kind !== "ready") return [];
    return history.result.object_ids.filter(
      (other) => byId.get(other)?.transaction.lifecycle_state === "ACTIVE",
    );
  }, [history, byId]);

  const section = (
    name: InspectorSection,
    body: ReactNode,
    ref?: Ref<HTMLElement>,
  ) => (
    <section
      ref={ref}
      key={name}
      data-section-body={name}
      aria-labelledby={`inspector-${name}`}
      className="grid gap-2 border-b px-3 py-3 last:border-b-0"
    >
      <h3
        id={`inspector-${name}`}
        tabIndex={-1}
        className="text-sm font-semibold text-foreground outline-none focus-visible:underline"
      >
        {names[name]}
      </h3>
      {body}
    </section>
  );

  return (
    <div className="ledger-inspector flex min-h-0 flex-1 flex-col">
      <div className="ledger-inspector-head grid gap-1 border-b px-3 py-2">
        <div className="flex items-start gap-1">
          <div className="grid min-w-0 flex-1">
            <h2 className="text-base font-medium break-words">
              {tx.description}
            </h2>
            <p className="text-sm text-muted-foreground break-words">
              {facts(t, [
                tx.counterparty ||
                  t("desktop.ledger.inspector.no_counterparty"),
                dateText(locale, tx.date, true),
              ])}
            </p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <IconButton label={t("desktop.ledger.inspector.actions")}>
                <Icon name="more" />
              </IconButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                icon="reset"
                disabled={staged === 0}
                onSelect={() => onStage({ type: "revert_movement", id })}
              >
                {t("desktop.ledger.edit.revert_movement")}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                icon="split"
                disabled={tx.lifecycle_state !== "ACTIVE" || sealed}
                onSelect={() => onSplit(row)}
              >
                {t("desktop.ledger.inspector.action.split")}…
              </DropdownMenuItem>
              {cohort.length >= 2 && (
                <DropdownMenuItem
                  icon="merge"
                  onSelect={() => onSelectCohort(cohort)}
                >
                  {t("desktop.ledger.inspector.action.merge_select")}
                </DropdownMenuItem>
              )}
              {lifecycleItems}
              {duplicate && (
                <DropdownMenuItem
                  icon="copy"
                  className="ledger-archive-duplicate"
                  disabled={
                    !lifecycleTakes(
                      "archive",
                      row,
                      sealed ? new Set([id]) : new Set(),
                    )
                  }
                  onSelect={() =>
                    onAction({
                      kind: "archive",
                      ids: [id],
                      reason: t("desktop.ledger.import_issue.duplicate"),
                    })
                  }
                >
                  {t("desktop.ledger.duplicate.archive")}…
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                icon="trash"
                onSelect={() => onAction({ kind: "remove", id })}
              >
                {t("desktop.ledger.inspector.action.remove")}…
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <IconButton
            label={t("desktop.ledger.inspector.close")}
            shortcut={chordText(INSPECTOR_CHORD)}
            aria-keyshortcuts={chordAria(INSPECTOR_CHORD)}
            onClick={onClose}
          >
            <Icon name="close" />
          </IconButton>
        </div>
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium tabular-nums">
            {amountText(locale, tx.amount)}{" "}
            <span className="text-muted-foreground">{tx.currency}</span>
          </span>
          <span>{directionLabel(t, tx.direction)}</span>
          <Badge variant="neutral" data-status={word}>
            {statusLabel(t, word, issueCount)}
          </Badge>
          {duplicate && (
            <Badge variant="neutral" className="ledger-duplicate-badge">
              <Icon name="copy" size="xs" className="text-warning" />
              {t("desktop.ledger.import_issue.duplicate")}
            </Badge>
          )}
          {tx.lifecycle_state !== "ACTIVE" && (
            <Badge variant="neutral">
              {lifecycleLabel(t, tx.lifecycle_state)}
            </Badge>
          )}
        </p>
        {staged > 0 && (
          <p className="ledger-unsaved flex items-center gap-1.5 text-sm">
            <span
              aria-hidden="true"
              className="h-4 border-l-2 border-dashed border-foreground"
            />
            {t("desktop.ledger.inspector.unsaved", { count: staged })}
            <Button
              variant="ghost"
              size="xs"
              onClick={() => onStage({ type: "revert_movement", id })}
            >
              {t("desktop.ledger.inspector.revert")}
            </Button>
          </p>
        )}
        {sealed && (
          <p className="flex items-start gap-1 text-sm text-muted-foreground">
            <Icon name="lock" size="xs" className="mt-0.5" />
            {t("desktop.ledger.inspector.sealed", {
              declarations: listed(
                t,
                sealing.map((use) =>
                  noted(
                    t,
                    declarationName(
                      t,
                      use.modelo,
                      use.period.filing_year,
                      use.period.code,
                    ),
                    revisionStateLabel(t, use),
                  ),
                ),
              ),
            })}
          </p>
        )}
      </div>
      <JumpIndex
        sections={INSPECTOR_SECTIONS}
        current={current}
        onJump={(target) => jump(target)}
        names={names}
        firstRef={indexFirst}
        badges={
          issues.length
            ? {
                classify: {
                  count: issues.length,
                  label: t("desktop.ledger.inspector.issue_count", {
                    count: issues.length,
                  }),
                },
              }
            : undefined
        }
      />
      <div
        ref={scroll}
        tabIndex={0}
        aria-label={t("desktop.ledger.inspector.sections")}
        className="ledger-inspector-body relative min-h-0 flex-1 overflow-y-auto focus-visible:-outline-offset-2"
      >
        {section(
          "classify",
          <ClassifySection
            scope={scope}
            port={port}
            classify={classify}
            issues={issues}
            actions={actions}
            rejectedBefore={
              view?.kind === "ready" &&
              view.result.latest_llm_rejection !== null
            }
            history={history?.kind === "ready" ? history.result : null}
            onFocusField={focusField}
            say={say}
          />,
        )}
        {section(
          "documents",
          <DocumentsSection
            port={port}
            row={row}
            evidence={evidence}
            actions={actions}
            onStage={onStage}
            locale={locale}
            say={say}
          />,
          documentsRef,
        )}
        {section(
          "invoice",
          <InvoiceSection
            row={row}
            rows={rows}
            invoices={invoices}
            actions={actions}
            allActions={stage.content.actions}
            onStage={onStage}
            locale={locale}
            onShow={onShow}
            onOpenInvoice={onOpenInvoice}
            say={say}
          />,
          invoiceRef,
        )}
        {section("details", <DetailsSection scope={scope} track={track} />)}
        {section(
          "history",
          <HistorySection
            row={row}
            changes={changes}
            history={history}
            track={track}
            rows={byId}
            locale={locale}
            onShow={onShow}
          />,
          historyRef,
        )}
      </div>
    </div>
  );
}
