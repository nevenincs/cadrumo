function(cadrumo_package_bootstrap output layout source_root)
  string(JSON bootstrap_relative GET "${layout}" bootstrap)
  set(bootstrap "${source_root}/native/${bootstrap_relative}")
  if(NOT EXISTS "${bootstrap}" OR IS_DIRECTORY "${bootstrap}")
    message(FATAL_ERROR "Declared package bootstrap is missing: ${bootstrap_relative}")
  endif()
  set(${output} "${bootstrap}" PARENT_SCOPE)
endfunction()

function(cadrumo_product_inputs output source_root)
  # ARGN contains only the project directories and hook directories selected by
  # pyproject.toml. Installer generators, registry authoring tools and tests do
  # not contribute bytes to these wheels.
  file(GLOB_RECURSE inputs CONFIGURE_DEPENDS "${source_root}/src/*")
  foreach(directory IN LISTS ARGN)
    file(TO_CMAKE_PATH "${directory}" directory)
    file(GLOB_RECURSE package_inputs CONFIGURE_DEPENDS "${source_root}/${directory}/*")
    list(APPEND inputs ${package_inputs})
  endforeach()
  list(FILTER inputs EXCLUDE REGEX "/(__pycache__|\\.git|tests)/|\\.pyc$|\\.lock$|/conftest\\.py$|/\\.aeat-generated-export-transaction-|/\\.generated-export-(backup|stage)-")
  foreach(name README.md LICENSE NOTICE pyproject.toml uv.lock .gitignore .gitattributes
      dev/.gitignore dev/.gitattributes dev/source_tree.py dev/_paths.py dev/__init__.py
      dev/packaging/__init__.py dev/packaging/authority_staging.py dev/packaging/command_execution.py
      dev/packaging/google_oauth.py dev/packaging/wheel_metadata.py dev/packaging/runtime_wheelhouse_contract.py)
    if(EXISTS "${source_root}/${name}")
      list(APPEND inputs "${source_root}/${name}")
    endif()
  endforeach()
  foreach(helper product hashing cmake_build action_cache target build_toolchain layout build_paths build_timing)
    list(APPEND inputs "${source_root}/dev/packaging/native/${helper}.py")
  endforeach()
  list(REMOVE_DUPLICATES inputs)
  set(${output} "${inputs}" PARENT_SCOPE)
endfunction()

function(cadrumo_assembly_product_inputs output product_root)
  # Assembly reads installed payloads and provenance, never wheel-build scratch.
  set(${output} "${product_root}/dependencies" "${product_root}/build/product-wheels.json" PARENT_SCOPE)
endfunction()

function(cadrumo_assembly_backend_inputs output source_root backend)
  # A verification-only sibling cannot change the assembled payload.
  set(${output} "${source_root}/dev/packaging/native/platforms/${backend}.py" PARENT_SCOPE)
endfunction()

function(cadrumo_provision_helpers output source_root)
  # Enroll acquisition owners, not assembly, cleanup, tests or desktop helpers.
  set(names provision.py layout.py target.py hashing.py build_toolchain.py)
  if(ARGC GREATER 2)
    list(APPEND names "platforms/${ARGV2}.py")
    if(NOT ARGV2 STREQUAL "windows")
      list(APPEND names platforms/posix.py)
    endif()
  else()
    list(APPEND names platforms/windows.py platforms/linux.py platforms/macos.py platforms/posix.py)
  endif()
  set(helpers)
  foreach(name IN LISTS names)
    if(EXISTS "${source_root}/dev/packaging/native/${name}")
      list(APPEND helpers "${source_root}/dev/packaging/native/${name}")
    endif()
  endforeach()
  set(${output} "${helpers}" PARENT_SCOPE)
endfunction()
