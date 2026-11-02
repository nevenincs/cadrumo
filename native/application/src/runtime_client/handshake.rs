use super::endpoint::{Endpoint, OpenCancellation, RuntimeChannel, connect};
use super::framing::{DOCUMENT_FRAME, document, frame, is_uuid, read_frame, text};
use super::refusal::Refusal;
use serde_json::{Map, Value, json};
use std::sync::Arc;
use std::time::Instant;

pub(super) const PROTOCOL_VERSION: u64 = 4;

/// What this process expects the runtime to be: the same installed version
/// and, where both know one, the same published authority generation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Cohort {
    pub product_version: String,
    pub authority_generation: Option<String>,
}

/// The runtime's readiness, as its handshake stated it. The boot id is not a bearer.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Hello {
    pub boot_id: String,
    pub product_version: String,
    pub storage_identity: String,
    pub authority_generation: Option<String>,
}

/// The client's hello. A connection that asks for lifecycle notices receives
/// `E` frames between replies; one that does not never does.
pub(super) fn hello_document(
    endpoint: &Endpoint,
    cohort: &Cohort,
    lifecycle_notices: bool,
) -> Value {
    let mut hello = json!({
        "kind": "client_hello",
        "protocol_version": PROTOCOL_VERSION,
        "product_version": cohort.product_version,
        "storage_identity": endpoint.storage_identity,
        "authority_generation": cohort.authority_generation,
    });
    if lifecycle_notices {
        hello["lifecycle_notices"] = json!("v1");
    }
    hello
}

/// Connects to `endpoint` before `deadline`, verifies the runtime as its
/// pipe's same-account peer, and completes the cohort handshake. Every
/// connection to the runtime, an event-reading one or a view stream, starts here.
pub(crate) fn handshake(
    endpoint: &Endpoint,
    cohort: &Cohort,
    lifecycle_notices: bool,
    deadline: Instant,
) -> Result<(RuntimeChannel, Hello), Refusal> {
    handshake_cancellable(
        endpoint,
        cohort,
        lifecycle_notices,
        deadline,
        Arc::new(OpenCancellation::new().map_err(Refusal::Io)?),
    )
}

pub(super) fn handshake_cancellable(
    endpoint: &Endpoint,
    cohort: &Cohort,
    lifecycle_notices: bool,
    deadline: Instant,
    cancellation: Arc<OpenCancellation>,
) -> Result<(RuntimeChannel, Hello), Refusal> {
    let pipe = connect(endpoint, deadline, cancellation)?;
    let payload = serde_json::to_vec(&hello_document(endpoint, cohort, lifecycle_notices))
        .map_err(|_| Refusal::InvalidFrame)?;
    pipe.write_all(&frame(DOCUMENT_FRAME, &payload)?, deadline)?;
    let (kind, payload) = read_frame(&pipe, deadline)?;
    if kind != DOCUMENT_FRAME {
        return Err(Refusal::InvalidFrame);
    }
    let hello = server_hello(&document(&payload)?, endpoint, cohort)?;
    Ok((pipe, hello))
}

pub(super) fn server_hello(
    document: &Map<String, Value>,
    endpoint: &Endpoint,
    cohort: &Cohort,
) -> Result<Hello, Refusal> {
    if text(document, "kind") != Some("server_hello")
        || document.get("protocol_version").and_then(Value::as_u64) != Some(PROTOCOL_VERSION)
    {
        return Err(Refusal::InvalidFrame);
    }
    let boot_id = text(document, "boot_id")
        .filter(|id| is_uuid(id))
        .ok_or(Refusal::InvalidFrame)?;
    let product_version = text(document, "product_version").ok_or(Refusal::InvalidFrame)?;
    let storage_identity = text(document, "storage_identity").ok_or(Refusal::InvalidFrame)?;
    let authority_generation = text(document, "authority_generation").map(str::to_owned);
    if product_version != cohort.product_version
        || matches!(
            (&authority_generation, &cohort.authority_generation),
            (Some(observed), Some(expected)) if observed != expected
        )
    {
        return Err(Refusal::VersionMismatch);
    }
    if storage_identity != endpoint.storage_identity {
        return Err(Refusal::RootMismatch);
    }
    Ok(Hello {
        boot_id: boot_id.to_owned(),
        product_version: product_version.to_owned(),
        storage_identity: storage_identity.to_owned(),
        authority_generation,
    })
}
