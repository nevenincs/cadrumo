import { useEffect, useRef } from "react";
import { TERMINAL_FONT_SIZES, type Prefs } from "../shell/layout";
import { terminalFontPx } from "../shell/metrics";
import { useStrings } from "../shell/strings";

function Choice<T extends string | number>({
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
  return (
    <div className="setting">
      <span className="setting-label">{label}</span>
      <div className="segmented" role="radiogroup" aria-label={label}>
        {options.map(([key, text]) => (
          <button
            key={String(key)}
            role="radio"
            aria-checked={value === key}
            onClick={() => onChange(key)}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

// Shell preferences only: nothing here writes product Settings or reaches the
// backend. Language and storage come from the host and are not set here.
export function Settings({
  prefs,
  setPrefs,
  onReset,
  close,
}: {
  prefs: Prefs;
  setPrefs: (prefs: Prefs) => void;
  onReset: () => void;
  close: () => void;
}) {
  const t = useStrings();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ref.current?.querySelector<HTMLElement>("[aria-checked='true']")?.focus();
    const away = (event: PointerEvent) => {
      const target = event.target as HTMLElement;
      if (
        ref.current &&
        !ref.current.contains(target) &&
        !target.closest(".rail")
      )
        close();
    };
    window.addEventListener("pointerdown", away, true);
    return () => window.removeEventListener("pointerdown", away, true);
  }, [close]);

  return (
    <div
      className="settings"
      role="dialog"
      aria-label={t("desktop.settings.title")}
      ref={ref}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          close();
        }
      }}
    >
      <h2>{t("desktop.settings.title")}</h2>
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
      <button className="settings-reset" onClick={onReset}>
        {t("desktop.settings.reset_layout")}
      </button>
    </div>
  );
}
