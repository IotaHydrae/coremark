# AGENTS.md

本仓库的工作规则，供 AI agent（以及人）在改动前先读一遍。

**实测结果**：[`RANKINGS.md`](RANKINGS.md) 是总表（天梯：每块板的最佳已验证配置、每时钟
效率、跨平台换算、soak 记录、各自的墙）；[`TOOLCHAINS.md`](TOOLCHAINS.md) 是**编译器天梯**
（同一块板、同一套配置，六个 GCC 版本的单核/双核分数）；[`rpi-pico/MEASUREMENTS.md`](rpi-pico/MEASUREMENTS.md)
是逐块板的原始表格；时钟/电压/flash 那一侧的解读在
[pico-turbo 的 measurements](https://github.com/IotaHydrae/pico-turbo/blob/main/docs/measurements.md)。

## 这个仓库是什么，以及结果去哪儿

**本仓库是测试台**：它的职责是找出芯片/板子在哪儿不再可靠，并留下一个**已知可用**的配置。
测出来的稳定配置**要回流到 [pico-turbo](https://github.com/IotaHydrae/pico-turbo)**，落成
`boards/<board>.cmake`（上限 + 档位 + 默认档）—— 因为时钟、电压、flash 分频属于应用真正
链接的那个库，而不是测量它们用的 benchmark。`tools/probe.py` 就是这条回路的一条命令：
测量 → 出报告 → 提议 `boards/<board>.cmake`。凡是在这里下的结论，都要在那边有落点。

---

## 铁律

1. **未经明确指令，不要 `git commit`，更不要 `git push`。**
2. **时钟、电压、flash 分频都由 pico-turbo 负责**，本仓库不要再长出自己的 profile 表或分频
   算术（原来那份在 RP2350 上会算出奇数 DIV 3，当时是**库自己的偶数检查**把它拒了；
   2026-09 核对 SDK 源码后确认：偶数限制是 RP2040 的，RP2350 的 w25q080 boot2 只查上限，
   该检查已按板子区分）。
3. **`ITERATIONS` 必须让一次运行 ≥10 秒**（CoreMark 自己的成绩规则）：默认按频率缩放、
   双核再乘 2。**时钟要取库解析后的值**（`PICO_TURBO_RESOLVED_CLK_KHZ`），不是
   `PICO_TURBO_SYS_CLK_KHZ`：用 board 档位构建时后者是空的，会退回按 stock 频率算 ——
   实测 420 MHz 的档位构建只跑 3.8 秒，被 CoreMark 判成 `Errors detected`（数据其实是对的）。
   固定次数只在"两次跑相同工作量做对比"时用，并且要检查总时长 —— 150 MHz 合适的次数在
   500 MHz 会短到被判无效。
4. **`MEM_STATIC` 与多 context 不能共存**（CoreMark 自己 `#error` 拒绝），别为了省栈去改。
5. **跑分必须留得下证据：`stdio_usb` 默认会丢输出** ✗ —— 没有主机打开端口时，SDK 直接把
   写进去的字符丢掉。soak 每次重启都要重新枚举，读取器晚一秒，**整次运行的日志就没了**
   （实测 REP=3 只拿到 2 次运行的结果，计数器却是 3，差点被当成"少跑了一次"）。
   构建里已经设了 `PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS`，让每次启动先等端口再开跑
   （等待发生在计时之前，不影响成绩）。**判定 soak 的基准是应用自己打的
   `COREMARK-REPEAT: run N of M` 计数与 `all M runs finished`，不是 reader 数到的行数。**
5a. **soak 少跑几次时，要问芯片自己为什么 —— 而且在回写之前问** ✓：控制台只说明"哪些次没
   报出来"，说明不了原因，而原因决定结论要不要改。三样东西按重要性排：**①PC（最关键）** ——
   实测一次 7/10 的 soak，PC 停在 `core_stop_parallel`，那是 core 0 在 `while (!s_core1_done)`
   里**无超时地等 core 1**，CFSR 为 0、没有任何 fault ⇒ 真正的结论是"**core 1 不再前进**"，
   而这个结论只有 PC 说得出来（它同时解释了为什么状态行/banner 都在、成绩却没有）。
   **②CFSR**（非 0 = 真 fault，配合 PC 定位）；**③运行计数** —— 应用的 `portable_fini` 顺序是
   "出成绩 → 读计数 +1 → 打印 `run N of M` → 写回 → 重启"，所以计数与成绩行数都是**已完成
   的次数**，单看计数分不出"下一次没启动"和"下一次跑中途挂了" ⇒ 要配 `CoreMark benchmark
   running` 的 **banner 数**：有 banner 没成绩 = 那一次启动了并在里面停住；连 banner 都没有
   = 那一次根本没起来（板子没启动）。
   **计数在 watchdog scratch 的 slot 6（魔数 `0x636d726b`）+ slot 7（计数）** ✓，两个平台的
   scratch 都从 `+0x0C` 起（RP2040 `0x40058000`、RP2350 `0x400D8000`）⇒ 魔数在 `+0x24`、
   计数在 `+0x28`。**slot 4 是 SDK 的** ✗：按"SCRATCH4"去读会拿到一个干净的 0，然后得出一个
   关于没人写过的寄存器的自信结论 —— 这个坑踩过一次，**读计数前先验魔数**。
   **顺序也是关键** ✗：`put_back()` 会写回上一个通过的镜像，而那个镜像自己跑完会把计数清零 ⇒
   实测这样只得到过一个 0；探针现在在 `put_back()` **之前**读，把判决写进 `results.json` 与
   报告的 Soak 段。**少跑几次不再记成 `ok`** ✓：重复跑的意义就在于每一次都报出来。
5b. **跑分期间别让主机休眠** ✗：合盖/挂起会让 reader 掉设备、整轮**一个成绩都留不下**，
   而现场看起来像"板子在这个频率上挂了"（实测就是这样误判过一次 420 MHz：日志里状态行
   明明写着 `420000 measured, vreg sel 15, usb ok`，成绩却没有，调试器读到 PC 停在
   `timer_time_reached`）。**状态行 + 没成绩 + PC 停在计时相关函数**，这个组合先怀疑主机，
   再怀疑板子。同理，`sudo systemctl suspend`、切换用户会话、拔掉主机侧 USB 都能造成一样的现场。
6. **`Errors detected` 不等于数据错**：CoreMark 把"没跑满 10 秒"也算 error。判定要看
   `[i]ERROR! ... crc` 这类逐项行和状态行。
7. **只有已验证的结论**：每个数字要能说出板子、时钟、电压、context 数、迭代数，**以及编译器**
   （见 `RANKINGS.md` 第 8 节：同板同频，GCC 13.2.1 与 16.2.0 相差 1.052990，且这个倍数在
   150–520 MHz 上六位有效数字不变；六个版本的完整天梯在 [`TOOLCHAINS.md`](TOOLCHAINS.md)，
   **13.2.0 是这六档里最快的，16.1.0 与 16.2.0 完全同级**）。编译选项也是被测变量之一：
   `tools/probe.py --cflags=-O2`（以 `-` 开头的值要用 `=`）会把选项记进每个数据点；实测
   `-O2` −0.41%、`-Os` −17.9%，且两者在 150 与 520 MHz 上**损失比例完全相同** ⇒ 分数只由
   执行的指令数决定，与取指/体积无关。指定编译器用 `--toolchain <前缀>`：它会**断言**这次
   构建真的用了那个前缀（SDK 会静默回退到 PATH ✗），天梯脚本是
   `tools/toolchain-ladder.sh`。

## 提交与身份

- `user.name` = `Wooden Chair`，`user.email` = `hua.zheng@embeddedboys.com`；`git commit -s`
- 内核风格提交信息；一个逻辑改动一个提交

## 构建与运行

```bash
export PICO_SDK_PATH=<pico-sdk>
cmake -S rpi-pico -B build -DPICO_BOARD=pico2 \
      -DPICO_TURBO_DIR=<pico-turbo> \
      -DPICO_TURBO_SYS_CLK_KHZ=520000 -DPICO_TURBO_VREG_VOLTAGE=VREG_VOLTAGE_1_60
cmake --build build -j
cmake --build build --target flash-erase   # 先擦再写再校验
```

一键跑完整套测量（时钟阶梯 + flash 分频阶梯 + 双核 + soak），接上探针即可，产出
`report.md`、`results.json`（可断点续跑）和一份可用的 `boards/<board>.cmake`：

```bash
tools/probe.py --board pico_w                    # 默认：阶梯 + 双核 + 10 次 soak
tools/probe.py --board pico2 --soak 30 --flash-ladder
tools/probe.py --identify-only                   # 只认板子，不动它
tools/probe.py --points 240000,300000 --soak 0   # 指定点、不跑 soak
```

| 开关 | 默认 | 作用 |
| --- | --- | --- |
| `COREMARK_ITERATIONS` | 0 | 0 = 按频率（双核 ×2）缩放，保证 ~12 s；给数字 = 固定次数做等量对比 |
| `COREMARK_REPEAT` | 1 | 跑 n 次，中间用 watchdog 重启并计数（520 MHz 双核实测 ≈50 次 ≈ 28 分钟） |
| `COREMARK_MULTITHREAD` | 1 | 2 = 每个核一个 context（电流最大，对电压最狠） |
| `PICO_TURBO_BINARY_TYPE` | default | `copy_to_ram` 用来把 flash 因素排除掉 |

每行运行都会打一条自描述状态（请求/配置/**硬件计数器实测**的时钟、稳压档位、flash、
clk_peri、USB 是否 48 MHz）—— 判定以它为准。

## 硬件纪律（与 pico-turbo 同一套，别省）

1. **批量前先跑一个点**：①构建 ✓ ②**回读 flash 与构建产物比对** ✓ ③拿到成绩 ✓
   ④状态里实测时钟 = 请求时钟 ✓。四项齐了才开循环。
2. **`openocd program ... verify` 可能谎报 "Verified OK"** ✗；用 `flash-erase` 目标或
   picotool，并回读比对。
3. **调试会话结束时不能把核留在 halt** ✗（bootrom 的 USB 会一起下线，板子从 `lsusb`
   消失）。以 `reset run` 收尾（没擦写过时 `resume` 也行；擦写过就必须 `reset run`，
   见纪律 8）。**跑分期间别碰 SWD**：CoreMark 用墙钟计时，一次 halt 就让那一轮成绩偏低
   （CRC 仍然正确，所以它是一条"validated 但分数异常"的假信号）。
4. **只有调试器时的完整烧写路径**（探针没接复位线、镜像又没有 USB 复位接口）：
   `init` → `halt` → `flash erase_sector 0 0 last` → `flash write_image <elf>` →
   `verify_image <elf>` → `dump_image` 回读比对 → `reset run`。`program` 内部要先复位，
   没复位线就报 `Unable to reset target`；`verify_image` 在 RP2350 上会报
   "error executing cortex_m crc algorithm"，**只有回读比对能当证据**。
5. **擦空 flash 就是没有按键时的 BOOTSEL** ✓：`flash erase_sector 0 0 last` 之后芯片自己
   以 `2e8a:000f` 出现（空白 RP2350 会进 bootrom 的 USB），picotool 又能用；卡在一个跑完
   的 app 上时这是唯一不靠手的回头路。**别把空板留在那儿**，擦完马上写回。
6. **不是每个镜像都提供 USB 复位接口** ✗：`picotool reboot --pid 0x0009 -f -u` 对这个
   CoreMark 镜像报 "no 0009 to reset"。启动用**确定能成**的那条（调试器 `reset run`，
   或 bootrom 的 `--pid 0x000f`）。
7. **读取器要在烧写之前启动** ✓，否则读的是上一个应用的残留输出；而且它的 CDC 握手
   （line coding + DTR）**必须重试** ✗ —— SDK 把"没有主机"当作"输出丢掉"，一次
   `[Errno 110]` 就换来空日志（实测 30 次 soak 全丢，计数器却在正常递增）。没收到任何数据
   时要反复重申握手，判定的基准始终是应用自己打的计数。
8. ~~**烧写和启动放进同一个 openocd 会话**，以 `reset run` 收尾~~ —— **已被 8b 取代**：
   `reset run` 是 vectreset，两个平台都会偶发地在启动交接处出问题（见 8b）。这条留在这里
   是因为它记着当时的教训：`resume` 会让旧镜像跑进刚被擦掉的区域而挂死。
8b. **烧写路径用"擦空 → bootrom → picotool"** ✓：`flash_and_run()` 现在是①调试器擦空
   （芯片自己进 BOOTSEL，两个平台都成立：RP2040 `2e8a:0003`、RP2350 `2e8a:000f`）②
   `picotool load -v` 写入（它的校验可信，openocd 的不可信）③在 bootrom 状态下回读比对
   ④`picotool reboot` 通过 bootrom 做**真芯片复位**。第③步结尾必须 `resume`：核停在 halt 会把
   bootrom 的 USB 一起带走，picotool 就找不到东西可重启。
   两个都会偶发失败的步骤都做了检查+重试：**擦除**（openocd 的 flash 驱动要在 SRAM 借
   64 KB 工作区，RP2350 上是 `0x20010000`，被刚 halt 的 app 占着时会失败，报
   `Could not allocate stack for flash programming code` —— 不检查的话 flash 没擦、picotool
   往旧镜像上写，最后由回读比对兜住、白费一轮）和 **picotool**（bootrom 刚枚举出来时它的
   第一次访问可能扑空，报 `No accessible RP-series devices in BOOTSEL mode were found`）。
   理由：探针没有 nRESET 线，**两个平台**的 `reset run` 都是 vectreset（只改 PC）。RP2040 上
   它让 SSI 停在非读模式（XIP 读出错位数据）；RP2350 上它偶发地把 boot2→crt0 的第一次交接
   打成 **INVSTATE**（CFSR `0x01020001`，故障 PC 落在 `platform_entry`），而 flash 逐字节
   正确、`reset run` 还报成功 —— 一度看起来像"板子在 150 MHz 挂了"。bootrom 自己的复位不会。
9. **诊断/单点手测时的调试器会话收尾** ✗（自动化流程见 8b：它不走这条路）。实测对照（同一 ELF）：halt 过而不用
   `reset run` 收尾 ⇒ 写完什么都不跑（这是 `tools/probe.py` 第一版的失败原因）；带 `reset run`
   ⇒ 正常出分。另有一次带 `reset run` 仍不出分，PC `0xfffffffe`（double fault）、XIP 读出的
   数据整条右移一个 nibble，而写入与校验都正常 ⇒ 推断是**回读 flash（`dump_image`）把 SSI
   留在非读模式，vectreset 修不回来**；实测的救命路径是**真芯片复位**（擦空 → `2e8a:0003`
   BOOTSEL → picotool 写入+重启 ✓）。当时据此让 `probe.py` 收尾为"清 `SCRATCH4` → 写看门狗
   `CTRL` TRIGGER → `reset run`"；**这条路后来被 8b 取代**：看门狗触发和随后的 `reset run`
   在 RP2350 上是竞态（复位后 bootrom 正在启动，vectreset 把 PC 拽走 ⇒ 偶发 lockup），
   而 bootrom 自己的复位没有这个问题。
10. **过快的 flash 分频会让板子变成软件复位救不回来的砖** ✗（boot2 里的分频每次复位都会
   重演；实测 DIV 4 @520 MHz 只能按 BOOTSEL 回来）。
11. **调试器用来定位**（PC 在 `core_list_find` = 在跑；`isr_hardfault` = 真挂；
   PC 在 bootrom = 镜像没起来）。

## 结果与现状

| 板子 | 单核 | 双核 | 上限 |
| --- | --- | --- | --- |
| 幸狐 Pico 2 | 150→422.71、300→845.41、520→1465.38、540→1521.74 it/s | 300→1512.07、520→**2612.7**（36 次连续通过） | 564 过、570 起不来 |
| 官方 Pico 2 | 520→1465.38、546→1538.64、552→1555.56、558→1572.47、564→1589.37 | 520→**2622.08**（50 次连续通过，极差 0.0002%） | 564 过、570 挂（已核实） |
| 官方 Pico W（RP2040） | 125→236.42、240→453.93、264→499.32、300→567.41、360→680.90、396→748.99、420→**794.39**、440→832.21 | 420→**1417.30**、440→**1484.79**（1.784×；各 20/30 次连续通过，极差 ≤0.0009%） | **≥440**（1.30 V，DIV 4 = 110 MHz flash 也撑住；合宙板 440 锁死 ⇒ 顶端是板子的） |
| WeAct RP2350A | 520→**1465.40**（GCC 16.2.0）、520→**1543.05**（GCC 13.2.1，见第 8 节） | 520→2613.91 单点过 ✗，但 **10 次 soak 三次都没跑满**（6/6/7 ✓，PC 停在 `core_stop_parallel` = core 0 无超时等 core 1 ✓）；13.2.1 下曾 10/10（2760.73） | 520 单核过、546 硬挂；**双核 520 是边缘**，400–520 之间的双核墙未定位 |

分数与频率**线性**：RP2350 从 150 到 564 MHz、RP2040 从 125 到 420 MHz 都是，RP2040 侧
**1.891 it/s per MHz 一路不变**（连 flash 时钟从 60 涨到 105 MHz 都一样），说明这个负载没
有内存/flash 墙。双核加速比两个平台都是 **1.78×**（第二核受限于共享的存储）—— 但这个因子
本身是**编译器**的数：六个 GCC 版本上实测在 **1.7745–1.8319** 之间（见 `TOOLCHAINS.md`）⇒
双核成绩的比较只能在同一编译器内做 ✓。
两块板同频双核成绩相差 0.36%（幸狐 2612.7 / 官方 2622.08），但**极差差三个数量级**
（0.39% vs 0.0002%）—— 同一颗芯片，差别在板子的供电，抖动比失败先出现。
**但"单点过"不等于"配置可用"**：WeAct 在 520 双核单点能过（2613.91 ✓），10 次 soak 却三次
都没跑满 ✓ ⇒ **一堵墙和一次失败是两件事**：板子能扛的最高时钟（520）比它能扛的最重负载
（双核 520 边缘）高一点，这正是"上限"与"可用配置"的区别。

## 待办

- Pico W 的真正顶端（440 已过），以及 105 MHz 以上的 flash 分频（越过 QSPI 接口极限）。
- 幸狐板的整套 flash 分频阶梯（只有"≤57 稳、78.75 出错"两个点）。
- **WeAct 的双核墙**：520 单核过、520 双核跑不满 10 次 soak ⇒ 400–520 之间哪一档双核稳，
  还没测（`--points 480000 --mt 2 --soak 10`）。这条会改 pico-turbo 里那块板的档位语义。
- **RP2040 侧换个编译器测一个点**：能不能 1.0530 还没验证（见 `RANKINGS.md` 第 8 节）。
- **工具链天梯还缺非 GCC 的行**：ARM 官方 release 工具链、`arm-none-eabi-clang`，以及 15.x
  （Arch 没为这个目标发过）—— 见 `TOOLCHAINS.md` 的"Not measured yet"。
