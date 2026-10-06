use cadrumo_application::{
    binary::{self, Architecture, BinaryExpectation, BinaryFormat},
    error::Error,
    value::Sha256Digest,
};
use sha2::{Digest, Sha256};

#[test]
fn running_native_executable_matches_host_and_rejects_wrong_cpu_format_and_digest() {
    let path = std::env::current_exe().unwrap();
    let digest = Sha256Digest::new(format!(
        "{:x}",
        Sha256::digest(std::fs::read(&path).unwrap())
    ))
    .unwrap();
    let host = BinaryExpectation::host().unwrap();
    binary::verify(&path, &digest, host).unwrap();
    let wrong_cpu = BinaryExpectation {
        architecture: Architecture::Arm,
        ..host
    };
    assert!(matches!(
        binary::verify(&path, &digest, wrong_cpu),
        Err(Error::Incompatible(_))
    ));
    let wrong_format = BinaryExpectation {
        format: BinaryFormat::Wasm,
        ..host
    };
    assert!(matches!(
        binary::verify(&path, &digest, wrong_format),
        Err(Error::Incompatible(_))
    ));
    let wrong_digest = Sha256Digest::new("00".repeat(32)).unwrap();
    assert!(matches!(
        binary::verify(&path, &wrong_digest, host),
        Err(Error::Integrity(_))
    ));
}

#[test]
fn refuses_nonbinary_even_with_matching_digest() {
    // The system temporary directory can have a linked ancestor (macOS /var).
    // Keep this format check separate from the production link-refusal check.
    let root = std::path::Path::new(env!("CARGO_TARGET_TMPDIR"));
    std::fs::create_dir_all(root).unwrap();
    let directory = tempfile::tempdir_in(root).unwrap();
    let path = directory.path().join("not-binary");
    std::fs::write(&path, b"text").unwrap();
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
    }
    let digest = Sha256Digest::new(format!("{:x}", Sha256::digest(b"text"))).unwrap();
    let result = binary::verify(&path, &digest, BinaryExpectation::host().unwrap());
    assert!(matches!(result, Err(Error::Incompatible(_))), "{result:?}");
}
