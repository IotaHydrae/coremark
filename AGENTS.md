# coremark —— 台架的工作规则

## Skills（本仓遵守）

本仓的一切工作遵循工作区 `../AGENTS.md` 约定的四份 skill。**摘要随仓携带**（离线可读），
完整版在工作区 `skills/`。

| skill | 本仓副本 | 一句话 |
| --- | --- | --- |
| Repository Exploration | [`skills/developer-repository-exprolation/Summary.md`](skills/developer-repository-exprolation/Summary.md) | 先理解再修改；证据优先于直觉 |
| Knowledge | [`skills/developer-knowledge/Summary.md`](skills/developer-knowledge/Summary.md) | 首屏结论、事实分级、信息预算、漂移检查 |
| Testing | [`skills/developer-testing/Summary.md`](skills/developer-testing/Summary.md) | tests/tools 分层、oracle 声明、退出码、N 次测量 |
| Code Quality | [`skills/developer-code-quality/Summary.md`](skills/developer-code-quality/Summary.md) | **能跑 ≠ 完成**；可读性有硬标准 |

### 动手前的四行闸门（**强制**）

改任何代码或配置**之前**先写出这四行 ✓。**第 1 行或第 4 行写不出来就停手** ✗ —— 那是在猜 ✗。

```text
已验证：<确认了什么，凭据是什么：代码/实测/构建日志>
仍未知：<还没确认的；不许用推测填空>
最小改动：<只改一处，为什么是这一处>
生效验证：<如何证明改动真的生效：探针 / grep 生成物 / 构建日志里的编译行>
```

**先确认仪器，再相信读数** ✓ —— 宏没被注入、文件没被编译、配置被 defconfig 覆盖，
这三件事的症状都是"结果莫名其妙" ✗。


> 本仓是**测试台**：找出芯片/板子在哪儿不再可靠，留下一个**已知可用**的配置，并把它回流成
> pico-turbo 的 `boards/<board>.cmake`。 通用知识库/测试约定见 [`../AGENTS.md`](../AGENTS.md)，
> 这里只写本仓特有的铁律、硬件纪律和构建方式。

## TL;DR

- **这是台架，不是产品**：产物是「某块板已知可用的配置」，回流到
  [pico-turbo](https://github.com/IotaHydrae/pico-turbo) 的 `boards/<board>.cmake`。
- **时钟/电压/flash 分频都归 pico-turbo**，本仓不再长第二张 profile 表或分频算术。
- **一条命令**：`tools/probe.py --board <board>`（阶梯 + 双核 + 10 次 soak），产出
  `report.md`、`results.json`（可断点续跑）和一份 `boards/<board>.cmake` 提案。
- **判定标准是应用自己打的证据**：flash 回读逐字节一致、`Correct operation validated`、
  无 CoreMark 错误、状态行里**实测**时钟 = 请求时钟；soak 看 `COREMARK-REPEAT: run N of M`
  数到 M，不看 reader 收到几行。
- **索引**：知识库 [docs/README.md](docs/README.md)；**未决问题 [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)**；
  实测 [RANKINGS.md](RANKINGS.md)、[TOOLCHAINS.md](TOOLCHAINS.md)、
  [rpi-pico/MEASUREMENTS.md](rpi-pico/MEASUREMENTS.md)。

## 与 pico-turbo 的分工

**每个数字都要在 pico-turbo 那边有落点，否则它只是这里的一条观察。** 时钟、电压和 flash
分频属于应用真正链接的那个库，不属于测量它们用的 benchmark：pico-turbo 决定一个配置
（board 文件里的上限 + 档位 + 默认档），本仓只负责**验证**它、找它的边界并提议更新。

本仓不写分频算术：旧版在 RP2350 上算出过奇数 DIV 3，被**库自己的偶数检查**拒了。 2026-09
核对 SDK 源码后确认：偶数限制是 RP2040 的（`w25q080`/`at25sf128a` 里
`#error PICO_FLASH_SPI_CLKDIV must be even`），RP2350 的 `w25q080` 只查上限，该检查已按板子
区分（`_FLASH_REQUIRES_EVEN`）。

## 铁律

1. **未经明确指令，不要 `git commit`，更不要 `git push`。** 提交规范：`user.name` =
   `Wooden Chair`，`user.email` = `hua.zheng@embeddedboys.com`，`git commit -s`，内核风格
   提交信息，一个逻辑改动一个提交。
2. **时钟、电压、flash 分频由 pico-turbo 负责**，见上节。本仓不再有自己的 profile 表。
3. **`ITERATIONS` 必须让一次运行 ≥10 秒**（CoreMark 自己的成绩规则）：默认按频率缩放、
   双核再乘 2，实测每次约 11.8–12 秒。 **时钟要取库解析后的值**
   （`PICO_TURBO_RESOLVED_CLK_KHZ`），不是 `PICO_TURBO_SYS_CLK_KHZ`：用 board 档位构建时
   后者是空的，会退回按 stock 频率算 —— 实测 420 MHz 的档位构建只跑 3.8 秒，被 CoreMark
   判成 `Errors detected`（数据其实是对的）。 固定次数只在"两次跑相同工作量做对比"时用，
   且要检查总时长：150 MHz 合适的次数在 500 MHz 会短到被判无效。
4. **`MEM_STATIC` 与多 context 不能共存**（CoreMark 自己 `#error` 拒绝），别为了省栈去改。
5. **跑分必须留得下证据：`stdio_usb` 默认会丢输出** ✗ —— 没有主机打开端口时，SDK 直接把
   写进去的字符丢掉。 soak 每次重启都要重新枚举，读取器晚一秒，**整次运行的日志就没了**
   （实测 REP=3 只拿到 2 次运行的结果，计数器却是 3）。 构建里设了
   `PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS`（20000 ms），让每次启动先等端口再开跑
   （等待发生在计时之前，不影响成绩）。 **判定 soak 的基准是应用自己打的
   `COREMARK-REPEAT: run N of M` 计数与 `all M runs finished`，不是 reader 数到的行数。**
   - **少跑几次要问芯片为什么，而且在回写之前问** ✓：控制台只说明"哪些次没报出来"，
     原因决定结论要不要改。 三样东西按重要性排：**①PC（最关键）** —— 实测一次 7/10 的 soak，
     PC 停在 `core_stop_parallel`，那是 core 0 在 `while (!s_core1_done)` 里**无超时地等
     core 1**，CFSR 为 0、没有任何 fault ⇒ 真正的结论是"**core 1 不再前进**"（它同时解释了
     为什么状态行/banner 都在、成绩却没有）。 **②CFSR**（非 0 = 真 fault，配合 PC 定位）。
     **③运行计数 + banner 数** —— `portable_fini` 的顺序是"出成绩 → 读计数 +1 → 打印
     `run N of M` → 写回 → 重启"，所以计数与成绩行数都是**已完成**的次数，单看计数分不出
     "下一次没启动"和"下一次跑中途挂了" ⇒ 要配 `CoreMark benchmark running` 的 banner 数：
     有 banner 没成绩 = 那一次启动了并在里面停住；连 banner 都没有 = 那一次根本没起来。
   - **计数在 watchdog scratch 的 slot 6（魔数 `0x636d726b`）+ slot 7（计数）** ✓。 两个平台
     scratch 都从 `+0x0C` 起（RP2040 `0x40058000`、RP2350 `0x400D8000`）⇒ 魔数在 `+0x24`、
     计数在 `+0x28`。 **slot 4（`+0x1C`）是 SDK 的** ✗：按 "SCRATCH4" 去读会拿到一个干净的 0，
     然后得出一个关于没人写过的寄存器的自信结论 —— **读计数前先验魔数**。
   - **顺序也是关键** ✗：`put_back()` 会写回上一个通过的镜像，而那个镜像自己跑完会把计数
     清零 ⇒ 实测这样只得到过一个 0；探针在 `put_back()` **之前**读，把判决写进 `results.json`
     与报告的 Soak 段。 **少跑几次不再记成 `ok`** ✓。
   - **跑分期间别让主机休眠** ✗：合盖/挂起会让 reader 掉设备、整轮**一个成绩都留不下**，而现场
     看起来像"板子在这个频率上挂了"（实测误判过一次 420 MHz：状态行写着
     `420000 measured, vreg sel 15, usb ok`，成绩却没有，PC 停在 `timer_time_reached`）。
     **状态行 + 没成绩 + PC 停在计时相关函数**，先怀疑主机再怀疑板子；`systemctl suspend`、
     切换用户会话、拔掉主机侧 USB 都能造成一样的现场。
6. **`Errors detected` 不等于数据错**：CoreMark 把"没跑满 10 秒"也算 error（`total_errors > 0`
   就打印它）。 数据错看 `[i]ERROR! ... crc ... - should be ...` 这类逐项行和状态行；
   `tools/probe_parse.py` 把两者分开（`errors` vs `item_errors`）。
7. **只有已验证的结论**：每个数字要能说出**板子、时钟、电压、context 数、迭代数，以及编译器**
   六要素。 编译器那部分的完整证据在 [TOOLCHAINS.md](TOOLCHAINS.md) 与
   [docs/compiler-flags.md](docs/compiler-flags.md)，这里只留不变量：
   - **编译器是数字的一部分** ✓：同板同频，GCC 13.2.1 与 16.2.0 相差 **1.052990**，且这个倍数
     在 150–520 MHz 上六位有效数字不变。 指定编译器用 `--toolchain <前缀>`，它会**断言**这次
     构建真的用了那个前缀（SDK 会静默回退到 PATH ✗）；天梯脚本是 `tools/toolchain-ladder.sh`。
   - **编译选项也是被测变量** ✓：`tools/probe.py --cflags=-O2`（以 `-` 开头的值要用 `=`）把选项
     记进每个数据点；实测 `-O2` −0.41%、`-Os` −17.9%，且两者在 150 与 520 MHz 上**损失比例完全
     相同** ⇒ 分数只由执行的指令数决定，与取指/体积无关。
   - **打包方不是变量** ✓：13.x 那一代四个独立打包方读 1543.051 / 1543.052 / 1543.052 / 1543.051
     ⇒ 按**版本号**就能跟别人比，但必须带上版本号。
   - **"哪个编译器更好"离开基准没有意义** ✓：同一个编译器对，四个负载给出的是 Embench
     `matmult-int` 快 **27.5%**、Dhrystone 快 1.2%、`statemate` 慢 1.9%、CoreMark 慢 5.3% ⇒
     天梯读作"**CoreMark 说**"，不能读作"这颗芯片上"。 而且两者在双核上倍数不同 ⇒ 双核成绩
     只能在同一编译器内比。
   - **一定要重复** ✗：实测十次运行里出现过一次坏读数（输出完整、自检 10/10 全过，但计时段
     时间戳少了 4.8 秒，分数因此高 13%，原因至今不明）⇒ 编译器对照至少 3 次交替重复，看中位数
     与离散度；**单次运行不足以下结论**。 该坏读数是
     [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 的第一条。

## 构建与运行

```bash
export PICO_SDK_PATH=<pico-sdk>
cmake -S rpi-pico -B build -DPICO_BOARD=pico2 \
      -DPICO_TURBO_DIR=<pico-turbo> \
      -DPICO_TURBO_SYS_CLK_KHZ=520000 -DPICO_TURBO_VREG_VOLTAGE=VREG_VOLTAGE_1_60
cmake --build build -j
cmake --build build --target flash-erase   # 先擦再写；verify 不是证据，见纪律 2
```

一键整套测量（时钟阶梯 + flash 分频阶梯 + 双核 + soak），接上探针即可：

```bash
tools/probe.py --board pico_w                    # 默认：阶梯 + 双核 + 10 次 soak
tools/probe.py --board pico2 --soak 30 --flash-ladder
tools/probe.py --identify-only                   # 只认板子，不动它
tools/probe.py --points 240000,300000 --soak 0   # 指定点（≤10000 当 MHz）、不跑 soak
```

| 开关 | 默认 | 作用 |
| --- | --- | --- |
| `COREMARK_ITERATIONS` | 0 | 0 = 按频率（双核 ×2）缩放，保证 ~12 s；给数字 = 固定次数做等量对比 |
| `COREMARK_REPEAT` | 1 | 跑 n 次，中间用 watchdog 重启并计数（520 MHz 双核实测 ≈50 次 ≈ 28 分钟） |
| `COREMARK_MULTITHREAD` | 1 | 2 = 每个核一个 context（电流最大，对电压最狠） |
| `PICO_TURBO_BINARY_TYPE` | default | `copy_to_ram` 用来把 flash 因素排除掉 |

每行运行都会打一条自描述状态（请求/配置/**硬件计数器实测**的时钟、稳压档位、flash、
clk_peri、USB 是否 48 MHz）—— 判定以它为准。 `probe.py` 的 `--mt` 默认 2、`--soak` 默认 10，
支持 `--version/--quiet/--verbose/--timeout`；退出码用工作区约定（3 = 环境错误，不是 FAIL）。

## 硬件纪律（与 pico-turbo 同一套，别省）

> 标~~删除线~~的条目**已被取代**，保留是因为它记着教训；**现行**做法看它后面那条。

1. **批量前先跑一个点**：①构建 ✓ ②**回读 flash 与构建产物比对** ✓ ③拿到成绩 ✓
   ④状态里实测时钟 = 请求时钟 ✓。 四项齐了才开循环。
2. **`openocd program ... verify` 可能谎报 "Verified OK"** ✗；用回读比对（`probe.py` 走
   erase → bootrom → picotool → dump 回读，或 picotool 自己的校验）。 CMake 里的
   `flash` / `flash-erase` 目标只是给人用的便利，它们结尾的 `verify` **不算证据**。
3. **调试会话结束时不能把核留在 halt** ✗（bootrom 的 USB 会一起下线，板子从 `lsusb`
   消失）。 诊断/手测会话以 `reset run` 收尾（没擦写过时 `resume` 也行；擦写过就必须
   `reset run`，见纪律 9 的历史与 8b 的现行路径）。 **跑分期间别碰 SWD**：CoreMark 用墙钟
   计时，一次 halt 就让那一轮成绩偏低（CRC 仍然正确，所以它是一条"validated 但分数异常"
   的假信号）。
4. **只有调试器时的完整烧写路径**（探针没接复位线、镜像又没有 USB 复位接口）：
   `init` → `halt` → `flash erase_sector 0 0 last` → `flash write_image <elf>` →
   `verify_image <elf>` → `dump_image` 回读比对 → `reset run`。 `program` 内部要先复位，
   没复位线就报 `Unable to reset target`；`verify_image` 在 RP2350 上会报
   "error executing cortex_m crc algorithm"，**只有回读比对能当证据**。
5. **擦空 flash 就是没有按键时的 BOOTSEL** ✓：`flash erase_sector 0 0 last` 之后芯片自己
   以 `2e8a:000f` 出现（空白 RP2350 会进 bootrom 的 USB），picotool 又能用；卡在一个跑完
   的 app 上时这是唯一不靠手的回头路。 **别把空板留在那儿**，擦完马上写回。
6. **不是每个镜像都提供 USB 复位接口** ✗：`picotool reboot --pid 0x0009 -f -u` 对这个
   CoreMark 镜像报 "no 0009 to reset"。 启动用**确定能成**的那条（调试器 `reset run`，
   或 bootrom 的 `--pid 0x000f`）。
7. **读取器要在烧写之前启动** ✓，否则读的是上一个应用的残留输出；而且它的 CDC 握手
   （line coding + DTR）**必须重试** ✗ —— SDK 把"没有主机"当作"输出丢掉"，一次
   `[Errno 110]` 就换来空日志（实测 30 次 soak 全丢，计数器却在正常递增）。 判定基准始终是
   应用自己打的计数。
8. ~~**烧写和启动放进同一个 openocd 会话**，以 `reset run` 收尾~~ —— **已被 8b 取代**。
   保留的理由：它记着当时的教训 —— `resume` 会让旧镜像跑进刚被擦掉的区域而挂死。
9. **烧写路径用"擦空 → bootrom → picotool"** ✓（`probe.py` 的 `flash_and_run()`）：
   ①调试器擦空（芯片自己进 BOOTSEL，RP2040 `2e8a:0003`、RP2350 `2e8a:000f`）②
   `picotool load -v` 写入（它的校验可信，openocd 的不可信）③在 bootrom 状态下回读比对
   ④`picotool reboot` 通过 bootrom 做**真芯片复位**。 第③步结尾必须 `resume`：核停在 halt
   会把 bootrom 的 USB 一起带走，picotool 就找不到东西可重启。 两个偶发失败的步骤都做了
   检查+重试：**擦除**（openocd 的 flash 驱动要在 SRAM 借 64 KB 工作区，RP2350 上是
   `0x20010000`，被刚 halt 的 app 占着时会失败，报
   `Could not allocate stack for flash programming code` —— 不检查的话 flash 没擦、picotool
   往旧镜像上写，最后由回读比对兜住、白费一轮）和 **picotool**（bootrom 刚枚举出来时它的
   第一次访问可能扑空，报 `No accessible RP-series devices in BOOTSEL mode were found`）。
   理由：探针没有 nRESET 线，**两个平台**的 `reset run` 都是 vectreset（只改 PC）。 RP2040 上
   它让 SSI 停在非读模式（XIP 读出错位数据）；RP2350 上它偶发地把 boot2→crt0 的第一次交接
   打成 **INVSTATE**（CFSR `0x01020001`，故障 PC 落在 `platform_entry`），而 flash 逐字节
   正确、`reset run` 还报成功 —— 一度看起来像"板子在 150 MHz 挂了"。 bootrom 自己的复位不会。
10. **诊断/单点手测的调试器会话收尾** ✗（自动化流程走 8b，不走这条路）。 实测对照（同一
    ELF）：halt 过而不用 `reset run` 收尾 ⇒ 写完什么都不跑；带 `reset run` ⇒ 正常出分。
    另有一次带 `reset run` 仍不出分，PC `0xfffffffe`（double fault）、XIP 读出的数据整条
    右移一个 nibble，而写入与校验都正常 ⇒ 当时推断是**回读 flash（`dump_image`）把 SSI 留在
    非读模式，vectreset 修不回来**；救命路径是**真芯片复位**（擦空 → `2e8a:0003` BOOTSEL →
    picotool 写入+重启）。 当时据此让 `probe.py` 收尾为"清 `SCRATCH4` → 写看门狗 `CTRL`
    TRIGGER → `reset run`"；**这条路后来被 8b 取代**：看门狗触发和随后的 `reset run` 在
    RP2350 上是竞态（复位后 bootrom 正在启动，vectreset 把 PC 拽走 ⇒ 偶发 lockup），而
    bootrom 自己的复位没有这个问题。
11. **过快的 flash 分频会让板子变成软件复位救不回来的砖** ✗（boot2 里的分频每次复位都会
    重演；实测 DIV 4 @520 MHz 只能按 BOOTSEL 回来）。
12. **调试器用来定位**：PC 在 `core_list_find` = 在跑；`isr_hardfault` = 真挂；
    PC 在 bootrom = 镜像没起来；PC 在 `core_stop_parallel` = core 0 无超时等 core 1。

## 相关

- [docs/README.md](docs/README.md) —— 知识库索引（范围 / 索引表 / 维护约定）。
- [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) —— 未决问题与待测项，按危害排序。
- [RANKINGS.md](RANKINGS.md)、[TOOLCHAINS.md](TOOLCHAINS.md)、
  [rpi-pico/MEASUREMENTS.md](rpi-pico/MEASUREMENTS.md) —— 实测与本仓的结论。
- [tools/probe.py](tools/probe.py) + [tools/probe_parse.py](tools/probe_parse.py) —— 测量与判定；
  离线测试 `python3 -m unittest discover -s tests`。
- [`../AGENTS.md`](../AGENTS.md) —— 工作区通用知识库/测试约定。

## 驱动工具的方式（与工作区规范同源）

- **不许盲目 `sleep`，不许 blanket 超时** ✓ —— 用**轮询就绪**（0.2 s 间隔）+ **秒级超时** ✓。
  硬件测试必须**显式定义就绪检测**，不要依赖"设备恰好已经跑着" ✓。
- 反例：`sleep 22` + `timeout 300` ⇒ 明明 0.4 s 就有结论的操作拖到几分钟 ✗。
- 正解：`usb.core.find` 轮询 ✓、控制请求 0.5 s 超时 ✓、shell 命令 `timeout 10` ✓。
