// The scenario ledger's reads of one movement's lineage and its actions,
// held to the registered contracts of `ledger.track`,
// `ledger.history.typed`, `ledger.remove`, the four lifecycle operations,
// `ledger.split.manual`, `ledger.merge`, `ledger.classify.iva-derive` and
// `ledger.allocate`. A request its contract would not decode is refused
// before anything runs; a movement a finalized revision cites, or one that
// is not active, is refused as the product refuses it. Results are the flat
// projections the host passes on. Everything it answers is synthetic.

import type {
  JsonObject,
  JsonValue,
  LedgerParticipation,
  LedgerRevisionReference,
  LedgerTransaction,
} from "../shell/ledger";
import {
  SEALED_PERIOD,
  cents,
  money,
  movementId,
  type FixtureLedger,
  type FixtureMovement,
} from "./fixtures/ledger";

/** A request its registered contract would not decode. */
export class MovementActionInvalid extends Error {}
/** Settled without writing, with the refusal's code. */
export class MovementActionStopped extends Error {
  constructor(readonly reason: string) {
    super(reason);
  }
}

type Tools = {
  profileId: string;
  now: () => string;
  events: () => string[];
  hex64: (text: string) => string;
};

type HistoryEvent = {
  event_type: string;
  occurred_at: string;
  object_id: string;
  details: Record<string, string>;
};
type LifecycleEntry = {
  previous_state: string;
  state: string;
  actor: string;
  source_command: string;
  changed_at: string;
  reason: string;
  bucket_event_id: string | null;
};
type SplitGroup = { id: string; parent: string; children: string[] };

const HEX = /^[0-9a-f]+$/;
const CANONICAL = /^(0|[1-9]\d*)(\.\d*[1-9])?$/;
const LIFECYCLE_OPERATIONS = [
  "ledger.archive",
  "ledger.stash",
  "ledger.restore",
  "ledger.exclude",
] as const;
type LifecycleOperation = (typeof LIFECYCLE_OPERATIONS)[number];
const RATES: Record<string, string> = {
  domestic_general: "0.21",
  domestic_reduced: "0.1",
  domestic_super_reduced: "0.04",
};
const SEALING_REVISION = {
  modelo: "303",
  filing_year: SEALED_PERIOD.filing_year,
  period: SEALED_PERIOD.code,
};

const object = (value: JsonValue | undefined): JsonObject | null =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
const text = (value: JsonValue | undefined): string | null =>
  typeof value === "string" ? value : null;
const invalid = (): never => {
  throw new MovementActionInvalid();
};
const stopped = (reason: string): never => {
  throw new MovementActionStopped(reason);
};

/** Only the named keys, as a strict request model admits. */
function only(request: JsonObject, keys: readonly string[]) {
  for (const key of Object.keys(request)) if (!keys.includes(key)) invalid();
}
function reason(request: JsonObject): string {
  const found = request.reason ?? "";
  if (typeof found !== "string" || found.length > 500) return invalid();
  return found.trim();
}

/** The scenario's movement actions and lineage reads over `ledger`. */
export function movementActionOperations(ledger: FixtureLedger, tools: Tools) {
  const { profileId, now, events, hex64 } = tools;
  const history = new Map<string, HistoryEvent[]>();
  const lifecycle = new Map<string, LifecycleEntry[]>();
  const groups: SplitGroup[] = [];

  const record = (
    id: string,
    event_type: string,
    details: Record<string, string>,
  ) => {
    const list = history.get(id) ?? [];
    list.push({ event_type, occurred_at: now(), object_id: id, details });
    history.set(id, list);
  };
  const find = (prefix: JsonValue | undefined): FixtureMovement => {
    if (
      typeof prefix !== "string" ||
      prefix.length < 1 ||
      prefix.length > 96 ||
      !HEX.test(prefix)
    )
      return invalid();
    const found = ledger.movements.filter((movement) =>
      movement.transaction.transaction_id.startsWith(prefix),
    );
    if (found.length === 0) return stopped("ERROR_TRANSACTION_NOT_FOUND");
    if (found.length > 1)
      return stopped("REFUSED_FINANCIAL_LEDGER_TRANSACTION_ID_PREFIX");
    return found[0]!;
  };
  const groupOf = (id: string) =>
    groups.find((group) => group.parent === id || group.children.includes(id));
  const sealingReference = (
    movement: FixtureMovement,
  ): LedgerRevisionReference => ({
    work_unit_id: hex64(`work-unit:303:${movement.transaction.transaction_id}`),
    calculation_revision_id: hex64("revision:303:2026:1T"),
    revision_state: "presentado",
    ...SEALING_REVISION,
  });
  const participation = (
    movement: FixtureMovement,
  ): LedgerParticipation[] | null =>
    movement.sealed
      ? [
          {
            calculation_revision_id: hex64("revision:303:2026:1T"),
            work_unit_id: hex64("work-unit:303:2026:1T"),
            modelo: "303",
            filing_year: SEALED_PERIOD.filing_year,
            period: { ...SEALED_PERIOD },
            revision_state: "presentado",
            filing_record_id: hex64("filing:303:2026:1T"),
            justificante_reference: null,
          },
        ]
      : null;
  const projected = (movement: FixtureMovement) =>
    ({ ...movement.transaction }) as unknown as JsonValue;
  const reviewOf = (classification: string) =>
    classification === "NOT_YET_PROCESSED"
      ? "pending"
      : classification === "SKIPPED_BY_RULE"
        ? "skipped"
        : classification === "REVIEWED_EXCLUDED"
          ? "excluded"
          : "reviewed";

  // ---- Reads ---------------------------------------------------------------

  function track(request: JsonObject): JsonObject {
    only(request, ["transaction_prefix"]);
    const movement = find(request.transaction_prefix);
    const t = movement.transaction;
    const imported = movement.import_batch_id !== null;
    return {
      profile_id: profileId,
      transaction_prefix: request.transaction_prefix as string,
      transaction: projected(movement),
      tracking: {
        transaction_id: t.transaction_id,
        created_event_id: imported
          ? null
          : hex64(`created:${t.transaction_id}`),
        evidence_provenance: t.purchase_invoice_evidence_id
          ? [
              {
                evidence_id: t.purchase_invoice_evidence_id,
                evidence_kind: "purchase_invoice",
                actor: "operator",
                source_command: "aeat app ledger attach",
                linked_at: t.created_at,
                bucket_event_id: null,
              },
            ]
          : [],
        edit_lineage: [],
        lifecycle_state: t.lifecycle_state,
        lifecycle_lineage: (lifecycle.get(t.transaction_id) ??
          []) as unknown as JsonValue,
      },
      imported_provenance: imported
        ? {
            provider_name: "csv",
            source_filename: `extracto-${movement.import_batch_id}.csv`,
            source_row_index: (ledger.movements.indexOf(movement) % 120) + 2,
            ingested_at: t.created_at,
            import_fingerprint: hex64(`fingerprint:${t.transaction_id}`),
          }
        : null,
      participated_in: participation(movement) as unknown as JsonValue,
    };
  }

  function historyTyped(request: JsonObject): JsonObject {
    only(request, ["transaction_prefix", "include_split_siblings"]);
    const siblings = request.include_split_siblings ?? false;
    if (typeof siblings !== "boolean") return invalid();
    const movement = find(request.transaction_prefix);
    const t = movement.transaction;
    const id = t.transaction_id;
    const group = groupOf(id);
    const objectIds = [id];
    if (siblings && group)
      for (const other of [group.parent, ...group.children])
        if (!objectIds.includes(other)) objectIds.push(other);
    const base: HistoryEvent[] = [
      {
        event_type:
          movement.import_batch_id !== null
            ? "ledger.transaction.imported"
            : "ledger.transaction.created",
        occurred_at: t.created_at,
        object_id: id,
        details:
          movement.import_batch_id !== null
            ? {
                import_batch_id: movement.import_batch_id,
                provider_name: "csv",
              }
            : { source_command: "aeat app ledger add" },
      },
    ];
    if (t.classified_at && !history.get(id)?.length)
      base.push({
        event_type: "ledger.transaction.classified",
        occurred_at: t.classified_at,
        object_id: id,
        details: {
          classification: t.business_classification,
          ...(t.category_id ? { category_id: t.category_id } : {}),
          classified_by: t.classified_by,
        },
      });
    if (movement.llm_rejected)
      base.push({
        event_type: "ledger.transaction.llm_suggestion.rejected",
        occurred_at: "2026-10-02T09:30:00Z",
        object_id: id,
        details: {
          suggestion_kind: "classification",
          classification: "PERSONAL",
          provenance: "llm:local-medium",
        },
      });
    const all = [
      ...base,
      ...objectIds.flatMap((anchor) => history.get(anchor) ?? []),
    ].sort((left, right) => left.occurred_at.localeCompare(right.occurred_at));
    return {
      profile_id: profileId,
      transaction_prefix: request.transaction_prefix as string,
      include_split_siblings: siblings,
      transaction_id: id,
      object_ids: objectIds,
      events: all.map((event, at) => ({
        event_id: hex64(`event:${id}:${at}:${event.event_type}`),
        event_type: event.event_type,
        occurred_at: event.occurred_at,
        actor: "operator",
        object_type: "ledger_transaction",
        object_id: event.object_id,
        details: event.details,
        model_reason_withheld: event.event_type.includes("llm"),
        output_path_withheld: false,
        undeclared_detail_count: 0,
      })),
      event_count: all.length,
    };
  }

  // ---- Writes --------------------------------------------------------------

  function remove(request: JsonObject): JsonObject {
    only(request, ["transaction_id", "reason", "dry_run", "actor"]);
    const why = reason(request);
    const dry = request.dry_run ?? false;
    if (typeof dry !== "boolean") return invalid();
    const movement = find(request.transaction_id);
    const t = movement.transaction;
    const blocking = movement.sealed ? [sealingReference(movement)] : [];
    if (!dry && blocking.length) stopped("ERROR_TRANSACTION_VALIDATION");
    const evidence = t.purchase_invoice_evidence_id
      ? [t.purchase_invoice_evidence_id]
      : [];
    if (!dry) {
      ledger.movements.splice(ledger.movements.indexOf(movement), 1);
      for (const invoice of ledger.invoices)
        invoice.linked_transaction_ids = invoice.linked_transaction_ids.filter(
          (linked) => linked !== t.transaction_id,
        );
    }
    return {
      profile_id: profileId,
      report: {
        bucket_id: profileId,
        transaction_id: t.transaction_id,
        removed: !dry,
        dry_run: dry,
        actor: "operator",
        reason: why,
        cascaded_purchase_invoice_evidence_ids: evidence,
        cascaded_attachment_ids: [...t.attachment_ids],
        blocking_modelo_references: blocking as unknown as JsonValue,
        stale_draft_revision_references: [],
        bucket_event_ids: dry ? [] : events(),
      },
    };
  }

  function changeLifecycle(
    operation: LifecycleOperation,
    request: JsonObject,
  ): JsonObject {
    only(request, ["transaction_id", "reason", "actor"]);
    const why = reason(request);
    const movement = find(request.transaction_id);
    const t = movement.transaction;
    const refused = (message: string): JsonObject => ({
      outcome: "validation_error",
      profile_id: profileId,
      operation_id: operation,
      result: null,
      validation: {
        messages: [message],
        transaction_id: t.transaction_id,
        transaction_ids: [],
        transaction_ids_omitted_count: 0,
        blocking_reference: movement.sealed
          ? (sealingReference(movement) as unknown as JsonValue)
          : null,
        blocking_reference_count: movement.sealed ? 1 : null,
      },
    });
    if (movement.sealed)
      return refused("A finalized declaration cites this movement.");
    const state = t.lifecycle_state;
    let next = state;
    let classification = t.business_classification;
    if (operation === "ledger.restore") {
      if (state !== "ARCHIVED" && state !== "STASHED")
        return refused("Only an archived or set-aside movement is restored.");
      next = "ACTIVE";
    } else if (state !== "ACTIVE") {
      return refused("Only an active movement can change state.");
    } else if (operation === "ledger.archive") next = "ARCHIVED";
    else if (operation === "ledger.stash") next = "STASHED";
    else {
      if (classification === "REVIEWED_EXCLUDED")
        return refused("The movement is already excluded.");
      classification = "REVIEWED_EXCLUDED";
    }
    const previous = { ...t };
    const changed = now();
    movement.transaction = {
      ...t,
      lifecycle_state: next,
      business_classification: classification,
      business_pct:
        classification === "REVIEWED_EXCLUDED" ? null : t.business_pct,
      modified_at: changed,
    };
    const ids = events();
    const entry: LifecycleEntry = {
      previous_state: state,
      state: next,
      actor: "operator",
      source_command: `aeat app ledger ${operation.slice("ledger.".length)}`,
      changed_at: changed,
      reason: why,
      bucket_event_id: ids[0] ?? null,
    };
    lifecycle.set(t.transaction_id, [
      ...(lifecycle.get(t.transaction_id) ?? []),
      entry,
    ]);
    record(
      t.transaction_id,
      operation === "ledger.exclude"
        ? "ledger.transaction.reviewed_excluded"
        : `ledger.transaction.${{ "ledger.archive": "archived", "ledger.stash": "stashed", "ledger.restore": "restored" }[operation]}`,
      {
        previous_lifecycle_state: state,
        lifecycle_state: next,
        ...(why ? { reason: why } : {}),
      },
    );
    return {
      outcome: "updated",
      profile_id: profileId,
      operation_id: operation,
      result: {
        profile_id: profileId,
        operation_id: operation,
        transaction: projected(movement),
        review_status: reviewOf(classification),
        bucket_event_ids: ids,
        replaced: {
          lifecycle_state: previous.lifecycle_state,
          business_classification: previous.business_classification,
          business_pct: previous.business_pct,
          classified_by: previous.classified_by,
          reversed_by: ["ledger.restore"],
        },
      },
      validation: null,
    };
  }

  function split(request: JsonObject): JsonObject {
    only(request, ["transaction_id", "children", "reason", "actor"]);
    const why = reason(request);
    const children = request.children;
    if (
      !Array.isArray(children) ||
      children.length < 2 ||
      children.length > 128
    )
      return invalid();
    const parts = children.map((child) => {
      const found = object(child);
      if (!found) return invalid();
      only(found, ["amount", "description"]);
      const amount = text(found.amount);
      const description = text(found.description)?.trim() ?? "";
      if (!amount || !CANONICAL.test(amount) || description === "")
        return invalid();
      return { amount, description };
    });
    const movement = find(request.transaction_id);
    const t = movement.transaction;
    if (t.lifecycle_state !== "ACTIVE" || movement.sealed)
      return stopped("ERROR_TRANSACTION_VALIDATION");
    const total = parts.reduce((sum, part) => sum + cents(part.amount), 0);
    if (total !== cents(t.amount))
      return stopped("ERROR_TRANSACTION_VALIDATION");
    const keys = new Set(
      parts.map((part) => `${part.amount}␟${part.description}`),
    );
    if (keys.size !== parts.length)
      return stopped("ERROR_TRANSACTION_VALIDATION");
    const groupId = hex64(`split:${t.transaction_id}`);
    const created = now();
    const ids: string[] = [];
    parts.forEach((part, index) => {
      const amount = money(cents(part.amount));
      const id = movementId({
        date: t.date,
        amount,
        description: part.description,
        own_account_id: movement.own_account_id,
        salt: `${groupId}:${index}`,
      });
      ids.push(id);
      const child: LedgerTransaction = {
        ...t,
        transaction_id: id,
        amount,
        description: part.description,
        business_classification: "NOT_YET_PROCESSED",
        business_pct: null,
        category_id: null,
        taxable_base: null,
        iva_rate: null,
        iva_amount: null,
        iva_category: null,
        irpf_category: null,
        purchase_invoice_evidence_id: null,
        invoice_id: null,
        attachment_ids: [],
        classified_by: "",
        classified_at: null,
        classification_reason: "",
        classification_confidence: null,
        value_in_eur: null,
        created_at: created,
        modified_at: created,
      };
      ledger.movements.splice(
        ledger.movements.indexOf(movement) + 1 + index,
        0,
        {
          transaction: child,
          group_label: movement.group_label,
          own_account_id: movement.own_account_id,
          import_batch_id: null,
          issue: null,
          sealed: false,
          llm_rejected: false,
          idempotency_key: null,
        },
      );
    });
    movement.transaction = {
      ...t,
      lifecycle_state: "SPLIT",
      modified_at: created,
    };
    groups.push({ id: groupId, parent: t.transaction_id, children: ids });
    const event = events()[0]!;
    record(t.transaction_id, "ledger.transaction.split", {
      split_group_id: groupId,
      parent_transaction_id: t.transaction_id,
      child_count: String(ids.length),
      ...(why ? { reason: why } : {}),
    });
    return {
      profile_id: profileId,
      parent_transaction_id: t.transaction_id,
      split_group_id: groupId,
      child_transaction_ids: ids,
      bucket_event_id: event,
      parent_business_classification: t.business_classification,
      child_business_classification: "NOT_YET_PROCESSED",
      remerged_by: ["ledger.merge"],
    };
  }

  function merge(request: JsonObject): JsonObject {
    only(request, ["child_ids", "reason", "actor"]);
    const why = reason(request);
    const named = request.child_ids;
    if (!Array.isArray(named) || named.length < 2) return invalid();
    const children = named.map((id) => find(id));
    const ids = children.map((child) => child.transaction.transaction_id);
    const group = groupOf(ids[0]!);
    if (
      !group ||
      group.children.length !== ids.length ||
      !group.children.every((id) => ids.includes(id)) ||
      children.some((child) => child.transaction.lifecycle_state !== "ACTIVE")
    )
      return stopped("ERROR_TRANSACTION_VALIDATION");
    const parent = ledger.movements.find(
      (movement) => movement.transaction.transaction_id === group.parent,
    );
    if (!parent) return stopped("ERROR_TRANSACTION_VALIDATION");
    for (const child of children)
      ledger.movements.splice(ledger.movements.indexOf(child), 1);
    parent.transaction = {
      ...parent.transaction,
      lifecycle_state: "ACTIVE",
      modified_at: now(),
    };
    groups.splice(groups.indexOf(group), 1);
    record(group.parent, "ledger.transaction.merged", {
      split_group_id: group.id,
      merged_transaction_id: group.parent,
      child_count: String(ids.length),
      ...(why ? { reason: why } : {}),
    });
    return {
      profile_id: profileId,
      split_group_id: group.id,
      parent_transaction_id: group.parent,
      merged_transaction_id: group.parent,
      source_child_ids: ids,
      bucket_event_id: events()[0]!,
    };
  }

  function ivaDerive(request: JsonObject): JsonObject {
    only(request, ["transaction_id", "iva_category", "actor"]);
    const category = text(request.iva_category);
    if (!category || category.length > 128) return invalid();
    const movement = find(request.transaction_id);
    const t = movement.transaction;
    const refused = (message: string): JsonObject => ({
      profile_id: profileId,
      outcome: "validation_error",
      transaction_id: t.transaction_id,
      iva_category: category,
      derivable: false,
      iva_rate: null,
      taxable_base: null,
      iva_amount: null,
      note: "",
      classification: null,
      validation_messages: [message],
    });
    if (t.lifecycle_state !== "ACTIVE" || movement.sealed)
      return refused(
        "Only an active movement that no finalized declaration cites takes figures.",
      );
    if (
      t.business_classification !== "BUSINESS" &&
      t.business_classification !== "MIXED"
    )
      return refused("Classify the movement as Business or Mixed first.");
    const rate = RATES[category];
    if (!rate)
      return {
        profile_id: profileId,
        outcome: "derived",
        transaction_id: t.transaction_id,
        iva_category: category,
        derivable: false,
        iva_rate: null,
        taxable_base: null,
        iva_amount: null,
        note: "This category has no single rate.",
        classification: null,
        validation_messages: [],
      };
    const gross = cents(t.amount);
    const base = Math.round(gross / (1 + Number(rate)));
    const next = {
      ...t,
      iva_category: category,
      iva_rate: rate,
      taxable_base: money(base),
      iva_amount: money(gross - base),
      modified_at: now(),
    };
    movement.transaction = next;
    record(t.transaction_id, "ledger.transaction.classified", {
      iva_category: category,
      classification: t.business_classification,
      classified_by: "operator",
    });
    return {
      profile_id: profileId,
      outcome: "derived",
      transaction_id: t.transaction_id,
      iva_category: category,
      derivable: true,
      iva_rate: rate,
      taxable_base: next.taxable_base,
      iva_amount: next.iva_amount,
      note: "",
      classification: {
        outcome: "classified",
        profile_id: profileId,
        transaction: projected(movement),
        deduction_fact_kind: null,
        investment_asset_id: null,
        review_status: reviewOf(next.business_classification),
        bucket_event_ids: events(),
        validation_kind: "none",
        validation_messages: [],
      },
      validation_messages: [],
    };
  }

  function allocate(request: JsonObject): JsonObject {
    only(request, [
      "transaction_id",
      "business_pct",
      "category_id",
      "usage_ratio_id",
      "prorrata_reference",
      "actor",
    ]);
    const share = text(request.business_pct);
    if (!share || !CANONICAL.test(share) || Number(share) > 1) return invalid();
    const movement = find(request.transaction_id);
    const t = movement.transaction;
    if (t.lifecycle_state !== "ACTIVE" || movement.sealed)
      return stopped("ERROR_TRANSACTION_VALIDATION");
    const classification =
      Number(share) === 1
        ? "BUSINESS"
        : Number(share) === 0
          ? "PERSONAL"
          : "MIXED";
    const optional = (key: string) =>
      request[key] === undefined ? undefined : text(request[key]);
    const category = optional("category_id");
    const ratio = optional("usage_ratio_id");
    const prorrata = optional("prorrata_reference");
    const stamp = now();
    movement.transaction = {
      ...t,
      business_classification: classification,
      business_pct: classification === "MIXED" ? share : null,
      ...(category ? { category_id: category } : {}),
      ...(ratio ? { usage_ratio_id: ratio } : {}),
      ...(prorrata ? { prorrata_reference: prorrata } : {}),
      classified_by: "operator",
      classified_at: stamp,
      modified_at: stamp,
    };
    record(t.transaction_id, "ledger.transaction.allocated", {
      business_pct: share,
      classification,
    });
    return {
      profile_id: profileId,
      transaction: projected(movement),
      review_status: reviewOf(classification),
      bucket_event_ids: events(),
    };
  }

  /** Records a model suggestion's rejection or approval in the history. */
  function noteReview(id: string, decision: "apply" | "reject", why: string) {
    record(
      id,
      decision === "reject"
        ? "ledger.transaction.llm_suggestion.rejected"
        : "ledger.transaction.classified",
      decision === "reject"
        ? {
            suggestion_kind: "classification",
            ...(why ? { operator_reason: why } : {}),
          }
        : { classified_by: "llm:local-medium" },
    );
  }

  const reads: Record<string, (request: JsonObject) => JsonObject> = {
    "ledger.track": track,
    "ledger.history.typed": historyTyped,
  };
  const writes: Record<string, (request: JsonObject) => JsonObject> = {
    "ledger.split.manual": split,
    "ledger.merge": merge,
    "ledger.classify.iva-derive": ivaDerive,
    "ledger.allocate": allocate,
    ...Object.fromEntries(
      LIFECYCLE_OPERATIONS.map((operation) => [
        operation,
        (request: JsonObject) => changeLifecycle(operation, request),
      ]),
    ),
  };
  return { reads, writes, remove, noteReview };
}
