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
//!
//! `items` declares the two setup items and their locations, `state` derives each item's
//! state from what a check observed, `plan` builds the approved plan and its digest with
//! the free-space rule, `activity` keeps the per-item writer lock and the crash-surviving
//! activity record, and `receipts` keeps the evidence of what was installed.
//!
//! `local_ai` installs, runs and checks the local AI's program and models.
//!
//! `browser` installs the bundled driver's pinned Chromium builds into the layout it reads.
//!
//! `engine` composes the items into status, plan, setup, verify, cancel and remove, the
//! one engine every surface reads. `protocol` is the `components` role's line protocol
//! over it, and `role_host` resolves an installation for the role from its own process.

pub mod activity;
pub mod browser;
pub mod connection;
pub mod engine;
pub mod failure;
pub(crate) mod http;
pub mod items;
pub mod local_ai;
pub mod network;
pub mod pins;
pub mod plan;
pub mod protocol;
pub mod proxy;
pub mod receipts;
#[cfg(feature = "platform")]
pub mod role_host;
pub mod state;
pub mod transfer;
pub mod url;

#[cfg(any(test, feature = "test-support"))]
pub mod test_servers;
