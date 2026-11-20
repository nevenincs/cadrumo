import { expect, test } from "@playwright/test";
import {
  consentStepOf,
  modelRefusalOf,
  modelRefusalOfOutcome,
  remedyAction,
} from "../src/components/ledger/inspector/modelRefusal";
import {
  servedNextStep,
  type LedgerErrorDetail,
  type LedgerOutcome,
} from "../src/shell/ledger";
import type { OperationResolveOffHostConsentStepV1 } from "../src/shell/ledgerDocumentContract";
import { modelFailureText } from "../src/components/ledger/inspector/inspectorWords";

// The refusal a model review settles with when the selected model runs
// off-host and the read carries no consent: the window shows the sentence the
// backend served and the two remedies it served, never the generic words for a
// model that cannot be reached.

const SENTENCE = "Reading this document off-host was refused (synthetic).";

const consentStep: OperationResolveOffHostConsentStepV1 = {
  kind: "resolve_off_host_consent",
  words: "Choose how to read this document",
  remedies: [
    {
      kind: "authorise_off_host",
      words: "Allow this document to be read off this computer",
      unavailable_words: "Allowing off-host reads comes with the queue.",
    },
    {
      kind: "switch_to_local_lane",
      words: "Switch to a model that runs on this computer",
      unavailable_words: "Pick a local model in the agent's picker.",
    },
  ],
};

const detail = (extra: Partial<LedgerErrorDetail>): LedgerErrorDetail => ({
  detail_version: 1,
  kind: "registered_error",
  error_code: "REFUSED_LEDGER_OFF_HOST_CONSENT_REQUIRED",
  message_key: "errors.refused.refused_llm_consent",
  context: [],
  context_entries_omitted: 0,
  precondition_verdict_json: null,
  ...extra,
});

const refused = (served: LedgerErrorDetail | null): LedgerOutcome => ({
  kind: "refused",
  operation_id: "a".repeat(64),
  revision: 3,
  reason: "REFUSED_LEDGER_OFF_HOST_CONSENT_REQUIRED",
  detail: served,
});

const served = detail({
  refusal_words: SENTENCE,
  refusal_words_language: "en",
  next_step: consentStep,
});

test("a consent refusal serves its sentence and both typed remedies", () => {
  const refusal = modelRefusalOfOutcome(refused(served));
  expect(refusal?.words).toBe(SENTENCE);
  const step = consentStepOf(refusal);
  expect(step?.remedies.map((remedy) => remedy.kind)).toEqual([
    "authorise_off_host",
    "switch_to_local_lane",
  ]);
  expect(servedNextStep(served)).toEqual(consentStep);
});

test("the served sentence is not the words for an unavailable model", () => {
  const refusal = modelRefusalOfOutcome(refused(served));
  const generic = modelFailureText(
    (key: string) => `generic:${key}`,
    "REFUSED_LEDGER_OFF_HOST_CONSENT_REQUIRED",
  );
  expect(refusal?.words).not.toBe(generic);
  expect(refusal?.words).toBe(SENTENCE);
});

test("a refusal that served nothing keeps the words of its code", () => {
  expect(modelRefusalOfOutcome(refused(detail({})))).toBeNull();
  expect(modelRefusalOfOutcome(refused(null))).toBeNull();
  expect(modelRefusalOf(undefined)).toBeNull();
});

test("a consent step with no usable remedy is not served", () => {
  const empty = detail({
    refusal_words: SENTENCE,
    refusal_words_language: "en",
    next_step: { ...consentStep, remedies: [] } as never,
  });
  expect(servedNextStep(empty)).toBeNull();
  expect(consentStepOf(modelRefusalOf(empty))).toBeNull();
});

test("a remedy opens the model picker, or says where the person goes", () => {
  const authorise = {
    kind: "authorise_off_host",
    words: "Allow",
    unavailable_words: "Comes with the queue.",
  } as const;
  const local = {
    kind: "switch_to_local_lane",
    words: "Switch",
    unavailable_words: "Pick a local model in the agent's picker.",
  } as const;
  const picker = { open: () => undefined };
  expect(remedyAction(local, picker)).toEqual({ kind: "open_model_picker" });
  expect(remedyAction(local, null)).toEqual({
    kind: "notice",
    words: local.unavailable_words,
  });
  // The authorisation is not in this window yet: it always says so.
  expect(remedyAction(authorise, picker)).toEqual({
    kind: "notice",
    words: authorise.unavailable_words,
  });
});
