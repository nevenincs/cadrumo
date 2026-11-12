import { useId, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import type {
  HouseholdGroup,
  HouseholdPersonEdit,
  HouseholdRow,
} from "../../shell/profileHousehold";
import { savedValue, seededValue, unreadDate } from "../../shell/profileInput";
import { useStrings } from "../../shell/strings";
import { leafField, shownLeaves, typedFacts } from "./householdModel";
import { ProfileValueEditor } from "./ProfileValueEditor";

/** What the dialog is for: a person to state, correct or take out. */
export type PersonAction = "add" | "edit" | "remove";

/**
 * One person of a household group: every leaf the group serves and asks of
 * this person now, in the product's words, entered as the profile enters it
 * everywhere else; or the question whether to take the person out. A leaf is
 * asked while one of the answers it is served after holds, and a leaf no
 * longer asked is not stated. Adding and removing are worded by the group's
 * served controls. A refusal is shown as the product worded it and leaves what
 * was typed in place.
 */
export function HouseholdPersonDialog({
  group,
  row,
  number,
  action,
  busy,
  words,
  onSave,
  onClose,
}: {
  group: HouseholdGroup;
  row: HouseholdRow | null;
  /** The person's place in the group, for the title. */
  number: number;
  action: PersonAction;
  busy: boolean;
  /** The sentence of the last refusal, as served. */
  words: string | null;
  /** States the person, or null to take the person out. */
  onSave(person: HouseholdPersonEdit | null): void;
  onClose(): void;
}) {
  const t = useStrings();
  const id = useId();
  const [returnFocus] = useState(() => document.activeElement);
  const stored = (leaf: string) =>
    row?.facts.find((fact) => fact.leaf === leaf)?.value ?? "";
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      group.leaves.map((leaf) => [
        leaf.leaf,
        seededValue(leafField(leaf, stored(leaf.leaf)), stored(leaf.leaf)),
      ]),
    ),
  );
  // Dates whose unreadable text is told: after the person leaves the field,
  // or tries to save with it.
  const [told, setTold] = useState<ReadonlySet<string>>(new Set());
  const unread = (leaf: HouseholdGroup["leaves"][number]) =>
    unreadDate(leafField(leaf, stored(leaf.leaf)), values[leaf.leaf] ?? "");
  const asked = shownLeaves(group.leaves, values);
  const missing = asked.filter(
    (leaf) => leaf.required && (values[leaf.leaf] ?? "").trim() === "",
  );
  const title =
    action === "add"
      ? (group.add_row_action?.action_words ?? "")
      : action === "remove"
        ? (group.remove_row_action?.action_words ?? "")
        : t("desktop.profile.household.edit_person", { number });
  const submit = () => {
    if (busy) return;
    if (action === "remove") return onSave(null);
    const refused = asked.filter((leaf) => unread(leaf) !== null);
    if (refused.length || missing.length) {
      setTold(new Set(refused.map((leaf) => leaf.leaf)));
      return;
    }
    onSave(
      typedFacts(
        asked,
        Object.fromEntries(
          asked.map((leaf) => [
            leaf.leaf,
            savedValue(
              leafField(leaf, stored(leaf.leaf)),
              values[leaf.leaf] ?? "",
            ),
          ]),
        ),
      ),
    );
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
            {action === "remove" ? (
              t("desktop.profile.household.remove_help")
            ) : (
              <span className="sr-only">{group.label}</span>
            )}
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid min-w-0 gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          {action !== "remove" &&
            asked.map((leaf) => {
              const text = unread(leaf);
              const refusal =
                text !== null && told.has(leaf.leaf) ? text : null;
              const field = leafField(leaf, stored(leaf.leaf));
              const control = `${id}-${leaf.leaf}`;
              return (
                <Field
                  key={leaf.leaf}
                  data-household-leaf={leaf.leaf}
                  data-invalid={refusal !== null}
                >
                  <FieldLabel htmlFor={control}>
                    {leaf.label}
                    {leaf.required && <span aria-hidden="true"> *</span>}
                  </FieldLabel>
                  {leaf.choices.length ? (
                    <NativeSelect
                      id={control}
                      aria-required={leaf.required}
                      value={values[leaf.leaf] ?? ""}
                      disabled={busy}
                      onChange={(event) =>
                        setValues({
                          ...values,
                          [leaf.leaf]: event.target.value,
                        })
                      }
                    >
                      <option value="">{t("desktop.profile.not_set")}</option>
                      {leaf.choices.map((choice) => (
                        <option key={choice.value} value={choice.value}>
                          {choice.label}
                        </option>
                      ))}
                    </NativeSelect>
                  ) : (
                    <ProfileValueEditor
                      field={field}
                      id={control}
                      required={leaf.required}
                      value={values[leaf.leaf] ?? ""}
                      disabled={busy}
                      invalid={refusal !== null || undefined}
                      describedBy={
                        [
                          refusal !== null ? `${control}-refused` : null,
                          leaf.help ? `${control}-help` : null,
                        ]
                          .filter(Boolean)
                          .join(" ") || undefined
                      }
                      onBlur={() => setTold(new Set(told).add(leaf.leaf))}
                      onChange={(value) => {
                        setTold(
                          new Set([...told].filter((l) => l !== leaf.leaf)),
                        );
                        setValues({ ...values, [leaf.leaf]: value });
                      }}
                    />
                  )}
                  <FieldError id={`${control}-refused`}>
                    {refusal !== null &&
                      t("desktop.editor.date.refused", { raw: refusal })}
                  </FieldError>
                  {leaf.help && (
                    <details
                      id={`${control}-help`}
                      className="grid gap-1 text-sm text-muted-foreground"
                    >
                      <summary className="cursor-pointer">
                        {t("desktop.profile.field_help")}
                      </summary>
                      <p>{leaf.help}</p>
                    </details>
                  )}
                </Field>
              );
            })}
          {words && (
            <Alert
              role="alert"
              tone="danger"
              icon={<Icon name="alert" />}
              data-household-refusal=""
            >
              {words}
            </Alert>
          )}
          <DialogFooter>
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
              disabled={busy || (action !== "remove" && missing.length > 0)}
            >
              {busy
                ? t("desktop.profile.saving")
                : action === "remove"
                  ? title
                  : t("desktop.profile.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
