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
 */
#ifndef _BOARDS_WEACT_RP2350A_H
#define _BOARDS_WEACT_RP2350A_H

#include "boards/pico2.h"

#endif
