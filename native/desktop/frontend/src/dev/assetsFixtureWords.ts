// The register's own sentences for the Assets simulation: each is the one
// the backend said for the same reason, facts and language, looked up in a
// recording.

import type { ReasonFact } from "@/shell/ledgerSetup";
import type { JsonObject, JsonValue } from "../shell/ledger";
import { said } from "./assetsServedWords";
import { decimalOf, textOf } from "./assetsFixtureBase";
import type { Register, Session } from "./assetsFixtureRegister";

export function makeWords(session: Session, elements: Register["elements"]) {
  // ---- The register's own sentences ---------------------------------------
  // Each is the one the backend said for the same reason, facts and session.language,
  // looked up in a recording; none is worded here. What the recording does not
  // hold is served as the backend serves a sentence it cannot say whole: null.

  /** A reason said whole, as it was recorded. */
  function reasonWords(
    key: string | null,
    reasonFacts: readonly ReasonFact[],
  ): string | null {
    if (key === null) return null;
    return (
      said(
        {
          kind: "reason",
          key,
          facts: reasonFacts.map(({ key: name, value, kind }) => ({
            key: name,
            value,
            kind,
          })),
        },
        session.language,
      ) ?? null
    );
  }
  /** The sentence telling which entry settles what a reason lacks. */
  function remedyWords(fieldKey: string | null): string | null {
    if (fieldKey === null) return null;
    return (
      said({ kind: "remedy", field_key: fieldKey }, session.language) ?? null
    );
  }
  const factsOf = (found: unknown): ReasonFact[] =>
    Array.isArray(found) ? (found as ReasonFact[]) : [];
  const rowsOf = (found: unknown): JsonObject[] =>
    Array.isArray(found) ? (found as JsonObject[]) : [];

  /** A refusal with the sentence said for it. */
  function wordedRefusal(refusal: JsonObject): JsonObject {
    const words = reasonWords(
      textOf(refusal.reason_key),
      factsOf(refusal.reason_facts),
    );
    return words === null
      ? refusal
      : {
          ...refusal,
          refusal_words: words,
          refusal_words_language: session.language,
        };
  }
  /** The detail of a refused answer, with its refusal worded. */
  function wordedDetail(detail: JsonObject): JsonObject {
    const refusal = detail.refusal;
    return refusal !== null && typeof refusal === "object"
      ? { ...detail, refusal: wordedRefusal(refusal as JsonObject) }
      : detail;
  }
  function wordedPlanRow(row: JsonObject): JsonObject {
    return {
      ...row,
      absence_reason_words: reasonWords(
        textOf(row.absence_reason_key),
        factsOf(row.absence_reason_facts),
      ),
      absence_remedy_words: remedyWords(textOf(row.absence_remedy_field_key)),
      claimable_refusal_words: reasonWords(
        textOf(row.claimable_refusal_key),
        factsOf(row.claimable_refusal_facts),
      ),
      claimable_refusal_remedy_words: remedyWords(
        textOf(row.claimable_refusal_remedy_field_key),
      ),
      minimum_reason_words: reasonWords(textOf(row.minimum_reason_key), []),
      words_language: session.language,
    };
  }

  /** A result with every sentence the register serves for it filled in. */
  function worded(definition: string, result: JsonObject): JsonObject {
    const out = wordedDetail(result);
    if (definition === "ledger.actividad-asset.list")
      return {
        ...out,
        rows: rowsOf(out.rows).map((row) => {
          const field = textOf(row.opening_remedy_field_key);
          return field === null
            ? row
            : {
                ...row,
                opening_remedy_words: remedyWords(field),
                words_language: session.language,
              };
        }),
      };
    if (definition === "ledger.actividad-asset.plan") {
      const limits = out.limits as JsonObject | null | undefined;
      return {
        ...out,
        rows: out.rows === null ? null : rowsOf(out.rows).map(wordedPlanRow),
        limits:
          limits === null || limits === undefined
            ? null
            : {
                ...limits,
                unavailable_reason_words: reasonWords(
                  textOf(limits.unavailable_reason_key),
                  factsOf(limits.unavailable_reason_facts),
                ),
                words_language: session.language,
              },
        advisories: rowsOf(out.advisories).map((advisory) => ({
          ...advisory,
          words: reasonWords(textOf(advisory.label_key), []),
          words_language: session.language,
        })),
      };
    }
    if (definition === "ledger.actividad-asset.disposal-calculate") {
      const calculation = out.calculation as JsonObject | null | undefined;
      return calculation === null || calculation === undefined
        ? out
        : {
            ...out,
            calculation: {
              ...calculation,
              findings: rowsOf(calculation.findings).map((finding) => ({
                ...finding,
                words: reasonWords(textOf(finding.label_key), []),
                words_language: session.language,
              })),
            },
          };
    }
    return out;
  }

  /** The handoff with its intervals, the elements its Modelo 130 amounts
   * leave out and the sentence for an amount that is partial, all said. */
  function wordedHandoff(result: JsonObject): JsonObject {
    const handoff = result.filing_handoff as JsonObject | null | undefined;
    if (handoff === null || handoff === undefined) return result;
    const nameOf = (id: string) => {
      const name = elements.get(id)?.list.name;
      return name !== null && name !== undefined && name.trim() !== ""
        ? name
        : null;
    };
    const gaps = rowsOf(handoff.m100_gaps).map((gap) => ({
      ...gap,
      words:
        said(
          {
            kind: "gap",
            gap_kind: gap.kind as string,
            name: nameOf(gap.asset_id as string),
            covered_from: gap.covered_from as string,
            covered_through: gap.covered_through as string,
            accrued: decimalOf(gap.accrued),
          },
          session.language,
        ) ?? null,
      words_language: session.language,
    }));
    const projections = [handoff.material_m130, handoff.intangible_m130].filter(
      (found): found is JsonObject => found !== null && found !== undefined,
    );
    const partial = (found: JsonValue | undefined): JsonValue => {
      if (found === null || found === undefined) return null;
      const projection = found as JsonObject;
      const count = (projection.unavailable_asset_ids as string[]).length;
      return count === 0
        ? { ...projection, partial_words: null, words_language: null }
        : {
            ...projection,
            partial_words:
              said({ kind: "partial", count }, session.language) ?? null,
            words_language: session.language,
          };
    };
    const leftOut = (
      [
        ["free_gap", "free_gap_asset_ids"],
        ["agrarian_excluded", "agrarian_excluded_asset_ids"],
        ["unavailable", "unavailable_asset_ids"],
      ] as const
    ).flatMap(([reason, field]) => {
      const ids = [
        ...new Set(projections.flatMap((found) => found[field] as string[])),
      ];
      if (ids.length === 0) return [];
      const words =
        said(
          { kind: "left_out", reason, names: ids.map(nameOf) },
          session.language,
        ) ?? null;
      return words === null
        ? []
        : [{ reason, asset_ids: ids, words, words_language: session.language }];
    });
    return {
      ...result,
      filing_handoff: {
        ...handoff,
        m100_gaps: gaps,
        material_m130: partial(handoff.material_m130),
        intangible_m130: partial(handoff.intangible_m130),
        left_out: leftOut,
      },
    };
  }

  return { wordedDetail, worded, wordedHandoff };
}
