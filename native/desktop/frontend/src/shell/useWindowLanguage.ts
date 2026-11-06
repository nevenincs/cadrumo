import { useMemo } from "react";
import type { Host } from "./host";
import type { SignInController } from "./signIn";
import {
  OUTPUT_LANGUAGES,
  SOURCE_LOCALE,
  translator,
  type Translate,
} from "./strings";
import type { useDesktopEnvironment } from "./useDesktopEnvironment";
import { useLanguage } from "./useLanguage";

/** The window's output language: the one the environment states until the
 * signed-in profile has its own, the control that changes it, and the
 * translator every surface words itself with. */
export function useWindowLanguage(
  host: Host,
  environment: ReturnType<typeof useDesktopEnvironment>,
  account: SignInController,
) {
  const language = useLanguage(
    host,
    environment.state === "ready"
      ? environment.value.outputLanguage
      : SOURCE_LOCALE,
    { phase: account.phase, profile: account.status?.active_profile ?? null },
  );
  const locale = language.locale;
  const languages = OUTPUT_LANGUAGES;
  const languageControl = {
    value: locale,
    languages,
    pending: language.pending,
    failed: language.failed,
    onChange: (code: string) => void language.change(code),
  };
  const t: Translate = useMemo(() => translator(locale), [locale]);
  return { language, locale, languages, languageControl, t };
}
