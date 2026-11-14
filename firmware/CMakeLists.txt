cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# Keep the build lean: only pull in what main/ asks for.
idf_build_set_property(MINIMAL_BUILD ON)
project(modem_doorbell)

# Sound bank (built by tools/mksounds.py): "idf.py flash" also writes it to the "sounds" partition.
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/sounds/bank.bin)
    esptool_py_flash_to_partition(flash "sounds" "${CMAKE_CURRENT_SOURCE_DIR}/sounds/bank.bin")
endif()
