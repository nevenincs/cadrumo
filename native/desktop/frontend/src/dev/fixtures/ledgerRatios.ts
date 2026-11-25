// The eligible usage-ratio categories the scenario host serves, as the
// backend serves them: the registry's kind token and its label and notes in
// the language asked for. The host and the scenarios that name a category
// share this one table.

export type RatioWording = { label: string; notes: string };

export type RatioEligibleFixture = {
  kind: string;
  wording: Record<"en" | "es" | "ca" | "hu", RatioWording>;
};

/** What the backend serves for a category in a language. */
export const ratioWording = (
  found: RatioEligibleFixture,
  language: string,
): RatioWording => {
  const wording = found.wording[language as keyof typeof found.wording];
  if (!wording) throw new Error(`no wording in ${language}`);
  return wording;
};

const HOME_AREA_NOTES = {
  en: "IRPF: where you use part of your habitual home for the activity, you deduct 30% of the ratio between the floor area used for the activity and the total floor area, unless you prove a higher or lower share (Ley 35/2006 art. 30.2, rule 5, letter b). IVA: the input cuota is deductible in proportion to the degree of use in the activity, without the 30% factor (Ley 37/1992 art. 95; TEAC resolution of 19 July 2023, RG 00/06654/2022).",
  es: "IRPF: si afectas parcialmente tu vivienda habitual a la actividad, deduces el 30 % de la proporción entre los metros cuadrados destinados a la actividad y la superficie total, salvo que pruebes un porcentaje superior o inferior (Ley 35/2006 art. 30.2, regla 5.ª, letra b). IVA: la cuota soportada es deducible en proporción al grado de utilización en la actividad, sin el factor del 30 % (Ley 37/1992 art. 95; Resolución del TEAC de 19 de julio de 2023, RG 00/06654/2022).",
  ca: "IRPF: si afectes parcialment el teu habitatge habitual a l'activitat, dedueixes el 30 % de la proporció entre els metres quadrats destinats a l'activitat i la superfície total, llevat que provis un percentatge superior o inferior (Ley 35/2006 art. 30.2, regla 5a, lletra b). IVA: la quota suportada és deduïble en proporció al grau d'utilització en l'activitat, sense el factor del 30 % (Ley 37/1992 art. 95; resolució del TEAC de 19 de juliol de 2023, RG 00/06654/2022).",
  hu: "IRPF: ha a lakóhelyed egy részét a tevékenységhez használod, a tevékenységre szánt alapterület és a teljes alapterület arányának 30%-át vonhatod le, kivéve, ha magasabb vagy alacsonyabb arányt igazolsz (Ley 35/2006 art. 30.2, 5. szabály, b pont). IVA: az előzetesen felszámított adó (cuota soportada) a tevékenységben való használat mértékének arányában vonható le, a 30%-os szorzó nélkül (Ley 37/1992 art. 95; a TEAC 2023. július 19-i határozata, RG 00/06654/2022).",
};

export const RATIO_ELIGIBLE_FIXTURE: Record<string, RatioEligibleFixture> = {
  suministros_home_office_internet: {
    kind: "usage_ratio_home_area",
    wording: {
      en: { label: "Home-office internet", notes: HOME_AREA_NOTES.en },
      es: { label: "Internet del despacho en casa", notes: HOME_AREA_NOTES.es },
      ca: {
        label: "Internet de l'habitatge-oficina",
        notes: HOME_AREA_NOTES.ca,
      },
      hu: {
        label: "Otthoni iroda internetköltsége",
        notes: HOME_AREA_NOTES.hu,
      },
    },
  },
  suministros_home_office_luz: {
    kind: "usage_ratio_home_area",
    wording: {
      en: { label: "Home-office electricity", notes: HOME_AREA_NOTES.en },
      es: {
        label: "Electricidad del despacho en casa",
        notes: HOME_AREA_NOTES.es,
      },
      ca: {
        label: "Electricitat de l'habitatge-oficina",
        notes: HOME_AREA_NOTES.ca,
      },
      hu: {
        label: "Otthoni iroda villamosenergia-költsége",
        notes: HOME_AREA_NOTES.hu,
      },
    },
  },
  telefonia_fija: {
    kind: "usage_ratio_home_area",
    wording: {
      en: { label: "Landline phone expense", notes: HOME_AREA_NOTES.en },
      es: { label: "Telefonía fija", notes: HOME_AREA_NOTES.es },
      ca: { label: "Despesa de telefonia fixa", notes: HOME_AREA_NOTES.ca },
      hu: { label: "Vezetékes telefon-költség", notes: HOME_AREA_NOTES.hu },
    },
  },
};
