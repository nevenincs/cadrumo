//! The Modelo definitions the window may name: closed and owned by the host.
//! These are the `modelo.*` operations reached by `aeat app modelo`, which
//! reaches the whole shipped family, and by the TUI workbench, so the
//! desktop's surface stays at parity with both. Any other definition is
//! refused before it reaches the relay.
//!
//! Each one carries what the host needs to submit it without restating its
//! request: where its subject comes from, and whether its request names the
//! profile at all. Both are read from the registered contract by
//! `relay_contracts.py` and pinned by the tests below.
use super::super::settle::Settling;

/// What settling an admitted definition can mean for the profile's records.
/// No Modelo definition pauses for a review: the shared settle loop answers
/// one should a definition come to declare it, and the tests below then ask
/// for its kind here.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Kind {
    /// Declares no effect that changes records.
    Read,
    /// May change records: an outcome that was not observed is unknown.
    Write,
}

/// The form a definition's subject reference takes in its contract.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Subject {
    /// The signed-in profile.
    Profile,
    /// The value of one request field, outermost name first.
    Field(&'static [&'static str]),
    /// That field's value where the request sets it, the profile otherwise.
    FieldOrProfile(&'static [&'static str]),
    /// The work unit owning the stored record that field names. Only the
    /// store knows it, so the window names it from the form it read.
    StoredWorkUnit(&'static [&'static str]),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) struct Definition {
    pub(super) id: &'static str,
    pub(super) kind: Kind,
    pub(super) subject: Subject,
    /// Whether the request names the profile, which the host then fills.
    pub(super) profile: bool,
}
impl Definition {
    pub(super) fn mutation(self) -> bool {
        self.kind != Kind::Read
    }
    /// Whether its amounts travel only as a transient financial operand.
    pub(super) fn financial(self) -> bool {
        FINANCIAL.contains(&self.id)
    }
    pub(super) fn settling(self) -> Settling {
        Settling {
            id: self.id,
            mutation: self.mutation(),
            result_paths: &super::RESULT_PATH_KEYS,
        }
    }
}

use Kind::{Read, Write};
use Subject::{Field, FieldOrProfile, Profile, StoredWorkUnit};

const WORK_UNIT: Subject = Field(&["work_unit_id"]);
const BASELINE_WORK_UNIT: Subject = Field(&["baseline", "work_unit_id"]);
const CALCULATION: Subject = StoredWorkUnit(&["calculation_revision_id"]);
/// The request names the profile, which the host fills.
const NAMED: bool = true;
/// The request takes the profile from the session alone.
const SESSION: bool = false;

/// The definitions whose amounts travel only through the relay's financial
/// operand, never in a plain payload.
pub(super) const FINANCIAL: [&str; 2] = ["modelo.edit.apply", "modelo.edit.preflight"];

const ADMITTED: [(&str, Kind, Subject, bool); 78] = [
    ("modelo.036.query", Read, Profile, NAMED),
    ("modelo.036.read", Read, Profile, NAMED),
    ("modelo.036.record", Write, Profile, NAMED),
    ("modelo.aggregate", Write, Profile, NAMED),
    (
        "modelo.aggregate.capture_received_invoice_retencion",
        Write,
        Profile,
        NAMED,
    ),
    ("modelo.audit.export", Write, Profile, NAMED),
    ("modelo.audit.query", Read, Profile, NAMED),
    ("modelo.audit.read", Read, Profile, NAMED),
    ("modelo.bindings.list", Read, Profile, NAMED),
    ("modelo.bindings.resolve", Read, Profile, NAMED),
    ("modelo.bindings.resolve.typed", Read, Profile, NAMED),
    ("modelo.compare", Write, Profile, NAMED),
    ("modelo.declarations.list", Read, Profile, NAMED),
    ("modelo.edit.apply", Write, WORK_UNIT, NAMED),
    ("modelo.edit.apply_prerequisite", Read, WORK_UNIT, NAMED),
    ("modelo.edit.preflight", Read, WORK_UNIT, NAMED),
    ("modelo.edit.renew", Read, BASELINE_WORK_UNIT, NAMED),
    ("modelo.export", Write, CALCULATION, SESSION),
    ("modelo.filing_record.import", Write, Profile, NAMED),
    ("modelo.filing_record.list", Read, Profile, NAMED),
    ("modelo.filing_record.view", Read, Profile, NAMED),
    ("modelo.history", Read, Profile, NAMED),
    ("modelo.history.timeline", Read, Profile, NAMED),
    ("modelo.iva-wallet.balance", Read, Profile, NAMED),
    ("modelo.iva-wallet.correct", Write, Profile, NAMED),
    ("modelo.iva-wallet.override", Write, Profile, NAMED),
    ("modelo.iva-wallet.seed", Write, Profile, NAMED),
    ("modelo.m145.create", Write, Profile, NAMED),
    ("modelo.m145.export", Write, Profile, NAMED),
    ("modelo.m145.mark_delivered_to_payer", Write, Profile, NAMED),
    ("modelo.m145.mark_locally_completed", Write, Profile, NAMED),
    ("modelo.m145.validate", Read, Profile, NAMED),
    ("modelo.m360_solicitud", Write, Profile, NAMED),
    ("modelo.observation.local", Write, Profile, NAMED),
    ("modelo.project", Write, Profile, NAMED),
    ("modelo.quickfile", Write, Profile, NAMED),
    ("modelo.readiness", Read, Profile, NAMED),
    ("modelo.readiness.summary", Read, Profile, NAMED),
    ("modelo.reconcile.export-xlsx", Write, Profile, NAMED),
    ("modelo.reconcile.import", Write, Profile, NAMED),
    ("modelo.reconcile.list", Read, Profile, NAMED),
    ("modelo.reconcile.pull", Write, Profile, NAMED),
    ("modelo.requires", Read, Profile, NAMED),
    ("modelo.review_package.build", Write, CALCULATION, NAMED),
    ("modelo.review_package.counter_sign", Write, Profile, NAMED),
    ("modelo.review_package.decrypt", Write, Profile, NAMED),
    (
        "modelo.review_package.encrypt_feedback",
        Write,
        Profile,
        NAMED,
    ),
    (
        "modelo.review_package.encrypt_for_recipient",
        Write,
        Profile,
        NAMED,
    ),
    (
        "modelo.review_package.import_feedback",
        Write,
        Profile,
        NAMED,
    ),
    ("modelo.review_package.sign", Write, Profile, NAMED),
    ("modelo.spreadsheet.export", Write, Profile, NAMED),
    ("modelo.verification_report.list", Read, Profile, NAMED),
    ("modelo.verification_report.view", Read, Profile, NAMED),
    (
        "modelo.work.amend",
        Write,
        StoredWorkUnit(&["baseline", "from_filing_record_id"]),
        SESSION,
    ),
    ("modelo.work.amendment_context", Read, Profile, NAMED),
    ("modelo.work.calculate", Write, WORK_UNIT, SESSION),
    ("modelo.work.casilla_help", Read, WORK_UNIT, NAMED),
    ("modelo.work.compare_taxation", Read, Profile, NAMED),
    ("modelo.work.create", Write, Profile, NAMED),
    ("modelo.work.dependencies", Read, Profile, NAMED),
    ("modelo.work.discard", Write, BASELINE_WORK_UNIT, SESSION),
    (
        "modelo.work.file",
        Write,
        StoredWorkUnit(&["approval", "calculation_revision_id"]),
        SESSION,
    ),
    ("modelo.work.filing_record", Read, Profile, NAMED),
    ("modelo.work.form", Read, WORK_UNIT, NAMED),
    ("modelo.work.history", Read, WORK_UNIT, NAMED),
    ("modelo.work.list", Read, Profile, NAMED),
    (
        "modelo.work.m303_attestation",
        Write,
        FieldOrProfile(&["work_unit_id"]),
        NAMED,
    ),
    ("modelo.work.metadata", Read, Profile, NAMED),
    (
        "modelo.work.preview_maritime_exemption",
        Read,
        Profile,
        NAMED,
    ),
    ("modelo.work.rename", Write, WORK_UNIT, SESSION),
    ("modelo.work.report_verify", Read, Profile, NAMED),
    ("modelo.work.review", Read, WORK_UNIT, NAMED),
    ("modelo.work.revision", Read, Profile, NAMED),
    ("modelo.work.revision_snapshot", Read, CALCULATION, NAMED),
    ("modelo.work.revisions", Read, Profile, NAMED),
    ("modelo.work.verify", Write, CALCULATION, SESSION),
    (
        "modelo.work.wizard_attempt",
        Write,
        Field(&["calculation", "work_unit_id"]),
        NAMED,
    ),
    ("modelo.work.wizard_context", Read, WORK_UNIT, NAMED),
];

/// The admitted definition named `id`, if the window may name it.
pub(super) fn admitted(id: &str) -> Option<Definition> {
    ADMITTED
        .binary_search_by(|(admitted, ..)| admitted.cmp(&id))
        .ok()
        .map(|at| {
            let (id, kind, subject, profile) = ADMITTED[at];
            Definition {
                id,
                kind,
                subject,
                profile,
            }
        })
}

#[cfg(test)]
pub(super) mod tests {
    use super::*;
    use serde_json::Value;

    /// The shipped manifest's Modelo family, its request fields and the
    /// relay's bounds, produced by `relay_contracts.py` and checked against
    /// their sources by its `--check` before these tests run.
    pub(in super::super) fn contracts() -> Value {
        serde_json::from_str(include_str!("relay_contracts.json")).unwrap()
    }

    fn subject_facts(subject: Subject) -> Value {
        let (kind, path): (&str, &[&str]) = match subject {
            Profile => ("profile", &[]),
            Field(path) => ("payload_field", path),
            FieldOrProfile(path) => ("payload_field_or_profile", path),
            StoredWorkUnit(path) => ("stored_work_unit", path),
        };
        serde_json::json!({"kind": kind, "path": path})
    }

    #[test]
    fn the_admitted_list_is_the_modelo_family_of_the_shipped_manifest() {
        let contracts = contracts();
        let shipped = contracts["operations"].as_object().unwrap();
        let admitted: Vec<&str> = ADMITTED.iter().map(|(id, ..)| *id).collect();
        let mut sorted = admitted.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(admitted, sorted, "the list is sorted and has no repeat");
        assert!(admitted.iter().all(|id| id.starts_with("modelo.")));
        let missing: Vec<_> = admitted
            .iter()
            .filter(|id| !shipped.contains_key(**id))
            .collect();
        assert!(missing.is_empty(), "admitted but not shipped: {missing:?}");
        let unadmitted: Vec<_> = shipped
            .keys()
            .filter(|id| !admitted.contains(&id.as_str()))
            .collect();
        assert!(
            unadmitted.is_empty(),
            "shipped but neither admitted nor refused here: {unadmitted:?}"
        );
        for id in admitted {
            let definition = super::admitted(id).unwrap();
            let facts = &shipped[id];
            assert!(
                facts["review"] != true,
                "{id} pauses for a review: give it a review kind"
            );
            let expected = if facts["may_write"] == true {
                Write
            } else {
                Read
            };
            assert_eq!(definition.kind, expected, "{id}");
            assert_eq!(subject_facts(definition.subject), facts["subject"], "{id}");
            assert_eq!(
                definition.profile,
                facts["profile_field"] == true,
                "{id} names the profile"
            );
            assert_eq!(
                definition.financial(),
                facts["financial"] == true,
                "{id} takes a financial operand"
            );
        }
    }

    #[test]
    fn only_an_admitted_definition_is_found() {
        let found = admitted("modelo.work.calculate").unwrap();
        assert_eq!(found.kind, Write);
        assert!(found.mutation());
        assert!(!found.profile);
        assert!(!admitted("modelo.work.form").unwrap().mutation());
        assert!(admitted("modelo.edit.apply").unwrap().financial());
        assert!(!admitted("modelo.work.form").unwrap().financial());
        for refused in [
            "",
            "modelo",
            "modelo.work.form ",
            "ledger.list",
            "modelo.work.submit",
            "auth.local-read",
        ] {
            assert!(admitted(refused).is_none(), "{refused:?}");
        }
    }

    #[test]
    fn the_host_stays_within_the_relays_request_bounds() {
        let relay = &contracts()["relay"];
        assert_eq!(
            relay["request_line_limit"].as_u64(),
            Some(crate::agent::person::REQUEST_LIMIT as u64 + 1),
            "the line limit counts its newline"
        );
    }
}
