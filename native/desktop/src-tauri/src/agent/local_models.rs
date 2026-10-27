//! The models the person added by name to a local lane's model list, the model
//! the person selected to read documents with, and the catalogue's local lanes,
//! read from and changed through the agent service and parsed into the closed
//! snapshot the window shows. A lane's recommended models are the catalogue's and
//! never cross here. A value outside the contract is a protocol failure, never
//! passed on.

use serde::Serialize;
use serde_json::Value;

/// A model id is 1 to 512 characters, none a C0 control or DEL, as the
/// agent's catalogues carry it.
const MODEL_LIMIT: usize = 512;
/// The most models the service keeps on the lists.
const MODELS_LIMIT: usize = 64;
/// The most local lanes a snapshot names.
const LANES_LIMIT: usize = 64;

/// One lane and one of its models: added to the lane's list, or selected to
/// read documents with.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ListedModel {
    pub lane: String,
    pub model: String,
}

/// Every added model and the selected reading model with the guard a change
/// sends back, or a record nobody can read, which lists and selects no model
/// and carries the guard of its reset. Either names the catalogue's local
/// lanes, whose models the picker offers from their lists.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum LocalModels {
    Readable {
        models: Vec<ListedModel>,
        reading: Option<ListedModel>,
        local_lanes: Vec<String>,
        revision: String,
    },
    Unreadable {
        local_lanes: Vec<String>,
        revision: String,
    },
}

impl LocalModels {
    /// The models added to `lane`'s list; none when the record is unreadable.
    pub fn added_to(&self, lane: &str) -> impl Iterator<Item = &str> {
        let models: &[ListedModel] = match self {
            Self::Readable { models, .. } => models,
            Self::Unreadable { .. } => &[],
        };
        models
            .iter()
            .filter(move |entry| entry.lane == lane)
            .map(|entry| entry.model.as_str())
    }
}

/// Why the read gave no snapshot, as the stable code the column words.
pub fn refusal(answer: &Value) -> Option<&'static str> {
    let refused = answer["kind"] == "refused"
        || answer
            .as_object()
            .is_some_and(|object| object.len() == 1 && object.contains_key("code"));
    if !refused {
        return None;
    }
    Some(match answer["code"].as_str() {
        Some("busy") => "agent_service_busy",
        Some("signed_out" | "not_signed_in" | "profile_locked") => "agent_signed_out",
        Some("service_stopping" | "catalog_unavailable" | "runtime_unavailable") => {
            "agent_service_not_ready"
        }
        _ => "agent_service_failed",
    })
}

/// Why a change gave no snapshot, as the stable code the window words: the
/// service's own reason the list was not changed, or what a read refusal
/// crosses as.
pub fn change_refusal(answer: &Value) -> Option<&'static str> {
    let crossed = refusal(answer)?;
    Some(match answer["code"].as_str() {
        Some("model_list_full") => "agent_local_models_full",
        Some("revision_conflict") => "agent_local_models_revision_conflict",
        Some("committed_readback_failed") => "agent_local_models_committed_readback_failed",
        Some("catalog_unavailable") => "agent_local_models_catalog_unavailable",
        Some("unknown") => "agent_local_models_unknown",
        _ => crossed,
    })
}

/// The snapshot in `answer`, or `None` when it breaks the contract.
pub fn parse(answer: &Value) -> Option<LocalModels> {
    let object = answer.as_object()?;
    if object.len() != 5 {
        return None;
    }
    let models = object.get("models")?.as_array()?;
    let reading = object.get("reading")?;
    let revision = object
        .get("revision")?
        .as_str()
        .filter(|text| is_revision(text))?
        .to_owned();
    let local_lanes = lanes(object.get("local_lanes")?)?;
    if object.get("unreadable")?.as_bool()? {
        return (models.is_empty() && reading.is_null()).then_some(LocalModels::Unreadable {
            local_lanes,
            revision,
        });
    }
    let reading = if reading.is_null() {
        None
    } else {
        Some(listed(reading)?)
    };
    if models.len() > MODELS_LIMIT {
        return None;
    }
    let models = models.iter().map(listed).collect::<Option<Vec<_>>>()?;
    let mut pairs: Vec<(&str, &str)> = models
        .iter()
        .map(|entry| (entry.lane.as_str(), entry.model.as_str()))
        .collect();
    pairs.sort_unstable();
    pairs.dedup();
    if pairs.len() != models.len() {
        return None;
    }
    Some(LocalModels::Readable {
        models,
        reading,
        local_lanes,
        revision,
    })
}

fn lanes(value: &Value) -> Option<Vec<String>> {
    let held = value.as_array()?;
    if held.len() > LANES_LIMIT {
        return None;
    }
    let lanes = held
        .iter()
        .map(|lane| {
            lane.as_str()
                .filter(|text| is_lane(text))
                .map(str::to_owned)
        })
        .collect::<Option<Vec<_>>>()?;
    let mut unique = lanes.clone();
    unique.sort_unstable();
    unique.dedup();
    (unique.len() == lanes.len()).then_some(lanes)
}

fn listed(entry: &Value) -> Option<ListedModel> {
    let object = entry.as_object()?;
    if object.len() != 2 {
        return None;
    }
    let lane = object.get("lane")?.as_str().filter(|text| is_lane(text))?;
    let model = object
        .get("model")?
        .as_str()
        .filter(|text| is_model(text))?;
    Some(ListedModel {
        lane: lane.to_owned(),
        model: model.to_owned(),
    })
}

pub fn is_revision(text: &str) -> bool {
    text.len() == 64
        && text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

pub fn is_lane(text: &str) -> bool {
    crate::shell::provider_settings::wire::is_provider_id(text)
}

pub fn is_model(text: &str) -> bool {
    (1..=MODEL_LIMIT).contains(&text.chars().count())
        && !text.chars().any(|c| c <= '\u{1f}' || c == '\u{7f}')
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn revision() -> String {
        "a".repeat(64)
    }

    fn entry(lane: &str, model: &str) -> ListedModel {
        ListedModel {
            lane: lane.to_owned(),
            model: model.to_owned(),
        }
    }

    fn local() -> Vec<String> {
        vec!["local_api".to_owned()]
    }

    #[test]
    fn a_readable_answer_becomes_every_added_model_in_order() {
        let answer = json!({
            "unreadable": false,
            "models": [
                {"lane": "local_api", "model": "synthetic-vision:1"},
                {"lane": "local_api", "model": "synthetic-text:1"},
                {"lane": "spare_api", "model": "synthetic-text:1"},
            ],
            "reading": {"lane": "keyed_api", "model": "synthetic-hosted:1"},
            "local_lanes": ["local_api"],
            "revision": revision(),
        });
        let parsed = parse(&answer).unwrap();
        assert_eq!(
            parsed,
            LocalModels::Readable {
                models: vec![
                    entry("local_api", "synthetic-vision:1"),
                    entry("local_api", "synthetic-text:1"),
                    entry("spare_api", "synthetic-text:1"),
                ],
                reading: Some(entry("keyed_api", "synthetic-hosted:1")),
                local_lanes: local(),
                revision: revision(),
            }
        );
        assert_eq!(
            parsed.added_to("local_api").collect::<Vec<_>>(),
            ["synthetic-vision:1", "synthetic-text:1"]
        );
        assert_eq!(refusal(&answer), None);
        let empty = json!({
            "unreadable": false, "models": [], "reading": null, "local_lanes": [], "revision": revision(),
        });
        assert_eq!(
            parse(&empty),
            Some(LocalModels::Readable {
                models: vec![],
                reading: None,
                local_lanes: vec![],
                revision: revision()
            })
        );
    }

    #[test]
    fn an_unreadable_record_lists_no_model_and_keeps_its_reset_guard() {
        let answer = json!({
            "unreadable": true, "models": [], "reading": null, "local_lanes": ["local_api"], "revision": revision(),
        });
        let parsed = parse(&answer).unwrap();
        assert_eq!(
            parsed,
            LocalModels::Unreadable {
                local_lanes: local(),
                revision: revision()
            }
        );
        assert_eq!(parsed.added_to("local_api").count(), 0);
    }

    #[test]
    fn an_answer_outside_the_contract_is_refused() {
        let model = |lane: &str, model: Value| json!({"lane": lane, "model": model});
        let many: Vec<Value> = (0..65)
            .map(|index| model("local_api", json!(format!("m{index}"))))
            .collect();
        let snapshot = |unreadable: bool, models: Value, reading: Value, lanes: Value| {
            json!({
                "unreadable": unreadable,
                "models": models,
                "reading": reading,
                "local_lanes": lanes,
                "revision": revision(),
            })
        };
        let none = || json!([]);
        let lanes = || json!(["local_api"]);
        let many_lanes: Vec<Value> = (0..65)
            .map(|index| json!(format!("lane_{index}")))
            .collect();
        let mut extra = snapshot(false, none(), Value::Null, lanes());
        extra["extra"] = json!(1);
        let mut missing_reading = snapshot(false, none(), Value::Null, lanes());
        missing_reading.as_object_mut().unwrap().remove("reading");
        let mut null_revision = snapshot(false, none(), Value::Null, lanes());
        null_revision["revision"] = Value::Null;
        for answer in [
            null_revision,
            snapshot(
                false,
                json!([model("Local", json!("m"))]),
                Value::Null,
                lanes(),
            ),
            snapshot(
                false,
                json!([model("local_api", json!("tab\there"))]),
                Value::Null,
                lanes(),
            ),
            snapshot(
                false,
                json!([model("local_api", json!("m".repeat(513)))]),
                Value::Null,
                lanes(),
            ),
            snapshot(
                false,
                json!([model("local_api", json!(""))]),
                Value::Null,
                lanes(),
            ),
            snapshot(
                false,
                json!([model("local_api", json!(null))]),
                Value::Null,
                lanes(),
            ),
            snapshot(
                false,
                json!([
                    model("local_api", json!("m")),
                    model("local_api", json!("m"))
                ]),
                Value::Null,
                lanes(),
            ),
            snapshot(
                true,
                json!([model("local_api", json!("m"))]),
                Value::Null,
                lanes(),
            ),
            snapshot(true, none(), model("local_api", json!("m")), lanes()),
            snapshot(false, none(), model("local_api", json!("")), lanes()),
            snapshot(false, none(), json!("local_api"), lanes()),
            snapshot(false, none(), Value::Null, json!(["Local"])),
            snapshot(
                false,
                none(),
                Value::Null,
                json!(["local_api", "local_api"]),
            ),
            snapshot(false, none(), Value::Null, Value::Null),
            snapshot(false, none(), Value::Null, json!(many_lanes)),
            extra,
            missing_reading,
            snapshot(
                false,
                json!([{"lane": "local_api", "model": "m", "role": "x"}]),
                Value::Null,
                lanes(),
            ),
            snapshot(false, json!(many), Value::Null, lanes()),
        ] {
            assert_eq!(parse(&answer), None, "{answer}");
        }
    }

    #[test]
    fn a_model_id_is_any_512_characters_without_a_control() {
        let longest = "m".repeat(512);
        let widest = "é".repeat(512);
        for accepted in [
            "synthetic-vision:1",
            "has space",
            "ñandú/modelo",
            &longest,
            &widest,
        ] {
            assert!(is_model(accepted), "{accepted}");
        }
        let longer = "m".repeat(513);
        for refused in ["", "line\nbreak", "nul\u{0}", "del\u{7f}", &longer] {
            assert!(!is_model(refused), "{refused:?}");
        }
    }

    #[test]
    fn a_change_refusal_keeps_the_services_reason_the_list_was_not_changed() {
        for (code, expected) in [
            ("model_list_full", "agent_local_models_full"),
            ("revision_conflict", "agent_local_models_revision_conflict"),
            (
                "committed_readback_failed",
                "agent_local_models_committed_readback_failed",
            ),
            (
                "catalog_unavailable",
                "agent_local_models_catalog_unavailable",
            ),
            ("unknown", "agent_local_models_unknown"),
            ("busy", "agent_service_busy"),
            ("profile_locked", "agent_signed_out"),
            ("service_stopping", "agent_service_not_ready"),
        ] {
            assert_eq!(change_refusal(&json!({"code": code})), Some(expected));
            assert_eq!(
                change_refusal(&json!({"kind": "refused", "code": code})),
                Some(expected)
            );
        }
        let snapshot = json!({
            "unreadable": false, "models": [], "reading": null, "local_lanes": [], "revision": revision(),
        });
        assert_eq!(change_refusal(&snapshot), None);
    }

    #[test]
    fn a_refusal_crosses_as_its_column_code() {
        for (code, expected) in [
            ("busy", "agent_service_busy"),
            ("signed_out", "agent_signed_out"),
            ("not_signed_in", "agent_signed_out"),
            ("profile_locked", "agent_signed_out"),
            ("service_stopping", "agent_service_not_ready"),
            ("unknown", "agent_service_failed"),
        ] {
            assert_eq!(
                refusal(&json!({"kind": "refused", "code": code})),
                Some(expected)
            );
            assert_eq!(refusal(&json!({"code": code})), Some(expected));
        }
    }
}
