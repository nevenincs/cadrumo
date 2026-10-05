import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
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
  // A radio group is one tab stop; the arrow keys choose within it.
  const step = (event: KeyboardEvent<HTMLDivElement>) => {
    const delta =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? 1
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? -1
          : 0;
    if (!delta) return;
    event.preventDefault();
    const at = options.findIndex(([key]) => key === value);
    const next = options[(at + delta + options.length) % options.length];
    if (!next) return;
    onChange(next[0]);
    const buttons =
      event.currentTarget.querySelectorAll<HTMLElement>("[role=radio]");
    buttons[options.indexOf(next)]?.focus();
  };
  return (
    <div className="setting">
      <span className="setting-label">{label}</span>
      <div
        className="segmented"
        role="radiogroup"
        aria-label={label}
        onKeyDown={step}
      >
        {options.map(([key, text]) => (
          <button
            key={String(key)}
            role="radio"
            aria-checked={value === key}
            tabIndex={value === key ? 0 : -1}
            onClick={() => onChange(key)}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

// Layout preferences remain local; Account uses the dedicated sign-in commands.
export function Settings({
  prefs,
  setPrefs,
  onReset,
  close,
  account,
}: {
  prefs: Prefs;
  setPrefs: (prefs: Prefs) => void;
  onReset: () => void;
  close: () => void;
  account: ReactNode;
}) {
  const t = useStrings();
  const ref = useRef<HTMLDivElement>(null);
  // Escape returns focus to where Settings was opened from.
  const [returnTo] = useState(() => document.activeElement);

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
          if (returnTo instanceof HTMLElement) returnTo.focus();
          close();
        }
      }}
    >
      <h2>{t("desktop.settings.title")}</h2>
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
      <button className="settings-reset" onClick={onReset}>
        {t("desktop.settings.reset_layout")}
      </button>
    </div>
  );
}
