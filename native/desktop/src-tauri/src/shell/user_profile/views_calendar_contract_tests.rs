//! The calendar the host asks for and serves, against a read the product
//! produced: `calendar_read_fixture.py` serialises the registered
//! `overview.calendar` request and served result from the product's own models
//! into the build's testing directory before these tests run, so every name
//! and value compared here is the product's, not one spelled in this file.
use super::*;

/// The one field the host withholds: where an observed event was read from.
const SOURCE: &str = "source_url";

fn produced() -> Value {
    serde_json::from_str(include_str!(env!("CADRUMO_CALENDAR_READ_CONTRACT_FIXTURE"))).unwrap()
}

/// The produced read and the profile and range its request names.
fn read() -> (Value, String, String, String) {
    let produced = produced();
    let named = |field: &str| produced["request"][field].as_str().unwrap().to_owned();
    let (profile, from, to) = (named("profile_id"), named("from_date"), named("to_date"));
    (produced["result"].clone(), profile, from, to)
}

#[test]
fn the_calendar_request_is_the_products_registered_request() {
    let produced = produced();
    let request = &produced["request"];
    let named = |field: &str| request[field].as_str().unwrap();
    assert_eq!(
        &calendar_request(
            named("profile_id"),
            named("output_language"),
            named("from_date"),
            named("to_date")
        ),
        request
    );
}

#[test]
fn the_served_calendar_is_the_products_snapshot_field_for_field() {
    let (result, profile, from, to) = read();
    let mut snapshot = result["payload"]["calendar"].clone();
    for event in snapshot["events"].as_array_mut().unwrap() {
        assert!(event.as_object_mut().unwrap().remove(SOURCE).is_some());
    }
    let served =
        serde_json::to_value(filing_calendar(result, &profile, &from, &to).unwrap()).unwrap();
    // Every field of the snapshot, nested rows included, under the product's
    // own name and with its own value; nothing added or renamed, and nothing
    // left out but the events' sources the host withholds.
    assert_eq!(served, snapshot);
    for rows in ["entries", "warnings", "suppressed_entries", "events"] {
        assert!(
            !served[rows].as_array().unwrap().is_empty(),
            "the produced read carries no {rows}, so it would not show them passed on"
        );
    }
}

#[test]
fn calendar_events_reach_the_window_without_their_source_url() {
    let (result, profile, from, to) = read();
    let read_from = result["payload"]["calendar"]["events"][0][SOURCE].clone();
    assert!(
        read_from.is_string(),
        "the produced event carries no source"
    );
    let served =
        serde_json::to_value(filing_calendar(result, &profile, &from, &to).unwrap()).unwrap();
    let event = &served["events"][0];
    assert!(event.get(SOURCE).is_none());
    assert!(!served.to_string().contains(read_from.as_str().unwrap()));
}

#[test]
fn a_calendar_for_another_profile_range_or_read_is_refused() {
    let (result, profile, from, to) = read();
    assert!(filing_calendar(result.clone(), "another", &from, &to).is_err());
    assert!(filing_calendar(result.clone(), &profile, &to, &to).is_err());
    assert!(filing_calendar(result.clone(), &profile, &from, &from).is_err());
    let mut other = result.clone();
    other["payload"]["kind"] = json!("agenda");
    assert!(filing_calendar(other, &profile, &from, &to).is_err());
    let mut survey = result.clone();
    survey["payload"]["calendar"] = Value::Null;
    assert!(filing_calendar(survey, &profile, &from, &to).is_err());
    let mut rangeless = result;
    rangeless["payload"]["calendar"]
        .as_object_mut()
        .unwrap()
        .remove("range");
    assert!(filing_calendar(rangeless, &profile, &from, &to).is_err());
}
