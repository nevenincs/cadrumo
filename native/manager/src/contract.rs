//! The native contract projected from its Python owners by the contract generator.
//!
//! The build supplies the generated `contract.rs` through `CADRUMO_CONTRACT_RS`, as it does
//! for the platform crate, so the runtime exit-reason table and the environment names have
//! one owner. A build without the projection fails to compile instead of guessing values.

include!(env!(
    "CADRUMO_CONTRACT_RS",
    "CADRUMO_CONTRACT_RS must name the contract generator's contract.rs"
));
