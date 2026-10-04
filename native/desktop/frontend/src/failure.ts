export type HostFailure = { code: string; operation: string; message: string };

export function failureMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "message" in error) {
    const code = "code" in error ? `${String(error.code)}: ` : "";
    return code + String(error.message);
  }
  return String(error);
}
