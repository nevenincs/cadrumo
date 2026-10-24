//! Component provisioning: the engine that downloads, installs, checks and removes the
//! browser and the local AI for every surface.
//!
//! `pins` reads the declarative package data naming the only bytes the engine accepts.
//! `url` reduces an address to what a download hop is judged by. `proxy` reads the
//! operator's proxy settings, `connection` reaches a publisher through them, `http` is the
//! small client codec spoken over that connection, and `transfer` fetches one pinned
//! archive with the hop, retry and resume rules; `network` is the preflight that classifies
//! whether an item's hosts can be reached. `failure` holds the closed failure
//! categories every outcome is reported in.

pub mod connection;
pub mod failure;
pub(crate) mod http;
pub mod network;
pub mod pins;
pub mod proxy;
pub mod transfer;
pub mod url;

#[cfg(test)]
pub(crate) mod test_servers;
