import type {
  SeededHistory,
  SelectedModel,
  SelectionChangeUnacknowledgedRefusalDetail,
} from "./shell/agentGatewayContract";

/** The typed code of a host refusal; the shell never shows the host's own
 * English message text. */
export function failureCode(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error)
    return String(error.code);
  return "unknown";
}

/** The finished sentence the product served for a refusal, which the host
 * passes on as served; null where it served none. */
export function failureWords(error: unknown): string | null {
  if (typeof error !== "object" || error === null) return null;
  const words = (error as { refusal_words?: unknown }).refusal_words;
  return typeof words === "string" && words.trim() !== "" ? words : null;
}

/** The context sizes a refusal states for a model that does not fit, as the
 * agent counted them; each only where the refusal knows it. */
export type ContextFit = {
  needed_tokens?: number;
  context_tokens?: number;
};

/** The context sizes `error` carries, or null where it carries none. */
export function failureFit(error: unknown): ContextFit | null {
  if (typeof error !== "object" || error === null) return null;
  const count = (name: "needed_tokens" | "context_tokens") => {
    const value = (error as Record<string, unknown>)[name];
    return typeof value === "number" && Number.isInteger(value) && value > 0
      ? value
      : undefined;
  };
  const needed = count("needed_tokens");
  const context = count("context_tokens");
  if (needed === undefined && context === undefined) return null;
  return {
    ...(needed !== undefined ? { needed_tokens: needed } : {}),
    ...(context !== undefined ? { context_tokens: context } : {}),
  };
}

/** What a run start refused for an unacknowledged change of model states:
 * the model the conversation ran with, the one asked for, and how much of
 * its history the new model is given, as the agent counted them. */
export type SelectionChangeFacts = Pick<
  SelectionChangeUnacknowledgedRefusalDetail,
  "previous" | "requested" | "history"
>;

const count = (value: unknown) =>
  typeof value === "number" && Number.isInteger(value) && value >= 0;

const selected = (value: unknown): value is SelectedModel =>
  typeof value === "object" &&
  value !== null &&
  typeof (value as { model?: unknown }).model === "string";

/** The facts of a refused change of model, where the refusal states them. */
export function failureSelectionChange(
  error: unknown,
): SelectionChangeFacts | null {
  if (typeof error !== "object" || error === null) return null;
  const facts = (error as { selection_change?: unknown }).selection_change;
  if (typeof facts !== "object" || facts === null) return null;
  const { previous, requested, history } = facts as Record<string, unknown>;
  if (!selected(previous) || !selected(requested)) return null;
  if (typeof history !== "object" || history === null) return null;
  const held = history as Record<string, unknown>;
  if (
    !count(held.retained_messages) ||
    !count(held.estimated_tokens) ||
    !count(held.omitted_messages)
  )
    return null;
  return { previous, requested, history: history as SeededHistory };
}
