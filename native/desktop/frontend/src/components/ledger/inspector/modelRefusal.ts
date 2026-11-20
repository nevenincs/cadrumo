import type { LedgerErrorDetail, LedgerOutcome } from "../../../shell/ledger";
import { servedNextStep, servedRefusalWords } from "../../../shell/ledger";
import type {
  OperationNextStepV1,
  OperationOffHostConsentRemedyV1,
} from "../../../shell/ledgerDocumentContract";

/** The step that settles an off-host consent refusal. */
export type ConsentStep = Extract<
  OperationNextStepV1,
  { kind: "resolve_off_host_consent" }
>;

/** What a refused model review serves beyond its closed code: the sentence
 * the backend worded and the step that puts the refusal right. */
export type ModelRefusal = {
  words: string | null;
  step: OperationNextStepV1 | null;
};

/** What the backend served for a refused review; null when it served
 * neither, so the page falls back to the words of the code. */
export function modelRefusalOf(
  detail: LedgerErrorDetail | null | undefined,
): ModelRefusal | null {
  const words = servedRefusalWords(detail);
  const step = servedNextStep(detail);
  return words === null && step === null ? null : { words, step };
}

/** The served refusal of an outcome the page asked a review for; null for an
 * outcome that is not a refusal or served nothing. */
export function modelRefusalOfOutcome(
  outcome: LedgerOutcome,
): ModelRefusal | null {
  return outcome.kind === "refused" ? modelRefusalOf(outcome.detail) : null;
}

/** The consent step a refusal serves, where it serves one. */
export function consentStepOf(
  refusal: ModelRefusal | null | undefined,
): ConsentStep | null {
  return refusal?.step?.kind === "resolve_off_host_consent"
    ? refusal.step
    : null;
}

/** What choosing a remedy does where this window stands: open the agent's
 * model picker, or say with the served words where the person puts the
 * refusal right instead. The authorisation itself is not in this window yet,
 * so it always says. */
export type RemedyAction =
  { kind: "open_model_picker" } | { kind: "notice"; words: string };

export function remedyAction(
  remedy: OperationOffHostConsentRemedyV1,
  picker: { open(): void } | null,
): RemedyAction {
  if (remedy.kind === "switch_to_local_lane" && picker !== null)
    return { kind: "open_model_picker" };
  return { kind: "notice", words: remedy.unavailable_words };
}
