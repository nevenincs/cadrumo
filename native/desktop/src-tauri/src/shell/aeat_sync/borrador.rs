//! Reads of the Modelo 100 borrador drafts the profile holds, and their
//! comparison with the saved calculation. Each runs one admitted read over
//! the held person's relay for exactly the profile the window names, and
//! answers the settled projection in the product's words once it is checked
//! to be the answer to the question asked: the profile, the kind of read, the
//! year and the language. Nothing here contacts AEAT, and what is read is
//! passed on and dropped. A draft is an observation of what AEAT printed, and
//! a comparison never stands for agreement: the product serves each side's
//! state and each box's own classification, and the host adds none.
use super::admitted::{Kind, admitted};
use super::{bare, held, invalid};
use crate::shell::relay::protocol;
use crate::shell::user_profile::ProfileHost;
use serde::Deserialize;
use serde_json::{Value, json};
use std::time::Duration;

/// Bounds a whole read, including admission and queueing, beyond following.
const READ_LIMIT: Duration = Duration::from_secs(140);
/// The longest unique prefix of a snapshot identity a view may name: the
/// identity is a hex-64 digest.
const SNAPSHOT_ID_LENGTH: std::ops::RangeInclusive<usize> = 1..=64;

/// The stored drafts a list asks for. Without one the product lists the
/// active drafts.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub(crate) enum State {
    Active,
    Superseded,
    Discarded,
    All,
}
impl State {
    fn token(self) -> &'static str {
        match self {
            Self::Active => "active",
            Self::Superseded => "superseded",
            Self::Discarded => "discarded",
            Self::All => "all",
        }
    }
}

/// Which stored drafts a read asks for.
#[derive(Clone, Debug, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub(crate) enum Selector {
    /// The stored drafts, newest first, in one lifecycle state.
    List { state: Option<State> },
    /// One draft, named by a unique prefix of its identity.
    View { snapshot_id: String },
    /// The active draft of one filing year, if there is one.
    Latest { filing_year: u16 },
}

/// The read of the drafts the window asks for. `Read` serves the full human
/// view, with the capture's provenance; `Query` serves the same drafts
/// without it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Reading {
    Read,
    Query,
}
impl Reading {
    fn definition(self) -> &'static str {
        match self {
            Self::Read => "live.borrador.100.read",
            Self::Query => "live.borrador.100.query",
        }
    }
}
/// The comparison with the saved calculation.
const COMPARE: &str = "live.borrador.100.compare";

impl Selector {
    /// The request's own members beyond the profile, or none where the
    /// selector is outside what the product accepts.
    fn members(&self) -> Option<Value> {
        match self {
            Self::List { state } => {
                let mut members = json!({"kind":"list"});
                if let Some(state) = state {
                    members["state"] = state.token().into();
                }
                Some(members)
            }
            Self::View { snapshot_id }
                if SNAPSHOT_ID_LENGTH.contains(&snapshot_id.len())
                    && snapshot_id
                        .bytes()
                        .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)) =>
            {
                Some(json!({"kind":"view","snapshot_id":snapshot_id}))
            }
            Self::Latest { filing_year } => {
                Some(json!({"kind":"latest","filing_year":filing_year}))
            }
            _ => None,
        }
    }
    /// Whether `projection` answers this selector for exactly `profile`: its
    /// kind, and the year or draft it was asked for.
    fn answered(&self, projection: &Value, profile: &str) -> bool {
        if projection["profile_id"] != profile {
            return false;
        }
        match self {
            Self::List { .. } => projection["kind"] == "list" && projection["rows"].is_array(),
            Self::View { snapshot_id } => {
                projection["kind"] == "view"
                    && projection["snapshot"]["snapshot_id"]
                        .as_str()
                        .is_some_and(|found| found.starts_with(snapshot_id.as_str()))
            }
            Self::Latest { filing_year } => {
                projection["kind"] == "latest" && projection["filing_year"] == *filing_year
            }
        }
    }
}

/// Whether `projection` is the comparison of `profile`'s `year`, worded in
/// `language`, with a status the product stated.
fn compared(projection: &Value, profile: &str, year: u16, language: &str) -> bool {
    projection["profile_id"] == profile
        && projection["filing_year"] == year
        && projection["language"] == language
        && projection["status"]["token"].is_string()
        && projection["rows"].is_array()
}

/// A failure the window may read: the closed code of a read, nothing else.
fn failed(code: &str) -> crate::shell::relay::Failure {
    bare(match code {
        "not_signed_in" => "not_signed_in",
        "refused" => "refused",
        _ => "unavailable",
    })
}

/// Runs the admitted read `definition` for `profile` with `payload`, which
/// carries the profile, and answers the projection `answered` accepts.
async fn run(
    host: &ProfileHost,
    profile: &str,
    definition: &'static str,
    payload: Value,
    answered: impl FnOnce(&Value) -> bool,
) -> crate::shell::relay::Result<Value> {
    if !matches!(admitted(definition), Some((_, Kind::Read))) {
        return Err(bare("unavailable"));
    }
    tokio::time::timeout(READ_LIMIT, async {
        let person = held(host, profile).await?;
        let projection = {
            let _serial = host.serial().await;
            host.run(&person, definition, payload, false).await
        }
        .map_err(|failure| failed(failure.code))?;
        if !answered(&projection) {
            return Err(protocol());
        }
        Ok(projection)
    })
    .await
    .unwrap_or_else(|_| Err(protocol()))
}

/// The stored drafts `selector` asks for, as `reading` serves them.
pub(super) async fn read(
    host: &ProfileHost,
    reading: Reading,
    profile: String,
    selector: Selector,
) -> crate::shell::relay::Result<Value> {
    let mut payload = selector.members().ok_or_else(invalid)?;
    payload["profile_id"] = profile.clone().into();
    run(
        host,
        &profile,
        reading.definition(),
        payload,
        |projection| selector.answered(projection, &profile),
    )
    .await
}

/// The year's newest readable draft beside the saved calculation, worded in
/// `language`.
pub(super) async fn compare(
    host: &ProfileHost,
    profile: String,
    filing_year: u16,
    language: String,
) -> crate::shell::relay::Result<Value> {
    if !crate::shell::language::supported(&language) {
        return Err(invalid());
    }
    let payload =
        json!({"profile_id":profile, "filing_year":filing_year, "output_language":language});
    run(host, &profile, COMPARE, payload, |projection| {
        compared(projection, &profile, filing_year, &language)
    })
    .await
}

#[cfg(test)]
mod tests {
    use super::*;

    const PROFILE: &str = "0b4f6c2e-8f0a-4a8e-9a43-5b1a6e0d7c11";

    fn selector(value: Value) -> Selector {
        serde_json::from_value(value).unwrap()
    }

    #[test]
    fn a_selector_asks_for_the_drafts_in_the_products_own_terms() {
        assert_eq!(
            selector(json!({"kind":"list","state":null})).members(),
            Some(json!({"kind":"list"}))
        );
        assert_eq!(
            selector(json!({"kind":"list","state":"all"})).members(),
            Some(json!({"kind":"list","state":"all"}))
        );
        assert_eq!(
            selector(json!({"kind":"view","snapshot_id":"ab12"})).members(),
            Some(json!({"kind":"view","snapshot_id":"ab12"}))
        );
        assert_eq!(
            selector(json!({"kind":"latest","filing_year":2025})).members(),
            Some(json!({"kind":"latest","filing_year":2025}))
        );
    }

    #[test]
    fn a_selector_outside_the_products_terms_is_refused() {
        for refused in [
            json!({"kind":"view","snapshot_id":""}),
            json!({"kind":"view","snapshot_id":"AB12"}),
            json!({"kind":"view","snapshot_id":"ab 12"}),
            json!({"kind":"view","snapshot_id":"g"}),
            json!({"kind":"view","snapshot_id":"a".repeat(65)}),
        ] {
            assert!(selector(refused.clone()).members().is_none(), "{refused}");
        }
        assert!(
            selector(json!({"kind":"view","snapshot_id":"a".repeat(64)}))
                .members()
                .is_some()
        );
        for year in [999, 2025, 10000] {
            assert_eq!(
                selector(json!({"kind":"latest","filing_year":year})).members(),
                Some(json!({"kind":"latest","filing_year":year}))
            );
        }
        for unread in [
            json!({"kind":"list","state":"everything"}),
            json!({"kind":"list","extra":1}),
            json!({"kind":"view"}),
            json!({"kind":"view","snapshot_id":"ab","filing_year":2025}),
            json!({"kind":"latest"}),
            json!({"kind":"latest","filing_year":-1}),
            json!({"kind":"rows"}),
        ] {
            assert!(
                serde_json::from_value::<Selector>(unread.clone()).is_err(),
                "{unread}"
            );
        }
    }

    #[test]
    fn a_read_is_answered_only_by_the_projection_of_its_own_question() {
        let list = selector(json!({"kind":"list"}));
        assert!(list.answered(
            &json!({"profile_id":PROFILE,"kind":"list","rows":[]}),
            PROFILE
        ));
        assert!(!list.answered(
            &json!({"profile_id":PROFILE,"kind":"latest","rows":[]}),
            PROFILE
        ));
        assert!(!list.answered(
            &json!({"profile_id":"another","kind":"list","rows":[]}),
            PROFILE
        ));
        assert!(!list.answered(&json!({"profile_id":PROFILE,"kind":"list"}), PROFILE));

        let view = selector(json!({"kind":"view","snapshot_id":"ab12"}));
        let shown =
            |id: &str| json!({"profile_id":PROFILE,"kind":"view","snapshot":{"snapshot_id":id}});
        assert!(view.answered(&shown("ab12cd"), PROFILE));
        assert!(!view.answered(&shown("cd12ab"), PROFILE));
        assert!(!view.answered(
            &json!({"profile_id":PROFILE,"kind":"view","snapshot":null}),
            PROFILE
        ));

        let latest = selector(json!({"kind":"latest","filing_year":2025}));
        assert!(latest.answered(
            &json!({"profile_id":PROFILE,"kind":"latest","filing_year":2025,"snapshot":null}),
            PROFILE
        ));
        assert!(!latest.answered(
            &json!({"profile_id":PROFILE,"kind":"latest","filing_year":2024}),
            PROFILE
        ));
        assert!(!latest.answered(
            &json!({"profile_id":PROFILE,"kind":"latest","filing_year":null}),
            PROFILE
        ));
    }

    #[test]
    fn a_comparison_answers_only_the_year_and_language_asked() {
        let served = json!({"profile_id":PROFILE,"filing_year":2025,"language":"hu",
            "status":{"token":"no_capture","words":"Words"},"rows":[]});
        assert!(compared(&served, PROFILE, 2025, "hu"));
        assert!(!compared(&served, "another", 2025, "hu"));
        assert!(!compared(&served, PROFILE, 2024, "hu"));
        assert!(!compared(&served, PROFILE, 2025, "en"));
        let mut statusless = served.clone();
        statusless["status"] = Value::Null;
        assert!(!compared(&statusless, PROFILE, 2025, "hu"));
        let mut rowless = served;
        rowless.as_object_mut().unwrap().remove("rows");
        assert!(!compared(&rowless, PROFILE, 2025, "hu"));
    }

    #[test]
    fn a_read_failure_reaches_the_window_as_a_closed_code_without_its_reason() {
        assert_eq!(failed("not_signed_in").code, "not_signed_in");
        assert_eq!(failed("refused").code, "refused");
        for other in [
            "unknown",
            "saved_unread",
            "conflict",
            "profile_mismatch",
            "",
        ] {
            assert_eq!(failed(other).code, "unavailable", "{other}");
        }
        assert!(failed("refused").reason.is_none());
    }

    #[test]
    fn the_reads_are_the_admitted_reads_of_the_product() {
        for definition in [
            Reading::Read.definition(),
            Reading::Query.definition(),
            COMPARE,
        ] {
            assert!(
                matches!(admitted(definition), Some((_, Kind::Read))),
                "{definition}"
            );
        }
    }
}
