// A refusal as the window shows it: the words the backend served for it, the
// primary way out, the further ways out in the order they were served, or the
// sentence saying there is none. The window words none of these. An action
// without served words gets no control, and an action whose operation the
// window does not admit is shown disabled with one generic chrome reason.
//
// This module holds only types and pure functions; `refusalRoute.ts` binds the
// router to the host-admitted definition lists.

import type { LedgerDefinitionId } from "./ledger";
import type { ModeloDefinitionId } from "./modelo";
import type {
  ActionArgumentSnapshot,
  ActionConditionality,
  AlternativeActionSnapshot,
  OutputLanguage,
  PreconditionVerdictSnapshot,
} from "./modeloContract/modelo";

/** The words and target the backend serves on one recovery action. Kept here
 * until the generated contract carries them; when it does, these fields come
 * from the generated `PreconditionVerdictSnapshot` and
 * `AlternativeActionSnapshot`, and this module is where the swap happens. */
export type ServedActionWords = {
  action_words?: string | null;
  action_words_language?: OutputLanguage | null;
  /** The registered operation the action opens. */
  target_command_key?: string | null;
};

export type ServedAlternativeAction = AlternativeActionSnapshot &
  ServedActionWords;

/** A precondition verdict with the served words it will carry. The wire
 * leaves `alternative_actions` out when it is empty. `no_recovery_words` is
 * served only beside a `no_recovery_outcome`. Kept here until the generated
 * contract carries them. */
export type ServedVerdict = Omit<
  PreconditionVerdictSnapshot,
  "alternative_actions"
> &
  ServedActionWords & {
    alternative_actions?: ServedAlternativeAction[];
    no_recovery_words?: string | null;
    no_recovery_words_language?: OutputLanguage | null;
  };

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

/** The place hosting `target_command_key`, by exact match against the
 * admitted lists; null when the window admits no such operation. */
export function placeIn(
  target_command_key: string | null | undefined,
  admitted: AdmittedDefinitions,
): WindowPlace | null {
  if (!target_command_key) return null;
  const ledger = admitted.ledger.find((id) => id === target_command_key);
  if (ledger !== undefined) return { page: "ledger", definition: ledger };
  const declarations = admitted.declarations.find(
    (id) => id === target_command_key,
  );
  if (declarations !== undefined)
    return { page: "declarations", definition: declarations };
  return null;
}

/** One served way out, in the verdict's order. */
export type RefusalWay = {
  role: "primary" | "alternative";
  action_id: string;
  target_command_key: string | null;
  argument_bindings: ActionArgumentSnapshot[];
  missing_argument_names: string[];
  conditionality: ActionConditionality;
  action_words: string | null;
  action_words_language: OutputLanguage | null;
};

const words = (value: string | null | undefined) =>
  typeof value === "string" && value.trim() !== "" ? value : null;

/** The verdict's ways out: the primary action first, then the alternatives
 * exactly as served, never sorted, filtered or deduplicated. None beside a
 * no-recovery outcome. */
export function refusalWays(verdict: ServedVerdict | null): RefusalWay[] {
  if (!verdict || verdict.no_recovery_outcome !== null) return [];
  const ways: RefusalWay[] = [];
  if (verdict.action_id !== null)
    ways.push({
      role: "primary",
      action_id: verdict.action_id,
      target_command_key: verdict.target_command_key ?? null,
      argument_bindings: verdict.argument_bindings,
      missing_argument_names: verdict.missing_argument_names,
      conditionality: verdict.conditionality,
      action_words: words(verdict.action_words),
      action_words_language: verdict.action_words_language ?? null,
    });
  for (const alternative of verdict.alternative_actions ?? [])
    ways.push({
      role: "alternative",
      action_id: alternative.action_id,
      target_command_key: alternative.target_command_key ?? null,
      argument_bindings: alternative.argument_bindings,
      missing_argument_names: alternative.missing_argument_names,
      conditionality: alternative.conditionality,
      action_words: words(alternative.action_words),
      action_words_language: alternative.action_words_language ?? null,
    });
  return ways;
}

/** What a refusal control hands its caller. The notice never submits: a
 * `form` intent opens the destination's form for the `missing` arguments; a
 * `follow` intent opens the destination with `bindings`, which hold every
 * argument the action takes. */
export type RefusalIntent = {
  kind: "form" | "follow";
  action_id: string;
  target_command_key: string;
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
  route: (target_command_key: string | null) => WindowPlace | null,
): RefusalControl[] {
  const controls: RefusalControl[] = [];
  for (const way of refusalWays(verdict)) {
    if (way.action_words === null) continue;
    const place = route(way.target_command_key);
    const conditional =
      way.conditionality === "requires_arguments" ||
      way.missing_argument_names.length > 0;
    controls.push({
      role: way.role,
      words: way.action_words,
      language: way.action_words_language,
      conditional,
      intent:
        place === null || way.target_command_key === null
          ? null
          : {
              kind: conditional ? "form" : "follow",
              action_id: way.action_id,
              target_command_key: way.target_command_key,
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
