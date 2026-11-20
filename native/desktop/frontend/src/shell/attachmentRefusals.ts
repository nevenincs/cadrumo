// How the window gathers the reads an off-host bar refused. The bar belongs to
// the installation, the profile or the mode, not to a file, so one answer
// covers every parked read it refuses and is worded once.

import type { DisclosureRefusalCode } from "./attachmentAdminContract";

/** The refusals that bar every off-host read alike, each with its own owner. */
export const BAR_CODES = [
  "gestor_mode",
  "cloud_upload_not_permitted",
  "profile_not_eligible",
  "profile_unreadable",
] as const satisfies readonly DisclosureRefusalCode[];

export type BarCode = (typeof BAR_CODES)[number];

export const isBarCode = (code: string): code is BarCode =>
  (BAR_CODES as readonly string[]).includes(code);

/** One parked read the service refused for a bar. */
export type BarredRead = {
  /** The agent's request for the read; the person answers it. */
  requestId: string;
  code: BarCode;
  /** The file's display name as the service gave it. */
  name: string | null;
};

/** The reads one bar refused, worded and answered together. */
export type BarredGroup = {
  code: BarCode;
  /** Each file once, in the order the reads arrived. */
  names: string[];
  /** Every request the group answers. */
  requestIds: string[];
};

/** Groups `reads` by bar, in the order each bar first refused one. */
export function groupBarredReads(reads: readonly BarredRead[]): BarredGroup[] {
  const groups = new Map<BarCode, BarredGroup>();
  for (const read of reads) {
    const group = groups.get(read.code) ?? {
      code: read.code,
      names: [],
      requestIds: [],
    };
    groups.set(read.code, group);
    group.requestIds.push(read.requestId);
    if (read.name !== null && !group.names.includes(read.name))
      group.names.push(read.name);
  }
  return [...groups.values()];
}

/** Each refusal in the closed set, in its own words. Any other failure could
 * not be recorded, and says so. */
export const refusalKey = (code: string) => {
  switch (code) {
    case "acknowledgement_missing":
      return "desktop.agent.attachment_refusal.acknowledgement_missing";
    case "reference_unknown":
      return "desktop.agent.attachment_refusal.reference_unknown";
    case "document_removed":
      return "desktop.agent.attachment_refusal.document_removed";
    case "gestor_mode":
      return "desktop.agent.attachment_refusal.gestor_mode";
    case "cloud_upload_not_permitted":
      return "desktop.agent.attachment_refusal.cloud_upload_not_permitted";
    case "profile_not_eligible":
      return "desktop.agent.attachment_refusal.profile_not_eligible";
    case "profile_unreadable":
      return "desktop.agent.attachment_refusal.profile_unreadable";
    case "file_changed_during_read":
      return "desktop.agent.attachment_refusal.file_changed_during_read";
    case "not_signed_in":
      return "desktop.agent.attachment_refusal.not_signed_in";
    case "grant_revoked":
      return "desktop.agent.attachment_refusal.grant_revoked";
    default:
      return "desktop.agent.attachment_refusal.service_failed";
  }
};
