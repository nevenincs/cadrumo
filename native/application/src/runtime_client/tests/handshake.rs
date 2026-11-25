use super::super::connection::Connection;
use super::super::endpoint::Endpoint;

use super::super::handshake::{Cohort, hello_document, server_hello};
use super::super::refusal::Refusal;
#[cfg(windows)]
use cadrumo_platform::runtime_pipe;
#[cfg(unix)]
use cadrumo_platform::runtime_socket;
use serde_json::{Map, Value, json};
use std::path::Path;
use std::time::{Duration, Instant};

#[cfg(windows)]
fn endpoint() -> Endpoint {
    Endpoint {
        pipe_name: r"\\.\pipe\cadrumo-runtime-test".into(),
        storage_identity: "f".repeat(64),
        owner_sid: "S-1-5-21-1-2-3-1001".into(),
    }
}

#[cfg(unix)]
fn endpoint() -> Endpoint {
    Endpoint {
        socket_leaf: format!("{}.sock", "f".repeat(32)),
        storage_identity: "f".repeat(64),
        owner_uid: 501,
    }
}

fn cohort(generation: Option<&str>) -> Cohort {
    Cohort {
        product_version: "0.6.0".into(),
        authority_generation: generation.map(str::to_owned),
    }
}

#[test]
fn the_client_hello_names_the_cohort_and_asks_for_lifecycle_notices() {
    let hello = hello_document(&endpoint(), &cohort(Some("a1")), true);
    assert_eq!(
        hello,
        json!({
            "kind": "client_hello", "protocol_version": 4, "product_version": "0.6.0",
            "storage_identity": "f".repeat(64), "authority_generation": "a1", "lifecycle_notices": "v1"
        })
    );
    assert!(hello_document(&endpoint(), &cohort(None), true)["authority_generation"].is_null());
}

#[test]
fn a_hello_that_asks_for_no_lifecycle_notices_omits_the_member() {
    let hello = hello_document(&endpoint(), &cohort(Some("a1")), false);
    assert_eq!(
        hello,
        json!({
            "kind": "client_hello", "protocol_version": 4, "product_version": "0.6.0",
            "storage_identity": "f".repeat(64), "authority_generation": "a1"
        })
    );
}

fn server(version: &str, identity: &str, generation: Option<&str>) -> Map<String, Value> {
    let mut document = json!({
        "kind": "server_hello", "protocol_version": 4, "product_version": version,
        "storage_identity": identity, "boot_id": "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
        "authority_generation": generation,
    });
    document.as_object_mut().unwrap().clone()
}

#[test]
fn the_server_hello_must_match_version_root_and_any_shared_generation() {
    let identity = "f".repeat(64);
    let hello = server_hello(
        &server("0.6.0", &identity, Some("a1")),
        &endpoint(),
        &cohort(Some("a1")),
    )
    .unwrap();
    assert_eq!(hello.boot_id, "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d");
    assert_eq!(hello.authority_generation.as_deref(), Some("a1"));
    // A side that knows no generation does not refuse the other's.
    assert!(
        server_hello(
            &server("0.6.0", &identity, None),
            &endpoint(),
            &cohort(Some("a1"))
        )
        .is_ok()
    );
    assert!(
        server_hello(
            &server("0.6.0", &identity, Some("a1")),
            &endpoint(),
            &cohort(None)
        )
        .is_ok()
    );
    assert!(matches!(
        server_hello(
            &server("0.6.0", &identity, Some("a2")),
            &endpoint(),
            &cohort(Some("a1"))
        ),
        Err(Refusal::VersionMismatch)
    ));
    assert!(matches!(
        server_hello(
            &server("0.6.1", &identity, None),
            &endpoint(),
            &cohort(None)
        ),
        Err(Refusal::VersionMismatch)
    ));
    assert!(matches!(
        server_hello(
            &server("0.6.0", &"e".repeat(64), None),
            &endpoint(),
            &cohort(None)
        ),
        Err(Refusal::RootMismatch)
    ));
    let mut wrong = server("0.6.0", &identity, None);
    wrong.insert("protocol_version".into(), json!(2));
    assert!(matches!(
        server_hello(&wrong, &endpoint(), &cohort(None)),
        Err(Refusal::InvalidFrame)
    ));
}

#[test]
#[cfg(windows)]
fn an_absent_endpoint_is_not_ready_and_an_unknown_root_names_none() {
    let endpoint = Endpoint {
        pipe_name: format!(r"\\.\pipe\cadrumo-runtime-absent-{}", std::process::id()),
        storage_identity: "f".repeat(64),
        owner_sid: runtime_pipe::current_user_sid().unwrap(),
    };
    let refused = match Connection::open(
        &endpoint,
        &cohort(None),
        Instant::now() + Duration::from_secs(2),
    ) {
        Ok(_) => panic!("an absent pipe must not connect"),
        Err(refused) => refused,
    };
    assert!(matches!(refused, Refusal::EndpointNotReady), "{refused}");
    assert!(matches!(
        Endpoint::of(Path::new(r"C:\cadrumo-no-such-root")),
        Err(Refusal::EndpointUntrusted)
    ));
    let here = Endpoint::of(&std::env::temp_dir()).unwrap();
    assert_eq!(
        here.pipe_name,
        format!(r"\\.\pipe\cadrumo-runtime-{}", here.storage_identity)
    );
    assert_eq!(here.storage_identity.len(), 64);
}

#[test]
#[cfg(target_os = "macos")]
fn an_absent_endpoint_is_not_ready_and_an_unknown_or_foreign_root_names_none() {
    let endpoint = Endpoint {
        socket_leaf: format!("{:032x}.sock", u128::from(std::process::id())),
        storage_identity: "f".repeat(64),
        owner_uid: cadrumo_platform::runtime_socket::current_uid(),
    };
    let refused = match Connection::open(
        &endpoint,
        &cohort(None),
        Instant::now() + Duration::from_secs(2),
    ) {
        Ok(_) => panic!("an absent socket must not connect"),
        Err(refused) => refused,
    };
    assert!(matches!(refused, Refusal::EndpointNotReady), "{refused}");
    assert!(matches!(
        Endpoint::of(Path::new("/cadrumo-no-such-root")),
        Err(Refusal::EndpointUntrusted)
    ));
    // The root directory belongs to the system account, never to this one.
    assert!(matches!(
        Endpoint::of(Path::new("/")),
        Err(Refusal::EndpointUntrusted)
    ));
    let here = Endpoint::of(&std::env::temp_dir()).unwrap();
    assert_eq!(here.storage_identity.len(), 64);
    assert_eq!(
        here.socket_leaf,
        format!("{}.sock", &here.storage_identity[..32])
    );
    assert_eq!(
        here.owner_uid,
        cadrumo_platform::runtime_socket::current_uid()
    );
}
