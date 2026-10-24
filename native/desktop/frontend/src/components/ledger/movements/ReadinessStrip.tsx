import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { readinessSnapshot, type Readiness } from "../../../shell/ledgerWindow";
import { useStrings, type Translate } from "../../../shell/strings";
import type {
  MovementFilters,
  ReadinessFilter,
  ReadinessSets,
} from "./movementsModel";
import { reasonDetail, reasonShort } from "./movementWords";

/** How many reason chips show before the rest fold behind "+n". */
const REASONS_SHOWN = 4;

type Pill = {
  key: string;
  icon: IconName;
  tone: "warning" | "success" | "neutral";
  count?: number;
  label: string;
  /** What pressing it filters to; a pill without one only says. */
  filter?: ReadinessFilter;
  /** The share of what it counts that a staged change classifies. */
  staged?: number;
};

/** A pill's sentence and its notes, as one line. */
const said = (...parts: string[]) => parts.filter(Boolean).join(" · ");

function pillsOf(
  t: Translate,
  locale: string,
  readiness: Readiness,
  sets: ReadinessSets,
  notes: { unsaved: number; stagedClassify: number; partial: boolean },
): Pill[] {
  const unsaved =
    notes.unsaved > 0
      ? t("desktop.ledger.readiness.unsaved", { count: notes.unsaved })
      : "";
  const partial = notes.partial
    ? t("desktop.ledger.readiness.loaded_only")
    : "";
  const pills: Pill[] = [];
  const snapshot = readinessSnapshot(readiness);
  const unknown = (label: string) =>
    pills.push({ key: "unknown", icon: "unknown", tone: "neutral", label });
  let ready: boolean | null = null;
  if (!snapshot)
    unknown(
      t(
        readiness.kind === "checking"
          ? "desktop.ledger.readiness.checking"
          : readiness.kind === "failed"
            ? "desktop.ledger.readiness.failed"
            : "desktop.ledger.readiness.not_checked",
      ),
    );
  // Staged changes leave the stored data as it was checked; saved ones do
  // not.
  else if (snapshot.savedSince > 0)
    unknown(
      t("desktop.ledger.readiness.out_of_date", {
        count: snapshot.savedSince,
      }),
    );
  else {
    ready = snapshot.preflight
      ? snapshot.preflight.ready
      : snapshot.status.ready;
    if (ready === null) unknown(t("desktop.ledger.readiness.not_measured"));
  }
  const checked =
    snapshot !== null && snapshot.savedSince === 0 && ready !== null;
  const fix = sets.fix.size;
  // Not ready with nothing this strip counts is still said, without a count.
  if (
    checked &&
    (fix > 0 ||
      (ready === false && sets.toClassify.size === 0 && sets.noRate.size === 0))
  )
    pills.push({
      key: "issues",
      icon: "alert",
      tone: "warning",
      ...(fix > 0 ? { count: fix, filter: "issues" as const } : {}),
      label: said(
        t("desktop.ledger.readiness.not_ready", { count: fix }),
        unsaved,
        partial,
      ),
    });
  const toClassify = sets.toClassify.size;
  if (toClassify > 0)
    pills.push({
      key: "to_classify",
      icon: "pending",
      tone: "neutral",
      count: toClassify,
      filter: "to_classify",
      staged: notes.stagedClassify / toClassify,
      label: said(
        t("desktop.ledger.count.to_classify", { count: toClassify }),
        notes.stagedClassify > 0
          ? t("desktop.ledger.readiness.staged", {
              count: notes.stagedClassify,
            })
          : "",
        unsaved,
        partial,
      ),
    });
  const noRate = sets.noRate.size;
  if (noRate > 0)
    pills.push({
      key: "no_rate",
      icon: "noRate",
      tone: "neutral",
      count: noRate,
      filter: "no_rate",
      label: said(
        t("desktop.ledger.readiness.no_rate", { count: noRate }),
        partial,
      ),
    });
  if (checked && ready && pills.length === 0 && snapshot)
    pills.push({
      key: "ready",
      icon: "check",
      tone: "success",
      label: t("desktop.ledger.readiness.ready", {
        time: new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(
          new Date(snapshot.checkedAt),
        ),
      }),
    });
  return pills;
}

/**
 * The period's readiness as it was last checked and as the stored rows
 * stand: a glyph and a count for each thing counted, hidden at zero, the
 * sentence in its tooltip and name. A pill that counts movements filters
 * the grid to exactly those it counts; a reason chip does the same for its
 * reason, and leads to the fix.
 */
export function ReadinessStrip({
  readiness,
  sets,
  filters,
  locale,
  unsaved,
  stagedClassify,
  partial,
  onPill,
  onReason,
  duplicates = 0,
  duplicatesShown = false,
  onDuplicates,
}: {
  readiness: Readiness;
  sets: ReadinessSets;
  filters: MovementFilters;
  locale: string;
  /** Movements and new movements with unsaved changes, which no count
   * includes. */
  unsaved: number;
  /** Movements to classify whose staged change classifies them. */
  stagedClassify: number;
  partial: boolean;
  onPill: (filter: ReadinessFilter | null) => void;
  onReason: (reason: string | null) => void;
  /** Movements an import flagged as likely duplicates, which a chip
   * shows. */
  duplicates?: number;
  duplicatesShown?: boolean;
  onDuplicates?: (show: boolean) => void;
}) {
  const t = useStrings();
  const [more, setMore] = useState(false);
  const pills = pillsOf(t, locale, readiness, sets, {
    unsaved,
    stagedClassify,
    partial,
  });
  const snapshot = readinessSnapshot(readiness);
  const current = snapshot !== null && snapshot.savedSince === 0;
  const reasons = current ? sets.reasons : [];
  const shown = more ? reasons : reasons.slice(0, REASONS_SHOWN);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <ul
        aria-label={t("desktop.ledger.readiness.title")}
        className="ledger-readiness flex flex-wrap items-center gap-1.5"
      >
        {pills.map((pill) => {
          const icon = (
            <Icon
              name={pill.icon}
              size="xs"
              className={
                pill.tone === "warning" && pill.filter
                  ? "text-warning"
                  : undefined
              }
            />
          );
          const body = (
            <>
              {icon}
              {pill.count !== undefined && (
                <span aria-hidden="true">{pill.count}</span>
              )}
              <span className="sr-only">{pill.label}</span>
              {pill.staged !== undefined && pill.staged > 0 && (
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 bottom-0 h-(--mark-edge) origin-left bg-foreground"
                  style={{ transform: `scaleX(${Math.min(1, pill.staged)})` }}
                />
              )}
            </>
          );
          const filter = pill.filter;
          return (
            <li key={pill.key} data-readiness={pill.key}>
              <Tooltip>
                <TooltipTrigger asChild>
                  {filter ? (
                    <Button
                      variant="pill"
                      size="xs"
                      className="relative overflow-hidden tabular-nums"
                      aria-pressed={filters.readiness === filter}
                      onClick={() =>
                        onPill(filters.readiness === filter ? null : filter)
                      }
                    >
                      {body}
                    </Button>
                  ) : (
                    <Badge
                      variant={pill.tone}
                      className="tabular-nums"
                      tabIndex={0}
                    >
                      {body}
                    </Badge>
                  )}
                </TooltipTrigger>
                <TooltipContent>{pill.label}</TooltipContent>
              </Tooltip>
            </li>
          );
        })}
      </ul>
      {duplicates > 0 && onDuplicates && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="pill"
              size="xs"
              className="ledger-duplicates"
              aria-pressed={duplicatesShown}
              onClick={() => onDuplicates(!duplicatesShown)}
            >
              <Icon name="copy" size="xs" className="text-warning" />
              <span aria-hidden="true">
                {t("desktop.ledger.duplicate.chip")}
              </span>
              <span aria-hidden="true" className="tabular-nums">
                {duplicates}
              </span>
              <span className="sr-only">
                {t("desktop.ledger.duplicate.chip_name", { count: duplicates })}
              </span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {t("desktop.ledger.duplicate.chip_name", { count: duplicates })}
          </TooltipContent>
        </Tooltip>
      )}
      {reasons.length > 0 && (
        <ul
          aria-label={t("desktop.ledger.readiness.reasons")}
          className="ledger-reasons flex flex-wrap items-center gap-1.5"
        >
          {shown.map(({ reason, ids }) => (
            <li key={reason} data-reason={reason}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="pill"
                    size="xs"
                    aria-pressed={filters.reason === reason}
                    onClick={() =>
                      onReason(filters.reason === reason ? null : reason)
                    }
                  >
                    {reasonShort(t, reason)}
                    <span className="tabular-nums">{ids.size}</span>
                    <span className="sr-only">
                      {t("desktop.ledger.readiness.reason_name", {
                        reason: reasonDetail(t, reason),
                        count: ids.size,
                      })}
                    </span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {reasonDetail(t, reason)} · {ids.size}
                </TooltipContent>
              </Tooltip>
            </li>
          ))}
          {reasons.length > REASONS_SHOWN && (
            <li>
              <Button
                variant="pill"
                size="xs"
                aria-expanded={more}
                aria-label={
                  more
                    ? t("desktop.ledger.readiness.fewer")
                    : t("desktop.ledger.readiness.more_name", {
                        count: reasons.length - REASONS_SHOWN,
                      })
                }
                onClick={() => setMore(!more)}
              >
                {more
                  ? t("desktop.ledger.readiness.fewer")
                  : t("desktop.ledger.readiness.more", {
                      count: reasons.length - REASONS_SHOWN,
                    })}
              </Button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
