// The scenario ledger's entry handlers: updating, classifying, bulk
// classifying, adding and reading the status of movements, and the readiness
// preflight of a period. Everything it answers is synthetic.

import { isDirection } from "../shell/ledgerContract";
import type {
  JsonObject,
  JsonValue,
  LedgerReviewStatus,
  LedgerTransaction,
} from "../shell/ledger";
import {
  LEDGER_UPDATE_FIELDS,
  type LedgerUpdateField,
} from "../shell/ledgerContract";
import {
  cents,
  type FixtureLedger,
  type FixtureMovement,
  LEDGER_FIXTURE_PROFILE_ID,
  money,
  movementId,
} from "./fixtures/ledger";
import {
  AMOUNT,
  BULK_COLUMNS,
  DATE,
  DECIDED,
  FRACTION,
  invalid,
  SEALED_MESSAGE,
  shortest,
  text,
  UPDATE_REQUIRED,
} from "./ledgerRequestFixture";
import { inPeriod, issues, resolve, reviewStatus } from "./ledgerQueryFixture";
import { parseCsv } from "./ledgerFileFixture";

/** The scenario ledger's entry answers over its movements. */
export function entryOperations(
  ledger: FixtureLedger,
  tools: {
    now: () => string;
    events: () => string[];
    /** Declarations calculated before their movements last changed. */
    staleFilings: (period: JsonValue | null) => JsonObject[];
  },
) {
  const { now, events, staleFilings } = tools;
  const transactionOf = (id: string) =>
    ledger.movements.find(
      (movement) => movement.transaction.transaction_id === id,
    );

  function update(request: JsonObject): JsonObject {
    const fields = request.patch_fields;
    const patch = request.patch;
    if (
      !Array.isArray(fields) ||
      fields.length < 1 ||
      fields.length > LEDGER_UPDATE_FIELDS.length ||
      new Set(fields).size !== fields.length ||
      typeof patch !== "object" ||
      patch === null ||
      Array.isArray(patch)
    )
      return invalid();
    const values = patch as JsonObject;
    for (const field of fields) {
      if (
        typeof field !== "string" ||
        !(LEDGER_UPDATE_FIELDS as readonly string[]).includes(field)
      )
        return invalid();
      if (
        (UPDATE_REQUIRED as string[]).includes(field) &&
        (values[field] ?? null) === null
      )
        return invalid();
    }
    const movement = resolve(ledger, request.transaction_id);
    const refused = (message: string): JsonObject => ({
      outcome: "validation_error",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      source_transaction_id: null,
      transaction: null,
      review_status: null,
      bucket_event_ids: [],
      group_label: null,
      own_account_id: null,
      validation_messages: [message],
    });
    if (movement.transaction.lifecycle_state !== "ACTIVE")
      return refused("Only an active movement can be updated.");
    if (movement.sealed) return refused(SEALED_MESSAGE);
    const next: LedgerTransaction = { ...movement.transaction };
    let group = movement.group_label;
    let account = movement.own_account_id;
    for (const field of fields as LedgerUpdateField[]) {
      const value = text(values[field]);
      if (field === "amount") {
        if (!value || !AMOUNT.test(value) || !shortest(value))
          return refused("The amount is not a canonical decimal.");
        next.amount = money(cents(value));
      } else if (
        field === "booked_date" ||
        field === "value_date" ||
        field === "operation_date" ||
        field === "accrual_date"
      ) {
        if (value !== null && !DATE.test(value))
          return refused("The date is not a calendar day.");
        next[field] = value as string;
      } else if (field === "direction") {
        if (!value || !isDirection(value.toUpperCase()))
          return refused("Unknown direction.");
        next.direction = value.toUpperCase();
      } else if (field === "currency") {
        if (!value || !/^[A-Z]{3}$/.test(value))
          return refused("Unknown currency.");
        next.currency = value;
      } else if (field === "group_label") {
        group = value === null || value.trim() === "" ? null : value.trim();
      } else if (field === "own_account_id") {
        if (
          value !== null &&
          !ledger.accounts.some((own) => own.own_account_id === value)
        )
          return refused("No own account has that id.");
        account = value;
      } else if (field === "counterparty") {
        next.counterparty = value ?? "";
      } else if (field === "description" || field === "notes") {
        next[field] = value ?? "";
      } else {
        next[field] = value;
      }
    }
    next.date = next.value_date ?? next.booked_date;
    const changed =
      JSON.stringify(next) !== JSON.stringify(movement.transaction) ||
      group !== movement.group_label ||
      account !== movement.own_account_id;
    if (!changed)
      return refused(
        "manual ledger update must change at least one ledger field",
      );
    const source = movement.transaction.transaction_id;
    // The id is the content address of these facts: changing one re-keys.
    if (
      next.amount !== movement.transaction.amount ||
      next.description !== movement.transaction.description ||
      next.date !== movement.transaction.date ||
      account !== movement.own_account_id
    )
      next.transaction_id = movementId({
        date: next.date,
        amount: next.amount,
        description: next.description,
        own_account_id: account,
        salt: source,
      });
    next.modified_at = now();
    movement.transaction = next;
    movement.group_label = group;
    movement.own_account_id = account;
    return {
      outcome: "updated",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      source_transaction_id: source,
      transaction: { ...next } as unknown as JsonValue,
      review_status: reviewStatus(next.business_classification),
      bucket_event_ids: events(),
      group_label: group,
      own_account_id: account,
      validation_messages: [],
    };
  }

  /** One row's classification, shared by the single and bulk writes. */
  function classifyRow(
    movement: FixtureMovement,
    values: Record<string, string | null>,
    by: string,
  ): "applied" | "skipped" {
    const next: LedgerTransaction = { ...movement.transaction };
    for (const [field, value] of Object.entries(values)) {
      if (field === "classification")
        next.business_classification = value ?? next.business_classification;
      else if (field === "notes") next.notes = value ?? "";
      else if (field in next)
        (next as unknown as Record<string, string | null>)[field] = value;
    }
    if (next.business_classification === "PERSONAL") {
      next.category_id = null;
      next.business_pct = null;
    }
    if (JSON.stringify(next) === JSON.stringify(movement.transaction))
      return "skipped";
    next.classified_by = by;
    next.classified_at = now();
    next.classification_reason = by;
    next.modified_at = next.classified_at;
    movement.transaction = next;
    return "applied";
  }
  const checkDecision = (classification: string | null, pct: string | null) => {
    if (!classification || !DECIDED.includes(classification)) return invalid();
    if ((classification === "MIXED") !== (pct !== null)) return invalid();
    if (pct !== null && (!FRACTION.test(pct) || !shortest(pct)))
      return invalid();
  };

  function classify(request: JsonObject): JsonObject {
    const fields = request.patch_fields;
    const patch = request.patch as JsonObject | undefined;
    if (
      !Array.isArray(fields) ||
      !fields.includes("business_classification") ||
      !patch
    )
      return invalid();
    const classification = text(patch.business_classification);
    const pct = text(patch.business_pct);
    checkDecision(classification, pct);
    const rate = text(patch.iva_rate);
    if (rate !== null && (!FRACTION.test(rate) || !shortest(rate)))
      return invalid();
    const movement = resolve(ledger, request.transaction_id);
    if (movement.sealed || movement.transaction.lifecycle_state !== "ACTIVE")
      return {
        outcome: "validation_error",
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        transaction: null,
        deduction_fact_kind: null,
        investment_asset_id: null,
        review_status: null,
        bucket_event_ids: [],
        validation_kind: "input",
        validation_messages: [
          movement.sealed
            ? SEALED_MESSAGE
            : "Only an active movement can be classified.",
        ],
      };
    const values: Record<string, string | null> = {};
    for (const field of fields as string[]) {
      if (field === "m210_income_classification") continue;
      values[field === "business_classification" ? "classification" : field] =
        text(patch[field]);
    }
    classifyRow(movement, values, "operator");
    const transaction = movement.transaction;
    return {
      outcome: "classified",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      transaction: { ...transaction } as unknown as JsonValue,
      deduction_fact_kind: transaction.deduction_fact_kind,
      investment_asset_id: transaction.investment_asset_id,
      review_status: reviewStatus(transaction.business_classification),
      bucket_event_ids: events(),
      validation_kind: "none",
      validation_messages: [],
    };
  }

  function bulk(request: JsonObject): JsonObject {
    const csv = text(request.csv_text);
    if (csv === null) return invalid();
    const refused = (message: string): JsonObject => ({
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      outcome: "validation_error",
      result: null,
      validation_messages: [message],
    });
    const lines = parseCsv(csv);
    const header = lines.shift() ?? [];
    if (
      !header.includes("transaction_id") ||
      !header.includes("classification")
    )
      return refused(
        "The CSV needs transaction_id and classification columns.",
      );
    const unknown = header.find((column) => !BULK_COLUMNS.includes(column));
    if (unknown !== undefined)
      return refused(
        "The CSV names a column bulk classification does not take.",
      );
    const failures: JsonValue[] = [];
    let applied = 0;
    let skipped = 0;
    lines.forEach((cells, index) => {
      const value = (column: string) => {
        const at = header.indexOf(column);
        const cell = at < 0 ? "" : (cells[at] ?? "");
        return cell.trim() === "" ? null : cell.trim();
      };
      const id = value("transaction_id") ?? "";
      const fail = (reason: string) =>
        failures.push({ row_index: index, transaction_id: id, reason });
      if (cells.length > header.length)
        return fail("The row has more cells than the header.");
      const classification = value("classification")?.toUpperCase() ?? null;
      const pct = value("business_pct");
      if (!classification) return fail("Every row needs a classification.");
      if (
        !DECIDED.includes(classification) ||
        (classification === "MIXED") !== (pct !== null)
      )
        return fail(
          "The classification is not one a person decides, or its business share is missing.",
        );
      let movement: FixtureMovement;
      try {
        movement = resolve(ledger, id);
      } catch {
        return fail("No single movement has that id.");
      }
      if (movement.transaction.lifecycle_state !== "ACTIVE")
        return fail("Only an active movement can be classified.");
      if (movement.sealed) return fail(SEALED_MESSAGE);
      const values: Record<string, string | null> = { classification };
      for (const column of header)
        if (
          !["transaction_id", "classification"].includes(column) &&
          value(column) !== null
        )
          values[column] = value(column);
      if (classifyRow(movement, values, "operator:bulk") === "applied")
        applied += 1;
      else skipped += 1;
    });
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      outcome: "classified",
      result: {
        total: lines.length,
        applied,
        skipped,
        failures,
        bucket_event_ids: applied ? events() : [],
      },
      validation_messages: [],
    };
  }

  function add(request: JsonObject): JsonObject {
    const booked = text(request.booked_date);
    const amount = text(request.amount);
    const direction = text(request.direction)?.toUpperCase() ?? null;
    const description = text(request.description);
    if (!booked || !DATE.test(booked) || !amount || !direction || !description)
      return invalid();
    const refused = (message: string): JsonObject => ({
      outcome: "validation_error",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      transaction: null,
      review_status: null,
      bucket_event_ids: [],
      advisory_input_classification: null,
      advisory_input_classification_inert: false,
      advisory_sector_id: null,
      advisory_sector_unmatched: false,
      validation_code: "invalid_command",
      validation_messages: [message],
    });
    if (!AMOUNT.test(amount))
      return refused("The amount is not a canonical decimal.");
    if (!isDirection(direction)) return refused("Unknown direction.");
    const classification =
      text(request.business_classification) ?? "NOT_YET_PROCESSED";
    const key = text(request.idempotency_key);
    const date = text(request.value_date) ?? booked;
    const account = text(request.own_account_id);
    const facts: LedgerTransaction = {
      transaction_id: "",
      date,
      booked_date: booked,
      value_date: text(request.value_date),
      operation_date: text(request.operation_date),
      accrual_date: text(request.accrual_date),
      amount: money(cents(amount)),
      currency: text(request.currency) ?? "EUR",
      direction,
      counterparty: text(request.counterparty) ?? "",
      description,
      business_classification: classification,
      business_pct: text(request.business_pct),
      category_id: text(request.category_id),
      taxable_base: text(request.taxable_base),
      iva_rate: text(request.iva_rate),
      iva_amount: text(request.iva_amount),
      recargo_amount: null,
      iva_category: text(request.iva_category),
      deduction_fact_kind: text(request.deduction_fact_kind),
      investment_asset_id: text(request.investment_asset_id),
      counterparty_country: text(request.counterparty_country),
      counterparty_identification_state: text(
        request.counterparty_identification_state,
      ),
      irpf_category: text(request.irpf_category),
      m210_income_classification: null,
      usage_ratio_id: text(request.usage_ratio_id),
      prorrata_reference: text(request.prorrata_reference),
      purchase_invoice_evidence_id: text(request.purchase_invoice_evidence_id),
      invoice_id: null,
      attachment_ids: [],
      notes: text(request.notes) ?? "",
      lifecycle_state: "ACTIVE",
      classified_by: classification === "NOT_YET_PROCESSED" ? "" : "operator",
      classified_at: null,
      classification_reason: "",
      classification_confidence: null,
      source_jurisdiction: text(request.source_jurisdiction),
      statement_reference: null,
      value_in_eur: null,
      fx_rate: null,
      created_at: "",
      modified_at: "",
    };
    const result = (
      transaction: LedgerTransaction,
      written: boolean,
    ): JsonObject => ({
      outcome: "created",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      transaction: { ...transaction } as unknown as JsonValue,
      review_status: reviewStatus(transaction.business_classification),
      bucket_event_ids: written ? events() : [],
      advisory_input_classification: null,
      advisory_input_classification_inert: false,
      advisory_sector_id: null,
      advisory_sector_unmatched: false,
      validation_code: null,
      validation_messages: [],
    });
    if (key !== null) {
      const stored = ledger.movements.find(
        (movement) => movement.idempotency_key === key,
      );
      if (stored) {
        const same = (Object.keys(facts) as (keyof LedgerTransaction)[])
          .filter(
            (field) =>
              ![
                "transaction_id",
                "created_at",
                "modified_at",
                "classified_at",
              ].includes(field),
          )
          .every(
            (field) =>
              JSON.stringify(facts[field]) ===
              JSON.stringify(stored.transaction[field]),
          );
        // A retry of the same add returns the row it stored and writes nothing.
        return same
          ? result(stored.transaction, false)
          : refused("application.ledger.errors.idempotency_key_conflict");
      }
    }
    const created = now();
    facts.transaction_id = movementId({
      date,
      amount: facts.amount,
      description,
      own_account_id: account,
      salt: key ?? created,
    });
    facts.created_at = created;
    facts.modified_at = created;
    if (classification !== "NOT_YET_PROCESSED") facts.classified_at = created;
    ledger.movements.push({
      transaction: facts,
      group_label: null,
      own_account_id: account,
      import_batch_id: null,
      issue: null,
      sealed: false,
      llm_rejected: false,
      withholding: [],
      idempotency_key: key,
    });
    return result(facts, true);
  }

  function status(request: JsonObject): JsonObject {
    const period = request.period ?? null;
    const rows = ledger.movements.filter((movement) =>
      inPeriod(movement, period),
    );
    const sum = (direction: string) =>
      money(
        rows
          .filter(
            (movement) =>
              movement.transaction.direction === direction &&
              ["BUSINESS", "MIXED"].includes(
                movement.transaction.business_classification,
              ),
          )
          .reduce(
            (total, movement) =>
              total +
              cents(
                movement.transaction.taxable_base ??
                  movement.transaction.amount,
              ),
            0,
          ),
      );
    // Every period's status runs no preflight, as the product's does: it
    // lists no issues and leaves readiness unmeasured.
    const found = period === null ? [] : issues(ledger, period);
    // The product counts movements over the whole ledger, whatever period
    // is asked for, and its review states over the active ones; only the
    // money totals and the foreign count read the period.
    const all = ledger.movements;
    const inState = (state: string) =>
      all.filter((movement) => movement.transaction.lifecycle_state === state);
    const active = inState("ACTIVE");
    const by = (state: LedgerReviewStatus) =>
      active.filter(
        (movement) =>
          reviewStatus(movement.transaction.business_classification) === state,
      ).length;
    const income = sum("INCOMING");
    const expense = sum("OUTGOING");
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      period: period as JsonValue,
      business_income_total: income,
      business_expense_total: expense,
      business_net_total: money(cents(income) - cents(expense)),
      total_count: all.length,
      active_count: active.length,
      archived_count: inState("ARCHIVED").length,
      stashed_count: inState("STASHED").length,
      split_count: inState("SPLIT").length,
      pending_review_count: by("pending"),
      reviewed_count: by("reviewed"),
      skipped_count: by("skipped"),
      checked_transaction_count: rows.length,
      readiness_issue_count: found.length,
      unconverted_currency_count: rows.filter(
        (movement) =>
          movement.transaction.lifecycle_state === "ACTIVE" &&
          ["BUSINESS", "MIXED"].includes(
            movement.transaction.business_classification,
          ) &&
          movement.transaction.currency !== "EUR" &&
          !movement.transaction.value_in_eur,
      ).length,
      ready: rows.length === 0 || period === null ? null : found.length === 0,
      readiness_issues: found.map((issue) => ({
        ...issue,
        transaction_present: true,
        business_classification:
          transactionOf(issue.transaction_id)?.transaction
            .business_classification ?? null,
        category_id: null,
        taxable_base: null,
        iva_rate: null,
        iva_amount: null,
      })),
      stale_filings: staleFilings(period),
    };
  }

  function preflight(request: JsonObject): JsonObject {
    const period = request.period;
    if (!period || typeof period !== "object" || Array.isArray(period))
      return invalid();
    const found = issues(ledger, period);
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      period,
      bucket_id: LEDGER_FIXTURE_PROFILE_ID,
      checked_transaction_count: ledger.movements.filter((movement) =>
        inPeriod(movement, period),
      ).length,
      issues: found,
      ready: found.length === 0,
    };
  }

  return {
    transactionOf,
    update,
    classifyRow,
    classify,
    bulk,
    add,
    status,
    preflight,
  };
}
