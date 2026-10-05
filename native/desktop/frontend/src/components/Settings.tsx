import { useId, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import {
  FOLLOW_LANGUAGE,
  TERMINAL_FONT_SIZES,
  type Prefs,
} from "../shell/layout";
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

/** A language's own name for itself, as the platform spells it. */
function languageName(code: string): string {
  try {
    const name = new Intl.DisplayNames([code], { type: "language" }).of(code);
    return name ? name.charAt(0).toLocaleUpperCase(code) + name.slice(1) : code;
  } catch {
    return code;
  }
}

/**
 * The settings popover, opened from the rail. Everything in it is a
 * preference of this window, kept in the browser's storage: it writes no
 * Cadrumo setting and reaches no backend. Account uses the dedicated sign-in
 * commands.
 */
export function Settings({
  prefs,
  setPrefs,
  languages,
  onReset,
  close,
  account,
}: {
  prefs: Prefs;
  setPrefs: (prefs: Prefs) => void;
  /** The languages the documentation is bundled in. */
  languages: readonly string[];
  onReset: () => void;
  close: () => void;
  account: ReactNode;
}) {
  const t = useStrings();
  const languageId = useId();
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
        className="settings grid w-settings gap-3"
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
          if (returnTo instanceof HTMLElement) returnTo.focus();
        }}
        onInteractOutside={(event) => {
          // The rail's own button toggles this popover; let it.
          if ((event.target as Element | null)?.closest?.(".rail"))
            event.preventDefault();
        }}
      >
        <h2 className="font-serif text-lg">{t("desktop.settings.title")}</h2>
        {account}
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
            (step) => [step, String(Math.round(terminalFontPx(step)))] as const,
          )}
          onChange={(fontSize) => setPrefs({ ...prefs, fontSize })}
        />
        {languages.length > 1 && (
          <Field>
            <FieldLabel htmlFor={languageId}>
              {t("desktop.settings.language")}
            </FieldLabel>
            <NativeSelect
              id={languageId}
              controlSize="sm"
              value={
                languages.includes(prefs.language)
                  ? prefs.language
                  : FOLLOW_LANGUAGE
              }
              onChange={(event) =>
                setPrefs({ ...prefs, language: event.target.value })
              }
            >
              <option value={FOLLOW_LANGUAGE}>
                {t("desktop.settings.follow_cadrumo")}
              </option>
              {languages.map((code) => (
                <option key={code} value={code} lang={code}>
                  {languageName(code)}
                </option>
              ))}
            </NativeSelect>
          </Field>
        )}
        <Button
          variant="outline"
          size="sm"
          className="justify-self-start"
          onClick={onReset}
        >
          {t("desktop.settings.reset_layout")}
        </Button>
      </PopoverContent>
    </Popover>
  );
}
