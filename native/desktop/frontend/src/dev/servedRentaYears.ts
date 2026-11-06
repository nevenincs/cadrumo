import { requireServed } from "./servedFixtures";
import { modeloFixture, type ModeloShape } from "./modeloFixture";
import type { OutputLanguage } from "../shell/modeloContract/modelo";
import type {
  ModeloFormYearProjection,
  ModeloWorkbenchFormProjectionV1,
} from "../shell/modeloContract/modeloWorkForm";
import { translator } from "../shell/strings";

// The filing years the stored Modelo 100 envelopes cover, read from what the
// application served for them. Nothing here lists a year: the couple of the
// Renta's own year and of every other year the producer read are found by
// name among the stored envelopes, and each year, the edition its form was
// built from and what its form offers are whatever the form states.

/** The Renta's own year: the declaration the other scenarios open. */
const OWN_YEAR_SHAPE = "renta-married";

/** The work unit the scenario's declarations list offers. */
export const RENTA_UNIT =
  "b1c431589384a105701ba15942606b5f5667cb677d6fa62e743cd0293f9baee4";

const names = Object.keys(
  requireServed(
    "modelo/modelo-100-0A-y*-en.json",
    import.meta.glob("@fixtures/modelo/modelo-100-0A-y*-en.json"),
  ),
);

/** The shapes that read the couple of each supported year. */
export function yearShapes(): ModeloShape[] {
  const others = names.flatMap((path) => {
    const filer = /modelo-100-0A-(y\d+)-en\.json$/.exec(path)?.[1];
    return filer ? [`renta-${filer}` as ModeloShape] : [];
  });
  return [OWN_YEAR_SHAPE, ...others];
}

export type ServedYear = {
  shape: ModeloShape;
  /** The filing year its form states. */
  year: number;
  /** The registry edition its form was built from. */
  revision: string;
  /** How the registry carried an edition to its year, as the form states it. */
  projection: ModeloFormYearProjection;
  form: ModeloWorkbenchFormProjectionV1;
};

const cache = new Map<OutputLanguage, Promise<ServedYear[]>>();

/** Every supported year's form, in the order of the year it states. */
export function servedYears(locale: OutputLanguage): Promise<ServedYear[]> {
  const known = cache.get(locale);
  if (known) return known;
  const read = readYears(locale);
  cache.set(locale, read);
  return read;
}

async function readYears(locale: OutputLanguage): Promise<ServedYear[]> {
  const read = await Promise.all(
    yearShapes().map(async (shape) => {
      const port = modeloFixture({
        say: () => undefined,
        translate: translator,
        wait: async () => undefined,
        signedIn: () => true,
        shape,
      });
      const form = await port.form(RENTA_UNIT, locale);
      const revision = form.form.form.registry_revision_id;
      return {
        shape,
        year: form.form.form.filing_year,
        revision,
        projection: form.form.form.year_projection,
        form,
      };
    }),
  );
  return read.sort((left, right) => left.year - right.year);
}
