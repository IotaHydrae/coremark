# Copyright (c) 2026 embeddedboys developers
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# This is the main CMakeLists file of the project. It is used to build the project
# using the CMake build system. You can find the documentation of CMake at
# https:#cmake.org/cmake/help/latest/index.html

cmake_minimum_required(VERSION 3.13)

# initialize the SDK based on PICO_SDK_PATH
# note: this must happen before project()
include(pico_sdk_import.cmake)

# set the project name
project(rpi-pico-coremark C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
SET(CMAKE_EXE_LINKER_FLAGS_DEBUG "${CMAKE_EXE_LINKER_FLAGS_DEBUG} -Wl,--print-memory-usage")
SET(CMAKE_EXE_LINKER_FLAGS_RELEASE "${CMAKE_EXE_LINKER_FLAGS_RELEASE} -Wl,--print-memory-usage")

message(STATUS "===== Global C FLAGS =====")
message(STATUS "CMAKE_C_FLAGS: ${CMAKE_C_FLAGS}")
message(STATUS "CMAKE_C_FLAGS_DEBUG: ${CMAKE_C_FLAGS_DEBUG}")
message(STATUS "CMAKE_C_FLAGS_RELEASE: ${CMAKE_C_FLAGS_RELEASE}")

message(STATUS "===== Global CXX FLAGS =====")
message(STATUS "CMAKE_CXX_FLAGS: ${CMAKE_CXX_FLAGS}")
message(STATUS "CMAKE_CXX_FLAGS_DEBUG: ${CMAKE_CXX_FLAGS_DEBUG}")
message(STATUS "CMAKE_CXX_FLAGS_RELEASE: ${CMAKE_CXX_FLAGS_RELEASE}")

if (PICO_SDK_VERSION_STRING VERSION_LESS "2.0.0")
    message(FATAL_ERROR "Raspberry Pi Pico SDK version 2.0.0 (or later) required. Your version is ${PICO_SDK_VERSION_STRING}")
endif()

# If you want debug output from USB (pass -DPICO_STDIO_USB=1) this ensures you don't lose any debug output while USB is set up
if (NOT DEFINED PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS)
    set(PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS 3000)
endif()

# initialize the Raspberry Pi Pico SDK
pico_sdk_init()

add_compile_options(-Wall
        -Wno-format          # int != int32_t as far as the compiler is concerned because gcc has int32_t as long int
        -Wno-unused-function # we have some for the docs that aren't called
        )
if (CMAKE_C_COMPILER_ID STREQUAL "GNU")
    add_compile_options(-Wno-maybe-uninitialized)
endif()

# Set all global variables here
option(OVERCLOCK_ENABLED 0)    # 1: enable, 0: disable

if(${PICO_BOARD} STREQUAL "pico" OR ${PICO_PLATFORM} STREQUAL "rp2040")
    set(PICO_BASE_SYS_CLK_KHZ 125000)
    set(COREMARK_BASE_ITRE 3000)
elseif(${PICO_BOARD} STREQUAL "pico2" OR ${PICO_PLATFORM} STREQUAL "rp2350")
    set(PICO_BASE_SYS_CLK_KHZ 150000)
    set(COREMARK_BASE_ITRE 5000)
endif()

if(OVERCLOCK_ENABLED)

    message(WARNING "Overclocking is enabled. This may damage your device. Use at own risk.")

    if(${PICO_BOARD} STREQUAL "pico" OR ${PICO_PLATFORM} STREQUAL "rp2040")
        # Overclocking profiles
        #      SYS_CLK  | FLASH_CLK | Voltage
        #  1  | 240MHz  |  120MHZ   |  1.10(V) (default, stable, recommended for most devices)
        #  2  | 266MHz  |  133MHz   |  1.10(V)
        #  3  | 360MHz  |  90MHz    |  1.20(V)
        #  4  | 400MHz  |  100MHz   |  1.30(V)
        #  5  | 416MHz  |  104MHz   |  1.30(V)
        option(OVERCLOCK_PROFILE 1)

        if(OVERCLOCK_PROFILE EQUAL 1)
            set(SYS_CLK_KHZ 240000)             # CPU clock speed
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})    # Peripheral clock speed
        elseif(OVERCLOCK_PROFILE EQUAL 2)
            set(SYS_CLK_KHZ 266000)
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})
        elseif(OVERCLOCK_PROFILE EQUAL 3)
            set(SYS_CLK_KHZ 360000)
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})
        elseif(OVERCLOCK_PROFILE EQUAL 4)
            set(SYS_CLK_KHZ 400000)
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})
        elseif(OVERCLOCK_PROFILE EQUAL 5)
            set(SYS_CLK_KHZ 416000)
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})
        else()
            message(FATAL_ERROR "Invalid overclocking profile")
        endif()
    elseif(${PICO_BOARD} STREQUAL "pico2" OR ${PICO_PLATFORM} STREQUAL "rp2350")
        # Overclocking profiles
        #      SYS_CLK  | FLASH_CLK | Voltage
        #  1  | 225MHz  |   75MHz   |  1.10(V) (default, stable, recommended for most devices)
        #  2  | 366MHz  |  122MHz   |  1.20(V)
        #  3  | 384MHz  |  128MHz   |  1.20(V)
        #  4  | 480MHz  |  160MHz   |  1.50(V)
        set(OVERCLOCK_PROFILE 1)

        if(OVERCLOCK_PROFILE EQUAL 1)
            set(SYS_CLK_KHZ 225000)             # CPU clock speed
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})    # Peripheral clock speed
        elseif(OVERCLOCK_PROFILE EQUAL 2)
            set(SYS_CLK_KHZ 366000)
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})
        elseif(OVERCLOCK_PROFILE EQUAL 3)
            set(SYS_CLK_KHZ 384000)
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})
        elseif(OVERCLOCK_PROFILE EQUAL 4)
            set(SYS_CLK_KHZ 480000)
            set(PERI_CLK_KHZ ${SYS_CLK_KHZ})
        else()
            message(FATAL_ERROR "Invalid overclocking profile")
        endif()
    endif()

else()  # OVERCLOCK_ENABLED

    message(WARNING "Overclocking is disabled.")
    set(SYS_CLK_KHZ ${PICO_BASE_SYS_CLK_KHZ}) # CPU clock speed
    set(PERI_CLK_KHZ ${SYS_CLK_KHZ})    # Peripheral clock speed

endif() # OVERCLOCK_ENABLED

include_directories(. include)

# user define common source files
file(GLOB_RECURSE COMMON_SOURCES
    core_list_join.c
    core_main.c
    core_matrix.c
    core_portme.c
    core_state.c
    core_util.c
)

# rest of your project
add_executable(${PROJECT_NAME} ${COMMON_SOURCES})
target_link_libraries(${PROJECT_NAME}
    pico_bootsel_via_double_reset
    pico_stdlib
)
target_include_directories(${PROJECT_NAME} PUBLIC .)

if(CMAKE_BUILD_TYPE STREQUAL "Release")
    string(REPLACE "\"" "\\\"" FLAGS_STR_ESCAPED "${CMAKE_C_FLAGS} ${CMAKE_C_FLAGS_RELEASE}")
elseif(CMAKE_BUILD_TYPE STREQUAL "Debug")
    string(REPLACE "\"" "\\\"" FLAGS_STR_ESCAPED "${CMAKE_C_FLAGS} ${CMAKE_C_FLAGS_DEBUG}")
else()
    
endif()

target_compile_definitions(${PROJECT_NAME}
    PRIVATE
    FLAGS_STR=\"${FLAGS_STR_ESCAPED}\"
)

math(EXPR ITERATIONS
    "${COREMARK_BASE_ITRE} * ${SYS_CLK_KHZ} / ${PICO_BASE_SYS_CLK_KHZ}"
)

target_compile_definitions(${PROJECT_NAME} PRIVATE
    ITERATIONS=${ITERATIONS}
    DEFAULT_SYS_CLK_KHZ=${SYS_CLK_KHZ}
)

# Note: If you are using a NOR flash like "w25q16". Just keep the following content.
# The maximum speed of "w25q16" is 133MHz, However, the clock speed of XIP QSPI is divided from "sys_clk".
# So, when your "sys_clk" is greater than 266MHz and default PICO_FLASH_SPI_CLKDIV=2, It will exceed the
# maximum speed, because PICO_FLASH_SPI_CLKDIV must be even, So 4 is good for most purpose, Otherwise,
# nothing should be done. These things will only useful when you overclocking the rp2040.
if(${PICO_BOARD} STREQUAL "pico" OR ${PICO_PLATFORM} STREQUAL "rp2040")
    if(${SYS_CLK_KHZ} GREATER 266000)
        set(PICO_FLASH_SPI_CLKDIV 4)
    else()
        set(PICO_FLASH_SPI_CLKDIV 2)
    endif()
elseif(${PICO_BOARD} STREQUAL  "pico2" OR ${PICO_PLATFORM} STREQUAL  "rp2350")
	set(PICO_FLASH_SPI_CLKDIV 3)
endif()

math(EXPR FLASH_CLK_KHZ "${SYS_CLK_KHZ} / ${PICO_FLASH_SPI_CLKDIV}")
math(EXPR FLASH_CLK_MHZ "${FLASH_CLK_KHZ} / 1000")
math(EXPR SYS_CLK_MHZ "${SYS_CLK_KHZ} / 1000")
message(WARNING "
    CPU speed   : ${SYS_CLK_MHZ} MHz
    Flash speed : ${FLASH_CLK_MHZ} MHz
    ITERATIONS  : ${ITERATIONS}
")
target_compile_definitions(bs2_default PRIVATE PICO_FLASH_SPI_CLKDIV=${PICO_FLASH_SPI_CLKDIV})
target_compile_definitions(${PROJECT_NAME} PRIVATE FLASH_CLK_KHZ=${FLASH_CLK_KHZ} PICO_FLASH_SPI_CLKDIV=${PICO_FLASH_SPI_CLKDIV})

pico_enable_stdio_usb(${PROJECT_NAME} 1)    # 0: disable, 1: enable
pico_enable_stdio_uart(${PROJECT_NAME} 1)   # 0: disable, 1: enable

pico_add_extra_outputs(${PROJECT_NAME}) # uf2 and more files
pico_set_binary_type(${PROJECT_NAME} default) # options: default | copy_to_ram | no_flash

# show target size info
add_custom_target(
    print-memory-usage ALL
    COMMAND arm-none-eabi-size -G ${CMAKE_PROJECT_NAME}.elf
    DEPENDS ${CMAKE_BINARY_DIR}/${CMAKE_PROJECT_NAME}.elf
    COMMENT "Print target size info"
    DEPENDS ${PROJECT_NAME}
)

# add a firmware flash target
if(${PICO_BOARD} STREQUAL "pico" OR ${PICO_PLATFORM} STREQUAL "rp2040")
	add_custom_target(
	    flash
	    COMMAND openocd -f interface/cmsis-dap.cfg -c "adapter speed 10000"
			    -f target/rp2040.cfg -s tcl -c "program ${CMAKE_PROJECT_NAME}.elf verify reset exit"
	    DEPENDS ${CMAKE_BINARY_DIR}/${CMAKE_PROJECT_NAME}.elf
	    COMMENT "Flashing firmware using CMSIS-DAP Debugger..."
	    DEPENDS ${PROJECT_NAME}
	)
elseif(${PICO_BOARD} STREQUAL  "pico2" OR ${PICO_PLATFORM} STREQUAL  "rp2350")
	add_custom_target(
	    flash
	    COMMAND openocd -f interface/cmsis-dap.cfg -c "adapter speed 10000"
		            -f target/rp2350.cfg -s tcl -c "program ${CMAKE_PROJECT_NAME}.elf verify reset exit"
	    DEPENDS ${CMAKE_BINARY_DIR}/${CMAKE_PROJECT_NAME}.elf
	    COMMENT "Flashing firmware using CMSIS-DAP Debugger..."
	    DEPENDS ${PROJECT_NAME}
	)
endif()
