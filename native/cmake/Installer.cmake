# Installer-only DLL: never included in application images or immutable runtime payloads.
include_guard(GLOBAL)
if(NOT WIN32)
  return()
endif()
set(installer_manifest "${PROJECT_SOURCE_DIR}/native/installer/Cargo.toml")
set(installer_profile "$<IF:$<CONFIG:Debug>,dev,release>")
# The crate is a cdylib and an rlib, so Cargo names its rlib and DLL without a hash. The manager
# also builds this crate as a dependency against its own cadrumo-application, and two such builds
# in one target directory overwrite each other's file (E0308 in the manager). Every Cargo command
# on this crate, including the bootstrap test in Packaging.cmake, uses this directory instead.
set(CADRUMO_INSTALLER_TARGET_DIR "${CADRUMO_PATH_CARGO}/installer")
set(CADRUMO_MSI_ADAPTER
  "${CADRUMO_INSTALLER_TARGET_DIR}/${CADRUMO_PIN_rust_target}/$<IF:$<CONFIG:Debug>,debug,release>/cadrumo_installer.dll")
set(CADRUMO_MSI_RUNNER
  "${CADRUMO_INSTALLER_TARGET_DIR}/${CADRUMO_PIN_rust_target}/$<IF:$<CONFIG:Debug>,debug,release>/cadrumo-msi-maintenance.exe")
cadrumo_cargo_command(installer_cargo)
cadrumo_build_step(installer_comment rust_installer GROUP native
  SUMMARY "compile the installer-only MSI adapter and maintenance runner"
  OUTPUTS "${CADRUMO_MSI_ADAPTER}" "${CADRUMO_MSI_RUNNER}")
add_custom_target(rust_installer
  COMMAND ${installer_cargo} build --locked --lib --bins --manifest-path "${installer_manifest}"
    --target-dir "${CADRUMO_INSTALLER_TARGET_DIR}"
    --target "${CADRUMO_PIN_rust_target}" --profile "${installer_profile}"
  BYPRODUCTS "${CADRUMO_MSI_ADAPTER}" "${CADRUMO_MSI_RUNNER}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${installer_comment}" VERBATIM)
add_dependencies(rust_installer native_contract)
if(COMMAND cadrumo_register_clean)
  cadrumo_register_clean(TARGET rust_installer PATHS "${CADRUMO_MSI_ADAPTER}" "${CADRUMO_MSI_RUNNER}")
endif()
if(BUILD_TESTING)
  cadrumo_build_step(installer_comment check_installer GROUP verification
    SUMMARY "lint the installer crate with clippy, warnings denied")
  add_custom_target(check_installer
    COMMAND ${installer_cargo} clippy --locked --all-targets --manifest-path "${installer_manifest}"
      --target-dir "${CADRUMO_INSTALLER_TARGET_DIR}"
      --target "${CADRUMO_PIN_rust_target}" --profile "${installer_profile}" -- -D warnings
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${installer_comment}" VERBATIM)
  add_dependencies(check_installer native_contract)
  add_test(NAME installer.rust
    COMMAND ${installer_cargo} test --locked --manifest-path "${installer_manifest}"
      --target-dir "${CADRUMO_INSTALLER_TARGET_DIR}"
      --target "${CADRUMO_PIN_rust_target}" --profile "${installer_profile}")
  set_tests_properties(installer.rust PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 0)
endif()
