# Media Archive Organizer

[English](README.md) | [日本語](README_ja.md)

面向高级用户的媒体整理工具，适用于需要重复检测、严格匹配和更高可控性的归档场景。

程序会优先读取图片 EXIF 时间；如果没有 EXIF 时间，则使用文件修改时间。
整理后的文件会按“年\月\日”的目录结构输出到目标目录中。

它支持：

- 基于日期的目录整理
- `move` / `copy` 两种模式
- 面向相似图片的 pHash 重复检测
- 面向完全一致文件的 SHA-256 严格检测
- 多语言命令行提示
- 每次运行独立日志，方便追溯

语言导航：

- English: [README.md](./README.md)
- 中文: [README_zh.md](./README_zh.md)
- 日本語: [README_ja.md](./README_ja.md)


## 项目定位

这是增强版媒体整理工程，适用于需要重复检测、严格匹配和更高可控性的场景。

相较于基础版按日期整理工具，它额外提供：

- 重复检测
- 严格的完全一致文件匹配
- 带阈值控制的相似图片检测
- 持久化 `hash_db`
- 更强的目标目录安全限制
- 最小自动化冒烟测试

如果你只需要低复杂度的按日期整理功能，基础版工具会更合适。


## 功能简介

- 递归扫描源目录中的子目录
- 按日期自动整理图片和视频
- 默认使用 `move` 模式移动文件
- 支持 `copy` 模式保留原文件
- 支持重复检测：可关闭、相似图片检测（pHash）或严格文件检测（SHA-256）
- 支持中文、英文、日文界面
- 每次运行自动生成独立日志文件
- 同名文件自动追加序号，避免直接覆盖
- 检测到重复图片时，会按 `保留文件名_dupN.ext` 的规则重命名并继续放入正式归档目录
- 自动生成 `duplicate_report.csv` 便于追溯重复文件关系
- 自动生成 `duplicates.json`，便于其他工具读取结构化重复结果


## 支持的文件类型

- `.jpg`
- `.jpeg`
- `.png`
- `.mp4`
- `.mov`


## 运行环境

- Windows 10 或 Windows 11
- Python 3.10 或更高版本
- 依赖库：`Pillow`, `exifread`, `pywin32`（仅限 Windows）

安装依赖：

```powershell
.\venv\Scripts\python.exe -m pip install Pillow exifread pywin32
```

说明：

- 建议先在项目根目录执行 `python -m venv venv`
- 项目的虚拟环境默认位于 `.\venv`
- 更推荐使用 `.\venv\Scripts\python.exe` 和 `.\venv\Scripts\pip.exe`，这样可以明确知道依赖安装到了当前项目的虚拟环境中
- 如果直接执行 `python` 或 `pip`，有可能调用到系统 Python 或其他虚拟环境

## 基本用法

请先进入项目根目录，再执行命令：

```powershell
cd D:\01_wk\16_person\ZeroTraceBrowser\media_engine
```

推荐执行方式：

```powershell
.\venv\Scripts\python.exe .\main.py --src 源目录 --dst 目标目录
```

示例：

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos
```


## 启动参数

### `--src`

源目录，必填。

### `--dst`

目标目录，必填。

### `--mode`

整理模式，可选：

- `move`：移动文件，默认值
- `copy`：拷贝文件，保留原文件

示例：

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --mode copy
```

### `--lang`

界面语言，可选：

- `zh`：中文
- `en`：英文
- `ja`：日文

示例：

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --lang en
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --lang ja
```

### `--duplicate-detection`

重复检测模式，可选：

- `off`：关闭重复检测
- `phash`：使用 pHash 检测相似图片
- `strict`：使用 SHA-256 检测完全一致文件
- `both`：同时取得 SHA-256 和 pHash，先检查 strict，再检查相似图片

说明：

- `phash` 更适合检测视觉上相近的图片
- `strict` 更适合严格用户，只有文件内容完全一致才会判定为重复
- `both` 会保留两种 hash，便于之后同时支持精确重复和相似图片流程
- `hash_db` 仅作为当前目标目录下的参考，不会把文件导向其他历史目标目录
- 检测到重复后，文件仍会移动或拷贝到正常的日期归档目录中
- 重复文件会基于首个保留文件名重命名，例如 `photo_dup1.jpg`、`photo_dup2.jpg`
- 每次运行会在日志同目录追加写入 `duplicate_report.csv`
- 每次运行也会在日志同目录生成 `duplicates.json`，用于保存结构化重复分组

示例：

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection off
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection strict
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection both
```

### `--phash-threshold`

设置 pHash 相似检测的最大汉明距离，默认值为 `4`。

说明：

- 数值越小，判定越严格
- 数值越大，越容易把相似图片视为重复
- 在 `--duplicate-detection phash` 或 `--duplicate-detection both` 时生效

示例：

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection phash --phash-threshold 4
```

### `--rebuild-hash-db-root`

从指定的已整理归档目录重建 `hash_db.json`。

说明：

- 使用该参数时不需要同时指定 `--src` 和 `--dst`
- 重建过程会扫描指定目录下支持的媒体文件
- 该命令只重建 `hash_db.json`；`duplicates.json` 会在正常整理运行并检测到重复时生成

示例：

```powershell
.\venv\Scripts\python.exe .\main.py --rebuild-hash-db-root D:\SortedPhotos
```

### `--rebuild-hash-db-mode`

设置 `hash_db.json` 的重建方式，可选：

- `replace`：覆盖重建，默认值
- `append`：保留已有记录并追加新记录

示例：

```powershell
.\venv\Scripts\python.exe .\main.py --rebuild-hash-db-root D:\SortedPhotos --rebuild-hash-db-mode append
```

### `--rebuild-hash-method`

设置重建时使用的 hash 类型，可选：

- `strict`：只重建 SHA-256 严格匹配记录
- `phash`：只重建 pHash 相似图片记录
- `both`：同时重建两种记录，默认值

示例：

```powershell
.\venv\Scripts\python.exe .\main.py --rebuild-hash-db-root D:\SortedPhotos --rebuild-hash-method both
```


## 常用示例

### 默认移动文件

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos
```

### 拷贝文件，不删除源文件

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --mode copy
```

### 使用英文界面

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --lang en
```

### 使用日文界面

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --lang ja
```

### 使用严格重复检测

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection strict
```

### 使用相似图片检测

```powershell
.\venv\Scripts\python.exe .\main.py --src D:\InputPhotos --dst D:\SortedPhotos --duplicate-detection phash --phash-threshold 4
```

### 从已整理目录重建 hash_db

```powershell
.\venv\Scripts\python.exe .\main.py --rebuild-hash-db-root D:\SortedPhotos --rebuild-hash-db-mode replace --rebuild-hash-method both
```


## 日志说明

程序每次运行都会自动在脚本所在目录下创建或使用 `log` 文件夹。

日志文件名格式如下：

```text
organize_log_YYYYMMDD_HHMMSS.txt
```

例如：

```text
organize_log_20260413_135222.txt
```

程序执行完成后，终端会显示本次日志文件的完整路径。

如果本次运行检测到了重复文件，还会在同一目录下追加生成：

```text
duplicate_report.csv
```

同时会生成结构化重复结果：

```text
duplicates.json
```

当前 CSV 至少包含以下字段：

- `original_name`
- `original_path`
- `kept_path`
- `duplicate_method`
- `hash`
- `duplicate_path`


## 整理规则

- 程序会递归扫描源目录中的所有子目录
- 优先读取图片 EXIF 时间
- 若无 EXIF 时间，则使用文件修改时间
- 按 `目标目录\年\月\日\` 的形式输出
- 若启用重复检测，只会参考当前目标目录中的历史记录
- 若目标目录存在同名文件，会自动追加序号
- 检测到重复文件时，仍会继续放入正常归档目录
- 重复文件会基于保留文件名追加 `_dupN`

同名文件示例：

```text
photo.jpg
photo_1.jpg
photo_2.jpg
```

重复检测命名示例：

```text
photo.jpg
photo_dup1.jpg
photo_dup2.jpg
```


## 文件结构说明

- `main.py`
  程序入口
- `core/`
  日期识别和 EXIF 读取逻辑
- `services/`
  文件整理逻辑
- `locales/`
  中英日提示文本
- `log/`
  每次运行生成的日志目录


## 注意事项

- 请确保源目录和目标目录填写正确
- 目标目录不能是源目录本身，也不能位于源目录内部
- 默认 `move` 模式会将文件从源目录移走
- 如果需要保留原文件，请使用 `--mode copy`
- 建议首次先使用少量文件测试
- 建议重要资料先备份再处理


## 常见失败原因

- 文件被占用，无法移动或拷贝
- 文件没有读取权限
- 图片 EXIF 信息异常
- 目标目录没有写入权限


## 免责声明

本工具用于对图片和视频文件进行自动整理。
在实际使用中，仍可能因路径错误、权限问题、文件占用、磁盘异常、时间信息错误、程序中断或其他不可预见因素导致整理结果不符合预期。

请特别注意以下事项：

- 默认 `move` 模式会移动原文件
- 同名文件会自动重命名
- EXIF 或文件时间不准确时，目标日期目录可能不符合真实拍摄日期
- 日志仅用于辅助排查，不构成结果完整性保证

为降低风险，建议：

1. 首次使用时先处理少量测试文件
2. 优先使用 `--mode copy` 验证效果
3. 正式处理前备份重要数据
4. 处理完成后检查日志与目标目录
