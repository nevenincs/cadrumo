use super::admitted::{ADMITTED, Kind};
use super::*;
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};

/// The shipped operation contract manifest, found from the crate upward: the
/// host tests run in a snapshot of the sources under the build tree, which
/// sits inside the repository checkout that owns the manifest.
fn manifest() -> String {
    let relative = std::path::Path::new("src/cadrumo/_data/operations/contract_manifest.json");
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .map(|directory| directory.join(relative))
        .find(|candidate| candidate.is_file())
        .expect("the shipped operation contract manifest is above the crate");
    std::fs::read_to_string(path).unwrap()
}

/// Each shipped definition's contract, by id.
fn contracts() -> BTreeMap<String, Value> {
    let manifest: Value = serde_json::from_str(&manifest()).unwrap();
    manifest["operations"]
        .as_array()
        .unwrap()
        .iter()
        .map(|entry| {
            let contract = entry["contract"].clone();
            (
                contract["definition_id"].as_str().unwrap().to_owned(),
                contract,
            )
        })
        .collect()
}
fn strings(value: &Value) -> BTreeSet<&str> {
    value
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item.as_str().unwrap())
        .collect()
}

#[test]
fn the_admitted_list_is_sorted_and_names_each_definition_once() {
    let ids: Vec<&str> = ADMITTED.iter().map(|(id, _)| *id).collect();
    let mut sorted = ids.clone();
    sorted.sort_unstable();
    sorted.dedup();
    assert_eq!(ids, sorted);
}

#[test]
fn every_admitted_definition_is_a_shipped_contract() {
    let contracts = contracts();
    for (id, _) in ADMITTED {
        assert!(contracts.contains_key(id), "{id} is not in the manifest");
    }
}

#[test]
fn a_read_declares_no_effect_that_changes_records() {
    let contracts = contracts();
    for (id, kind) in ADMITTED {
        let effects = strings(&contracts[id]["permitted_effects"]);
        let changes = effects.iter().any(|e| matches!(*e, "updated" | "partial"));
        assert_eq!(changes, kind != Kind::Read, "{id}: {effects:?}");
    }
}

#[test]
fn no_admitted_definition_pauses_for_the_person_or_can_be_cancelled() {
    let contracts = contracts();
    for (id, _) in ADMITTED {
        assert_eq!(contracts[id]["cancellation"], "unsupported", "{id}");
        assert_eq!(contracts[id]["interaction_kinds"], json!([]), "{id}");
    }
}

#[test]
fn the_list_holds_only_reads_of_aeat_or_the_profile() {
    for (id, _) in ADMITTED {
        assert!(
            id.starts_with("live.") || id == "auth.session.acquire",
            "{id} is outside the live reads"
        );
        assert!(
            !["submit", "filing", "present", "write"]
                .iter()
                .any(|word| id.contains(word)),
            "{id}"
        );
    }
}

#[test]
fn the_areas_submit_only_admitted_definitions_and_leave_none_unused() {
    let mut named: BTreeSet<&str> = BTreeSet::from([
        "auth.session.acquire",
        "live.borrador.100.import",
        "live.notifications.latest",
        "live.notifications.show",
        "live.sync.status",
    ]);
    for area in Area::ORDER {
        named.extend(area.definitions());
    }
    let admitted: BTreeSet<&str> = ADMITTED.iter().map(|(id, _)| *id).collect();
    assert_eq!(named, admitted);
}

#[test]
fn areas_run_in_the_fixed_order() {
    let mut ordered = Area::ORDER;
    ordered.sort();
    assert_eq!(ordered, Area::ORDER);
}

fn selection(value: Value) -> Result<Plan> {
    serde_json::from_value::<Selection>(value)
        .map_err(|_| invalid())?
        .admit()
}

#[test]
fn a_selection_runs_each_area_once_in_the_fixed_order() {
    let plan = selection(json!({
        "areas": ["filed", "census", "filed", "vat"],
        "years": [2025, 2023, 2025],
        "forms": ["303", "130", "303"],
    }))
    .unwrap();
    assert_eq!(plan.areas, [Area::Census, Area::Vat, Area::Filed]);
    assert_eq!(plan.years, [2023, 2025]);
    assert_eq!(plan.forms, ["130", "303"]);
    assert!(!plan.dry_run);
}

#[test]
fn a_dry_run_leaves_out_every_area_but_filed_declarations() {
    let plan = selection(json!({
        "areas": ["census", "notifications", "filed"],
        "years": [2025],
        "dry_run": true,
    }))
    .unwrap();
    assert_eq!(plan.areas, [Area::Filed]);
    assert!(plan.dry_run);
    assert!(
        selection(json!({"areas": ["census", "notifications"], "dry_run": true})).is_err(),
        "a dry run with nothing to read is refused"
    );
}

#[test]
fn a_selection_needs_years_only_where_an_area_reads_by_year() {
    assert!(selection(json!({"areas": ["census", "identity", "notifications"]})).is_ok());
    for area in ["vat", "filed"] {
        assert!(selection(json!({"areas": [area]})).is_err(), "{area}");
        assert!(selection(json!({"areas": [area], "years": [2025]})).is_ok());
    }
}

#[test]
fn a_selection_refuses_what_the_window_may_not_name() {
    for refused in [
        json!({"areas": []}),
        json!({"areas": ["borrador"]}),
        json!({"areas": ["census"], "output_root": "C:\\"}),
        json!({"areas": ["census"], "nif": "00000000T"}),
        json!({"areas": ["filed"], "years": [25]}),
        json!({"areas": ["filed"], "years": [2025], "forms": ["../x"]}),
        json!({"areas": ["filed"], "years": [2025], "forms": [""]}),
    ] {
        assert!(selection(refused.clone()).is_err(), "{refused}");
    }
}
