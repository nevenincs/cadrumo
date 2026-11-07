// The scenario ledger's answers to the Assets tab's operations: a register of
// synthetic elements (see `assetsRegister.ts`) read as the backend reads it, and
// the writes the tab sends, answered with the reasons the backend gives. A
// write changes what the next read says, but the figures of a plan stay the
// recorded ones: only a claim, a description, a correction and a baja move
// anything, and a plan is never recalculated. An element made through create
// starts with a plan worked out for a linear election and the reason there is
// none for any other; the request it is made from is judged as the backend
// judges a revision.

import type { OutputLanguage } from "../shell/ledger";
import { ledgerLanguage } from "../shell/ledgerLanguage";
import { type Handler, TAKES_LANGUAGE, type Tools } from "./assetsFixtureBase";
import { makeRegister } from "./assetsFixtureRegister";
import { makeWords } from "./assetsFixtureWords";
import { makeWrites } from "./assetsFixtureWrites";

export function assetOperations(tools: Tools) {
  /** The language the call in hand is answered in: the one it asks for, else
   * the one the window shows, as a worker answers in the language it runs in. */
  const session = { language: "es" as OutputLanguage };
  // The register words a refusal's detail through the sentences, which read
  // the register's elements: they are made after it and reached when it stops.
  const late = { words: null as ReturnType<typeof makeWords> | null };
  const register = makeRegister(tools, session, (detail) =>
    late.words === null ? detail : late.words.wordedDetail(detail),
  );
  const words = makeWords(session, register.elements);
  late.words = words;
  const { wordedDetail, worded, wordedHandoff } = words;
  const { reads, describe } = register;
  const {
    forecast,
    inspect,
    filingHandoff,
    calculate,
    dispose,
    create,
    correct,
    claim,
  } = makeWrites(register);

  /** A handler answered in the language of its call, its sentences said. */
  const speaking =
    (definition: string, handler: Handler): Handler =>
    (request) => {
      const { output_language: asked, ...rest } = request;
      session.language = (
        typeof asked === "string" ? asked : (ledgerLanguage() ?? "es")
      ) as OutputLanguage;
      const answer = handler(TAKES_LANGUAGE.has(definition) ? rest : request);
      return definition === "ledger.actividad-asset.filing-handoff"
        ? wordedHandoff(wordedDetail(answer))
        : worded(definition, answer);
    };
  const spoken = (handlers: Record<string, Handler>): Record<string, Handler> =>
    Object.fromEntries(
      Object.entries(handlers).map(([definition, handler]) => [
        definition,
        speaking(definition, handler),
      ]),
    );

  return {
    reads: spoken({
      ...reads,
      "ledger.actividad-asset.forecast": forecast,
      "ledger.actividad-asset.inspect": inspect,
      "ledger.actividad-asset.filing-handoff": filingHandoff,
      "ledger.actividad-asset.disposal-calculate": calculate,
    } as Record<string, Handler>),
    writes: spoken({
      "ledger.actividad-asset.describe": describe,
      "ledger.actividad-asset.dispose": dispose,
      "ledger.actividad-asset.create": create,
      "ledger.actividad-asset.correct": correct,
      "ledger.actividad-asset.claim": claim,
    } as Record<string, Handler>),
  };
}
