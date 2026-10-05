//! The manager's session records against the shared conformance vectors.
//!
//! `session_record_vectors.json` holds Quit markers whose verdicts the Python canonical-JSON
//! owner confirms in `dev/packaging/tests/test_native_manager_session_records.py`: what the
//! manager writes is what canonical JSON writes, every spelling it accepts is grammatical,
//! and `refused_by_manager` lists grammatical records that the marker's schema refuses.

use cadrumo_manager::session::claim::START_CLAIM_LOCATION;
use cadrumo_manager::session::quit::{
    MAXIMUM_QUIT_MARKER_BYTES, QUIT_MARKER_LOCATION, decode_quit_marker, encode_quit_marker,
};
use serde_json::Value;

fn vectors() -> Value {
    serde_json::from_str(include_str!("session_record_vectors.json")).expect("vectors JSON")
}

fn strings<'a>(value: &'a Value, kind: &str) -> Vec<&'a str> {
    value["quit_markers"][kind]
        .as_array()
        .unwrap_or_else(|| panic!("quit_markers.{kind}"))
        .iter()
        .map(|item| item.as_str().expect("vector string"))
        .collect()
}

#[test]
fn locations_and_bound_match_the_vectors() {
    let vectors = vectors();
    assert_eq!(
        vectors["start_claim_location"].as_str(),
        Some(START_CLAIM_LOCATION.join("/").as_str())
    );
    assert_eq!(
        vectors["quit_marker_location"].as_str(),
        Some(QUIT_MARKER_LOCATION.join("/").as_str())
    );
    assert_eq!(
        vectors["quit_marker_maximum_bytes"].as_u64(),
        Some(MAXIMUM_QUIT_MARKER_BYTES)
    );
}

#[test]
fn canonical_markers_decode_and_encode_to_the_same_bytes() {
    let vectors = vectors();
    let canonical = strings(&vectors, "canonical");
    assert!(!canonical.is_empty());
    for raw in canonical {
        let marker = decode_quit_marker(raw.as_bytes()).unwrap_or_else(|| panic!("{raw}"));
        assert_eq!(
            encode_quit_marker(&marker),
            Some(raw.as_bytes().to_vec()),
            "{raw}"
        );
    }
}

#[test]
fn equivalent_spellings_decode_to_their_canonical_marker() {
    let vectors = vectors();
    let equivalent = vectors["quit_markers"]["equivalent"]
        .as_array()
        .expect("equivalent");
    assert!(!equivalent.is_empty());
    for vector in equivalent {
        let raw = vector["raw"].as_str().expect("raw");
        let canonical = vector["canonical"].as_str().expect("canonical");
        let marker = decode_quit_marker(raw.as_bytes()).unwrap_or_else(|| panic!("{raw:?}"));
        assert_eq!(
            encode_quit_marker(&marker),
            Some(canonical.as_bytes().to_vec()),
            "{raw:?}"
        );
    }
}

#[test]
fn records_outside_the_grammar_or_the_schema_are_refused() {
    let vectors = vectors();
    let refused = strings(&vectors, "refused");
    let schema = strings(&vectors, "refused_by_manager");
    assert!(!refused.is_empty() && !schema.is_empty());
    for raw in refused.into_iter().chain(schema) {
        assert_eq!(decode_quit_marker(raw.as_bytes()), None, "{raw:?}");
    }
}

#[test]
fn a_marker_above_the_bound_is_refused() {
    let vectors = vectors();
    let canonical = strings(&vectors, "canonical")[0];
    let bound = usize::try_from(MAXIMUM_QUIT_MARKER_BYTES).expect("bound");
    let mut padded = canonical.as_bytes().to_vec();
    padded.resize(bound, b' ');
    assert!(decode_quit_marker(&padded).is_some(), "at the bound");
    padded.push(b' ');
    assert_eq!(decode_quit_marker(&padded), None, "above the bound");
}
