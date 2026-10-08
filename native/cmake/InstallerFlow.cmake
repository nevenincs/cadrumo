# Build the native format from the exact payload produced by this source graph.
# The distribution project owns package layout, native tools and installation gates.
include_guard(GLOBAL)
set(distribution_source "${PROJECT_SOURCE_DIR}/native/cmake/distribution")
file(READ "${distribution_source}/CMakePresets.json" distribution_presets)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${distribution_source}/CMakePresets.json")
string(JSON distribution_count LENGTH "${distribution_presets}" configurePresets)
math(EXPR distribution_last "${distribution_count} - 1")
set(distribution_preset)
foreach(index RANGE ${distribution_last})
  string(JSON target GET "${distribution_presets}" configurePresets ${index} cacheVariables CADRUMO_TARGET)
  if(target STREQUAL CADRUMO_TARGET)
    if(distribution_preset)
      message(FATAL_ERROR "More than one native distribution preset owns ${CADRUMO_TARGET}")
    endif()
    string(JSON distribution_preset GET "${distribution_presets}" configurePresets ${index} name)
    string(JSON distribution_binary GET "${distribution_presets}" configurePresets ${index} binaryDir)
  endif()
endforeach()
if(NOT distribution_preset)
  message(FATAL_ERROR "No native distribution preset owns ${CADRUMO_TARGET}")
endif()
string(REPLACE "\${sourceDir}" "${distribution_source}" distribution_binary "${distribution_binary}")
string(REPLACE "\${presetName}" "${distribution_preset}" distribution_binary "${distribution_binary}")
cmake_path(NORMAL_PATH distribution_binary)

set(distribution_arguments
  "-DCADRUMO_PAYLOAD:PATH=${CADRUMO_PATH_STAGE}/$<CONFIG>/app"
  "-DCADRUMO_DEV_PYTHON:FILEPATH=${CADRUMO_DEV_PYTHON}"
  "-DCADRUMO_CHANNEL:STRING=${CADRUMO_CHANNEL}")
set(distribution_desktop "")
if(image_count GREATER 0)
  math(EXPR distribution_image_last "${image_count} - 1")
  foreach(index RANGE ${distribution_image_last})
    string(JSON desktop GET "${application_images}" ${index} desktop)
    string(JSON staged GET "${application_images}" ${index} staged)
    if(desktop AND staged)
      string(JSON distribution_desktop GET "${application_images}" ${index} package_path)
    endif()
  endforeach()
endif()
# Always pass the empty value too: a previous desktop build must not leak into a
# later runtime-only package through the distribution CMake cache.
list(APPEND distribution_arguments "-DCADRUMO_DESKTOP_EXECUTABLE:STRING=${distribution_desktop}")
set(distribution_dependencies bundle)
if(WIN32)
  list(APPEND distribution_dependencies rust_installer)
  foreach(variable CADRUMO_MSI_ADAPTER CADRUMO_MSI_RUNNER)
    get_directory_property(artifact DIRECTORY "${PROJECT_SOURCE_DIR}/native" DEFINITION "${variable}")
    if(artifact)
      list(APPEND distribution_arguments "-D${variable}:FILEPATH=${artifact}")
    endif()
  endforeach()
  if(CADRUMO_WIX_EXECUTABLE)
    list(APPEND distribution_arguments "-DCADRUMO_WIX_EXECUTABLE:FILEPATH=${CADRUMO_WIX_EXECUTABLE}")
  endif()
endif()
# Every source preset shares the enrolled distribution preset. Keep its cache
# bound to this payload until packaging finishes, even across source build trees.
# Bracket arguments preserve literal paths without a second CMake expansion.
function(cadrumo_installer_argument output value)
  set(delimiter "=")
  while("${value}" MATCHES "]${delimiter}]")
    string(APPEND delimiter "=")
  endwhile()
  set(${output} "[${delimiter}[${value}]${delimiter}]" PARENT_SCOPE)
endfunction()
cadrumo_installer_argument(lock_path "${distribution_binary}/native-installer.lock")
set(distribution_script "file(LOCK ${lock_path} GUARD PROCESS TIMEOUT 600)\n")
set(distribution_configure "${CMAKE_COMMAND}" --preset "${distribution_preset}" -S "${distribution_source}"
  ${distribution_arguments})
set(distribution_build "${CMAKE_COMMAND}" --build "${distribution_binary}" --config "$<CONFIG>" --target native-package)
foreach(command distribution_configure distribution_build)
  string(APPEND distribution_script "execute_process(COMMAND")
  foreach(argument IN LISTS ${command})
    cadrumo_installer_argument(quoted "${argument}")
    string(APPEND distribution_script " ${quoted}")
  endforeach()
  string(APPEND distribution_script " COMMAND_ERROR_IS_FATAL ANY)\n")
endforeach()
set(distribution_script_path "${PROJECT_BINARY_DIR}/native-installer-$<CONFIG>.cmake")
file(GENERATE OUTPUT "${distribution_script_path}" CONTENT "${distribution_script}")
add_custom_target(native-installer
  COMMAND "${CMAKE_COMMAND}" -P "${distribution_script_path}"
  DEPENDS ${distribution_dependencies}
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" USES_TERMINAL VERBATIM)
# The script is generated build-system state. The nested preset owns package
# outputs and cleanup; this target has no independently removable artifacts.
cadrumo_register_clean(TARGET native-installer)
