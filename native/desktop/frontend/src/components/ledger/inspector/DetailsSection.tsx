import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { LedgerTrackResult } from "../../../shell/ledger";
import { effectiveFacts } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { amountText, dateText, stampText } from "../movements/movementWords";
import { periodText } from "../ledgerWords";
import { InspectorField } from "./InspectorField";
import { quarterMove } from "./inspectorModel";
import { declarationName } from "./inspectorWords";
import { stagedField, type FieldScope } from "./movementFields";
import type { InspectorRead } from "./useInspectorReads";

/**
 * The inspector's Details section: every fact of the movement, the ones the
 * grid does not show among them, where it came from, and its identities.
 * A change to a date that moves the movement to another quarter says which
 * declarations it affects.
 */
export function DetailsSection({
  scope,
  track,
  copy,
  say,
}: {
  scope: FieldScope;
  track: InspectorRead<LedgerTrackResult> | null;
  copy: (text: string) => Promise<void>;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const { row, changes, locale } = scope;
  const tx = row.transaction;
  const facts = effectiveFacts(row, changes);
  const moved = quarterMove(tx, facts);
  const tracked = track?.kind === "ready" ? track.result : null;
  const uses = tracked?.participated_in ?? [];
  const moveNote = moved
    ? [
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
      ].join(" · ")
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
          {dateText(locale, tx.date, true)}
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
                {amountText(locale, tx.value_in_eur)} EUR
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
            <dd>{stampText(locale, provenance.ingested_at)}</dd>
          </>
        )}
        <dt className="text-muted-foreground">
          {t("desktop.ledger.inspector.added")}
        </dt>
        <dd>{stampText(locale, tx.created_at)}</dd>
        <dt className="text-muted-foreground">
          {t("desktop.ledger.inspector.last_saved")}
        </dt>
        <dd>{stampText(locale, tx.modified_at)}</dd>
      </dl>

      <details className="ledger-technical">
        <summary className="cursor-pointer text-sm text-muted-foreground">
          {t("desktop.ledger.inspector.technical")}
        </summary>
        <dl className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 font-mono text-xs">
          <dt className="font-sans text-muted-foreground">
            {t("desktop.ledger.inspector.movement_id")}
          </dt>
          <dd className="flex items-center gap-1 break-all">
            {tx.transaction_id}
            <IconButton
              label={t("desktop.ledger.inspector.copy_id")}
              onClick={() =>
                void copy(tx.transaction_id).then(() =>
                  say(t("desktop.ledger.inspector.copied_id")),
                )
              }
            >
              <Icon name="copy" size="xs" />
            </IconButton>
          </dd>
          {provenance?.import_fingerprint && (
            <>
              <dt className="font-sans text-muted-foreground">
                {t("desktop.ledger.inspector.fingerprint")}
              </dt>
              <dd className="break-all">{provenance.import_fingerprint}</dd>
            </>
          )}
          {(tracked?.tracking.edit_lineage.length ?? 0) > 0 && (
            <>
              <dt className="font-sans text-muted-foreground">
                {t("desktop.ledger.inspector.earlier_ids")}
              </dt>
              <dd className="break-all">
                {tracked!.tracking.edit_lineage
                  .map((entry) => entry.previous_transaction_id)
                  .join(", ")}
              </dd>
            </>
          )}
        </dl>
      </details>
    </div>
  );
}
