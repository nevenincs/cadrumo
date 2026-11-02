use super::framing::{sha256_hex, text};
use super::refusal::Refusal;
use cadrumo_platform::runtime_connect::ConnectRefusal;
use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

#[cfg(windows)]
use cadrumo_platform::runtime_pipe;
#[cfg(windows)]
pub use cadrumo_platform::runtime_pipe::ConnectCancellation as OpenCancellation;
#[cfg(unix)]
use cadrumo_platform::runtime_socket;
#[cfg(unix)]
pub use cadrumo_platform::runtime_socket::ConnectCancellation as OpenCancellation;
#[cfg(windows)]
pub type RuntimeChannel = cadrumo_platform::runtime_pipe::Pipe;
#[cfg(unix)]
pub type RuntimeChannel = cadrumo_platform::runtime_socket::Socket;

/// The endpoint a storage root's runtime serves, derived from the root alone.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Endpoint {
    #[cfg(windows)]
    pub pipe_name: String,
    /// The runtime's entry in this account's private socket namespace.
    #[cfg(unix)]
    pub socket_leaf: String,
    /// The hex digest both peers compare in the handshake.
    pub storage_identity: String,
    /// The account that owns the root; the runtime's process must be its own.
    #[cfg(windows)]
    pub owner_sid: String,
    /// The account that owns the root; the runtime's process must be its own.
    #[cfg(unix)]
    pub owner_uid: u32,
}

impl Endpoint {
    /// The endpoint of `storage_root`, followed through links as the runtime
    /// follows it. A root that cannot be identified names no endpoint.
    #[cfg(windows)]
    pub fn of(storage_root: &Path) -> Result<Self, Refusal> {
        let identity =
            runtime_pipe::storage_identity(storage_root).map_err(|_| Refusal::EndpointUntrusted)?;
        let storage_identity = sha256_hex(identity.text().as_bytes());
        Ok(Self {
            pipe_name: format!(r"\\.\pipe\cadrumo-runtime-{storage_identity}"),
            storage_identity,
            owner_sid: identity.owner_sid,
        })
    }

    /// The endpoint of `storage_root`, followed through links as the runtime
    /// follows it. A root that cannot be identified names no endpoint.
    #[cfg(unix)]
    pub fn of(storage_root: &Path) -> Result<Self, Refusal> {
        let identity = runtime_socket::storage_identity(storage_root)
            .map_err(|_| Refusal::EndpointUntrusted)?;
        let storage_identity = sha256_hex(identity.text().as_bytes());
        Ok(Self {
            socket_leaf: format!("{}.sock", &storage_identity[..32]),
            storage_identity,
            owner_uid: identity.uid,
        })
    }
}

/// Connects to the endpoint's runtime as its verified same-account peer.
pub(super) fn connect(
    endpoint: &Endpoint,
    deadline: Instant,
    cancellation: Arc<OpenCancellation>,
) -> Result<RuntimeChannel, ConnectRefusal> {
    #[cfg(windows)]
    let (name, owner) = (&endpoint.pipe_name, &endpoint.owner_sid);
    #[cfg(unix)]
    let (name, owner) = (&endpoint.socket_leaf, endpoint.owner_uid);
    RuntimeChannel::connect_cancellable(name, owner, deadline, cancellation)
}
