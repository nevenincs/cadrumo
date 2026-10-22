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
  | { kind: "complete" };
export type ProfileChange = {
  profile_id: string;
  expected_revision: number;
  expected_content_digest: string;
  edit: ProfileEdit;
};
export type UserProfilePort = {
  read(language: string): Promise<UserProfile>;
  change(change: ProfileChange): Promise<void>;
  observe(changed: () => void): Promise<() => void>;
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
  } | null>(null);
  useEffect(() => {
    control.current = null;
    if (!port || reader === null || !shown) return;
    let alive = true,
      reading = false,
      saving = false,
      again = false;
    let unsubscribe: (() => void) | undefined;
    let state = EMPTY;
    const update = (patch: Partial<State>) => {
      if (!alive) return;
      state = { ...state, ...patch };
      setStored({ identity, state });
    };
    const refresh = async () => {
      if (!alive) return;
      if (reading || saving) {
        again = true;
        return;
      }
      reading = true;
      do {
        again = false;
        update({ loading: true });
        try {
          const data = await port.read(language);
          update({ data, error: state.error === "unknown" ? "unknown" : null });
        } catch (error) {
          update({ data: null, error: failure(error) });
        }
      } while (alive && again && !saving);
      reading = false;
      update({ loading: false });
    };
    control.current = {
      refresh: async () => {
        update({ error: null, saved: false });
        await refresh();
      },
      async save(base, edit) {
        if (
          !alive ||
          saving ||
          reading ||
          state.error === "unknown" ||
          state.data?.profile_id !== base.profile_id
        )
          return false;
        if (
          base.record_revision !== state.data.record_revision ||
          base.content_digest !== state.data.content_digest
        ) {
          update({ error: "conflict" });
          return false;
        }
        saving = true;
        update({ saving: true, error: null, saved: false });
        let committed = false;
        try {
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
          saving = false;
          update({ saving: false });
          if (committed || again || state.error === "conflict") {
            const writeError = state.error;
            await refresh();
            if (committed && !state.data) update({ error: "saved_unread" });
            else if (writeError && writeError !== "saved_unread")
              update({ error: writeError });
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
  const state =
    stored.identity === identity && reader !== null && shown
      ? stored.state
      : EMPTY;
  return { ...state, refresh, save };
}

export const profileText = (value: string) =>
  value.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
export const fieldValue = (field: ProfileField) =>
  field.choices.find((choice) => choice.value === field.value)?.label ??
  field.value;
