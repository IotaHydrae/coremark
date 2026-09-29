---
name: pico-bench
description: 在这块 CoreMark + pico-turbo 硬件测试台上做一次可信的测量与判定——时钟阶梯、flash 分频阶梯、双核、soak，以及"这轮结果算不算数"。当用户要测某块 Pico / Pico 2 / Pico W 的顶端或稳定性、要跑 soak、要问某个频率（电压、flash 分频）稳不稳、要判断一份 report.md 或 results.json 是否可信、要给某块板出一份 boards/<board>.cmake、或者要改 tools/probe.py 与 rpi-pico/ 里的测量代码时，都用这个 skill。即使用户没说 probe、CoreMark、超频这些词，只要话题落在这块台架上的测量，就先读它。
---

# pico-bench

本仓库是**台架**，不是产品：它的产出是「某块板已知可用的配置」，而那个配置要回流成
pico-turbo 的 `boards/<board>.cmake`。时钟、电压、flash 分频属于那个库，本仓库不要再长出
自己的 profile 表或分频算术。

**真值来源，先读这些再动手**：

| 要什么 | 读哪 |
|---|---|
| 规矩（铁律、硬件纪律、判定口径） | `AGENTS.md` —— 本仓库会自动加载；离开本仓库时见文末"跨仓库" |
| 已经测出什么 | `RANKINGS.md`（总表）、`rpi-pico/MEASUREMENTS.md`（逐块板原始表） |
| 要动测量代码 | `rpi-pico/README.md` + `tools/probe.py` 顶部的 docstring |

写结论前先查 `RANKINGS.md`：已经测过的点不要重测，除非是要复现或推翻它。

## 一条命令

```bash
# 在仓库根目录跑；输出目录 probe-<board>-<stamp>/ 落在当前工作目录（已被 gitignore）
.claude/skills/pico-bench/scripts/run_probe.sh --board pico_w
```

它做三件事：跑 `preflight.py`（台架体检）→ 挂一个 `systemd-inhibit` 睡眠抑制
→ 用**能 import pyusb 的解释器**执行 `tools/probe.py`。

常见变体：

| 目的 | 命令 |
|---|---|
| 整套体检（阶梯 + 分频 + 双核 + 10 次 soak） | `run_probe.sh --board pico2` |
| 长 soak | `run_probe.sh --board pico2 --soak 30 --flash-ladder` |
| 只认板子，不动它 | `run_probe.sh --identify-only` |
| 只测几个点、不 soak | `run_probe.sh --board pico_w --points 240000,300000 --soak 0` |
| 测 board file 里的某个档位（clock/voltage/div 都由库决定） | `run_probe.sh --board pico_w --profile turbo` |

**不要手搓 cmake 去测点**——`probe.py` 的每一点都要走「构建 → 擦空 → bootrom → picotool
写入 → 回读逐字节比对 → 运行」这条路径，手工那条路会掉进 `reset run` 只是 vectreset 的坑。
手搓 cmake 只在改测量代码本身、需要人盯着编译器输出时用。

## 判定：什么算「通过」

五条证据，缺一条这个点就是个观察值，不是结论。`probe.py` 对每一点都算这五条
（`rec["checks"]`），**第一点不通过就不往上走**：

| 证据 | 看哪里 | 假信号长什么样 |
|---|---|---|
| flash 回读与构建产物逐字节一致 | `readback: 0 differing bytes` | openocd 报 `Verified OK` 却只写了前半 —— 所以只看回读比对 |
| 应用自己说 `Correct operation validated` | 控制台 | CRC 对了但分数偏低（SWD 被碰过）仍会 validated，所以要连实测时钟一起看 |
| 没有 `Errors detected` | 控制台 | **它也代表「没跑满 10 秒」**，不代表数据错；要看有没有 `[i]ERROR! ... crc` 这类逐项行 |
| 状态行里**实测**时钟 = 请求时钟 | `PICO-TURBO: ... measured ...` | PLL 落不到的点上，SDK 会原地不动，看着像不稳定 |
| soak：`COREMARK-REPEAT: run N of M` 数到 M | 控制台 | reader 数到的行数**不是**基准。曾经 reader 只收到 2 次而计数器是 3，差点被当成"少跑了一次" |

一轮跑完，用这个独立复核一遍（它不信 `results.json` 里写好的结论，而是从记录和原始日志
重新算一遍）：

```bash
.claude/skills/pico-bench/scripts/check_results.py probe-<board>-<stamp>/
```

退出码非 0 = 有点数的证据与它的结论对不上，或原始的 `logs/console-*.log` 与记录对不上。

## 一轮结束之后

1. 读 `report.md`：它按 `RANKINGS.md` 的形状写，直接对得上。
2. `boards/<board>.cmake` 是**提案**，不是结论——人工读一遍（尤其 flash 上限和档位），
   再按 pico-turbo 的规矩回流到那边，本仓库不 commit 它（它在 `probe-*/` 里）。
3. 要把新数字写进 `RANKINGS.md` / `MEASUREMENTS.md`：每个数字说得出**板子、时钟、电压、
   context 数、迭代数、flash 分频**，缺 flash 分频的行别人复现不了。

## 卡住了：先分类，再动手

| 现象 | 先怀疑 | 动作 |
|---|---|---|
| 状态行正常、没有成绩、PC 停在计时相关函数 | **主机**（休眠/掉设备），不是板子 | 查是不是合盖、切会话、拔过 USB —— 这条误判过一次 420 MHz |
| PC 在 `isr_hardfault` | 板子，真挂 | 记成 hang，**不要**记成低分 |
| 什么都没打印、PC 在 bootrom | 镜像没起来 | 查回读比对和 boot2 分频 |
| 有状态行但 USB 不上线（如 RP2350 570 MHz） | 芯片那边 | 这就是个结论：该频率不活 |
| `lsusb` 里板子整个消失 | 核留在 halt，或探针没接好 | 见 `AGENTS.md` 纪律 3：会话不能以 halt 收尾 |

## 跑的时候不许做的事

- **别碰 SWD**。一次 halt 就让那一轮成绩偏低，而 CRC 仍然正确 —— 是一枚"validated 但分数
  异常"的假信号。要看 PC 就等这一轮结束。
- **别让主机休眠**。`run_probe.sh` 已经挂了 `systemd-inhibit`，但别手动 `sudo systemctl
  suspend`、别切用户会话、别拔主机侧 USB。
- **别指望 `picotool reboot --pid 0x0009`**：这个镜像没有 USB 复位接口，它只会回
  "no 0009 to reset"。确定能成的是 bootrom 的 `--pid 0x000f`/`0x0003`。
- **别把空板留在那儿**：擦空 flash 之后马上写回（`probe.py` 的 `put_back()` 会做，手工做时
  别忘了）。

## 环境上的两个坑

- **pyusb 在仓库的 `.venv` 里，不在系统 python 里**：直接 `python3 tools/probe.py` 会死在
  "pyusb is needed for the console reader"。`run_probe.sh` 会自己挑解释器（`probe.py` 用它
  的 `sys.executable` 起 reader，所以挑一次就对了）。
- **`PICO_SDK_PATH` 可能没导出**：`probe.py` 缺省会找 `~/.pico-sdk`，找不到就报错退出。
  用 `--sdk <path>` 或先 `export`。

## 跨仓库

脚本不写死路径：按 `COREMARK_DIR` → 当前工作目录向上 → 脚本自身位置向上 → 同级 `coremark/`
的顺序找 `tools/probe.py`。所以这个目录可以直接复制过去用：

```bash
cp -r .claude/skills/pico-bench ~/.claude/skills/
```

在 pico-turbo 里复用它时，库侧的纪律在 pico-turbo 自己的 `AGENTS.md`（申请顺序、偶数分频、
板子上限），本 skill 只管台架这一侧的测量与判定。
