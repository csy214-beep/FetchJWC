# FetchJWC

CUIT教务处“教学运行”通知监控工具。
常驻系统托盘，定时抓取新通知并弹出提醒。

## 功能

- 定时检查（默认30分钟）教务处网站“教学运行”板块。
- 发现新通知时托盘弹出提示，显示标题。
- 右键菜单：手动获取、打开网页、开机自启（Windows）、退出。
- 缓存已读通知，避免重复提醒。

## 使用方式

### 直接下载（推荐）

从 [Releases](https://github.com/csy214-beep/FetchJWC/releases) 下载最新的 `FetchJWC.exe`，运行即可（需将 `assets` 文件夹置于同目录）。

### 从源码运行

需要 Python 3.8+。

```bash
git clone https://github.com/csy214-beep/FetchJWC.git
cd FetchJWC
python -m venv .venv
.venv\Scripts\activate  # Windows
# 或 source .venv/bin/activate (Linux/macOS)
pip install -r requirements.txt
python main.py
```

### 打包成 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=assets/101309096_p0.ico --add-data "assets;assets" main.py
```

## 配置

编辑 `main.py` 开头的配置区可修改检查间隔、目标网址、缓存路径等。

## 许可证

MIT © igugyj
