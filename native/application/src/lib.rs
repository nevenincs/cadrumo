//! Application management independent of GUI, Python execution and global settings.
//!
//! Callers supply release metadata and paths resolved by the platform/storage owner.
//! Inspection never provisions components or starts processes.
//!
//! `package` consumes the assembler's file inventory. `capability` combines package,
//! component and user prerequisites without downloading. `child` accepts a complete
//! platform-projected environment and creates commands with ambient inheritance disabled.
//! `component` verifies pinned ZIP bytes before extracting into a private staging tree,
//! then activates an immutable version by replacing one pointer under an OS file lock.
//! `binary` checks pinned executable bytes and target headers. `python` explicitly probes
//! interpreter identity and existing Python browser policy with bounded time and output.
//! The probe never launches a browser or downloads components. Its timeout covers child
//! execution, not synchronous file verification; only the immediate child is contained.
//!
//! Component roots must be application-owned directories. Link checks refuse existing
//! symlinks and Windows reparse points; they do not sandbox a hostile same-user writer.
//! Cancellation is checked between stream reads and filesystem stages, not during a
//! blocked transport read. Interruption recovery covers process termination; activation
//! does not claim power-loss durability. Old versions are retained for active consumers.
//! Download metadata must arrive through a trusted release channel: hashes alone do not
//! authenticate publishers. Browser revisions, storage defaults and supported target
//! declarations remain with their existing owners and are inputs to this library.

pub mod binary;
pub mod capability;
pub mod child;
pub mod component;
pub mod error;
pub mod package;
pub mod python;
pub mod value;

mod filesystem;
