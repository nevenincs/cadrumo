cmake_minimum_required(VERSION 4.4)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source distribution build directory")
endif()
include(../Identity.cmake)
file(READ "${CADRUMO_SOURCE_ROOT}/native/toolchain.json" toolchain)
string(JSON required_cmake GET "${toolchain}" cmake)
if(NOT CMAKE_VERSION VERSION_EQUAL required_cmake)
  message(FATAL_ERROR "CMake ${required_cmake} is required")
endif()
project(CADRUMO VERSION "${CADRUMO_ID_VERSION}"
  DESCRIPTION "${CADRUMO_ID_DESCRIPTION}" HOMEPAGE_URL "${CADRUMO_ID_HOMEPAGE}"
  SPDX_LICENSE "${CADRUMO_ID_LICENSE}" LANGUAGES NONE)
set(CADRUMO_PAYLOAD "" CACHE PATH "Assembled native payload containing data/package-manifest.json")
set(CADRUMO_DESKTOP_EXECUTABLE "" CACHE STRING "Payload-relative real desktop executable; empty for runtime-only packages")
if(NOT IS_DIRECTORY "${CADRUMO_PAYLOAD}")
  message(FATAL_ERROR "Set CADRUMO_PAYLOAD to an assembled native payload")
endif()
if(CADRUMO_DESKTOP_EXECUTABLE)
  set(desktop_args --desktop "${CADRUMO_DESKTOP_EXECUTABLE}")
endif()
set(installation_helper "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.installation)
include(../CachedCommand.cmake)
set(installation_inputs "${CADRUMO_PAYLOAD}" "${CADRUMO_PATH_GENERATED}/identity.json"
  "${CMAKE_BINARY_DIR}/build-paths.json" "${CADRUMO_SOURCE_ROOT}/LICENSE" "${CADRUMO_SOURCE_ROOT}/NOTICE"
  "${CADRUMO_SOURCE_ROOT}/docs/_static/cadrumo-favicon.svg")
foreach(helper installation installation_filesystem distribution_prepare build_paths hashing layout package_inventory docs_stage)
  list(APPEND installation_inputs "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/${helper}.py")
endforeach()
cadrumo_cached_command(installation_command installation_prepare INPUTS ${installation_inputs}
  OUTPUTS "${CADRUMO_PATH_INSTALLATION_STAGE}" "${CADRUMO_PATH_INSTALLATION_METADATA}")
add_custom_target(installation_prepare ALL
  COMMAND ${installation_command} "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.distribution_prepare
    --payload "${CADRUMO_PAYLOAD}" --identity "${CADRUMO_PATH_GENERATED}/identity.json"
    --build "${CMAKE_BINARY_DIR}" ${desktop_args}
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)
add_dependencies(installation_prepare setup-native-builder)
cadrumo_register_clean(TARGET installation_prepare PATHS "${CADRUMO_PATH_INSTALLATION_WORK}")
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
  set(CMAKE_INSTALL_PREFIX "${CMAKE_BINARY_DIR}/install" CACHE PATH "Explicit development installation prefix" FORCE)
endif()
configure_file(VerifyInstall.cmake.in "${CMAKE_BINARY_DIR}/VerifyInstall.cmake" @ONLY)
install(SCRIPT "${CMAKE_BINARY_DIR}/VerifyInstall.cmake")
install(DIRECTORY "${CADRUMO_PATH_INSTALLATION_STAGE}/" DESTINATION . USE_SOURCE_PERMISSIONS)
set(CADRUMO_UNINSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}" CACHE PATH "Exact prefix previously installed with cmake --install")
set(CADRUMO_UNINSTALL_RECEIPT "${CADRUMO_PATH_INSTALLATION_METADATA}/installation.json"
  CACHE FILEPATH "Receipt identifying the installed prefix; older receipts are retained in installation/receipts")
add_custom_target(uninstall
  COMMAND ${installation_helper} uninstall --prefix "${CADRUMO_UNINSTALL_PREFIX}"
    --receipt "${CADRUMO_UNINSTALL_RECEIPT}"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)

set(CPACK_PACKAGE_NAME "${CADRUMO_ID_NAME}")
set(CPACK_PACKAGE_VENDOR "${CADRUMO_ID_PUBLISHER}")
set(CPACK_PACKAGE_CONTACT "${CADRUMO_ID_CONTACT}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "${CADRUMO_ID_DESCRIPTION}")
set(CPACK_PACKAGE_HOMEPAGE_URL "${CADRUMO_ID_HOMEPAGE}")
set(CPACK_PACKAGE_VERSION "${CADRUMO_ID_VERSION}")
set(CPACK_PACKAGE_INSTALL_DIRECTORY "${CADRUMO_ID_NAME}")
set(CPACK_PACKAGE_FILE_NAME "${CADRUMO_ID_PACKAGE_NAME}-${CADRUMO_ID_VERSION}-${CADRUMO_TARGET}")
set(CPACK_PACKAGE_DIRECTORY "${CADRUMO_PATH_PACKAGES}")
set(CPACK_BUILD_CONFIG Release)
set(CPACK_SYSTEM_NAME "${CADRUMO_TARGET}")
set(CPACK_PACKAGING_INSTALL_PREFIX /)
set(CPACK_VERBATIM_VARIABLES YES)
configure_file("${CADRUMO_SOURCE_ROOT}/LICENSE" "${CMAKE_BINARY_DIR}/LICENSE.txt" COPYONLY)
set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_BINARY_DIR}/LICENSE.txt")
if(CADRUMO_TARGET STREQUAL "windows-x86-64")
  set(CPACK_GENERATOR WIX)
  configure_file(WindowsMsiGate.cmake.in "${CMAKE_BINARY_DIR}/WindowsMsiGate.cmake" @ONLY)
  set(CPACK_PROJECT_CONFIG_FILE "${CMAKE_BINARY_DIR}/WindowsMsiGate.cmake")
  set(CPACK_WIX_VERSION 4)
  set(CPACK_WIX_ARCHITECTURE x64)
  set(CPACK_WIX_INSTALL_SCOPE perMachine)
  set(CPACK_WIX_UPGRADE_GUID "${CADRUMO_ID_UPGRADE_CODE}")
  set(CPACK_WIX_PROGRAM_MENU_FOLDER "${CADRUMO_ID_NAME}")
  set(CPACK_WIX_PROPERTY_ARPURLINFOABOUT "${CADRUMO_ID_HOMEPAGE}")
  set(CPACK_WIX_PROPERTY_ARPHELPLINK "${CADRUMO_ID_HOMEPAGE}/issues")
  file(READ "${CADRUMO_PAYLOAD}/data/package-manifest.json" payload_manifest)
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CADRUMO_PAYLOAD}/data/package-manifest.json")
  string(JSON payload_image_count LENGTH "${payload_manifest}" layout application_images)
  set(installed_manager FALSE)
  if(payload_image_count GREATER 0)
    math(EXPR last_payload_image "${payload_image_count} - 1")
    foreach(index RANGE 0 ${last_payload_image})
      string(JSON payload_image_target GET "${payload_manifest}" layout application_images ${index} target)
      if(payload_image_target STREQUAL "rust_manager")
        set(installed_manager TRUE)
      endif()
    endforeach()
  endif()
  if(CADRUMO_DESKTOP_EXECUTABLE OR installed_manager)
    set(CPACK_WIX_EXTRA_SOURCES "${CADRUMO_PATH_INSTALLATION_METADATA}/Desktop.wxs")
    set(CPACK_WIX_PATCH_FILE "${CADRUMO_PATH_INSTALLATION_METADATA}/DesktopPatch.xml")
  endif()
elseif(CADRUMO_TARGET MATCHES "^linux-")
  set(CPACK_GENERATOR "DEB;RPM")
  set(CPACK_DEBIAN_PACKAGE_NAME "${CADRUMO_ID_PACKAGE_NAME}")
  set(CPACK_RPM_PACKAGE_NAME "${CADRUMO_ID_PACKAGE_NAME}")
  set(CPACK_DEBIAN_PACKAGE_MAINTAINER "${CADRUMO_ID_PUBLISHER} <${CADRUMO_ID_CONTACT}>")
  set(CPACK_DEBIAN_PACKAGE_SECTION utils)
  string(REPLACE "glibc-" "" glibc_floor "${CADRUMO_ID_COMPATIBILITY_FLOOR}")
  set(CPACK_DEBIAN_PACKAGE_DEPENDS "libc6 (>= ${glibc_floor})")
  set(CPACK_DEBIAN_PACKAGE_SHLIBDEPS ON)
  set(CPACK_RPM_PACKAGE_LICENSE "${CADRUMO_ID_LICENSE}")
  set(CPACK_RPM_PACKAGE_REQUIRES "glibc >= ${glibc_floor}")
  set(CPACK_RPM_PACKAGE_AUTOREQPROV ON)
  set(CPACK_RPM_PACKAGE_RELOCATABLE OFF)
  set(CPACK_RPM_EXCLUDE_FROM_AUTO_FILELIST_ADDITION /opt)
  if(CADRUMO_TARGET STREQUAL "linux-aarch64")
    set(CPACK_DEBIAN_PACKAGE_ARCHITECTURE arm64)
    set(CPACK_RPM_PACKAGE_ARCHITECTURE aarch64)
  else()
    set(CPACK_DEBIAN_PACKAGE_ARCHITECTURE amd64)
    set(CPACK_RPM_PACKAGE_ARCHITECTURE x86_64)
  endif()
elseif(CADRUMO_TARGET STREQUAL "macos-arm64")
  set(CPACK_GENERATOR DragNDrop)
  set(CPACK_DMG_VOLUME_NAME "${CADRUMO_ID_NAME}")
  set(CPACK_DMG_DISABLE_APPLICATIONS_SYMLINK OFF)
endif()
set(distribution_archive "${CADRUMO_PATH_PACKAGES}/${CPACK_PACKAGE_FILE_NAME}.zip")
include(CPack)
function(cadrumo_distribution_package target generator)
  set(msi_guard)
  if(generator STREQUAL "WIX")
    set(msi_guard COMMAND "${CMAKE_COMMAND}" -E chdir "${CADRUMO_SOURCE_ROOT}"
      "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.windows_msi
      reject-combined --build "${CMAKE_BINARY_DIR}")
  endif()
  add_custom_target(${target}
    ${msi_guard}
    COMMAND "${CMAKE_CPACK_COMMAND}" --config "${CMAKE_BINARY_DIR}/CPackConfig.cmake"
      -C "$<CONFIG>" -G "${generator}"
    DEPENDS installation_prepare USES_TERMINAL VERBATIM)
endfunction()
if(CADRUMO_TARGET STREQUAL "windows-x86-64")
  add_custom_target(msi-author
    COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.windows_msi author
      --build "${CMAKE_BINARY_DIR}" --identity "${CADRUMO_PATH_GENERATED}/identity.json" ${desktop_args}
    DEPENDS installation_prepare
    WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)
  cadrumo_register_clean(TARGET msi-author PATHS "${CADRUMO_PATH_INSTALLATION_METADATA}/wix")
  if(installed_manager)
    find_program(CADRUMO_WIX_EXECUTABLE NAMES wix DOC "WiX 5+ compiler for scoped MSI products")
    set(msi_build_helper "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.windows_msi_build)
    set(msi_build_arguments --build "${CMAKE_BINARY_DIR}"
      --identity "${CADRUMO_PATH_GENERATED}/identity.json" ${desktop_args})
    add_custom_target(msi
      COMMAND ${msi_build_helper} build ${msi_build_arguments} --wix "${CADRUMO_WIX_EXECUTABLE}"
      DEPENDS msi-author WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
    add_custom_target(msi-verify
      COMMAND ${msi_build_helper} verify ${msi_build_arguments}
      DEPENDS msi WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
    # Readiness is an independent refusal, so missing compilers do not hide the
    # lifecycle blockers. It never installs products or changes login registration.
    add_custom_target(check-msi-installation
      COMMAND ${msi_build_helper} check-installation ${msi_build_arguments}
      WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)
    cadrumo_register_clean(TARGET msi PATHS "${CADRUMO_PATH_PACKAGES}/msi")
  else()
    cadrumo_distribution_package(msi WIX)
  endif()
elseif(CADRUMO_TARGET MATCHES "^linux-")
  cadrumo_distribution_package(deb DEB)
  cadrumo_distribution_package(rpm RPM)
elseif(CADRUMO_TARGET STREQUAL "macos-arm64")
  cadrumo_distribution_package(dmg DragNDrop)
endif()
# The generated `package` target builds ALL first; `zip` selects the portable
# install-based archive independently of host installer tool availability.
cadrumo_cached_command(distribution_zip_command zip
  INPUTS "${CADRUMO_PATH_INSTALLATION_STAGE}" "${CADRUMO_PATH_INSTALLATION_METADATA}"
    "${CMAKE_BINARY_DIR}/CPackConfig.cmake" "${CMAKE_BINARY_DIR}/cmake_install.cmake"
    "${CMAKE_BINARY_DIR}/VerifyInstall.cmake" "${CMAKE_CPACK_COMMAND}"
  OUTPUTS "${distribution_archive}")
add_custom_target(zip COMMAND ${distribution_zip_command} "${CMAKE_CPACK_COMMAND}"
  --config "${CMAKE_BINARY_DIR}/CPackConfig.cmake" -C "$<CONFIG>" -G ZIP
  DEPENDS installation_prepare USES_TERMINAL VERBATIM)
add_custom_target(clean-package
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cleanup "${CMAKE_BINARY_DIR}" packages
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)
