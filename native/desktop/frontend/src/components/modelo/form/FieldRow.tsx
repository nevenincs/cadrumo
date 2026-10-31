import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type {
  ModeloFormText,
  PublicModeloFormField,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import { BoxNumber } from "./BoxNumber";
import { useForm } from "./formContext";
import { ORIGIN_LOOK, TONE_TEXT } from "./originLook";
import { confirmIntent, editKey, fieldKey, type StagedEdit } from "./session";
import { ValueCell } from "./ValueCell";

/** An official label written all in capitals, put in sentence case. */
export const calm = (text: string) =>
  text.length > 3 && text === text.toUpperCase() && /[A-ZÁÉÍÓÚÑ]/.test(text)
    ? text.charAt(0) + text.slice(1).toLowerCase()
    : text;

/** A label, with a note when it is not in the reader's language. */
export function Label({ text }: { text: ModeloFormText }) {
  const t = useStrings();
  const { translated } = useForm();
  return (
    <>
      {calm(text.text)}
      {text.disclosure !== "localized" && translated && (
        <span className="ml-1.5 text-xs text-faint">
          ({t(`workspace.modelo.disclosure.${text.disclosure}`)})
        </span>
      )}
    </>
  );
}

function OriginMark({
  field,
  staged,
}: {
  field: PublicModeloFormField;
  staged: StagedEdit | undefined;
}) {
  const t = useStrings();
  if (staged)
    return (
      <span className="inline-flex items-center gap-1 text-sm text-foreground">
        <Icon name="edit" size="xs" />
        {staged.intent.kind === "restore_source_value" ||
        staged.intent.kind === "remove_override"
          ? t("workspace.modelo.staged.restore")
          : t("workspace.modelo.attention.staged")}
      </span>
    );
  if (!field.origin_words) return null;
  const look = ORIGIN_LOOK[field.origin];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-sm",
        TONE_TEXT[look.tone],
      )}
    >
      <Icon name={look.icon} size="xs" />
      {field.origin_words}
    </span>
  );
}

/** Keeps the keyboard on the chosen box while the form has it. */
export function useChosenFocus<E extends HTMLElement>(
  chosen: boolean,
  editing: boolean,
) {
  const ref = useRef<E>(null);
  useEffect(() => {
    const element = ref.current;
    if (
      chosen &&
      !editing &&
      element?.closest("[data-modelo-form]")?.contains(document.activeElement)
    )
      element.focus({ preventScroll: true });
  }, [chosen, editing]);
  return ref;
}

/** One box on its own line: its printed number, its words, its value and
 * where the value comes from. */
export function FieldRow({ field }: { field: PublicModeloFormField }) {
  const t = useStrings();
  const form = useForm();
  const { session, editing, setEditing, onDone, onOpenSurface } = form;
  const key = fieldKey(field);
  const staged = session.staged.get(editKey(field));
  const selected = session.selectedKey === key;
  const open = editing?.key === key ? editing.request : null;
  const editable = session.editable(field);
  const confirm = !staged && editable ? confirmIntent(field) : null;
  const ref = useChosenFocus<HTMLDivElement>(selected, open !== null);
  return (
    <div
      ref={ref}
      role="row"
      aria-selected={selected}
      data-key={key}
      tabIndex={selected ? 0 : -1}
      onClick={() => session.select(key)}
      onFocus={(event) => {
        if (event.target === event.currentTarget) session.select(key);
      }}
      className={cn(
        "group grid min-h-11 cursor-default grid-cols-[--spacing(10)_minmax(0,1fr)_auto_--spacing(44)] items-center gap-3 rounded-md px-2 py-1 outline-none",
        "hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring aria-selected:bg-selected",
        field.origin === "not_applicable" && "text-muted-foreground",
      )}
    >
      <span role="gridcell">
        <BoxNumber box={field.box} />
      </span>
      <span role="gridcell" className="min-w-0 text-base leading-snug">
        <Label text={field.label} />
      </span>
      <span role="gridcell" className="flex justify-end">
        <ValueCell
          field={field}
          staged={staged}
          grammar={session.grammarOf(field)}
          editable={editable}
          editing={open}
          onEditingChange={(request) =>
            setEditing(request ? key : null, request ?? undefined)
          }
          enter={session.enter}
          onDone={(how) => onDone(field, how)}
          onOpenSurface={onOpenSurface}
        />
      </span>
      <span
        role="gridcell"
        className="flex min-w-0 flex-col items-start gap-0.5"
      >
        <OriginMark field={field} staged={staged} />
        {staged && (
          <span className="text-xs text-faint tabular-nums">
            {t("workspace.modelo.was", {
              value: staged.field.value_text ?? "—",
            })}
          </span>
        )}
        {confirm && (
          <Button
            size="xs"
            variant="outline"
            onClick={(event) => {
              event.stopPropagation();
              session.stage(field, confirm);
            }}
          >
            <Icon name="tick" size="xs" />
            {t("workspace.modelo.editor.confirm")}
          </Button>
        )}
      </span>
    </div>
  );
}
