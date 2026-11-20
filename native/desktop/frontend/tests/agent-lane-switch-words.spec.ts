import { expect, test } from "@playwright/test";
import type { ComponentProps } from "react";
import type { LocalisedNotice } from "./support/localisedNotice";
import { markupOf } from "./support/markup";

// What is said over the composer about a change of model and about a carried
// conversation: each count agrees with the noun it counts in the window's
// language, and a model is named as the picker names it. The expected
// sentences are written out here, not derived from the catalogue.

const draw = () =>
  markupOf<ComponentProps<typeof LocalisedNotice>>(
    "../tests/support/localisedNotice.tsx",
    "LocalisedNotice",
  );

const NO_ACTION = () => {};
const names: Record<string, string> = {
  "fixture-deep": "Fixture Deep",
  "fixture-quick": "Fixture Quick",
};

/** The words a markup shows: tags dropped and the escapes React writes undone. */
const textOf = (markup: string) =>
  markup
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();

const asked = (
  retained: number,
  omitted: number,
): ComponentProps<typeof LocalisedNotice>["changeAsk"] => ({
  previous: { model: "fixture-deep", effort: null },
  requested: { model: "fixture-quick", effort: null },
  history: {
    retained_messages: retained,
    estimated_tokens: 37,
    omitted_messages: omitted,
  },
});

const change = async (locale: string, retained: number, omitted: number) =>
  textOf(
    (await draw())({
      locale,
      changeAsk: asked(retained, omitted),
      carryFrom: null,
      carried: null,
      modelName: (model) => names[model] ?? model,
      onConfirmChange: NO_ACTION,
      onWithdrawChange: NO_ACTION,
      onBackToSource: NO_ACTION,
    }),
  );

const carry = async (locale: string, carried: number, omitted: number) =>
  textOf(
    (await draw())({
      locale,
      changeAsk: null,
      carryFrom: null,
      carried: {
        source_run_id: "r",
        carried_turns: carried,
        omitted_turns: omitted,
        carried_tokens: 10,
        omitted_tokens: 10,
      },
      modelName: (model) => model,
      onConfirmChange: NO_ACTION,
      onWithdrawChange: NO_ACTION,
      onBackToSource: NO_ACTION,
    }),
  );

test("a change of model names both models as the picker does", async () => {
  const said = await change("es", 4, 0);
  expect(said).toContain("de Fixture Deep a Fixture Quick.");
  expect(said).not.toContain("fixture-deep");
  expect(said).not.toContain("fixture-quick");
});

test("a model the picker does not name is said by its id", async () => {
  const said = textOf(
    (await draw())({
      locale: "en",
      changeAsk: asked(4, 0),
      carryFrom: null,
      carried: null,
      modelName: (model) => model,
      onConfirmChange: NO_ACTION,
      onWithdrawChange: NO_ACTION,
      onBackToSource: NO_ACTION,
    }),
  );
  expect(said).toContain("from fixture-deep to fixture-quick.");
});

test("in Spanish each count of a change of model agrees with its noun", async () => {
  expect(await change("es", 1, 2)).toContain(
    "El modelo nuevo recibe 1 mensaje de esta conversación (unos 37 tokens). Se omiten 2 mensajes anteriores.",
  );
  expect(await change("es", 2, 1)).toContain(
    "El modelo nuevo recibe 2 mensajes de esta conversación (unos 37 tokens). Se omite 1 mensaje anterior.",
  );
  expect(await change("es", 0, 0)).toContain(
    "El modelo nuevo recibe 0 mensajes de esta conversación (unos 37 tokens). Se omiten 0 mensajes anteriores.",
  );
});

test("in English each count of a change of model agrees with its noun", async () => {
  expect(await change("en", 1, 1)).toContain(
    "The new model gets 1 message of this conversation (about 37 tokens). 1 older message is left out.",
  );
  expect(await change("en", 3, 0)).toContain(
    "The new model gets 3 messages of this conversation (about 37 tokens). 0 older messages are left out.",
  );
});

test("in Catalan each count of a change of model agrees with its noun", async () => {
  expect(await change("ca", 1, 1)).toContain(
    "El model nou rep 1 missatge d'aquesta conversa (uns 37 tokens). S'omet 1 missatge anterior.",
  );
  expect(await change("ca", 2, 2)).toContain(
    "El model nou rep 2 missatges d'aquesta conversa (uns 37 tokens). S'ometen 2 missatges anteriors.",
  );
});

test("Hungarian keeps its noun singular after a number", async () => {
  expect(await change("hu", 1, 1)).toContain(
    "Az új modell 1 üzenetet kap ebből a beszélgetésből (kb. 37 token). 1 korábbi üzenet kimarad.",
  );
  expect(await change("hu", 2, 2)).toContain(
    "Az új modell 2 üzenetet kap ebből a beszélgetésből (kb. 37 token). 2 korábbi üzenet kimarad.",
  );
});

test("a carried conversation counts its turns in the right number", async () => {
  expect(await carry("es", 1, 1)).toBe(
    "Esta conversación empezó con 1 turno de la anterior. Se omitió 1 turno más antiguo.",
  );
  expect(await carry("es", 2, 3)).toBe(
    "Esta conversación empezó con 2 turnos de la anterior. Se omitieron 3 turnos más antiguos.",
  );
  expect(await carry("en", 1, 2)).toBe(
    "This conversation began with 1 turn of the earlier one. 2 older turns were left out.",
  );
  expect(await carry("ca", 1, 1)).toBe(
    "Aquesta conversa va començar amb 1 torn de l'anterior. Es va ometre 1 torn més antic.",
  );
  expect(await carry("hu", 1, 1)).toBe(
    "Ez a beszélgetés az előző 1 körével indult. 1 régebbi kör kimaradt.",
  );
});
