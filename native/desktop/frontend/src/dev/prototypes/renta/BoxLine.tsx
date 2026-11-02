import { BoxNumber } from "@/components/modelo/form/BoxNumber";
import { FieldFacts, FieldHelp } from "@/components/modelo/form/FieldFacts";
import { ORIGIN_LOOK, TONE_TEXT } from "@/components/modelo/form/originLook";
import {
  ATTENTION_ICON,
  ATTENTION_TONE,
} from "@/components/modelo/workspace/Marks";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type {
  ModeloFormIssueLine,
  PublicModeloFormField,
} from "@/shell/modeloContract";

// One served box as a line: its number, its label with the form's own help
// and details button, the value or the origin's words when it holds none, and
// the served notes beside it. A box without a value shows its origin's words,
// never a zero. It stays apart from the form's row because these panels draw
// boxes outside a form session, with nothing to choose or edit.

export function BoxLine({
  field,
  lines = [],
}: {
  field: PublicModeloFormField;
  lines?: readonly ModeloFormIssueLine[];
}) {
  const look = ORIGIN_LOOK[field.origin];
  return (
    <li
      data-box={field.box ?? undefined}
      data-origin={field.origin}
      className="flex flex-col gap-1 border-b border-border py-2 last:border-b-0"
    >
      <div className="flex items-center gap-3">
        <BoxNumber box={field.box} />
        <span className="flex min-w-0 flex-1 items-start gap-1 text-sm">
          <span className="min-w-0">{field.label.text}</span>
          <FieldFacts field={field} className="-my-0.5 shrink-0" />
        </span>
        <span
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 text-sm",
            TONE_TEXT[look.tone],
          )}
        >
          <Icon name={look.icon} size="xs" />
          {field.value_text ? (
            <span className="font-mono tabular-nums">{field.value_text}</span>
          ) : (
            <span>{field.origin_words}</span>
          )}
        </span>
      </div>
      <FieldHelp field={field} className="pl-13 text-xs" />
      {field.value_text && field.origin_words && (
        <div className="pl-13 text-xs text-muted-foreground">
          {field.origin_words}
        </div>
      )}
      {field.editability_words && (
        <div className="pl-13 text-xs text-muted-foreground">
          {field.editability_words}
        </div>
      )}
      {lines.map((line) => (
        <div
          key={line.technical}
          data-level={line.level}
          className="flex items-start gap-1.5 pl-13 text-xs"
        >
          <Icon
            name={ATTENTION_ICON[line.level]}
            size="xs"
            className={cn("mt-0.5", ATTENTION_TONE[line.level])}
          />
          <span>
            {line.message} {line.action}
          </span>
        </div>
      ))}
    </li>
  );
}
