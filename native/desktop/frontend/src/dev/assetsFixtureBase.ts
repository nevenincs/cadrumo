// What the scenario ledger's Assets simulation shares across its parts: the
// scenario's clock and vocabulary, whole-cent amounts and the element it holds.

import type {
  DescriptorFacts,
  DisposalFacts,
  MethodFactKind,
  ReasonFactKind,
} from "@/shell/ledgerSetup";
import type { JsonObject } from "../shell/ledger";
import {
  METHOD_FACTS,
  SCENARIO_TODAY,
  type ScenarioElement,
} from "./assetsRegister";

export type Handler = (request: JsonObject) => JsonObject;

/** One fact an election of a method states, as the options serve it. */
export type ServedFact = {
  path: string[];
  kind: MethodFactKind;
  required: boolean;
  required_with_group: boolean;
  token_family: string | null;
  tokens: string[];
};

/** The facts the options serve for each method, whichever kind admits it. */
export const SERVED_METHOD_FACTS = Object.values(METHOD_FACTS)
  .flat()
  .filter(
    (found, at, all) =>
      all.findIndex((other) => other.method === found.method) === at,
  ) as unknown as { method: string; facts: ServedFact[] }[];

export type Tools = {
  now: () => string;
  hex64: (text: string) => string;
  /** Throws the refusal of a request its contract would not decode. */
  invalid: () => never;
  /** Throws a refusal the ledger settles with its own result as detail. */
  stop: (reason: string, detail: JsonObject) => never;
};

/** The scenario's date: the register reads as of it. */
export const VALIDATION = "REFUSED_ACTIVIDAD_ASSET_VALIDATION";
export const INCOMPLETE = "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE";
export const UNSUPPORTED = "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED";
export const CLAIM_CONFLICT = "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT";
export const ERRORS = "ledger.actividad_asset.errors.";
export const STATE = "ledger.actividad_asset.non_deductible_iva_state.";
export const FINDING = "ledger.actividad_asset.disposal_finding.";
export const FAMILY = "ledger.actividad_asset.";
/** The scenario clock's year: the register reads plans through it. */
export const todayYear = Number(SCENARIO_TODAY.slice(0, 4));
export const DATE = /^\d{4}-\d{2}-\d{2}$/;

export const json = <T>(value: T): JsonObject => value as unknown as JsonObject;
export const dec = (value: string) => ({ decimal: value });

/** A reason fact stated with the kind of the value it was raised with, as the
 * backend serves it; a bare string is a text. */
export type Fact = string | { value: string; kind: ReasonFactKind };
export const typed =
  (kind: ReasonFactKind) =>
  (value: string | number): Fact => ({ value: String(value), kind });
export const asDate = typed("date");
export const asCount = typed("count");
export const asAmount = typed("amount");
export const asPercent = typed("percent");

// ---- Amounts, in whole cents --------------------------------------------------

export const toCents = (text: string): number => Math.round(Number(text) * 100);
export const fromCents = (cents: number): string => (cents / 100).toFixed(2);

export const leap = (year: number) =>
  (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
export const daysBetween = (from: string, until: string) =>
  Math.round((Date.parse(until) - Date.parse(from)) / 86_400_000);
export const later = (a: string, b: string) => (a > b ? a : b);
export const dayBefore = (iso: string) =>
  new Date(Date.parse(iso) - 86_400_000).toISOString().slice(0, 10);
export const dayAfter = (iso: string) =>
  new Date(Date.parse(iso) + 86_400_000).toISOString().slice(0, 10);
/** A span with the last day it covers beside its exclusive boundary. */
export const withThrough = <T extends { covered_until: string }>(span: T) => ({
  ...span,
  covered_through: dayBefore(span.covered_until),
});
export const earlier = (a: string, b: string) => (a < b ? a : b);

/** The charge of a span on the tax year's cumulative curve: each end is
 * rounded, so contiguous spans add up to the year's figure. */
export function chargeFor(
  annual: string,
  window: string,
  from: string,
  until: string,
  year: number,
): string {
  const days = leap(year) ? 366 : 365;
  const upTo = (point: string) =>
    Math.round((toCents(annual) * daysBetween(window, point)) / days);
  return fromCents(upTo(until) - upTo(from));
}

// ---- The register ----------------------------------------------------------------

/** What the register holds of one element. */
export type Element = Omit<ScenarioElement, "id"> & {
  id: string;
  /** The facts of the latest description. */
  descriptor: DescriptorFacts | null;
  /** The day after the last day of service, if it has a baja. */
  outOfService: string | null;
  /** The baja the element carries, if any. */
  baja: DisposalFacts | null;
};

export const textOf = (found: unknown): string | null =>
  typeof found === "string" && found !== "" ? found : null;
export const decimalOf = (found: unknown): string | null =>
  found !== null &&
  typeof found === "object" &&
  typeof (found as { decimal?: unknown }).decimal === "string"
    ? (found as { decimal: string }).decimal
    : null;

/** The reads that take the language their sentences are said in. */
export const TAKES_LANGUAGE = new Set<string>([
  "ledger.actividad-asset.list",
  "ledger.actividad-asset.plan",
  "ledger.actividad-asset.disposal-calculate",
]);

/** The fields of a revision that state a token, which the history words by
 * the catalogue key of the token. */
export const TOKEN_FIELDS: Record<string, string> = {
  acquired_condition: "acquired_condition",
  acquisition_shape: "acquisition_shape",
  "basis.stage": "basis_stage",
  "opening_history.status": "opening_history_status",
};
