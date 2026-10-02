# coremark 知识库索引

> 台架测什么、结论是什么、数字在哪。  **范围**：本仓（`coremark`）的实测与结论；时钟/电压/flash
> 分频的算术与 profile 属于 [pico-turbo](https://github.com/IotaHydrae/pico-turbo)，这里只验证它、
> 找它的边界。  **工作规则**见 [../AGENTS.md](../AGENTS.md)。

## 文档索引

| 文档 | 一句话内容 |
| --- | --- |
| [../AGENTS.md](../AGENTS.md) | 台架铁律、硬件纪律、构建与运行 |
| [../RANKINGS.md](../RANKINGS.md) | 跨板天梯：每板最佳已验证配置、双核倍率、读数字的规矩（§8 编译器） |
| [../TOOLCHAINS.md](../TOOLCHAINS.md) | 编译器天梯：同一板/点/配置，7 个 GCC + 2 个 clang |
| [compiler-packagers.md](compiler-packagers.md) | 同一个编译器的不同打包方不是变量，按版本号即可比 |
| [per-clock-efficiency.md](per-clock-efficiency.md) | 每时钟效率常数（2.8180 / 1.8914）与跨平台换算 |
| [soaks.md](soaks.md) | 全部重复跑记录，WeAct 双核两种失败形态与抖动来源 |
| [ceilings.md](ceilings.md) | 各板的频率/flash 墙、电压档，以及回流到 pico-turbo 的板文件 |
| [compiler-flags.md](compiler-flags.md) | 编译选项也是被测变量：`-O2` / `-Os` / `-flto` 的实测 |
| [compiler-vs-workload.md](compiler-vs-workload.md) | "哪个编译器更好"只在某个负载内成立（CoreMark/Embench/Dhrystone） |
| [../rpi-pico/README.md](../rpi-pico/README.md) | 移植的构建/烧写/选项与一次历史运行 |
| [../rpi-pico/MEASUREMENTS.md](../rpi-pico/MEASUREMENTS.md) | 实测总索引 + 方法学 + 未测清单 |
| [../rpi-pico/measurements/pico2.md](../rpi-pico/measurements/pico2.md) | 官方 Pico 2 原始表（含 flash 分频阶梯与 50 次 soak） |
| [../rpi-pico/measurements/luckfox.md](../rpi-pico/measurements/luckfox.md) | 幸狐 Pico 2 原始表 |
| [../rpi-pico/measurements/pico_w.md](../rpi-pico/measurements/pico_w.md) | 官方 Pico W（RP2040）原始表 |
| [../rpi-pico/measurements/weact_rp2350a.md](../rpi-pico/measurements/weact_rp2350a.md) | WeAct RP2350A 原始表与双核 soak 失败 |
| [../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md) | 未决问题与待测项，**按危害排序** |
| [../toolchain-ab/README.md](../toolchain-ab/README.md) | 两个提交的二进制（13.2.1 vs 16.2.0）与逐指令拆解材料 |
| [../README.md](../README.md) | **上游 EEMBC CoreMark 原版 README**（vendored，未改动）；不是本仓知识库 |

## 维护约定

- 一次改动**只动文档**：`tests/`、`tools/`、`src/` 与 `rpi-pico/*.c` 不碰。
- 每个数字必须能说出六要素：**板子、时钟、电压、context 数、迭代数、编译器**。
- 结论方向性不可省：天梯读作"**CoreMark 说**"，不能读作"这颗芯片上"。
- 只写已验证结论；推测标"未验证"。 不写本机绝对路径/内网 IP/口令/代理地址/序列号，
  统一用 `<pico-sdk>`、`<probe>`、`<host>:<port>` 占位。
- 超过 300 行的文档要拆分；新文档走"首屏 `> 一句话结论` + `## TL;DR`"。
- 每次改动收尾跑：`python3 tests/test_docs_drift.py`、`tests/test_probe_parse.py`、
  `tests/test_probe_cli.py`。
