# Each native component and each staged package gets an id, sequence and date keyed on the
# content of its inputs (dev/packaging/native/build_stamp.py). Release callers freeze any of
# them for every component and package with an explicit cache value; empty means allocated.
# Caches from before allocation hold the old default number 1 and the first configure's date
# under the old help strings; those defaults are not explicit choices, so they become empty.
if(DEFINED CACHE{CADRUMO_BUILD_NUMBER})
  get_property(help CACHE CADRUMO_BUILD_NUMBER PROPERTY HELPSTRING)
  if(help STREQUAL "Explicit numeric build identifier" AND "$CACHE{CADRUMO_BUILD_NUMBER}" STREQUAL "1")
    set(CADRUMO_BUILD_NUMBER "" CACHE STRING "" FORCE)
  endif()
endif()
if(DEFINED CACHE{CADRUMO_BUILD_DATE})
  get_property(help CACHE CADRUMO_BUILD_DATE PROPERTY HELPSTRING)
  if(help STREQUAL "Build date; SOURCE_DATE_EPOCH controls the default")
    set(CADRUMO_BUILD_DATE "" CACHE STRING "" FORCE)
  endif()
endif()
set(CADRUMO_BUILD_NUMBER "" CACHE STRING "Frozen build sequence (1-65535) of every component and package; empty allocates by content")
set_property(CACHE CADRUMO_BUILD_NUMBER PROPERTY HELPSTRING
  "Frozen build sequence (1-65535) of every component and package; empty allocates by content")
if(NOT CADRUMO_BUILD_NUMBER STREQUAL "")
  if(NOT CADRUMO_BUILD_NUMBER MATCHES "^[1-9][0-9]*$" OR CADRUMO_BUILD_NUMBER GREATER 65535)
    message(FATAL_ERROR "CADRUMO_BUILD_NUMBER must be an integer from 1 to 65535, or empty to allocate by content")
  endif()
endif()
set(CADRUMO_BUILD_ID "" CACHE STRING "Frozen build id (YYYYMMDDNN) of every component and package; empty allocates by content")
if(NOT CADRUMO_BUILD_ID STREQUAL "" AND NOT CADRUMO_BUILD_ID MATCHES "^[0-9]{8}[0-9][0-9]+$")
  message(FATAL_ERROR "CADRUMO_BUILD_ID must be YYYYMMDD followed by a two-or-more-digit iteration, or empty")
endif()
set(CADRUMO_BUILD_DATE "" CACHE STRING "Frozen ISO UTC build date; empty dates each new identity (SOURCE_DATE_EPOCH applies)")
set_property(CACHE CADRUMO_BUILD_DATE PROPERTY HELPSTRING
  "Frozen ISO UTC build date; empty dates each new identity (SOURCE_DATE_EPOCH applies)")
if(NOT CADRUMO_BUILD_DATE STREQUAL "" AND NOT CADRUMO_BUILD_DATE MATCHES
    "^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z$")
  message(FATAL_ERROR "CADRUMO_BUILD_DATE must be an ISO UTC timestamp such as 2026-10-19T08:00:00Z, or empty")
endif()
