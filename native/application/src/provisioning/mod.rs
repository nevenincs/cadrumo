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

pub mod activity;
pub mod browser;
pub mod connection;
pub mod failure;
pub(crate) mod http;
pub mod items;
pub mod local_ai;
pub mod network;
pub mod pins;
pub mod plan;
pub mod proxy;
pub mod receipts;
pub mod state;
pub mod transfer;
pub mod url;

#[cfg(test)]
pub(crate) mod test_servers;
