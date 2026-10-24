//! The ledger definitions the window may name: closed and owned by the host.
//! These are the `ledger.*` operations reached by `aeat app ledger` and by
//! the TUI ledger workspace. Any other definition is refused before it
//! reaches the relay.

/// What settling an admitted definition can mean for the profile's records.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Kind {
    /// Declares no effect that changes records.
    Read,
    /// May change records: an outcome that was not observed is unknown.
    Write,
    /// May change records, after the person answers its review.
    Review,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) struct Definition {
    pub(super) id: &'static str,
    pub(super) kind: Kind,
}
impl Definition {
    pub(super) fn mutation(self) -> bool {
        self.kind != Kind::Read
    }
}

use Kind::{Read, Review, Write};

const ADMITTED: [(&str, Kind); 87] = [
    ("ledger.actividad-asset.claim", Write),
    ("ledger.actividad-asset.correct", Write),
    ("ledger.actividad-asset.create", Write),
    ("ledger.actividad-asset.filing-handoff", Read),
    ("ledger.actividad-asset.forecast", Read),
    ("ledger.actividad-asset.inspect", Read),
    ("ledger.add", Write),
    ("ledger.allocate", Write),
    ("ledger.archive", Write),
    ("ledger.attach", Write),
    ("ledger.bienes_inversion.declare", Write),
    ("ledger.bienes_inversion.list", Write),
    ("ledger.check", Read),
    ("ledger.classify.bulk", Write),
    ("ledger.classify.iva-derive", Write),
    ("ledger.classify.review", Review),
    ("ledger.classify.single", Write),
    ("ledger.counterparty", Write),
    ("ledger.detach", Write),
    ("ledger.evidence.add", Write),
    ("ledger.evidence.attachment_queue", Read),
    ("ledger.evidence.attachment_view", Read),
    ("ledger.evidence.batch", Write),
    ("ledger.evidence.confirm", Write),
    ("ledger.evidence.consent.list", Read),
    ("ledger.evidence.extract", Write),
    ("ledger.evidence.list", Read),
    ("ledger.evidence.query", Read),
    ("ledger.evidence.reader-readiness", Read),
    ("ledger.evidence.remove", Write),
    ("ledger.evidence.review.list", Read),
    ("ledger.evidence.review.summary", Read),
    ("ledger.evidence.review.view", Read),
    ("ledger.evidence.update", Write),
    ("ledger.evidence.view", Read),
    ("ledger.exclude", Write),
    ("ledger.export", Write),
    ("ledger.history", Read),
    ("ledger.history.typed", Read),
    ("ledger.import", Write),
    ("ledger.inventory.closing-authority.record", Write),
    ("ledger.inventory.create", Write),
    ("ledger.inventory.list", Write),
    ("ledger.inventory.movement.add", Write),
    ("ledger.inventory.valuation.preview", Write),
    ("ledger.invoice.add", Write),
    ("ledger.invoice.import", Write),
    ("ledger.invoice.list", Read),
    ("ledger.invoice.remove", Write),
    ("ledger.invoice.update", Write),
    ("ledger.invoice.view", Read),
    ("ledger.invoice.wizard", Write),
    ("ledger.link", Write),
    ("ledger.list", Read),
    ("ledger.llm-diagnostics", Read),
    ("ledger.merge", Write),
    ("ledger.own_account", Write),
    ("ledger.participation", Read),
    ("ledger.participation.rebuild", Write),
    ("ledger.preflight", Read),
    ("ledger.prorrata.declare_sector", Write),
    ("ledger.prorrata.elect_especial", Write),
    ("ledger.prorrata.elect_general", Write),
    ("ledger.prorrata.list", Write),
    ("ledger.prorrata.revoke_especial", Write),
    ("ledger.prorrata.seed", Write),
    ("ledger.prorrata.seed_sector", Write),
    ("ledger.prorrata.settle_sector", Write),
    ("ledger.ratios.eligible", Read),
    ("ledger.ratios.list", Read),
    ("ledger.ratios.set", Write),
    ("ledger.ratios.unset", Write),
    ("ledger.ratios.validate", Read),
    ("ledger.remove", Write),
    ("ledger.reset", Write),
    ("ledger.restore", Write),
    ("ledger.review", Read),
    ("ledger.rule.add", Write),
    ("ledger.rule.apply", Write),
    ("ledger.rule.list", Read),
    ("ledger.split.manual", Write),
    ("ledger.split.review", Review),
    ("ledger.stash", Write),
    ("ledger.status", Read),
    ("ledger.track", Read),
    ("ledger.update", Write),
    ("ledger.view", Read),
];

/// The admitted definition named `id`, if the window may name it.
pub(super) fn admitted(id: &str) -> Option<Definition> {
    ADMITTED
        .binary_search_by(|(admitted, _)| admitted.cmp(&id))
        .ok()
        .map(|at| Definition {
            id: ADMITTED[at].0,
            kind: ADMITTED[at].1,
        })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    /// The shipped manifest's ledger family and the relay's bounds, produced
    /// by `relay_contracts.py` and checked against their sources by its
    /// `--check` before these tests run.
    fn contracts() -> Value {
        serde_json::from_str(include_str!("relay_contracts.json")).unwrap()
    }

    #[test]
    fn the_admitted_list_is_the_ledger_family_of_the_shipped_manifest() {
        let contracts = contracts();
        let shipped = contracts["operations"].as_object().unwrap();
        let admitted: Vec<&str> = ADMITTED.iter().map(|(id, _)| *id).collect();
        let mut sorted = admitted.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(admitted, sorted, "the list is sorted and has no repeat");
        assert!(admitted.iter().all(|id| id.starts_with("ledger.")));
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
        for (id, kind) in ADMITTED {
            let facts = &shipped[id];
            let expected = match (facts["review"] == true, facts["may_write"] == true) {
                (true, true) => Review,
                (false, true) => Write,
                (false, false) => Read,
                (true, false) => panic!("{id} pauses for a review but writes nothing"),
            };
            assert_eq!(kind, expected, "{id}");
        }
    }

    #[test]
    fn only_an_admitted_definition_is_found() {
        let found = admitted("ledger.classify.review").unwrap();
        assert_eq!(found.kind, Review);
        assert!(found.mutation());
        assert!(!admitted("ledger.list").unwrap().mutation());
        for refused in [
            "",
            "ledger",
            "ledger.list ",
            "user-profile.view",
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
