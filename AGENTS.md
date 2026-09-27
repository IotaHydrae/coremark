# AGENTS.md

本仓库的工作规则，供 AI agent（以及人）在改动前先读一遍。

**实测结果在 [`rpi-pico/MEASUREMENTS.md`](rpi-pico/MEASUREMENTS.md)**（本仓库）与
[pico-turbo 的 measurements](https://github.com/IotaHydrae/pico-turbo/blob/main/docs/measurements.md)
（时钟/电压/flash 那一侧）。本文只写约束和入口。

---

## 铁律

1. **未经明确指令，不要 `git commit`，更不要 `git push`。**
2. **时钟、电压、flash 分频都由 pico-turbo 负责**，本仓库不要再长出自己的 profile 表或分频
   算术（原来那份在 RP2350 上会算出奇数 DIV 3，boot stage 2 直接拒绝）。
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
6. **`Errors detected` 不等于数据错**：CoreMark 把"没跑满 10 秒"也算 error。判定要看
   `[i]ERROR! ... crc` 这类逐项行和状态行。
7. **只有已验证的结论**：每个数字要能说出板子、时钟、电压、context 数、迭代数。

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
8. **烧写和启动放进同一个 openocd 会话**，以 `reset run` 收尾：`resume` 会让旧镜像跑进刚被
   擦掉的区域而挂死，而 `reset run` 才是"启动新写的镜像"这个动作，两者都不留 halt 状态。
9. **过快的 flash 分频会让板子变成软件复位救不回来的砖** ✗（boot2 里的分频每次复位都会
   重演；实测 DIV 4 @520 MHz 只能按 BOOTSEL 回来）。
10. **调试器用来定位**（PC 在 `core_list_find` = 在跑；`isr_hardfault` = 真挂；
   PC 在 bootrom = 镜像没起来）。

## 结果与现状

| 板子 | 单核 | 双核 | 上限 |
| --- | --- | --- | --- |
| 幸狐 Pico 2 | 150→422.71、300→845.41、520→1465.38、540→1521.74 it/s | 300→1512.07、520→**2612.7**（36 次连续通过） | 564 过、570 起不来 |
| 官方 Pico 2 | 520→1465.38、546→1538.64、552→1555.56、558→1572.47、564→1589.37 | 520→**2622.08**（50 次连续通过，极差 0.0002%） | 564 过、570 挂（已核实） |
| 官方 Pico W（RP2040） | 125→236.42、240→453.93、264→499.32、300→567.41、360→680.90、396→748.99、420→**794.38** | 420→**1417.30**（1.784×，30 次连续通过） | ≥420（平台上限；440 未测） |

分数与频率**线性**：RP2350 从 150 到 564 MHz、RP2040 从 125 到 420 MHz 都是，RP2040 侧
**1.891 it/s per MHz 一路不变**（连 flash 时钟从 60 涨到 105 MHz 都一样），说明这个负载没
有内存/flash 墙。双核加速比两个平台都是 **1.78×**（第二核受限于共享的存储）。
两块板同频双核成绩相差 0.36%（幸狐 2612.7 / 官方 2622.08），但**极差差三个数量级**
（0.39% vs 0.0002%）—— 同一颗芯片，差别在板子的供电，抖动比失败先出现。

## 待办

- Pico W 在 420 MHz 以上（合宙 RP2040 板 440 锁死），以及 105 MHz 以上的 flash 分频。
- 幸狐板的整套 flash 分频阶梯（只有"≤57 稳、78.75 出错"两个点）。
