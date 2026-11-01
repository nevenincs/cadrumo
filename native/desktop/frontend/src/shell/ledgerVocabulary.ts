// The ledger's closed vocabularies the product fixes in its language: a
// movement's classification, direction and lifecycle. The registry's own
// lists, which change with the law, are served and not held here.

/** A movement's classifications: the three a person decides, then the
 * dispositions the product sets. */
export const CLASSIFICATIONS = [
  "BUSINESS",
  "PERSONAL",
  "MIXED",
  "NOT_YET_PROCESSED",
  "PROCESSED_UNCLASSIFIED",
  "SKIPPED_BY_RULE",
  "FAILED_VALIDATION",
  "REVIEWED_EXCLUDED",
] as const;
export type Classification = (typeof CLASSIFICATIONS)[number];
export const isClassification = (id: string): id is Classification =>
  (CLASSIFICATIONS as readonly string[]).includes(id);

export const DIRECTIONS = [
  "INCOMING",
  "OUTGOING",
  "INTERNAL_TRANSFER",
] as const;
export type Direction = (typeof DIRECTIONS)[number];
export const isDirection = (id: string): id is Direction =>
  (DIRECTIONS as readonly string[]).includes(id);

export const LIFECYCLE_STATES = [
  "ACTIVE",
  "ARCHIVED",
  "STASHED",
  "SPLIT",
] as const;
export type LifecycleState = (typeof LIFECYCLE_STATES)[number];
export const isLifecycleState = (id: string): id is LifecycleState =>
  (LIFECYCLE_STATES as readonly string[]).includes(id);

/** What an import marked on a movement, as the list filters it. */
export const IMPORT_ISSUES = [
  "original-file",
  "gap",
  "duplicate",
  "parser",
] as const;
export type ImportIssue = (typeof IMPORT_ISSUES)[number];
