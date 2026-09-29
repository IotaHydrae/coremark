/*
 * Board: WeAct Studio RP2350A core board (V1.0).  RP2350A rev 2, Winbond
 * W25Q32FV/JV 4 MB.
 *
 * Everything this firmware touches is a Pico 2's: the chip, the pinout, the size
 * of the flash.  What is not the same is what the bench measures -- 520 MHz
 * validated and 546 MHz hard-faulted here, where the official board and the
 * Luckfox clone both reach 564 -- and that is not a pin definition, so it does not
 * live in this file.  It goes to pico-turbo's boards/weact_rp2350a.cmake, which is
 * keyed by PICO_BOARD.
 *
 * The name exists so that file can exist.  A clone sharing `pico2` inherits a
 * ceiling measured on somebody else's board, which is exactly the mistake this
 * repository keeps finding: a board's name is not a specification (RANKINGS.md,
 * section 7).  If a V2.0 of this board turns up, it wants a name of its own for
 * the same reason -- nobody has measured whether the two are the same board.
 *
 * The three declarations below are not decoration.  The SDK does not read this file
 * as C when it decides what the board *is*: `cmake/generic_board.cmake` reads it line
 * by line and pattern-matches for `pico_board_cmake_set(...)`, and it does not follow
 * `#include`.  So `#include "boards/pico2.h"` -- which pico2.h itself invites -- gives
 * the C side of a Pico 2 and none of the CMake side, `PICO_PLATFORM` stays at its
 * rp2040 default, and a build of this board is Cortex-M0+ code whose UF2 carries the
 * rp2040 family id.  Measured, by configuring one: `PICO_PLATFORM:STRING=rp2040`,
 * `PICO_PLATFORM_CMAKE_FILE=.../rp2040.cmake`, and picotool refusing the image with
 * "Family ID 'rp2040' cannot be downloaded anywhere".  (C tolerates these lines
 * because pico.h defines them to nothing, which is how pico2.h can carry them too.)
 */
#ifndef _BOARDS_WEACT_RP2350A_H
#define _BOARDS_WEACT_RP2350A_H

pico_board_cmake_set(PICO_PLATFORM, rp2350)
pico_board_cmake_set_default(PICO_FLASH_SIZE_BYTES, (4 * 1024 * 1024))
pico_board_cmake_set_default(PICO_RP2350_A2_SUPPORTED, 1)

#include "boards/pico2.h"

#endif
