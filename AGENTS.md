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
   双核再乘 2。固定次数只在"两次跑相同工作量做对比"时用，并且要检查总时长 ——
   150 MHz 合适的次数在 500 MHz 会短到被判无效。
4. **`MEM_STATIC` 与多 context 不能共存**（CoreMark 自己 `#error` 拒绝），别为了省栈去改。
5. **`Errors detected` 不等于数据错**：CoreMark 把"没跑满 10 秒"也算 error。判定要看
   `[i]ERROR! ... crc` 这类逐项行和状态行。
6. **只有已验证的结论**：每个数字要能说出板子、时钟、电压、context 数、迭代数。

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
| `COREMARK_REPEAT` | 1 | 跑 n 次，中间用 watchdog 重启并计数（≈50 次 ≈ 10 分钟 soak） |
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
   消失）。以 `reset run`/`resume` 收尾。
4. **读取器要在烧写之前启动** ✓，否则读的是上一个应用的残留输出。
5. **过快的 flash 分频会让板子变成软件复位救不回来的砖** ✗（boot2 里的分频每次复位都会
   重演；实测 DIV 4 @520 MHz 只能按 BOOTSEL 回来）。
6. **调试器用来定位**（PC 在 `core_list_find` = 在跑；`isr_hardfault` = 真挂；
   PC 在 bootrom = 镜像没起来）。

## 结果与现状

| 板子 | 单核 | 双核 | 上限 |
| --- | --- | --- | --- |
| 幸狐 Pico 2 | 150→422.71、300→845.41、520→1465.38、540→1521.74 it/s | 300→1512.07、520→**2612.7**（36 次连续通过） | 564 过、570 起不来 |
| 官方 Pico 2 | 520→1465.38、546→1538.64、552→1555.56、558→1572.47、564→1589.37 | 待测 | 564 过、570 挂（已核实） |

分数与频率**线性**（150→564 MHz 都是），说明这个负载下没有内存/flash 墙。

## 待办

- Pico W（RP2040）：`-DPICO_BOARD=pico_w`，CPU 125/240/300/400/420 + 分频阶梯。
- flash 分频阶梯的中间点（DIV 6/8），以及幸狐板整套。
- 官方板双核 soak（`MT=2 REP=50`）。
