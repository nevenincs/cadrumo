import type { BorradorPort } from "../../../shell/borrador";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloFormAddressV1 } from "../../../shell/modeloContract/modeloEditWork";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import type { OpenableSurface } from "../details/Details";
import type { FormSession } from "../form/session";
import { BorradorComparison } from "./BorradorComparison";
import { useBorradorComparison } from "./borradorComparisonRead";
import { Heading } from "./CheckView";
import { TaxationComparison } from "./TaxationComparison";
import { useTaxationComparison } from "./taxationComparisonRead";

// The comparisons a declaration offers. Each is drawn only where the form says
// the declaration asks for it, and the window offers no comparison of its
// own: the taxation comparison is the application's, worked out on the values
// the declaration holds, and the AEAT draft is read from the profile's drafts.
// Neither changes the declaration; the draft's printed values are
// observations beside the calculation and never reach the form.

function Taxation({
  envelope,
  port,
  session,
  locale,
  onGo,
  onOpenSurface,
  canOpenSurface,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  session: FormSession;
  locale: string;
  onGo(address: ModeloFormAddressV1): void;
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface(surface: OpenableSurface): boolean;
}) {
  const { read, ask } = useTaxationComparison({
    port,
    workUnitId: envelope.work_unit_id,
    calculation: envelope.calculation_revision_id,
  });
  return (
    <TaxationComparison
      read={read}
      onAsk={ask}
      locale={locale}
      fieldAt={session.fieldAt}
      onGo={onGo}
      onOpenProfile={
        canOpenSurface("profile") ? () => onOpenSurface("profile") : null
      }
    />
  );
}

function Borrador({
  envelope,
  borrador,
  language,
  locale,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  borrador: BorradorPort;
  language: OutputLanguage;
  locale: string;
}) {
  const { read, ask } = useBorradorComparison({
    port: borrador,
    profile: envelope.profile_id,
    year: envelope.form.form.filing_year,
    language,
    calculation: envelope.calculation_revision_id,
  });
  return <BorradorComparison read={read} onAsk={ask} locale={locale} />;
}

/** Whether a declaration offers any comparison in this window: the form says
 * it asks for one, and the borrador one needs the host's drafts. */
export function offersComparison(
  envelope: ModeloWorkbenchFormProjectionV1,
  borrador: BorradorPort | undefined,
): boolean {
  const form = envelope.form.form;
  return form.compares_taxation || (form.compares_borrador && !!borrador);
}

/**
 * The comparison view of one declaration: the comparison of joint and
 * individual filing, and the AEAT draft against the calculation, each only
 * where the form says the declaration asks for it.
 */
export function ComparisonView({
  envelope,
  port,
  borrador,
  session,
  language,
  locale,
  onGo,
  onOpenSurface,
  canOpenSurface,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  /** The profile's drafts, or none where this window cannot read them. */
  borrador: BorradorPort | undefined;
  session: FormSession;
  language: OutputLanguage;
  locale: string;
  onGo(address: ModeloFormAddressV1): void;
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface(surface: OpenableSurface): boolean;
}) {
  const t = useStrings();
  const form = envelope.form.form;
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading
        title={t("desktop.modelo.compare.title")}
        lead={t("desktop.modelo.compare.lead")}
      />
      {form.compares_taxation && (
        <Taxation
          envelope={envelope}
          port={port}
          session={session}
          locale={locale}
          onGo={onGo}
          onOpenSurface={onOpenSurface}
          canOpenSurface={canOpenSurface}
        />
      )}
      {form.compares_borrador && borrador && (
        <Borrador
          envelope={envelope}
          borrador={borrador}
          language={language}
          locale={locale}
        />
      )}
    </div>
  );
}
