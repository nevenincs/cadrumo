// A refusal as the window shows it: the words the backend served for it, the
// primary way out, the further ways out in the order they were served, or the
// sentence saying there is none. The window words none of these. An action
// without served words gets no control, and an action whose operation the
// window does not admit is shown disabled with one generic chrome reason.
//
// This module holds only types and pure functions; `refusalRoute.ts` binds the
// router to the host-admitted definition lists.

import type { LedgerDefinitionId, LedgerErrorDetail } from "./ledger";
import type { ModeloDefinitionId } from "./modelo";
import type {
  ActionArgumentSnapshot,
  ActionArgumentSource,
  ActionArgumentStatus,
  ActionConditionality,
  ActionEvidenceProvenance,
  AlternativeActionSnapshot,
  ConditionEvidenceSnapshot,
  NoRecoveryOutcome,
  OutputLanguage,
  PreconditionVerdictSnapshot,
  PublicScalar,
} from "./modeloContract/modelo";

/** One further way out, as the generated contract serves it. */
export type ServedAlternativeAction = AlternativeActionSnapshot;

/** A precondition verdict as served: the generated snapshot, whose optional
 * properties are the ones the wire leaves out. */
export type ServedVerdict = PreconditionVerdictSnapshot;

/** What a refusal notice is given: the refusal words the operation detail
 * served (`refusal_words`, as `servedRefusalWords` reads them) and the verdict
 * that settled it, when the refusal carries one. */
export type ServedRefusal = {
  refusal_words: string | null;
  refusal_words_language?: OutputLanguage | null;
  verdict: ServedVerdict | null;
};

/** The window place that hosts an admitted operation. */
export type WindowPlace =
  | { page: "ledger"; definition: LedgerDefinitionId }
  | { page: "declarations"; definition: ModeloDefinitionId };

/** The window's closed lists of host-admitted definitions, by the page that
 * hosts them. */
export type AdmittedDefinitions = {
  ledger: readonly LedgerDefinitionId[];
  declarations: readonly ModeloDefinitionId[];
};

/** The place hosting one served action: the first of its
 * `target_operation_ids`, in served order, that an admitted list holds by
 * exact match; null when the window admits none of them. */
export function placeIn(
  target_operation_ids: readonly string[],
  admitted: AdmittedDefinitions,
): WindowPlace | null {
  for (const operation of target_operation_ids) {
    const ledger = admitted.ledger.find((id) => id === operation);
    if (ledger !== undefined) return { page: "ledger", definition: ledger };
    const declarations = admitted.declarations.find((id) => id === operation);
    if (declarations !== undefined)
      return { page: "declarations", definition: declarations };
  }
  return null;
}

/** One served way out, in the verdict's order. */
export type RefusalWay = {
  role: "primary" | "alternative";
  action_id: string;
  target_operation_ids: string[];
  argument_bindings: ActionArgumentSnapshot[];
  missing_argument_names: string[];
  conditionality: ActionConditionality;
  action_words: string | null;
  action_words_language: OutputLanguage | null;
};

const words = (value: string | null | undefined) =>
  typeof value === "string" && value.trim() !== "" ? value : null;

// The wire leaves an unserved word or routing field out, so each is read as
// absent when it is missing.
function servedWay(
  role: RefusalWay["role"],
  action_id: string,
  action: Omit<AlternativeActionSnapshot, "action_id">,
): RefusalWay {
  return {
    role,
    action_id,
    target_operation_ids: action.target_operation_ids ?? [],
    argument_bindings: action.argument_bindings,
    missing_argument_names: action.missing_argument_names,
    conditionality: action.conditionality,
    action_words: words(action.action_words),
    action_words_language: action.action_words_language ?? null,
  };
}

/** The verdict's ways out: the primary action first, then the alternatives
 * exactly as served, never sorted, filtered or deduplicated. None beside a
 * no-recovery outcome. */
export function refusalWays(verdict: ServedVerdict | null): RefusalWay[] {
  if (!verdict || verdict.no_recovery_outcome !== null) return [];
  const ways: RefusalWay[] = [];
  if (verdict.action_id !== null)
    ways.push(servedWay("primary", verdict.action_id, verdict));
  for (const alternative of verdict.alternative_actions ?? [])
    ways.push(servedWay("alternative", alternative.action_id, alternative));
  return ways;
}

/** What a refusal control hands its caller. The notice never submits: a
 * `form` intent opens the destination's form for the `missing` arguments; a
 * `follow` intent opens the destination with `bindings`, which hold every
 * argument the action takes. */
export type RefusalIntent = {
  kind: "form" | "follow";
  action_id: string;
  place: WindowPlace;
  bindings: ActionArgumentSnapshot[];
  missing: string[];
};

/** One control the notice draws, in served order. A way without served words
 * draws none; a way the window cannot route is drawn disabled. */
export type RefusalControl = {
  role: "primary" | "alternative";
  words: string;
  language: OutputLanguage | null;
  /** Served as needing arguments before it can run: never styled as
   * certain. */
  conditional: boolean;
  /** Null when no admitted place hosts the action. */
  intent: RefusalIntent | null;
};

export function refusalControls(
  verdict: ServedVerdict | null,
  route: (target_operation_ids: readonly string[]) => WindowPlace | null,
): RefusalControl[] {
  const controls: RefusalControl[] = [];
  for (const way of refusalWays(verdict)) {
    if (way.action_words === null) continue;
    const place = route(way.target_operation_ids);
    const conditional =
      way.conditionality === "requires_arguments" ||
      way.missing_argument_names.length > 0;
    controls.push({
      role: way.role,
      words: way.action_words,
      language: way.action_words_language,
      conditional,
      intent:
        place === null
          ? null
          : {
              kind: conditional ? "form" : "follow",
              action_id: way.action_id,
              place,
              bindings: way.argument_bindings,
              missing: way.missing_argument_names,
            },
    });
  }
  return controls;
}

/** The served refusal sentence and the served no-recovery sentence, when
 * served. */
export function refusalSentences(refusal: ServedRefusal): {
  refusal: { words: string; language: OutputLanguage | null } | null;
  noRecovery: { words: string; language: OutputLanguage | null } | null;
} {
  const refused = words(refusal.refusal_words);
  const verdict = refusal.verdict;
  const none =
    verdict && verdict.no_recovery_outcome !== null
      ? words(verdict.no_recovery_words)
      : null;
  return {
    refusal:
      refused === null
        ? null
        : { words: refused, language: refusal.refusal_words_language ?? null },
    noRecovery:
      none === null
        ? null
        : {
            words: none,
            language: verdict?.no_recovery_words_language ?? null,
          },
  };
}

// The closed sets a stored verdict's tokens are checked against, each keyed by
// its generated union so a token the contract gains fails the type check here.
const CONDITIONALITY: Record<ActionConditionality, true> = {
  immediate: true,
  requires_arguments: true,
  not_applicable: true,
};
const NO_RECOVERY: Record<NoRecoveryOutcome, true> = {
  terminal: true,
  safety: true,
  operator_decision: true,
};
const LANGUAGE: Record<OutputLanguage, true> = {
  es: true,
  en: true,
  ca: true,
  hu: true,
};
const PROVENANCE: Record<ActionEvidenceProvenance, true> = {
  application_state: true,
  domain_evaluation: true,
  persisted_state: true,
  registry_record: true,
  runtime_observation: true,
};
const ARGUMENT_STATUS: Record<ActionArgumentStatus, true> = {
  resolved: true,
  missing: true,
};
const ARGUMENT_SOURCE: Record<ActionArgumentSource, true> = {
  "operator_action.verdict_context": true,
  "operator_action.condition_evidence": true,
  "operator_action.request_context": true,
};

type Json = Record<string, unknown>;
const isRecord = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const member = <T extends string>(
  set: Record<T, true>,
  value: unknown,
): value is T => typeof value === "string" && Object.hasOwn(set, value);
const text = (value: unknown): string | null =>
  typeof value === "string" ? value : null;
const texts = (value: unknown): string[] | null =>
  value === undefined
    ? []
    : Array.isArray(value) && value.every((item) => typeof item === "string")
      ? value
      : null;
const scalar = (value: unknown): PublicScalar | null =>
  typeof value === "string" ||
  typeof value === "number" ||
  typeof value === "boolean"
    ? value
    : null;
const optionalLanguage = (value: unknown): OutputLanguage | null | undefined =>
  value === undefined || value === null
    ? null
    : member(LANGUAGE, value)
      ? value
      : undefined;
const all = <T>(items: (T | null)[]): T[] | null =>
  items.some((item) => item === null) ? null : (items as T[]);

function argument(value: unknown): ActionArgumentSnapshot | null {
  if (!isRecord(value)) return null;
  const name = text(value.argument_name);
  const source = value.source ?? null;
  if (name === null || !member(ARGUMENT_STATUS, value.status)) return null;
  if (source !== null && !member(ARGUMENT_SOURCE, source)) return null;
  const held = value.value ?? null;
  const read = held === null ? null : scalar(held);
  if (held !== null && read === null) return null;
  return {
    argument_name: name,
    status: value.status,
    value: read,
    source,
    source_key: text(value.source_key),
    source_evidence_id: text(value.source_evidence_id),
  };
}

function evidence(value: unknown): ConditionEvidenceSnapshot | null {
  if (!isRecord(value) || !isRecord(value.values)) return null;
  const condition = text(value.condition_id);
  const id = text(value.evidence_id);
  if (condition === null || id === null) return null;
  if (!member(PROVENANCE, value.provenance)) return null;
  const values = all(
    Object.entries(value.values).map(([key, item]) => {
      const held = scalar(item);
      return held === null ? null : { key, value: held };
    }),
  );
  if (values === null) return null;
  return {
    condition_id: condition,
    evidence_id: id,
    provenance: value.provenance,
    values,
  };
}

/** The action fields a stored verdict and each of its alternatives share. */
function action(
  value: Json,
): Omit<AlternativeActionSnapshot, "action_id"> | null {
  const bindings = Array.isArray(value.argument_bindings ?? [])
    ? all(((value.argument_bindings ?? []) as unknown[]).map(argument))
    : null;
  const missing = texts(value.missing_argument_names);
  const targets = texts(value.target_operation_ids);
  const language = optionalLanguage(value.action_words_language);
  if (bindings === null || missing === null || targets === null) return null;
  if (language === undefined) return null;
  if (!member(CONDITIONALITY, value.conditionality)) return null;
  return {
    argument_bindings: bindings,
    missing_argument_names: missing,
    conditionality: value.conditionality,
    action_words: text(value.action_words),
    action_words_language: language,
    target_operation_ids: targets,
  };
}

const actionId = (value: unknown): string | null =>
  isRecord(value) ? text(value.action_id) : null;

/** The verdict a refused operation's error detail stored as JSON, with the
 * words and routing the worker served on it, in the generated snapshot's
 * shape; null when the detail carries none or carries one this window cannot
 * read, so the refusal is still shown by its words alone. */
export function servedVerdictFromJson(
  json: string | null | undefined,
): ServedVerdict | null {
  if (!json) return null;
  let value: unknown;
  try {
    value = JSON.parse(json);
  } catch {
    return null;
  }
  if (!isRecord(value)) return null;
  const condition = text(value.failed_condition_id);
  const primary = action(value);
  const proofs = Array.isArray(value.evidence)
    ? all((value.evidence as unknown[]).map(evidence))
    : null;
  const outcome = value.no_recovery_outcome ?? null;
  const noRecoveryLanguage = optionalLanguage(value.no_recovery_words_language);
  const primaryId =
    (value.action ?? null) === null ? null : actionId(value.action);
  if (condition === null || primary === null || proofs === null) return null;
  if (outcome !== null && !member(NO_RECOVERY, outcome)) return null;
  if (noRecoveryLanguage === undefined) return null;
  if ((value.action ?? null) !== null && primaryId === null) return null;
  const listed = value.alternative_actions ?? [];
  if (!Array.isArray(listed)) return null;
  const alternatives = all(
    (listed as unknown[]).map((item) => {
      if (!isRecord(item)) return null;
      const id = actionId(item.action);
      const fields = action(item);
      return id === null || fields === null
        ? null
        : { action_id: id, ...fields };
    }),
  );
  if (alternatives === null) return null;
  return {
    ...primary,
    failed_condition_id: condition,
    evidence: proofs,
    action_id: primaryId,
    no_recovery_outcome: outcome,
    no_recovery_words: text(value.no_recovery_words),
    no_recovery_words_language: noRecoveryLanguage,
    alternative_actions: alternatives,
  };
}

/** A refused operation as the window's one refusal notice takes it: the
 * sentence the backend served, its language, and the verdict the error detail
 * stored with the words and routing the worker served on its ways out, or its
 * no-way-out sentence. */
export function servedRefusal(
  words: string | null,
  detail: LedgerErrorDetail | null,
): ServedRefusal {
  const language = detail?.refusal_words_language ?? null;
  return {
    refusal_words: words,
    refusal_words_language: member(LANGUAGE, language) ? language : null,
    verdict: servedVerdictFromJson(detail?.precondition_verdict_json),
  };
}
