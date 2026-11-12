import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type {
  ModeloFormText,
  PublicModeloFormField,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { BoxNoteList } from "./BoxNoteList";
import { notesOf } from "./boxNotes";
import { BoxNumber } from "./BoxNumber";
import { readOnlyReason } from "./entryField";
import { FieldFacts, FieldHelp } from "./FieldFacts";
import { openableSurface, useForm } from "./formContext";
import { ORIGIN_LOOK, TONE_TEXT } from "./originLook";
import {
  confirmIntent,
  editKey,
  fieldKey,
  servedPriorWithdrawal,
  type StagedEdit,
} from "./session";
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
        {staged.intent.kind === "restore_source_value" &&
        staged.intent.change === "remove"
          ? t("workspace.modelo.staged.remove")
          : staged.intent.kind === "remove_override" &&
              (staged.intent.withdraws !== undefined ||
                staged.intent.withdrawsPrior !== undefined)
            ? t("desktop.modelo.statements.withdrawn")
            : staged.intent.kind === "restore_source_value" ||
                staged.intent.kind === "remove_override"
              ? t("workspace.modelo.staged.restore")
              : t("workspace.modelo.attention.staged")}
      </span>
    );
  // A box the filer stated holds nothing is marked so, in a word and a mark
  // as well as the served words, never drawn as a value typed.
  if (field.stated_absent !== null)
    return (
      <span
        data-stated=""
        className="inline-flex flex-wrap items-center gap-1.5 text-sm text-foreground"
      >
        <Badge variant="neutral">
          <Icon name="bookmark" size="xs" />
          {t("desktop.modelo.statements.mark")}
        </Badge>
        {field.origin_words}
      </span>
    );
  // A box holding a figure the filer stated for an earlier return the
  // application does not hold says so, with the served words for where its
  // value comes from, never as a value typed or read from a stored return.
  if (field.stated_prior_value)
    return (
      <span
        data-stated-prior={field.stated_prior_value.family_id ?? ""}
        className="inline-flex flex-wrap items-center gap-1.5 text-sm text-foreground"
      >
        <Badge variant="neutral">
          <Icon name="bookmark" size="xs" />
          {t("desktop.modelo.statements.mark")}
        </Badge>
        {field.stated_prior_value.origin_words}
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

/** One box on its own line: its printed number, its words with the help the
 * read serves for it, its value and where the value comes from. */
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
  const withdrawal = staged ? null : session.withdrawal(field);
  // The served withdrawal of every figure stated for the same earlier
  // returns as this box's, which takes them all out together.
  const priorFamily = staged ? null : field.stated_prior_value?.family_id;
  const priorWithdrawal = priorFamily
    ? servedPriorWithdrawal(session.priorValues, priorFamily)
    : null;
  const [priorUnplaced, setPriorUnplaced] = useState(false);
  // The box of the statement that cannot be taken out, once a withdrawal
  // was asked for and nothing was staged.
  const [kept, setKept] = useState<PublicModeloFormField | null>(null);
  const reason = readOnlyReason(field);
  const ref = useChosenFocus<HTMLDivElement>(selected, open !== null);
  const notes = notesOf(form.notes, field);
  const surface = openableSurface(form, field);
  // A box locked to its source is corrected there, never typed into here.
  const correctAt =
    surface && field.editability === "locked_source" && !staged
      ? surface
      : null;
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
      <span role="gridcell" className="flex min-w-0 flex-col gap-0.5 py-1">
        <span className="flex items-start gap-1 text-base leading-snug">
          <span className="min-w-0">
            <Label text={field.label} />
          </span>
          <FieldFacts field={field} className="-my-0.5 shrink-0" />
        </span>
        <FieldHelp field={field} full={selected} />
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
          onOpenSurface={surface ? onOpenSurface : undefined}
        />
      </span>
      <span
        role="gridcell"
        className="flex min-w-0 flex-col items-start gap-0.5"
      >
        <OriginMark field={field} staged={staged} />
        {reason && (
          <span className="flex items-start gap-1 text-sm text-muted-foreground">
            <Icon name="lock" size="xs" className="mt-0.5 shrink-0" />
            {reason}
          </span>
        )}
        {correctAt && onOpenSurface && (
          <Button
            size="xs"
            variant="link"
            className="h-auto p-0 text-sm"
            onClick={(event) => {
              event.stopPropagation();
              onOpenSurface(correctAt);
            }}
          >
            {t(`workspace.modelo.surface.correct.${correctAt}`)}
            <Icon name="forward" size="xs" />
          </Button>
        )}
        {staged && (
          <span className="text-xs text-faint tabular-nums">
            {t("workspace.modelo.was", {
              value: staged.field.value_text ?? "—",
            })}
          </span>
        )}
        {withdrawal && (
          <Button
            size="xs"
            variant="outline"
            data-withdraw=""
            onClick={(event) => {
              event.stopPropagation();
              const outcome = session.withdraw(field);
              setKept(outcome?.kind === "refused" ? outcome.field : null);
            }}
          >
            <Icon name="erase" size="xs" />
            {t("desktop.modelo.statements.withdraw")}
          </Button>
        )}
        {priorWithdrawal && (
          <Button
            size="xs"
            variant="outline"
            data-withdraw-prior=""
            onClick={(event) => {
              event.stopPropagation();
              const outcome = session.withdrawPriorValues(priorWithdrawal);
              setKept(outcome.kind === "refused" ? outcome.field : null);
              setPriorUnplaced(
                outcome.kind === "refused" && outcome.field === null,
              );
            }}
          >
            <Icon name="erase" size="xs" />
            {priorWithdrawal.action_words}
          </Button>
        )}
        {priorUnplaced && !staged && (
          <span
            role="status"
            className="flex items-start gap-1 text-sm text-warning"
          >
            <Icon name="alert" size="xs" className="mt-0.5 shrink-0" />
            {t("desktop.modelo.statements.not_placed")}
          </span>
        )}
        {kept && !staged && (
          <span
            role="status"
            className="flex items-start gap-1 text-sm text-warning"
          >
            <Icon name="alert" size="xs" className="mt-0.5 shrink-0" />
            {t("desktop.modelo.statements.withdraw_kept", {
              box: kept.box ?? kept.label.text,
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
      {notes.length > 0 && (
        <span role="gridcell" className="col-span-3 col-start-2 pb-1">
          <BoxNoteList notes={notes} />
        </span>
      )}
    </div>
  );
}
