/** The pages a link may open, by the word the link spells them with, as
 * the navigation register's TUI views. */
const PAGES: Readonly<Record<string, string>> = {
  home: "home",
  ledger: "ledger",
  withholding: "withholding",
  declarations: "declarations",
  "aeat-sync": "aeat-sync",
  operations: "operations",
  installation: "installation",
  setup: "setup",
  reference: "reference",
  profile: "profile",
  "aeat-auth": "profile/aeat-access",
};

/** Only this exact shape is a page: no arguments, credentials or other hosts. */
const PAGE =
  /^cadrumo:\/\/profiles\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/([a-z-]+)$/;
const NIL = "00000000-0000-0000-0000-000000000000";

export type CadrumoLink =
  /** Not Cadrumo's to open: an address for the browser, or for nobody. */
  | { kind: "other" }
  /** Cadrumo's scheme, but no page this window can open. */
  | { kind: "malformed" }
  | { kind: "page"; profile: string; destination: string };

export function cadrumoLink(url: string): CadrumoLink {
  if (!/^cadrumo:/i.test(url)) return { kind: "other" };
  const match = PAGE.exec(url);
  const profile = match?.[1];
  const page = match?.[2];
  const destination =
    page !== undefined && Object.hasOwn(PAGES, page) ? PAGES[page] : undefined;
  if (!profile || profile === NIL || !destination) return { kind: "malformed" };
  return { kind: "page", profile, destination };
}
