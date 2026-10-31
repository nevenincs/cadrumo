import { useMemo, useState } from "react";
import { EntryInput } from "@/components/editors/EntryInput";
import type { EditorProps } from "@/components/editors/editorProps";
import { Calendar } from "@/components/ui/calendar";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  formatDay,
  formatDayFigures,
  readLocaleDay,
} from "@/shared/dateFormats";
import { useStrings } from "@/shell/strings";

/**
 * A calendar day: held as an ISO `YYYY-MM-DD`, or `""`, shown in the window's
 * language. It can be typed in the language's order or as ISO, or picked from
 * the calendar. Text naming no real day stays as typed for `parseIsoDate` to
 * refuse. `min` and `max` are ISO days the backend serves; they limit the
 * calendar only.
 */
export function DateEditor({
  min,
  max,
  onPicked,
  className,
  ...editor
}: EditorProps & {
  min?: string;
  max?: string;
  /** Called after a day is picked from the calendar, which also calls
   * `onChange`. A grid cell commits here. */
  onPicked?(iso: string): void;
}) {
  const t = useStrings();
  const locale = t.locale ?? "en";
  const [open, setOpen] = useState(false);
  const reading = useMemo(
    () => ({
      read: (typed: string) =>
        typed.trim() === "" ? "" : readLocaleDay(locale, typed),
      shown: (value: string) => formatDay(locale, value),
      typed: (value: string) => formatDayFigures(locale, value),
    }),
    [locale],
  );
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <div data-slot="date-editor" className="relative">
          <EntryInput
            {...editor}
            reading={reading}
            className={cn(
              "pr-[calc(var(--spacing-control-xs)+--spacing(2))]",
              className,
            )}
          />
          <PopoverTrigger asChild>
            <IconButton
              label={t("desktop.editor.date.open")}
              side="top"
              disabled={editor.disabled}
              className="absolute top-1/2 right-1 -translate-y-1/2"
            >
              <Icon name="calendar" />
            </IconButton>
          </PopoverTrigger>
        </div>
      </PopoverAnchor>
      <PopoverContent
        align="end"
        className="w-auto"
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <Calendar
          locale={locale}
          value={editor.value}
          min={min}
          max={max}
          onSelect={(iso) => {
            editor.onChange(iso);
            setOpen(false);
            onPicked?.(iso);
          }}
          labels={{
            previousMonth: t("desktop.editor.date.previous_month"),
            nextMonth: t("desktop.editor.date.next_month"),
            month: t("desktop.editor.date.month"),
            year: t("desktop.editor.date.year"),
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
