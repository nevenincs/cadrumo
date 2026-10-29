//! The one closed table that reads how an admitted operation settled: its
//! terminal condition, effect and refusal code, and its result's typed
//! counts, as one of four outcomes. Codes stay here; the window is served
//! the outcome and a closed reason only.
use serde::Serialize;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

/// The refusal a live capture settles with when the AEAT session it read
/// through has ended: the run pauses for a new sign-in.
pub(crate) const SESSION_ENDED: &str = "REFUSED_APPLICATION_LIVE_AEAT_SESSION_ENDED";

/// Refusals that say the profile's AEAT access is not set up or not enough.
const NO_ACCESS: [&str; 5] = [
    "REFUSED_APPLICATION_LIVE_NIF_IVA_CERTIFICATE_REQUIRED",
    "REFUSED_AUTH_CERTIFICATE_SOURCE_NOT_FOUND",
    "REFUSED_AUTH_LOGIN_PRECONDITION",
    "REFUSED_AUTH_PROVIDER_NOT_CONFIGURED",
    "REFUSED_CLAVE_CREDENTIALS_INCOMPLETE",
];
/// Refusals that say something the read needs is not there now.
const UNAVAILABLE: [&str; 1] = ["REFUSED_BROWSER_NOT_READY"];

/// Why an item did not bring anything, as the window words it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum Reason {
    SessionEnded,
    NoAccess,
    Unavailable,
    Refused,
    Other,
}

/// How an item settled.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) enum Outcome {
    Brought,
    NothingFound,
    Failed(Reason),
    /// Not observed: it may have been brought. Never retried by the host.
    #[default]
    Unknown,
}

/// What a brought item added or found different, where its result says.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Counts {
    pub(crate) new: u64,
    pub(crate) changed: u64,
}

/// A refusal code as its closed reason.
pub(crate) fn reason(code: Option<&str>) -> Reason {
    match code {
        Some(SESSION_ENDED) => Reason::SessionEnded,
        Some(code) if NO_ACCESS.contains(&code) => Reason::NoAccess,
        Some(code) if UNAVAILABLE.contains(&code) => Reason::Unavailable,
        _ => Reason::Refused,
    }
}

/// How the terminal projection `p` settled before its result is read: a
/// success needs its result, anything else is decided here. A refusal or
/// failure that may have written something is unknown.
pub(crate) fn terminal(p: &Value) -> Option<Outcome> {
    if p["terminal_condition"] == "succeeded" {
        return None;
    }
    // A capture may end its session part way, after earlier parts were kept,
    // and one that may write reports that before it reads: only an ended
    // session that kept nothing is read again on resume. Either pauses the
    // run, which [`session_ended`] tells apart from the item's outcome.
    if p["effect"] != "none" {
        return Some(Outcome::Unknown);
    }
    if p["refusal_ref"] == SESSION_ENDED {
        return Some(Outcome::Failed(Reason::SessionEnded));
    }
    Some(match p["terminal_condition"].as_str() {
        Some("refused") => Outcome::Failed(reason(p["refusal_ref"].as_str())),
        Some("failed" | "cancelled" | "interrupted") => Outcome::Failed(Reason::Other),
        _ => Outcome::Unknown,
    })
}

/// Whether the terminal projection `p` settled because its AEAT session
/// ended: the run pauses there for a new sign-in, whatever the item's outcome.
pub(crate) fn session_ended(p: &Value) -> bool {
    p["terminal_condition"] != "succeeded" && p["refusal_ref"] == SESSION_ENDED
}

fn count(value: &Value) -> Option<u64> {
    value.as_u64()
}

/// The succeeded result `document` of `definition` as an outcome and its
/// counts. A document that does not read as its definition's result is
/// unknown: the capture ran, and what it kept was not observed.
pub(crate) fn succeeded(definition: &str, document: &Value) -> (Outcome, Counts) {
    let unknown = (Outcome::Unknown, Counts::default());
    let found = |any: bool| {
        if any {
            Outcome::Brought
        } else {
            Outcome::NothingFound
        }
    };
    match definition {
        "live.verify.nif-iva" | "live.verify.tgvi" => {
            // A verdict is what the check brings; an unknown verdict is a
            // check that got no answer.
            match document["verdict"].as_str() {
                Some("valid" | "invalid") => (Outcome::Brought, Counts::default()),
                Some("unknown") => (Outcome::Failed(Reason::Unavailable), Counts::default()),
                _ => unknown,
            }
        }
        "live.notifications.capture" => match count(&document["row_count"]) {
            Some(rows) => (found(rows > 0), Counts::default()),
            None => unknown,
        },
        "live.iva-wallet.history-capture" => {
            let (Some(captured), Some(calculated), Some(failed)) = (
                count(&document["captured_count"]),
                count(&document["calculation_observation_count"]),
                count(&document["failed_declaration_count"]),
            ) else {
                return unknown;
            };
            let outcome = if failed > 0 {
                Outcome::Failed(Reason::Other)
            } else {
                found(captured + calculated > 0)
            };
            (
                outcome,
                Counts {
                    new: captured,
                    changed: 0,
                },
            )
        }
        "live.filed-capture.bulk" => {
            let (Some(captured), Some(failed), Some(conflicts), Some(pairs)) = (
                count(&document["captured_count"]),
                count(&document["failed_count"]),
                count(&document["filing_evidence_conflict_count"]),
                document["pair_outcomes"].as_array(),
            ) else {
                return unknown;
            };
            // Rows read that the profile already held are found, not new.
            let rows: u64 = pairs
                .iter()
                .filter_map(|pair| count(&pair["row_count"]))
                .sum();
            let outcome = if failed > 0 {
                Outcome::Failed(Reason::Other)
            } else {
                found(captured > 0 || rows > 0)
            };
            (
                outcome,
                Counts {
                    new: captured,
                    changed: conflicts,
                },
            )
        }
        "live.filed-discover" => match discovered(document) {
            Some(pairs) => (found(!pairs.is_empty()), Counts::default()),
            None => unknown,
        },
        _ => unknown,
    }
}

/// The forms a discovery found, by year; none where the document does not
/// read as one.
pub(crate) fn discovered(document: &Value) -> Option<BTreeMap<u16, BTreeSet<String>>> {
    let mut found: BTreeMap<u16, BTreeSet<String>> = BTreeMap::new();
    for pair in document["pairs"].as_array()? {
        let year = u16::try_from(pair["ejercicio"].as_u64()?).ok()?;
        let form = pair["modelo"].as_str()?;
        if !(1..=8).contains(&form.len()) || !form.bytes().all(|b| b.is_ascii_alphanumeric()) {
            return None;
        }
        found.entry(year).or_default().insert(form.to_owned());
    }
    Some(found)
}

impl Outcome {
    /// The outcome as the window words it.
    pub(crate) fn word(self) -> &'static str {
        match self {
            Self::Brought => "brought",
            Self::NothingFound => "nothing_found",
            Self::Failed(_) => "failed",
            Self::Unknown => "unknown",
        }
    }
}

/// The worst of an area's outcomes: unknown outranks a failure, a failure
/// anything brought, and something brought nothing found.
pub(crate) fn worst(outcomes: impl IntoIterator<Item = Outcome>) -> Option<Outcome> {
    let rank = |outcome: &Outcome| match outcome {
        Outcome::NothingFound => 0,
        Outcome::Brought => 1,
        Outcome::Failed(_) => 2,
        Outcome::Unknown => 3,
    };
    outcomes.into_iter().max_by_key(rank)
}
