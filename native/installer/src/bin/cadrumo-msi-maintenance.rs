//! Explicit CMake maintenance support; MSI remains the distribution format.
fn main() {
    let arguments: Vec<_> = std::env::args_os().skip(1).collect();
    if arguments.len() == 1 && matches!(arguments[0].to_str(), Some("--help" | "-h")) {
        println!("Usage: cadrumo-msi-maintenance install --plan <verified-plan.json>");
        return;
    }
    #[cfg(windows)]
    if arguments.len() == 3 && arguments[0] == "install" && arguments[1] == "--plan" {
        let result = cadrumo_installer::runner::install(std::path::Path::new(&arguments[2]));
        println!(
            "{}",
            serde_json::to_string(&result).expect("fixed maintenance result schema")
        );
        std::process::exit(if result.succeeded() { 0 } else { 1 });
    }
    eprintln!("An explicit Windows install operation and verified plan are required. Use --help.");
    std::process::exit(2);
}
