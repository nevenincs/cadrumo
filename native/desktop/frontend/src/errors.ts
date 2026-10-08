/** The typed code of a host refusal; the shell never shows the host's own
 * English message text. */
export function failureCode(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error)
    return String(error.code);
  return "unknown";
}
