// What the scenario ledger's setup answers share: the refusals they raise,
// the decoding every handler starts with, and the sentence the backend
// serves for a refusal. Everything it answers is synthetic.

import type { JsonObject, JsonValue } from "../shell/ledger";
import servedEntryOptions from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import servedWords from "@fixtures/ledger-served-words/ledgerServedWords.json" with { type: "json" };

export const servedOptions = (family: string) =>
  servedEntryOptions.families.find((found) => found.family === family)!.options;

/** A request its registered contract would not decode. */
export class SetupRequestInvalid extends Error {}
/** Settled refused because the recordings behind the scenario hold no answer
 * for the request: the fixture states no figure of its own, so it has nothing
 * else it can honestly say. */
export class SetupRequestUnrecorded extends Error {}
/** Settled refused after it had kept part of what it was asked for: the
 * operation's effect is partial, neither none nor unknown. */
export class SetupKeptInPart extends Error {
  constructor(
    readonly reason: string,
    readonly detail: JsonObject | null = null,
  ) {
    super(reason);
  }
}
/** Settled without writing, with the refusal's code and its detail. */
export class SetupStopped extends Error {
  constructor(
    readonly reason: string,
    readonly detail: JsonObject | null = null,
  ) {
    super(reason);
  }
}

export type Tools = {
  profileId: string;
  today: string;
  now: () => string;
  events: () => string[];
  hex64: (text: string) => string;
  /** The file a token the window was given stands for. */
  fileOf: (token: JsonValue | undefined) => { name: string };
  /** The language the backend words a refusal in. */
  language: string;
};

export type Handler = (request: JsonObject) => JsonObject;

export const invalid = (): never => {
  throw new SetupRequestInvalid();
};
export const text = (value: JsonValue | undefined): string | null =>
  typeof value === "string" && value !== "" ? value : null;
export const required = (value: JsonValue | undefined): string =>
  text(value) ?? invalid();
export const whole = (value: JsonValue | undefined): number =>
  typeof value === "number" && Number.isInteger(value) ? value : invalid();
export const decimalOf = (value: JsonValue | undefined): string => {
  if (
    typeof value !== "object" ||
    value === null ||
    Array.isArray(value) ||
    typeof value.decimal !== "string" ||
    !/^(0|[1-9]\d*)(\.\d+)?$/.test(value.decimal)
  )
    return invalid();
  return value.decimal;
};
export const decimal = (value: string) => ({ decimal: value });
export const DATE = /^\d{4}-\d{2}-\d{2}$/;
export const fromKeys = (request: JsonObject, allowed: readonly string[]) => {
  if (Object.keys(request).some((key) => !allowed.includes(key))) invalid();
};

/** The sentence the backend serves for a refusal, in the window's language,
 * filled from the refusal's facts; nothing where a fact it names is not
 * held, as the backend then words the code alone. */
export const servedRefusal =
  (language: string) =>
  (
    family: keyof typeof servedWords,
    reason: string,
    facts: JsonObject = {},
  ): JsonObject => {
    const byLanguage = (
      servedWords[family] as Record<string, Record<string, string>>
    )[reason];
    if (!byLanguage) return {};
    const template = byLanguage[language] ?? byLanguage.en;
    if (template === undefined) return {};
    let missing = false;
    const words = template.replace(/\{(\w+)\}/g, (_, name: string) => {
      const fact = facts[name];
      if (fact === null || fact === undefined || typeof fact === "object") {
        missing = true;
        return "";
      }
      return String(fact);
    });
    if (missing) return {};
    return {
      refusal_words: words,
      refusal_words_language: byLanguage[language] ? language : "en",
    };
  };
