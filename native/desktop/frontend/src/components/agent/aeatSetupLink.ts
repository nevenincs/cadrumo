/** Only this exact local route is actionable; no arguments or credentials. */
const AEAT_SETUP =
  /^cadrumo:\/\/profiles\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/aeat-auth$/;

export function aeatSetupProfile(url: string): string | null {
  const profile = AEAT_SETUP.exec(url)?.[1] ?? null;
  return profile === "00000000-0000-0000-0000-000000000000" ? null : profile;
}
