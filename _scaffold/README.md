# `_scaffold\` —— 脚手架与中间产物

本目录存放**开发/测试/资料提取**用的脚本与中间产物，**不参与程序分发**。
按项目约定：所有脚手架文件都放这里，不散落根目录。

## 脚本

| 文件 | 用途 | 用法 |
| --- | --- | --- |
| `extract_pdf_text.py` | 从 `..\中国国标麻将标准PDF\` 下的 PDF 提取全文 | `python -u _scaffold/extract_pdf_text.py`（加 `--stat` 只统计文本层） |
| `split_qa.py` | 《问答》OCR 切分 v1（按「XX篇」分段） | `python -u _scaffold/split_qa.py --full` |
| `split_qa2.py` | 《问答》OCR 切分 v2（题干必须在同一行结尾带 ?） | 同上 |
| `split_qa3.py` | 《问答》OCR 切分 v3（**推荐**，用「题号近似递增」锁定题目起始行，识别 125 问） | `python -u _scaffold/split_qa3.py --full`；`--range a b` 分段；`--dump N` 打印第 N 题 |
| `compact_qa.py` | 压缩问答文本：剔除牌例图噪声行 + 限量截断，便于人工整理 | `python -u _scaffold/compact_qa.py --cap 900 [--range a b]` |
| `inspect_pyc.py` | **反查 `..\__pycache__\mahjong_core.cpython-310.pyc`**：打印模块常量、类、方法、`co_consts`、字节码（v2.0.0 重建引擎时的参考，现已不再需要） | `python -u _scaffold/inspect_pyc.py` → 生成 `pyc_dump.txt` |
| **`test_engine.py`** | **算番引擎自测（73 项）**：九莲宝灯/七对/**含四张的七对**/**连七对（含跨花色反例）**/十三幺/七星不靠/组合龙/大四喜字一色/碰碰和双同刻/平和断幺/杠/听牌/起和门槛/自摸互斥/花牌口径/旧接口/非法输入/番表 | `python -u _scaffold/test_engine.py` → 日志 `_engine_out.txt` |
| **`cli_test.py`** | **命令行 / import 算番入口测试（34 项，v2.6.0）**：`mahjong_core.py --hand/--win/--waits/--meld/--version/--fan-table/--help`（含中文与简写写法、退出码 0/1/2、输出纯 ASCII）、**主程序（=打包后的 exe）带参数不启动界面**、`score_hand()` 与 `MahjongFanCalculator().score()` 一致、「core 里没有任何 socket/HTTPServer 代码」 | `python -u _scaffold/cli_test.py` → 日志 `_cli_out.txt` |
| **`smoke_test.py`** | **界面冒烟测试（229 项）**：结构、复选框动态文案、选牌减牌、听牌候选与算番、碰/明杠/暗杠/吃、**暗杠面背面渲染**、设计图那手牌、重置、风圈风位、**花牌按钮/展示行/恢复**、设置自动保存与恢复、番表/用法页、引擎一致性、**本地 API 菜单启停与端口持久化**、**§17b Web 版：局域网 + 口令（真起服务验证 401/200/首页免口令/花牌图；★ 用随机空闲端口）**、**§18 重置 = 全部复位（v2.4.4）**、**§19 程序图标（v2.4.7）**、**§20 免口令访问设置（v2.5.0：默认值/对话框/落盘恢复/真起服务验证 401 与 200）**、**§21 点已选的牌取消（v2.7.2，22 项，`QTest.mouseClick` 发真实点击：角标 3→2 不误加、立牌−1、**点暗杠牌背撤销整组**、取消和张、取消单张花牌、空态/越界不崩）**、**§22 Web 版显示设置（v2.7.5，8 项：菜单项文案、默认两个按钮都不显示、状态栏文案、改设置后 `api_show` 落盘、新窗口恢复、老设置没这个键时回默认）** | `python -u _scaffold/smoke_test.py` → 日志 `_smoke_out.txt` |
| **`api_smoke_test.py`** | **Web 版服务 + Web 客户端测试（167 项）**：真实起服务（`port=0`）+ 真实 HTTP。 存活/版本/牌张表/番表/算番（POST 与 GET 简写、`counts`、副露+暗杠、门风、花牌、不与起和分）/听牌（九莲宝灯 9 张、`waits_all`）/错误处理（非法牌张/张数/非 JSON/未知接口/非法吃/非法风位/花牌>8/**张数口径 4 项**）/口令与 CORS/Web 页面特征/静态资源（`/debug`、`/manifest.webmanifest`、`/tiles/*.png` 含花牌图、非法名 404、路径穿越）/免口令静态 vs 口令接口/**4 条页面 JS 白盒回归**/**★ v2.4.4–2.4.6：15 项布局 + 触摸断言**/**★【7b】v2.5.0：31 项免口令白名单断言（默认值、`anon=None` vs `()`、单开 info、单开 score+waits、全关、全开、空口令不生效、未知键不误放行、“/”不能当前缀的回归）** + **★ v2.7.0/v2.7.8：12 项布局断言（五档循环：经典/自适应/大/更大/最大，系数 0/1/1.2/1.4/1.6，`cycleLayout()`，`mj_layout2`，基准夹紧 20~46 后乘系数；CSS 变量默认值＝旧像素值、各处尺寸走变量、默认 fixed、经典还原、resize 监听）** + **★ v2.7.9：4 项底部跳转按钮（`gotoBlock` 滚到区块、`#c_pool`/`#c_res` id、`.flash` 高亮 + `button:disabled` 置灰、`updateJumpBtns` 在启动/render/resize 都重算）** + **★ v2.7.1：5 项副露/暗杠渲染断言（`meldHtml()` 存在且被 `render()` 调用、暗杠＝面·背·背·面 且牌背走 `/tiles/empty.png`、只有暗杠盖牌、`.meldgap` 存在）** + **★ v2.7.4【7c】6 项「客户端提前断开不刷屏」（真发 4 次 RST + 把 `sys.stderr` 重定向到内存捕获，断言无 `Exception occurred` / traceback，且断开后服务照常 200）** + **★ v2.7.5【7d】10 项「Web 页面工具按钮默认不显示」（`WEB_SHOW_ITEMS` 两项与键序、`WEB_SHOW_DEFAULT` 为空、默认首页 200 且两个按钮都是 `display:none`、页面无占位符残留、`show=("debug",)` 只显示自测页、`show=("debug","token")` 两个都显示、`render_web_client()` 应用名与占位符替换正确）** + **★ v2.7.6【7e】14 项「客户端按钮大小档位」（CSS 默认＝升级前的 15px/7/11、`button` 走 `--btn-fs/--btn-pad-*`、`mj_btnsize2` 键、5 档字号 15/17/19/21/23、5 档内边距 7/11→9/14→11/17→13/20→15/23、**默认档＝第 1 档（最小）且与 CSS 默认一致**、没有比默认更小的档、`#szbtn` 在「布局」之后且 onclick 循环、默认档清内联变量、启动恢复、越界回默认、首屏文案一致）**（v2.7.7 按用户反馈把默认改成最小档、只往大） | `python -u _scaffold/api_smoke_test.py` → 日志 `_api_out.txt` |
| **`verify_all.py`** | **全量枚举 + 算番校验**。**v2.4.3 起：不带参数就是「完整检验（不抽样）」** —— 牌型空间 100% 穷尽 ≈ **2842 万手**（标准型全量 + 组合龙 11,016 + 特殊 742 + **七对全空间 C(34,7)=5,379,616** + **七对含四张 k=3/k=2/k=1 = 185,504 / 2,782,560 / 8,069,424**），逐手做「和牌判定/分解集合/特殊 tag/逐分解逐番对拍/取优/番值/并存违规/无故丢番」；分阶段 `main,waits,score,sweep,neg,meld,golden`（默认不含 sweep）；**生成器 + 分批（--batch）+ 进度文件，可中断续跑**。旧的分层抽样路径保留为 `--quick` / `--sample` | `python -u _scaffold/verify_all.py [--phases main,waits,...] [--families "组合龙,k=3"] [--batch 300000] [--restart]`（完整）<br>`python -u _scaffold/verify_all.py --quick`（抽样快版）→ 日志 `_verify_out.txt` |
| **`error_audit.py`** | **错误类别全枚举 + 故障注入**（v2.2.0 新增）：把「算番器可能出错的地方」穷举成 **25 类**，逐类**注入一个真实缺陷**（共 **29 个**），要求被 D1~D10 检测器抓到；抓不到就是「校验盲区」（脚本以非零退出码报错）。含「七对 4 张同牌」口径审计与**口径回归防护**（E29） | `python -u _scaffold/error_audit.py`（约 3 分钟）→ 日志 `_audit_out.txt`，退出码 0 = 全部抓到 |
| **`indy.py`** | **第二套独立实现**（不共用任何判定代码）：自己的牌张编码、自己的分解递归、81 个番种另写一遍、自己的「不计」闭包。供 `verify_all.py` 对拍 | 无命令行 |
| **`sweep_qidui4.py`** | **七对含四张：逐族完整扇扫**（v2.2.1 新增）：按「k 个四张」分族（k=3 全量 185,504 / k=2 全量 2,782,560 / k=1 抽样或全量 800 万）跑引擎 × 独立实现 × 逐分解校验，专治「随机抽样漏掉稀有族」 | `python -u _scaffold/sweep_qidui4.py [--only k3|k2|k1]` → 日志 `_sweep_out.txt` |
| **`golden_fans.py`** | **81 个番种的金标准牌例**（每个番种一手构造牌 + 副露/和张/选项）；`parse_tiles/parse_melds/parse_opts/parse_entry` 供校验脚本使用 | 无命令行 |
| `dbg_diff.py` / `dbg_search.py` | 差异定位：打印引擎/独立实现在同一分解下的番种差异（含随机搜索） | `python -u _scaffold/dbg_search.py` |
| **`shot_ui.py`** | **真实平台截图**到 `shots\ui_*.png`（人工肉眼验收界面，当前 **7 张**；v2.4.1 用它验收「选项区四行」，v2.4.2 验收「牌池间距」，**v2.4.3 起截图尺寸用 `M.WIN_W/M.WIN_H`（= 程序默认 680×940），不再硬编码 1180**） | `python -u _scaffold/shot_ui.py` |
| **`make_icon.py`** | **生成程序图标 `icon.ico`**（v2.4.7）：红中牌样式（蓝底 `#2f7ff0` + 白牌面 + 红「中」），**7 张尺寸各自单独绘制**（不是缩放，小尺寸不糊），手写 ICO 容器（每张都是 PNG 条目，Qt/Nuitka 都认）；顺带导出 `icon_preview.png` 给人看 | `python -u _scaffold/make_icon.py` → 根目录 `icon.ico` + 日志 `_icon_out.txt` |
| **`probe_icon_live.py`** | **真机验证窗口图标**（v2.4.7）：真实平台开窗后，用 Win32 `WM_GETICON` / `GWL_HICON` 看系统是否真的拿到了图标句柄（任务栏/Alt+Tab/标题栏都取它）；offscreen 只能验 `QIcon` 非空 | `python -u _scaffold/probe_icon_live.py` → 日志 `_probe_icon_out.txt` |
| **`probe_api_token.py`** | **查「带口令访问却 401」**（v2.4.7）：开局域网 → 启动服务 → 分别用 `?token=` 与 `X-Api-Token` 各请求一次，并打印窗口侧/服务侧 token 与 `netstat` 监听情况 | `python -u _scaffold/probe_api_token.py` → 日志 `_probe_api_token_out.txt` |
| **`probe_click_remove.py`** | **「点已选的牌取消」真机探针（v2.7.2）**：真实平台开窗，用 `QTest.mouseClick` 点红角标 / 立牌一张 / 副露一张（暗杠牌背）/ 和张 / 花牌行，断言数据真的变了。★ 红角标是牌按钮的**子控件**，真机才能证明「点角标不会反过来又加一张」（offscreen 过了也别省这一步） | `python -u _scaffold/probe_click_remove.py` → 日志 `_probe_click_out.txt` |
| **`build_exe.py`** | **Nuitka 打包**（由根目录 `0_nuitka_pyside6_clang_auto.bat` 调用）：把《国标麻将标准规则.json》与整个《麻将图》用 `--include-data-files` 带上；**`icon.ico` 存在时自动加 `--windows-icon-from-ico=icon.ico`（exe 文件自身图标）与 `--include-data-files=icon.ico=icon.ico`（运行时窗口/任务栏图标，缺它会出现「exe 有图标但窗口没有」）**。★ v2.7.3：入口 `Mahjong_Calculator.py` → 产物 `build_output\Mahjong_Calculator\` + `Mahjong_Calculator.exe`（编译完自动把 `.dist` 改名，不带 `.dist` 后缀；旧目录会保留为 `Mahjong_Calculator_旧编译_时间戳`）；编译前检查 exe 是否在运行（含三个历史名字） | `set EM_SKIP_BUILD=1` 可干跑自检 |
| `smoke_test_v1_pyqt5.py` | v1.1.0（PyQt5 界面）的旧冒烟测试，已归档 | — |

## 中间产物

| 路径 | 内容 |
| --- | --- |
| `pdf_text\` | 各 PDF 提取出的纯文本 + `_stat.json`（页数/字数/空页统计）。**带文本层的只有两个 `orcmypdf` 版本**，其余为影印件（提取为空） |
| `qa_split\` | 《问答》切分结果：`question_index.txt`（题号索引）、`qa_full*.txt`（问+答原文）、`qa_compact*.txt`（清洗压缩版）、`idx_*.txt`（分段索引） |
| `pyc_dump.txt` | `mahjong_core` 的结构反查报告（重建源码的依据） |
| `legacy\` | 早期残缺的 `国标麻将标准规则.json`（已被 v1.1.0 全量版取代） |
| `_smoke_out.txt` | 最近一次界面冒烟测试日志（UTF-8，防 PowerShell 管道丢输出） |
| `_engine_out.txt` | 最近一次引擎自测日志（UTF-8） |
| `_verify_out.txt` | 最近一次全量校验日志（UTF-8，实时刷新，可随时看进度） |
| `_audit_out.txt` | 最近一次「错误类别 + 故障注入」审计报告（UTF-8，实时刷新） |
| `_api_out.txt` | 最近一次 API / Web 客户端测试日志（UTF-8） |
| `_icon_out.txt` | 最近一次生成 `icon.ico` 的日志（UTF-8，含 Qt 能否读到的自检） |
| `_probe_icon_out.txt` | 最近一次真机图标探针日志（UTF-8，含 Win32 图标句柄） |
| `_probe_api_token_out.txt` | 最近一次「口令 401」排查日志（UTF-8） |
| `_probe_click_out.txt` | 最近一次「点已选的牌取消」真机点击探针日志（UTF-8，v2.7.2） |
| `icon_preview.png` | `make_icon.py` 顺手导出的 256×256 预览图（人工看图标长什么样） |
| `shots\` | 界面截图（`ui_1_empty` / `ui_2_ting` / `ui_3_win` / `ui_4_melds` / `ui_5_fan_table` / `ui_6_help` / `ui_7_flowers_fantable`）+ **`v271_melds.png`（v2.7.1：Web 端副露区，暗杠＝面·背·背·面）** |
| `软件升级迭代记录_v1.1.0_备份.md` | v2.0.0 重写文档前的旧版记录（存档） |
| `__pycache__\` | 脚本自身的字节码缓存 |

## 环境注记（踩过的坑）

1. **哪些 PDF 有文本层**：`… ocrmypdf.pdf` / `… orcmypdf.pdf` 有；影印版与抽页版（34-38、224-228）没有。
2. **PowerShell 重定向编码**：`python x.py > out.txt` 写出的是 **UTF-16**；要 UTF-8 就让脚本自己用
   `open(..., encoding='utf-8')` 写（`inspect_pyc.py` 就是这样做的）。
3. **工作目录**：终端工具可能把命令开头的 `cd X;` 简化掉，导致脚本在用户目录下运行。
   本目录脚本全部用 `__file__` 推导项目根目录，因此**用绝对路径调用最稳**：
   `& "D:/Program Files/Python310/python.exe" -u "G:\Python_Code\Mahjong_Calculator\_scaffold\smoke_test.py"`
4. **离屏测试**：`QT_QPA_PLATFORM=offscreen` 下 `QMessageBox` 会永久阻塞，测试里必须替换掉；
   同时 Qt 会打印 `QFontDatabase: Cannot find font directory …` 警告，属环境噪声可忽略。
5. **中文别写在 `python -c` 里**（PowerShell 按 GBK 传参会乱码），写成脚本文件。
6. **测试要隔离设置文件**：把 `Mahjong_Calculator.settings_path` 指到临时文件，不要把真实
   `mahjong_settings.json` 当作草稿纸；并且每次测试/截图前先删掉临时文件（否则上次保存的
   「当前页/模式」会被恢复，导致截图串页）。
7. **读 UTF-8 日志**：PowerShell 控制台先 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`，
   否则中文会显示成乱码（文件本身是正常的 UTF-8）。
8. **全量校验很吃时间**：标准型和牌型共 1150 万种（完整枚举），全量跑约 20~30 分钟（6 进程）；
   平时改动用 `--quick`（约 2 分钟）即可。日志写 `_verify_out.txt`，别用 `| Out-String`
   （管道会等到进程结束才回显）。
9. **改动番种判定后不要只看手写牌例**：手写牌例极易漏掉「同一手牌的另一种分解方式」
   （典型：一色三同顺的 123×3 同时可看成 111+222+333 三节高），必须靠双实现对拍。
10. **断言必须用「注入前快照 + 第二套实现」做参照**（v2.2.0 踩坑）：`error_audit.py` 一开始用
    引擎自身的 `decompositions()` 当断言基准，结果注入的缺陷把断言基准也一起改了，
    “自己掩盖自己”导致假盲区。另外：`max_delta` 类的断言一定先取快照（`PRISTINE`）。
11. **构造定向反例手牌必须给「和张」**（v2.2.0 踩坑）：`H(melds, tiles)` 不传 win 时会被当作
    「听牌用例」只走听牌分支，D4/D5 等逐分解检查都不会跑 → 看起来“缺陷未被发现”。
    完整手牌用 `HW(codes)`（自取最后一张为和张）。
12. **牌号是跳花色连续编号**（筒0-8/索9-17/万18-26）：凡是用「差几」判断连续性的地方，
    必须同时比较花色（v2.2.0 的连七对缺陷就出在这里）。
13. **控制台打印 emoji 会报 UnicodeEncodeError**：日志函数要「先写文件、再 try print」，
    否则带 ✅/⚠ 的行只会丢在控制台，文件里反而是完整的。
14. **两套实现对「必然并存番种」的写法要一致**（v2.2.1 踩坑）：含 4 张同牌的七对里，
    「四归一」按《问答》Q71 属必然并存，**引擎根本不产生它**；而 `indy` 一开始按
    「某张牌=4 张」直接多算，靠不计表才被剔掉 → raw 对拍（D5）会报差异。
    两套实现要么都产生、要么都不产生，**不要一半靠不计表兜底**。
15. **改了成立条件就必须把新牌型纳入枚举**（v2.2.1）：七对改成「4 张算两对」后，
    `verify_all` 原来的七对枚举（7 个不同对子）完全覆盖不到新牌型，
    于是补了「3 四张完整 + 1~2 四张抽样」，否则校验会「看起来很全但根本没测到」。
16. **Web 端只能真机验（v2.4.0 踩坑）**：`WEB_CLIENT` 是内联 JS，Python 测试只能盯页面文本特征。
    v2.4.0 的 4 个真缺陷（算番张数口径、设和张后不进算番分支、牌池重建 DOM 丢点击、花牌被当手牌）
    **全部是真浏览器点出来的**——所以改完 JS 必须：
    ① `python -u mahjong_api.py --host 0.0.0.0 --token 1234` 起服务；
    ② 浏览器打开 `http://127.0.0.1:8718/?token=1234`；
    ③ 走一遍「点 13 张→看听牌→点第 14 张→看总番→加一张花牌」；
    ④ 把总番跟 `mahjong_core` 同一手牌的结果对一下（应该逐项一致）。
    另外：**页面上的元素 ref 会在每次重绘后失效**，用浏览器的脚本工具批量点击时**用 CSS 选择器**
    （`#pool .tile[data-code="W9"]`）而不是元素引用。
17. **不要在每个操作里重建整个 DOM**（v2.4.0）：牌池上次每次 `render()` 都重建 44 张图，
    快速连点时 mousedown/mouseup 之间的节点被换掉 → **点击丢失（实测 13 次丢 2 次）**。
    正确做法：`buildPool()` 只建一次 + `updatePool()` 只改类名/角标文字。
18. **改文档/源码别用脚本改**（换行符铁律）：项目文件全部 **UTF-8 无 BOM + CRLF**；
    用 Python `open(...,'r')` 读再写会把 CRLF 变 LF。要用编辑工具改；只读分析用 `open(...,'rb')`。
19. **调界面布局时不要改控件属性名**（v2.4.1）：算番页选项区改成四行时只动了 `QHBoxLayout` 的组装，
    `cb_tsumo` / `cb_last_tile` / `cb_special_a` / `cb_special_b` / `wind_round_group` / `cb_round` /
    `wind_seat_group` / `cb_seat` / `btn_flowers` / `lbl_flower_count` 一律没改名 —— 于是
    `_refresh_all` / `_apply_settings` / `_options` 和三套测试**一行都不用改**。若改名，
    「老设置恢复」和测试会一起坏。
20. **判断「布局到底几行」可以在离屏下量坐标**（v2.4.1）：`python` 里 `QApplication` + 窗口 `show()`
    + `app.processEvents()`，然后打印各控件的
    `widget.mapTo(window, widget.rect().center())` 的 x/y：四行就是 **4 个不同的 y**，
    同一行内的 x 递增顺序就代表显示顺序（比看截图靠谱，offscreen 截图没有字体）。
21. **窗口尺寸/几何迁移的坑（v2.4.3）**：主程序里窗口尺寸是常量 `WIN_W/WIN_H/MIN_W/MIN_H`
    （默认 680×940，最小 600×560；牌池只需 ~560px）。设置里存 `geometry` + `geo_ver`，
    `geo_ver < GEO_VER(2)` 时 `_apply_settings` 会把宽度**一次性**收紧到 `WIN_W`（高度/位置保留）。
    测试要点：① 无设置 → 默认尺寸；② 旧几何（无 `geo_ver`）→ 宽度被收紧；
    ③ `geo_ver=2` 的几何 → **原样恢复**（不能被反复收紧）；④ 保存后 `geo_ver=2` 落盘。
    要再改默认尺寸就把 `GEO_VER` +1，否则用户已存过的几何永远不会被更新。
22. **完整检验（不抽样）跑很长，但有办法「提前拿到结论」（v2.4.3）**：`verify_all.py` 默认就是完整检验
    （2842 万手，4 核约数十小时）。族顺序是**稀有族优先**，所以用 `--families` 先跑
    「组合龙,特殊,k=3」几分钟就能拿到稀有牌型的完整结论；进度写 `_verify_progress_<阶段>.json`，
    **中断后重跑同一条命令会自动续跑**（重头跑加 `--restart`）。
    ★ **跨实现对拍只能比「两边都实现的口径」**：`indy` 不实现「终局不计表补充项（`EXTRA_EXCLUDES`）」
    也不抑制「已计不求人不再计自摸」，拿这两项去对拍会每批都刷假差异（已用 `_norm_ind()` 排除）。
23. **改了「重置」/ 新增状态变量时，测试会跟着变（v2.4.4）**：`on_reset()` 现在会把**圈风/风位也复位为
    「东风圈/东风位」并立即落盘**。所以任何「依赖前面测例留下的圈风/风位」的断言都会挂 ——
    测试里要**自己先把状态设好再断言**（`smoke_test.py` 第 13 节就是这么改的：先
    `cb_round[1].setChecked(True)` / `cb_seat[3].setChecked(True)` 再断言已保存）。
    同理，以后新增任何状态（新控件/新变量）都要同时加进**桌面版 `on_reset()` 与 Web 端 `resetAll()`**。
24. **Web 端布局必须跟桌面版一致（v2.4.4）**：顺序 = 牌选择区（4 行）→ 模式行（含重置）→ **选项区四行**
    （□选项 / 风圈 / 风位 / 花牌 8 张小图 + 「N 张」）→ 已选牌 → 听牌候选 → 算番结果；
    **花牌不在牌池里**。改完 `api_smoke_test.py` 的布局断言会先拦一遍，然后还要真机浏览器看：
    `python mahjong_api.py --port 8720` → 打开 `http://127.0.0.1:8720/` →
    点 13 张看听牌 → 点候选出总番 → 点花牌行加花牌 → 点「重置」看是否全清。
25. **Web 端样式靠「祖先类选择器」，重排 HTML 别把类名弄丢（v2.4.5 踩过）**：`.pool .line`、
    `.tiles img`、`.row .lb` 都必须祖先带类名才生效。v2.4.4 重排时牌池容器漏了 `class="pool"`，
    行 `.line` 拿不到 `display:flex` → **每张牌各占一行**（用户一眼就看出来了）。
    所以：① 重排后逐块对照 CSS 需要的类名；② 关键布局样式**同时用 `#id` 再写一份兜底**
    （现已改成 `#pool .line,.pool .line{display:flex;gap:3px;flex-wrap:wrap}`）；
    ③ 真机验证时用 DOM 几何量「每行张数 / 同一行 top 是否相同」，比等用户发现快。
26. **Web 端是给手机用的，交互别依赖右键 / 悬停（v2.4.6，用户点名）**：减牌现在是
    **点牌上的红色角标 −1** ＋ **「已选牌→立牌」里点一张减一张**；长按/右键保留但不再是唯一入口。
    角标必须 `stopPropagation` 掉 `mousedown/mouseup/click/touchstart/touchend/contextmenu`
    （否则会冒泡成「加一张」），并用 `-webkit-touch-callout:none`+`user-select:none`
    避免长按弹系统菜单。新增 Web 交互先问：**手机上单手能不能完成？**
27. **测试别用默认端口 8718，会「撞」出莫名其妙的失败（v2.4.7 踩过）**：Windows 的
    `SO_REUSEADDR`（Python `HTTPServer.allow_reuse_address=1`）**允许同一端口被重复绑定**，
    所以当机器上另有真实运行的 API/Web 服务（或没退干净的旧实例）也听着 8718 时，
    我们的服务照样能启动成功，但**请求会被随机投给其中一台**——现象是
    「§17b 无口令 401 通过、带着正确口令却仍 401」（连续两次复现，netstat 却看不到 LISTENING）。
    修法：测试改用 `free_port()` 拿一个**空闲随机端口**（服务仍支持 `port=0`），
    并在断言里加**最多 3 次重试 + 失败时打印窗口侧/服务侧 token**，避免瞬时状态掩盖真问题。
28. **程序图标要「三处齐全」（v2.4.7）**：① exe 文件自身的图标靠
    `--windows-icon-from-ico=icon.ico`；② 运行时窗口/任务栏图标靠程序自己
    `app_icon()` 读 exe 同目录的 `icon.ico`（所以必须 `--include-data-files=icon.ico=icon.ico`
    把它打进 dist）；③ `main()`（app 级）与 `MahjongFanWindow.__init__`（窗口级）**两处**
    `setWindowIcon` 都要写——少一处就会出现「exe 有图标但窗口没有」。
    图标读不到时必须**安静降级为空 QIcon**，不能让程序起不来。
    验证：offscreen 下断言 `QIcon` 非空/多尺寸，真机再用 `probe_icon_live.py` 看系统句柄。
29. **免口令白名单的三个坑（v2.5.0）**：① 命令行/嵌入用
    `mahjong_api.py --anon web,info`（`none` = 全部要口令）；分组在 `ANON_GROUPS`，
    **`*` 结尾＝前缀项，其余精确相等** —— `"/"` 必须当精确项，写成前缀会命中一切路径；
    ② `ApiServer(anon=None)` = 用默认 `ANON_DEFAULT`（web+debug，旧行为），
    **`anon=()` 才是「全部要口令」**，把默认值改成 `()` 会让老调用方/老测试一夜间全 401；
    ③ 关掉 web 免口令后页面要用 `?token=` 打开，页面里的牌面图靠 `q()` 自动带上口令
    （`img()/imgClk()` 已改，否则一片碎图）。
30. **不要把菜单 action 从 `menuBar()` 里反查**（v2.5.0 踩过）：
    测试里写 `win.menuBar().actions()[1].menu().actions()` 会撞到已失效的 QMenu 包装，报
    `RuntimeError: Internal C++ object (PySide6.QtWidgets.QMenu) already deleted`；
    菜单 action 一律**存成窗口属性**（`self.act_api` / `act_api_lan` / `act_api_token` /
    `act_api_anon`）再引用。
31. **算番入口就是 `mahjong_core`，别绕道 HTTP（v2.6.0，用户点名）**：
    - 程序间调用：`import mahjong_core`（`MahjongFanCalculator` / 便捷函数 `score_hand()`），
      或直接跑 `mahjong_core.py` / 主程序 exe 的 CLI（一次调用算完就退出）。
    - CLI 在 `mahjong_core.cli_main()`；`Mahjong_Calculator.main()` 用 `cli_wanted(argv)` 判断，
      命中就**不创建 QApplication**。新增选项时 `CLI_FLAGS` 与 `argparse` 两处都要加。
    - **JSON 必须 `ensure_ascii=True`**（纯 ASCII，\uXXXX 形式）—— 跨语言/跨编码读取才不乱；
      **退出码语义固定：0 成功 / 1 不能和牌 / 2 参数或牌面有错**。
    - 打包用 `--windows-console-mode=attach`（**不是 disable**）：双击仍是纯 GUI，
      但被 cmd/subprocess 调用时能挂到父控制台；`disable` 会让 exe 彻底丢弃 stdout。
32. **Web 页「经典 / 自适应」两套布局共存（v2.7.0，用户点名「先保留现在的布局，再新增自适应」）**：
    - 牌尺寸全部写成 CSS 变量（`--tw/--th/--pw/--ph/--fw/--fh/--fwi/--fhi/--ww/--wh/--gw/--pgap`），
      **`:root` 默认值必须逐个像素等于老版本**（38/52、34/46、34/46、28/38、间距 4/3）——
      守住这个不变量，「经典」布局就永远与升级前一致。
    - 自适应只在 `body.auto` 下写**内联**变量（一行 9 张 + 高度上限，夹 20~46px）；
      切回经典靠 `removeProperty` 清掉内联值，**不要**用 JS 重写一遍默认值。
    - 新增尺寸相关控件时要同步加进 `LAYOUT_VARS` 与 `autoSize()`；改完**必须真机量**：
      Playwright 改视口（360/390/768）×（经典/自适应），读 `#pool .tile` 与 `img` 的 `getBoundingClientRect`。
      实测参考：平板 768 自适应牌图 46×63、手机 390 自适应 34×46、小屏 360 自适应 31×42、经典一律 32×44。
33. **Web 端副露的「画法」必须和桌面版一样（v2.7.1，用户点名「web客户端的暗杠的显示不对，
    怎么跟 明杠 的一样了？」）**：**桌面版 `_meld_codes()` 是唯一口径** —— 暗杠 = **面·背·背·面**
    （中间两张用 `empty.png` 牌背）、明杠 / 碰 / 吃全正面、相邻副露之间留间隔
    （桌面版 `GAP` 哨兵 ⇒ Web 端 `<span class="meldgap">`）。Web 端由 `meldHtml()` 渲染 `#m_melds`
    （`render()` 调用它），原来是一行 `mkTiles(el("m_melds"),S.melds.flatMap(m=>m.tiles),…)`
    **一把平铺** ⇒ 暗杠跟明杠长得一模一样。
    ★ **踩坑教训**：这次数据层**一个字都没错**（`S.melds` 的 `kind/concealed`、`meldsBody()`、
    `countUsed()`、`totalTiles()` 全对），坏的只是渲染层没看 `concealed` ——
    所以「Web 端显示不对」**先去读桌面版怎么画**，再逐组对照，别只盯数据/接口。
    改完必须**真机量 DOM**（Playwright）：暗杠 4 张里中间两张的 `src` 必须是 `/tiles/empty.png`、
    明杠 4 张必须全正面；另：`img()` 只认牌编码，牌背要自己写 `<img src="/tiles/empty.png">`。
34. **桌面版「不用右键也能减牌」（v2.7.2，用户点名「就好像 手机屏幕那种 没有右键也可以操作的样子」）**：
    - 牌选择区的**红角标**（`CountBadge`）点一下 = −1；「已选牌」区（`TileRow(clickable=True)`
      + `ClickTile`）**点某一张 = 取消这一张**（立牌 −1、副露撤销那一组、和张取消、花牌取消那张）；
      右键**保留**给鼠标。
    - **角标点击必须 `event.accept()`** —— 它是牌按钮（`QToolButton`）的子控件，不 `accept`
      就会冒泡成「再加一张」（测试专门断言「点角标后 3→2，不是变成 4」）。
    - 副露渲染改成 `_meld_items()` → `(牌编码, 组号)`，**payload 非 None 才可点**，
      **暗杠牌背（`BACK_TILE`）也可点**（点它撤销整组）；`_meld_codes()` 保留为老接口（只取编码）。
    - `_refresh_all` 里四处 `set_tiles(codes, payloads, tip)` 要一起改，**payloads 长度必须与 codes 相同**。
    - 验证两条都要跑：`smoke_test.py` §21（22 项，`QTest.mouseClick`）+ **真机**
      `probe_click_remove.py`（10 项）—— offscreen 过了也别省真机（子控件的层级/命中不一样）。
35. **英文名 / 文件名 / exe / 产物目录统一叫 `Mahjong_Calculator`（v2.7.3）**：
    - 主程序 `Mahjong_Calculator.py`、exe `Mahjong_Calculator.exe`、产物 `build_output\Mahjong_Calculator\`；
      **界面中文名「国标麻将算番器」不变**（`APP_NAME`；英文名是 `APP_NAME_EN`，主程序 119–121 行）。
    - 引擎 `mahjong_core.py` / Web 版 `mahjong_api.py` **故意不改名** —— `import mahjong_core` 是给
      外部程序用的 API 契约（改了会直接弄断）；文档里 `mahjong_gui.py` 的历史写法已加注说明。
    - **新写脚手架脚本一律 `import Mahjong_Calculator as M`**（不再是 `mahjong_gui`）；
      旧 `.pyc` 缓存（`__pycache__\mahjong_gui.*.pyc`）要删掉，否则排查时容易被旧字节码误导。
    - 产物改名后，文档/示例里的 exe 调用一律写 `Mahjong_Calculator.exe --hand … --json`。
36. **手机连 Web 版时报的 `ConnectionResetError` 是噪声，不是错误（v2.7.4）**：
    - 现象：控制台刷一屏 `Exception occurred during processing of request from ('192.168.x.x', 52542)`
      + `ConnectionResetError: [WinError 10054] 远程主机强迫关闭了一个现有的连接。`
    - 原因：手机/平板浏览器**刷新、关标签页、切后台、回收预连接**时直接把 TCP 掰断（RST），
      `socketserver` 就把 `rfile.readline()` 的异常连 traceback 一起打印。**对服务与算番毫无影响**。
    - 已治：`mahjong_api.py` 的 `CLIENT_GONE_ERRORS` + `Handler.handle_one_request()`（吞）
      + `QuietHTTPServer.handle_error()`（兜底静音）。★ **只静音这四类断开异常，其它异常照旧完整打印**
      —— 别把 `handle_error()` 整体吞掉，那会把真 bug 一起藏起来。
    - 验证：`api_smoke_test.py` 的【7c】用 `SO_LINGER + close` 真发 RST，并把 `sys.stderr` 换成内存
      缓冲区断言「没有 Exception occurred / Traceback」。测试服务跑在同进程，所以这招才可行。
