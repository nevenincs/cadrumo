import { useId, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useNavigationGuard } from "../../shell/navigation/hooks";
import { useStrings } from "../../shell/strings";
import { savedValue, seededValue, unreadDate } from "../../shell/profileInput";
import { isEmpty } from "../../shell/profileRows";
import { ProfileValueEditor } from "./ProfileValueEditor";
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

/** What an input starts as, and what leaving it so leaves of the detail. A
 * masked detail is write-only: it is never shown, so its input starts empty
 * and an empty one keeps what is saved. */
const startOf = (field: ProfileField, kind: ProfileDraft["kind"]) =>
  kind === "add_row" || field.masked
    ? ""
    : seededValue(field, field.value ?? "");

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
      draft.fields.map((field) => [field.path, startOf(field, draft.kind)]),
    ),
  );
  // Dates whose unreadable text is told: after the person leaves the field,
  // or tries to save with it.
  const [told, setTold] = useState<ReadonlySet<string>>(new Set());
  const { fields, section, kind } = draft;
  const unread = (field: ProfileField) =>
    kind === "remove_row" ? null : unreadDate(field, values[field.path] ?? "");
  // A draft that differs from what is stored is asked about before a
  // navigation takes the page down; the editor does not otherwise hold the
  // window as a dialog does. The page itself weighs a save in flight.
  const drafted =
    kind !== "remove_row" &&
    fields.some((field) => (values[field.path] ?? "") !== startOf(field, kind));
  useNavigationGuard("profile", drafted ? "dirty" : "clean", {
    discard: onClose,
  });
  const key = (field: ProfileField) =>
    field.path.slice(
      section.key.length +
        1 +
        (field.row_index === null ? 0 : field.row_index.length + 1),
    );
  const title = kind === "field" ? fields[0]!.label : section.title;
  // An empty masked input keeps the saved value: there is nothing to save,
  // and clearing it is the page's own action.
  const nothing = kind === "field" && fields[0]!.masked && !drafted;
  const submit = async () => {
    if (busy || changed || blocked || nothing) return;
    const refused = fields.filter((field) => unread(field) !== null);
    if (refused.length) {
      setTold(new Set(refused.map((field) => field.path)));
      return;
    }
    let edit: ProfileEdit;
    if (kind === "field")
      edit = {
        kind,
        path: fields[0]!.path,
        value: savedValue(fields[0]!, values[fields[0]!.path] ?? ""),
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
          : (values[field.path] ?? "") !== startOf(field, kind),
      );
      const entries = supplied
        .filter((field) => (values[field.path] ?? "") !== "")
        .map((field) => ({
          field_key: key(field),
          value: savedValue(field, values[field.path] ?? ""),
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
        modalLayer={false}
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
            fields.map((field, index) => {
              const text = unread(field);
              const refusal =
                text !== null && told.has(field.path) ? text : null;
              return (
                <Field key={field.path} data-invalid={refusal !== null}>
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
                        setValues({
                          ...values,
                          [field.path]: event.target.value,
                        })
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
                    <ProfileValueEditor
                      field={field}
                      id={`${id}-${index}`}
                      required={field.required}
                      value={values[field.path] ?? ""}
                      disabled={busy}
                      invalid={refusal !== null || undefined}
                      describedBy={
                        [
                          refusal !== null ? `${id}-${index}-refused` : null,
                          field.help?.length ? `${id}-${index}-help` : null,
                        ]
                          .filter(Boolean)
                          .join(" ") || undefined
                      }
                      onBlur={() => setTold(new Set(told).add(field.path))}
                      onChange={(value) => {
                        setTold(
                          new Set([...told].filter((p) => p !== field.path)),
                        );
                        setValues({ ...values, [field.path]: value });
                      }}
                    />
                  )}
                  <FieldError id={`${id}-${index}-refused`}>
                    {refusal !== null &&
                      t("desktop.editor.date.refused", { raw: refusal })}
                  </FieldError>
                  {field.masked && !isEmpty(field) && (
                    <FieldDescription>
                      {t("desktop.profile.aeat.saved_value")}
                    </FieldDescription>
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
              );
            })}
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
            <Button
              type="submit"
              disabled={busy || changed || blocked || nothing}
            >
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
