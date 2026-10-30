import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  COUNT_ICON,
  COUNT_KINDS,
  countWord,
  refusalText,
  tokenWord,
} from "./assetsWords";
import { DASH, figureText } from "./planWords";

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
  stale: "check",
};

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
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          aria-label={words}
          className="inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium tabular-nums text-secondary-foreground"
        >
          <Icon
            name={COUNT_ICON[kind]}
            size="xs"
            className={ATTENTION_TONE[COUNT_LEVEL[kind]]}
          />
          <span aria-hidden="true">{count}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{words}</TooltipContent>
    </Tooltip>
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
        cell: (row) => row.serial_number ?? DASH,
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
        cell: (row) => dateText(locale, row.in_service_date, true),
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
        cell: (row) => figureText(locale, row.basis),
      },
      {
        key: "pending",
        label: t(ASSET_KEYS.list.column.pending),
        numeric: true,
        sort: (row) => rankDecimal(row.pending?.decimal),
        cell: (row) => figureText(locale, row.pending) ?? DASH,
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
