import type { ReactNode } from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { PublicModeloFormField } from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { BoxNumber } from "./BoxNumber";

// What the read says about one box beyond its value, in its own words: the
// box's name, which a grid shows only as its row and column, the help the
// registry's catalogue gives it, where its value comes from and whether it
// can be changed. A box the read gives no help shows none; the window writes
// none.

/** The served help under a box's label, cut to two lines unless `full`. */
export function FieldHelp({
  field,
  full = false,
  className,
}: {
  field: PublicModeloFormField;
  full?: boolean;
  className?: string;
}) {
  if (!field.help) return null;
  return (
    <p
      data-field-help=""
      className={cn(
        "text-sm leading-snug text-muted-foreground",
        !full && "line-clamp-2",
        className,
      )}
    >
      {field.help}
    </p>
  );
}

function Fact({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-medium text-muted-foreground">{title}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

/** Everything the read serves in words about one box, as a list. Its legal
 * references and formula come as identifiers, which are never shown; the
 * box's help card says them in words. */
export function FieldFactList({ field }: { field: PublicModeloFormField }) {
  const t = useStrings();
  return (
    <div className="flex flex-col gap-3">
      <dl className="flex flex-col gap-3">
        <Fact title={t("workspace.modelo.details.what_it_means")}>
          {field.help ? (
            <span className="leading-relaxed">{field.help}</span>
          ) : (
            <span className="text-muted-foreground">
              {t("workspace.modelo.help.no_explanation")}
            </span>
          )}
        </Fact>
        {(field.origin_words || field.origin_explanation) && (
          <Fact title={t("workspace.modelo.editor.block.where_from")}>
            <span className="flex flex-col gap-0.5">
              {field.origin_words && <span>{field.origin_words}</span>}
              {field.origin_explanation && (
                <span className="text-muted-foreground">
                  {field.origin_explanation}
                </span>
              )}
            </span>
          </Fact>
        )}
      </dl>
      {field.editability_words && (
        <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
          <Icon name="lock" size="xs" className="mt-0.5 shrink-0" />
          {field.editability_words}
        </p>
      )}
    </div>
  );
}

/** A button beside a box that opens what the read serves about it. */
export function FieldFacts({
  field,
  className,
}: {
  field: PublicModeloFormField;
  className?: string;
}) {
  const t = useStrings();
  return (
    <Popover>
      <PopoverTrigger asChild>
        <IconButton
          label={t("workspace.modelo.field.details")}
          size="xs"
          className={cn("text-faint hover:text-foreground", className)}
          data-field-facts=""
        >
          <Icon name="info" />
        </IconButton>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="flex w-96 flex-col gap-3"
        aria-label={t("workspace.modelo.field.details")}
      >
        <div className="flex items-start gap-2">
          <BoxNumber box={field.box} size="sm" />
          <span className="text-base leading-snug font-medium">
            {field.label.text}
          </span>
        </div>
        <FieldFactList field={field} />
      </PopoverContent>
    </Popover>
  );
}
