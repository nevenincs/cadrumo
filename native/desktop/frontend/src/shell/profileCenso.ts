export type CensoReadiness = {
  provider: string;
  route: string;
  ready: boolean;
  requirements: {
    field: string;
    satisfied: boolean;
    reason: string;
    secret: boolean;
  }[];
};
export type CensoSnapshot = {
  operation: string;
  state:
    | "reading"
    | "device"
    | "review"
    | "done"
    | "stopped"
    | "unknown"
    | "unsupported";
  can_cancel: boolean;
  review_digest: string | null;
  fields: {
    path: string;
    current: string | null;
    incoming: string | null;
    preserve: boolean;
  }[];
};
export type CensoDecision = "apply" | "reject" | "cancel";
export type CensoPort = {
  observe?(changed: () => void): Promise<() => void>;
  readiness(profile: string): Promise<CensoReadiness>;
  start(profile: string): Promise<CensoSnapshot>;
  status(profile: string, operation: string): Promise<CensoSnapshot>;
  answer(
    profile: string,
    operation: string,
    reviewDigest: string | null,
    decision: CensoDecision,
  ): Promise<CensoSnapshot>;
};

// Closed runtime reasons, never arbitrary keys or raw field paths as copy.
export const censoRequirementKeys = {
  profile_tax_id_required: "auth.sync.requirement.profile_tax_id_required",
  auth_method_required: "auth.sync.requirement.auth_method_required",
  certificate_file_required: "auth.sync.requirement.certificate_file_required",
  certificate_passphrase_required:
    "auth.sync.requirement.certificate_passphrase_required",
  clave_identity_required: "auth.sync.requirement.clave_identity_required",
  profile_identity_must_match:
    "auth.sync.requirement.profile_identity_must_match",
  nie_support_required: "auth.sync.requirement.nie_support_required",
  dni_validity_required: "auth.sync.requirement.dni_validity_required",
  clave_password_required: "auth.sync.requirement.clave_password_required",
  no_path_set: "auth.sync.requirement.certificate_file_required",
  file_missing: "auth.sync.requirement.file_missing",
  unreadable: "auth.sync.requirement.unreadable",
  corrupt: "auth.sync.requirement.corrupt",
  expired: "auth.sync.requirement.expired",
  expiring: "auth.sync.requirement.expiring",
  ok: "auth.sync.requirement.ok",
} as const;
