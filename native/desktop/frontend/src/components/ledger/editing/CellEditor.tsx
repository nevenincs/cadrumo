import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { TypedField } from "@/components/editors/TypedField";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import type { EditorContext } from "@/components/ui/data-grid";
import { commitKeyOf, type CommitKey } from "@/components/ui/dataGridModel";
import { Icon } from "@/components/ui/icon";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import { formatDay } from "@/shared/dateFormats";
import type { FieldSpec } from "@/shared/fieldKind";
import { formatDecimal } from "@/shared/numbers";
import type { DraftField, StageField } from "../../../shell/ledgerStage";
import {
  DIRECTIONS,
  IRPF_CATEGORIES,
  IVA_CATEGORIES,
  SPENDING_CATEGORY_FAMILIES,
} from "../../../shell/ledgerVocabulary";
import { useStrings } from "../../../shell/strings";
import {
  categoryOption,
  classificationLabel,
  directionLabel,
  irpfCategoryLabel,
  ivaCategoryLabel,
} from "../movements/movementWords";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import {
  NO_ACCOUNT,
  clearRefusal,
  parseCell,
  pointsText,
  textLimitOf,
  type CellValue,
  type EditKind,
  type EditRefusal,
} from "./editingModel";
import { choiceLabels, refusalText } from "./editingWords";

/** What a cell editor hands the grid: a value to stage, a clear, or a
 * refusal to mark in the cell. Delete hands it null, a clear. */
export type EditCommit =
  | { kind: "value"; value: CellValue }
  | { kind: "clear" }
  | { kind: "refused"; refusal: EditRefusal };

const TYPED: ReadonlySet<EditKind> = new Set([
  "text",
  "amount",
  "figure",
  "date",
  "percent",
]);
export const isTyped = (kind: EditKind) => TYPED.has(kind);

/** The field a typed cell is: money to the cent, a percentage typed in
 * points, a day, or a line of text. */
function specOf(kind: EditKind, field: StageField | DraftField): FieldSpec {
  switch (kind) {
    case "amount":
    case "figure":
      return { kind: "money" };
    case "percent":
      return { kind: "percent", unit: "points" };
    case "date":
      return { kind: "date" };
    default:
      return { kind: "text", maxLength: textLimitOf(field) };
  }
}

/** A suggestion the way the window writes it: the canonical text the grammar
 * offers, in the language's marks and day order. */
function suggestionText(
  locale: string,
  kind: EditKind,
  suggestion: string,
): string {
  if (kind === "date") return formatDay(locale, suggestion);
  if (kind === "text" || !/^-?\d+(\.\d+)?$/.test(suggestion)) return suggestion;
  const figure = formatDecimal(locale, suggestion, { grouping: false });
  return kind === "percent" ? `${figure}%` : figure;
}

/** Whether a focus or key target is in a floating part of another editor, a
 * calendar for one, which is still part of this edit. */
const inCompanion = (target: EventTarget | null) =>
  target instanceof Element &&
  target.closest("[data-slot=popover-content]:not(.ledger-cell-note)");

/**
 * A typed cell editor: the value in the product's grammar, and a refusal
 * that echoes what was typed and keeps the editor open until it is fixed or
 * cancelled. Left by the pointer, a refused value is kept as typed and
 * marked in the cell. A date takes a wider field than its column, laid over
 * the cell.
 */
export function TypedEditor({
  context,
  kind,
  field,
  value,
  stored,
}: {
  context: EditorContext;
  kind: EditKind;
  field: StageField | DraftField;
  /** The value as the editor opens with it, in canonical text. */
  value: string;
  /** Whether the cell holds a value now: an empty cell left empty is no
   * clear. */
  stored: boolean;
}) {
  const t = useStrings();
  const locale = t.locale ?? "en";
  const id = useId();
  const control = useRef<HTMLDivElement>(null);
  const anchor = useRef<HTMLSpanElement>(null);
  const [text, setText] = useState(context.initial ?? value);
  const [error, setError] = useState<EditRefusal | null>(null);
  const [lift, setLift] = useState(0);
  const done = useRef(false);
  const floating = kind === "date";
  const labels = useMemo(() => choiceLabels(t, null), [t]);
  useLayoutEffect(() => {
    if (floating) setLift(anchor.current?.offsetHeight ?? 0);
  }, [floating]);
  useEffect(() => {
    const element = control.current?.querySelector("input");
    if (!element) return;
    element.focus({ preventScroll: true });
    if (context.initial === undefined) element.select();
    else element.setSelectionRange(element.value.length, element.value.length);
  }, [context.initial, lift]);

  /** What the held text stages, or why it cannot. A percentage is typed in
   * points and the grammar reads it as such. */
  const decide = (held: string): EditCommit | "nothing" => {
    const typed = kind === "percent" ? pointsText(held) : held;
    const parsed = parseCell(kind, field, typed, labels);
    if (parsed.kind === "refused")
      return { kind: "refused", refusal: { ...parsed.refusal, raw: held } };
    if (parsed.kind === "value") return { kind: "value", value: parsed.value };
    if (!stored) return "nothing";
    const refusal = clearRefusal(field);
    return refusal ? { kind: "refused", refusal } : { kind: "clear" };
  };
  const finish = (via: CommitKey, held = text) => {
    const decided = decide(held);
    if (decided === "nothing") {
      done.current = true;
      context.cancel(via !== "pointer");
      return;
    }
    if (decided.kind === "refused" && via !== "pointer") {
      setError(decided.refusal);
      control.current?.querySelector("input")?.focus();
      return;
    }
    done.current = true;
    context.commit(decided, via);
  };
  const shown = error && {
    ...error,
    ...(error.suggestion
      ? { suggestion: suggestionText(locale, kind, error.suggestion) }
      : {}),
  };
  const message = shown ? refusalText(t, shown) : null;
  const noteId = `${id}-note`;
  const editor = (
    <div
      ref={control}
      data-slot="data-grid-editor"
      className={floating ? "w-field" : "h-full w-full"}
      onKeyDown={(event) => {
        if (!event.currentTarget.contains(event.target as Node)) return;
        const how = commitKeyOf(event);
        if (!how) return;
        event.preventDefault();
        event.stopPropagation();
        if (how === "cancel") {
          done.current = true;
          context.cancel();
          return;
        }
        finish(how);
      }}
      onBlur={(event) => {
        const next = event.relatedTarget;
        if (done.current || inCompanion(event.target) || inCompanion(next))
          return;
        if (next instanceof Node && event.currentTarget.contains(next)) return;
        if (text === value && context.initial === undefined) {
          done.current = true;
          context.cancel(false);
          return;
        }
        finish("pointer");
      }}
    >
      <TypedField
        field={specOf(kind, field)}
        value={text}
        onChange={(held) => {
          setText(held);
          setError(null);
        }}
        onPicked={(picked) => finish("pointer", picked)}
        aria-label={context.label}
        describedBy={
          [context.describedBy, message ? noteId : null]
            .filter(Boolean)
            .join(" ") || undefined
        }
        invalid={error ? true : undefined}
        controlSize="sm"
        className={cn(
          "ledger-cell-editor rounded-none border-ring",
          floating ? "h-control-sm" : "h-full",
        )}
        autoFocus
      />
    </div>
  );
  const note = message ? (
    <p id={noteId} className="flex items-start gap-1.5 text-sm text-foreground">
      <Icon name="alert" size="xs" className="mt-0.5 text-destructive" />
      {message}
      {/* The refusal names the form it would take: one press uses it,
          nothing is guessed silently. */}
      {error?.suggestion && (
        <Button
          type="button"
          variant="outline"
          size="xs"
          className="ledger-cell-suggestion shrink-0"
          onPointerDown={(event) => event.preventDefault()}
          onClick={() => {
            const parsed = parseCell(kind, field, error.suggestion!, labels);
            if (parsed.kind !== "value") return;
            done.current = true;
            context.commit({ kind: "value", value: parsed.value }, "enter");
          }}
        >
          {t("desktop.ledger.edit.refusal.use", {
            suggestion: shown?.suggestion ?? "",
          })}
        </Button>
      )}
    </p>
  ) : null;
  return (
    <Popover open>
      <PopoverAnchor asChild>
        <span ref={anchor} className="relative flex h-full w-full">
          {!floating && editor}
        </span>
      </PopoverAnchor>
      {(floating || note) && (
        <PopoverContent
          align="start"
          side="bottom"
          sideOffset={floating ? -lift : 2}
          className={cn(
            "ledger-cell-note grid gap-1.5",
            floating ? "w-auto p-0" : "w-field p-2",
          )}
          onOpenAutoFocus={(event) => event.preventDefault()}
          onCloseAutoFocus={(event) => event.preventDefault()}
          onEscapeKeyDown={(event) => event.preventDefault()}
        >
          {floating && editor}
          {note && <div className={floating ? "p-2" : undefined}>{note}</div>}
        </PopoverContent>
      )}
    </Popover>
  );
}

/** The options a choice column offers, grouped and labelled. */
function useChoices(
  kind: EditKind,
  transfer: boolean,
  accounts: readonly OwnAccountChoice[] | null,
): { options: ComboboxOption[]; label: string } {
  const t = useStrings();
  return useMemo(() => {
    switch (kind) {
      case "account":
        return {
          label: t("desktop.ledger.column.account"),
          options: [
            { value: NO_ACCOUNT, label: t("desktop.ledger.account.none") },
            ...(accounts ?? []).map((account) => ({
              value: account.id,
              label: account.label,
            })),
          ],
        };
      case "direction":
        return {
          label: t("desktop.ledger.column.direction"),
          options: DIRECTIONS.map((value) => ({
            value,
            label: directionLabel(t, value),
          })),
        };
      case "classification":
        return {
          label: t("desktop.ledger.column.classification"),
          options: (["BUSINESS", "PERSONAL", "MIXED"] as const).map(
            (value) => ({
              value,
              label: classificationLabel(t, value),
              ...(transfer && value !== "PERSONAL"
                ? {
                    disabled: true,
                    reason: t("desktop.ledger.classify.transfers_only"),
                  }
                : {}),
            }),
          ),
        };
      case "category":
        return {
          label: t("desktop.ledger.column.category"),
          options: SPENDING_CATEGORY_FAMILIES.flatMap(([family, members]) =>
            members.map((value) => categoryOption(t, family, value)),
          ),
        };
      case "iva_category":
        return {
          label: t("desktop.ledger.column.iva_category"),
          options: IVA_CATEGORIES.map((value) => ({
            value,
            label: ivaCategoryLabel(t, value),
          })),
        };
      default:
        return {
          label: t("desktop.ledger.column.irpf_category"),
          options: IRPF_CATEGORIES.map((value) => ({
            value,
            label: irpfCategoryLabel(t, value),
          })),
        };
    }
  }, [kind, transfer, accounts, t]);
}

/** A choice cell editor: a searchable list, grouped where the vocabulary
 * has families. Enter or Tab chooses; Escape leaves the value as it was. */
export function ChoiceEditor({
  context,
  kind,
  value,
  transfer = false,
  accounts = null,
}: {
  context: EditorContext;
  kind: EditKind;
  value: string | null;
  /** The movement is a transfer, which is Personal or unclassified only. */
  transfer?: boolean;
  /** The register's own accounts, for the account column. */
  accounts?: readonly OwnAccountChoice[] | null;
}) {
  const t = useStrings();
  const { options, label } = useChoices(kind, transfer, accounts);
  return (
    <Combobox
      label={label}
      value={kind === "account" && value === null ? NO_ACCOUNT : value}
      options={options}
      initialQuery={context.initial}
      emptyLabel={t("desktop.ledger.edit.no_match")}
      placeholder={t("desktop.ledger.edit.search", { column: label })}
      className="ledger-cell-choice"
      onCommit={(chosen, via) =>
        context.commit(
          { kind: "value", value: { value: chosen } } satisfies EditCommit,
          via,
        )
      }
      onCancel={(via) => context.cancel(via === "escape")}
    />
  );
}
