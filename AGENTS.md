# Repository Guidelines

## 项目结构与模块组织
`app/` 放托盘应用入口：`main.py` 负责生命周期和日志初始化，`tray.py` 负责托盘菜单和报告窗口。`scripts/` 放监控与报表脚本，包括 `active_monitor.py`、`input_hook.py`、`browsing_monitor.py` 和 `watchdog.py`。运行期数据写入 `data/`，如 `active/`、`daily/`、`*.log`、`state.json`，这些属于本地产物，不应视为源码。`build/` 与 `dist/` 是 PyInstaller 打包输出，`TimeCraft.spec` 定义打包入口和资源。

## 构建、测试与开发命令
先执行 `pip install -r requirements.txt` 安装依赖。

- `python app/main.py`：本地启动托盘应用。
- `python scripts/active_monitor.py`：只运行前台活动监控。
- `python scripts/browsing_monitor.py`：采集浏览器历史并写入 `data/daily/`。
- `python scripts/browsing_monitor.py report 2026-05-28`：为指定日期生成日报。
- `pyinstaller TimeCraft.spec`：打包 Windows 可执行文件到 `dist/`。

## 编码风格与命名约定
使用 Python 3，统一 4 空格缩进。函数和变量使用 `snake_case`，类名使用 `PascalCase`，例如 `TrayApp`。控制流保持平坦，优先早返回。Windows API、进程探测和钩子逻辑集中放在 `scripts/`，不要扩散到 UI 层。注释只说明意图、边界和取舍，不复述代码字面意思。涉及中文文案或报告内容的文件统一使用 UTF-8。

## 测试要求
当前仓库还没有提交自动化测试。每次改动后，先做最小相关验证：托盘改动运行 `python app/main.py`，钩子或心跳相关改动运行 `python scripts/active_monitor.py`，报表相关改动运行 `python scripts/browsing_monitor.py report <date>`。如果新增自动化测试，放到 `tests/` 目录，文件名使用 `test_*.py`，保证 `pytest` 可直接发现。

## 提交与合并请求规范
沿用现有历史里的提交风格：使用 `feat:`、`refactor:` 等简短前缀，后面跟精炼摘要。一次提交只解决一个功能点，不要把无关修改混在一起。提交 PR 时应写清影响范围，是 `app/`、监控、报表还是打包链路；列出在 Windows 上做过的手工验证步骤；如果改了托盘界面或报告窗口，附截图。

## 数据与配置说明
不要提交 `data/` 下生成的监控数据、日志或心跳文件。调整路径配置时，要同时检查本地运行路径和 `TimeCraft.spec` 中的打包路径，保证两边保持一致。
