import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useStrings, type Translate } from "../../../shell/strings";
import { ATTENTION_TONE, GlyphMark } from "../../modelo/workspace/Marks";
import type { ModeloFormAttention } from "../../../shell/modeloContract";
import { dateText } from "../movements/movementWords";
import { SetupTable, type Column } from "../setup/SetupParts";
import type { SetupCall } from "../setup/setupModel";
import type { AssetCounts, AssetListRow } from "./assetsContract";
import { ASSET_KEYS, COUNT_ICON, COUNT_KINDS, countWord } from "./assetsWords";

/** A token the backend states, in the chrome's words for it; "other" where
 * the chrome has none, never the raw token. */
export function tokenWord(
  t: Translate,
  family: "kind" | "method" | "reason",
  token: string,
): string {
  const key = `desktop.ledger.assets.option.${family}.${token}`;
  // A catalogue without the key answers with the key itself.
  const word = /^[a-z0-9_]+$/.test(token) ? t(key) : key;
  return word === key
    ? t(`desktop.ledger.assets.option.${family}.other`)
    : word;
}

/** A refusal in words: its own where the chrome has them, else the code. */
export function refusalText(
  t: Translate,
  refusal: { code: string } | null,
): string {
  const code = (refusal?.code ?? "").toLowerCase();
  const key = `desktop.ledger.assets.refusal.${code}`;
  const word = /^[a-z0-9_]+$/.test(code) ? t(key) : key;
  return word === key
    ? t("desktop.ledger.form.refused", { code: refusal?.code || "refused" })
    : word;
}

/** Words the refusal a settled-but-refused call carries, for a `CallLine`. */
export function callRefusal(
  t: Translate,
  call: SetupCall<unknown> | null,
): () => string | null {
  return () => {
    if (call?.kind !== "refused") return null;
    const found = (call.detail as { refusal?: { code: string } | null } | null)
      ?.refusal;
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

const DASH = "—";

/**
 * The register's elements, one row each: name, serial, kind, method, the day
 * it entered service, a baja mark where it has one and a pill for each kind
 * of year that needs attention. An element given a baja stays listed. No
 * identifier is drawn; the name is the way in to the element's detail.
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
          <span className="flex items-center gap-1.5">
            <Button
              variant="link"
              size="xs"
              className="h-auto min-w-0 p-0 text-left whitespace-normal"
              onClick={() => onSelect(row.asset_id)}
            >
              {row.name ?? t(ASSET_KEYS.list.no_name)}
            </Button>
            {row.baja && (
              <GlyphMark
                icon="archive"
                words={t(ASSET_KEYS.list.disposed, {
                  date: dateText(locale, row.baja.date, true),
                })}
                className="text-muted-foreground"
              />
            )}
          </span>
        ),
      },
      {
        key: "serial",
        label: t(ASSET_KEYS.list.column.serial),
        sort: (row) => row.serial,
        cell: (row) => row.serial ?? DASH,
      },
      {
        key: "kind",
        label: t(ASSET_KEYS.list.column.kind),
        sort: (row) => tokenWord(t, "kind", row.kind_key),
        cell: (row) => tokenWord(t, "kind", row.kind_key),
      },
      {
        key: "method",
        label: t(ASSET_KEYS.list.column.method),
        sort: (row) => tokenWord(t, "method", row.method_key),
        cell: (row) => tokenWord(t, "method", row.method_key),
      },
      {
        key: "in_service",
        label: t(ASSET_KEYS.list.column.in_service),
        sort: (row) => row.in_service_date,
        cell: (row) => dateText(locale, row.in_service_date, true),
      },
      {
        key: "status",
        label: t(ASSET_KEYS.plan.column.status),
        cell: (row) => <CountPills counts={row.counts} />,
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
