import sys
import os
import json
import logging
import requests
import webbrowser
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer


def get_base_path():
    """获取程序基础路径，兼容开发环境和打包后的 exe"""
    if getattr(sys, 'frozen', False):  # 是否被打包
        return os.path.dirname(sys.executable)  # exe 所在目录
    else:
        return os.path.dirname(__file__)  # 脚本所在目录


# ==================== 配置区 ====================
TARGET_URL = "https://jwc.cuit.edu.cn/"
MORE_LINK = "https://jwc.cuit.edu.cn/"
CHECK_INTERVAL = 30 * 60 * 1000  # 30分钟
BASE_DIR = get_base_path()
CACHE_DIR = os.path.join(BASE_DIR, "cache")
ICON_PATH = os.path.join(BASE_DIR, "assets", "101309096_p0.ico")
DATA_FILE = os.path.join(CACHE_DIR, "notices.json")
LOG_FILE = os.path.join(CACHE_DIR, "monitor.log")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)  # 使用 makedirs 更安全
# ================================================

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台（便于调试）
    ]
)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(QIcon(ICON_PATH))
        self.setToolTip("通知监控 - 教学运行")
        self._create_menu()
        # 启动后立即执行第一次检查（根据文件是否存在决定是否通知）
        QTimer.singleShot(0, self._first_check)
        # 启动定时自动检查
        self.timer = QTimer()
        self.timer.timeout.connect(self._auto_check)
        self.timer.start(CHECK_INTERVAL)

    def _create_menu(self):
        menu = QMenu()

        manual_action = QAction("获取通知", self)
        manual_action.triggered.connect(self._manual_check)

        open_latest_news = QAction("打开最新通知", self)
        open_latest_news.triggered.connect(self._open_latest_news)

        open_action = QAction("打开教务处网站", self)
        open_action.triggered.connect(self._open_web)

        open_dir = QAction("程序文件夹", self)
        open_dir.triggered.connect(lambda: os.startfile(BASE_DIR))

        open_cache = QAction("日志文件夹", self)
        open_cache.triggered.connect(lambda: os.startfile(CACHE_DIR))

        # 开机自启切换
        self.auto_start_action = QAction("开机自启", self)
        self.auto_start_action.setCheckable(True)
        self.auto_start_action.setChecked(self._is_auto_start_enabled())
        self.auto_start_action.triggered.connect(self._toggle_auto_start)
        menu.addAction(manual_action)
        menu.addSeparator()
        menu.addActions([open_action, open_latest_news, open_dir, open_cache, self.auto_start_action])

        menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self._exit_app)
        menu.addAction(exit_action)

        self.setContextMenu(menu)

    def _first_check(self):
        """首次启动检查：若已有缓存文件则对比并通知，否则仅保存"""
        try:
            current = fetch_notices()
            if current is None:
                logging.error("首次抓取失败")
                return

            # 尝试加载旧数据
            old = self._load_notices()
            if old:  # 有旧数据 → 检查新通知
                new = get_new_notices(old, current)
                if new:
                    self._show_message("有新通知", format_notices(new))
                    logging.info(f"启动时发现 {len(new)} 条新通知")
                else:
                    logging.info("启动时无新通知")
            else:  # 无旧数据（首次运行）→ 仅保存，不通知
                logging.info("首次运行，初始化数据文件，不发送通知")

            # 更新内存和文件
            self.last_notices = current
            self._save_notices(current)

        except Exception as e:
            logging.exception(f"首次检查异常: {e}")

    def _auto_check(self):
        """定时自动检查：只在新通知时提醒，失败时不通知"""
        try:
            # 每次从文件加载旧数据，确保基准最新
            old = self._load_notices()
            current = fetch_notices()
            if current is None:
                logging.warning("自动抓取失败，保持静默")
                return

            new = get_new_notices(old, current)
            if new:
                self._show_message("有新通知", format_notices(new))
                logging.info(f"自动检查发现 {len(new)} 条新通知")
            else:
                logging.info("自动检查无新通知")

            # 无论有无新通知，更新保存
            self.last_notices = current
            self._save_notices(current)

        except Exception as e:
            logging.exception(f"自动检查异常: {e}")

    def _manual_check(self):
        """手动获取：总是发送通知"""
        try:
            old = self._load_notices()
            current = fetch_notices()
            if current is None:
                self._show_message("错误", "获取通知失败，请检查网络或页面")
                logging.error("手动抓取失败")
                return

            new = get_new_notices(old, current)
            if new:
                self._show_message("有新通知", format_notices(new))
                logging.info(f"手动检查发现 {len(new)} 条新通知")
            else:
                self._show_message("暂无新通知", f"最近一条：{old[0].get('title')}")
                logging.info("手动检查无新通知")

            # 更新保存
            self.last_notices = current
            self._save_notices(current)

        except Exception as e:
            self._show_message("异常", f"手动获取时出错: {e}")
            logging.exception(f"手动检查异常: {e}")

    def _open_latest_news(self):
        old = self._load_notices()
        if old:
            webbrowser.open(old[0].get("link"))
        else:
            self._show_message("错误", "历史记录为空！")

    def _open_web(self):
        webbrowser.open(MORE_LINK)

    def _exit_app(self):
        QApplication.quit()

    def _show_message(self, title, message):
        self.showMessage(title, message, QIcon(ICON_PATH), 5000)

    def _load_notices(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"读取缓存文件失败: {e}")
                return []
        return []

    def _save_notices(self, notices):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(notices, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存缓存文件失败: {e}")

    # ---------- 开机自启相关 ----------
    def _is_auto_start_enabled(self):
        """检查注册表Run键中是否存在本程序"""
        if sys.platform != 'win32':
            return False
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, "TeachingMonitor")
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            logging.warning(f"检查开机自启状态失败: {e}")
            return False

    def _set_auto_start(self, enable):
        """设置或取消开机自启（仅Windows，且仅支持打包后的exe）"""
        if sys.platform != 'win32':
            self._show_message("不支持", "仅Windows支持开机自启设置")
            return

        # 未打包时提示需先打包（因为sys.executable可能是python.exe，会导致控制台窗口）
        if not getattr(sys, 'frozen', False):
            self._show_message("提示", "请先将程序打包为exe再设置开机自启")
            return

        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            if enable:
                exe_path = sys.executable
                value = f'"{exe_path}"'  # 路径加引号以防空格
                winreg.SetValueEx(key, "TeachingMonitor", 0, winreg.REG_SZ, value)
                logging.info("已设置开机自启")
            else:
                try:
                    winreg.DeleteValue(key, "TeachingMonitor")
                    logging.info("已取消开机自启")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            # 更新菜单项勾选状态
            self.auto_start_action.setChecked(enable)
        except Exception as e:
            logging.exception(f"设置开机自启失败: {e}")
            self._show_message("错误", f"设置开机自启失败: {e}")

    def _toggle_auto_start(self, checked):
        """切换开机自启状态"""
        self._set_auto_start(checked)


def fetch_notices():
    """抓取页面，返回通知列表，失败返回 None"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        resp = requests.get(TARGET_URL, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 定位“教学运行”标题所在的 panel-heading
        headings = soup.find_all('div', class_='panel-heading')
        target_heading = None
        for h in headings:
            if '教学运行' in h.get_text():
                target_heading = h
                break
        if not target_heading:
            logging.error("未找到“教学运行”标题")
            return None

        panel_body = target_heading.find_next_sibling('div', class_='panel-body')
        if not panel_body:
            logging.error("未找到对应的 panel-body")
            return None

        titles = panel_body.find_all('div', class_='title')
        notices = []
        for div in titles:
            h5 = div.find('h5', class_='col_5')
            if not h5:
                continue
            a = h5.find('a')
            if not a:
                continue
            link = a.get('href', '')
            if link:
                link = urljoin(TARGET_URL, link)
            title = a.get_text(strip=True)
            h6 = div.find('h6')
            date = h6.get_text(strip=True) if h6 else ''
            notices.append({
                'title': title,
                'link': link,
                'date': date
            })
        logging.info(f"抓取成功，共 {len(notices)} 条通知")
        return notices
    except Exception as e:
        logging.exception(f"抓取过程异常: {e}")
        return None


def get_new_notices(old_list, new_list):
    old_links = {item['link'] for item in old_list}
    return [item for item in new_list if item['link'] not in old_links]


def format_notices(notices, max_preview=3):
    if not notices:
        return "无"
    lines = [item['title'] for item in notices[:max_preview]]
    if len(notices) > max_preview:
        lines.append(f"等 {len(notices)} 条新通知")
    return '\n'.join(lines)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    if not os.path.exists(ICON_PATH):
        logging.warning(f"图标文件 {ICON_PATH} 不存在，托盘图标可能不可见")

    tray = TrayIcon()
    tray.show()
    sys.exit(app.exec())
