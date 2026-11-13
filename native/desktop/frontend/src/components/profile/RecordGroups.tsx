import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { formatDay } from "@/shared/dateFormats";
import { formatAmount } from "@/shared/numbers";
import type {
  ProfileRecordAction,
  ProfileRecordLedgerRowItem,
  ProfileRecordMemberItem,
  ProfileRecordReduction,
  ProfileRecordReductionYear,
} from "../../shell/profileContract";
import type {
  RecordGroupBlock,
  RecordGroupStream,
} from "../../shell/profileRecordGroups";
import type { RefusalIntent, ServedRefusal } from "../../shell/refusal";
import { SOURCE_LOCALE, useStrings } from "../../shell/strings";
import { RefusalNotice } from "../RefusalNotice";
import { directionLabel } from "../ledger/movements/movementWords";

// The profile's record groups, drawn exactly as the record-group read serves
// them: each group a card with its served kind and summary, the rows that name
// it indented under the row their served `parent_ref` names with their served
// relation words, and the ledger rows linked to it with the served words of
// their expense concept. Every kind is drawn the same way, so the element
// takes any family of related rows. A member that states a reduction draws it
// as served: its title, each fact with its served words and whether it is
// stated, and each year's outcome and tier words, with the fact that keeps a
// year from being determined and the door that states it. Every door is a
// served registered operation with its served label, handed to the owner with
// the field it opens on (none opens the row as a whole); a refusal the owner
// holds is drawn on the row it names through the window's one refusal notice.

/** A door chosen on a stored row: the row's identity and the served door,
 * whose `field_key` names the field it opens on, or none for the whole row. */
export type RecordDoorChoice = {
  /** The row's identity, `section.row`, as the read serves it. */
  rowRef: string;
  sectionKey: string;
  rowKey: string;
  action: ProfileRecordAction;
};

/** A refusal the owner holds for one row, named by its served identity. */
export type RecordRefusal = { rowRef: string; refusal: ServedRefusal };

export type RecordGroupsState = "reading" | "ready" | "failed";

export type RecordGroupsProps = {
  /** Each kind's groups as read so far, in the kinds' served order. */
  streams: readonly RecordGroupStream[];
  state: RecordGroupsState;
  /** Reads the next page of the first kind whose read continues. */
  onMore?: () => void;
  /** Reads every kind again from its first page. */
  onReadAgain?: () => void;
  onDoor?: (choice: RecordDoorChoice) => void;
  refusal?: RecordRefusal | null;
  onRefusalAction?: (intent: RefusalIntent) => void;
  /** Whether this window may write the profile now. */
  writable?: boolean;
};

function Doors({
  actions,
  rowRef,
  sectionKey,
  rowKey,
  props,
}: {
  actions: readonly ProfileRecordAction[];
  rowRef: string;
  sectionKey: string;
  rowKey: string;
  props: RecordGroupsProps;
}) {
  const onDoor = props.onDoor;
  if (!onDoor || actions.length === 0) return null;
  return (
    <span className="flex shrink-0 flex-wrap gap-1">
      {actions.map((action) => (
        <Button
          key={`${action.door}:${action.field_key ?? ""}`}
          size="xs"
          variant="ghost"
          lang={action.label_words_language}
          disabled={props.writable === false}
          data-record-door={action.operation_definition_id}
          data-record-door-field={action.field_key ?? ""}
          onClick={() => onDoor({ rowRef, sectionKey, rowKey, action })}
        >
          <Icon name={action.door === "remove" ? "trash" : "edit"} size="xs" />
          {action.label_words}
        </Button>
      ))}
    </span>
  );
}

function Refused({
  rowRef,
  props,
}: {
  rowRef: string;
  props: RecordGroupsProps;
}) {
  const refusal = props.refusal;
  if (!refusal || refusal.rowRef !== rowRef) return null;
  return (
    <RefusalNotice
      refusal={refusal.refusal}
      onAction={(intent) => props.onRefusalAction?.(intent)}
    />
  );
}

function ReductionYear({
  year,
  member,
  props,
}: {
  year: ProfileRecordReductionYear;
  member: ProfileRecordMemberItem;
  props: RecordGroupsProps;
}) {
  const missing = year.missing_fact;
  return (
    <li
      data-record-reduction-year={year.ejercicio ?? ""}
      data-record-reduction-outcome={year.outcome}
      className="flex flex-col gap-1"
    >
      <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
        {year.ejercicio !== null && (
          <span className="font-medium tabular-nums text-foreground">
            {year.ejercicio}
          </span>
        )}
        <span
          lang={year.outcome_words_language}
          className="min-w-0 break-words text-foreground"
        >
          {year.outcome_words}
        </span>
        {year.tier_words !== null && (
          <span
            data-record-reduction-tier=""
            lang={year.tier_words_language ?? undefined}
            className="text-muted-foreground"
          >
            {year.tier_words}
          </span>
        )}
      </div>
      {missing !== null && (
        <div
          data-record-reduction-missing={missing.field_key}
          className="flex items-start gap-3"
        >
          <span
            lang={missing.fact_words_language}
            className="min-w-0 flex-1 break-words text-sm text-warning"
          >
            {missing.fact_words}
          </span>
          <Doors
            actions={[missing.way_out]}
            rowRef={member.row_ref}
            sectionKey={member.section_key}
            rowKey={member.row_key}
            props={props}
          />
        </div>
      )}
    </li>
  );
}

function Reduction({
  reduction,
  member,
  props,
}: {
  reduction: ProfileRecordReduction;
  member: ProfileRecordMemberItem;
  props: RecordGroupsProps;
}) {
  const t = useStrings();
  const heading = useId();
  return (
    <section
      aria-labelledby={heading}
      data-record-reduction=""
      className="flex flex-col gap-1.5 border-t border-border pt-2"
    >
      <h5
        id={heading}
        lang={reduction.title_words_language}
        className="text-sm font-medium text-foreground"
      >
        {reduction.title_words}
      </h5>
      {reduction.facts.length > 0 && (
        <ul className="flex flex-col gap-0.5">
          {reduction.facts.map((fact) => (
            <li
              key={fact.field_key}
              data-record-reduction-fact={fact.field_key}
              data-stated={fact.stated}
              className="flex flex-wrap items-baseline gap-x-2 text-sm"
            >
              <span
                lang={fact.fact_words_language}
                className="min-w-0 break-words text-foreground"
              >
                {fact.fact_words}
              </span>
              <span className="text-muted-foreground">
                {t(
                  fact.stated
                    ? "desktop.profile.record_groups.reduction.fact_stated"
                    : "desktop.profile.record_groups.reduction.fact_not_stated",
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {reduction.years.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {reduction.years.map((year, index) => (
            <ReductionYear
              key={`${year.ejercicio ?? ""}:${index}`}
              year={year}
              member={member}
              props={props}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function LedgerRow({ row }: { row: ProfileRecordLedgerRowItem }) {
  const t = useStrings();
  const locale = t.locale ?? SOURCE_LOCALE;
  return (
    <li
      data-record-ledger-row={row.transaction_id}
      className="flex flex-wrap items-baseline gap-x-2 text-sm"
    >
      <span className="text-muted-foreground tabular-nums">
        {formatDay(locale, row.booked_date)}
      </span>
      <span className="text-muted-foreground">
        {directionLabel(t, row.direction)}
      </span>
      <span className="tabular-nums text-foreground">
        {formatAmount(locale, row.amount.decimal, { currency: row.currency })}
      </span>
      <span className="min-w-0 break-words text-foreground">
        {row.description}
      </span>
      {row.concept_words !== null && (
        <span
          data-record-concept=""
          lang={row.concept_words_language ?? undefined}
          className="text-muted-foreground"
        >
          {row.concept_words}
        </span>
      )}
    </li>
  );
}

function LinkedRows({ block }: { block: RecordGroupBlock }) {
  const t = useStrings();
  const heading = useId();
  const total = block.group.ledger_row_count;
  const shown = block.ledgerRows.length;
  return (
    <section
      aria-labelledby={heading}
      data-record-linked-rows=""
      className="flex flex-col gap-1.5"
    >
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h5 id={heading} className="text-sm font-medium text-foreground">
          {t("desktop.profile.record_groups.linked_rows")}
        </h5>
        {shown < total && (
          <span className="text-sm text-muted-foreground tabular-nums">
            {t("desktop.profile.record_groups.linked_rows_shown", {
              shown,
              total,
            })}
          </span>
        )}
      </div>
      {total === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.profile.record_groups.linked_rows_none")}
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {block.ledgerRows.map((row) => (
            <LedgerRow key={row.transaction_id} row={row} />
          ))}
        </ul>
      )}
    </section>
  );
}

function GroupCard({
  block,
  props,
}: {
  block: RecordGroupBlock;
  props: RecordGroupsProps;
}) {
  const heading = useId();
  const group = block.group;
  return (
    <section
      aria-labelledby={heading}
      data-record-group={group.group_key}
      data-record-kind={group.payload_kind}
      className="flex flex-col gap-3 rounded-lg border border-border bg-background p-3"
    >
      <div className="flex items-start gap-3">
        <div className="flex min-w-0 flex-1 flex-col">
          <span
            lang={group.kind_words_language}
            className="text-sm text-muted-foreground"
          >
            {group.kind_words}
          </span>
          <h4
            id={heading}
            lang={group.summary_words_language}
            className="break-words text-base font-medium text-foreground"
          >
            {group.summary_words}
          </h4>
        </div>
        <Doors
          actions={group.actions}
          rowRef={group.group_key}
          sectionKey={group.section_key}
          rowKey={group.row_key}
          props={props}
        />
      </div>
      <Refused rowRef={group.group_key} props={props} />
      {block.members.length > 0 && (
        <ul className="flex flex-col gap-2">
          {block.members.map(({ item, depth }) => (
            <li
              key={item.row_ref}
              data-record-member={item.row_ref}
              data-record-parent={item.parent_ref}
              style={{ marginInlineStart: `${(depth - 1) * 1.5}rem` }}
              className="flex flex-col gap-1 rounded-md border border-border px-3 py-2"
            >
              <div className="flex items-start gap-3">
                <div className="flex min-w-0 flex-1 flex-col">
                  <span
                    lang={item.relation_words_language}
                    className="text-sm text-muted-foreground"
                  >
                    {item.relation_words}
                  </span>
                  <span
                    lang={item.summary_words_language}
                    className="break-words text-sm text-foreground"
                  >
                    <span lang={item.kind_words_language} className="sr-only">
                      {item.kind_words}
                    </span>
                    {item.summary_words}
                  </span>
                </div>
                <Doors
                  actions={item.actions}
                  rowRef={item.row_ref}
                  sectionKey={item.section_key}
                  rowKey={item.row_key}
                  props={props}
                />
              </div>
              {item.reduction !== null && (
                <Reduction
                  reduction={item.reduction}
                  member={item}
                  props={props}
                />
              )}
              <Refused rowRef={item.row_ref} props={props} />
            </li>
          ))}
        </ul>
      )}
      <LinkedRows block={block} />
    </section>
  );
}

/**
 * The record groups element. It draws the streams its owner read and hands
 * every door, the next page and a fresh read to the owner.
 */
export function RecordGroups(props: RecordGroupsProps) {
  const t = useStrings();
  const heading = useId();
  const blocks = props.streams.flatMap((stream) => stream.blocks);
  const refusal =
    props.streams.find((stream) => stream.refusal !== null)?.refusal ?? null;
  const continues = props.streams.some((stream) => stream.nextCursor !== null);
  const reading = props.state === "reading";
  return (
    <section
      aria-labelledby={heading}
      aria-busy={reading}
      data-record-groups={props.state}
      className="flex flex-col gap-3 rounded-lg border bg-card p-4"
    >
      <h3 id={heading} className="text-base font-semibold text-foreground">
        {t("desktop.profile.record_groups.title")}
      </h3>
      {reading && blocks.length === 0 && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          {t("desktop.profile.record_groups.reading")}
        </p>
      )}
      {props.state === "failed" && (
        <p role="alert" className="text-sm text-warning">
          {t("desktop.profile.record_groups.read_failed")}
        </p>
      )}
      {refusal !== null && (
        <p
          role="alert"
          data-record-groups-refused=""
          lang={refusal.language ?? undefined}
          className="text-sm text-warning"
        >
          {refusal.words}
        </p>
      )}
      {props.state === "ready" && refusal === null && blocks.length === 0 && (
        <p
          data-record-groups-empty=""
          className="text-sm text-muted-foreground"
        >
          {t("desktop.profile.record_groups.empty")}
        </p>
      )}
      {blocks.length > 0 && (
        <div className="flex flex-col gap-3">
          {blocks.map((block) => (
            <GroupCard
              key={block.group.group_key}
              block={block}
              props={props}
            />
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {continues && props.onMore && (
          <Button
            size="xs"
            variant="outline"
            data-record-groups-more=""
            disabled={reading}
            onClick={props.onMore}
          >
            {reading && <Spinner />}
            {t("desktop.profile.record_groups.more")}
          </Button>
        )}
        {(props.state === "failed" || refusal !== null) &&
          props.onReadAgain && (
            <Button
              size="xs"
              variant="outline"
              data-record-groups-read-again=""
              onClick={props.onReadAgain}
            >
              {t("desktop.profile.record_groups.read_again")}
            </Button>
          )}
      </div>
    </section>
  );
}
