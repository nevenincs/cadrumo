# Installer-only DLL: never included in application images or immutable runtime payloads.
include_guard(GLOBAL)
if(NOT WIN32)
  return()
endif()
set(installer_manifest "${PROJECT_SOURCE_DIR}/native/installer/Cargo.toml")
set(installer_profile "$<IF:$<CONFIG:Debug>,dev,release>")
set(CADRUMO_MSI_ADAPTER
  "${CADRUMO_PATH_CARGO}/${CADRUMO_PIN_rust_target}/$<IF:$<CONFIG:Debug>,debug,release>/cadrumo_installer.dll")
set(CADRUMO_MSI_RUNNER
  "${CADRUMO_PATH_CARGO}/${CADRUMO_PIN_rust_target}/$<IF:$<CONFIG:Debug>,debug,release>/cadrumo-msi-maintenance.exe")
cadrumo_cargo_command(installer_cargo)
add_custom_target(rust_installer
  COMMAND ${installer_cargo} build --locked --lib --bins --manifest-path "${installer_manifest}"
    --target "${CADRUMO_PIN_rust_target}" --profile "${installer_profile}"
  BYPRODUCTS "${CADRUMO_MSI_ADAPTER}" "${CADRUMO_MSI_RUNNER}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
if(COMMAND cadrumo_register_clean)
  cadrumo_register_clean(TARGET rust_installer PATHS "${CADRUMO_MSI_ADAPTER}" "${CADRUMO_MSI_RUNNER}")
endif()
if(BUILD_TESTING)
  add_test(NAME installer.rust
    COMMAND ${installer_cargo} test --locked --manifest-path "${installer_manifest}"
      --target "${CADRUMO_PIN_rust_target}" --profile "${installer_profile}")
  set_tests_properties(installer.rust PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 600)
endif()
