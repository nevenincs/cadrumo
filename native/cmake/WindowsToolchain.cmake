# CMake reads this before compiler detection, including try_compile projects.
file(READ "${CMAKE_CURRENT_LIST_DIR}/../toolchain.json" cadrumo_toolchain)
string(JSON cadrumo_msvc GET "${cadrumo_toolchain}" msvc)
string(JSON cadrumo_sdk GET "${cadrumo_toolchain}" windows_sdk)
set(CMAKE_GENERATOR_PLATFORM x64 CACHE STRING "CADRUMO architecture")
set(CMAKE_GENERATOR_TOOLSET "version=${cadrumo_msvc}" CACHE STRING "CADRUMO MSVC toolset" FORCE)
set(CMAKE_SYSTEM_VERSION "${cadrumo_sdk}" CACHE STRING "CADRUMO Windows SDK" FORCE)
