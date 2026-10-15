import { useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { LanguageSelect, type LanguageControl } from "./LanguageSelect";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { TERMINAL_FONT_SIZES, type Prefs } from "../shell/layout";
import { terminalFontPx } from "../shell/metrics";
import { useStrings } from "../shell/strings";

/** A choice among a few short options: a labelled segmented control. */
function Choice<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly (readonly [T, string])[];
  onChange: (value: T) => void;
}) {
  const id = useId();
  return (
    <Field>
      <FieldLabel id={id}>{label}</FieldLabel>
      <SegmentedControl
        aria-labelledby={id}
        value={value}
        onValueChange={(next) => {
          const chosen = options.find(([key]) => key === next);
          if (chosen) onChange(chosen[0]);
        }}
      >
        {options.map(([key, text]) => (
          <SegmentedControlItem key={key} value={key}>
            {text}
          </SegmentedControlItem>
        ))}
      </SegmentedControl>
    </Field>
  );
}

/** Window presentation settings and the shared output language. */
export function Settings({
  prefs,
  setPrefs,
  language,
  onReset,
  close,
}: {
  prefs: Prefs;
  setPrefs: (prefs: Prefs) => void;
  language: LanguageControl;
  onReset: () => void;
  close: () => void;
}) {
  const t = useStrings();
  const windowId = useId();
  const content = useRef<HTMLDivElement>(null);
  // Closing returns focus to where settings was opened from.
  const [returnTo] = useState(() => document.activeElement);
  return (
    <Popover open onOpenChange={(open) => !open && close()}>
      {/* It opens beside the rail's last button; the anchor marks the spot. */}
      <PopoverAnchor asChild>
        <span
          aria-hidden="true"
          className="pointer-events-none fixed bottom-2 left-rail size-0"
        />
      </PopoverAnchor>
      <PopoverContent
        ref={content}
        side="right"
        align="end"
        aria-label={t("desktop.settings.title")}
        className="settings grid w-settings grid-cols-1 gap-3"
        onOpenAutoFocus={(event) => {
          // The current appearance, not whatever control happens to be first.
          const chosen = content.current?.querySelector<HTMLElement>(
            "[role=radio][aria-checked=true]",
          );
          if (!chosen) return;
          event.preventDefault();
          chosen.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          // Unless focus has already been put somewhere: what closed
          // settings may have sent the keyboard on.
          if (
            returnTo instanceof HTMLElement &&
            document.activeElement === document.body
          )
            returnTo.focus();
        }}
        onInteractOutside={(event) => {
          // The rail's own button toggles this popover; let it.
          if ((event.target as Element | null)?.closest?.(".rail"))
            event.preventDefault();
        }}
      >
        <h2 className="font-serif text-lg">{t("desktop.settings.title")}</h2>
        <section className="grid gap-3" aria-labelledby={windowId}>
          <h3
            id={windowId}
            className="text-sm font-medium text-muted-foreground"
          >
            {t("desktop.settings.window")}
          </h3>
          <Choice
            label={t("desktop.settings.appearance")}
            value={prefs.appearance}
            options={[
              ["follow", t("desktop.settings.follow_docs")],
              ["light", t("desktop.settings.light")],
              ["dark", t("desktop.settings.dark")],
            ]}
            onChange={(appearance) => setPrefs({ ...prefs, appearance })}
          />
          <Choice
            label={t("desktop.settings.terminals")}
            value={prefs.terminals}
            options={[
              ["match", t("desktop.settings.match_appearance")],
              ["dark", t("desktop.settings.always_dark")],
            ]}
            onChange={(terminals) => setPrefs({ ...prefs, terminals })}
          />
          <Choice
            label={t("desktop.settings.docs_and_tui")}
            value={prefs.orientation}
            options={[
              ["row", t("desktop.settings.side_by_side")],
              ["column", t("desktop.settings.stacked")],
            ]}
            onChange={(orientation) => setPrefs({ ...prefs, orientation })}
          />
          <Choice
            label={t("desktop.settings.first_pane")}
            value={prefs.order}
            options={[
              ["docs", t("desktop.pane.docs")],
              ["tui", t("desktop.pane.tui")],
            ]}
            onChange={(order) => setPrefs({ ...prefs, order })}
          />
          <Choice
            label={t("desktop.settings.terminal_text")}
            value={prefs.fontSize}
            options={TERMINAL_FONT_SIZES.map(
              (step) =>
                [step, String(Math.round(terminalFontPx(step)))] as const,
            )}
            onChange={(fontSize) => setPrefs({ ...prefs, fontSize })}
          />
          <LanguageSelect {...language} />
          <Button
            variant="outline"
            size="sm"
            className="justify-self-start"
            onClick={onReset}
          >
            {t("desktop.settings.reset_layout")}
          </Button>
        </section>
      </PopoverContent>
    </Popover>
  );
}
