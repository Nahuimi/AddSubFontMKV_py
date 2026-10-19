# AddSubFontMKV_py

ASFMKV（AddSubFontMKV）Python 版。分析 ASS/SSA 字幕实际用到的字体，把字体**子集化**，
再与媒体、字幕一起封装成 MKV / MKS，或把字体直接**内嵌进字幕**。
提供交互式菜单，也提供完整的命令行接口。

## 一、安装

依赖由 [uv](https://docs.astral.sh/uv/) 管理（`pyproject.toml` + 已提交的 `uv.lock`）：

```powershell
winget install --id=astral-sh.uv -e     # 安装 uv；已安装可跳过
uv sync                                 # 创建 .venv，安装运行时依赖 + dev 依赖
uv run asfmkv --version
```

- 完全复现依赖：`uv sync --frozen`（CI 即如此）；升级依赖：`uv lock --upgrade`。
- 不用 uv 时：`pip install -e ".[dev]"`。
- 源码方式运行：`uv run python -m asfmkv`。

**运行环境**：Python ≥ 3.11（与 `requires-python` 一致），CI 使用 3.12。

**必需依赖**（版本范围见 `pyproject.toml`）：

| 依赖 | 用途 |
|---|---|
| `fonttools>=4.67,<5` | 字体解析与子集化 |
| `chardet>=7.6,<8` | 字幕编码检测 |
| `colorama>=0.4.6,<0.5` | Windows 控制台颜色 |

**可选外部工具**（缺失时相关功能自动降级，不影响其他功能）：

| 工具 | 用途 | 缺失时 |
|---|---|---|
| `mkvmerge` | 默认封装方式、语言代码 | 改用 FFmpeg 封装 |
| `ffmpeg` / `ffprobe` | FFmpeg 封装 | 只能使用 mkvmerge |
| `choice` | Windows 交互菜单按键 | 退化为文本输入 |

字体缓存在 `%APPDATA%\ASFMKVpy`，可随时删除，程序会自动重建；缓存目录不可写时自动跳过，不影响功能。

---

## 二、命令行接口

入口为 `asfmkv`，等价写法 `python -m asfmkv`。以下示例省略 `uv run` 前缀，
用 uv 时补上（如 `uv run asfmkv list-fonts ...`）。

不带子命令时进入交互式主菜单：

```powershell
uv run python -m asfmkv
```

### 2.1 通用参数

```text
ASFMKV [-h] [-v] [--ini INI] [--extlist EXTLIST] {list-fonts,subset,mux,transcode,match} ...
```

| 参数 | 说明 |
|---|---|
| `-h`, `--help` | 帮助；`asfmkv <子命令> --help` 查看子命令帮助 |
| `-v`, `--version` | 显示版本号 |
| `--ini <文件>` | 指定 `ASFMKVpy.ini`；默认读取程序目录（源码运行 = 项目根，打包后 = exe 同目录），不存在则只用内置默认值 |
| `--extlist <列表>` | 覆盖媒体扩展名，分号分隔，如 `"mkv;mp4;avi"` |

### 2.2 子命令一览

| 子命令 | 作用 | 对文件的影响 |
|---|---|---|
| `list-fonts` | 列出字幕所需字体 | 不改动源文件（可能生成报告 / 副本目录） |
| `subset` | 子集化字体，可选封装 / 内嵌 | 只生成新文件，不改动源文件 |
| `mux` | 直接封装媒体、字幕、字体 | 只生成新文件 |
| `transcode` | 字幕批量转 UTF-8-BOM | 生成新文件 |
| `match` | 媒体与字幕名称匹配 | 预览后确认才重命名 |

### 2.3 list-fonts

```powershell
asfmkv list-fonts <字幕文件或目录>
```

按 `[字符数] 字体名 <字体文件>` 列出所需字体，未找到的显示为 `[N] 字体名 - No Found`，
末尾给出字体概览。受这些配置开关影响：`resultw`（写出 `Fonts/fonts.txt`）、
`copyfont`（复制字体到 `Fonts/`）、`s_subdir`（搜索子目录）、`char_lost`（统计缺字，较慢）、
`exact_lost`（按字幕列出缺字字体）、`embedded_font_extract`（抽出内嵌字体）。

```powershell
asfmkv list-fonts "D:\Anime\ep01.sc.ass"
asfmkv list-fonts "D:\Anime\Season1"
```

### 2.4 subset

```powershell
asfmkv subset <媒体文件、字幕文件或目录> [选项]
```

| 参数 | 说明 |
|---|---|
| `--subtitle <文件>` | 指定字幕，可重复；指定后不再按文件名自动匹配 |
| `--out-ass` / `--out-font` / `--out-media` | 字幕 / 字体 / 媒体（或 MKS）输出目录 |
| `--mux` | 子集化后封装为 MKV（仅输入为媒体文件时生效） |
| `--mks` | 子集化后封装为外置 MKS（可批量；目录内有视频则按视频合并字幕） |
| `--embed` | 把子集字体内嵌进 ASS/SSA，不生成媒体文件 |
| `--pattern "<含 * 的规则>"` | 视频文件名规则（同交互菜单），按剧集把字幕归组，用于 `--mks` / `--embed` 批量 |
| `--ffmpeg` | 用 FFmpeg 而非 mkvmerge 封装（配合 `--mux`） |

四种模式：

1. 不带 `--mux` / `--mks` / `--embed`：只子集化。默认在字幕同目录生成 `*.subset.ass`，字体输出到 `Fonts/<字幕名>/`。
2. `--mux`：子集化 + 封装为 MKV（默认 mkvmerge，加 `--ffmpeg` 用 FFmpeg）。
3. `--mks`：子集化 + 封装为外置 MKS（含子集化字幕轨与子集字体附件，不含视频）；逐组处理：
   目录内有视频则同一视频的多条字幕合并为一个 mks，只有字幕则每条字幕各生成一个 mks
   （加 `--pattern` 可把同一集的 chs/cht 合并成一个 mks）。
4. `--embed`：把子集字体写入 ASS/SSA 的 `[Fonts]` 段，输出内嵌字体字幕；逐组内嵌，
   每份字幕只嵌入它自己用到的子集字体（不会把全剧集字体塞进每一份）。

```powershell
# 只子集化
asfmkv subset "D:\Anime\ep01.mkv" --out-ass "D:\Out\subs" --out-font "D:\Out\fonts"
# 子集化并封装
asfmkv subset "D:\Anime\ep01.mkv" --mux --out-media "D:\Out\mkv"
asfmkv subset "D:\Anime\ep01.mkv" --mux --ffmpeg --out-media "D:\Out\mkv"
# 字体内嵌进字幕（可批量）
asfmkv subset "D:\Anime\ep01.sc.ass" --embed --out-ass "D:\Out\embed"
asfmkv subset "D:\Anime\Season1" --embed --out-ass "D:\Out\embed"
# 生成外置 MKS（可批量，需要 mkvmerge）
asfmkv subset "D:\Anime\Season1" --mks --out-media "D:\Out\mks"
# 只有字幕没有视频时，用文件规则把同一集的字幕合并成一个 mks / 一起内嵌
asfmkv subset "D:\Out\subs" --mks --out-media "D:\Out\mks" --pattern "[VCB-Studio] Tsuki ga Kirei [*][Ma10p_1080p][x265_flac_dts]"
asfmkv subset "D:\Out\subs" --embed --out-ass "D:\Out\embed" --pattern "[VCB-Studio] Tsuki ga Kirei [*][Ma10p_1080p][x265_flac_dts]"
# 只处理指定字幕
asfmkv subset "D:\Anime\ep01.mkv" --subtitle "D:\Anime\ep01.sc.ass" --out-font "D:\Out\fonts"
```

> `--mks` 输出的 mks 文件名默认与字幕/视频同名、`.mks` 结尾；需安装 mkvmerge。
> `--pattern` 的写法和交互菜单的“视频文件名规则”一致：把每集不同的部分换成 `*`，
> 程序用匹配到的文本作为剧集名（也作为输出文件名）；匹配不到的字幕各自单独一组。
> 子集化细节由配置控制：`char_compatible`（广兼容子集）、`ignore_lost`（忽略缺字）、
> `error_stop`（失败即中断）、`fontload`（使用工作目录字体）等。
> 开启 `fontload`（默认）时会先自动载入字幕同目录及其名字含 `font` 的子目录里的字体，
> 所以把字体放在字幕目录的 `Fonts/` 下即可直接子集化。
> 缺少字体时会提示输入字体文件或所在目录；输入 `SKIPFONT`（全大写）跳过剩余缺失字体。

### 2.5 mux

```powershell
asfmkv mux <媒体文件> [选项]
```

| 参数 | 说明 |
|---|---|
| `--subtitle <文件>` | 追加字幕轨，可重复 |
| `--font <文件>` | 追加字体附件，可重复 |
| `-o`, `--output <文件>` | 输出路径（严格使用，不改名） |
| `--mks` | 输出外置字幕 `.mks` 而非 `.mkv` |

`mux` 不做子集化，只打包现成的媒体 / 字幕 / 字体，源文件不删除。
不指定 `-o` 时输出 `<媒体名>.muxed.mkv`，已存在则依次为 `<媒体名>.muxed#1.mkv`、`#2`……
`--mks` 用于只打包字幕与字体：**媒体不会被打包**，只用于推导输出文件名与轨道标题，
配合 `--font` 可把字体作为附件写入 mks。

```powershell
asfmkv mux "D:\Anime\ep01.mkv" --subtitle "D:\Out\subs\ep01.subset.ass" `
       --font "D:\Out\fonts\ep01\Arial.ABCD1234.ttf" -o "D:\Out\ep01.mkv"
asfmkv mux "D:\Anime\ep01.mkv" --subtitle "D:\Out\subs\ep01.subset.ass" -o "D:\Out\ep01.mks" --mks
asfmkv mux "D:\Anime\ep01.mkv" --subtitle "D:\Out\subs\ep01.subset.ass" `
       --font "D:\Out\fonts\ep01\Arial.ABCD1234.ttf" -o "D:\Out\ep01.mks" --mks
```

### 2.6 transcode

```powershell
asfmkv transcode <字幕文件或目录>
```

把 ASS/SSA/SRT 转为 **UTF-8-BOM**。目录输入的输出为 `UTF8-Subtitles/xxx.utf8.ass`；
单文件输入则在同目录生成 `xxx.utf8.ass`。已是 UTF-8-BOM 的文件提示 `[Already UTF-8-BOM]` 并跳过。

```powershell
asfmkv transcode "D:\Anime\Season1"
asfmkv transcode "D:\Anime\ep01.sc.ass"
```

### 2.7 match

```powershell
asfmkv match <字幕目录> <视频目录>
```

自动推断剧集编号位置，给出重命名预览，确认后执行；在字幕目录写入 `subsRename_*.log` 供撤销。

```powershell
asfmkv match "D:\Anime\subs" "D:\Anime\videos"
```

---

## 三、下载预发布版 / 自行打包

### 3.1 从 GitHub Actions 发布预发布版

仓库提供两个**手动触发**的工作流，每次输入版本号（如 `v0.0.1`）打包一次，
把 `ASFMKV.exe` 压缩成 zip 发布到**对应版本号的预发布 Release**（标签即版本号）：

| 工作流 | 打包方式 | 资产名（示例） |
|---|---|---|
| `.github/workflows/release-beta.yml` | Nuitka onefile | `ASFMKV-Nuitka-v0.0.1.zip` |
| `.github/workflows/release-beta-pyinstaller.yml` | PyInstaller onefile | `ASFMKV-PyInstaller-v0.0.1.zip` |

1. 打开仓库 **Actions** 页面，左侧选择任一工作流；
2. 点击 **Run workflow**，填写版本号（必填，如 `v0.0.1`）后运行；
3. 结束后到 **Releases** 打开对应标签（标记为 Pre-release），下载 zip 解压即可。

两个工作流发布到同一个版本号 Release，所以两个 zip 会出现在同一页面；
zip 内只有一个 `ASFMKV.exe`。重复运行同一版本号会覆盖同名资产。

两个入口工作流只是壳，实际打包 / 发布步骤都在可复用的
`.github/workflows/release-beta-build.yml`（`workflow_call`）里，改流程只需动这一个文件：

- 先 `uv sync --frozen --group build-<打包方式>`，只装当前打包方式需要的那套工具；
- 跑全量测试；
- 用输入的版本号生成 `asfmkv/_version.py`（该文件不入库），因此 `ASFMKV.exe --version`
  会与 Release 标签一致，同时写入 exe 的 Windows 文件版本属性；
- 打包后冒烟测试会校验 `--version` 输出确实包含该版本号；
- 发布时把资产传到同名预发布 Release；若该标签已经是正式 Release，则拒绝覆盖。

另外 `.github/workflows/ci.yml` 在 push / PR 时跑 ruff + 单元测试（Python 3.11 / 3.12），
以及单独一个默认装了 mkvmerge / ffmpeg 的集成测试 job。


### 3.2 本地用 Nuitka 打包

打包入口 `build_entry.py` 已随仓库提供（等价于 `python -m asfmkv`）。

```powershell
uv sync --group build-nuitka     # 安装 nuitka / zstandard

# 缓存放到项目内：%LOCALAPPDATA% 不可写的受限环境必需
$env:NUITKA_CACHE_DIR = "$PWD\.cache\nuitka"
# 受限环境还要把 TEMP 指到项目内，否则 MSVC 链接器会报
# LNK1104: 无法打开文件 "...\Temp\lnk{...}.tmp"
$env:TEMP = "$PWD\.cache\tmp"; $env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

uv run python -m nuitka --standalone --onefile --assume-yes-for-downloads `
    --include-package=asfmkv --include-package-data=fontTools `
    --windows-console-mode=force `
    --output-dir=dist --output-filename=ASFMKV.exe build_entry.py
```

> 受限环境（临时目录不可写）有两处会出问题：构建时 MSVC 链接器报
> `LNK1104: ...\Temp\lnk{...}.tmp`，运行时报
> `failed to open ...\onefile_...\build_entry.dll for writing`。
> 构建时按上面把 `TEMP`/`TMP` 指到项目内；运行单文件版时同样先把 `TEMP` 指向可写目录，
> 或去掉 `--onefile` 生成免解包的目录版（`dist/build_entry.dist/`，最稳）。
>
> 本地打包沿用源码里的 `APP_VERSION`（当前为 `Pre25-refactor`）；发布工作流会生成
> `asfmkv/_version.py` 覆盖它。想在本地复现发布版本号，手动写这个文件即可：
> `'APP_VERSION = "0.0.1"' | Set-Content asfmkv/_version.py -Encoding utf8`（该文件已被 git 忽略）。

### 3.3 本地用 PyInstaller 打包

```powershell
uv sync --group build-pyinstaller  # 安装 pyinstaller

$env:PYINSTALLER_CONFIG_DIR = "$PWD\.cache\pyinstaller"
# 受限环境同样把 TEMP 指到项目内（见 3.2）
$env:TEMP = "$PWD\.cache\tmp"; $env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

uv run python -m PyInstaller --noconfirm --clean --onefile --console --name ASFMKV `
    --distpath dist --workpath build `
    --collect-all fontTools --collect-all chardet build_entry.py
```

> 报 `failed to create cache directory` 或无法写 `%LOCALAPPDATA%` 时，检查上面的缓存目录变量。
> 两种方式的产物都是 `dist/ASFMKV.exe`（先后运行会互相覆盖，任选其一）。
> 单文件版运行时要解包到 `%TEMP%`；若报 `Could not create temporary directory!`
> 或解压失败（受限终端 / 沙箱），说明临时目录不可写：先把 TEMP 指到可写目录（见 3.2），
> 在普通桌面环境运行，或加 `--onedir` 生成免解包的目录版。
> `ASFMKVpy.ini` 需放在 exe 同目录；`mkvmerge` / `ffmpeg` 为可选依赖，
> 缺失时相关功能自动降级；首次运行可能被 SmartScreen 拦截。

---

## 四、配置文件 ASFMKVpy.ini

优先级：内置默认值 < `ASFMKVpy.ini` < 命令行参数。键名大小写不敏感，兼容旧字段名
（如 `usingFF`、`matchStrict`、`noRequestFont`）。

```ini
[settings]
; 布尔值：1 为真，其余为假
usingFF=0
notfont=0
matchStrict=1
char_compatible=1
extlist=mkv,mp4,mts,mpg,avi
; 自定义字体目录，以 ? 分隔
fontin=D:\Fonts?E:\MoreFonts
```

常用开关：

| 键 | 含义 |
|---|---|
| `usingFF` | 启动时检测并启用 FFmpeg |
| `notfont` | 封装时不附加字体 |
| `noRequestFont` | 缺少字体时不询问，直接跳过 |
| `char_compatible` | 广兼容性子集化（补齐数字/字母） |
| `ignoreLost` | 忽略字体缺少的字符 |
| `errorStop` | 子集化失败即中断 |
| `fontload` / `s_fontload` | 使用工作目录 / 子目录中的字体 |
| `rmAssIn` / `rmAttach` | 封装时移除内挂字幕 / 原有附件 |
| `v_subdir` / `s_subdir` | 搜索子目录（视频 / 字幕） |
| `copyfont` / `resultw` | 复制所需字体到 `Fonts/` / 写出结果文件 |
| `subl_local` | 界面语言区域代码，如 `zh_CN` |

---

## 五、项目结构

```text
pyproject.toml  依赖与工具配置（uv / pytest / ruff）
uv.lock         依赖锁定文件（随代码提交）
build_entry.py  打包入口（Nuitka / PyInstaller 共用）
asfmkv/
  cli.py        命令行入口
  config/       配置模型、旧 INI 兼容层
  core/         异常、日志与颜色
  platform/     控制台交互、注册表、缓存路径
  utils/        文件、CRC、子进程、编码检测
  fonts/        字体扫描 / 解析 / 缓存 / 子集化
  ass/          ASS/SSA 解析、写回、字体使用分析
  mux/          mkvmerge / FFmpeg / 内嵌封装
  match/        媒体扫描、字幕匹配、重命名
  services/     高层用例
  ui/           交互菜单
tests/
  unit/         单元测试
  integration/  集成测试（需系统字体或外部工具）
.github/workflows/
  ci.yml                        push / PR：ruff + 单元 / 集成测试
  release-beta.yml              Nuitka 发布入口
  release-beta-pyinstaller.yml  PyInstaller 发布入口
  release-beta-build.yml        两个入口共用的打包 / 发布实现
```

## 六、测试

```powershell
uv run pytest -q                        # 全部测试
uv run pytest -q -m "not integration"   # 跳过集成测试
uv run ruff check asfmkv tests          # 静态检查
```

> 不用 uv：`pip install -e ".[dev]"` 后直接 `python -m pytest -q` / `ruff check asfmkv tests`。
>
> CI（`.github/workflows/ci.yml`）会跑：ruff 静态检查、单元测试（Python 3.11 / 3.12）、
> 集成测试（单独 job，先装 mkvmerge / ffmpeg）。

---

## 七、许可证

[Apache License 2.0](LICENSE)，完整条款见 `LICENSE`。
