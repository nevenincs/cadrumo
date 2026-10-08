//! Native package maintenance admission. This library never launches product processes.
pub mod admission;
#[cfg(windows)]
pub mod custody;
#[cfg(windows)]
pub mod owner;
#[cfg(windows)]
pub mod runner;
#[cfg(windows)]
pub mod windows;
