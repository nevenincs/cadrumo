import { useId, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useStrings } from "../../shell/strings";
import { profileInput } from "../../shell/profileInput";
import type {
  ProfileEdit,
  ProfileField,
  ProfileSection,
  UserProfile,
} from "../../shell/userProfile";

export type ProfileDraft = {
  base: UserProfile;
  fields: ProfileField[];
  section: ProfileSection;
  kind: "field" | "add_row" | "update_row" | "remove_row";
};
export function ProfileEditor({
  draft,
  busy,
  changed,
  blocked,
  error,
  onRefresh,
  onSave,
  onClose,
}: {
  draft: ProfileDraft;
  busy: boolean;
  changed: boolean;
  blocked: boolean;
  error: string | null;
  onRefresh: () => void;
  onSave: (edit: ProfileEdit) => Promise<boolean>;
  onClose: () => void;
}) {
  const t = useStrings(),
    id = useId();
  const [returnFocus] = useState(() => document.activeElement);
  const [values, setValues] = useState(() =>
    Object.fromEntries(
      draft.fields.map((field) => [
        field.path,
        draft.kind === "add_row" ? "" : (field.value ?? ""),
      ]),
    ),
  );
  const { fields, section, kind } = draft;
  const key = (field: ProfileField) =>
    field.path.slice(
      section.key.length +
        1 +
        (field.row_index === null ? 0 : field.row_index.length + 1),
    );
  const title = kind === "field" ? fields[0]!.label : section.title;
  const submit = async () => {
    if (busy || changed || blocked) return;
    let edit: ProfileEdit;
    if (kind === "field")
      edit = {
        kind,
        path: fields[0]!.path,
        value: values[fields[0]!.path] ?? "",
      };
    else if (kind === "remove_row")
      edit = {
        kind,
        section_key: section.key,
        row_key: fields[0]!.row_index ?? "",
      };
    else {
      const supplied = fields.filter((field) =>
        kind === "add_row"
          ? (values[field.path] ?? "").trim() !== ""
          : (values[field.path] ?? "") !== (field.value ?? ""),
      );
      const entries = supplied
        .filter((field) => (values[field.path] ?? "") !== "")
        .map((field) => ({
          field_key: key(field),
          value: values[field.path] ?? "",
        }));
      edit =
        kind === "add_row"
          ? { kind, section_key: section.key, values: entries }
          : {
              kind,
              section_key: section.key,
              row_key: fields[0]!.row_index ?? "",
              values: entries,
              clear_fields: supplied
                .filter((field) => (values[field.path] ?? "") === "")
                .map(key),
            };
    }
    if (await onSave(edit)) onClose();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent
        closeLabel={busy ? undefined : t("desktop.profile.cancel")}
        onCloseAutoFocus={(event) => {
          if (returnFocus instanceof HTMLElement && returnFocus.isConnected) {
            event.preventDefault();
            returnFocus.focus();
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {kind === "remove_row" ? (
              t("desktop.profile.remove_help")
            ) : (
              <span className="sr-only">{title}</span>
            )}
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid min-w-0 gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {kind !== "remove_row" &&
            fields.map((field, index) => (
              <Field key={field.path}>
                <FieldLabel htmlFor={`${id}-${index}`}>
                  {field.label}
                  {field.required && <span aria-hidden="true"> *</span>}
                </FieldLabel>
                {field.choices.length ? (
                  <NativeSelect
                    id={`${id}-${index}`}
                    aria-required={field.required}
                    value={values[field.path] ?? ""}
                    disabled={busy}
                    onChange={(event) =>
                      setValues({ ...values, [field.path]: event.target.value })
                    }
                    aria-describedby={
                      field.help?.length ? `${id}-${index}-help` : undefined
                    }
                  >
                    <option value="">{t("desktop.profile.not_set")}</option>
                    {field.choices.map((choice) => (
                      <option key={choice.value} value={choice.value}>
                        {choice.label}
                      </option>
                    ))}
                  </NativeSelect>
                ) : (
                  <Input
                    {...profileInput(field)}
                    aria-required={field.required}
                    id={`${id}-${index}`}
                    value={values[field.path] ?? ""}
                    maxLength={4096}
                    disabled={busy}
                    aria-describedby={
                      field.help?.length ? `${id}-${index}-help` : undefined
                    }
                    onChange={(event) =>
                      setValues({ ...values, [field.path]: event.target.value })
                    }
                  />
                )}
                {field.help && (
                  <details
                    id={`${id}-${index}-help`}
                    className="grid gap-1 text-sm text-muted-foreground"
                  >
                    <summary className="cursor-pointer">
                      {t("desktop.profile.field_help")}
                    </summary>
                    {field.help.filter(Boolean).map((text, i) => (
                      <p key={i}>{text}</p>
                    ))}
                  </details>
                )}
              </Field>
            ))}
          {changed && (
            <Alert tone="warning">{t("desktop.profile.conflict")}</Alert>
          )}
          {error && (
            <Alert role="alert" tone="danger">
              {error}
            </Alert>
          )}
          <DialogFooter>
            {blocked && (
              <Button
                type="button"
                variant="outline"
                onClick={onRefresh}
                disabled={busy}
              >
                {t("desktop.profile.refresh")}
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={onClose}
            >
              {t("desktop.profile.cancel")}
            </Button>
            <Button type="submit" disabled={busy || changed || blocked}>
              {t(
                busy
                  ? "desktop.profile.saving"
                  : kind === "remove_row"
                    ? "desktop.profile.remove"
                    : "desktop.profile.save",
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
