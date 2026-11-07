import { useStrings } from "../../shell/strings";

/** The mark of a required detail or section, said in words to a reader. */
export function RequiredMark() {
  const t = useStrings();
  return (
    <>
      <span aria-hidden="true" className="font-semibold text-foreground">
        {" "}
        *
      </span>
      <span className="sr-only"> ({t("desktop.profile.required")})</span>
    </>
  );
}

/** A detail with no value. */
export function Unset() {
  const t = useStrings();
  return (
    <span className="text-faint" title={t("desktop.profile.not_set")}>
      –<span className="sr-only">{t("desktop.profile.not_set")}</span>
    </span>
  );
}
