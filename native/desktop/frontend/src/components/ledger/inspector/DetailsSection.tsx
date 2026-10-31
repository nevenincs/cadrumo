import { Icon } from "@/components/ui/icon";
import { facts } from "@/shell/compose";
import type { LedgerTrackResult } from "../../../shell/ledger";
import { effectiveFacts } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { periodText } from "../ledgerWords";
import { InspectorField } from "./InspectorField";
import { quarterMove } from "./inspectorModel";
import { declarationName } from "./inspectorWords";
import { stagedField, type FieldScope } from "./movementFields";
import type { InspectorRead } from "./useInspectorReads";
import { formatAmount } from "../../../shared/numbers";
import { formatDay, formatTime } from "../../../shared/dateFormats";

/**
 * The inspector's Details section: every fact of the movement, the ones the
 * grid does not show among them, and where it came from.
 * A change to a date that moves the movement to another quarter says which
 * declarations it affects.
 */
export function DetailsSection({
  scope,
  track,
}: {
  scope: FieldScope;
  track: InspectorRead<LedgerTrackResult> | null;
}) {
  const t = useStrings();
  const { row, changes, locale } = scope;
  const tx = row.transaction;
  const effective = effectiveFacts(row, changes);
  const moved = quarterMove(tx, effective);
  const tracked = track?.kind === "ready" ? track.result : null;
  const uses = tracked?.participated_in ?? [];
  const moveNote = moved
    ? facts(t, [
        t("desktop.ledger.inspector.moves_to", {
          period: periodText(t, locale, moved.to),
        }),
        ...uses.map((use) =>
          t("desktop.ledger.inspector.affects", {
            declaration: declarationName(
              t,
              use.modelo,
              use.period.filing_year,
              use.period.code,
            ),
          }),
        ),
      ])
    : null;
  const identity =
    changes?.amount || changes?.description || changes?.own_account_id
      ? t("desktop.ledger.inspector.new_identity")
      : null;
  const provenance = tracked?.imported_provenance ?? null;
  const field = (
    name: Parameters<typeof stagedField>[1],
    kind: Parameters<typeof stagedField>[2],
    note?: string | null,
  ) => (
    <InspectorField
      key={name}
      {...stagedField(scope, name, kind)}
      note={note ?? undefined}
    />
  );

  return (
    <div className="grid gap-3">
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5">
        <dt className="pt-1 text-sm text-muted-foreground">
          {t("desktop.ledger.inspector.effective_date")}
        </dt>
        <dd className="px-1.5 py-1 text-sm tabular-nums">
          {formatDay(locale, tx.date)}
          <span className="block text-xs text-muted-foreground">
            {tx.value_date
              ? t("desktop.ledger.inspector.from_value_date")
              : t("desktop.ledger.inspector.from_booked_date")}
          </span>
        </dd>
        {field("booked_date", "date", changes?.booked_date ? moveNote : null)}
        {field("value_date", "date", changes?.value_date ? moveNote : null)}
        {field("amount", "amount", changes?.amount ? identity : null)}
        {field("direction", "direction")}
        {field("currency", "currency")}
        <dt className="pt-1 text-sm text-muted-foreground">
          {t("desktop.ledger.inspector.eur_value")}
        </dt>
        <dd className="px-1.5 py-1 text-sm">
          {tx.currency === "EUR" ? (
            <span className="text-muted-foreground">
              {t("desktop.ledger.inspector.eur_same")}
            </span>
          ) : tx.value_in_eur !== null ? (
            <span className="grid">
              <span className="font-medium tabular-nums">
                {formatAmount(locale, tx.value_in_eur)} EUR
              </span>
              {tx.fx_rate && (
                <span className="text-xs text-muted-foreground">
                  {t("desktop.ledger.inspector.fx_rate", { rate: tx.fx_rate })}
                </span>
              )}
            </span>
          ) : (
            <span className="grid">
              <span className="flex items-center gap-1">
                <Icon name="noRate" size="xs" />
                {t("desktop.ledger.inspector.no_rate")}
              </span>
              <span className="text-xs text-muted-foreground">
                {t("desktop.ledger.inspector.no_rate_detail")}
              </span>
            </span>
          )}
        </dd>
        {field("description", "text", changes?.description ? identity : null)}
        {field("counterparty", "text")}
        {field("counterparty_country", "country")}
        {field("counterparty_identification_state", "country")}
        <dt className="pt-1 text-sm text-muted-foreground">
          {t("desktop.ledger.inspector.source_jurisdiction")}
        </dt>
        <dd className="px-1.5 py-1 text-sm">
          {tx.source_jurisdiction ?? (
            <span className="text-muted-foreground">
              {t("desktop.ledger.inspector.not_stated")}
            </span>
          )}
        </dd>
        {field(
          "own_account_id",
          "account",
          changes?.own_account_id ? identity : null,
        )}
        {field("group_label", "text")}
        {field("notes", "text")}
      </dl>

      <dl className="ledger-provenance grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted-foreground">
          {t("desktop.ledger.inspector.came_from")}
        </dt>
        <dd className="break-words">
          {track === null || track.kind === "reading"
            ? t("desktop.ledger.loading")
            : track.kind === "failed"
              ? t("desktop.ledger.inspector.unread")
              : provenance
                ? t("desktop.ledger.inspector.file_row", {
                    file: provenance.source_filename,
                    row: provenance.source_row_index,
                  })
                : t("desktop.ledger.inspector.added_by_hand")}
        </dd>
        {provenance && (
          <>
            <dt className="text-muted-foreground">
              {t("desktop.ledger.inspector.read_as")}
            </dt>
            <dd>{provenance.provider_name}</dd>
            <dt className="text-muted-foreground">
              {t("desktop.ledger.inspector.imported")}
            </dt>
            <dd>{formatTime(locale, provenance.ingested_at)}</dd>
          </>
        )}
        <dt className="text-muted-foreground">
          {t("desktop.ledger.inspector.added")}
        </dt>
        <dd>{formatTime(locale, tx.created_at)}</dd>
        <dt className="text-muted-foreground">
          {t("desktop.ledger.inspector.last_saved")}
        </dt>
        <dd>{formatTime(locale, tx.modified_at)}</dd>
      </dl>
    </div>
  );
}
