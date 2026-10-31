import { useMemo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { facts } from "../../../shell/compose";
import { useStrings, type Translate } from "../../../shell/strings";
import { ATTENTION_TONE } from "../../modelo/workspace/Marks";
import type { ModeloFormAttention } from "../../../shell/modeloContract";
import { dateText } from "../movements/movementWords";
import { rankDecimal, SetupTable, type Column } from "../setup/SetupParts";
import type { SetupCall } from "../setup/setupModel";
import type {
  ActivityAssetRefusal,
  AssetCounts,
  AssetListRow,
} from "../../../shell/ledgerSetup";
import {
  ASSET_KEYS,
  bajaText,
  COUNT_ICON,
  COUNT_KINDS,
  countWord,
  openingRemedy,
  refusalText,
  tokenWord,
} from "./assetsWords";
import { figureText } from "./planWords";

/** Words the refusal a settled-but-refused call carries, for a `CallLine`. */
export function callRefusal(
  t: Translate,
  call: SetupCall<unknown> | null,
): () => string | null {
  return () => {
    if (call?.kind !== "refused") return null;
    const found = (
      call.detail as { refusal?: ActivityAssetRefusal | null } | null
    )?.refusal;
    return found ? refusalText(t, found) : null;
  };
}

/** How serious each kind of count reads; colour only reinforces the glyph
 * and the words. */
const COUNT_LEVEL: Record<keyof AssetCounts, ModeloFormAttention> = {
  missing: "missing",
  incomplete: "confirm",
  conflict: "blocks",
  unsupported: "check",
  without_tables: "info",
  stale: "check",
};

/** A small mark that says one thing: its words are the accessible name and the
 * tooltip, and it takes keyboard focus so the tooltip needs no mouse. */
export function Hint({
  words,
  className,
  children,
}: {
  words: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          tabIndex={0}
          aria-label={words}
          className={cn(
            "inline-flex items-center gap-1 rounded-full focus-visible:outline-(length:--focus-ring) focus-visible:outline-ring focus-visible:outline-solid",
            className,
          )}
        >
          {children}
        </span>
      </TooltipTrigger>
      <TooltipContent>{words}</TooltipContent>
    </Tooltip>
  );
}

/** A figure the register does not know, drawn as a dashed circle. It is
 * named "Not known" and the tooltip says why. */
export function NotKnown({ why }: { why: string }) {
  const t = useStrings();
  return (
    <Hint words={facts(t, [t(ASSET_KEYS.not_known), why])}>
      <Icon name="unknown" size="xs" className="text-muted-foreground" />
    </Hint>
  );
}

/** A year with nothing recorded in it, drawn as an empty slot: a known state
 * that needs no explanation beyond its name. */
export function NothingRecorded({ why }: { why?: string | null }) {
  const t = useStrings();
  return (
    <Hint words={facts(t, [t(ASSET_KEYS.mark.nothing_recorded), why])}>
      <Icon name="canvas" size="xs" className="text-muted-foreground" />
    </Hint>
  );
}

/** A figure that does not apply to this year, such as one after the basis is
 * spent: known, and drawn as a circle struck through. */
export function NotApplicable({ why }: { why?: string | null }) {
  const t = useStrings();
  return (
    <Hint words={facts(t, [t(ASSET_KEYS.mark.not_applicable), why])}>
      <Icon name="noRate" size="xs" className="text-muted-foreground" />
    </Hint>
  );
}

/** One kind of count as a glyph and its number, the words in the tooltip and
 * the accessible name. */
export function CountPill({
  kind,
  count,
}: {
  kind: keyof AssetCounts;
  count: number;
}) {
  const t = useStrings();
  const words = countWord(t, kind, count);
  return (
    <Hint
      words={words}
      className="bg-secondary px-2 py-0.5 text-xs font-medium tabular-nums text-secondary-foreground"
    >
      <Icon
        name={COUNT_ICON[kind]}
        size="xs"
        className={ATTENTION_TONE[COUNT_LEVEL[kind]]}
      />
      <span aria-hidden="true">{count}</span>
    </Hint>
  );
}

/** The kinds of count that are above none, in the order they are shown. */
export function CountPills({ counts }: { counts: AssetCounts }) {
  return (
    <span className="flex flex-wrap items-center gap-1">
      {COUNT_KINDS.filter((kind) => counts[kind] > 0).map((kind) => (
        <CountPill key={kind} kind={kind} count={counts[kind]} />
      ))}
    </span>
  );
}

/**
 * The register's elements, one row each: name, serial number, kind, method,
 * the day it entered service, where it stands in the register, its basis and
 * what is left of it, and a pill for each kind of year that needs attention.
 * An element out of service stays listed. No identifier is drawn; the name is
 * the way in to the element's detail.
 */
export function AssetList({
  rows,
  selected,
  onSelect,
  locale,
}: {
  rows: readonly AssetListRow[];
  selected: string | null;
  onSelect: (assetId: string) => void;
  locale: string;
}) {
  const t = useStrings();
  const columns = useMemo<Column<AssetListRow>[]>(
    () => [
      {
        key: "name",
        label: t(ASSET_KEYS.list.column.name),
        sort: (row) => row.name,
        cell: (row) => (
          <Button
            variant="link"
            size="xs"
            className="h-auto min-w-0 p-0 text-left whitespace-normal"
            onClick={() => onSelect(row.asset_id)}
          >
            {row.name ?? t(ASSET_KEYS.list.no_name)}
          </Button>
        ),
      },
      {
        key: "serial",
        label: t(ASSET_KEYS.list.column.serial),
        sort: (row) => row.serial_number,
        cell: (row) =>
          row.serial_number ?? (
            <NothingRecorded why={t(ASSET_KEYS.list.serial_missing)} />
          ),
      },
      {
        key: "kind",
        label: t(ASSET_KEYS.list.column.kind),
        sort: (row) => tokenWord(t, "asset_kind", row.asset_kind),
        cell: (row) => tokenWord(t, "asset_kind", row.asset_kind),
      },
      {
        key: "method",
        label: t(ASSET_KEYS.list.column.method),
        sort: (row) => tokenWord(t, "method", row.method),
        cell: (row) => tokenWord(t, "method", row.method),
      },
      {
        key: "in_service",
        label: t(ASSET_KEYS.list.column.in_service),
        sort: (row) => row.in_service_date,
        cell: (row) => (
          <span className="whitespace-nowrap">
            {dateText(locale, row.in_service_date, true)}
          </span>
        ),
      },
      {
        key: "state",
        label: t(ASSET_KEYS.list.column.state),
        sort: (row) => tokenWord(t, "register_state", row.state),
        cell: (row) => tokenWord(t, "register_state", row.state),
      },
      {
        key: "basis",
        label: t(ASSET_KEYS.list.column.basis),
        numeric: true,
        sort: (row) => rankDecimal(row.basis.decimal),
        cell: (row) => (
          <span className="whitespace-nowrap">
            {figureText(locale, row.basis)}
          </span>
        ),
      },
      {
        key: "pending",
        label: t(ASSET_KEYS.list.column.pending),
        numeric: true,
        sort: (row) =>
          rankDecimal(row.pending_applies ? row.pending?.decimal : undefined),
        cell: (row) => {
          // After a baja nothing is left to amortize: the figure is not
          // drawn, and the mark says why.
          if (!row.pending_applies)
            return (
              <NotApplicable
                why={
                  row.disposal === null
                    ? null
                    : bajaText(t, locale, row.disposal)
                }
              />
            );
          const pending = figureText(locale, row.pending);
          return pending === null ? (
            <NotKnown why={openingRemedy(t)} />
          ) : (
            <span className="whitespace-nowrap">{pending}</span>
          );
        },
      },
      {
        key: "findings",
        label: t(ASSET_KEYS.plan.column.status),
        cell: (row) => <CountPills counts={row.findings} />,
      },
    ],
    [t, locale, onSelect],
  );
  return (
    <SetupTable
      label={t(ASSET_KEYS.list.label)}
      rows={rows}
      rowKey={(row) => row.asset_id}
      columns={columns}
      selected={selected}
      className="ledger-assets-list"
    />
  );
}
