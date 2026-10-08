//! Explicit CMake maintenance support; MSI remains the distribution format.
fn main() {
    let arguments: Vec<_> = std::env::args_os().skip(1).collect();
    if arguments.len() == 1 && matches!(arguments[0].to_str(), Some("--help" | "-h")) {
        println!(
            "Usage: cadrumo-msi-maintenance <install|unregister> --plan <verified-plan.json>\n       cadrumo-msi-maintenance remove-version --plan <verified-plan.json> --version <release>"
        );
        return;
    }
    #[cfg(windows)]
    if arguments.len() >= 3 && arguments[1] == "--plan" {
        let plan = std::path::Path::new(&arguments[2]);
        let result = match (arguments[0].to_str(), arguments.len()) {
            (Some("install"), 3) => cadrumo_installer::runner::install(plan),
            (Some("unregister"), 3) => cadrumo_installer::runner::unregister(plan),
            (Some("remove-version"), 5) if arguments[3] == "--version" => {
                let Some(release) = arguments[4].to_str() else {
                    eprintln!("The release must be UTF-8.");
                    std::process::exit(2);
                };
                cadrumo_installer::runner::remove_version(plan, release)
            }
            _ => {
                eprintln!("Invalid maintenance operation. Use --help.");
                std::process::exit(2);
            }
        };
        println!(
            "{}",
            serde_json::to_string(&result).expect("fixed maintenance result schema")
        );
        std::process::exit(if result.succeeded() { 0 } else { 1 });
    }
    eprintln!(
        "An explicit Windows maintenance operation and verified plan are required. Use --help."
    );
    std::process::exit(2);
}
