// The scenario ledger's batch edit: `ledger.update.batch.preview` answers
// what writing one property set per movement would do, and
// `ledger.update.batch` writes it when the plan it finds is the one the
// preview answered. Each row's outcome follows from the synthetic movement
// alone, so a scenario knows it in advance: a movement it does not hold is
// gone, one changed since the page read it is a conflict, one not active or
// sealed is refused, a cleared required property is refused, and one
// already holding every value is unchanged. Everything it answers is
// synthetic.

import type { JsonObject, JsonValue } from "../shell/ledger";
import {
  BATCH_PLAN_CHANGED,
  BATCH_ROW_LIMIT,
  type LedgerPropertySetField,
} from "../shell/ledgerMovementContract";
import { PROPERTY_SET_FIELDS } from "../shell/ledgerPlan";
import {
  type FixtureLedger,
  type FixtureMovement,
  LEDGER_FIXTURE_PROFILE_ID,
} from "./fixtures/ledger";
import {
  MovementActionInvalid,
  MovementActionStopped,
} from "./ledgerMovementActionFixture";
import { FRACTION, SEALED_MESSAGE } from "./ledgerRequestFixture";

/** The properties a batch edit may set but never clear. */
const REQUIRED: readonly LedgerPropertySetField[] = [
  "business_classification",
  "notes",
];
const CLASSIFICATIONS = ["BUSINESS", "PERSONAL", "MIXED", "UNCLASSIFIED"];

type Row = {
  transaction_id: string;
  expected_modified_at: string;
  fields: LedgerPropertySetField[];
  values: Partial<Record<LedgerPropertySetField, string | null>>;
};

/** The rows of a batch request, or a refusal of its shape. */
function rowsOf(request: JsonObject): Row[] {
  const rows = request.rows;
  if (!Array.isArray(rows) || rows.length < 1 || rows.length > BATCH_ROW_LIMIT)
    throw new MovementActionInvalid();
  const seen = new Set<string>();
  return rows.map((raw) => {
    if (typeof raw !== "object" || raw === null || Array.isArray(raw))
      throw new MovementActionInvalid();
    const row = raw as JsonObject;
    const id = row.transaction_id;
    const stamp = row.expected_modified_at;
    const properties = row.properties;
    if (
      typeof id !== "string" ||
      seen.has(id) ||
      typeof stamp !== "string" ||
      typeof properties !== "object" ||
      properties === null ||
      Array.isArray(properties)
    )
      throw new MovementActionInvalid();
    seen.add(id);
    const set = properties as JsonObject;
    const fields = set.fields;
    if (
      !Array.isArray(fields) ||
      fields.length < 1 ||
      new Set(fields).size !== fields.length ||
      !fields.every(
        (field) =>
          typeof field === "string" &&
          (PROPERTY_SET_FIELDS as readonly string[]).includes(field),
      )
    )
      throw new MovementActionInvalid();
    const values: Row["values"] = {};
    for (const field of PROPERTY_SET_FIELDS) {
      const value = set[field] ?? null;
      if (value !== null && typeof value !== "string")
        throw new MovementActionInvalid();
      // A value of a property not named is a request the contract refuses.
      if (!(fields as string[]).includes(field)) {
        if (value !== null) throw new MovementActionInvalid();
        continue;
      }
      values[field] = value;
    }
    return {
      transaction_id: id,
      expected_modified_at: stamp,
      fields: fields as LedgerPropertySetField[],
      values,
    };
  });
}

/** What a movement stores of a property, empty text as nothing. */
function storedOf(
  movement: FixtureMovement,
  field: LedgerPropertySetField,
): string | null {
  const value =
    field === "group_label"
      ? movement.group_label
      : (movement.transaction as unknown as Record<string, unknown>)[field];
  return typeof value === "string" && value !== "" ? value : null;
}

/** Why a value cannot be written, in the worker's words, or null. */
function refusalOf(
  field: LedgerPropertySetField,
  value: string | null,
): string | null {
  if (value === null)
    return REQUIRED.includes(field)
      ? `The ${field} cannot be cleared by a batch edit.`
      : null;
  if (field === "business_classification" && !CLASSIFICATIONS.includes(value))
    return "Unknown classification.";
  if (field === "business_pct" && !FRACTION.test(value))
    return "The business share is not a fraction between 0 and 1.";
  return null;
}

export function batchOperations(
  ledger: FixtureLedger,
  tools: {
    now: () => string;
    events: () => string[];
    hex64: (text: string) => string;
  },
) {
  const { now, events, hex64 } = tools;
  const movementOf = (id: string) =>
    ledger.movements.find(
      (movement) => movement.transaction.transaction_id === id,
    );

  /** Each row's outcome against the ledger as it is now; nothing written. */
  function plan(rows: readonly Row[]) {
    return rows.map((row) => {
      const movement = movementOf(row.transaction_id);
      const base = {
        transaction_id: row.transaction_id,
        changed_fields: [] as string[],
        messages: [] as string[],
        previous: null as JsonObject | null,
        result_transaction_id: null as string | null,
        modified_at: null as string | null,
        cause: null as string | null,
      };
      if (!movement)
        return { ...base, outcome: "conflict", cause: "not_found" } as const;
      if (movement.transaction.modified_at !== row.expected_modified_at)
        return {
          ...base,
          outcome: "conflict",
          cause: "changed_since_seen",
        } as const;
      if (movement.transaction.lifecycle_state !== "ACTIVE")
        return {
          ...base,
          outcome: "refused",
          cause: "not_active",
          messages: ["Only an active movement can be updated."],
        } as const;
      if (movement.sealed)
        return {
          ...base,
          outcome: "refused",
          cause: "sealed",
          messages: [SEALED_MESSAGE],
        } as const;
      // A row carries at most four sentences, as the contract bounds it.
      const messages = row.fields
        .flatMap((field) => {
          const said = refusalOf(field, row.values[field] ?? null);
          return said ? [said] : [];
        })
        .slice(0, 4);
      if (messages.length)
        return {
          ...base,
          outcome: "refused",
          cause: "invalid",
          messages,
        } as const;
      const previous: JsonObject = { fields: row.fields };
      for (const field of PROPERTY_SET_FIELDS)
        previous[field] = row.fields.includes(field)
          ? storedOf(movement, field)
          : null;
      const changed = row.fields.filter(
        (field) => storedOf(movement, field) !== (row.values[field] ?? null),
      );
      const kept = {
        ...base,
        previous,
        result_transaction_id: movement.transaction.transaction_id,
        modified_at: movement.transaction.modified_at,
      };
      return changed.length
        ? ({ ...kept, outcome: "applied", changed_fields: changed } as const)
        : ({ ...kept, outcome: "unchanged" } as const);
    });
  }

  type Planned = ReturnType<typeof plan>;
  // The digest leaves out sentences and stamps, as the worker's does.
  const digestOf = (planned: Planned) =>
    hex64(
      JSON.stringify(
        planned.map((row) => [
          row.transaction_id,
          row.outcome,
          row.cause,
          row.changed_fields,
        ]),
      ),
    );
  const counts = (planned: Planned) => {
    const counted = { applied: 0, unchanged: 0, refused: 0, conflict: 0 };
    for (const row of planned) counted[row.outcome] += 1;
    return counted;
  };
  const result = (
    outcome: "previewed" | "applied" | "plan_changed",
    planned: Planned,
    eventIds: string[] = [],
  ): JsonObject => ({
    profile_id: LEDGER_FIXTURE_PROFILE_ID,
    outcome,
    plan_digest: digestOf(planned),
    rows: planned as unknown as JsonValue,
    counts: counts(planned),
    bucket_event_ids: eventIds,
  });

  function preview(request: JsonObject): JsonObject {
    return result("previewed", plan(rowsOf(request)));
  }

  function write(request: JsonObject): JsonObject {
    const rows = rowsOf(request);
    const reviewed = request.reviewed_plan_digest;
    if (typeof reviewed !== "string" || !/^[0-9a-f]{64}$/.test(reviewed))
      throw new MovementActionInvalid();
    const planned = plan(rows);
    if (digestOf(planned) !== reviewed)
      throw new MovementActionStopped(
        BATCH_PLAN_CHANGED,
        result("plan_changed", planned),
      );
    const written = planned.map((row, at) => {
      if (row.outcome !== "applied") return row;
      const movement = movementOf(row.transaction_id)!;
      const values = rows[at]!.values;
      const next = { ...movement.transaction } as unknown as Record<
        string,
        unknown
      >;
      for (const field of row.changed_fields as LedgerPropertySetField[]) {
        const value = values[field] ?? null;
        if (field === "group_label") movement.group_label = value;
        else if (field === "counterparty" || field === "notes")
          next[field] = value ?? "";
        else next[field] = value;
      }
      next.modified_at = now();
      movement.transaction = next as unknown as typeof movement.transaction;
      return { ...row, modified_at: next.modified_at as string };
    });
    const wrote = written.some((row) => row.outcome === "applied");
    return result("applied", written, wrote ? events() : []);
  }

  return {
    reads: { "ledger.update.batch.preview": preview },
    writes: { "ledger.update.batch": write },
  };
}
