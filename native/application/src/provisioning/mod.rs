//! Component provisioning: the engine that downloads, installs, checks and removes the
//! browser and the local AI for every surface.
//!
//! `pins` reads the declarative package data naming the only bytes the engine accepts.
//! `url` reduces an address to what a download hop is judged by.

pub mod pins;
pub mod url;
