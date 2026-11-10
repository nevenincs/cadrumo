//! The models the person added by name to a local lane's model list, the model
//! the person selected to read documents with, and the catalogue's local lanes,
//! read from and changed through the agent service and parsed into the closed
//! snapshot the window shows. A lane's recommended models are the catalogue's and
//! never cross here. A value outside the contract is a protocol failure, never
//! passed on.
//!
//! The same record holds the local engine and its placement. A readable setting is
//! handed on to the runtime manager's local engine selection record, which tells the
//! manager which engine's server to run; the manager owns that record's format.

use cadrumo_application::provisioning::local_ai::{LocalEngine, Placement, package_default_engine};
use serde::Serialize;
use serde_json::Value;
use std::path::Path;

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

/// The local engine and placement with the guard a change sends back, or a record
/// nobody can read, which names neither and carries the guard of its reset. Either
/// carries the engines and placements the service offers, which do not depend on the
/// record being readable.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum LocalEngineSetting {
    Readable {
        engine: LocalEngine,
        placement: Placement,
        choices: Choices,
        revision: String,
        /// Whether the person stored this setting. An unchosen one is the defaults the
        /// package derives, which the window shows as they are and which the runtime
        /// manager must never keep as a choice.
        #[serde(skip)]
        chosen: bool,
    },
    Unreadable {
        choices: Choices,
        revision: String,
    },
}

/// The engines and the placements the service offers, each in its order.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Choices {
    pub engine: Vec<LocalEngine>,
    pub placement: Vec<Placement>,
}

/// What the runtime manager's selection record is made to hold for a setting.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RecordSync {
    /// The person's choice, stored unless the record already holds it.
    Store(LocalEngine, Placement),
    /// No choice: the record is removed, so the manager runs the package's defaults.
    Clear,
    /// A setting nobody can read says nothing about the choice: the record is left alone.
    Leave,
}

impl LocalEngineSetting {
    /// What the runtime manager's selection record is made to hold for this setting.
    pub fn record_sync(&self) -> RecordSync {
        match self {
            Self::Readable {
                engine,
                placement,
                chosen: true,
                ..
            } => RecordSync::Store(*engine, *placement),
            Self::Readable { chosen: false, .. } => RecordSync::Clear,
            Self::Unreadable { .. } => RecordSync::Leave,
        }
    }
}

/// The local engine setting in `answer`, or `None` when it breaks the contract: exactly
/// the six members, a revision digest, an engine and placement named exactly when the
/// record is readable, a choice only of a readable record, and `choices`: an object of
/// exactly an `engine` and a `placement` list, each non-empty, of known tokens, without
/// a repeat.
pub fn parse_engine(answer: &Value) -> Option<LocalEngineSetting> {
    let object = answer.as_object()?;
    if object.len() != 6 {
        return None;
    }
    let lists = object.get("choices")?.as_object()?;
    if lists.len() != 2 {
        return None;
    }
    let choices = Choices {
        engine: offered(lists.get("engine")?, engine_token)?,
        placement: offered(lists.get("placement")?, placement_token)?,
    };
    let revision = object
        .get("revision")?
        .as_str()
        .filter(|text| is_revision(text))?
        .to_owned();
    let engine = object.get("engine")?;
    let placement = object.get("placement")?;
    let chosen = object.get("chosen")?.as_bool()?;
    if object.get("unreadable")?.as_bool()? {
        return (engine.is_null() && placement.is_null() && !chosen)
            .then_some(LocalEngineSetting::Unreadable { choices, revision });
    }
    Some(LocalEngineSetting::Readable {
        engine: engine_token(engine.as_str()?)?,
        placement: placement_token(placement.as_str()?)?,
        choices,
        revision,
        chosen,
    })
}

/// The values a service's list of offered tokens names, or `None` unless it is a
/// non-empty array of tokens `token` knows, none named twice.
fn offered<T: PartialEq>(list: &Value, token: fn(&str) -> Option<T>) -> Option<Vec<T>> {
    let mut offered: Vec<T> = Vec::new();
    for entry in list.as_array()? {
        let value = token(entry.as_str()?)?;
        if offered.contains(&value) {
            return None;
        }
        offered.push(value);
    }
    (!offered.is_empty()).then_some(offered)
}

/// Why a choice of `engine` is refused before it reaches the service: llama.cpp on a
/// package that carries no llama-server to run it with, which is a package whose
/// default engine ([`package_default_engine`]) is not llama.cpp.
pub fn engine_unavailable(engine: LocalEngine, package_root: &Path) -> Option<&'static str> {
    (engine == LocalEngine::LlamaCpp
        && package_default_engine(package_root) != LocalEngine::LlamaCpp)
        .then_some("agent_local_engine_unavailable")
}

/// The engine the service names `text`.
pub fn engine_token(text: &str) -> Option<LocalEngine> {
    match text {
        "llamacpp" => Some(LocalEngine::LlamaCpp),
        "ollama" => Some(LocalEngine::Ollama),
        _ => None,
    }
}

/// The placement the service names `text`.
pub fn placement_token(text: &str) -> Option<Placement> {
    match text {
        "auto" => Some(Placement::Auto),
        "cpu_only" => Some(Placement::CpuOnly),
        _ => None,
    }
}

/// The engine and placement the runtime manager's selection record under `root` holds:
/// the defaults the package at `package_root` derives when there is no record, and `None`
/// for a record that cannot be read, which never stands for the defaults.
#[cfg(any(windows, target_os = "macos"))]
pub fn manager_selection(root: &Path, package_root: &Path) -> Option<(LocalEngine, Placement)> {
    cadrumo_manager::local_engine::LocalEngineSelection::read(root)
        .selection(package_root)
        .map(|selection| (selection.engine, selection.placement))
}

/// This platform's desktop writes no selection record for a manager, so the defaults the
/// package derives hold.
#[cfg(not(any(windows, target_os = "macos")))]
pub fn manager_selection(_root: &Path, package_root: &Path) -> Option<(LocalEngine, Placement)> {
    Some((package_default_engine(package_root), Placement::default()))
}

/// Stores `engine` and `placement` as the runtime manager's selection under `root`, unless
/// the record already holds exactly them, so a repeated read does not rewrite it. Whether
/// it was written.
#[cfg(any(windows, target_os = "macos"))]
pub fn record_selection(
    root: &Path,
    engine: LocalEngine,
    placement: Placement,
) -> std::io::Result<bool> {
    use cadrumo_manager::local_engine::{LocalEngineSelection, Recorded};
    let selection = LocalEngineSelection::new(engine, placement);
    if LocalEngineSelection::read(root) == Recorded::Selected(selection) {
        return Ok(false);
    }
    selection.store(root)?;
    Ok(true)
}

/// This platform's desktop has no manager selection record to write.
#[cfg(not(any(windows, target_os = "macos")))]
pub fn record_selection(
    _root: &Path,
    _engine: LocalEngine,
    _placement: Placement,
) -> std::io::Result<bool> {
    Ok(false)
}

/// Removes the runtime manager's selection record under `root`, readable or not; an
/// absent one is already clear.
#[cfg(any(windows, target_os = "macos"))]
pub fn clear_selection(root: &Path) -> std::io::Result<()> {
    cadrumo_manager::local_engine::LocalEngineSelection::clear(root)
}

/// This platform's desktop has no manager selection record to remove.
#[cfg(not(any(windows, target_os = "macos")))]
pub fn clear_selection(_root: &Path) -> std::io::Result<()> {
    Ok(())
}

/// Makes the runtime manager's selection record under `root` hold what `sync` says.
pub fn sync_record(root: &Path, sync: RecordSync) -> std::io::Result<()> {
    match sync {
        RecordSync::Store(engine, placement) => {
            record_selection(root, engine, placement).map(|_| ())
        }
        RecordSync::Clear => clear_selection(root),
        RecordSync::Leave => Ok(()),
    }
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
pub(crate) mod tests {
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

    /// An engine answer as the service sends it; a readable one is a stored choice.
    fn engine_answer(unreadable: bool, engine: Value, placement: Value) -> Value {
        json!({
            "unreadable": unreadable,
            "chosen": !unreadable,
            "engine": engine,
            "placement": placement,
            "choices": {
                "engine": ["llamacpp", "ollama"],
                "placement": ["auto", "cpu_only"],
            },
            "revision": revision(),
        })
    }

    /// Every engine and placement offered, as the service lists them.
    fn served_choices() -> Choices {
        Choices {
            engine: vec![LocalEngine::LlamaCpp, LocalEngine::Ollama],
            placement: vec![Placement::Auto, Placement::CpuOnly],
        }
    }

    #[test]
    fn a_readable_engine_setting_crosses_as_the_window_reads_it() {
        let parsed = parse_engine(&engine_answer(false, json!("llamacpp"), json!("cpu_only")));
        assert_eq!(
            parsed,
            Some(LocalEngineSetting::Readable {
                engine: LocalEngine::LlamaCpp,
                placement: Placement::CpuOnly,
                choices: served_choices(),
                revision: revision(),
                chosen: true,
            })
        );
        let parsed = parsed.unwrap();
        assert_eq!(
            parsed.record_sync(),
            RecordSync::Store(LocalEngine::LlamaCpp, Placement::CpuOnly)
        );
        assert_eq!(
            serde_json::to_value(&parsed).unwrap(),
            json!({"state": "readable", "engine": "llamacpp", "placement": "cpu_only", "choices": {"engine": ["llamacpp", "ollama"], "placement": ["auto", "cpu_only"]}, "revision": revision()})
        );
        let ollama = parse_engine(&engine_answer(false, json!("ollama"), json!("auto"))).unwrap();
        assert_eq!(
            serde_json::to_value(&ollama).unwrap(),
            json!({"state": "readable", "engine": "ollama", "placement": "auto", "choices": {"engine": ["llamacpp", "ollama"], "placement": ["auto", "cpu_only"]}, "revision": revision()})
        );
        assert_eq!(
            refusal(&engine_answer(false, json!("ollama"), json!("auto"))),
            None
        );
    }

    #[test]
    fn an_unreadable_engine_setting_names_no_engine_and_keeps_its_reset_guard() {
        let parsed = parse_engine(&engine_answer(true, Value::Null, Value::Null)).unwrap();
        assert_eq!(
            parsed,
            LocalEngineSetting::Unreadable {
                choices: served_choices(),
                revision: revision()
            }
        );
        assert_eq!(parsed.record_sync(), RecordSync::Leave);
        assert_eq!(
            serde_json::to_value(&parsed).unwrap(),
            json!({"state": "unreadable", "choices": {"engine": ["llamacpp", "ollama"], "placement": ["auto", "cpu_only"]}, "revision": revision()})
        );
    }

    #[test]
    fn an_unchosen_setting_is_the_package_default_the_window_reads_and_clears_the_record() {
        let mut answer = engine_answer(false, json!("llamacpp"), json!("auto"));
        answer["chosen"] = json!(false);
        let parsed = parse_engine(&answer).unwrap();
        assert_eq!(
            parsed,
            LocalEngineSetting::Readable {
                engine: LocalEngine::LlamaCpp,
                placement: Placement::Auto,
                choices: served_choices(),
                revision: revision(),
                chosen: false,
            }
        );
        assert_eq!(parsed.record_sync(), RecordSync::Clear);
        // The window reads the same setting whether or not it was chosen.
        assert_eq!(
            serde_json::to_value(&parsed).unwrap(),
            json!({"state": "readable", "engine": "llamacpp", "placement": "auto", "choices": {"engine": ["llamacpp", "ollama"], "placement": ["auto", "cpu_only"]}, "revision": revision()})
        );
    }

    #[test]
    fn the_offered_engines_and_placements_cross_in_the_services_order() {
        let mut answer = engine_answer(false, json!("ollama"), json!("auto"));
        answer["choices"] = json!({"engine": ["ollama"], "placement": ["cpu_only", "auto"]});
        let parsed = parse_engine(&answer).unwrap();
        assert_eq!(
            serde_json::to_value(&parsed).unwrap(),
            json!({
                "state": "readable", "engine": "ollama", "placement": "auto",
                "choices": {"engine": ["ollama"], "placement": ["cpu_only", "auto"]},
                "revision": revision(),
            })
        );
        // An unreadable record offers the same lists.
        let mut unreadable = engine_answer(true, Value::Null, Value::Null);
        unreadable["choices"] = json!({"engine": ["llamacpp"], "placement": ["auto"]});
        assert_eq!(
            parse_engine(&unreadable),
            Some(LocalEngineSetting::Unreadable {
                choices: Choices {
                    engine: vec![LocalEngine::LlamaCpp],
                    placement: vec![Placement::Auto],
                },
                revision: revision(),
            })
        );
    }

    #[test]
    fn an_offered_list_outside_the_contract_refuses_the_whole_answer() {
        for member in ["engine", "placement"] {
            let (known, other) = if member == "engine" {
                ("ollama", "llamacpp")
            } else {
                ("auto", "cpu_only")
            };
            for list in [
                json!([]),
                json!([known, known]),
                json!([known, other, known]),
                json!([known, "vllm"]),
                json!([known, "Auto"]),
                json!([known, 1]),
                json!([known, null]),
                json!([[known]]),
                json!(known),
                json!({"engine": true}),
                Value::Null,
            ] {
                for unreadable in [false, true] {
                    let mut answer = if unreadable {
                        engine_answer(true, Value::Null, Value::Null)
                    } else {
                        engine_answer(false, json!("ollama"), json!("auto"))
                    };
                    answer["choices"][member] = list.clone();
                    assert_eq!(parse_engine(&answer), None, "{member} {list} {answer}");
                }
            }
            // A list that is missing from `choices`.
            let mut missing = engine_answer(false, json!("ollama"), json!("auto"));
            missing["choices"].as_object_mut().unwrap().remove(member);
            assert_eq!(parse_engine(&missing), None, "{member} missing");
        }
        // `choices` is exactly the two lists, as an object.
        let readable = || engine_answer(false, json!("ollama"), json!("auto"));
        let mut extra_list = readable();
        extra_list["choices"]["third"] = json!(["auto"]);
        let mut misnamed = readable();
        misnamed["choices"] = json!({"engine": ["ollama"], "placements": ["auto"]});
        let mut flat = readable();
        flat["choices"] = json!(["ollama"]);
        let mut absent = readable();
        absent.as_object_mut().unwrap().remove("choices");
        let mut null_choices = readable();
        null_choices["choices"] = Value::Null;
        // The seven-member answer with the flat lists beside it is no answer.
        let mut flat_members = readable();
        flat_members.as_object_mut().unwrap().remove("choices");
        flat_members["choices"] = json!(["ollama"]);
        flat_members["placement_choices"] = json!(["auto"]);
        for answer in [
            extra_list,
            misnamed,
            flat,
            absent,
            null_choices,
            flat_members,
        ] {
            assert_eq!(parse_engine(&answer), None, "{answer}");
        }
    }

    #[test]
    fn an_engine_setting_outside_the_contract_is_refused() {
        let readable = || engine_answer(false, json!("ollama"), json!("auto"));
        let mut extra = readable();
        extra["extra"] = json!(1);
        let mut missing = readable();
        missing.as_object_mut().unwrap().remove("placement");
        let mut upper_revision = readable();
        upper_revision["revision"] = json!("A".repeat(64));
        let mut short_revision = readable();
        short_revision["revision"] = json!("a".repeat(63));
        let mut null_revision = readable();
        null_revision["revision"] = Value::Null;
        let mut textual_flag = readable();
        textual_flag["unreadable"] = json!("false");
        let mut unchosen_missing = readable();
        unchosen_missing.as_object_mut().unwrap().remove("chosen");
        let mut textual_choice = readable();
        textual_choice["chosen"] = json!("true");
        let mut null_choice = readable();
        null_choice["chosen"] = Value::Null;
        let mut chosen_unreadable = engine_answer(true, Value::Null, Value::Null);
        chosen_unreadable["chosen"] = json!(true);
        let mut renamed_choice = readable();
        renamed_choice.as_object_mut().unwrap().remove("chosen");
        renamed_choice["extra"] = json!(false);
        for answer in [
            unchosen_missing,
            textual_choice,
            null_choice,
            chosen_unreadable,
            renamed_choice,
            extra,
            missing,
            upper_revision,
            short_revision,
            null_revision,
            textual_flag,
            engine_answer(false, json!("llama_cpp"), json!("auto")),
            engine_answer(false, json!("Ollama"), json!("auto")),
            engine_answer(false, json!("vllm"), json!("auto")),
            engine_answer(false, json!("ollama"), json!("gpu")),
            engine_answer(false, json!("ollama"), json!("cpu")),
            engine_answer(false, json!(1), json!("auto")),
            engine_answer(false, Value::Null, Value::Null),
            engine_answer(false, json!("ollama"), Value::Null),
            engine_answer(true, json!("ollama"), json!("auto")),
            engine_answer(true, json!("ollama"), Value::Null),
            engine_answer(true, Value::Null, json!("auto")),
            json!([]),
            Value::Null,
        ] {
            assert_eq!(parse_engine(&answer), None, "{answer}");
        }
        // A refusal is no setting, and a change refusal keeps the service's reason.
        let conflict = json!({"kind": "refused", "code": "revision_conflict"});
        assert_eq!(parse_engine(&conflict), None);
        assert_eq!(
            change_refusal(&conflict),
            Some("agent_local_models_revision_conflict")
        );
        assert_eq!(
            change_refusal(&json!({"code": "committed_readback_failed"})),
            Some("agent_local_models_committed_readback_failed")
        );
    }

    #[test]
    fn engine_and_placement_tokens_are_the_services_closed_sets() {
        assert_eq!(engine_token("llamacpp"), Some(LocalEngine::LlamaCpp));
        assert_eq!(engine_token("ollama"), Some(LocalEngine::Ollama));
        for refused in ["", "llama_cpp", "llama.cpp", "LLAMACPP", "ollama ", "vllm"] {
            assert_eq!(engine_token(refused), None, "{refused:?}");
        }
        assert_eq!(placement_token("auto"), Some(Placement::Auto));
        assert_eq!(placement_token("cpu_only"), Some(Placement::CpuOnly));
        for refused in ["", "cpu", "gpu", "CPU_ONLY", "cpu-only", "auto "] {
            assert_eq!(placement_token(refused), None, "{refused:?}");
        }
    }

    #[cfg(any(windows, target_os = "macos"))]
    #[test]
    fn the_managers_selection_is_written_only_when_it_differs() {
        use std::time::{SystemTime, UNIX_EPOCH};
        let root = std::env::temp_dir().join(format!(
            "cadrumo-desktop-engine-selection-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let package = Package::new(false);
        let selection = |root: &Path| manager_selection(root, &package.root());
        // No record is the package's defaults, and a setting is written the first time.
        assert_eq!(
            selection(&root),
            Some((LocalEngine::Ollama, Placement::Auto))
        );
        assert!(record_selection(&root, LocalEngine::LlamaCpp, Placement::CpuOnly).unwrap());
        assert_eq!(
            selection(&root),
            Some((LocalEngine::LlamaCpp, Placement::CpuOnly))
        );
        // The same setting read again rewrites nothing; another one replaces it.
        assert!(!record_selection(&root, LocalEngine::LlamaCpp, Placement::CpuOnly).unwrap());
        assert!(record_selection(&root, LocalEngine::Ollama, Placement::Auto).unwrap());
        assert!(!record_selection(&root, LocalEngine::Ollama, Placement::Auto).unwrap());
        // A record nobody can read is never the defaults, and the next setting replaces it.
        cadrumo_manager::custody::write_local_record(
            &root.join(cadrumo_manager::contract::LOCAL_ENGINE_SELECTION),
            b"{",
            4096,
        )
        .unwrap();
        assert_eq!(selection(&root), None);
        assert!(record_selection(&root, LocalEngine::Ollama, Placement::Auto).unwrap());
        assert_eq!(
            selection(&root),
            Some((LocalEngine::Ollama, Placement::Auto))
        );
        std::fs::remove_dir_all(&root).unwrap();
    }

    /// A package root of its own, removed after the test, carrying a llama-server or not.
    pub(crate) struct Package(std::path::PathBuf);

    impl Package {
        pub(crate) fn new(carrying: bool) -> Self {
            use std::time::{SystemTime, UNIX_EPOCH};
            let root = std::env::temp_dir().join(format!(
                "cadrumo-desktop-package-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            std::fs::create_dir_all(&root).unwrap();
            // The packaged-program check refuses a linked ancestor, and a Unix temporary
            // folder can sit under one, as macOS's `/var` does.
            #[cfg(unix)]
            let root = std::fs::canonicalize(&root).unwrap();
            if carrying {
                let folder = root.join("package").join(cadrumo_platform::LLAMA_SERVER);
                std::fs::create_dir_all(&folder).unwrap();
                let program = folder.join(if cfg!(windows) {
                    "llama-server.exe"
                } else {
                    "llama-server"
                });
                std::fs::write(&program, b"#!/bin/sh\nexit 0\n").unwrap();
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    std::fs::set_permissions(&program, std::fs::Permissions::from_mode(0o755))
                        .unwrap();
                }
            } else {
                std::fs::create_dir_all(root.join("package")).unwrap();
            }
            Self(root)
        }

        /// The package root, as the desktop is launched from it.
        pub(crate) fn root(&self) -> std::path::PathBuf {
            self.0.join("package")
        }
    }

    impl Drop for Package {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[cfg(any(windows, target_os = "macos"))]
    #[test]
    fn a_chosen_setting_is_stored_an_unchosen_one_clears_the_record_and_an_unreadable_one_leaves_it()
     {
        use cadrumo_manager::local_engine::{LocalEngineSelection, Recorded};
        use std::time::{SystemTime, UNIX_EPOCH};
        let root = std::env::temp_dir().join(format!(
            "cadrumo-desktop-engine-sync-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let read = || LocalEngineSelection::read(&root);
        let selected =
            |engine, placement| Recorded::Selected(LocalEngineSelection::new(engine, placement));
        let unreadable = || {
            cadrumo_manager::custody::write_local_record(
                &root.join(cadrumo_manager::contract::LOCAL_ENGINE_SELECTION),
                b"{",
                4096,
            )
            .unwrap();
            assert_eq!(read(), Recorded::Unreadable);
        };
        let llama_cpu = RecordSync::Store(LocalEngine::LlamaCpp, Placement::CpuOnly);
        // Store over an absent record.
        assert_eq!(read(), Recorded::Absent);
        sync_record(&root, llama_cpu).unwrap();
        assert_eq!(read(), selected(LocalEngine::LlamaCpp, Placement::CpuOnly));
        // Store over a different stored choice replaces it.
        sync_record(
            &root,
            RecordSync::Store(LocalEngine::Ollama, Placement::Auto),
        )
        .unwrap();
        assert_eq!(read(), selected(LocalEngine::Ollama, Placement::Auto));
        // Clear over a stored choice removes it, so the package's defaults apply.
        sync_record(&root, RecordSync::Clear).unwrap();
        assert_eq!(read(), Recorded::Absent);
        // Clear over a record nobody can read removes it as well.
        unreadable();
        sync_record(&root, RecordSync::Clear).unwrap();
        assert_eq!(read(), Recorded::Absent);
        // Leave over a record nobody can read keeps it as it is.
        unreadable();
        sync_record(&root, RecordSync::Leave).unwrap();
        assert_eq!(read(), Recorded::Unreadable);
        // The rule that picks each: a stored choice, no choice, a setting nobody can read.
        let setting = |chosen: bool| LocalEngineSetting::Readable {
            engine: LocalEngine::LlamaCpp,
            placement: Placement::CpuOnly,
            choices: served_choices(),
            revision: revision(),
            chosen,
        };
        assert_eq!(setting(true).record_sync(), llama_cpu);
        assert_eq!(setting(false).record_sync(), RecordSync::Clear);
        assert_eq!(
            LocalEngineSetting::Unreadable {
                choices: served_choices(),
                revision: revision()
            }
            .record_sync(),
            RecordSync::Leave
        );
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn a_package_carrying_llama_server_admits_either_engine() {
        let package = Package::new(true);
        for engine in [LocalEngine::LlamaCpp, LocalEngine::Ollama] {
            assert_eq!(engine_unavailable(engine, &package.root()), None);
        }
    }

    #[test]
    fn a_package_without_llama_server_refuses_llama_cpp_and_admits_ollama() {
        let package = Package::new(false);
        assert_eq!(
            engine_unavailable(LocalEngine::LlamaCpp, &package.root()),
            Some("agent_local_engine_unavailable")
        );
        assert_eq!(
            engine_unavailable(LocalEngine::Ollama, &package.root()),
            None
        );
    }
}
