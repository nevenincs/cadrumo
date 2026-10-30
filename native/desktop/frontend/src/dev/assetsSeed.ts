// The scenario register of the Assets tab: synthetic elements whose plans,
// lists and histories are fixed data, stated as the backend states them. Every
// figure follows the linear schedule over the registry's own amortization table
// (a charge for a span is the annual charge by days, rounded on the tax year's
// cumulative curve, and never more than the basis left), every coefficient lies
// in its table class's corridor and every class is one the table lists for the
// kind. Years before the first edition the product supports carry no edition and
// no figure. The tables below are the registry's normal modality.

import type { JsonObject } from "@/shell/ledger";
import type {
  AssetListRow,
  DisposalCalculation,
  DisposalFinding,
  ElectionLimits,
  PlanRow,
  TableGroup,
  TimelineEvent,
} from "@/shell/ledgerSetup";

export type SeedElement = {
  id: string;
  list: AssetListRow;
  rows: PlanRow[];
  limits: ElectionLimits;
  events: TimelineEvent[];
  /** The revisions the register holds of the element, as the backend serves them. */
  revisions: { revision: JsonObject; revision_id: string }[];
  /** The annual charge, to the cent; the schedule spreads it by days. */
  annual: string;
  /** The charge for each span the plan offers to claim, by `from/until`. */
  forecasts: Record<string, string>;
  /** The figures of a sale on the scenario's date with no amount stated,
   * worked out by the registry's own baja calculation; null where the element
   * cannot be worked out. A stated amount moves only the result. */
  disposal:
    | (Omit<
        DisposalCalculation,
        | "disposal_date"
        | "reason"
        | "transmission_value"
        | "transmission_costs"
        | "result"
        | "route_changed_by_later_affectation"
        | "findings"
      > & { findings: Omit<DisposalFinding, "label_key">[] })
    | null;
};

export const SEED_ELEMENTS: readonly SeedElement[] = [
  {
    rows: [
      {
        tax_year: 2023,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "2169.86",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "2169.86",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2023",
          authored_filing_year: 2023,
          projected: false,
        },
        service_days: 275,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:furgoneta:2023:a",
            amount: {
              decimal: "2169.86",
            },
            covered_from: "2023-04-01",
            covered_until: "2024-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "560cd54b111d30e2ced2bbefb05643bf173c17734e430c33efa12beb75d8db32",
          },
        ],
        minimum_through: {
          decimal: "1291.59",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2024,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "2880.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "2880.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2024",
          authored_filing_year: 2024,
          projected: false,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [
          {
            claim_id: "claim:furgoneta:2024:a",
            amount: {
              decimal: "2880.00",
            },
            covered_from: "2024-01-01",
            covered_until: "2025-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "560cd54b111d30e2ced2bbefb05643bf173c17734e430c33efa12beb75d8db32",
          },
        ],
        minimum_through: {
          decimal: "3005.87",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2025,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "2880.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "2880.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:furgoneta:2025:a",
            amount: {
              decimal: "2880.00",
            },
            covered_from: "2025-01-01",
            covered_until: "2026-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "560cd54b111d30e2ced2bbefb05643bf173c17734e430c33efa12beb75d8db32",
          },
        ],
        minimum_through: {
          decimal: "4720.16",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2026,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "2880.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "1428.16",
        },
        claim_state: "partial",
        claimable_intervals: [
          {
            covered_from: "2026-07-01",
            covered_until: "2027-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:furgoneta:2026:a",
            amount: {
              decimal: "1428.16",
            },
            covered_from: "2026-01-01",
            covered_until: "2026-07-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "560cd54b111d30e2ced2bbefb05643bf173c17734e430c33efa12beb75d8db32",
          },
        ],
        minimum_through: {
          decimal: "6434.44",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2027,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "2880.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2027-01-01",
            covered_until: "2028-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "8148.73",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2028,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "2880.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2028-01-01",
            covered_until: "2029-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [],
        minimum_through: {
          decimal: "9863.01",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2029,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "2880.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2029-01-01",
            covered_until: "2030-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "11577.30",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2030,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "2880.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2030-01-01",
            covered_until: "2031-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "13291.59",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2031,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "1670.14",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2031-01-01",
            covered_until: "2032-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "15005.87",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2032,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: null,
        absence: "basis_exhausted",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [],
        minimum_through: {
          decimal: "16720.16",
        },
        minimum_complete: true,
      },
    ],
    limits: {
      class_key: "transporte-externo",
      maximum_coefficient: {
        decimal: "0.16",
      },
      minimum_coefficient: {
        decimal: "0.07142857142857142857142857143",
      },
      maximum_period_years: {
        decimal: "14",
      },
      maximum_period_ends_on: "2037-04-01",
      not_table_bound: null,
      unavailable_reason_key: null,
      class_label: "Elementos de transporte externo",
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Real Decreto 439/2007, art. 22",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a22",
        },
        {
          text: "Ley 35/2006, art. 29",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a29",
        },
        {
          text: "Real Decreto 439/2007, art. 30",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a30",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "2880.00",
    forecasts: {
      "2026-07-01/2027-01-01": "1451.84",
      "2027-01-01/2028-01-01": "2880.00",
      "2028-01-01/2029-01-01": "2880.00",
      "2029-01-01/2030-01-01": "2880.00",
      "2030-01-01/2031-01-01": "2880.00",
      "2031-01-01/2032-01-01": "2880.00",
    },
    list: {
      asset_id: "furgoneta",
      name: "Furgoneta de reparto",
      serial_number: "FR-2023-0114",
      asset_kind: "material",
      state: "in_service",
      in_service_date: "2023-04-01",
      method: "linear",
      revision_number: 1,
      basis: {
        decimal: "24000.00",
      },
      accumulated: {
        decimal: "9358.02",
      },
      pending: {
        decimal: "14641.98",
      },
      findings: {
        missing: 1,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2023, 2024, 2025, 2026],
      projected_years: [2027, 2028, 2029, 2030, 2031, 2032],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2023-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "furgoneta",
        record_id:
          "560cd54b111d30e2ced2bbefb05643bf173c17734e430c33efa12beb75d8db32",
        effect_date: "2023-04-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2023-04-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "24000.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "transporte-externo",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.12",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "furgoneta",
        record_id: "descriptor:furgoneta:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Furgoneta de reparto",
            before_key: null,
            after_key: null,
          },
          {
            field: "serial_number",
            before: null,
            after: "FR-2023-0114",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
      {
        sequence: 3,
        recorded_at: "2023-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "furgoneta",
        record_id: "claim:furgoneta:2023:a",
        effect_date: "2023-04-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "2169.86",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 4,
        recorded_at: "2024-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "furgoneta",
        record_id: "claim:furgoneta:2024:a",
        effect_date: "2024-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "2880.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 5,
        recorded_at: "2025-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "furgoneta",
        record_id: "claim:furgoneta:2025:a",
        effect_date: "2025-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "2880.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 6,
        recorded_at: "2026-07-02T08:15:00Z",
        kind: "claim",
        asset_id: "furgoneta",
        record_id: "claim:furgoneta:2026:a",
        effect_date: "2026-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "1428.16",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    ],
    id: "furgoneta",
    disposal: {
      acquisition_value: {
        decimal: "24000.00",
      },
      deducted: {
        decimal: "9358.02",
      },
      minimum: {
        decimal: "6434.46",
      },
      reduction: {
        decimal: "9358.02",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "14641.98",
      },
      years: [
        {
          tax_year: 2023,
          claims: {
            decimal: "2169.86",
          },
          deducted_through: {
            decimal: "2169.86",
          },
          minimum_through: {
            decimal: "1291.59",
          },
          reduction_through: {
            decimal: "2169.86",
          },
        },
        {
          tax_year: 2024,
          claims: {
            decimal: "2880.00",
          },
          deducted_through: {
            decimal: "5049.86",
          },
          minimum_through: {
            decimal: "3005.88",
          },
          reduction_through: {
            decimal: "5049.86",
          },
        },
        {
          tax_year: 2025,
          claims: {
            decimal: "2880.00",
          },
          deducted_through: {
            decimal: "7929.86",
          },
          minimum_through: {
            decimal: "4720.17",
          },
          reduction_through: {
            decimal: "7929.86",
          },
        },
        {
          tax_year: 2026,
          claims: {
            decimal: "1428.16",
          },
          deducted_through: {
            decimal: "9358.02",
          },
          minimum_through: {
            decimal: "6434.46",
          },
          reduction_through: {
            decimal: "9358.02",
          },
        },
      ],
      findings: [
        {
          kind: "claim_gap",
          tax_year: 2026,
          effect_on_cost: null,
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "furgoneta",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "60f7b87f3cacddd83f50355df93b77d31348798f565db35b4edf4328985c967e",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "cde40905354915ad2823fd4bc7fba932069a4af87d95140d1b1014819512d3de",
            evidence_fingerprint:
              "545abb28a3c15a2a1451dae57e1b97e5d78e8932bc8ec5c1ac5e5a3fb60bfa8b",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "24000.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2023-04-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "transporte-externo",
            linear_coefficient: {
              decimal: "0.12",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: {
            category: "mixed_vehicle",
            private_use: "none",
            listed_use: null,
            recorded_in_activity_books: true,
            evidence_reference: "vehicle declaration kept with the purchase",
            electric_propulsion: null,
          },
        },
        revision_id:
          "560cd54b111d30e2ced2bbefb05643bf173c17734e430c33efa12beb75d8db32",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2019,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "covered_by_opening",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: null,
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2020,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "covered_by_opening",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: null,
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2021,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "covered_by_opening",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: null,
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2022,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "800.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "800.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2022",
          authored_filing_year: 2022,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:plotter:2022:a",
            amount: {
              decimal: "800.00",
            },
            covered_from: "2022-01-01",
            covered_until: "2023-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "a8cd7f9d5df28f6131c5ab45818b40dce38e64e727349deab86ed0d4adb9dc76",
          },
        ],
        minimum_through: {
          decimal: "400.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2023,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "400.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "400.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2023",
          authored_filing_year: 2023,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:plotter:2023:a",
            amount: {
              decimal: "400.00",
            },
            covered_from: "2023-01-01",
            covered_until: "2024-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "a8cd7f9d5df28f6131c5ab45818b40dce38e64e727349deab86ed0d4adb9dc76",
          },
        ],
        minimum_through: {
          decimal: "800.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2024,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: null,
        absence: "basis_exhausted",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2024",
          authored_filing_year: 2024,
          projected: false,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [],
        minimum_through: {
          decimal: "1200.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2025,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: null,
        absence: "basis_exhausted",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1600.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2026,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: null,
        absence: "basis_exhausted",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "2000.00",
        },
        minimum_complete: false,
      },
    ],
    limits: {
      class_key: "equipo-proceso-informacion",
      maximum_coefficient: {
        decimal: "0.25",
      },
      minimum_coefficient: {
        decimal: "0.125",
      },
      maximum_period_years: {
        decimal: "8",
      },
      maximum_period_ends_on: "2027-03-01",
      not_table_bound: null,
      unavailable_reason_key: null,
      class_label: "Equipos para procesos de información",
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Real Decreto 439/2007, art. 22",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a22",
        },
        {
          text: "Ley 35/2006, art. 29",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a29",
        },
        {
          text: "Real Decreto 439/2007, art. 30",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a30",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "800.00",
    forecasts: {},
    list: {
      asset_id: "plotter",
      name: "Plotter HP DesignJet",
      serial_number: "HP-DJ-77310",
      asset_kind: "material",
      state: "fully_amortized",
      in_service_date: "2019-03-01",
      method: "linear",
      revision_number: 1,
      basis: {
        decimal: "3200.00",
      },
      accumulated: {
        decimal: "3200.00",
      },
      pending: {
        decimal: "0.00",
      },
      findings: {
        missing: 0,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2022, 2023, 2024, 2025, 2026],
      projected_years: [],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2022-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "plotter",
        record_id:
          "a8cd7f9d5df28f6131c5ab45818b40dce38e64e727349deab86ed0d4adb9dc76",
        effect_date: "2019-03-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2019-03-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "3200.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "equipo-proceso-informacion",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.25",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "plotter",
        record_id: "descriptor:plotter:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Plotter HP DesignJet",
            before_key: null,
            after_key: null,
          },
          {
            field: "serial_number",
            before: null,
            after: "HP-DJ-77310",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
      {
        sequence: 3,
        recorded_at: "2022-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "plotter",
        record_id: "claim:plotter:2022:a",
        effect_date: "2022-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "800.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 4,
        recorded_at: "2023-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "plotter",
        record_id: "claim:plotter:2023:a",
        effect_date: "2023-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "400.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    ],
    id: "plotter",
    disposal: {
      acquisition_value: {
        decimal: "3200.00",
      },
      deducted: {
        decimal: "3200.00",
      },
      minimum: null,
      reduction: {
        decimal: "3200.00",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "0.00",
      },
      years: [
        {
          tax_year: 2019,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "2000.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "2000.00",
          },
        },
        {
          tax_year: 2020,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "2000.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "2000.00",
          },
        },
        {
          tax_year: 2021,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "2000.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "2000.00",
          },
        },
        {
          tax_year: 2022,
          claims: {
            decimal: "800.00",
          },
          deducted_through: {
            decimal: "2800.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "2800.00",
          },
        },
        {
          tax_year: 2023,
          claims: {
            decimal: "400.00",
          },
          deducted_through: {
            decimal: "3200.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "3200.00",
          },
        },
        {
          tax_year: 2024,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "3200.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "3200.00",
          },
        },
        {
          tax_year: 2025,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "3200.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "3200.00",
          },
        },
        {
          tax_year: 2026,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "3200.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "3200.00",
          },
        },
      ],
      findings: [
        {
          kind: "minimum_unresolved",
          tax_year: 2019,
          effect_on_cost: null,
        },
        {
          kind: "minimum_unresolved",
          tax_year: 2020,
          effect_on_cost: null,
        },
        {
          kind: "minimum_unresolved",
          tax_year: 2021,
          effect_on_cost: null,
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "plotter",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "a53145317fd940de14560e30ea36fe57b22d0fc0d7e0097e515a712ce1fbdcb4",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "ab8d745d28550fc64e786883751cd4c1b844d97ba59680464c95b54da647c01d",
            evidence_fingerprint:
              "bd7ac2ef8e00c6b08f18386871936d020dfd3004fc9eeb1397e6e9095dbe48b3",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "3200.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2019-03-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "2000.00",
            },
            amortization_method: "linear",
            covered_through_tax_year: 2021,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "equipo-proceso-informacion",
            linear_coefficient: {
              decimal: "0.25",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "a8cd7f9d5df28f6131c5ab45818b40dce38e64e727349deab86ed0d4adb9dc76",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2019,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "edition_unavailable",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "edition_unavailable",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: null,
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2020,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "edition_unavailable",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "edition_unavailable",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: null,
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2021,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "edition_unavailable",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "edition_unavailable",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: null,
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2022,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "360.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2022",
          authored_filing_year: 2022,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:compresor:2022:a",
            amount: {
              decimal: "360.00",
            },
            covered_from: "2022-01-01",
            covered_until: "2023-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "7127fc69e0644ada65bed7cc0b0d6a7a3b75ca98b43993765254dfa0fff56d18",
          },
        ],
        minimum_through: {
          decimal: "166.67",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2023,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "360.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2023",
          authored_filing_year: 2023,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:compresor:2023:a",
            amount: {
              decimal: "360.00",
            },
            covered_from: "2023-01-01",
            covered_until: "2024-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "7127fc69e0644ada65bed7cc0b0d6a7a3b75ca98b43993765254dfa0fff56d18",
          },
        ],
        minimum_through: {
          decimal: "333.33",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2024,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "360.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2024",
          authored_filing_year: 2024,
          projected: false,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [
          {
            claim_id: "claim:compresor:2024:a",
            amount: {
              decimal: "360.00",
            },
            covered_from: "2024-01-01",
            covered_until: "2025-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "7127fc69e0644ada65bed7cc0b0d6a7a3b75ca98b43993765254dfa0fff56d18",
          },
        ],
        minimum_through: {
          decimal: "500.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2025,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "360.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:compresor:2025:a",
            amount: {
              decimal: "360.00",
            },
            covered_from: "2025-01-01",
            covered_until: "2026-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "7127fc69e0644ada65bed7cc0b0d6a7a3b75ca98b43993765254dfa0fff56d18",
          },
        ],
        minimum_through: {
          decimal: "666.67",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2026,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "360.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:compresor:2026:a",
            amount: {
              decimal: "360.00",
            },
            covered_from: "2026-01-01",
            covered_until: "2027-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "7127fc69e0644ada65bed7cc0b0d6a7a3b75ca98b43993765254dfa0fff56d18",
          },
        ],
        minimum_through: {
          decimal: "833.33",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2027,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2027-01-01",
            covered_until: "2028-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1000.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2028,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2028-01-01",
            covered_until: "2029-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [],
        minimum_through: {
          decimal: "1166.67",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2029,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2029-01-01",
            covered_until: "2030-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1333.33",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2030,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "120.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2030-01-01",
            covered_until: "2031-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1500.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2031,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: null,
        absence: "basis_exhausted",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1666.67",
        },
        minimum_complete: false,
      },
    ],
    limits: {
      class_key: "maquinaria",
      maximum_coefficient: {
        decimal: "0.12",
      },
      minimum_coefficient: {
        decimal: "0.05555555555555555555555555556",
      },
      maximum_period_years: {
        decimal: "18",
      },
      maximum_period_ends_on: "2037-06-01",
      not_table_bound: null,
      unavailable_reason_key: null,
      class_label: "Maquinaria",
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Real Decreto 439/2007, art. 22",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a22",
        },
        {
          text: "Ley 35/2006, art. 29",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a29",
        },
        {
          text: "Real Decreto 439/2007, art. 30",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a30",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "360.00",
    forecasts: {
      "2027-01-01/2028-01-01": "360.00",
      "2028-01-01/2029-01-01": "360.00",
      "2029-01-01/2030-01-01": "360.00",
      "2030-01-01/2031-01-01": "360.00",
    },
    list: {
      asset_id: "compresor",
      name: "Compresor de taller",
      serial_number: "CT-1187",
      asset_kind: "material",
      state: "in_service",
      in_service_date: "2019-06-01",
      method: "linear",
      revision_number: 1,
      basis: {
        decimal: "3000.00",
      },
      accumulated: {
        decimal: "1800.00",
      },
      pending: {
        decimal: "1200.00",
      },
      findings: {
        missing: 0,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2022, 2023, 2024, 2025, 2026],
      projected_years: [2027, 2028, 2029, 2030, 2031],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2022-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "compresor",
        record_id:
          "7127fc69e0644ada65bed7cc0b0d6a7a3b75ca98b43993765254dfa0fff56d18",
        effect_date: "2019-06-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2019-06-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "3000.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "maquinaria",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.12",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "compresor",
        record_id: "descriptor:compresor:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Compresor de taller",
            before_key: null,
            after_key: null,
          },
          {
            field: "serial_number",
            before: null,
            after: "CT-1187",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
      {
        sequence: 3,
        recorded_at: "2022-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "compresor",
        record_id: "claim:compresor:2022:a",
        effect_date: "2022-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "360.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 4,
        recorded_at: "2023-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "compresor",
        record_id: "claim:compresor:2023:a",
        effect_date: "2023-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "360.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 5,
        recorded_at: "2024-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "compresor",
        record_id: "claim:compresor:2024:a",
        effect_date: "2024-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "360.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 6,
        recorded_at: "2025-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "compresor",
        record_id: "claim:compresor:2025:a",
        effect_date: "2025-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "360.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 7,
        recorded_at: "2026-07-02T08:15:00Z",
        kind: "claim",
        asset_id: "compresor",
        record_id: "claim:compresor:2026:a",
        effect_date: "2026-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "360.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    ],
    id: "compresor",
    disposal: {
      acquisition_value: {
        decimal: "3000.00",
      },
      deducted: {
        decimal: "1800.00",
      },
      minimum: null,
      reduction: {
        decimal: "1800.00",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "1200.00",
      },
      years: [
        {
          tax_year: 2019,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "0.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "0.00",
          },
        },
        {
          tax_year: 2020,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "0.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "0.00",
          },
        },
        {
          tax_year: 2021,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "0.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "0.00",
          },
        },
        {
          tax_year: 2022,
          claims: {
            decimal: "360.00",
          },
          deducted_through: {
            decimal: "360.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "360.00",
          },
        },
        {
          tax_year: 2023,
          claims: {
            decimal: "360.00",
          },
          deducted_through: {
            decimal: "720.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "720.00",
          },
        },
        {
          tax_year: 2024,
          claims: {
            decimal: "360.00",
          },
          deducted_through: {
            decimal: "1080.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "1080.00",
          },
        },
        {
          tax_year: 2025,
          claims: {
            decimal: "360.00",
          },
          deducted_through: {
            decimal: "1440.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "1440.00",
          },
        },
        {
          tax_year: 2026,
          claims: {
            decimal: "360.00",
          },
          deducted_through: {
            decimal: "1800.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "1800.00",
          },
        },
      ],
      findings: [
        {
          kind: "claim_gap",
          tax_year: 2019,
          effect_on_cost: null,
        },
        {
          kind: "minimum_unresolved",
          tax_year: 2019,
          effect_on_cost: null,
        },
        {
          kind: "claim_gap",
          tax_year: 2020,
          effect_on_cost: null,
        },
        {
          kind: "minimum_unresolved",
          tax_year: 2020,
          effect_on_cost: null,
        },
        {
          kind: "claim_gap",
          tax_year: 2021,
          effect_on_cost: null,
        },
        {
          kind: "minimum_unresolved",
          tax_year: 2021,
          effect_on_cost: null,
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "compresor",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "2486f945cdf86a563aa15bc8f91017c3c9ca53d2fbc3abf36065d3a9f33eba4f",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "b34bc924e05559069ff39a29a5de32a9cb79871a03eff246a38b9644c3230319",
            evidence_fingerprint:
              "b95592400eca5786086dad5267bd219a9d3d1ed458828392a5cdc88d596134fa",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "3000.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2019-06-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "maquinaria",
            linear_coefficient: {
              decimal: "0.12",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "7127fc69e0644ada65bed7cc0b0d6a7a3b75ca98b43993765254dfa0fff56d18",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2022,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "200.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "200.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2022",
          authored_filing_year: 2022,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:cristaleria:2022:a",
            amount: {
              decimal: "200.00",
            },
            covered_from: "2022-01-01",
            covered_until: "2023-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "88db509d3004cfed2c0949be881afc41a18c287e85d6dbd20f3f08bb81f0e7e4",
          },
        ],
        minimum_through: {
          decimal: "200.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2023,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "200.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "200.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2023",
          authored_filing_year: 2023,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:cristaleria:2023:a",
            amount: {
              decimal: "200.00",
            },
            covered_from: "2023-01-01",
            covered_until: "2024-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "88db509d3004cfed2c0949be881afc41a18c287e85d6dbd20f3f08bb81f0e7e4",
          },
        ],
        minimum_through: {
          decimal: "400.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2024,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "200.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [
          {
            covered_from: "2024-01-01",
            covered_until: "2025-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2024",
          authored_filing_year: 2024,
          projected: false,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [],
        minimum_through: {
          decimal: "600.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2025,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "200.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [
          {
            covered_from: "2025-01-01",
            covered_until: "2026-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "800.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2026,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "period_elapsed",
        absence_reason_key:
          "ledger.actividad_asset.errors.amortization_period_elapsed",
        absence_reason_facts: [
          {
            key: "ended_on",
            value: "2026-01-01",
          },
        ],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "800.00",
        },
        minimum_complete: true,
      },
    ],
    limits: {
      class_key: "cristaleria",
      maximum_coefficient: {
        decimal: "0.5",
      },
      minimum_coefficient: {
        decimal: "0.25",
      },
      maximum_period_years: {
        decimal: "4",
      },
      maximum_period_ends_on: "2026-01-01",
      not_table_bound: null,
      unavailable_reason_key: null,
      class_label: "Cristalería",
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Real Decreto 439/2007, art. 22",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a22",
        },
        {
          text: "Ley 35/2006, art. 29",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a29",
        },
        {
          text: "Real Decreto 439/2007, art. 30",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a30",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "200.00",
    forecasts: {
      "2024-01-01/2025-01-01": "200.00",
      "2025-01-01/2026-01-01": "200.00",
    },
    list: {
      asset_id: "cristaleria",
      name: "Cristalería de la sala de catas",
      serial_number: null,
      asset_kind: "material",
      state: "in_service",
      in_service_date: "2022-01-01",
      method: "linear",
      revision_number: 1,
      basis: {
        decimal: "800.00",
      },
      accumulated: {
        decimal: "400.00",
      },
      pending: {
        decimal: "400.00",
      },
      findings: {
        missing: 2,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2022, 2023, 2024, 2025, 2026],
      projected_years: [],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2022-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "cristaleria",
        record_id:
          "88db509d3004cfed2c0949be881afc41a18c287e85d6dbd20f3f08bb81f0e7e4",
        effect_date: "2022-01-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2022-01-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "800.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "cristaleria",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.25",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "cristaleria",
        record_id: "descriptor:cristaleria:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Cristalería de la sala de catas",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
      {
        sequence: 3,
        recorded_at: "2022-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "cristaleria",
        record_id: "claim:cristaleria:2022:a",
        effect_date: "2022-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "200.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 4,
        recorded_at: "2023-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "cristaleria",
        record_id: "claim:cristaleria:2023:a",
        effect_date: "2023-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "200.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    ],
    id: "cristaleria",
    disposal: {
      acquisition_value: {
        decimal: "800.00",
      },
      deducted: {
        decimal: "400.00",
      },
      minimum: {
        decimal: "800.00",
      },
      reduction: {
        decimal: "800.00",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "0.00",
      },
      years: [
        {
          tax_year: 2022,
          claims: {
            decimal: "200.00",
          },
          deducted_through: {
            decimal: "200.00",
          },
          minimum_through: {
            decimal: "200.00",
          },
          reduction_through: {
            decimal: "200.00",
          },
        },
        {
          tax_year: 2023,
          claims: {
            decimal: "200.00",
          },
          deducted_through: {
            decimal: "400.00",
          },
          minimum_through: {
            decimal: "400.00",
          },
          reduction_through: {
            decimal: "400.00",
          },
        },
        {
          tax_year: 2024,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "400.00",
          },
          minimum_through: {
            decimal: "600.00",
          },
          reduction_through: {
            decimal: "600.00",
          },
        },
        {
          tax_year: 2025,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "400.00",
          },
          minimum_through: {
            decimal: "800.00",
          },
          reduction_through: {
            decimal: "800.00",
          },
        },
        {
          tax_year: 2026,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "400.00",
          },
          minimum_through: {
            decimal: "800.00",
          },
          reduction_through: {
            decimal: "800.00",
          },
        },
      ],
      findings: [
        {
          kind: "claim_gap",
          tax_year: 2024,
          effect_on_cost: null,
        },
        {
          kind: "minimum_exceeded_deduction",
          tax_year: 2024,
          effect_on_cost: {
            decimal: "200.00",
          },
        },
        {
          kind: "claim_gap",
          tax_year: 2025,
          effect_on_cost: null,
        },
        {
          kind: "minimum_exceeded_deduction",
          tax_year: 2025,
          effect_on_cost: {
            decimal: "200.00",
          },
        },
        {
          kind: "no_minimum_authority",
          tax_year: 2026,
          effect_on_cost: null,
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "cristaleria",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "b3c79e37e048a5436e5eb994fd1b25f7af8a4f531aa2ef4a252067323136025a",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "28de6015d2995985e9ccabb6caa220cc2816825acfabfb05a8c000bf531a250f",
            evidence_fingerprint:
              "71af6db521cd5bae0c8a74b86b62aaaccf0b1e6c7bf4b87b5d198f426d533170",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "800.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2022-01-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "cristaleria",
            linear_coefficient: {
              decimal: "0.25",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "88db509d3004cfed2c0949be881afc41a18c287e85d6dbd20f3f08bb81f0e7e4",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2021,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "edition_unavailable",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "edition_unavailable",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: null,
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2022,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "720.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "720.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2022",
          authored_filing_year: 2022,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:camara:2022:a",
            amount: {
              decimal: "720.00",
            },
            covered_from: "2022-01-01",
            covered_until: "2023-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "1fdac19279e0acbe427bafdd6e9953d7d5e48de48848a183910eab414fda725e",
          },
        ],
        minimum_through: {
          decimal: "333.33",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2023,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "720.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "720.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2023",
          authored_filing_year: 2023,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:camara:2023:a",
            amount: {
              decimal: "720.00",
            },
            covered_from: "2023-01-01",
            covered_until: "2024-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "1fdac19279e0acbe427bafdd6e9953d7d5e48de48848a183910eab414fda725e",
          },
        ],
        minimum_through: {
          decimal: "666.67",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2024,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "720.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "720.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2024",
          authored_filing_year: 2024,
          projected: false,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [
          {
            claim_id: "claim:camara:2024:a",
            amount: {
              decimal: "720.00",
            },
            covered_from: "2024-01-01",
            covered_until: "2025-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "1fdac19279e0acbe427bafdd6e9953d7d5e48de48848a183910eab414fda725e",
          },
        ],
        minimum_through: {
          decimal: "1000.00",
        },
        minimum_complete: false,
      },
      {
        tax_year: 2025,
        method: "linear",
        coefficient: {
          decimal: "0.12",
        },
        planned: {
          decimal: "357.04",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "357.04",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: 181,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:camara:2025:a",
            amount: {
              decimal: "357.04",
            },
            covered_from: "2025-01-01",
            covered_until: "2025-07-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "1fdac19279e0acbe427bafdd6e9953d7d5e48de48848a183910eab414fda725e",
          },
        ],
        minimum_through: {
          decimal: "1333.33",
        },
        minimum_complete: false,
      },
    ],
    limits: {
      class_key: "maquinaria",
      maximum_coefficient: {
        decimal: "0.12",
      },
      minimum_coefficient: {
        decimal: "0.05555555555555555555555555556",
      },
      maximum_period_years: {
        decimal: "18",
      },
      maximum_period_ends_on: "2039-01-01",
      not_table_bound: null,
      unavailable_reason_key: null,
      class_label: "Maquinaria",
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Real Decreto 439/2007, art. 22",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a22",
        },
        {
          text: "Ley 35/2006, art. 29",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a29",
        },
        {
          text: "Real Decreto 439/2007, art. 30",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a30",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "720.00",
    forecasts: {},
    list: {
      asset_id: "camara",
      name: "Cámara de revelado",
      serial_number: "CR-3312",
      asset_kind: "material",
      state: "out_of_service",
      in_service_date: "2021-01-01",
      method: "linear",
      revision_number: 1,
      basis: {
        decimal: "6000.00",
      },
      accumulated: {
        decimal: "2517.04",
      },
      pending: {
        decimal: "3482.96",
      },
      findings: {
        missing: 0,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2022, 2023, 2024, 2025],
      projected_years: [],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2022-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "camara",
        record_id:
          "1fdac19279e0acbe427bafdd6e9953d7d5e48de48848a183910eab414fda725e",
        effect_date: "2021-01-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2021-01-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "6000.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "maquinaria",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.12",
            before_key: null,
            after_key: null,
          },
          {
            field: "out_of_service_date",
            before: null,
            after: "2025-07-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "camara",
        record_id: "descriptor:camara:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Cámara de revelado",
            before_key: null,
            after_key: null,
          },
          {
            field: "serial_number",
            before: null,
            after: "CR-3312",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
      {
        sequence: 3,
        recorded_at: "2022-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "camara",
        record_id: "claim:camara:2022:a",
        effect_date: "2022-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "720.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 4,
        recorded_at: "2023-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "camara",
        record_id: "claim:camara:2023:a",
        effect_date: "2023-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "720.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 5,
        recorded_at: "2024-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "camara",
        record_id: "claim:camara:2024:a",
        effect_date: "2024-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "720.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 6,
        recorded_at: "2025-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "camara",
        record_id: "claim:camara:2025:a",
        effect_date: "2025-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "357.04",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    ],
    id: "camara",
    disposal: {
      acquisition_value: {
        decimal: "6000.00",
      },
      deducted: {
        decimal: "2517.04",
      },
      minimum: null,
      reduction: {
        decimal: "2517.04",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "3482.96",
      },
      years: [
        {
          tax_year: 2021,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "0.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "0.00",
          },
        },
        {
          tax_year: 2022,
          claims: {
            decimal: "720.00",
          },
          deducted_through: {
            decimal: "720.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "720.00",
          },
        },
        {
          tax_year: 2023,
          claims: {
            decimal: "720.00",
          },
          deducted_through: {
            decimal: "1440.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "1440.00",
          },
        },
        {
          tax_year: 2024,
          claims: {
            decimal: "720.00",
          },
          deducted_through: {
            decimal: "2160.00",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "2160.00",
          },
        },
        {
          tax_year: 2025,
          claims: {
            decimal: "357.04",
          },
          deducted_through: {
            decimal: "2517.04",
          },
          minimum_through: null,
          reduction_through: {
            decimal: "2517.04",
          },
        },
      ],
      findings: [
        {
          kind: "claim_gap",
          tax_year: 2021,
          effect_on_cost: null,
        },
        {
          kind: "minimum_unresolved",
          tax_year: 2021,
          effect_on_cost: null,
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "camara",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "e59c2f3716c42fac35b2134ac1d572ed62472ef6716718306b931ed860b55754",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "f8bf606a87dc03c248703a5af696ede7c572af8f384ea189707a4d1d5395e9e1",
            evidence_fingerprint:
              "271cdd9faf7033f7c4cfc48e9aee4b7886369330518f1ee90eadbd7d5c1fd4f9",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "6000.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2021-01-01",
          out_of_service_date: "2025-07-01",
          disposal: {
            disposal_date: "2025-06-30",
            reason: "sale",
            proceeds: {
              decimal: "1500.00",
            },
            transmission_costs: {
              decimal: "0.00",
            },
            market_value: null,
            prior_free_depreciation_regime: null,
            later_affectation_on: null,
          },
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "maquinaria",
            linear_coefficient: {
              decimal: "0.12",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "1fdac19279e0acbe427bafdd6e9953d7d5e48de48848a183910eab414fda725e",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2024,
        method: "linear",
        coefficient: {
          decimal: "0.20",
        },
        planned: {
          decimal: "329.51",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "329.51",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2024",
          authored_filing_year: 2024,
          projected: false,
        },
        service_days: 335,
        calendar_days: 366,
        claims: [
          {
            claim_id: "claim:licencia:2024:a",
            amount: {
              decimal: "329.51",
            },
            covered_from: "2024-02-01",
            covered_until: "2025-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "15f70714e8eb30f1db70722c0c66f88b5427f6d7c9aef3ff75fcf32ef6f8166e",
          },
        ],
        minimum_through: {
          decimal: "274.59",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2025,
        method: "linear",
        coefficient: {
          decimal: "0.20",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "360.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:licencia:2025:a",
            amount: {
              decimal: "360.00",
            },
            covered_from: "2025-01-01",
            covered_until: "2026-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "15f70714e8eb30f1db70722c0c66f88b5427f6d7c9aef3ff75fcf32ef6f8166e",
          },
        ],
        minimum_through: {
          decimal: "574.59",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2026,
        method: "linear",
        coefficient: {
          decimal: "0.20",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [
          {
            covered_from: "2026-01-01",
            covered_until: "2027-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "874.59",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2027,
        method: "linear",
        coefficient: {
          decimal: "0.20",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2027-01-01",
            covered_until: "2028-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1174.59",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2028,
        method: "linear",
        coefficient: {
          decimal: "0.20",
        },
        planned: {
          decimal: "360.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2028-01-01",
            covered_until: "2029-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [],
        minimum_through: {
          decimal: "1474.59",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2029,
        method: "linear",
        coefficient: {
          decimal: "0.20",
        },
        planned: {
          decimal: "30.49",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2029-01-01",
            covered_until: "2030-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1774.59",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2030,
        method: "linear",
        coefficient: {
          decimal: "0.20",
        },
        planned: null,
        absence: "basis_exhausted",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1800.00",
        },
        minimum_complete: true,
      },
    ],
    limits: {
      class_key: "intangible-software",
      maximum_coefficient: {
        decimal: "0.33",
      },
      minimum_coefficient: {
        decimal: "0.1666666666666666666666666667",
      },
      maximum_period_years: {
        decimal: "6",
      },
      maximum_period_ends_on: "2030-02-01",
      not_table_bound: null,
      unavailable_reason_key: null,
      class_label: "Sistemas y programas informáticos",
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Real Decreto 439/2007, art. 30",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a30",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "360.00",
    forecasts: {
      "2026-01-01/2027-01-01": "360.00",
      "2027-01-01/2028-01-01": "360.00",
      "2028-01-01/2029-01-01": "360.00",
      "2029-01-01/2030-01-01": "360.00",
    },
    list: {
      asset_id: "licencia",
      name: "Licencia de facturación",
      serial_number: null,
      asset_kind: "intangible",
      state: "in_service",
      in_service_date: "2024-02-01",
      method: "linear",
      revision_number: 1,
      basis: {
        decimal: "1800.00",
      },
      accumulated: {
        decimal: "689.51",
      },
      pending: {
        decimal: "1110.49",
      },
      findings: {
        missing: 1,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2024, 2025, 2026],
      projected_years: [2027, 2028, 2029, 2030],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2024-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "licencia",
        record_id:
          "15f70714e8eb30f1db70722c0c66f88b5427f6d7c9aef3ff75fcf32ef6f8166e",
        effect_date: "2024-02-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "intangible",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2024-02-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "1800.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "intangible-software",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.20",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "licencia",
        record_id: "descriptor:licencia:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Licencia de facturación",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
      {
        sequence: 3,
        recorded_at: "2024-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "licencia",
        record_id: "claim:licencia:2024:a",
        effect_date: "2024-02-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "329.51",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 4,
        recorded_at: "2025-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "licencia",
        record_id: "claim:licencia:2025:a",
        effect_date: "2025-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "360.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    ],
    id: "licencia",
    disposal: {
      acquisition_value: {
        decimal: "1800.00",
      },
      deducted: {
        decimal: "689.51",
      },
      minimum: {
        decimal: "874.59",
      },
      reduction: {
        decimal: "874.59",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "925.41",
      },
      years: [
        {
          tax_year: 2024,
          claims: {
            decimal: "329.51",
          },
          deducted_through: {
            decimal: "329.51",
          },
          minimum_through: {
            decimal: "274.59",
          },
          reduction_through: {
            decimal: "329.51",
          },
        },
        {
          tax_year: 2025,
          claims: {
            decimal: "360.00",
          },
          deducted_through: {
            decimal: "689.51",
          },
          minimum_through: {
            decimal: "574.59",
          },
          reduction_through: {
            decimal: "689.51",
          },
        },
        {
          tax_year: 2026,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "689.51",
          },
          minimum_through: {
            decimal: "874.59",
          },
          reduction_through: {
            decimal: "874.59",
          },
        },
      ],
      findings: [
        {
          kind: "claim_gap",
          tax_year: 2026,
          effect_on_cost: null,
        },
        {
          kind: "minimum_exceeded_deduction",
          tax_year: 2026,
          effect_on_cost: {
            decimal: "185.08",
          },
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "licencia",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "48d4b2c3c6f37c5a05cf21dfaa37c34e305d6a0e806bb07118e2d496f5a03a57",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "70f5cb673ea76882569d0bfa4fa3d51a21b9d7fc331425a761c26689e17c61c7",
            evidence_fingerprint:
              "189dfd4de9bbcbfd5821892fbbacaf361b89e1e7611d4b667926055215d4ba26",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "intangible",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "1800.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2024-02-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "intangible-software",
            linear_coefficient: {
              decimal: "0.20",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "15f70714e8eb30f1db70722c0c66f88b5427f6d7c9aef3ff75fcf32ef6f8166e",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2024,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "146.17",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "146.17",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2024",
          authored_filing_year: 2024,
          projected: false,
        },
        service_days: 214,
        calendar_days: 366,
        claims: [
          {
            claim_id: "claim:herramienta:2024:a",
            amount: {
              decimal: "146.17",
            },
            covered_from: "2024-06-01",
            covered_until: "2025-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "0a17aacb8134c450951172aecfa93f86d70c297854cc6d583b3b124e3379944e",
          },
        ],
        minimum_through: {
          decimal: "73.09",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2025,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "250.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "250.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:herramienta:2025:a",
            amount: {
              decimal: "250.00",
            },
            covered_from: "2025-01-01",
            covered_until: "2026-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "0a17aacb8134c450951172aecfa93f86d70c297854cc6d583b3b124e3379944e",
          },
        ],
        minimum_through: {
          decimal: "198.09",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2026,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "250.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "250.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:herramienta:2026:a",
            amount: {
              decimal: "250.00",
            },
            covered_from: "2026-01-01",
            covered_until: "2027-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "0a17aacb8134c450951172aecfa93f86d70c297854cc6d583b3b124e3379944e",
          },
        ],
        minimum_through: {
          decimal: "323.09",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2027,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "250.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2027-01-01",
            covered_until: "2028-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "448.09",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2028,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "103.83",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2028-01-01",
            covered_until: "2029-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [],
        minimum_through: {
          decimal: "573.09",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2029,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: null,
        absence: "basis_exhausted",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "698.09",
        },
        minimum_complete: true,
      },
    ],
    limits: {
      class_key: "util-herramienta",
      maximum_coefficient: {
        decimal: "0.25",
      },
      minimum_coefficient: {
        decimal: "0.125",
      },
      maximum_period_years: {
        decimal: "8",
      },
      maximum_period_ends_on: "2032-06-01",
      not_table_bound: null,
      unavailable_reason_key: null,
      class_label: "Útiles y herramientas",
      legal_citations: [
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Real Decreto 439/2007, art. 22",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a22",
        },
        {
          text: "Ley 35/2006, art. 29",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a29",
        },
        {
          text: "Real Decreto 439/2007, art. 30",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a30",
        },
      ],
      legal_citations_complete: false,
    },
    annual: "250.00",
    forecasts: {
      "2027-01-01/2028-01-01": "250.00",
      "2028-01-01/2029-01-01": "250.00",
    },
    list: {
      asset_id: "herramienta",
      name: null,
      serial_number: null,
      asset_kind: "material",
      state: "in_service",
      in_service_date: "2024-06-01",
      method: "linear",
      revision_number: 1,
      basis: {
        decimal: "1000.00",
      },
      accumulated: {
        decimal: "646.17",
      },
      pending: {
        decimal: "353.83",
      },
      findings: {
        missing: 0,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2024, 2025, 2026],
      projected_years: [2027, 2028, 2029],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2024-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "herramienta",
        record_id:
          "0a17aacb8134c450951172aecfa93f86d70c297854cc6d583b3b124e3379944e",
        effect_date: "2024-06-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2024-06-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "1000.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "util-herramienta",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.25",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2024-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "herramienta",
        record_id: "claim:herramienta:2024:a",
        effect_date: "2024-06-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "146.17",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 3,
        recorded_at: "2025-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "herramienta",
        record_id: "claim:herramienta:2025:a",
        effect_date: "2025-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "250.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
      {
        sequence: 4,
        recorded_at: "2026-07-02T08:15:00Z",
        kind: "claim",
        asset_id: "herramienta",
        record_id: "claim:herramienta:2026:a",
        effect_date: "2026-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "250.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    ],
    id: "herramienta",
    disposal: {
      acquisition_value: {
        decimal: "1000.00",
      },
      deducted: {
        decimal: "646.17",
      },
      minimum: {
        decimal: "323.09",
      },
      reduction: {
        decimal: "646.17",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "353.83",
      },
      years: [
        {
          tax_year: 2024,
          claims: {
            decimal: "146.17",
          },
          deducted_through: {
            decimal: "146.17",
          },
          minimum_through: {
            decimal: "73.09",
          },
          reduction_through: {
            decimal: "146.17",
          },
        },
        {
          tax_year: 2025,
          claims: {
            decimal: "250.00",
          },
          deducted_through: {
            decimal: "396.17",
          },
          minimum_through: {
            decimal: "198.09",
          },
          reduction_through: {
            decimal: "396.17",
          },
        },
        {
          tax_year: 2026,
          claims: {
            decimal: "250.00",
          },
          deducted_through: {
            decimal: "646.17",
          },
          minimum_through: {
            decimal: "323.09",
          },
          reduction_through: {
            decimal: "646.17",
          },
        },
      ],
      findings: [],
    },
    revisions: [
      {
        revision: {
          asset_id: "herramienta",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "ead1189aae506fc17ff580765f6b3bc77e5da95837e730a7f8df3d1de309edd4",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "39fcb7d7c55eb3bea9b343d8eef6e9bf836b1e68463ad18b2c9bb0978a45578c",
            evidence_fingerprint:
              "66f46cc72a09e9b43e2dd37725e79a826382eee32258b7c518293fb4b4aaa122",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "1000.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2024-06-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "util-herramienta",
            linear_coefficient: {
              decimal: "0.25",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "0a17aacb8134c450951172aecfa93f86d70c297854cc6d583b3b124e3379944e",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2025,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "950.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "1000.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [
          {
            claim_id: "claim:servidor:2025:a",
            amount: {
              decimal: "1000.00",
            },
            covered_from: "2025-01-01",
            covered_until: "2026-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "78d8df9f5e59d09c169c49c0e16a9734b4b053ac1dddb6681b6ac448c8a2bea3",
          },
        ],
        minimum_through: {
          decimal: "475.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2026,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "950.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [
          {
            covered_from: "2026-01-01",
            covered_until: "2027-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "950.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2027,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "950.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2027-01-01",
            covered_until: "2028-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "1425.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2028,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: {
          decimal: "900.00",
        },
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [
          {
            covered_from: "2028-01-01",
            covered_until: "2029-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 366,
        calendar_days: 366,
        claims: [],
        minimum_through: {
          decimal: "1900.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2029,
        method: "linear",
        coefficient: {
          decimal: "0.25",
        },
        planned: null,
        absence: "basis_exhausted",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "not_due",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: 365,
        calendar_days: 365,
        claims: [],
        minimum_through: {
          decimal: "2375.00",
        },
        minimum_complete: true,
      },
    ],
    limits: {
      class_key: "equipo-proceso-informacion",
      maximum_coefficient: {
        decimal: "0.25",
      },
      minimum_coefficient: {
        decimal: "0.125",
      },
      maximum_period_years: {
        decimal: "8",
      },
      maximum_period_ends_on: "2033-01-01",
      not_table_bound: null,
      unavailable_reason_key: null,
      class_label: "Equipos para procesos de información",
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Real Decreto 439/2007, art. 22",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a22",
        },
        {
          text: "Ley 35/2006, art. 29",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a29",
        },
        {
          text: "Real Decreto 439/2007, art. 30",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a30",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "950.00",
    forecasts: {
      "2026-01-01/2027-01-01": "950.00",
      "2027-01-01/2028-01-01": "950.00",
      "2028-01-01/2029-01-01": "950.00",
    },
    list: {
      asset_id: "servidor",
      name: "Servidor de archivos",
      serial_number: "SRV-0042",
      asset_kind: "material",
      state: "in_service",
      in_service_date: "2025-01-01",
      method: "linear",
      revision_number: 2,
      basis: {
        decimal: "3800.00",
      },
      accumulated: {
        decimal: "1000.00",
      },
      pending: {
        decimal: "2800.00",
      },
      findings: {
        missing: 1,
        incomplete: 0,
        conflict: 0,
        stale: 1,
      },
      years: [2025, 2026],
      projected_years: [2027, 2028, 2029],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2025-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "servidor",
        record_id:
          "78d8df9f5e59d09c169c49c0e16a9734b4b053ac1dddb6681b6ac448c8a2bea3",
        effect_date: "2025-01-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2025-01-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "4000.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "equipo-proceso-informacion",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.25",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "servidor",
        record_id: "descriptor:servidor:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Servidor de archivos",
            before_key: null,
            after_key: null,
          },
          {
            field: "serial_number",
            before: null,
            after: "SRV-0042",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
      {
        sequence: 3,
        recorded_at: "2025-02-01T11:00:00Z",
        kind: "claim",
        asset_id: "servidor",
        record_id: "claim:servidor:2025:a",
        effect_date: "2025-01-01",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "1000.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: false,
          stale_reason: "revision_changed",
        },
      },
      {
        sequence: 4,
        recorded_at: "2026-03-02T16:40:00Z",
        kind: "revision",
        asset_id: "servidor",
        record_id:
          "437861476814dff5dfdb02a1e63e995fb682429873c5596eb9c85ec38c1defe0",
        effect_date: "2025-01-01",
        origin: "ledger.actividad-asset.correct",
        changes: [
          {
            field: "basis.basis_amount",
            before: "4000.00",
            after: "3800.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: null,
      },
    ],
    id: "servidor",
    disposal: {
      acquisition_value: {
        decimal: "3800.00",
      },
      deducted: {
        decimal: "1000.00",
      },
      minimum: {
        decimal: "950.00",
      },
      reduction: {
        decimal: "1000.00",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "2800.00",
      },
      years: [
        {
          tax_year: 2025,
          claims: {
            decimal: "1000.00",
          },
          deducted_through: {
            decimal: "1000.00",
          },
          minimum_through: {
            decimal: "475.00",
          },
          reduction_through: {
            decimal: "1000.00",
          },
        },
        {
          tax_year: 2026,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "1000.00",
          },
          minimum_through: {
            decimal: "950.00",
          },
          reduction_through: {
            decimal: "1000.00",
          },
        },
      ],
      findings: [
        {
          kind: "claim_gap",
          tax_year: 2026,
          effect_on_cost: null,
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "servidor",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "9516cd4929684d9b779279cc95607a90c0fa1f571585c692a08cb8f037722b98",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "70959a76a0cfe26ddd07c916d1532676c8b19b81109971f30d3c77d1bf271d09",
            evidence_fingerprint:
              "cc8231866ed4de2af8d02ff4bf82719a8514733fe42b014b382d9f17826041e1",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "4000.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2025-01-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "equipo-proceso-informacion",
            linear_coefficient: {
              decimal: "0.25",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "78d8df9f5e59d09c169c49c0e16a9734b4b053ac1dddb6681b6ac448c8a2bea3",
      },
      {
        revision: {
          asset_id: "servidor",
          revision_number: 2,
          supersedes_revision_id:
            "78d8df9f5e59d09c169c49c0e16a9734b4b053ac1dddb6681b6ac448c8a2bea3",
          acquisition: {
            observed_transaction_id:
              "9516cd4929684d9b779279cc95607a90c0fa1f571585c692a08cb8f037722b98",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "70959a76a0cfe26ddd07c916d1532676c8b19b81109971f30d3c77d1bf271d09",
            evidence_fingerprint:
              "cc8231866ed4de2af8d02ff4bf82719a8514733fe42b014b382d9f17826041e1",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "3800.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2025-01-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "equipo-proceso-informacion",
            linear_coefficient: {
              decimal: "0.25",
            },
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "437861476814dff5dfdb02a1e63e995fb682429873c5596eb9c85ec38c1defe0",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2023,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "incomplete",
        absence_reason_key:
          "ledger.actividad_asset.errors.opening_history_missing",
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [],
        claimable_refusal_key:
          "ledger.actividad_asset.errors.opening_history_missing",
        edition: {
          revision_id: "2023",
          authored_filing_year: 2023,
          projected: false,
        },
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "450.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2024,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "incomplete",
        absence_reason_key:
          "ledger.actividad_asset.errors.opening_history_missing",
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [],
        claimable_refusal_key:
          "ledger.actividad_asset.errors.opening_history_missing",
        edition: {
          revision_id: "2024",
          authored_filing_year: 2024,
          projected: false,
        },
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "900.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2025,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "incomplete",
        absence_reason_key:
          "ledger.actividad_asset.errors.opening_history_missing",
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [],
        claimable_refusal_key:
          "ledger.actividad_asset.errors.opening_history_missing",
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: false,
        },
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "1350.00",
        },
        minimum_complete: true,
      },
      {
        tax_year: 2026,
        method: "linear",
        coefficient: null,
        planned: null,
        absence: "incomplete",
        absence_reason_key:
          "ledger.actividad_asset.errors.opening_history_missing",
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [],
        claimable_refusal_key:
          "ledger.actividad_asset.errors.opening_history_missing",
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "1800.00",
        },
        minimum_complete: true,
      },
    ],
    limits: {
      class_key: "instalacion-resto",
      maximum_coefficient: null,
      minimum_coefficient: null,
      maximum_period_years: null,
      maximum_period_ends_on: null,
      not_table_bound: "authority_unavailable",
      unavailable_reason_key:
        "ledger.actividad_asset.errors.opening_history_missing",
      class_label: "Resto instalaciones",
      legal_citations: [],
      legal_citations_complete: true,
    },
    annual: "900.00",
    forecasts: {},
    list: {
      asset_id: "estanteria",
      name: "Estanterías de almacén",
      serial_number: null,
      asset_kind: "material",
      state: "in_service",
      in_service_date: "2023-01-01",
      method: "linear",
      revision_number: 1,
      basis: {
        decimal: "9000.00",
      },
      accumulated: null,
      pending: null,
      findings: {
        missing: 4,
        incomplete: 4,
        conflict: 0,
        stale: 0,
      },
      years: [2023, 2024, 2025, 2026],
      projected_years: [],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2023-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "estanteria",
        record_id:
          "d102612d27089ac5a69339bb13de2dad99bc3269bd7cce1d1482b49fccccd76d",
        effect_date: "2023-01-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2023-01-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "9000.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "linear",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.authority_class_key",
            before: null,
            after: "instalacion-resto",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.linear_coefficient",
            before: null,
            after: "0.10",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "missing",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.missing",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "estanteria",
        record_id: "descriptor:estanteria:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Estanterías de almacén",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
    ],
    id: "estanteria",
    disposal: null,
    revisions: [
      {
        revision: {
          asset_id: "estanteria",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "fcf8d908bd0bf585c6a9b55d4e0f0aac85bc20ae713cc53d9154b1e7be7576b9",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "ce677c9e8cb5fdc991a7133b4942aa6a7968c1276a310a2c97829d41cbce9643",
            evidence_fingerprint:
              "b921182a4f1eace0b310e5a340345880af9d38c33bc917367977221743c77727",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "9000.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2023-01-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "missing",
            accumulated_amount: null,
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "linear",
            authority_class_key: "instalacion-resto",
            linear_coefficient: null,
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: null,
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "d102612d27089ac5a69339bb13de2dad99bc3269bd7cce1d1482b49fccccd76d",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2026,
        method: "low_value_free",
        coefficient: null,
        planned: null,
        absence: "free_election",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "280.00",
        },
        claim_state: "claimed",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: null,
        calendar_days: null,
        claims: [
          {
            claim_id: "claim:taladro:2026:a",
            amount: {
              decimal: "280.00",
            },
            covered_from: "2026-03-10",
            covered_until: "2027-01-01",
            effective: true,
            superseded_by: null,
            revision_id:
              "af334604210b0c356bbd26d6ad7608a666a8de6b661261030333d021fc8e7021",
          },
        ],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
    ],
    limits: {
      class_key: null,
      maximum_coefficient: null,
      minimum_coefficient: null,
      maximum_period_years: null,
      maximum_period_ends_on: null,
      not_table_bound: "free_election",
      unavailable_reason_key: null,
      class_label: null,
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Ley 27/2014, art. 12 3 e",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "0.00",
    forecasts: {},
    list: {
      asset_id: "taladro",
      name: "Taladro percutor",
      serial_number: "TP-5521",
      asset_kind: "material",
      state: "fully_amortized",
      in_service_date: "2026-03-10",
      method: "low_value_free",
      revision_number: 1,
      basis: {
        decimal: "280.00",
      },
      accumulated: {
        decimal: "280.00",
      },
      pending: {
        decimal: "0.00",
      },
      findings: {
        missing: 0,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2026],
      projected_years: [],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2026-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "taladro",
        record_id:
          "af334604210b0c356bbd26d6ad7608a666a8de6b661261030333d021fc8e7021",
        effect_date: "2026-03-10",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2026-03-10",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "280.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "low_value_free",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "taladro",
        record_id: "descriptor:taladro:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Taladro percutor",
            before_key: null,
            after_key: null,
          },
          {
            field: "serial_number",
            before: null,
            after: "TP-5521",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
      {
        sequence: 3,
        recorded_at: "2026-07-02T08:15:00Z",
        kind: "claim",
        asset_id: "taladro",
        record_id: "claim:taladro:2026:a",
        effect_date: "2026-03-10",
        origin: "ledger.actividad-asset.claim",
        changes: [
          {
            field: "amount",
            before: null,
            after: "280.00",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: true,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    ],
    id: "taladro",
    disposal: {
      acquisition_value: {
        decimal: "280.00",
      },
      deducted: {
        decimal: "280.00",
      },
      minimum: {
        decimal: "0.00",
      },
      reduction: {
        decimal: "280.00",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "0.00",
      },
      years: [
        {
          tax_year: 2026,
          claims: {
            decimal: "280.00",
          },
          deducted_through: {
            decimal: "280.00",
          },
          minimum_through: {
            decimal: "0.00",
          },
          reduction_through: {
            decimal: "280.00",
          },
        },
      ],
      findings: [
        {
          kind: "no_minimum_authority",
          tax_year: 2026,
          effect_on_cost: null,
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "taladro",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "0e858003b470ea006536f9b5600e479307597b0d64dbaacbc3d409a82a9ab4dc",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "a17dbfcb09c1269f2598835b1b4288aeafd05785916dfb18d6deb58c8da73a5d",
            evidence_fingerprint:
              "1e8a8e0ef9ad7d0607101b04870a2606911c9c5bb26e13c82b3fbe8fbf0070d8",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "280.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2026-03-10",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "low_value_free",
            authority_class_key: null,
            linear_coefficient: null,
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: {
              election_reference: "election recorded with the purchase",
              new_material_evidence_reference: "purchase invoice",
            },
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "af334604210b0c356bbd26d6ad7608a666a8de6b661261030333d021fc8e7021",
      },
    ],
  },
  {
    rows: [
      {
        tax_year: 2026,
        method: "low_value_free",
        coefficient: null,
        planned: null,
        absence: "free_election",
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: {
          decimal: "0.00",
        },
        claim_state: "missing",
        claimable_intervals: [
          {
            covered_from: "2026-09-01",
            covered_until: "2027-01-01",
          },
        ],
        claimable_refusal_key: null,
        edition: {
          revision_id: "2025",
          authored_filing_year: 2025,
          projected: true,
        },
        service_days: null,
        calendar_days: null,
        claims: [],
        minimum_through: {
          decimal: "0.00",
        },
        minimum_complete: false,
      },
    ],
    limits: {
      class_key: null,
      maximum_coefficient: null,
      minimum_coefficient: null,
      maximum_period_years: null,
      maximum_period_ends_on: null,
      not_table_bound: "free_election",
      unavailable_reason_key: null,
      class_label: null,
      legal_citations: [
        {
          text: "Ley 35/2006, art. 28",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
        },
        {
          text: "Ley 27/2014, art. 12",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
        {
          text: "Real Decreto 634/2015, art. 5",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a5",
        },
        {
          text: "Real Decreto 634/2015, art. 6",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a6",
        },
        {
          text: "Real Decreto 634/2015, art. 7",
          permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2015-7771#a7",
        },
        {
          text: "Ley 27/2014, DA 18",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava",
        },
        {
          text: "Ley 27/2014, art. 102",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a102",
        },
        {
          text: "Ley 27/2014, DA 17",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoseptima",
        },
        {
          text: "Ley 27/2014, art. 12 3 e",
          permalink:
            "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#a12",
        },
      ],
      legal_citations_complete: true,
    },
    annual: "0.00",
    forecasts: {},
    list: {
      asset_id: "impresora",
      name: "Impresora 3D",
      serial_number: "I3D-0907",
      asset_kind: "material",
      state: "in_service",
      in_service_date: "2026-09-01",
      method: "low_value_free",
      revision_number: 1,
      basis: {
        decimal: "250.00",
      },
      accumulated: {
        decimal: "0.00",
      },
      pending: {
        decimal: "250.00",
      },
      findings: {
        missing: 1,
        incomplete: 0,
        conflict: 0,
        stale: 0,
      },
      years: [2026],
      projected_years: [],
    },
    events: [
      {
        sequence: 1,
        recorded_at: "2026-01-15T09:30:00Z",
        kind: "revision",
        asset_id: "impresora",
        record_id:
          "b8bb0e27d52d1277a1c2f1d96970de75db557819ed4a1214ced8930c73e553f6",
        effect_date: "2026-09-01",
        origin: "ledger.actividad-asset.create",
        changes: [
          {
            field: "asset_kind",
            before: null,
            after: "material",
            before_key: null,
            after_key: null,
          },
          {
            field: "in_service_date",
            before: null,
            after: "2026-09-01",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.basis_amount",
            before: null,
            after: "250.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "basis.non_deductible_iva",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "residual_value",
            before: null,
            after: "0.00",
            before_key: null,
            after_key: null,
          },
          {
            field: "amortization.method",
            before: null,
            after: "low_value_free",
            before_key: null,
            after_key: null,
          },
          {
            field: "acquired_condition",
            before: null,
            after: "new",
            before_key: null,
            after_key: "ledger.actividad_asset.acquired_condition.new",
          },
          {
            field: "acquisition_shape",
            before: null,
            after: "primary_purchase",
            before_key: null,
            after_key:
              "ledger.actividad_asset.acquisition_shape.primary_purchase",
          },
          {
            field: "basis.stage",
            before: null,
            after: "business_allocated",
            before_key: null,
            after_key: "ledger.actividad_asset.basis_stage.business_allocated",
          },
          {
            field: "opening_history.status",
            before: null,
            after: "known",
            before_key: null,
            after_key: "ledger.actividad_asset.opening_history_status.known",
          },
        ],
        affects_calculation: true,
        claim: null,
      },
      {
        sequence: 2,
        recorded_at: "2026-01-20T10:05:00Z",
        kind: "descriptor",
        asset_id: "impresora",
        record_id: "descriptor:impresora:2",
        effect_date: null,
        origin: "ledger.actividad-asset.describe",
        changes: [
          {
            field: "name",
            before: null,
            after: "Impresora 3D",
            before_key: null,
            after_key: null,
          },
          {
            field: "serial_number",
            before: null,
            after: "I3D-0907",
            before_key: null,
            after_key: null,
          },
        ],
        affects_calculation: false,
        claim: null,
      },
    ],
    id: "impresora",
    disposal: {
      acquisition_value: {
        decimal: "250.00",
      },
      deducted: {
        decimal: "0.00",
      },
      minimum: {
        decimal: "0.00",
      },
      reduction: {
        decimal: "0.00",
      },
      excess: {
        decimal: "0.00",
      },
      net_value: {
        decimal: "250.00",
      },
      years: [
        {
          tax_year: 2026,
          claims: {
            decimal: "0",
          },
          deducted_through: {
            decimal: "0.00",
          },
          minimum_through: {
            decimal: "0.00",
          },
          reduction_through: {
            decimal: "0.00",
          },
        },
      ],
      findings: [
        {
          kind: "claim_gap",
          tax_year: 2026,
          effect_on_cost: null,
        },
        {
          kind: "no_minimum_authority",
          tax_year: 2026,
          effect_on_cost: null,
        },
      ],
    },
    revisions: [
      {
        revision: {
          asset_id: "impresora",
          revision_number: 1,
          supersedes_revision_id: null,
          acquisition: {
            observed_transaction_id:
              "638ebba7c3f5c123d6c7ccf26fa6a106c4aea8da8bf533cc9f821029185f87a5",
            observed_lineage_event_id: null,
            invoice_evidence_id:
              "70808083ecd40008919447dfbe40e47b791340b05f8dfecc35616b160280a674",
            evidence_fingerprint:
              "6ac41d0f4abd99db8b67abbbbefada0a5636d5434a7b7eeb6d588f15fbe265f2",
          },
          acquisition_shape: "primary_purchase",
          asset_kind: "material",
          basis: {
            stage: "business_allocated",
            basis_amount: {
              decimal: "250.00",
            },
            non_deductible_iva: {
              decimal: "0.00",
            },
            is_property: false,
            construction_cost: null,
            land_cost: null,
            ownership_mode: null,
            ownership_share: null,
            office_area: null,
            total_area: null,
            business_use_share: null,
            prior_allocation_provenance: "allocation booked in the ledger",
          },
          residual_value: {
            decimal: "0",
          },
          in_service_date: "2026-09-01",
          out_of_service_date: null,
          disposal: null,
          opening_history: {
            status: "known",
            accumulated_amount: {
              decimal: "0.00",
            },
            amortization_method: null,
            covered_through_tax_year: null,
          },
          acquired_condition: "new",
          building_construction_date: null,
          amortization: {
            regime: "normal",
            method: "low_value_free",
            authority_class_key: null,
            linear_coefficient: null,
            shift_hours_per_day: null,
            sum_of_digits_period_years: null,
            digit_order: null,
            approved_plan: null,
            useful_life: null,
            small_enterprise: null,
            low_value: {
              election_reference: "election recorded with the purchase",
              new_material_evidence_reference: "purchase invoice",
            },
            research_development_evidence_reference: null,
            charging_infrastructure: null,
            renewable_self_consumption: null,
            used_original_price: null,
          },
          vehicle_affectation: null,
        },
        revision_id:
          "b8bb0e27d52d1277a1c2f1d96970de75db557819ed4a1214ced8930c73e553f6",
      },
    ],
  },
];

/** What the registry admits per asset kind in the normal modality: its table classes. */
export const TABLE_GROUPS: Record<string, readonly TableGroup[]> = {
  material: [
    {
      class_key: "almacen-deposito",
      maximum_coefficient: {
        decimal: "0.07",
      },
      minimum_coefficient: {
        decimal: "0.03333333333333333333333333333",
      },
      maximum_period_years: {
        decimal: "30",
      },
      class_label: "Almacenes y depósitos (gaseosos, líquidos y sólidos)",
    },
    {
      class_key: "central-carbon",
      maximum_coefficient: {
        decimal: "0.04",
      },
      minimum_coefficient: {
        decimal: "0.02",
      },
      maximum_period_years: {
        decimal: "50",
      },
      class_label: "Centrales de carbón",
    },
    {
      class_key: "central-hidraulica",
      maximum_coefficient: {
        decimal: "0.02",
      },
      minimum_coefficient: {
        decimal: "0.01",
      },
      maximum_period_years: {
        decimal: "100",
      },
      class_label: "Centrales hidráulicas",
    },
    {
      class_key: "central-nuclear",
      maximum_coefficient: {
        decimal: "0.03",
      },
      minimum_coefficient: {
        decimal: "0.01666666666666666666666666667",
      },
      maximum_period_years: {
        decimal: "60",
      },
      class_label: "Centrales nucleares",
    },
    {
      class_key: "central-otra",
      maximum_coefficient: {
        decimal: "0.05",
      },
      minimum_coefficient: {
        decimal: "0.025",
      },
      maximum_period_years: {
        decimal: "40",
      },
      class_label: "Otras centrales",
    },
    {
      class_key: "central-renovable",
      maximum_coefficient: {
        decimal: "0.07",
      },
      minimum_coefficient: {
        decimal: "0.03333333333333333333333333333",
      },
      maximum_period_years: {
        decimal: "30",
      },
      class_label: "Centrales renovables",
    },
    {
      class_key: "cristaleria",
      maximum_coefficient: {
        decimal: "0.5",
      },
      minimum_coefficient: {
        decimal: "0.25",
      },
      maximum_period_years: {
        decimal: "4",
      },
      class_label: "Cristalería",
    },
    {
      class_key: "edificio-comercial-administrativo-servicios-vivienda",
      maximum_coefficient: {
        decimal: "0.02",
      },
      minimum_coefficient: {
        decimal: "0.01",
      },
      maximum_period_years: {
        decimal: "100",
      },
      class_label:
        "Edificios comerciales, administrativos, de servicios y viviendas",
    },
    {
      class_key: "edificio-industrial",
      maximum_coefficient: {
        decimal: "0.03",
      },
      minimum_coefficient: {
        decimal: "0.01470588235294117647058823529",
      },
      maximum_period_years: {
        decimal: "68",
      },
      class_label: "Edificios industriales",
    },
    {
      class_key: "enseres-otros",
      maximum_coefficient: {
        decimal: "0.15",
      },
      minimum_coefficient: {
        decimal: "0.07142857142857142857142857143",
      },
      maximum_period_years: {
        decimal: "14",
      },
      class_label: "Otros enseres",
    },
    {
      class_key: "equipo-electronico",
      maximum_coefficient: {
        decimal: "0.2",
      },
      minimum_coefficient: {
        decimal: "0.1",
      },
      maximum_period_years: {
        decimal: "10",
      },
      class_label: "Equipos electrónicos",
    },
    {
      class_key: "equipo-medico",
      maximum_coefficient: {
        decimal: "0.15",
      },
      minimum_coefficient: {
        decimal: "0.07142857142857142857142857143",
      },
      maximum_period_years: {
        decimal: "14",
      },
      class_label: "Equipos médicos y asimilados",
    },
    {
      class_key: "equipo-proceso-informacion",
      maximum_coefficient: {
        decimal: "0.25",
      },
      minimum_coefficient: {
        decimal: "0.125",
      },
      maximum_period_years: {
        decimal: "8",
      },
      class_label: "Equipos para procesos de información",
    },
    {
      class_key: "instalacion-cables",
      maximum_coefficient: {
        decimal: "0.07",
      },
      minimum_coefficient: {
        decimal: "0.03333333333333333333333333333",
      },
      maximum_period_years: {
        decimal: "30",
      },
      class_label: "Cables",
    },
    {
      class_key: "instalacion-resto",
      maximum_coefficient: {
        decimal: "0.1",
      },
      minimum_coefficient: {
        decimal: "0.05",
      },
      maximum_period_years: {
        decimal: "20",
      },
      class_label: "Resto instalaciones",
    },
    {
      class_key: "instalacion-subestacion-red",
      maximum_coefficient: {
        decimal: "0.05",
      },
      minimum_coefficient: {
        decimal: "0.025",
      },
      maximum_period_years: {
        decimal: "40",
      },
      class_label:
        "Subestaciones. Redes de transporte y distribución de energía",
    },
    {
      class_key: "lenceria",
      maximum_coefficient: {
        decimal: "0.25",
      },
      minimum_coefficient: {
        decimal: "0.125",
      },
      maximum_period_years: {
        decimal: "8",
      },
      class_label: "Lencería",
    },
    {
      class_key: "maquinaria",
      maximum_coefficient: {
        decimal: "0.12",
      },
      minimum_coefficient: {
        decimal: "0.05555555555555555555555555556",
      },
      maximum_period_years: {
        decimal: "18",
      },
      class_label: "Maquinaria",
    },
    {
      class_key: "mobiliario",
      maximum_coefficient: {
        decimal: "0.1",
      },
      minimum_coefficient: {
        decimal: "0.05",
      },
      maximum_period_years: {
        decimal: "20",
      },
      class_label: "Mobiliario",
    },
    {
      class_key: "molde-matriz-modelo",
      maximum_coefficient: {
        decimal: "0.33",
      },
      minimum_coefficient: {
        decimal: "0.1666666666666666666666666667",
      },
      maximum_period_years: {
        decimal: "6",
      },
      class_label: "Moldes, matrices y modelos",
    },
    {
      class_key: "obra-civil-general",
      maximum_coefficient: {
        decimal: "0.02",
      },
      minimum_coefficient: {
        decimal: "0.01",
      },
      maximum_period_years: {
        decimal: "100",
      },
      class_label: "Obra civil general",
    },
    {
      class_key: "obra-civil-infraestructuras-mineras",
      maximum_coefficient: {
        decimal: "0.07",
      },
      minimum_coefficient: {
        decimal: "0.03333333333333333333333333333",
      },
      maximum_period_years: {
        decimal: "30",
      },
      class_label: "Infraestructuras y obras mineras",
    },
    {
      class_key: "obra-civil-pavimentos",
      maximum_coefficient: {
        decimal: "0.06",
      },
      minimum_coefficient: {
        decimal: "0.02941176470588235294117647059",
      },
      maximum_period_years: {
        decimal: "34",
      },
      class_label: "Pavimentos",
    },
    {
      class_key: "otro-elemento",
      maximum_coefficient: {
        decimal: "0.1",
      },
      minimum_coefficient: {
        decimal: "0.05",
      },
      maximum_period_years: {
        decimal: "20",
      },
      class_label: "Otros elementos",
    },
    {
      class_key: "terreno-escombrera",
      maximum_coefficient: {
        decimal: "0.04",
      },
      minimum_coefficient: {
        decimal: "0.02",
      },
      maximum_period_years: {
        decimal: "50",
      },
      class_label: "Terrenos dedicados exclusivamente a escombreras",
    },
    {
      class_key: "transporte-autocamion",
      maximum_coefficient: {
        decimal: "0.2",
      },
      minimum_coefficient: {
        decimal: "0.1",
      },
      maximum_period_years: {
        decimal: "10",
      },
      class_label: "Autocamiones",
    },
    {
      class_key: "transporte-buque-aeronave",
      maximum_coefficient: {
        decimal: "0.1",
      },
      minimum_coefficient: {
        decimal: "0.05",
      },
      maximum_period_years: {
        decimal: "20",
      },
      class_label: "Buques, aeronaves",
    },
    {
      class_key: "transporte-externo",
      maximum_coefficient: {
        decimal: "0.16",
      },
      minimum_coefficient: {
        decimal: "0.07142857142857142857142857143",
      },
      maximum_period_years: {
        decimal: "14",
      },
      class_label: "Elementos de transporte externo",
    },
    {
      class_key: "transporte-interno",
      maximum_coefficient: {
        decimal: "0.1",
      },
      minimum_coefficient: {
        decimal: "0.05",
      },
      maximum_period_years: {
        decimal: "20",
      },
      class_label: "Elementos de transporte interno",
    },
    {
      class_key: "transporte-locomotora-vagon-traccion",
      maximum_coefficient: {
        decimal: "0.08",
      },
      minimum_coefficient: {
        decimal: "0.04",
      },
      maximum_period_years: {
        decimal: "25",
      },
      class_label: "Locomotoras, vagones y equipos de tracción",
    },
    {
      class_key: "util-herramienta",
      maximum_coefficient: {
        decimal: "0.25",
      },
      minimum_coefficient: {
        decimal: "0.125",
      },
      maximum_period_years: {
        decimal: "8",
      },
      class_label: "Útiles y herramientas",
    },
  ],
  intangible: [
    {
      class_key: "intangible-audiovisual",
      maximum_coefficient: {
        decimal: "0.33",
      },
      minimum_coefficient: {
        decimal: "0.1666666666666666666666666667",
      },
      maximum_period_years: {
        decimal: "6",
      },
      class_label:
        "Producciones cinematográficas, fonográficas, videos y series audiovisuales",
    },
    {
      class_key: "intangible-software",
      maximum_coefficient: {
        decimal: "0.33",
      },
      minimum_coefficient: {
        decimal: "0.1666666666666666666666666667",
      },
      maximum_period_years: {
        decimal: "6",
      },
      class_label: "Sistemas y programas informáticos",
    },
  ],
};

/** The methods the registry admits per asset kind in the normal modality. */
export const ADMITTED_METHODS: Record<string, readonly string[]> = {
  material: [
    "approved_plan",
    "constant_percentage",
    "linear",
    "low_value_free",
    "research_development_building",
    "research_development_free",
    "small_enterprise_employment_free",
    "sum_of_digits",
  ],
  intangible: [
    "approved_plan",
    "constant_percentage",
    "goodwill",
    "intangible_indefinite_life",
    "intangible_useful_life",
    "linear",
    "research_development_free",
    "sum_of_digits",
  ],
};
