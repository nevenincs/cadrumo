import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type ProfileField = {
  path: string;
  label: string;
  value: string | null;
  masked: boolean;
  required: boolean;
  field_type: string;
  choices: { value: string; label: string }[];
  help: string[] | null;
  about: string;
  row_index: string | null;
};
export type ProfileSection = {
  key: string;
  title: string;
  summary: string;
  repeatable: boolean;
  fields: ProfileField[];
};
export type UserProfile = {
  profile_id: string;
  record_revision: number;
  content_digest: string;
  setup_state: "complete" | "incomplete";
  valid: boolean;
  sections: ProfileSection[];
  missing_required: string[];
  notices: { severity: string; message: string }[];
  pages: number;
};
export type ProfileEdit =
  | { kind: "field"; path: string; value: string }
  | {
      kind: "add_row";
      section_key: string;
      values: { field_key: string; value: string }[];
    }
  | {
      kind: "update_row";
      section_key: string;
      row_key: string;
      values: { field_key: string; value: string }[];
      clear_fields: string[];
    }
  | { kind: "remove_row"; section_key: string; row_key: string }
  | { kind: "complete" }
  /** The sign-in method, the host's only way to change `auth.provider` and
   * `auth.clave_movil_route`. `certificate` is a picker token, never a path. */
  | {
      kind: "auth_method";
      provider: string;
      clave_movil_route: string | null;
      certificate: string | null;
    };
export type ProfileChange = {
  profile_id: string;
  expected_revision: number;
  expected_content_digest: string;
  edit: ProfileEdit;
};
/** A certificate file chosen in the native dialog: a token the host
 * resolves, and the file's name; the path never reaches the window. */
export type AeatCertificate = { token: string; name: string };
/** The providers that keep a secret apart from the profile. */
export type AeatCredentialProvider = "certificate" | "clave_permanente";
export type AeatCredential = {
  profile_id: string;
  provider: AeatCredentialProvider;
  password: string;
};
/** The profile's AEAT access beyond its plain facts. */
export type AeatAccessPort = {
  /** Null when the person closes the dialog without choosing; rejects with
   * `{ code: "invalid" }` for a file that is not a PKCS#12 certificate. */
  pickCertificate(): Promise<AeatCertificate | null>;
  /** Saves the passphrase or password apart from the profile. A rejection
   * is read by `credentialFailure`; nothing is retried after one that
   * leaves the outcome unknown. */
  saveCredential(credential: AeatCredential): Promise<void>;
};
export type UserProfilePort = {
  read(language: string): Promise<UserProfile>;
  change(change: ProfileChange): Promise<void>;
  observe(changed: () => void): Promise<() => void>;
  readonly aeat: AeatAccessPort;
};
export type ProfileFailure =
  | "unavailable"
  | "not_signed_in"
  | "refused"
  | "conflict"
  | "unknown"
  | "saved_unread";
function failure(error: unknown): ProfileFailure {
  const code = (error as { code?: string } | null)?.code;
  return code === "not_signed_in" ||
    code === "refused" ||
    code === "conflict" ||
    code === "unknown" ||
    code === "saved_unread"
    ? code
    : "unavailable";
}
/** Codes after which a credential save is known not to have happened. */
const SETTLED_CREDENTIAL_FAILURES = [
  "invalid",
  "refused",
  "conflict",
  "not_signed_in",
];

/** How a rejected credential save is read. The host rejects with
 * `{ code }`: after a settled code nothing happened; `unavailable` is the
 * runtime being out of reach; any other code, `unknown` and `saved_unread`
 * among them, leaves the outcome unconfirmed. */
export function credentialFailure(
  error: unknown,
): "refused" | "unavailable" | "unconfirmed" {
  const code = (error as { code?: unknown } | null)?.code;
  if (typeof code !== "string") return "unconfirmed";
  if (SETTLED_CREDENTIAL_FAILURES.includes(code)) return "refused";
  return code === "unavailable" ? "unavailable" : "unconfirmed";
}

type State = {
  data: UserProfile | null;
  loading: boolean;
  saving: boolean;
  error: ProfileFailure | null;
  saved: boolean;
};
const EMPTY: State = {
  data: null,
  loading: true,
  saving: false,
  error: null,
  saved: false,
};

/** One mounted profile reader. Pushes coalesce behind a single read; stale
 * responses are dropped and drafts keep the revision they were opened on. */
export function useUserProfile(
  port: UserProfilePort | undefined,
  reader: string | null,
  language: string,
  shown: boolean,
) {
  const identity = useMemo(
    () => ({ port, reader, language, shown }),
    [port, reader, language, shown],
  );
  const [stored, setStored] = useState({ identity, state: EMPTY });
  const control = useRef<{
    refresh(): Promise<void>;
    save(base: UserProfile, edit: ProfileEdit): Promise<boolean>;
    latest(): UserProfile | null;
  } | null>(null);
  useEffect(() => {
    control.current = null;
    if (!port || reader === null || !shown) return;
    let alive = true,
      reading = false,
      saving = false,
      again = false;
    let unsubscribe: (() => void) | undefined;
    let readFinished = Promise.resolve();
    let state = EMPTY;
    const update = (patch: Partial<State>) => {
      if (!alive) return;
      state = { ...state, ...patch };
      setStored({ identity, state });
    };
    const refresh = async (saveReadback = false) => {
      if (!alive) return;
      if (reading || (saving && !saveReadback)) {
        again = true;
        return;
      }
      reading = true;
      let finishRead!: () => void;
      readFinished = new Promise<void>((resolve) => {
        finishRead = resolve;
      });
      do {
        again = false;
        update({ loading: true });
        try {
          const data = await port.read(language);
          update({ data, error: state.error === "unknown" ? "unknown" : null });
        } catch (error) {
          const code = failure(error);
          update({
            data: code === "not_signed_in" ? null : state.data,
            error: state.error === "unknown" ? "unknown" : code,
          });
        }
      } while (alive && again && (!saving || saveReadback));
      reading = false;
      update({ loading: false });
      finishRead();
    };
    control.current = {
      refresh: async () => {
        update({ error: null, saved: false });
        await refresh();
      },
      latest: () => state.data,
      async save(base, edit) {
        if (
          !alive ||
          saving ||
          state.error === "unknown" ||
          state.data?.profile_id !== base.profile_id
        )
          return false;
        saving = true;
        update({ saving: true, error: null, saved: false });
        let committed = false;
        try {
          // Reserve the save before waiting, so observation pushes cannot
          // repeatedly overtake the edit. The draft retains its original CAS.
          await readFinished;
          if (!alive) return false;
          if (state.data?.profile_id !== base.profile_id) {
            update({ error: "not_signed_in" });
            return false;
          }
          if (
            base.record_revision !== state.data.record_revision ||
            base.content_digest !== state.data.content_digest
          ) {
            update({ error: "conflict" });
            return false;
          }
          await port.change({
            profile_id: base.profile_id,
            expected_revision: base.record_revision,
            expected_content_digest: base.content_digest,
            edit,
          });
          committed = true;
          update({ saved: true });
        } catch (error) {
          const code = failure(error);
          committed = code === "saved_unread";
          update({ error: code, saved: committed });
        } finally {
          try {
            if (committed || again || state.error === "conflict") {
              const writeError = state.error;
              // Keep the save reserved, including its UI, until readback and
              // coalesced observations settle. Only this read may bypass it.
              await refresh(true);
              if (committed && (!state.data || state.error === "unavailable"))
                update({ error: "saved_unread" });
              else if (writeError && writeError !== "saved_unread")
                update({ error: writeError });
            }
          } finally {
            saving = false;
            update({ saving: false });
          }
        }
        return alive && committed;
      },
    };
    void port
      .observe(() => {
        void refresh();
      })
      .then((stop) => {
        if (!alive) {
          stop();
          return;
        }
        unsubscribe = stop;
        void refresh();
      })
      .catch(() => update({ loading: false, error: "unavailable" }));
    return () => {
      alive = false;
      unsubscribe?.();
      control.current = null;
    };
  }, [identity, port, reader, language, shown]);
  const refresh = useCallback(() => {
    void control.current?.refresh();
  }, []);
  const save = useCallback(
    (base: UserProfile, edit: ProfileEdit) =>
      control.current?.save(base, edit) ?? Promise.resolve(false),
    [],
  );
  /** The profile as last read, which a render may not have drawn yet: the
   * base of the next edit in a sequence of saves. */
  const latest = useCallback(() => control.current?.latest() ?? null, []);
  const state =
    stored.identity === identity && reader !== null && shown
      ? stored.state
      : EMPTY;
  return { ...state, refresh, save, latest };
}

export const profileText = (value: string) =>
  value.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
export const fieldValue = (field: ProfileField) =>
  field.choices.find((choice) => choice.value === field.value)?.label ??
  field.value;
