import type { ProfileSection } from "@/shell/userProfile";
import type {
  ModeloFormCalculationNote,
  ModeloFormCounts,
  ModeloFormElectionQuestion,
  ModeloFormExportOffer,
  ModeloFormIssueLine,
  ModeloFormResultView,
  ModeloFormText,
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
  PublicModeloFormField,
} from "@/shell/modeloContract";

// Fixtures of the Renta design prototypes, each a JSON file in ./fixtures/
// for every language. They were read for a synthetic taxpayer through the
// application's own read path: `modelo.work.form` over the published 2025
// Modelo 100 revision, once for a profile that declares activity income and
// once for a salaried one, both calculated with the two answers the
// calculation refused without (the earlier year's negative general base and
// whether direct estimation is normal), and once never calculated. Each
// envelope is cut down to a few sections, with the admitted baseline's
// permitted surface cut to the same boxes; nothing in what is kept was
// changed. Beside them:
//
// - `outline` is the served pages and sections without their boxes, and a
//   proposed outline grouping them, with per-group counts of the boxes the
//   form already marks as needing the filer. The grouping is a proposal for
//   the backend to serve, not something the window works out.
// - `credits`, `family` and `result` are the served fields of the boxes each
//   element shows, with the served profile sections, issue lines,
//   calculation notes, header result views and export offers. The stated
//   results to pay and to refund were worded by the backend's own header
//   builder for a figure no synthetic calculation reached.
// - `election` is the setup flow's imputation question in the backend
//   catalogue's words, shaped as a served question would be.

export type Language = OutputLanguage;

export type ServedSection = {
  id: string;
  heading: ModeloFormText;
  official_heading: string | null;
  counts: ModeloFormCounts;
};

export type ServedPage = {
  id: string;
  heading: ModeloFormText;
  counts: ModeloFormCounts;
  sections: ServedSection[];
};

export type Attention = { needs_you: number; failed: number };

export type ProposedGroup = {
  id: string;
  sections: { id: string; page_id: string; attention: Attention }[];
  attention: Attention;
};

export type Outline = { served: ServedPage[]; proposed: ProposedGroup[] };

export type CreditsCase = {
  fields: PublicModeloFormField[];
  issue_lines: ModeloFormIssueLine[];
  calculation_notes: ModeloFormCalculationNote[];
};

export type Credits = {
  declared_activity: CreditsCase;
  salaried: CreditsCase;
  not_calculated: CreditsCase;
};

export type Family = {
  profile: {
    profile_id: string;
    record_revision: number;
    sections: ProfileSection[];
  };
  minimums: PublicModeloFormField[];
};

export type ResultCase = {
  header: ModeloFormResultView;
  fields: PublicModeloFormField[];
};

export type Result = {
  failed: ResultCase;
  not_calculated: ResultCase;
  stated: Record<"to_pay" | "to_refund", ModeloFormResultView>;
  export_offer: ModeloFormExportOffer;
  elections_303: ModeloFormElectionQuestion[];
};

export type ElectionWords = {
  question: {
    id: string;
    prompt: string;
    help: string;
    choices: { value: string; label: string; description: string }[];
    proposed: string;
  };
  year: { id: string; prompt: string; help: string };
  accounting: { id: string; prompt: string };
};

export type Fixtures = {
  form: ModeloWorkbenchFormProjectionV1;
  outline: Outline;
  credits: Credits;
  family: Family;
  result: Result;
  election: ElectionWords;
};

const FILES = import.meta.glob<unknown>("./fixtures/*.json", {
  import: "default",
});

/** One fixture in the reader's language, read on first use. */
export async function fixture<K extends keyof Fixtures>(
  kind: K,
  language: Language,
): Promise<Fixtures[K]> {
  const load = FILES[`./fixtures/${kind}-${language}.json`];
  if (!load) throw new Error(`no ${kind} fixture in ${language}`);
  return (await load()) as Fixtures[K];
}

/** The fields of one fixture's form, in form order. */
export function formFields(
  envelope: ModeloWorkbenchFormProjectionV1,
): PublicModeloFormField[] {
  return envelope.form.form.pages.flatMap((page) =>
    page.sections.flatMap((section) =>
      section.blocks.flatMap((block) =>
        block.kind === "field" ? [block.field] : [],
      ),
    ),
  );
}

/** The envelope with only the sections named, every other part as read. */
export function withSections(
  envelope: ModeloWorkbenchFormProjectionV1,
  ids: readonly string[],
): ModeloWorkbenchFormProjectionV1 {
  const pages = envelope.form.form.pages
    .map((page) => ({
      ...page,
      sections: page.sections.filter((section) => ids.includes(section.id)),
    }))
    .filter((page) => page.sections.length > 0);
  return {
    ...envelope,
    form: { ...envelope.form, form: { ...envelope.form.form, pages } },
  };
}
