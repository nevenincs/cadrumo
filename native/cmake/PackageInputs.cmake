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
  # Package trees are enumerated when the consuming action runs, never at configure time:
  # a new source file must not re-run configure. The manifest writer receives them as
  # tree lines, `tree<TAB><policy><TAB><root><TAB><subdirectory>`, in ${output}_trees.
  set(inputs)
  set(trees "tree\tproduct\t${source_root}\tsrc")
  foreach(directory IN LISTS ARGN)
    file(TO_CMAKE_PATH "${directory}" directory)
    list(APPEND trees "tree\tproduct\t${source_root}\t${directory}")
  endforeach()
  list(REMOVE_DUPLICATES trees)
  foreach(name README.md LICENSE NOTICE pyproject.toml uv.lock .gitignore .gitattributes
      dev/.gitignore dev/.gitattributes dev/source_tree.py dev/_paths.py dev/__init__.py
      dev/packaging/__init__.py dev/packaging/authority_staging.py dev/packaging/command_execution.py
      dev/packaging/google_oauth.py dev/packaging/wheel_metadata.py dev/packaging/runtime_wheelhouse_contract.py)
    if(EXISTS "${source_root}/${name}")
      list(APPEND inputs "${source_root}/${name}")
    endif()
  endforeach()
  foreach(helper product product_snapshot product_hatch_types hashing cmake_build action_selection base_dependencies action_cache target build_toolchain layout build_paths build_directory build_timing)
    list(APPEND inputs "${source_root}/dev/packaging/native/${helper}.py")
  endforeach()
  list(REMOVE_DUPLICATES inputs)
  set(${output} "${inputs}" PARENT_SCOPE)
  set(${output}_trees "${trees}" PARENT_SCOPE)
endfunction()

function(cadrumo_assembly_product_inputs output product_root)
  # Assembly reads installed payloads and provenance, never wheel-build scratch.
  set(${output} "${product_root}/dependencies" "${product_root}/build/product-wheels.json"
    "${product_root}/agent-wheel.json" PARENT_SCOPE)
endfunction()

function(cadrumo_assembly_backend_inputs output source_root backend)
  # A verification-only sibling cannot change the assembled payload.
  set(inputs "${source_root}/dev/packaging/native/platforms/${backend}.py")
  if(NOT backend STREQUAL "windows")
    foreach(helper posix posix_assembly posix_images)
      list(APPEND inputs "${source_root}/dev/packaging/native/platforms/${helper}.py")
    endforeach()
  endif()
  set(${output} "${inputs}" PARENT_SCOPE)
endfunction()

function(cadrumo_provision_helpers output source_root)
  # Enroll acquisition owners, not assembly, cleanup, tests or desktop helpers.
  set(names provision.py layout.py target.py hashing.py build_toolchain.py)
  if(ARGC GREATER 2)
    list(APPEND names "platforms/${ARGV2}.py")
    if(NOT ARGV2 STREQUAL "windows")
      list(APPEND names platforms/posix.py platforms/posix_sdk_download.py)
    endif()
  else()
    list(APPEND names platforms/windows.py platforms/linux.py platforms/macos.py platforms/posix.py platforms/posix_sdk_download.py)
  endif()
  set(helpers)
  foreach(name IN LISTS names)
    if(EXISTS "${source_root}/dev/packaging/native/${name}")
      list(APPEND helpers "${source_root}/dev/packaging/native/${name}")
    endif()
  endforeach()
  set(${output} "${helpers}" PARENT_SCOPE)
endfunction()
