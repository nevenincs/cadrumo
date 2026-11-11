/** The typed code of a host refusal; the shell never shows the host's own
 * English message text. */
export function failureCode(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error)
    return String(error.code);
  return "unknown";
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
