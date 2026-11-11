import { expect, test } from "@playwright/test";
import { refusalWords } from "../src/components/agent/agentRefusalWords";
import { failureFit } from "../src/errors";
import type { Translate } from "../src/shell/strings";

// A model that does not fit is said with the context sizes its refusal
// counted: the shortfall where both are known, the context it could not be
// loaded with where only that is, and the general words otherwise.

const said: string[] = [];
const t = Object.assign(
  (key: string, values?: Record<string, string | number>) => {
    said.push(JSON.stringify(values ?? {}));
    return key;
  },
  { locale: "en" },
) as Translate;
const DOES_NOT_FIT = "agent_gateway_model_does_not_fit";

test("a refusal's context sizes are read as positive whole numbers only", () => {
  expect(
    failureFit({
      code: DOES_NOT_FIT,
      needed_tokens: 17700,
      context_tokens: 16384,
    }),
  ).toEqual({ needed_tokens: 17700, context_tokens: 16384 });
  expect(failureFit({ code: DOES_NOT_FIT, context_tokens: 8192 })).toEqual({
    context_tokens: 8192,
  });
  for (const unusable of [0, -1, 1.5, "17700", null])
    expect(
      failureFit({ code: DOES_NOT_FIT, needed_tokens: unusable }),
    ).toBeNull();
  expect(failureFit({ code: DOES_NOT_FIT })).toBeNull();
  expect(failureFit("refused")).toBeNull();
  expect(failureFit(null)).toBeNull();
});

test("the shortfall is said with both sizes, formatted for the locale", () => {
  said.length = 0;
  expect(
    refusalWords(t, DOES_NOT_FIT, {
      needed_tokens: 17700,
      context_tokens: 16384,
    }),
  ).toBe("desktop.agent.model_does_not_fit_shortfall");
  expect(JSON.parse(said[0] ?? "null")).toEqual({
    needed: "17,700",
    context: "16,384",
  });
});

test("a load refused for memory is said with the context it tried", () => {
  said.length = 0;
  expect(refusalWords(t, DOES_NOT_FIT, { context_tokens: 8192 })).toBe(
    "desktop.agent.model_does_not_fit_memory",
  );
  expect(JSON.parse(said[0] ?? "null")).toEqual({ context: "8,192" });
});

test("without sizes, and for any other code, the words are unchanged", () => {
  expect(refusalWords(t, DOES_NOT_FIT)).toBe(
    "desktop.agent.model_does_not_fit_refused",
  );
  expect(refusalWords(t, DOES_NOT_FIT, { needed_tokens: 17700 })).toBe(
    "desktop.agent.model_does_not_fit_refused",
  );
  expect(
    refusalWords(t, "agent_gateway_model_not_installed", {
      needed_tokens: 1,
      context_tokens: 1,
    }),
  ).toBe("desktop.agent.model_not_installed_refused");
});
