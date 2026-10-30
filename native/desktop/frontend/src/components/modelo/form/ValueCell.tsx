import {
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { commitKeyOf, type CommitKey } from "@/components/ui/dataGridModel";
import { Icon } from "@/components/ui/icon";
import { inputVariants } from "@/components/ui/input";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import type {
  ModeloEditWritableScalarSurfaceEntryV1,
  PublicModeloFormField,
  SourceSurface,
} from "../../../shell/modeloContract";
import { factsGap } from "../../../shell/compose";
import { useStrings, type Translate } from "../../../shell/strings";
import { ORIGIN_LOOK, TONE_TEXT } from "./originLook";
import type { EntryOutcome, FormSession, StagedEdit } from "./session";
import { stagedText } from "./stagedWords";

// One box's value and the one way to change it. The value is the text the
// application wrote for it; a box with none shows only a dash, and its
// origin's words say why. Typing follows the data grid: Enter, F2 or a typed
// character opens the editor, Enter, Tab and Shift+Tab keep the entry and
// move on, Escape leaves the box as it was. What was typed is read by the
// application before it is staged; a value fed by a source asks first
// whether to correct it at its source instead.

/** A request to open a box's editor, holding the character that opened it
 * when one did. */
export type EditRequest = { seed?: string };

/** A casilla's data type, as the registry declares it. */
type CasillaDataType = ModeloEditWritableScalarSurfaceEntryV1["data_type"];
/** The kinds of entry the editor's placeholder names. */
type EntryKind =
  | "boolean"
  | "date"
  | "decimal"
  | "integer"
  | "money"
  | "ratio"
  | "text"
  | "year";

/** How each data type is typed: the placeholder it shows and whether it
 * reads as a figure. Keyed by the generated type, so a type the registry
 * gains does not compile until it is placed here. */
const TYPING: Record<CasillaDataType, { entry: EntryKind; figure: boolean }> = {
  decimal: { entry: "decimal", figure: true },
  money: { entry: "money", figure: true },
  integer: { entry: "integer", figure: true },
  ratio: { entry: "ratio", figure: true },
  year: { entry: "year", figure: false },
  boolean: { entry: "boolean", figure: false },
  date: { entry: "date", figure: false },
  text: { entry: "text", figure: false },
  nif: { entry: "text", figure: false },
  period_code: { entry: "text", figure: false },
  country_code: { entry: "text", figure: false },
  iban: { entry: "text", figure: false },
  name: { entry: "text", figure: false },
  nif_iva: { entry: "text", figure: false },
  ccaa_code: { entry: "text", figure: false },
  province_code: { entry: "text", figure: false },
  postal_code: { entry: "text", figure: false },
  municipality_code: { entry: "text", figure: false },
  bic: { entry: "text", figure: false },
};
const typing = (field: PublicModeloFormField) =>
  Object.hasOwn(TYPING, field.data_type)
    ? TYPING[field.data_type as CasillaDataType]
    : TYPING.text;

const placeholder = (t: Translate, field: PublicModeloFormField) =>
  t(`workspace.modelo.editor.placeholder.${typing(field).entry}`);

/** The surfaces a value fed by a source can be corrected at. */
const CORRECTABLE: ReadonlySet<SourceSurface> = new Set([
  "ledger",
  "withholding",
  "profile",
  "declarations",
]);

/** The words a box's value cell shows: the staged edit, the value, or a
 * dash where it holds none. */
export function cellText(
  t: Translate,
  field: PublicModeloFormField,
  staged: StagedEdit | undefined,
): string {
  if (staged) return stagedText(t, staged);
  return field.value_text ?? "—";
}

function Editor({
  field,
  initial,
  seed,
  label,
  enter,
  onClose,
}: {
  field: PublicModeloFormField;
  initial: string;
  seed: string | undefined;
  label: string;
  enter: FormSession["enter"];
  onClose: (how: CommitKey | "cancel") => void;
}) {
  const t = useStrings();
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState(seed ?? initial);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const settled = useRef(false);
  const describedBy = useId();
  useLayoutEffect(() => {
    const element = input.current;
    if (!element) return;
    element.focus({ preventScroll: true });
    if (seed === undefined) element.select();
    else element.setSelectionRange(element.value.length, element.value.length);
  }, [seed]);

  const said = (outcome: EntryOutcome): string | null => {
    if (outcome.kind === "refused")
      return (
        outcome.entry.refusal_words ?? t("workspace.modelo.editor.unreadable")
      );
    if (outcome.kind === "failed")
      return outcome.words ?? t("workspace.modelo.editor.not_checked");
    return null;
  };

  const keep = async (how: CommitKey) => {
    if (pending) return;
    if (text.trim() === initial.trim()) {
      settled.current = true;
      onClose(how === "pointer" ? "cancel" : how);
      return;
    }
    setPending(true);
    setMessage(null);
    const outcome = await enter(field, text);
    setPending(false);
    const refusal = said(outcome);
    if (refusal) {
      setMessage(refusal);
      input.current?.focus({ preventScroll: true });
      return;
    }
    settled.current = true;
    onClose(how);
  };

  return (
    <span className="flex flex-col items-end gap-1">
      <span className="flex items-center gap-1.5">
        {pending && (
          <Spinner
            className="size-icon-xs text-muted-foreground"
            label={t("workspace.modelo.editor.reading")}
          />
        )}
        <input
          ref={input}
          data-slot="modelo-value-editor"
          aria-label={label}
          aria-describedby={message ? describedBy : undefined}
          aria-invalid={message ? true : undefined}
          aria-busy={pending || undefined}
          readOnly={pending}
          value={text}
          placeholder={placeholder(t, field)}
          inputMode={typing(field).figure ? "decimal" : "text"}
          onChange={(event) => {
            setText(event.target.value);
            setMessage(null);
          }}
          onKeyDown={(event) => {
            event.stopPropagation();
            const how = commitKeyOf(event);
            if (!how) return;
            event.preventDefault();
            if (how === "cancel") {
              settled.current = true;
              onClose("cancel");
            } else void keep(how);
          }}
          onBlur={() => {
            if (settled.current || pending || message) return;
            void keep("pointer");
          }}
          className={cn(
            inputVariants({ controlSize: "sm" }),
            "w-40",
            typing(field).figure && "text-right tabular-nums",
            message && "border-destructive",
          )}
        />
      </span>
      {message && (
        <span
          id={describedBy}
          role="alert"
          className="max-w-64 text-right text-sm text-destructive"
        >
          {message}
        </span>
      )}
    </span>
  );
}

/** Asked before a value from a source is replaced: correcting it where it
 * comes from is offered first, and replacing it here is said plainly. */
function ReplaceSource({
  field,
  children,
  open,
  onOpenChange,
  onReplace,
  onOpenSurface,
}: {
  field: PublicModeloFormField;
  children: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onReplace: () => void;
  onOpenSurface?: (surface: SourceSurface) => void;
}) {
  const t = useStrings();
  const surface = field.bindings[0]?.policy.surface;
  const correctable =
    surface !== undefined && CORRECTABLE.has(surface) && onOpenSurface;
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverAnchor asChild>{children}</PopoverAnchor>
      <PopoverContent align="end" className="flex w-80 flex-col gap-3">
        <p className="text-base">
          <span className="font-medium tabular-nums">
            {field.value_text ?? "—"}
          </span>
          {field.origin_words && (
            <>
              {factsGap(t)}
              {field.origin_words}
            </>
          )}
        </p>
        <p className="text-sm text-muted-foreground">
          {t("workspace.modelo.legend.meaning.origin.overrides_source")}
        </p>
        <div className="flex flex-col gap-2">
          {correctable && (
            <Button
              variant="primary"
              size="sm"
              className="justify-start"
              onClick={() => {
                onOpenChange(false);
                onOpenSurface(surface);
              }}
            >
              <Icon name="forward" size="xs" />
              {t(`workspace.modelo.surface.correct.${surface}`)}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="justify-start"
            onClick={onReplace}
            autoFocus={!correctable}
          >
            <Icon name="swap" size="xs" />
            {t("workspace.modelo.editor.replace_here")}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export type ValueCellProps = {
  field: PublicModeloFormField;
  staged: StagedEdit | undefined;
  /** Whether this box's value can be typed in here. */
  editable: boolean;
  editing: EditRequest | null;
  onEditingChange: (request: EditRequest | null) => void;
  enter: FormSession["enter"];
  /** The editor closed: kept by `how`, or left as it was. */
  onDone: (how: CommitKey | "cancel") => void;
  onOpenSurface?: (surface: SourceSurface) => void;
  align?: "row" | "grid";
};

export function ValueCell({
  field,
  staged,
  editable,
  editing,
  onEditingChange,
  enter,
  onDone,
  onOpenSurface,
  align = "row",
}: ValueCellProps) {
  const t = useStrings();
  const [replacing, setReplacing] = useState(false);
  const fromSource = field.editability === "overridable_source" && !staged;
  const label = t("workspace.modelo.editor.new_value_for_box", {
    box: field.box ?? "",
  });
  if (editing && editable && (!fromSource || replacing))
    return (
      <Editor
        field={field}
        initial={staged?.entry ?? ""}
        seed={editing.seed}
        label={label}
        enter={enter}
        onClose={(how) => {
          setReplacing(false);
          onEditingChange(null);
          onDone(how);
        }}
      />
    );
  const text = cellText(t, field, staged);
  const look = ORIGIN_LOOK[field.origin];
  const face = (
    <button
      type="button"
      tabIndex={-1}
      disabled={!editable}
      aria-label={
        field.value_text === null && !staged && field.origin_words
          ? `${field.box ?? ""} ${field.origin_words}`.trim()
          : undefined
      }
      onClick={(event) => {
        event.stopPropagation();
        onEditingChange({});
      }}
      className={cn(
        "flex h-control-sm min-w-32 items-center justify-end rounded-md px-2 text-base tabular-nums disabled:cursor-default",
        align === "grid" && "w-full",
        editable &&
          "cursor-text border border-input bg-card hover:border-border-strong",
        field.standing === "needs_you" && !staged && "border-warning",
        staged && "border-foreground bg-selected text-foreground",
        !staged &&
          (field.value_text === null
            ? TONE_TEXT[look.tone === "danger" ? "danger" : "quiet"]
            : "text-foreground"),
      )}
    >
      {text}
    </button>
  );
  if (!fromSource || !editable) return face;
  return (
    <ReplaceSource
      field={field}
      open={editing !== null && !replacing}
      onOpenChange={(open) => !open && onEditingChange(null)}
      onReplace={() => setReplacing(true)}
      onOpenSurface={onOpenSurface}
    >
      {face}
    </ReplaceSource>
  );
}
