// The eligible usage-ratio categories the scenario host serves, as the
// backend serves them: the registry's kind token and its wording, in English
// whatever language is asked for. The host and the scenarios that name a
// category share this one table.

export type RatioEligibleFixture = {
  kind: string;
  label: string;
  notes: string;
};

const HOME_AREA_NOTES =
  "Deductible in proportion to the home's business-use floor area, where the home is only partly used for the activity (Ley 35/2006 art. 30.2.5.b rule 4).";

export const RATIO_ELIGIBLE_FIXTURE: Record<string, RatioEligibleFixture> = {
  suministros_home_office_internet: {
    kind: "usage_ratio_home_area",
    label: "Home-office internet",
    notes: HOME_AREA_NOTES,
  },
  suministros_home_office_luz: {
    kind: "usage_ratio_home_area",
    label: "Home-office electricity",
    notes: HOME_AREA_NOTES,
  },
  telefonia_fija: {
    kind: "usage_ratio_home_area",
    label: "Landline phone expense",
    notes: HOME_AREA_NOTES,
  },
};
