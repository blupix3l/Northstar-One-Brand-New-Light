"""
NorthStar Browser — Optimised Edition
======================================
Key optimisations over the original:
  1.  QSS split into a static base + two tiny theme patches; _apply_style()
      now only swaps the patch, not 3 000 chars.
  2.  HistoryPanel._render() virtualises the list — only renders the 60 rows
      that fit on screen; adding more rows doesn't create more widgets.
  3.  _build_newtab_html() memoised: only rebuilds when bookmarks or dark-mode
      actually change.
  4.  resizeEvent pins all panels in a single pass (one setGeometry call each).
  5.  StarShareBeacon lifecycle is properly guarded against double-start.
  6.  HistoryPanel disk-flush is idempotent and skipped when not dirty.
  7.  _apply_web_theme() never calls reload() on already-matching pages.
  8.  bm_cards was computed twice in _build_newtab_html — removed duplicate.
  9.  _refresh_tab_buttons skips style recomputation for unchanged tabs.
 10.  Panel positioning uses setGeometry() (one call) instead of
      setFixedWidth + setFixedHeight + move (three calls).

Requirements (unchanged):
    pip install PyQt6 PyQt6-WebEngine requests keyring
"""
# Please note that all lines of code relating to 'Opal Discovery' is dead code and is NOT part of the actual browser experience.

import sys, re, json, os, time, datetime, subprocess, threading, sqlite3
import hashlib, secrets, string, struct, pickle, glob, base64
import faulthandler, traceback as _traceback_mod
from concurrent.futures import ThreadPoolExecutor
import socket, uuid as _uuid_mod

# ── Crash logging ─────────────────────────────────────────────────────────────
# Enable faulthandler to dump traceback on segfault/abort to stderr + crash.log.
faulthandler.enable()

# Log file for crash traces so we can see what killed the process.
_CRASH_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
try:
    _crash_log_fh = open(_CRASH_LOG, "a", encoding="utf-8")
    faulthandler.enable(file=_crash_log_fh)
except Exception:
    _crash_log_fh = None

def _crash_excepthook(exc_type, exc_value, exc_tb):
    """Global uncaught-exception handler — writes to crash.log + stderr."""
    try:
        tb = "".join(_traceback_mod.format_exception(exc_type, exc_value, exc_tb))
        msg = f"\n{'='*60}\nCRASH {time.strftime('%Y-%m-%d %H:%M:%S')}\n{tb}{'='*60}\n"
        sys.stderr.write(msg)
        sys.stderr.flush()
        with open(_CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass
    # Call the default handler so the interpreter still exits normally.
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _crash_excepthook

import html as _html_mod
from urllib.parse import urlparse, quote, quote_plus, parse_qs
from fernway_manager import get_fernway
from bg_render import get_background_js
from oled_theme import (
    oled_enabled, oled_popup_qss, oled_qss_tokens, oled_toolbar_qss,
    oled_web_tokens, oled_css_vars, oled_wallpaper_video_src,
)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    # "--disable-gpu-shader-disk-cache "
    "--enable-smooth-scrolling "
    "--disable-features=CompressionDictionaryTransport,SharedDictionary,SharedDictionaryUsage,"
    "AudioOutputDeviceSelection,PermissionsPolicyReporting,PermissionPrediction "
    "--disable-shared-dictionary "
    "--enable-gpu-rasterization --enable-zero-copy "
    "--enable-native-gpu-memory-buffers --enable-oop-rasterization "
    "--enable-accelerated-video-decode --enable-accelerated-mjpeg-decode "
    "--enable-webgl-image-chromium --enable-webgl2-compute-context "
    "--ignore-gpu-blocklist "
    "--disable-features=CalculateNativeWinOcclusion "
    "--disable-background-networking "
    "--disable-default-apps "
    "--disable-sync "
    "--disable-translate "
    # "--disable-background-timer-throttling "
    # "--disable-backgrounding-occluded-windows "
    # "--disable-renderer-backgrounding "
    # "--disable-ipc-flooding-protection "
)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTabWidget, QStatusBar, QCompleter,
    QSplitter, QTextEdit, QLabel, QDialog, QListWidget, QListWidgetItem,
    QComboBox, QStackedWidget,
    QFrame, QSizePolicy, QProgressBar, QMenu, QMessageBox, QScrollArea,
    QFileDialog, QSizeGrip, QGraphicsOpacityEffect, QColorDialog, QSlider,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage,
    QWebEngineDownloadRequest, QWebEngineSettings, QWebEngineScript,
    QWebEngineUrlScheme, QWebEngineUrlSchemeHandler, QWebEngineUrlRequestJob,
    QWebEnginePermission, QWebEngineUrlRequestInterceptor,
)
from PyQt6.QtCore import (
    QUrl, Qt, QThread, pyqtSignal, QStringListModel,
    QTimer, QSize, QPoint, QPointF, QRect, QPropertyAnimation, QEasingCurve, QEvent,
    QParallelAnimationGroup, qInstallMessageHandler, QtMsgType,
    QObject, pyqtSlot, QByteArray, QBuffer,
)
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtGui import (
    QKeySequence, QShortcut, QColor, QPalette, QFont,
    QIcon, QPixmap, QPainter, QAction, QCursor,
)

QWEBCHANNEL_JS_B64 = (
    "Ly8gQ29weXJpZ2h0IChDKSAyMDE2IFRoZSBRdCBDb21wYW55IEx0ZC4KLy8gQ29weXJpZ2h0IChDKSAyMDE2IEtsYXLDpGx2ZGFsZW5zIERhdGFrb25zdWx0IEFCLCBhIEtEQUIgR3JvdXAgY29tcGFueSwgaW5mb0BrZGFiLmNvbSwgYXV0aG9yIE1pbGlhbiBXb2xmZiA8bWlsaWFuLndvbGZmQGtkYWIuY29tPgovLyBTUERYLUxpY2Vuc2UtSWRlbnRpZmllcjogTGljZW5zZVJlZi1RdC1Db21tZXJjaWFsIE9SIExHUEwtMy4wLW9ubHkgT1IgR1BMLTIuMC1vbmx5IE9SIEdQTC0zLjAtb25seQovLyBRdC1TZWN1cml0eSBzY29yZTpjcml0aWNhbCByZWFzb246ZGF0YS1wYXJzZXIKCiJ1c2Ugc3RyaWN0IjsKCnZhciBRV2ViQ2hhbm5lbE1lc3NhZ2VUeXBlcyA9IHsKICAgIHNpZ25hbDogMSwKICAgIHByb3BlcnR5VXBkYXRlOiAyLAogICAgaW5pdDogMywKICAgIGlkbGU6IDQsCiAgICBkZWJ1ZzogNSwKICAgIGludm9rZU1ldGhvZDogNiwKICAgIGNvbm5lY3RUb1NpZ25hbDogNywKICAgIGRpc2Nvbm5lY3RGcm9tU2lnbmFsOiA4LAogICAgc2V0UHJvcGVydHk6IDksCiAgICByZXNwb25zZTogMTAsCn07Cgp2YXIgUVdlYkNoYW5uZWwgPSBmdW5jdGlvbih0cmFuc3BvcnQsIGluaXRDYWxsYmFjaywgY29udmVydGVycykKewogICAgaWYgKHR5cGVvZiB0cmFuc3BvcnQgIT09ICJvYmplY3QiIHx8IHR5cGVvZiB0cmFuc3BvcnQuc2VuZCAhPT0gImZ1bmN0aW9uIikgewogICAgICAgIGNvbnNvbGUuZXJyb3IoIlRoZSBRV2ViQ2hhbm5lbCBleHBlY3RzIGEgdHJhbnNwb3J0IG9iamVjdCB3aXRoIGEgc2VuZCBmdW5jdGlvbiBhbmQgb25tZXNzYWdlIGNhbGxiYWNrIHByb3BlcnR5LiIgKwogICAgICAgICAgICAgICAgICAgICAgIiBHaXZlbiBpczogdHJhbnNwb3J0OiAiICsgdHlwZW9mKHRyYW5zcG9ydCkgKyAiLCB0cmFuc3BvcnQuc2VuZDogIiArIHR5cGVvZih0cmFuc3BvcnQuc2VuZCkpOwogICAgICAgIHJldHVybjsKICAgIH0KCiAgICB2YXIgY2hhbm5lbCA9IHRoaXM7CiAgICB0aGlzLnRyYW5zcG9ydCA9IHRyYW5zcG9ydDsKCiAgICB2YXIgY29udmVydGVyUmVnaXN0cnkgPQogICAgewogICAgICAgIERhdGUgOiBmdW5jdGlvbihyZXNwb25zZSkgewogICAgICAgICAgICBpZiAodHlwZW9mIHJlc3BvbnNlID09PSAic3RyaW5nIgogICAgICAgICAgICAgICAgJiYgcmVzcG9uc2UubWF0Y2goCiAgICAgICAgICAgICAgICAgICAgICAgIC9eLT9cZCstXGR7Mn0tXGR7Mn1UXGR7Mn06XGR7Mn06XGR7Mn0oPzpcLlxkKik/KFstK1x1MjIxMl0oXGR7Mn0pOihcZHsyfSl8Wik/JC8pKSB7CiAgICAgICAgICAgICAgICB2YXIgZGF0ZSA9IG5ldyBEYXRlKHJlc3BvbnNlKTsKICAgICAgICAgICAgICAgIGlmICghaXNOYU4oZGF0ZSkpCiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIGRhdGU7CiAgICAgICAgICAgIH0KICAgICAgICAgICAgcmV0dXJuIHVuZGVmaW5lZDsgLy8gUmV0dXJuIHVuZGVmaW5lZCBpZiBjdXJyZW50IGNvbnZlcnRlciBpcyBub3QgYXBwbGljYWJsZQogICAgICAgIH0KICAgIH07CgogICAgdGhpcy51c2VkQ29udmVydGVycyA9IFtdOwoKICAgIHRoaXMuYWRkQ29udmVydGVyID0gZnVuY3Rpb24oY29udmVydGVyKQogICAgewogICAgICAgIGlmICh0eXBlb2YgY29udmVydGVyID09PSAic3RyaW5nIikgewogICAgICAgICAgICBpZiAoY29udmVydGVyUmVnaXN0cnkuaGFzT3duUHJvcGVydHkoY29udmVydGVyKSkKICAgICAgICAgICAgICAgIHRoaXMudXNlZENvbnZlcnRlcnMucHVzaChjb252ZXJ0ZXJSZWdpc3RyeVtjb252ZXJ0ZXJdKTsKICAgICAgICAgICAgZWxzZQogICAgICAgICAgICAgICAgY29uc29sZS5lcnJvcigiQ29udmVydGVyICciICsgY29udmVydGVyICsgIicgbm90IGZvdW5kIik7CiAgICAgICAgfSBlbHNlIGlmICh0eXBlb2YgY29udmVydGVyID09PSAiZnVuY3Rpb24iKSB7CiAgICAgICAgICAgIHRoaXMudXNlZENvbnZlcnRlcnMucHVzaChjb252ZXJ0ZXIpOwogICAgICAgIH0gZWxzZSB7CiAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoIkludmFsaWQgY29udmVydGVyIG9iamVjdCB0eXBlICIgKyB0eXBlb2YgY29udmVydGVyKTsKICAgICAgICB9CiAgICB9CgogICAgaWYgKEFycmF5LmlzQXJyYXkoY29udmVydGVycykpIHsKICAgICAgICBmb3IgKGNvbnN0IGNvbnZlcnRlciBvZiBjb252ZXJ0ZXJzKQogICAgICAgICAgICB0aGlzLmFkZENvbnZlcnRlcihjb252ZXJ0ZXIpOwogICAgfSBlbHNlIGlmIChjb252ZXJ0ZXJzICE9PSB1bmRlZmluZWQpIHsKICAgICAgICB0aGlzLmFkZENvbnZlcnRlcihjb252ZXJ0ZXJzKTsKICAgIH0KCiAgICB0aGlzLnNlbmQgPSBmdW5jdGlvbihkYXRhKQogICAgewogICAgICAgIGlmICh0eXBlb2YoZGF0YSkgIT09ICJzdHJpbmciKSB7CiAgICAgICAgICAgIGRhdGEgPSBKU09OLnN0cmluZ2lmeShkYXRhKTsKICAgICAgICB9CiAgICAgICAgY2hhbm5lbC50cmFuc3BvcnQuc2VuZChkYXRhKTsKICAgIH0KCiAgICB0aGlzLnRyYW5zcG9ydC5vbm1lc3NhZ2UgPSBmdW5jdGlvbihtZXNzYWdlKQogICAgewogICAgICAgIHZhciBkYXRhID0gbWVzc2FnZS5kYXRhOwogICAgICAgIGlmICh0eXBlb2YgZGF0YSA9PT0gInN0cmluZyIpIHsKICAgICAgICAgICAgZGF0YSA9IEpTT04ucGFyc2UoZGF0YSk7CiAgICAgICAgfQogICAgICAgIHN3aXRjaCAoZGF0YS50eXBlKSB7CiAgICAgICAgICAgIGNhc2UgUVdlYkNoYW5uZWxNZXNzYWdlVHlwZXMuc2lnbmFsOgogICAgICAgICAgICAgICAgY2hhbm5lbC5oYW5kbGVTaWduYWwoZGF0YSk7CiAgICAgICAgICAgICAgICBicmVhazsKICAgICAgICAgICAgY2FzZSBRV2ViQ2hhbm5lbE1lc3NhZ2VUeXBlcy5yZXNwb25zZToKICAgICAgICAgICAgICAgIGNoYW5uZWwuaGFuZGxlUmVzcG9uc2UoZGF0YSk7CiAgICAgICAgICAgICAgICBicmVhazsKICAgICAgICAgICAgY2FzZSBRV2ViQ2hhbm5lbE1lc3NhZ2VUeXBlcy5wcm9wZXJ0eVVwZGF0ZToKICAgICAgICAgICAgICAgIGNoYW5uZWwuaGFuZGxlUHJvcGVydHlVcGRhdGUoZGF0YSk7CiAgICAgICAgICAgICAgICBicmVhazsKICAgICAgICAgICAgZGVmYXVsdDoKICAgICAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoImludmFsaWQgbWVzc2FnZSByZWNlaXZlZDoiLCBtZXNzYWdlLmRhdGEpOwogICAgICAgICAgICAgICAgYnJlYWs7CiAgICAgICAgfQogICAgfQoKICAgIHRoaXMuZXhlY0NhbGxiYWNrcyA9IHt9OwogICAgdGhpcy5leGVjSWQgPSAwOwogICAgdGhpcy5leGVjID0gZnVuY3Rpb24oZGF0YSwgY2FsbGJhY2spCiAgICB7CiAgICAgICAgaWYgKCFjYWxsYmFjaykgewogICAgICAgICAgICAvLyBpZiBubyBjYWxsYmFjayBpcyBnaXZlbiwgc2VuZCBkaXJlY3RseQogICAgICAgICAgICBjaGFubmVsLnNlbmQoZGF0YSk7CiAgICAgICAgICAgIHJldHVybjsKICAgICAgICB9CiAgICAgICAgaWYgKGNoYW5uZWwuZXhlY0lkID09PSBOdW1iZXIuTUFYX1ZBTFVFKSB7CiAgICAgICAgICAgIC8vIHdyYXAKICAgICAgICAgICAgY2hhbm5lbC5leGVjSWQgPSBOdW1iZXIuTUlOX1ZBTFVFOwogICAgICAgIH0KICAgICAgICBpZiAoZGF0YS5oYXNPd25Qcm9wZXJ0eSgiaWQiKSkgewogICAgICAgICAgICBjb25zb2xlLmVycm9yKCJDYW5ub3QgZXhlYyBtZXNzYWdlIHdpdGggcHJvcGVydHkgaWQ6ICIgKyBKU09OLnN0cmluZ2lmeShkYXRhKSk7CiAgICAgICAgICAgIHJldHVybjsKICAgICAgICB9CiAgICAgICAgZGF0YS5pZCA9IGNoYW5uZWwuZXhlY0lkKys7CiAgICAgICAgY2hhbm5lbC5leGVjQ2FsbGJhY2tzW2RhdGEuaWRdID0gY2FsbGJhY2s7CiAgICAgICAgY2hhbm5lbC5zZW5kKGRhdGEpOwogICAgfTsKCiAgICB0aGlzLm9iamVjdHMgPSB7fTsKCiAgICB0aGlzLmhhbmRsZVNpZ25hbCA9IGZ1bmN0aW9uKG1lc3NhZ2UpCiAgICB7CiAgICAgICAgdmFyIG9iamVjdCA9IGNoYW5uZWwub2JqZWN0c1ttZXNzYWdlLm9iamVjdF07CiAgICAgICAgaWYgKG9iamVjdCkgewogICAgICAgICAgICBvYmplY3Quc2lnbmFsRW1pdHRlZChtZXNzYWdlLnNpZ25hbCwgbWVzc2FnZS5hcmdzKTsKICAgICAgICB9IGVsc2UgewogICAgICAgICAgICBjb25zb2xlLndhcm4oIlVuaGFuZGxlZCBzaWduYWw6ICIgKyBtZXNzYWdlLm9iamVjdCArICI6OiIgKyBtZXNzYWdlLnNpZ25hbCk7CiAgICAgICAgfQogICAgfQoKICAgIHRoaXMuaGFuZGxlUmVzcG9uc2UgPSBmdW5jdGlvbihtZXNzYWdlKQogICAgewogICAgICAgIGlmICghbWVzc2FnZS5oYXNPd25Qcm9wZXJ0eSgiaWQiKSkgewogICAgICAgICAgICBjb25zb2xlLmVycm9yKCJJbnZhbGlkIHJlc3BvbnNlIG1lc3NhZ2UgcmVjZWl2ZWQ6ICIsIEpTT04uc3RyaW5naWZ5KG1lc3NhZ2UpKTsKICAgICAgICAgICAgcmV0dXJuOwogICAgICAgIH0KICAgICAgICBjaGFubmVsLmV4ZWNDYWxsYmFja3NbbWVzc2FnZS5pZF0obWVzc2FnZS5kYXRhKTsKICAgICAgICBkZWxldGUgY2hhbm5lbC5leGVjQ2FsbGJhY2tzW21lc3NhZ2UuaWRdOwogICAgfQoKICAgIHRoaXMuaGFuZGxlUHJvcGVydHlVcGRhdGUgPSBmdW5jdGlvbihtZXNzYWdlKQogICAgewogICAgICAgIG1lc3NhZ2UuZGF0YS5mb3JFYWNoKGRhdGEgPT4gewogICAgICAgICAgICB2YXIgb2JqZWN0ID0gY2hhbm5lbC5vYmplY3RzW2RhdGEub2JqZWN0XTsKICAgICAgICAgICAgaWYgKG9iamVjdCkgewogICAgICAgICAgICAgICAgb2JqZWN0LnByb3BlcnR5VXBkYXRlKGRhdGEuc2lnbmFscywgZGF0YS5wcm9wZXJ0aWVzKTsKICAgICAgICAgICAgfSBlbHNlIHsKICAgICAgICAgICAgICAgIGNvbnNvbGUud2FybigiVW5oYW5kbGVkIHByb3BlcnR5IHVwZGF0ZTogIiArIGRhdGEub2JqZWN0ICsgIjo6IiArIGRhdGEuc2lnbmFsKTsKICAgICAgICAgICAgfQogICAgICAgIH0pOwogICAgICAgIGNoYW5uZWwuZXhlYyh7dHlwZTogUVdlYkNoYW5uZWxNZXNzYWdlVHlwZXMuaWRsZX0pOwogICAgfQoKICAgIHRoaXMuZGVidWcgPSBmdW5jdGlvbihtZXNzYWdlKQogICAgewogICAgICAgIGNoYW5uZWwuc2VuZCh7dHlwZTogUVdlYkNoYW5uZWxNZXNzYWdlVHlwZXMuZGVidWcsIGRhdGE6IG1lc3NhZ2V9KTsKICAgIH07CgogICAgY2hhbm5lbC5leGVjKHt0eXBlOiBRV2ViQ2hhbm5lbE1lc3NhZ2VUeXBlcy5pbml0fSwgZnVuY3Rpb24oZGF0YSkgewogICAgICAgIGZvciAoY29uc3Qgb2JqZWN0TmFtZSBvZiBPYmplY3Qua2V5cyhkYXRhKSkgewogICAgICAgICAgICBuZXcgUU9iamVjdChvYmplY3ROYW1lLCBkYXRhW29iamVjdE5hbWVdLCBjaGFubmVsKTsKICAgICAgICB9CgogICAgICAgIC8vIG5vdyB1bndyYXAgcHJvcGVydGllcywgd2hpY2ggbWlnaHQgcmVmZXJlbmNlIG90aGVyIHJlZ2lzdGVyZWQgb2JqZWN0cwogICAgICAgIGZvciAoY29uc3Qgb2JqZWN0TmFtZSBvZiBPYmplY3Qua2V5cyhjaGFubmVsLm9iamVjdHMpKSB7CiAgICAgICAgICAgIGNoYW5uZWwub2JqZWN0c1tvYmplY3ROYW1lXS51bndyYXBQcm9wZXJ0aWVzKCk7CiAgICAgICAgfQoKICAgICAgICBpZiAoaW5pdENhbGxiYWNrKSB7CiAgICAgICAgICAgIGluaXRDYWxsYmFjayhjaGFubmVsKTsKICAgICAgICB9CiAgICAgICAgY2hhbm5lbC5leGVjKHt0eXBlOiBRV2ViQ2hhbm5lbE1lc3NhZ2VUeXBlcy5pZGxlfSk7CiAgICB9KTsKfTsKCmZ1bmN0aW9uIFFPYmplY3QobmFtZSwgZGF0YSwgd2ViQ2hhbm5lbCkKewogICAgdGhpcy5fX2lkX18gPSBuYW1lOwogICAgd2ViQ2hhbm5lbC5vYmplY3RzW25hbWVdID0gdGhpczsKCiAgICAvLyBMaXN0IG9mIGNhbGxiYWNrcyB0aGF0IGdldCBpbnZva2VkIHVwb24gc2lnbmFsIGVtaXNzaW9uCiAgICB0aGlzLl9fb2JqZWN0U2lnbmFsc19fID0ge307CgogICAgLy8gQ2FjaGUgb2YgYWxsIHByb3BlcnRpZXMsIHVwZGF0ZWQgd2hlbiBhIG5vdGlmeSBzaWduYWwgaXMgZW1pdHRlZAogICAgdGhpcy5fX3Byb3BlcnR5Q2FjaGVfXyA9IHt9OwoKICAgIHZhciBvYmplY3QgPSB0aGlzOwoKICAgIC8vIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KCiAgICB0aGlzLnVud3JhcFFPYmplY3QgPSBmdW5jdGlvbihyZXNwb25zZSkKICAgIHsKICAgICAgICBmb3IgKGNvbnN0IGNvbnZlcnRlciBvZiB3ZWJDaGFubmVsLnVzZWRDb252ZXJ0ZXJzKSB7CiAgICAgICAgICAgIHZhciByZXN1bHQgPSBjb252ZXJ0ZXIocmVzcG9uc2UpOwogICAgICAgICAgICBpZiAocmVzdWx0ICE9PSB1bmRlZmluZWQpCiAgICAgICAgICAgICAgICByZXR1cm4gcmVzdWx0OwogICAgICAgIH0KCiAgICAgICAgaWYgKHJlc3BvbnNlIGluc3RhbmNlb2YgQXJyYXkpIHsKICAgICAgICAgICAgLy8gc3VwcG9ydCBsaXN0IG9mIG9iamVjdHMKICAgICAgICAgICAgcmV0dXJuIHJlc3BvbnNlLm1hcChxb2JqID0+IG9iamVjdC51bndyYXBRT2JqZWN0KHFvYmopKQogICAgICAgIH0KICAgICAgICBpZiAoIShyZXNwb25zZSBpbnN0YW5jZW9mIE9iamVjdCkpCiAgICAgICAgICAgIHJldHVybiByZXNwb25zZTsKCiAgICAgICAgaWYgKCFyZXNwb25zZVsiX19RT2JqZWN0Kl9fIl0gfHwgcmVzcG9uc2UuaWQgPT09IHVuZGVmaW5lZCkgewogICAgICAgICAgICB2YXIgak9iaiA9IHt9OwogICAgICAgICAgICBmb3IgKGNvbnN0IHByb3BOYW1lIG9mIE9iamVjdC5rZXlzKHJlc3BvbnNlKSkgewogICAgICAgICAgICAgICAgak9ialtwcm9wTmFtZV0gPSBvYmplY3QudW53cmFwUU9iamVjdChyZXNwb25zZVtwcm9wTmFtZV0pOwogICAgICAgICAgICB9CiAgICAgICAgICAgIHJldHVybiBqT2JqOwogICAgICAgIH0KCiAgICAgICAgdmFyIG9iamVjdElkID0gcmVzcG9uc2UuaWQ7CiAgICAgICAgaWYgKHdlYkNoYW5uZWwub2JqZWN0c1tvYmplY3RJZF0pCiAgICAgICAgICAgIHJldHVybiB3ZWJDaGFubmVsLm9iamVjdHNbb2JqZWN0SWRdOwoKICAgICAgICBpZiAoIXJlc3BvbnNlLmRhdGEpIHsKICAgICAgICAgICAgY29uc29sZS5lcnJvcigiQ2Fubm90IHVud3JhcCB1bmtub3duIFFPYmplY3QgIiArIG9iamVjdElkICsgIiB3aXRob3V0IGRhdGEuIik7CiAgICAgICAgICAgIHJldHVybjsKICAgICAgICB9CgogICAgICAgIHZhciBxT2JqZWN0ID0gbmV3IFFPYmplY3QoIG9iamVjdElkLCByZXNwb25zZS5kYXRhLCB3ZWJDaGFubmVsICk7CiAgICAgICAgcU9iamVjdC5kZXN0cm95ZWQuY29ubmVjdChmdW5jdGlvbigpIHsKICAgICAgICAgICAgaWYgKHdlYkNoYW5uZWwub2JqZWN0c1tvYmplY3RJZF0gPT09IHFPYmplY3QpIHsKICAgICAgICAgICAgICAgIGRlbGV0ZSB3ZWJDaGFubmVsLm9iamVjdHNbb2JqZWN0SWRdOwogICAgICAgICAgICAgICAgLy8gcmVzZXQgdGhlIG5vdyBkZWxldGVkIFFPYmplY3QgdG8gYW4gZW1wdHkge30gb2JqZWN0CiAgICAgICAgICAgICAgICAvLyBqdXN0IGFzc2lnbmluZyB7fSB0aG91Z2ggd291bGQgbm90IGhhdmUgdGhlIGRlc2lyZWQgZWZmZWN0LCBidXQgdGhlCiAgICAgICAgICAgICAgICAvLyBiZWxvdyBhbHNvIGVuc3VyZXMgYWxsIGV4dGVybmFsIHJlZmVyZW5jZXMgd2lsbCBzZWUgdGhlIGVtcHR5IG1hcAogICAgICAgICAgICAgICAgLy8gTk9URTogdGhpcyBkZXRvdXIgaXMgbmVjZXNzYXJ5IHRvIHdvcmthcm91bmQgUVRCVUctNDAwMjEKICAgICAgICAgICAgICAgIE9iamVjdC5rZXlzKHFPYmplY3QpLmZvckVhY2gobmFtZSA9PiBkZWxldGUgcU9iamVjdFtuYW1lXSk7CiAgICAgICAgICAgIH0KICAgICAgICB9KTsKICAgICAgICAvLyBoZXJlIHdlIGFyZSBhbHJlYWR5IGluaXRpYWxpemVkLCBhbmQgdGh1cyBtdXN0IGRpcmVjdGx5IHVud3JhcCB0aGUgcHJvcGVydGllcwogICAgICAgIHFPYmplY3QudW53cmFwUHJvcGVydGllcygpOwogICAgICAgIHJldHVybiBxT2JqZWN0OwogICAgfQoKICAgIHRoaXMudW53cmFwUHJvcGVydGllcyA9IGZ1bmN0aW9uKCkKICAgIHsKICAgICAgICBmb3IgKGNvbnN0IHByb3BlcnR5SWR4IG9mIE9iamVjdC5rZXlzKG9iamVjdC5fX3Byb3BlcnR5Q2FjaGVfXykpIHsKICAgICAgICAgICAgb2JqZWN0Ll9fcHJvcGVydHlDYWNoZV9fW3Byb3BlcnR5SWR4XSA9IG9iamVjdC51bndyYXBRT2JqZWN0KG9iamVjdC5fX3Byb3BlcnR5Q2FjaGVfX1twcm9wZXJ0eUlkeF0pOwogICAgICAgIH0KICAgIH0KCiAgICBmdW5jdGlvbiBhZGRTaWduYWwoc2lnbmFsRGF0YSwgaXNQcm9wZXJ0eU5vdGlmeVNpZ25hbCkKICAgIHsKICAgICAgICB2YXIgc2lnbmFsTmFtZSA9IHNpZ25hbERhdGFbMF07CiAgICAgICAgdmFyIHNpZ25hbEluZGV4ID0gc2lnbmFsRGF0YVsxXTsKICAgICAgICBvYmplY3Rbc2lnbmFsTmFtZV0gPSB7CiAgICAgICAgICAgIGNvbm5lY3Q6IGZ1bmN0aW9uKGNhbGxiYWNrKSB7CiAgICAgICAgICAgICAgICBpZiAodHlwZW9mKGNhbGxiYWNrKSAhPT0gImZ1bmN0aW9uIikgewogICAgICAgICAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoIkJhZCBjYWxsYmFjayBnaXZlbiB0byBjb25uZWN0IHRvIHNpZ25hbCAiICsgc2lnbmFsTmFtZSk7CiAgICAgICAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICAgICAgfQoKICAgICAgICAgICAgICAgIG9iamVjdC5fX29iamVjdFNpZ25hbHNfX1tzaWduYWxJbmRleF0gPSBvYmplY3QuX19vYmplY3RTaWduYWxzX19bc2lnbmFsSW5kZXhdIHx8IFtdOwogICAgICAgICAgICAgICAgb2JqZWN0Ll9fb2JqZWN0U2lnbmFsc19fW3NpZ25hbEluZGV4XS5wdXNoKGNhbGxiYWNrKTsKCiAgICAgICAgICAgICAgICAvLyBvbmx5IHJlcXVpcmVkIGZvciAicHVyZSIgc2lnbmFscywgaGFuZGxlZCBzZXBhcmF0ZWx5IGZvciBwcm9wZXJ0aWVzIGluIHByb3BlcnR5VXBkYXRlCiAgICAgICAgICAgICAgICBpZiAoaXNQcm9wZXJ0eU5vdGlmeVNpZ25hbCkKICAgICAgICAgICAgICAgICAgICByZXR1cm47CgogICAgICAgICAgICAgICAgLy8gYWxzbyBub3RlIHRoYXQgd2UgYWx3YXlzIGdldCBub3RpZmllZCBhYm91dCB0aGUgZGVzdHJveWVkIHNpZ25hbAogICAgICAgICAgICAgICAgaWYgKHNpZ25hbE5hbWUgPT09ICJkZXN0cm95ZWQiIHx8IHNpZ25hbE5hbWUgPT09ICJkZXN0cm95ZWQoKSIgfHwgc2lnbmFsTmFtZSA9PT0gImRlc3Ryb3llZChRT2JqZWN0KikiKQogICAgICAgICAgICAgICAgICAgIHJldHVybjsKCiAgICAgICAgICAgICAgICAvLyBhbmQgb3RoZXJ3aXNlIHdlIG9ubHkgbmVlZCB0byBiZSBjb25uZWN0ZWQgb25seSBvbmNlCiAgICAgICAgICAgICAgICBpZiAob2JqZWN0Ll9fb2JqZWN0U2lnbmFsc19fW3NpZ25hbEluZGV4XS5sZW5ndGggPT0gMSkgewogICAgICAgICAgICAgICAgICAgIHdlYkNoYW5uZWwuZXhlYyh7CiAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6IFFXZWJDaGFubmVsTWVzc2FnZVR5cGVzLmNvbm5lY3RUb1NpZ25hbCwKICAgICAgICAgICAgICAgICAgICAgICAgb2JqZWN0OiBvYmplY3QuX19pZF9fLAogICAgICAgICAgICAgICAgICAgICAgICBzaWduYWw6IHNpZ25hbEluZGV4CiAgICAgICAgICAgICAgICAgICAgfSk7CiAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgIH0sCiAgICAgICAgICAgIGRpc2Nvbm5lY3Q6IGZ1bmN0aW9uKGNhbGxiYWNrKSB7CiAgICAgICAgICAgICAgICBpZiAodHlwZW9mKGNhbGxiYWNrKSAhPT0gImZ1bmN0aW9uIikgewogICAgICAgICAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoIkJhZCBjYWxsYmFjayBnaXZlbiB0byBkaXNjb25uZWN0IGZyb20gc2lnbmFsICIgKyBzaWduYWxOYW1lKTsKICAgICAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgICAgICAvLyBUaGlzIG1ha2VzIGEgbmV3IGxpc3QuIFRoaXMgaXMgaW1wb3J0YW50IGJlY2F1c2UgaXQgd29uJ3QgaW50ZXJmZXJlIHdpdGgKICAgICAgICAgICAgICAgIC8vIHNpZ25hbCBwcm9jZXNzaW5nIGlmIGEgZGlzY29ubmVjdGlvbiBoYXBwZW5zIHdoaWxlIGVtaXR0aWcgYSBzaWduYWwKICAgICAgICAgICAgICAgIG9iamVjdC5fX29iamVjdFNpZ25hbHNfX1tzaWduYWxJbmRleF0gPSAob2JqZWN0Ll9fb2JqZWN0U2lnbmFsc19fW3NpZ25hbEluZGV4XSB8fCBbXSkuZmlsdGVyKGZ1bmN0aW9uKGMpIHsKICAgICAgICAgICAgICAgICAgcmV0dXJuIGMgIT0gY2FsbGJhY2s7CiAgICAgICAgICAgICAgICB9KTsKICAgICAgICAgICAgICAgIGlmICghaXNQcm9wZXJ0eU5vdGlmeVNpZ25hbCAmJiBvYmplY3QuX19vYmplY3RTaWduYWxzX19bc2lnbmFsSW5kZXhdLmxlbmd0aCA9PT0gMCkgewogICAgICAgICAgICAgICAgICAgIC8vIG9ubHkgcmVxdWlyZWQgZm9yICJwdXJlIiBzaWduYWxzLCBoYW5kbGVkIHNlcGFyYXRlbHkgZm9yIHByb3BlcnRpZXMgaW4gcHJvcGVydHlVcGRhdGUKICAgICAgICAgICAgICAgICAgICB3ZWJDaGFubmVsLmV4ZWMoewogICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBRV2ViQ2hhbm5lbE1lc3NhZ2VUeXBlcy5kaXNjb25uZWN0RnJvbVNpZ25hbCwKICAgICAgICAgICAgICAgICAgICAgICAgb2JqZWN0OiBvYmplY3QuX19pZF9fLAogICAgICAgICAgICAgICAgICAgICAgICBzaWduYWw6IHNpZ25hbEluZGV4CiAgICAgICAgICAgICAgICAgICAgfSk7CiAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgIH0KICAgICAgICB9OwogICAgfQoKICAgIC8qKgogICAgICogSW52b2tlcyBhbGwgY2FsbGJhY2tzIGZvciB0aGUgZ2l2ZW4gc2lnbmFsbmFtZS4gQWxzbyB3b3JrcyBmb3IgcHJvcGVydHkgbm90aWZ5IGNhbGxiYWNrcy4KICAgICAqLwogICAgZnVuY3Rpb24gaW52b2tlU2lnbmFsQ2FsbGJhY2tzKHNpZ25hbE5hbWUsIHNpZ25hbEFyZ3MpCiAgICB7CiAgICAgICAgdmFyIGNvbm5lY3Rpb25zID0gb2JqZWN0Ll9fb2JqZWN0U2lnbmFsc19fW3NpZ25hbE5hbWVdOwogICAgICAgIGlmIChjb25uZWN0aW9ucykgewogICAgICAgICAgICBjb25uZWN0aW9ucy5mb3JFYWNoKGZ1bmN0aW9uKGNhbGxiYWNrKSB7CiAgICAgICAgICAgICAgICBjYWxsYmFjay5hcHBseShjYWxsYmFjaywgc2lnbmFsQXJncyk7CiAgICAgICAgICAgIH0pOwogICAgICAgIH0KICAgIH0KCiAgICB0aGlzLnByb3BlcnR5VXBkYXRlID0gZnVuY3Rpb24oc2lnbmFscywgcHJvcGVydHlNYXApCiAgICB7CiAgICAgICAgLy8gdXBkYXRlIHByb3BlcnR5IGNhY2hlCiAgICAgICAgZm9yIChjb25zdCBwcm9wZXJ0eUluZGV4IG9mIE9iamVjdC5rZXlzKHByb3BlcnR5TWFwKSkgewogICAgICAgICAgICB2YXIgcHJvcGVydHlWYWx1ZSA9IHByb3BlcnR5TWFwW3Byb3BlcnR5SW5kZXhdOwogICAgICAgICAgICBvYmplY3QuX19wcm9wZXJ0eUNhY2hlX19bcHJvcGVydHlJbmRleF0gPSB0aGlzLnVud3JhcFFPYmplY3QocHJvcGVydHlWYWx1ZSk7CiAgICAgICAgfQoKICAgICAgICBmb3IgKGNvbnN0IHNpZ25hbE5hbWUgb2YgT2JqZWN0LmtleXMoc2lnbmFscykpIHsKICAgICAgICAgICAgLy8gSW52b2tlIGFsbCBjYWxsYmFja3MsIGFzIHNpZ25hbEVtaXR0ZWQoKSBkb2VzIG5vdC4gVGhpcyBlbnN1cmVzIHRoZQogICAgICAgICAgICAvLyBwcm9wZXJ0eSBjYWNoZSBpcyB1cGRhdGVkIGJlZm9yZSB0aGUgY2FsbGJhY2tzIGFyZSBpbnZva2VkLgogICAgICAgICAgICBpbnZva2VTaWduYWxDYWxsYmFja3Moc2lnbmFsTmFtZSwgc2lnbmFsc1tzaWduYWxOYW1lXSk7CiAgICAgICAgfQogICAgfQoKICAgIHRoaXMuc2lnbmFsRW1pdHRlZCA9IGZ1bmN0aW9uKHNpZ25hbE5hbWUsIHNpZ25hbEFyZ3MpCiAgICB7CiAgICAgICAgaW52b2tlU2lnbmFsQ2FsbGJhY2tzKHNpZ25hbE5hbWUsIHRoaXMudW53cmFwUU9iamVjdChzaWduYWxBcmdzKSk7CiAgICB9CgogICAgZnVuY3Rpb24gYWRkTWV0aG9kKG1ldGhvZERhdGEpCiAgICB7CiAgICAgICAgdmFyIG1ldGhvZE5hbWUgPSBtZXRob2REYXRhWzBdOwogICAgICAgIHZhciBtZXRob2RJZHggPSBtZXRob2REYXRhWzFdOwoKICAgICAgICAvLyBGdWxseSBzcGVjaWZpZWQgbWV0aG9kcyBhcmUgaW52b2tlZCBieSBpZCwgb3RoZXJzIGJ5IG5hbWUgZm9yIGhvc3Qtc2lkZSBvdmVybG9hZCByZXNvbHV0aW9uCiAgICAgICAgdmFyIGludm9rZWRNZXRob2QgPSBtZXRob2ROYW1lW21ldGhvZE5hbWUubGVuZ3RoIC0gMV0gPT09ICcpJyA/IG1ldGhvZElkeCA6IG1ldGhvZE5hbWUKCiAgICAgICAgb2JqZWN0W21ldGhvZE5hbWVdID0gZnVuY3Rpb24oKSB7CiAgICAgICAgICAgIHZhciBhcmdzID0gW107CiAgICAgICAgICAgIHZhciBjYWxsYmFjazsKICAgICAgICAgICAgdmFyIGVyckNhbGxiYWNrOwogICAgICAgICAgICBmb3IgKHZhciBpID0gMDsgaSA8IGFyZ3VtZW50cy5sZW5ndGg7ICsraSkgewogICAgICAgICAgICAgICAgdmFyIGFyZ3VtZW50ID0gYXJndW1lbnRzW2ldOwogICAgICAgICAgICAgICAgaWYgKHR5cGVvZiBhcmd1bWVudCA9PT0gImZ1bmN0aW9uIikKICAgICAgICAgICAgICAgICAgICBjYWxsYmFjayA9IGFyZ3VtZW50OwogICAgICAgICAgICAgICAgZWxzZQogICAgICAgICAgICAgICAgICAgIGFyZ3MucHVzaChhcmd1bWVudCk7CiAgICAgICAgICAgIH0KCiAgICAgICAgICAgIHZhciByZXN1bHQ7CiAgICAgICAgICAgIC8vIGR1cmluZyB0ZXN0LCB3ZWJDaGFubmVsLmV4ZWMgc3luY2hyb25vdXNseSBjYWxscyB0aGUgY2FsbGJhY2sKICAgICAgICAgICAgLy8gdGhlcmVmb3JlLCB0aGUgcHJvbWlzZSBtdXN0IGJlIGNvbnN0dWN0ZWQgYmVmb3JlIGNhbGxpbmcKICAgICAgICAgICAgLy8gd2ViQ2hhbm5lbC5leGVjIHRvIGVuc3VyZSB0aGUgY2FsbGJhY2sgaXMgc2V0IHVwCiAgICAgICAgICAgIGlmICghY2FsbGJhY2sgJiYgKHR5cGVvZihQcm9taXNlKSA9PT0gJ2Z1bmN0aW9uJykpIHsKICAgICAgICAgICAgICByZXN1bHQgPSBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXNvbHZlLCByZWplY3QpIHsKICAgICAgICAgICAgICAgIGNhbGxiYWNrID0gcmVzb2x2ZTsKICAgICAgICAgICAgICAgIGVyckNhbGxiYWNrID0gcmVqZWN0OwogICAgICAgICAgICAgIH0pOwogICAgICAgICAgICB9CgogICAgICAgICAgICB3ZWJDaGFubmVsLmV4ZWMoewogICAgICAgICAgICAgICAgInR5cGUiOiBRV2ViQ2hhbm5lbE1lc3NhZ2VUeXBlcy5pbnZva2VNZXRob2QsCiAgICAgICAgICAgICAgICAib2JqZWN0Ijogb2JqZWN0Ll9faWRfXywKICAgICAgICAgICAgICAgICJtZXRob2QiOiBpbnZva2VkTWV0aG9kLAogICAgICAgICAgICAgICAgImFyZ3MiOiBhcmdzCiAgICAgICAgICAgIH0sIGZ1bmN0aW9uKHJlc3BvbnNlKSB7CiAgICAgICAgICAgICAgICBpZiAocmVzcG9uc2UgIT09IHVuZGVmaW5lZCkgewogICAgICAgICAgICAgICAgICAgIHZhciByZXN1bHQgPSBvYmplY3QudW53cmFwUU9iamVjdChyZXNwb25zZSk7CiAgICAgICAgICAgICAgICAgICAgaWYgKGNhbGxiYWNrKSB7CiAgICAgICAgICAgICAgICAgICAgICAgIChjYWxsYmFjaykocmVzdWx0KTsKICAgICAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKGVyckNhbGxiYWNrKSB7CiAgICAgICAgICAgICAgICAgIChlcnJDYWxsYmFjaykoKTsKICAgICAgICAgICAgICAgIH0KICAgICAgICAgICAgfSk7CgogICAgICAgICAgICByZXR1cm4gcmVzdWx0OwogICAgICAgIH07CiAgICB9CgogICAgZnVuY3Rpb24gYmluZEdldHRlclNldHRlcihwcm9wZXJ0eUluZm8pCiAgICB7CiAgICAgICAgdmFyIHByb3BlcnR5SW5kZXggPSBwcm9wZXJ0eUluZm9bMF07CiAgICAgICAgdmFyIHByb3BlcnR5TmFtZSA9IHByb3BlcnR5SW5mb1sxXTsKICAgICAgICB2YXIgbm90aWZ5U2lnbmFsRGF0YSA9IHByb3BlcnR5SW5mb1syXTsKICAgICAgICAvLyBpbml0aWFsaXplIHByb3BlcnR5IGNhY2hlIHdpdGggY3VycmVudCB2YWx1ZQogICAgICAgIC8vIE5PVEU6IGlmIHRoaXMgaXMgYW4gb2JqZWN0LCBpdCBpcyBub3QgZGlyZWN0bHkgdW53cmFwcGVkIGFzIGl0IG1pZ2h0CiAgICAgICAgLy8gcmVmZXJlbmNlIG90aGVyIFFPYmplY3QgdGhhdCB3ZSBkbyBub3Qga25vdyB5ZXQKICAgICAgICBvYmplY3QuX19wcm9wZXJ0eUNhY2hlX19bcHJvcGVydHlJbmRleF0gPSBwcm9wZXJ0eUluZm9bM107CgogICAgICAgIGlmIChub3RpZnlTaWduYWxEYXRhKSB7CiAgICAgICAgICAgIGlmIChub3RpZnlTaWduYWxEYXRhWzBdID09PSAxKSB7CiAgICAgICAgICAgICAgICAvLyBzaWduYWwgbmFtZSBpcyBvcHRpbWl6ZWQgYXdheSwgcmVjb25zdHJ1Y3QgdGhlIGFjdHVhbCBuYW1lCiAgICAgICAgICAgICAgICBub3RpZnlTaWduYWxEYXRhWzBdID0gcHJvcGVydHlOYW1lICsgIkNoYW5nZWQiOwogICAgICAgICAgICB9CiAgICAgICAgICAgIGFkZFNpZ25hbChub3RpZnlTaWduYWxEYXRhLCB0cnVlKTsKICAgICAgICB9CgogICAgICAgIE9iamVjdC5kZWZpbmVQcm9wZXJ0eShvYmplY3QsIHByb3BlcnR5TmFtZSwgewogICAgICAgICAgICBjb25maWd1cmFibGU6IHRydWUsCiAgICAgICAgICAgIGdldDogZnVuY3Rpb24gKCkgewogICAgICAgICAgICAgICAgdmFyIHByb3BlcnR5VmFsdWUgPSBvYmplY3QuX19wcm9wZXJ0eUNhY2hlX19bcHJvcGVydHlJbmRleF07CiAgICAgICAgICAgICAgICBpZiAocHJvcGVydHlWYWx1ZSA9PT0gdW5kZWZpbmVkKSB7CiAgICAgICAgICAgICAgICAgICAgLy8gVGhpcyBzaG91bGRuJ3QgaGFwcGVuCiAgICAgICAgICAgICAgICAgICAgY29uc29sZS53YXJuKCJVbmRlZmluZWQgdmFsdWUgaW4gcHJvcGVydHkgY2FjaGUgZm9yIHByb3BlcnR5IFwiIiArIHByb3BlcnR5TmFtZSArICJcIiBpbiBvYmplY3QgIiArIG9iamVjdC5fX2lkX18pOwogICAgICAgICAgICAgICAgfQoKICAgICAgICAgICAgICAgIHJldHVybiBwcm9wZXJ0eVZhbHVlOwogICAgICAgICAgICB9LAogICAgICAgICAgICBzZXQ6IGZ1bmN0aW9uKHZhbHVlKSB7CiAgICAgICAgICAgICAgICBpZiAodmFsdWUgPT09IHVuZGVmaW5lZCkgewogICAgICAgICAgICAgICAgICAgIGNvbnNvbGUud2FybigiUHJvcGVydHkgc2V0dGVyIGZvciAiICsgcHJvcGVydHlOYW1lICsgIiBjYWxsZWQgd2l0aCB1bmRlZmluZWQgdmFsdWUhIik7CiAgICAgICAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICAgICAgfQogICAgICAgICAgICAgICAgb2JqZWN0Ll9fcHJvcGVydHlDYWNoZV9fW3Byb3BlcnR5SW5kZXhdID0gdmFsdWU7CiAgICAgICAgICAgICAgICB2YXIgdmFsdWVUb1NlbmQgPSB2YWx1ZTsKICAgICAgICAgICAgICAgIHdlYkNoYW5uZWwuZXhlYyh7CiAgICAgICAgICAgICAgICAgICAgInR5cGUiOiBRV2ViQ2hhbm5lbE1lc3NhZ2VUeXBlcy5zZXRQcm9wZXJ0eSwKICAgICAgICAgICAgICAgICAgICAib2JqZWN0Ijogb2JqZWN0Ll9faWRfXywKICAgICAgICAgICAgICAgICAgICAicHJvcGVydHkiOiBwcm9wZXJ0eUluZGV4LAogICAgICAgICAgICAgICAgICAgICJ2YWx1ZSI6IHZhbHVlVG9TZW5kCiAgICAgICAgICAgICAgICB9KTsKICAgICAgICAgICAgfQogICAgICAgIH0pOwoKICAgIH0KCiAgICAvLyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCgogICAgZGF0YS5tZXRob2RzLmZvckVhY2goYWRkTWV0aG9kKTsKCiAgICBkYXRhLnByb3BlcnRpZXMuZm9yRWFjaChiaW5kR2V0dGVyU2V0dGVyKTsKCiAgICBkYXRhLnNpZ25hbHMuZm9yRWFjaChmdW5jdGlvbihzaWduYWwpIHsgYWRkU2lnbmFsKHNpZ25hbCwgZmFsc2UpOyB9KTsKCiAgICBPYmplY3QuYXNzaWduKG9iamVjdCwgZGF0YS5lbnVtcyk7Cn0KClFPYmplY3QucHJvdG90eXBlLnRvSlNPTiA9IGZ1bmN0aW9uKCkgewogICAgaWYgKHRoaXMuX19pZF9fID09PSB1bmRlZmluZWQpIHJldHVybiB7fTsKICAgIHJldHVybiB7CiAgICAgICAgaWQ6IHRoaXMuX19pZF9fLAogICAgICAgICJfX1FPYmplY3QqX18iOiB0cnVlCiAgICB9Owp9OwoKLy9yZXF1aXJlZCBmb3IgdXNlIHdpdGggbm9kZWpzCmlmICh0eXBlb2YgbW9kdWxlID09PSAnb2JqZWN0JykgewogICAgbW9kdWxlLmV4cG9ydHMgPSB7CiAgICAgICAgUVdlYkNoYW5uZWw6IFFXZWJDaGFubmVsCiAgICB9Owp9Cg=="
)

# ── Register opal:// as a trusted local scheme ───────────────
# Must happen before any QApplication/QCoreApplication is created.
# SecureScheme + LocalScheme allows the page to be treated as a secure origin.
# NOTE: Frontend JS no longer contacts localhost — Leo summaries are generated
#       by the Python backend (OpalSearchWorker) and injected as static HTML.
_opal_scheme = QWebEngineUrlScheme(b"opal")
_opal_scheme.setFlags(
    QWebEngineUrlScheme.Flag.SecureScheme |
    QWebEngineUrlScheme.Flag.LocalScheme |
    QWebEngineUrlScheme.Flag.LocalAccessAllowed |
    QWebEngineUrlScheme.Flag.CorsEnabled
)
QWebEngineUrlScheme.registerScheme(_opal_scheme)

_northstar_scheme = QWebEngineUrlScheme(b"northstar")
_northstar_scheme.setFlags(
    QWebEngineUrlScheme.Flag.SecureScheme |
    QWebEngineUrlScheme.Flag.LocalScheme |
    QWebEngineUrlScheme.Flag.LocalAccessAllowed |
    QWebEngineUrlScheme.Flag.CorsEnabled
)
QWebEngineUrlScheme.registerScheme(_northstar_scheme)



# ── Debug toggle ──────────────────────────────────────────────────────────────
_DEBUG: bool = os.environ.get("NS_DEBUG", "").lower() in ("1", "true", "yes")

# ── Media feature flag ───────────────────────────────────────────────────────
ENABLE_MEDIA_FETCH: bool = False # Temporarily disable media fetching entirely

def _log(tag: str, msg: str) -> None:
    if _DEBUG:
        print(f"[OPAL:{tag}] {msg}", flush=True)


# ─────────────────────────────────────────────
#  FLUID UI COMPONENTS
# ─────────────────────────────────────────────
class FluidButton(QPushButton):
    """QPushButton with smooth hover transitions using a layered approach."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._overlay = QWidget(self)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._overlay.setObjectName("FluidOverlay")
        self._eff = QGraphicsOpacityEffect(self._overlay)
        self._overlay.setGraphicsEffect(self._eff)
        self._eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._eff, b"opacity")
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._overlay.setGeometry(self.rect())

    def enterEvent(self, e):
        if not get_fernway().get("hover_animations_enabled", True):
            self._anim.stop()
            self._eff.setOpacity(0.0)
            super().enterEvent(e)
            return
        m = _get_motion_params()
        self._anim.stop()
        self._anim.setDuration(m["in_ms"])
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not get_fernway().get("hover_animations_enabled", True):
            self._anim.stop()
            self._eff.setOpacity(0.0)
            super().leaveEvent(e)
            return
        m = _get_motion_params()
        self._anim.stop()
        self._anim.setDuration(m["out_ms"])
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(e)


# ─────────────────────────────────────────────
def _get_motion_params():
    """Retrieve motion parameters from Fernway customization manager."""
    fw = get_fernway()
    intensity = max(0.0, min(1.5, float(fw.get("animation_intensity", 1.0))))
    speed_ms = max(0.0, float(fw.get("transition_speed_ms", 240)))
    duration_scale = intensity * 1.2

    return {
        "in_ms": round(speed_ms * duration_scale),
        "out_ms": round(speed_ms * duration_scale * 0.875),
        "fade_ms": round(speed_ms * duration_scale * 0.8),
        "dim_ms": round(speed_ms * duration_scale * 0.7),
        "slide_px": round(22 * intensity),
    }

def _ns_opacity(widget) -> QGraphicsOpacityEffect:
    """Return (or lazily create) a QGraphicsOpacityEffect on *widget*."""
    eff = widget.graphicsEffect()
    if not isinstance(eff, QGraphicsOpacityEffect):
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
    return eff


def _ns_panel_show(widget, raise_fn=None):
    """Slide a floating panel in from the right with a simultaneous fade-in.

    Call *after* setGeometry() / _pin_panel(), *before* show().
    raise_fn (callable) is invoked once the widget is visible.
    Automatically cancels any running exit animation.
    """
    # Guard: already animating in
    if getattr(widget, "_ns_entering", False):
        return
        
    # If a hide-animation is in flight, cancel it and fire its dim callback
    # immediately so the panel-open counter stays balanced.
    exit_anim = getattr(widget, "_ns_exit_anim", None)
    if exit_anim is not None:
        exit_anim.stop()
        on_hidden = getattr(widget, "_ns_exit_on_hidden", None)
        if on_hidden:
            on_hidden()
            widget._ns_exit_on_hidden = None
        widget._ns_exit_anim = None
        widget._ns_exiting   = False

    eff = _ns_opacity(widget)
    eff.setOpacity(0.0)

    m = _get_motion_params()

    # Keep the travel distance short so the panel does not feel like it enters from off-screen.
    target = widget.pos()
    start  = QPoint(target.x() + m["slide_px"], target.y())
    widget.move(start)
    widget.show()
    if raise_fn:
        raise_fn()

    slide = QPropertyAnimation(widget, b"pos", widget)
    slide.setDuration(m["in_ms"])
    slide.setStartValue(start)
    slide.setEndValue(target)
    slide.setEasingCurve(QEasingCurve.Type.InOutCubic)

    # Fade in alongside the panel movement.
    fade = QPropertyAnimation(eff, b"opacity", widget)
    fade.setDuration(m["fade_ms"])
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.InOutCubic)

    grp = QParallelAnimationGroup(widget)
    grp.addAnimation(slide)
    grp.addAnimation(fade)
    widget._ns_entering = True
    def _on_finished():
        widget._ns_entering = False
        _ns_opacity(widget).setOpacity(1.0)
        widget.update()
    grp.finished.connect(_on_finished)
    grp.start()
    widget._ns_enter_anim = grp


def _ns_panel_hide(widget, on_hidden=None):
    """Slide a floating panel slightly right with a fade-out, then hide().

    on_hidden() is called once the widget is fully hidden.
    Guards against double-triggering automatically.
    """
    if not widget.isVisible():
        if on_hidden:
            on_hidden()
        return
    # Guard: exit animation already in flight for this widget
    if getattr(widget, "_ns_exiting", False):
        return

    # Cancel any running enter animation
    ea = getattr(widget, "_ns_enter_anim", None)
    if ea is not None:
        ea.stop()
        widget._ns_enter_anim = None
        widget._ns_entering = False

    eff = _ns_opacity(widget)

    m = _get_motion_params()
    start = widget.pos()
    end   = QPoint(start.x() + m["slide_px"], start.y())

    slide = QPropertyAnimation(widget, b"pos", widget)
    slide.setDuration(m["out_ms"])
    slide.setStartValue(start)
    slide.setEndValue(end)
    slide.setEasingCurve(QEasingCurve.Type.InOutCubic)

    fade = QPropertyAnimation(eff, b"opacity", widget)
    fade.setDuration(m["out_ms"])
    fade.setStartValue(eff.opacity())
    fade.setEndValue(0.0)
    fade.setEasingCurve(QEasingCurve.Type.InOutCubic)

    grp = QParallelAnimationGroup(widget)
    grp.addAnimation(slide)
    grp.addAnimation(fade)

    widget._ns_exiting        = True
    widget._ns_exit_anim      = grp
    widget._ns_exit_on_hidden = on_hidden  # stored so show() can fire it early

    def _on_done():
        widget.hide()
        widget._ns_exiting        = False
        widget._ns_exit_anim      = None
        widget._ns_exit_on_hidden = None
        if on_hidden:
            on_hidden()

    grp.finished.connect(_on_done)
    grp.start()


def _ns_fade_widget(widget, duration=None, delay=0):
    eff = _ns_opacity(widget)

    # ✅ CRITICAL GUARD (prevents invisible text bug)
    if widget.isVisible() and eff.opacity() == 1.0:
        return

    eff.setOpacity(0.0)
    
    if duration is None:
        duration = _get_motion_params()["fade_ms"]

    # Stop any in-flight fade so two animations don't fight over opacity.
    prev = getattr(widget, "_ns_fade_anim", None)
    if prev is not None:
        prev.stop()

    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    if delay:
        QTimer.singleShot(delay, anim.start)
    else:
        anim.start()

    widget._ns_fade_anim = anim


# ─────────────────────────────────────────────
#  PATH HELPERS
# ─────────────────────────────────────────────
def _app_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "NorthStar")
    os.makedirs(d, exist_ok=True)
    return d

base_dir = _data_dir()

cache_dir = os.path.join(base_dir, "cache")
storage_dir = os.path.join(base_dir, "storage")

os.makedirs(cache_dir, exist_ok=True)
os.makedirs(storage_dir, exist_ok=True)

def _asset(name: str) -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(_app_dir(), name)

def _northstar_user_agent() -> str:
    """Standard Chrome UA with the *actual* QtWebEngine/Chrome versions.

    Kept dynamic so sites see the true engine version after an upgrade —
    a hardcoded "QtWebEngine/6.8.2 Chrome/122" claim would be stale and can
    get NorthStar blocked (CDNs/Wikimedia)."""
    qtwe = chrome = ""
    try:
        from PyQt6.QtWebEngineCore import qWebEngineVersion, qWebEngineChromiumVersion
        qtwe = qWebEngineVersion() or qtwe
        chrome = qWebEngineChromiumVersion() or chrome
    except Exception:
        pass
    if not qtwe:
        try:
            from PyQt6.QtCore import QT_VERSION_STR
            qtwe = QT_VERSION_STR
        except Exception:
            qtwe = "6.10.0"
    if not chrome:
        chrome = "132.0.0.0"
    return (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) QtWebEngine/{qtwe} Chrome/{chrome} Safari/537.36")

# ── Global wallpaper list (shared between new tab pages) ─────
_global_wallpaper_files = []
_global_wallpaper_indices = []
_global_bookmarks = []
_global_dark_mode = True  # light mode removed
_global_search_engine_url = "https://www.google.com/search?q={}"
_global_favicon_data_cache = {}
def _wallpapers_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "assets", "wallpapers")
    return os.path.join(_app_dir(), "assets", "wallpapers")

def _refresh_wallpaper_list():
    global _global_wallpaper_files, _global_wallpaper_indices
    import random
    wallpapers_dir = _wallpapers_dir()
    _global_wallpaper_files = []
    if os.path.exists(wallpapers_dir):
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
            _global_wallpaper_files.extend(glob.glob(os.path.join(wallpapers_dir, ext)))
    _global_wallpaper_indices = list(range(len(_global_wallpaper_files)))
    random.shuffle(_global_wallpaper_indices)

_refresh_wallpaper_list()

# ── NorthStar URL Scheme Handler ──
class NorthStarUrlSchemeHandler(QWebEngineUrlSchemeHandler):
    """Single handler for all northstar:// URLs — dispatches by path prefix."""
    def requestStarted(self, job: QWebEngineUrlRequestJob):
        url = job.requestUrl().toString()
        try:
            # ── Wallpaper: northstar://wallpaper/<index> ──
            if url.startswith("northstar://wallpaper/"):
                index_str = url[len("northstar://wallpaper/"):]
                index = int(index_str)
                if index < 0 or index >= len(_global_wallpaper_files):
                    job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                    return
                wallpaper_path = _global_wallpaper_files[index]
                with open(wallpaper_path, "rb") as f:
                    data = f.read()
                ext = os.path.splitext(wallpaper_path)[1].lower()
                mime = b"image/jpeg"
                if ext == ".png":
                    mime = b"image/png"
                elif ext == ".webp":
                    mime = b"image/webp"
                from PyQt6.QtCore import QBuffer, QByteArray
                buffer = QBuffer()
                buffer.setData(QByteArray(data))
                buffer.open(QBuffer.OpenModeFlag.ReadOnly)
                buffer.setParent(job)
                job.reply(mime, buffer)
                return

            # ── Host-side clipboard write: northstar://clipboard?text=... ──
            # The page-side shim routes navigator.clipboard.writeText here so the
            # copy lands in the REAL Qt clipboard (unrestricted — no Chromium
            # clipboard permission / user-gesture gating). Avoids the silent
            # failure of the async clipboard API under QtWebEngine.
            if url.startswith("northstar://clipboard"):
                try:
                    from urllib.parse import urlparse as _up, parse_qs as _pqs
                    _params = _pqs(_up(url).query)
                    _text = _params.get("text", [""])[0]
                    from PyQt6.QtWidgets import QApplication
                    QApplication.clipboard().setText(_text)
                except Exception:
                    pass
                # Reply with a 1x1 transparent GIF so the <img>/fetch completes.
                from PyQt6.QtCore import QBuffer, QByteArray
                _gif = QByteArray(
                    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
                    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
                    b"\x01\x00\x00\x02\x02D\x01\x00;")
                _buf = QBuffer()
                _buf.setData(_gif)
                _buf.open(QBuffer.OpenModeFlag.ReadOnly)
                _buf.setParent(job)
                job.reply(b"image/gif", _buf)
                return

            if url.startswith("northstar://wallpaper/video/"):
                filename = url.replace("northstar://wallpaper/video/", "")
                path = os.path.join(_asset("wallpaper_videos"), filename)
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        data = f.read()
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"video/mp4", buf)
                    return
            # ── New Tab: northstar://newtab ──
            if url == "northstar://newtab" or url.rstrip("/") == "northstar://newtab":
                html = _build_newtab_html(
                    _global_bookmarks,
                    dark_mode=_global_dark_mode,
                    search_engine_url=_global_search_engine_url
                )
                data = html.encode("utf-8")
                from PyQt6.QtCore import QBuffer, QByteArray
                buf = QBuffer()
                buf.setData(QByteArray(data))
                buf.open(QBuffer.OpenModeFlag.ReadOnly)
                buf.setParent(job)
                job.reply(b"text/html; charset=utf-8", buf)
                return

            # ── Settings: northstar://settings ──
            if url.startswith("northstar://settings"):
                from PyQt6.QtCore import QBuffer, QByteArray
                from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs
                parsed = _urlparse(url)
                params = _parse_qs(parsed.query)
                
                if url.startswith("northstar://settings/save"):
                    key = params.get("key", [""])[0]
                    value = params.get("value", [""])[0]
                    section = params.get("section", [""])[0]
                    if section == "s":
                        s = _load_settings()
                        # Light mode is removed — dark always wins, regardless
                        # of any (re)written value.
                        s["dark_mode"] = True
                        if value == "true": value = True
                        elif value == "false": value = False
                        else:
                            try: value = float(value); value = int(value) if value == int(value) else value
                            except: pass
                        s[key] = value
                        _save_settings(s)
                        # Notify the running app about settings changes
                        try:
                            from PyQt6.QtWidgets import QApplication
                            app = QApplication.instance()
                            if app:
                                for w in app.topLevelWidgets():
                                    if hasattr(w, '_on_settings_changed'):
                                        w._on_settings_changed(s)
                                        break
                        except: pass
                    elif section == "fw":
                        fw = get_fernway()
                        if value == "true": value = True
                        elif value == "false": value = False
                        else:
                            try: value = float(value)
                            except: pass
                        fw.set(key, value)
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return
                
                if url.startswith("northstar://settings/preset"):
                    mode = params.get("mode", ["balanced"])[0]
                    fw = get_fernway()
                    if mode == "default":
                        fw.reset_to_defaults()
                    else:
                        fw.set_performance_mode(mode)
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return
                
                if url.startswith("northstar://settings/clear-permissions"):
                    _perm_manager.clear_all()
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return

                if url.startswith("northstar://settings/clear-data"):
                    data_type = params.get("type", [""])[0]
                    if data_type in ("cache", "cookies", "history"):
                        from PyQt6.QtWidgets import QApplication
                        app = QApplication.instance()
                        if app:
                            window = next(
                                (w for w in app.topLevelWidgets()
                                 if hasattr(w, "_clear_browser_data")),
                                None,
                            )
                            if window:
                                QTimer.singleShot(
                                    0, lambda w=window, t=data_type: w._clear_browser_data(t)
                                )
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return
                
                html = _build_settings_html(dark_mode=_global_dark_mode)
                data = html.encode("utf-8")
                buf = QBuffer(); buf.setData(QByteArray(data))
                buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                job.reply(b"text/html; charset=utf-8", buf)
                return

            # ── Extensions: northstar://extensions ──
            if url.startswith("northstar://extensions"):
                from PyQt6.QtCore import QBuffer, QByteArray
                from PyQt6.QtWidgets import QApplication
                from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs
                parsed = _urlparse(url)
                params = _parse_qs(parsed.query)

                # Locate the ExtensionManager and its owning window.
                _ext_mgr = None
                _ext_window = None
                _app = QApplication.instance()
                if _app is not None:
                    for w in _app.topLevelWidgets():
                        if hasattr(w, "extensions"):
                            _ext_mgr = w.extensions
                            _ext_window = w
                            break

                if url.startswith("northstar://extensions/enable"):
                    ext_id = params.get("id", [""])[0]
                    on = params.get("on", ["true"])[0] in ("true", "1")
                    # Emit to the GUI thread — native (Qt 6.10+) backend calls
                    # QWebEngineExtensionManager which must be used on the
                    # owning thread.
                    if _ext_window is not None:
                        _ext_window.extensions_action_requested.emit("enable", ext_id, on)
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return

                if url.startswith("northstar://extensions/remove"):
                    ext_id = params.get("id", [""])[0]
                    if _ext_window is not None:
                        _ext_window.extensions_action_requested.emit("remove", ext_id, None)
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return

                if url.startswith("northstar://extensions/install"):
                    # Directory picker must run on the GUI thread. Emit the
                    # window's signal (queued cross-thread delivery) so the
                    # dialog opens on the UI thread.
                    if _ext_window is not None:
                        _ext_window.install_extension_requested.emit()
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return

                if url.startswith("northstar://extensions/browse"):
                    # External browser launch off the IO thread → signal.
                    if _ext_window is not None:
                        _ext_window.browse_addons_requested.emit()
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return

                # ── Extensions management UI ──
                ext_list = _ext_mgr.list_extensions() if _ext_mgr else []
                _ext_backend = getattr(_ext_mgr.backend, "name", "content-script") if _ext_mgr else "content-script"
                html = _build_extensions_html(ext_list, dark_mode=_global_dark_mode, backend=_ext_backend)
                data = html.encode("utf-8")
                buf = QBuffer(); buf.setData(QByteArray(data))
                buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                job.reply(b"text/html; charset=utf-8", buf)
                return

            # ── Notes: northstar://notes ──

            if url.startswith("northstar://notes"):
                from PyQt6.QtCore import QBuffer, QByteArray
                from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs
                parsed = _urlparse(url)
                params = _parse_qs(parsed.query)
                
                if url.startswith("northstar://notes/add"):
                    title = params.get("title", [""])[0]
                    body = params.get("body", [""])[0]
                    import datetime as _dt
                    notes = _load_notes()
                    notes.append({"title": title, "body": body, "date": _dt.datetime.now().strftime("%Y-%m-%d %H:%M")})
                    _save_notes(notes)
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return
                
                if url.startswith("northstar://notes/update"):
                    index = int(params.get("index", ["-1"])[0])
                    title = params.get("title", [""])[0]
                    body = params.get("body", [""])[0]
                    notes = _load_notes()
                    if 0 <= index < len(notes):
                        notes[index]["title"] = title
                        notes[index]["body"] = body
                        _save_notes(notes)
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return
                
                if url.startswith("northstar://notes/delete"):
                    index = int(params.get("index", ["-1"])[0])
                    notes = _load_notes()
                    if 0 <= index < len(notes):
                        notes.pop(index)
                        _save_notes(notes)
                    data = b'{"ok":true}'
                    buf = QBuffer(); buf.setData(QByteArray(data))
                    buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                    job.reply(b"application/json", buf)
                    return
                
                html = _build_notes_html(dark_mode=_global_dark_mode)
                data = html.encode("utf-8")
                buf = QBuffer(); buf.setData(QByteArray(data))
                buf.open(QBuffer.OpenModeFlag.ReadOnly); buf.setParent(job)
                job.reply(b"text/html; charset=utf-8", buf)
                return

            job.fail(QWebEngineUrlRequestJob.Error.UrlInvalid)
        except Exception as e:
            _log("URL_HANDLER", f"NorthStar URL handler error: {e}")
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)


def _load_css(asset_path: str) -> str:
    """Load CSS content from an asset path."""
    css_path = _asset(asset_path)
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""


# ─────────────────────────────────────────────
#  STARTUP CACHE
# ─────────────────────────────────────────────
_CACHE_FILE     = os.path.join(_data_dir(), "northstar_startup.cache")
_CACHE_VERSION  = 6
__version__ = "4.0.0"
_CACHE_TTL      = 86_400          # 24 h
_CACHE_MAX_SIZE = 300 * 1024 * 1024   # 300 MB — evict the whole file above this

class StartupCache:
    """Persistent disk cache for expensive startup data.

    Primary use-cases
    -----------------
    * New-tab HTML  — large f-string templated at startup; caching it across
      launches avoids re-rendering hundreds of lines of CSS each time.
    * Any other picklable value callers want to persist cheaply.

    Write policy
    ------------
    Writes are *self-scheduling*: every call to put() arms a 30-second
    debounce timer (daemon thread).  The cache flushes itself quietly in the
    background rather than blocking the UI on close.

    Size limit
    ----------
    On load, if the cache file exceeds _CACHE_MAX_SIZE (300 MB) it is deleted
    and the cache starts empty for this session — no manual intervention needed.
    """

    def __init__(self):
        self._data:         dict                    = {}
        self._dirty:        bool                    = False
        self._generation:   int                     = 0
        self._flush_timer:  threading.Timer | None  = None
        self._lock = threading.Lock()
        self._loaded = threading.Event()
        # Load in background thread so pickle deserialization never blocks startup
        t = threading.Thread(target=self._load, daemon=True)
        t.start()

    # ── persistence ──────────────────────────
    def _load(self):
        with self._lock:
            generation = self._generation
        loaded_data = None
        try:
            if os.path.getsize(_CACHE_FILE) > _CACHE_MAX_SIZE:
                os.remove(_CACHE_FILE)
            else:
                with open(_CACHE_FILE, "rb") as f:
                    raw = pickle.load(f)
                if (isinstance(raw, dict) and raw.get("_v") == _CACHE_VERSION
                        and time.time() - raw.get("_ts", 0) <= _CACHE_TTL):
                    loaded_data = {k: v for k, v in raw.items() if not k.startswith("_")}
        except Exception:
            loaded_data = {}
        finally:
            with self._lock:
                if (self._generation == generation and not self._dirty
                        and loaded_data is not None):
                    self._data = loaded_data
                self._loaded.set()

    def _schedule_flush(self):
        """Arm (or re-arm) a 30 s background flush after the last write."""
        with self._lock:
            if self._flush_timer is not None:
                self._flush_timer.cancel()
            t = threading.Timer(30.0, self._background_flush)
            t.daemon = True   # won't keep the process alive at exit
            t.start()
            self._flush_timer = t

    def _background_flush(self):
        with self._lock:
            self._flush_timer = None
        self.flush()

    def flush(self):
        """Write dirty in-memory data to disk (safe to call any time)."""
        with self._lock:
            if not self._dirty:
                return
            generation = self._generation
            snapshot = dict(self._data)
        try:
            payload = {"_v": _CACHE_VERSION, "_ts": time.time(), **snapshot}
            with open(_CACHE_FILE, "wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
            with self._lock:
                if generation == self._generation:
                    self._dirty = False
        except Exception:
            pass

    # ── public API ───────────────────────────
    def get(self, key, default=None):
        if not self._loaded.is_set():
            return default
        with self._lock:
            return self._data.get(key, default)

    def put(self, key, value):
        with self._lock:
            if self._data.get(key) == value:
                return          # unchanged — don't dirty or reschedule
            self._data[key] = value
            self._dirty = True
            self._generation += 1
        self._schedule_flush()   # write itself 30 s after last mutation

    def invalidate(self, key=None):
        """Clear one key, or the entire cache when key is None."""
        with self._lock:
            if key is None:
                self._data.clear()
            else:
                self._data.pop(key, None)
            self._dirty = True
            self._generation += 1
        self._schedule_flush()


_startup_cache = StartupCache()





# ─────────────────────────────────────────────
#  BOOKMARKS
# ─────────────────────────────────────────────
BOOKMARKS_FILE = os.path.join(_data_dir(), "northstar_bookmarks.json")
FAVICON_CACHE_FILE = os.path.join(_data_dir(), "northstar_favicons.json")

def _load_bookmarks():
    try:
        with open(BOOKMARKS_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def _save_bookmarks(lst):
    try:
        with open(BOOKMARKS_FILE, "w") as f:
            json.dump(lst, f, indent=2)
    except Exception:
        pass

def _load_favicon_cache():
    """Load persisted favicon data: {domain: base64_png_bytes}."""
    try:
        with open(FAVICON_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_favicon_cache(data):
    """Persist favicon data to disk."""
    temp_path = f"{FAVICON_CACHE_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(temp_path, FAVICON_CACHE_FILE)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass

def _parse_netscape_bookmarks(html_text: str) -> list:
    """Parse a Netscape bookmark file (Chrome/Edge/Firefox export) and return
    a list of {title, url} dicts. Folder structure and add_date are ignored —
    we only need the flat list of links.
    """
    out = []
    for m in re.finditer(r'<A\s+HREF="([^"]+)"[^>]*>(.*?)</A>',
                         html_text, flags=re.IGNORECASE | re.DOTALL):
        url = m.group(1).strip()
        if not url or url.lower().startswith(("place:", "javascript:", "about:")):
            continue
        title = _html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if not title:
            title = url
        out.append({"title": title[:200], "url": url})
    return out


# ── INSTALLED-BROWSER BOOKMARK IMPORTER ─────────────────────────────────────
# Chromium-family browsers (Chrome, Edge, Brave, Vivaldi, Opera) store
# bookmarks in a JSON file under the user data dir. Firefox uses SQLite
# (places.sqlite). We only read the Bookmarks Bar and Other Bookmarks
# folders — synced/mobile profiles are skipped.

_CHROMIUM_BOOKMARK_ROOTS = {"bookmark_bar", "other", "synced"}  # roots we want

_CHROMIUM_BROWSERS = [
    # (display name, relative user-data root, profile subdirs to scan)
    ("Chrome",  os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"), "Default Profile*"),
    ("Edge",    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data"),     "Default Profile*"),
    ("Brave",   os.path.join(os.environ.get("APPDATA", ""),      "BraveSoftware", "Brave-Browser", "User Data"), "Default Profile*"),
    ("Vivaldi", os.path.join(os.environ.get("APPDATA", ""),      "Vivaldi", "User Data"),               "Default Profile*"),
    ("Opera",   os.path.join(os.environ.get("APPDATA", ""),      "Opera Software", "Opera Stable"),     ""),
]


def _iter_chromium_profiles(user_data_dir: str):
    """Yield (profile_name, bookmarks_json_path) for every profile found
    under the given Chromium user-data directory that has a Bookmarks file.
    """
    if not user_data_dir or not os.path.isdir(user_data_dir):
        return
    try:
        entries = sorted(os.listdir(user_data_dir))
    except OSError:
        return
    for name in entries:
        if not (name == "Default" or name.startswith("Profile ")):
            continue
        candidate = os.path.join(user_data_dir, name, "Bookmarks")
        if os.path.isfile(candidate):
            yield name, candidate


def _extract_chromium_bookmarks(json_path: str) -> list:
    """Read a Chromium Bookmarks JSON and return {title,url} pairs from the
    Bookmarks Bar and Other Bookmarks roots (recursively).
    """
    out: list = []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return out

    def walk(node: dict):
        if not isinstance(node, dict):
            return
        if node.get("type") == "url":
            url = (node.get("url") or "").strip()
            if not url or url.lower().startswith(("place:", "javascript:", "about:", "chrome:", "edge:", "brave:", "vivaldi:", "opera:")):
                return
            title = (node.get("name") or url).strip()
            out.append({"title": title[:200], "url": url})
            return
        if node.get("type") == "folder":
            # Skip mobile / synced subtrees unless the root asked for them.
            children = node.get("children") or []
            for c in children:
                walk(c)
            return

    roots = data.get("roots") or {}
    for root_name, root in roots.items():
        if root_name in _CHROMIUM_BOOKMARK_ROOTS:
            walk(root)
    return out


def _extract_firefox_bookmarks(sqlite_path: str) -> list:
    """Read Firefox places.sqlite (read-only) and return {title,url} from
    the Bookmarks Menu and Bookmarks Toolbar folders.
    """
    out: list = []
    uri = f"file:{sqlite_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        try:
            conn = sqlite3.connect(sqlite_path)
        except sqlite3.OperationalError:
            return out
    try:
        cur = conn.cursor()
        # 1=Bookmarks Menu, 2=Bookmarks Toolbar, 3=Unsorted Bookmarks, ...
        # (per Firefox source — these IDs are stable across recent versions.)
        cur.execute(
            """
            SELECT b.title, p.url
            FROM moz_bookmarks b
            JOIN moz_places p ON p.id = b.fk
            WHERE b.type = 1
              AND b.parent IN (1, 2)
              AND p.url IS NOT NULL
              AND p.url NOT LIKE 'place:%'
              AND p.url NOT LIKE 'javascript:%'
              AND p.url NOT LIKE 'about:%'
            """
        )
        for title, url in cur.fetchall():
            url = (url or "").strip()
            if not url:
                continue
            title = (title or url).strip()
            out.append({"title": title[:200], "url": url})
    except sqlite3.DatabaseError:
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return out


def _firefox_profile_dirs() -> list:
    """Return candidate places.sqlite paths for every Firefox profile."""
    base = os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox", "Profiles")
    if not os.path.isdir(base):
        return []
    paths = []
    try:
        for name in sorted(os.listdir(base)):
            # Default profile dir ends in ".default" or ".default-release".
            cand = os.path.join(base, name, "places.sqlite")
            if os.path.isfile(cand):
                paths.append(cand)
    except OSError:
        pass
    return paths


def _detect_installed_browsers() -> list:
    """Return [(display_name, [{title,url}, ...])] for every installed
    browser we can find. Order: Chrome, Edge, Brave, Vivaldi, Opera, Firefox.
    Browsers with zero bookmarks are omitted.
    """
    results: list = []

    for name, user_data, _ in _CHROMIUM_BROWSERS:
        if not user_data or not os.path.isdir(user_data):
            continue
        seen_urls: set = set()
        merged: list = []
        for _profile, path in _iter_chromium_profiles(user_data):
            for bm in _extract_chromium_bookmarks(path):
                if bm["url"] in seen_urls:
                    continue
                seen_urls.add(bm["url"])
                merged.append(bm)
        if merged:
            results.append((name, merged))

    for sqlite_path in _firefox_profile_dirs():
        bookmarks = _extract_firefox_bookmarks(sqlite_path)
        if bookmarks:
            # Firefox shows up once even if multiple profiles exist.
            results.append(("Firefox", bookmarks))

    return results

def _root_domain(host: str) -> str:
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host








# ─────────────────────────────────────────────
#  LEO AI WORKER
# ─────────────────────────────────────────────
class LeoAIWorker(QThread):
    chunk_ready = pyqtSignal(str)
    done        = pyqtSignal()
    error       = pyqtSignal(str)

    def __init__(self, prompt, context="", system=None):
        super().__init__()
        self.prompt = prompt
        self.context = context
        self.system = system or "You are Leo, a helpful browser assistant. Be concise and clear."

    def run(self):
        try:
            from ai_manager import AIManager
            ai_manager = AIManager()
            provider = ai_manager.get_current_provider()
            
            for token in provider.generate_stream(self.prompt, system=self.system, context=self.context):
                if token.startswith("Error:"):
                    self.error.emit(token[6:])
                    return
                self.chunk_ready.emit(token)
            
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class OpalSearchWorker(QThread):
    """Three-phase Opal search worker.

    Phase 1 — Web discovery results emitted once ready.
    Phase 2 — Images emitted as soon as they are available.
    Phase 3 — Videos emitted as soon as they are available.
    
    PROGRESSIVE: Also emits individual web results via `result_ready` as they arrive!
    """

    results_ready = pyqtSignal(str, list, str)  # (query, results, "")
    result_ready  = pyqtSignal(str, dict)                # (query, individual result dict)
    images_ready  = pyqtSignal(str, list)         # (query, images)
    videos_ready  = pyqtSignal(str, list)         # (query, videos)
    failed        = pyqtSignal(str)

    def __init__(self, query: str, ns_search=None, search_manager=None):
        super().__init__()
        self.query     = query
        self.ns_search = ns_search
        self._search_manager = search_manager
        self._results = []
        self._videos = []
        self._load_time = None

    def run(self) -> None:
        import time
        start = time.perf_counter()
        # We use a ThreadPoolExecutor to run search phases
        with ThreadPoolExecutor(max_workers=4) as pool:
            # Phase 2 & 3: Images & Videos (only if media fetch is enabled)
            f3 = None
            f4 = None
            if ENABLE_MEDIA_FETCH:
                f3 = pool.submit(self._fetch_images)
                f4 = pool.submit(self._fetch_videos)

            # Fetch discovery results
            try:
                self._fetch_results_progressive()
                
                # Wait for images/videos if needed!
                if f3:
                    f3.result()
                if f4:
                    f4.result()

                self._load_time = time.perf_counter() - start
                self.results_ready.emit(self.query, self._results, "")
            except Exception as exc:
                self.failed.emit(str(exc))

    def _fetch_results_progressive(self):
        try:
            if self._search_manager:
                # Use new SearchManager backend
                search_results = self._search_manager.search(self.query, limit=20)
                self._from_cache = getattr(self._search_manager, "_last_cached", False)
                self._results = []
                
                # Buffer results to prevent signal flooding
                buffer = []
                for sr in search_results:
                    domain = ""
                    import re as _re
                    m = _re.search(r"https?://([^/]+)", sr.url)
                    if m:
                        domain = m.group(1)
                    result_dict = {
                        "title": sr.title,
                        "url": sr.url,
                        "snippet": sr.snippet,
                        "display_url": sr.display_url or domain,
                        "domain": domain,
                        "favicon": sr.favicon or f"https://icons.duckduckgo.com/ip3/{domain}.ico",
                        "thumbnail": "",
                        "pageid": 0,
                    }
                    self._results.append(result_dict)
                    buffer.append(result_dict)
                    
                    if len(buffer) >= 5:
                        for r in buffer:
                            self.result_ready.emit(self.query, r)
                        buffer = []
                        QThread.msleep(10)
                
                # Flush remaining
                for r in buffer:
                    self.result_ready.emit(self.query, r)
            else:
                # Fallback to old NorthStarSearch
                self._results = self.ns_search.fetch_opal_results(self.query, max_candidate_pool=100)
                buffer = []
                for i, result in enumerate(self._results):
                    buffer.append(result)
                    if len(buffer) >= 5:
                        for r in buffer:
                            self.result_ready.emit(self.query, r)
                        buffer = []
                        QThread.msleep(10)
                for r in buffer:
                    self.result_ready.emit(self.query, r)
        except Exception as exc:
            self._results = []
            self.failed.emit(str(exc))

    def _fetch_images(self):
        try:
            _log("WORKER", f"Fetching images for {self.query!r}")
            images = self.ns_search.fetch_opal_images(self.query)
            if images:
                _log("WORKER", f"Emitting {len(images)} images for {self.query!r}")
                self.images_ready.emit(self.query, images)
            else:
                _log("WORKER", f"No images found for {self.query!r}")
        except Exception as exc:
            _log("WORKER_ERR", f"Image fetch failed: {exc}")
            
    def _fetch_videos(self):
        try:
            _log("WORKER", f"Fetching videos for {self.query!r}")
            videos = self.ns_search.fetch_opal_videos(self.query)
            self._videos = videos
            if videos:
                _log("WORKER", f"Emitting {len(videos)} videos for {self.query!r}")
                self.videos_ready.emit(self.query, videos)
            else:
                _log("WORKER", f"No videos found for {self.query!r}")
        except Exception as exc:
            self._videos = []
            _log("WORKER_ERR", f"Video fetch failed: {exc}")

# ─────────────────────────────────────────────
#  OPAL DISCOVERY — results page renderer
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
#  LOADING PAGE  (unchanged aesthetically; updated flavour text)
# ─────────────────────────────────────────────────────────────────────────────

def _build_opal_loading_html(query: str, dark_mode: bool = True) -> str:
    q_esc = _html_mod.escape(query)
    q_enc = quote_plus(query)
    
    fw = get_fernway()
    accent_p = fw.get("accent_primary", "#4fc3f7")
    accent_s = fw.get("accent_secondary", "#9c6ff7")
    opacity = fw.get("transparency_level", 0.88)
    glow_int = fw.get("glow_intensity", 0.5)
    blur_str = fw.get("blur_strength", 20)
    
    if oled_enabled():
        css_vars = oled_css_vars(blur_str)
    elif dark_mode:
        css_vars = (
            f"--bg:#080b14;--surface:rgba(255,255,255,0.028);--surface2:rgba(255,255,255,0.055);"
            f"--border:rgba(100,120,200,{0.1 + 0.15 * glow_int});--accent:{accent_p};--accent2:{accent_s};"
            f"--text:#dde4f0;--muted:#6b7a99;--glow:rgba(79,195,247,{0.2 + 0.3 * glow_int});"
            f"--hdr-bg:rgba(8, 11, 20, {opacity});"
            f"--scrollbar:rgba(255,255,255,0.1);--link-accent:{accent_s};"
            f"--thumb-bg:rgba(255,255,255,0.04);--blur:{blur_str}px;"
        )
    else:
        css_vars = (
            f"--bg:#f0f4ff;--surface:rgba(0,0,0,0.03);--surface2:rgba(0,0,0,0.07);"
            f"--border:rgba(80,100,200,{0.1 + 0.1 * glow_int});--accent:{accent_p};--accent2:{accent_s};"
            f"--text:#1e1b4b;--muted:#6b7280;--glow:rgba(79,70,229,{0.2 + 0.2 * glow_int});"
            f"--hdr-bg:rgba(240, 244, 255, {opacity});"
            f"--scrollbar:rgba(0,0,0,0.15);--link-accent:{accent_s};"
            f"--thumb-bg:rgba(0,0,0,0.06);--blur:{blur_str}px;"
        )

    # ── constellation & wallpaper carousel ─────────────────────────────────────
    wallpaper_mode = fw.get("wallpaper_mode", "static")
    wallpaper_count = len(_global_wallpaper_files)
    wallpaper_indices = _global_wallpaper_indices
    wallpaper_indices_js = json.dumps(wallpaper_indices)

    video_html = ""
    if wallpaper_mode == "video":
        video_html = (
            '<video id="wallpaper-video" autoplay muted loop playsinline '
            'style="position:fixed;top:0;left:0;width:100%;height:100%;'
            'object-fit:cover;z-index:1;pointer-events:none;'
            'filter:blur(8px);transform:scale(1.05) translateZ(0);'
            'will-change: transform; backface-visibility: hidden;">'
            '<source src="' + oled_wallpaper_video_src() + '" type="video/webm">'
            '</video>'
        )

    bg_style = fw.get("background_style", "current")
    if dark_mode:
        line_col, dot_col = "#4fc3f7", "#4fc3f7"
    else:
        line_col, dot_col = "#4f46e5", "#4f46e5"
    constellation_js = get_background_js(bg_style, line_col, dot_col, dark_mode)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{q_esc} — Opal Discovery</title>
<style>
/* ── reset ─────────────────────────────────────── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{{css_vars}}}
html,body{{
  height:100%;background:var(--bg);color:var(--text);
  font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;
  line-height:1.6;overflow-x:hidden
}}

/* ── Wallpaper Carousel ───────────────────────────────────────────────────── */
#wallpaper-carousel{{
  position:fixed;
  top:0;
  left:0;
  width:100%;
  height:100%;
  z-index:0;
  pointer-events:none;
}}
.wallpaper-slide{{
  position:absolute;
  top:0;
  left:0;
  width:100%;
  height:100%;
  background-size:cover;
  background-position:center;
  background-repeat:no-repeat;
  opacity:0;
  transition:opacity 1s ease-in-out;
  z-index:0;
  filter: blur(5px);
  transform: scale(1.05);
}}
.wallpaper-slide.active{{
  opacity:1;
}}
#wallpaper-carousel::before{{
  content:'';
  position:absolute;
  inset:0;
  z-index:1;
  background:linear-gradient(to bottom, rgba(0,0,0,0.05), rgba(0,0,0,0.15));
}}
#wallpaper-carousel::after{{
  content:'';
  position:absolute;
  inset:0;
  z-index:1;
  background:radial-gradient(circle at center, transparent 0%, rgba(0,0,0,0.10) 100%);
}}

#bg{{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;
  display:{'none' if wallpaper_mode == 'video' or (wallpaper_mode == 'carousel' and wallpaper_count > 0) else 'block'};}}
::-webkit-scrollbar{{width:5px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--scrollbar);border-radius:3px}}

/* ── header ────────────────────────────────────── */
.hdr{{
  position:sticky;top:0;z-index:100;
  background:var(--hdr-bg);backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
  padding:10px 28px;display:flex;align-items:center;gap:18px
}}
.brand{{display:flex;align-items:center;gap:7px;text-decoration:none;
        white-space:nowrap;cursor:pointer}}
.brand-gem{{font-size:20px;filter:drop-shadow(0 0 7px var(--accent))}}
.brand-name{{
  font-size:11px;font-weight:700;letter-spacing:.12em;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent
}}
.sbar{{
  flex:1;max-width:580px;
  background:var(--surface2);border:1px solid var(--border);
  border-radius:24px;
  transition:border-color .2s,box-shadow .2s
}}
.sbar form{{display:flex;align-items:center;width:100%;height:100%;padding:0 12px}}
.sbar:focus-within{{border-color:var(--accent);box-shadow:0 0 0 3px var(--glow)}}
.sbar input{{
  flex:1;background:transparent;border:none;outline:none;
  color:var(--text);font-size:14px;padding:8px 0
}}
.sbar input::placeholder{{color:var(--muted)}}
.sbtn{{background:none;border:none;cursor:pointer;color:var(--muted);
       font-size:16px;padding:4px;transition:color .2s}}
.sbtn:hover{{color:var(--accent)}}

/* ── page layout ───────────────────────────────── */
.page{{max-width:740px;margin:0 auto;padding:22px 28px 70px;position:relative;z-index:10}}

/* ── results header ────────────────────────────── */
.res-hdr{{
  font-size:11px;color:var(--muted);letter-spacing:.07em;text-transform:uppercase;
  margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:6px
}}
.web-badge{{
  font-size:10px;font-weight:700;letter-spacing:.06em;
  color:var(--accent);border:1px solid var(--accent);
  border-radius:4px;padding:1px 5px;text-transform:uppercase;opacity:.85
}}

/* ── result card ───────────────────────────────── */
.card{{
  background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:14px 18px;margin-bottom:10px;cursor:pointer;
  transition:all .15s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  transform: translateY(4px);
  animation: fade-in 0.15s ease-out forwards;
}}
.card:nth-child(1) {{ animation-delay: 0ms; }}
.card:nth-child(2) {{ animation-delay: 30ms; }}
.card:nth-child(3) {{ animation-delay: 60ms; }}
.card:nth-child(4) {{ animation-delay: 90ms; }}
.card:nth-child(5) {{ animation-delay: 120ms; }}
.card:nth-child(6) {{ animation-delay: 150ms; }}
.card:nth-child(7) {{ animation-delay: 180ms; }}
.card:nth-child(8) {{ animation-delay: 210ms; }}

/* ── skeleton cards for progressive loading ───────────────────────────────── */
.card.skeleton{{
  cursor:default;pointer-events:none;
  background:var(--surface2);
}}
.skeleton-text{{
  width:100%;height:14px;background:var(--surface);
  border-radius:4px;margin-bottom:8px;
  opacity: 0.6;
  animation:skeleton-pulse 1.5s ease-in-out infinite;
}}
.skeleton-title{{
  width:60%;height:18px;
}}
.skeleton-snip-1{{width:100%}}
.skeleton-snip-2{{width:90%}}
.skeleton-snip-3{{width:75%}}

@keyframes fade-in {{
  from {{ opacity: 0; transform: translateY(4px); }}
  to {{ opacity: 0.75; transform: translateY(0); }}
}}
@keyframes skeleton-pulse{{0%,100%{{opacity:0.6}}50%{{opacity:0.3}}}}

.card:hover{{
  background:var(--surface2);border-color:rgba(79,195,247,.35);
  box-shadow:0 8px 32px rgba(0,0,0,0.4),0 0 0 1px rgba(79,195,247,0.15);
  transform:translateY(-3px);
  opacity:1;
}}

/* card inner layout: text body left, thumbnail right */
.card-inner{{display:flex;align-items:flex-start;gap:14px}}
.card-body{{flex:1;min-width:0;display:flex;flex-direction:column}}

/* thumbnail */
.card-thumb{{
  width:76px;height:76px;border-radius:8px;object-fit:cover;flex-shrink:0;
  background:var(--thumb-bg);opacity:.9;
  border:1px solid var(--border);
  transition:opacity .2s
}}
.card:hover .card-thumb{{opacity:1}}

.card-meta{{display:flex;align-items:center;gap:6px;margin-bottom:5px}}
.fav{{border-radius:2px;opacity:.8;flex-shrink:0;width:14px;height:14px}}
.dom{{font-size:12px;color:var(--accent);font-weight:500}}
.durl{{
  font-size:11px;color:var(--muted);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;max-width:340px
}}
.card-title{{
  display:block;font-size:15px;font-weight:500;color:var(--accent);
  text-decoration:none;line-height:1.4;margin-bottom:5px;transition:color .15s
}}
.card-title:hover{{color:#a5b4fc}}
.card-snip{{
  font-size:13px;color:#8892aa;line-height:1.65;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden
}}
.read-link{{
  display:inline-block;margin-top:7px;font-size:11px;color:var(--link-accent);
  text-decoration:none;opacity:.75;transition:opacity .15s
}}
.read-link:hover{{opacity:1;text-decoration:underline}}

/* no results */
.no-res{{text-align:center;padding:48px;color:var(--muted)}}
.web-link{{color:var(--accent);text-decoration:none}}
.web-link:hover{{text-decoration:underline}}

/* ── related links ────────────────────────────── */
.rel-box{{
  margin-bottom:26px;display:flex;flex-direction:column;gap:10px
}}
.rel-card{{
  background:var(--surface2);border:1px solid var(--border);border-radius:12px;
  padding:12px 16px;display:flex;align-items:center;gap:12px;
  text-decoration:none;transition:transform .15s,border-color .15s,box-shadow .15s
}}
.rel-card:hover{{
  transform:translateY(-1px);border-color:rgba(79,195,247,.3);
  box-shadow:0 4px 12px rgba(0,0,0,.2);
}}
.rel-card.skeleton{{pointer-events:none;opacity:0.7}}
.rel-fav{{width:18px;height:18px;border-radius:3px;flex-shrink:0}}
.rel-info{{flex:1;min-width:0}}
.rel-name{{
  display:block;font-size:14px;font-weight:600;color:var(--accent);
  margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}}
.rel-desc{{
  font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}}
.rel-arrow{{color:var(--muted);font-size:14px;margin-left:auto}}

/* ── image results ─────────────────────────────── */
.img-grid{{
  display:grid;grid-template-columns:repeat(auto-fill, minmax(140px, 1fr));
  gap:12px;margin-bottom:28px;
}}
.img-item{{
  position:relative;aspect-ratio:1/1;border-radius:12px;
  overflow:hidden;background:var(--surface2);border:1px solid var(--border);
  cursor:pointer;transition:transform .2s,box-shadow .2s;
}}
.img-item:hover{{
  transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.4);
  border-color:rgba(79,195,247,0.3);
}}
.img-item img{{
  width:100%;height:100%;object-fit:cover;transition:opacity .3s;
}}
.img-meta{{
  position:absolute;bottom:0;left:0;right:0;padding:8px;
  background:linear-gradient(transparent, rgba(0,0,0,0.85));
  color:#fff;font-size:10px;opacity:0;transition:opacity .2s;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  pointer-events:none;
}}
.img-item:hover .img-meta{{opacity:1}}

/* ── related videos section ─────────────────────────────── */
.video-grid{{
  display:flex;overflow-x:auto;gap:14px;margin-bottom:28px;padding-bottom:8px;scrollbar-width:none;
}}
.video-grid::-webkit-scrollbar{{display:none;}}

.video-item{{
  min-width:220px;max-width:260px;flex-shrink:0;cursor:pointer;
  background:var(--surface);border:1px solid var(--border);border-radius:12px;
  overflow:hidden;transition:transform .2s,box-shadow .2s,border-color .2s;
}}
.video-item:hover{{
  transform:translateY(-3px);box-shadow:0 10px 28px rgba(0,0,0,0.45);
  border-color:rgba(79,195,247,.35);
}}

.video-thumb-wrapper{{
  position:relative;aspect-ratio:16/9;background:var(--surface2);
}}
.video-thumb{{
  width:100%;height:100%;object-fit:cover;
}}
.video-duration{{
  position:absolute;right:6px;bottom:6px;
  background:rgba(0,0,0,0.8);color:#fff;
  font-size:11px;padding:2px 6px;border-radius:4px;
}}
.video-info{{
  padding:10px 12px;
}}
.video-title{{
  font-size:13px;font-weight:600;color:var(--text);
  line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;margin-bottom:4px;
}}
.video-meta{{
  display:flex;gap:8px;
}}
.video-channel,.video-source{{
  font-size:11px;color:var(--muted);
}}

.view-all-btn{{
  color:var(--accent);text-decoration:none;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;opacity:0.8;
  transition:opacity 0.2s,transform 0.2s;
}}
.view-all-btn:hover{{opacity:1;transform:translateX(2px)}}
.show-all-wrap{{
  display:flex;justify-content:center;margin-top:-12px;margin-bottom:24px;
}}
.show-all-btn{{
  background:var(--surface2);border:1px solid var(--border);border-radius:8px;
  padding:8px 20px;font-size:12px;font-weight:600;color:var(--text);
  text-decoration:none;transition:background 0.2s,border-color 0.2s,transform 0.2s;
  display:flex;align-items:center;gap:8px;
}}
.show-all-btn:hover{{
  background:var(--surface);border-color:rgba(79,195,247,0.4);
  transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.2);
}}

/* ── discovery ─────────────────────────────────── */
.disc{{margin-top:32px;padding-top:22px;border-top:1px solid var(--border)}}
.disc-title{{
  font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:13px;display:flex;align-items:center;gap:6px
}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chip{{
  background:var(--surface);border:1px solid var(--border);border-radius:20px;
  padding:5px 13px;font-size:12px;color:var(--text);cursor:pointer;
  text-decoration:none;display:inline-block;
  transition:background .15s,border-color .15s,color .15s
}}
.chip:hover{{background:var(--surface2);border-color:rgba(79,195,247,.4);color:var(--accent)}}

/* ── pagination ─────────────────────────────────── */
.pagination{{
  display:flex;justify-content:center;align-items:center;gap:16px;margin-top:24px;
}}
.pagination-btn{{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:8px 16px;font-size:12px;font-weight:600;color:var(--text);
  cursor:pointer;transition:background 0.2s,border-color 0.2s,color 0.2s;
}}
.pagination-btn:hover:not(:disabled){{
  background:var(--surface2);border-color:rgba(79,195,247,.4);color:var(--accent);
}}
.pagination-btn:disabled{{
  opacity:0.4;cursor:not-allowed;
}}
.pagination-info{{
  font-size:12px;color:var(--muted);
}}

/* ── loading indicator ─────────────────────────────── */
.load-row{{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:24px;position:relative;z-index:1}}
.load-dots{{display:flex;gap:5px}}
.load-dot{{width:5px;height:5px;border-radius:50%;background:var(--muted);animation:dot-pulse 1s ease-in-out infinite}}
.load-dot:nth-child(2){{animation-delay:.15s}}
.load-dot:nth-child(3){{animation-delay:.3s}}
@keyframes dot-pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.3;transform:scale(.7)}}}}
.load-label{{font-size:11px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}}

/* ── Leo insight box ─────────────────────────── */
.leo-box{{background:linear-gradient(135deg,rgba(79,195,247,0.04),rgba(156,111,247,0.04));border:1px solid var(--border);border-radius:14px;padding:18px 22px;margin-bottom:28px;position:relative;overflow:hidden;transition:all 0.3s ease}}
.leo-box:hover{{border-color:var(--accent2);background:linear-gradient(135deg,rgba(79,195,247,0.08),rgba(156,111,247,0.08))}}
.leo-box::before{{content:'';position:absolute;inset:0;background:linear-gradient(110deg,transparent 30%,var(--accent2) 33%,transparent 70%);background-size:200% 100%;animation:glint 2.5s linear infinite}}
.leo-hdr{{display:flex;align-items:center;gap:8px;margin-bottom:14px;position:relative;z-index:1}}
.leo-star{{font-size:14px;color:var(--accent2);filter:drop-shadow(0 0 6px var(--accent2))}}
.leo-lbl{{font-size:12px;font-weight:700;color:var(--accent);letter-spacing:.06em}}
.leo-dot-wrap{{margin-left:auto;display:flex;align-items:center;gap:6px}}
.leo-dot{{width:6px;height:6px;border-radius:50%;background:var(--accent2);animation:pulse 1.2s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.3}}}}
@keyframes glint{{0%{{background-position:-200% 0}}100%{{background-position:200% 0}}}}

.leo-thinking{{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:10px;margin-top:4px}}
.dot-flashing{{position:relative;width:6px;height:6px;border-radius:5px;background-color:var(--accent2);color:var(--accent2);animation:dot-flashing 1s infinite linear alternate;animation-delay:.5s;margin-left:15px}}
.dot-flashing::before,.dot-flashing::after{{content:'';display:inline-block;position:absolute;top:0}}
.dot-flashing::before{{left:-12px;width:6px;height:6px;border-radius:5px;background-color:var(--accent2);color:var(--accent2);animation:dot-flashing 1s infinite linear alternate;animation-delay:0s}}
.dot-flashing::after{{left:12px;width:6px;height:6px;border-radius:5px;background-color:var(--accent2);color:var(--accent2);animation:dot-flashing 1s infinite linear alternate;animation-delay:1s}}
@keyframes dot-flashing{{0%{{background-color:var(--accent2)}}50%,100%{{background-color:rgba(156,111,247,.2)}}}}
</style>
</head>
<body>

<div id="wallpaper-carousel"></div>
<canvas id="bg"></canvas>
{video_html}

<header class="hdr">
  <div class="brand" onclick="history.back()">
    <span class="brand-gem">◈</span>
    <span class="brand-name">OPAL DISCOVERY</span>
  </div>
  <div class="sbar">
    <form onsubmit="doSearch(event)">
      <input id="q" type="text" value="{q_esc}" placeholder="Explore further…" autocomplete="off">
      <button class="sbtn" type="submit">⟶</button>
    </form>
  </div>
</header>

<div class="page">
  <div id="leo-box-container" style="display:none">
    <div class="leo-box">
      <div class="leo-hdr">
        <span class="leo-star">✦</span>
        <span class="leo-lbl">Leo Insight</span>
        <div class="leo-dot-wrap"><div class="leo-dot"></div><span class="leo-stat">Synthesizing web data…</span></div>
      </div>
      <div class="leo-thinking" id="leo-text">
         Searching for primary sources...
         <div class="dot-flashing"></div>
      </div>
    </div>
  </div>
  <div id="rel-container"></div>
  <div id="img-container"></div>
  <div id="vid-container"></div>
  <div class="res-hdr">Discovery Results <span class="web-badge">Web</span></div>
  <div id="results"></div>
  <div id="pagination" class="pagination" style="display:none">
    <button class="pagination-btn" id="prev-btn" disabled>&lt; Previous</button>
    <span class="pagination-info" id="page-info">Page 1</span>
    <button class="pagination-btn" id="next-btn">Next &gt;</button>
  </div>
  <div class="load-row" id="loading-indicator">
    <div class="load-dots">
      <div class="load-dot"></div>
      <div class="load-dot"></div>
      <div class="load-dot"></div>
    </div>
    <span class="load-label">Mapping information</span>
  </div>
</div>

<script>
let currentQuery = {json.dumps(query)}
const OPAL  = "northstar://search?q="
// Make ALL_RESULTS mutable, so we can add progressive results
let ALL_RESULTS = []
const RESULTS_PER_PAGE = 8
let currentPage = 0

// Batch and debounce for addResult
let _result_batch = []
let _result_debounce_timer = null

function _flush_result_batch() {{
  if (_result_batch.length === 0) return;
  for (let result of _result_batch) {{
    ALL_RESULTS.push(result);
  }}
  _result_batch = [];
  renderResults();
  // Hide loading indicator if we have at least one result
  var indicator = document.getElementById('loading-indicator');
  if (indicator && ALL_RESULTS.length > 0) {{
    indicator.style.display = 'none';
  }}
}}

// Global functions for Python ↔ JS communication
function initializeSearch(query) {{
  currentQuery = query;
  ALL_RESULTS = [];
  currentPage = 0;
  document.getElementById('q').value = query;
  document.getElementById('loading-indicator').style.display = 'flex';
  document.getElementById('results').innerHTML = '';
  document.getElementById('pagination').style.display = 'none';
  document.getElementById('rel-container').innerHTML = '';
  document.getElementById('img-container').innerHTML = '';
  document.getElementById('vid-container').innerHTML = '';
  document.getElementById('leo-box-container').style.display = 'none';
  updateChips(query);
}}

function clearResults() {{
  ALL_RESULTS = [];
  currentPage = 0;
  document.getElementById('results').innerHTML = '';
  document.getElementById('pagination').style.display = 'none';
}}

function showLoading(query) {{
  initializeSearch(query);
}}

function addResult(result_dict) {{
  _result_batch.push(result_dict);
  if (_result_debounce_timer) clearTimeout(_result_debounce_timer);
  if (_result_batch.length >= 5) {{
    _flush_result_batch();
  }} else {{
    _result_debounce_timer = setTimeout(_flush_result_batch, 150);
  }}
}}

function setResults(results) {{
  ALL_RESULTS = results;
  currentPage = 0;
  _flush_result_batch();
}}

function appendRelated(links) {{
  if (!links || links.length === 0) return;
  const h = (s) => s.replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[m]));
  let out = '<div class="res-hdr">Related Links</div><div class="rel-box">';
  links.forEach(l => {{
    const name = h(l.name || '');
    const url = h(l.url || '#');
    const desc = h(l.description || '');
    const fav = h(l.favicon || '');
    out += `
<a class="rel-card" href="${{url}}">
  <img class="rel-fav" src="${{fav}}" onerror="this.style.visibility='hidden'" alt="">
  <div class="rel-info">
    <span class="rel-name">${{name}}</span>
    ${{desc ? `<span class="rel-desc">${{desc}}</span>` : ''}}
  </div>
  <span class="rel-arrow">⟶</span>
</a>`;
  }});
  out += '</div>';
  document.getElementById('rel-container').innerHTML = out;
}}

function injectRelated(html) {{
  var container = document.getElementById('rel-container');
  if (!container) return;
  container.innerHTML = html;
}}

function appendImages(images) {{
  if (!images || images.length === 0) return;
  const h = (s) => s.replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[m]));
  let out = '<div class="res-hdr">Images</div><div class="img-grid">';
  images.forEach(img => {{
    const title = h(img.title || '');
    const url = h(img.url || '#');
    const thumbnail = h(img.thumbnail || '');
    out += `
<a class="img-item" href="${{url}}" target="_blank" rel="noopener noreferrer">
  <img src="${{thumbnail}}" alt="${{title}}" loading="lazy" onerror="this.style.display='none'">
  <div class="img-meta">${{title}}</div>
</a>`;
  }});
  out += '</div>';
  document.getElementById('img-container').innerHTML = out;
}}

function injectImages(html) {{
  var container = document.getElementById('img-container');
  if (!container) return;
  container.innerHTML = html;
}}

function appendVideos(videos) {{
  if (!videos || videos.length === 0) return;
  const h = (s) => s.replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[m]));
  let out = '<div class="res-hdr">Videos</div><div class="video-grid">';
  videos.forEach(vid => {{
    const title = h(vid.title || '');
    const url = h(vid.url || '#');
    const thumbnail = h(vid.thumbnail || '');
    const duration = h(vid.duration || '');
    const source = h(vid.source || '');
    out += `
<a class="video-item" href="${{url}}" target="_blank" rel="noopener noreferrer">
  <div class="video-thumb-wrapper">
    <img class="video-thumb" src="${{thumbnail}}" alt="${{title}}" loading="lazy" onerror="this.style.display='none'">
    ${{duration ? `<div class="video-duration">${{duration}}</div>` : ''}}
  </div>
  <div class="video-info">
    <div class="video-title">${{title}}</div>
    <div class="video-meta">
      ${{source ? `<span class="video-source">${{source}}</span>` : ''}}
    </div>
  </div>
</a>`;
  }});
  out += '</div>';
  document.getElementById('vid-container').innerHTML = out;
}}

function injectVideos(html) {{
  var container = document.getElementById('vid-container');
  if (!container) return;
  container.innerHTML = html;
}}

function finishSearch() {{
  document.getElementById('loading-indicator').style.display = 'none';
}}

(function(){{
  var v = document.getElementById('wallpaper-video');
  if (v) {{ v.play().catch(function(){{}}); }}
}})();

/* ── Wallpaper Carousel ───────────────────────────────────────────────────── */
(function(){{
  var WALLPAPER_INDICES = {wallpaper_indices_js};
  var WALLPAPER_MODE = '{wallpaper_mode}';
  var SLIDE_DURATION = 60000; // 60 seconds per slide
  var carousel = document.getElementById('wallpaper-carousel');
  var currentIndex = 0;
  var lastTransitionTime = 0;
  var intervalId = null;
  var preloadedImage = null;

  function preloadImage(src) {{
    preloadedImage = new Image();
    preloadedImage.src = src;
  }}

  function loadCarouselState() {{
    try {{
      var state = JSON.parse(localStorage.getItem('northstarWallpaperState'));
      if (state && state.indices && JSON.stringify(state.indices) === JSON.stringify(WALLPAPER_INDICES)) {{
        currentIndex = state.index || 0;
        lastTransitionTime = state.lastTime || Date.now();
      }}
    }} catch (e) {{
      console.warn('Failed to load wallpaper state:', e);
    }}
  }}

  function saveCarouselState() {{
    try {{
      localStorage.setItem('northstarWallpaperState', JSON.stringify({{
        indices: WALLPAPER_INDICES,
        index: currentIndex,
        lastTime: Date.now()
      }}));
    }} catch (e) {{
      console.warn('Failed to save wallpaper state:', e);
    }}
  }}

  function setActiveSlide(index) {{
    var slides = carousel.querySelectorAll('.wallpaper-slide');
    if (slides[index]) {{
      slides.forEach(function(s, i) {{
        s.classList.toggle('active', i === index);
      }});
      currentIndex = index;
      saveCarouselState();
    }}
  }}

  function nextSlide() {{
    var slides = carousel.querySelectorAll('.wallpaper-slide');
    if (slides.length > 1) {{
      var nextIndex = (currentIndex + 1) % slides.length;
      slides[nextIndex].style.backgroundImage =
        'url(northstar://wallpaper/' + WALLPAPER_INDICES[nextIndex] + ')';
      setActiveSlide(nextIndex);
      preloadImage(
        'northstar://wallpaper/' + WALLPAPER_INDICES[(nextIndex + 1) % slides.length]
      );
    }}
  }}

  if (WALLPAPER_MODE === 'carousel' && WALLPAPER_INDICES.length > 0) {{
    loadCarouselState();
    WALLPAPER_INDICES.forEach(function(index, i) {{
      var slide = document.createElement('div');
      slide.className = 'wallpaper-slide' + (i === currentIndex ? ' active' : '');
      if (i === currentIndex) {{
        slide.style.backgroundImage = 'url(northstar://wallpaper/' + index + ')';
      }}
      carousel.appendChild(slide);
    }});
    if (WALLPAPER_INDICES.length > 1) {{
      var timeSinceLastTransition = Date.now() - lastTransitionTime;
      var slidesMissed = Math.floor(timeSinceLastTransition / SLIDE_DURATION);
      if (slidesMissed > 0) {{
        currentIndex = (currentIndex + slidesMissed) % WALLPAPER_INDICES.length;
        var slides = carousel.querySelectorAll('.wallpaper-slide');
        slides.forEach(function(s, i) {{
          s.classList.toggle('active', i === currentIndex);
        }});
      }}
      carousel.children[currentIndex].style.backgroundImage =
        'url(northstar://wallpaper/' + WALLPAPER_INDICES[currentIndex] + ')';
      preloadImage(
        'northstar://wallpaper/' + WALLPAPER_INDICES[(currentIndex + 1) % WALLPAPER_INDICES.length]
      );
      intervalId = setInterval(nextSlide, SLIDE_DURATION);
      saveCarouselState();
    }}
  }}
}})();

{constellation_js}

function doSearch(e) {{
  e.preventDefault();
  var q = document.getElementById('q').value.trim();
  if (q) window.location.href = OPAL + encodeURIComponent(q);
}}

function updateChips(query) {{
  var q = query.toLowerCase();
  var topics;
  var hasNumbers = /\\d/.test(q);
  var isProduct = hasNumbers || q.length < 10;
  
  if (isProduct) {{
    topics = [
      query + " specs",
      query + " review",
      query + " battery",
      query + " camera",
      query + " vs alternatives",
      query + " price",
    ];
  }} else {{
    topics = [
      query + " explained",
      "what is " + query,
      query + " examples",
      query + " tutorial",
      query + " alternatives",
      query + " documentation",
    ];
  }}
  
  const chipsContainer = document.createElement('div');
  chipsContainer.className = 'disc';
  const title = document.createElement('div');
  title.className = 'disc-title';
  title.innerHTML = '<span>◆</span> Related searches';
  chipsContainer.appendChild(title);
  const chipsDiv = document.createElement('div');
  chipsDiv.className = 'chips';
  chipsDiv.id = 'chips';
  
  topics.forEach(function(t) {{
    var a = document.createElement('a');
    a.className = 'chip';
    a.textContent = t;
    a.href = OPAL + encodeURIComponent(t);
    chipsDiv.appendChild(a);
  }});
  
  chipsContainer.appendChild(chipsDiv);
  const page = document.querySelector('.page');
  const existingDisc = page.querySelector('.disc');
  if (existingDisc) existingDisc.remove();
  page.appendChild(chipsContainer);
}}

function buildCardsHTML(results, qEnc) {{
  const h = (s) => s.replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[m]));
  return results.map(r => {{
    const title = h(r.title || '');
    const url = h(r.url || '#');
    const snippet = h(r.snippet || '');
    const domain = h(r.domain || '');
    const favicon = h(r.favicon || '');
    const display_url = h(r.display_url || '');
    const thumbnail = h(r.thumbnail || '');
    let thumbHtml = '';
    if (thumbnail) {{
      thumbHtml = `<img class="card-thumb" src="${{thumbnail}}" alt="" loading="lazy" onerror="this.style.display='none'">`;
    }}
    return `<div class="card" onclick="location.href='${{url}}'">
  <div class="card-inner">
    <div class="card-body">
      <div class="card-meta">
        <img class="fav" src="${{favicon}}" onerror="this.style.visibility='hidden'" width="14" height="14" alt="">
        <span class="dom">${{domain}}</span>
        <span class="durl">${{display_url}}</span>
      </div>
      <a class="card-title" href="${{url}}" onclick="event.stopPropagation()">${{title}}</a>
      <p class="card-snip">${{snippet}}</p>
      <a class="read-link" href="${{url}}" onclick="event.stopPropagation()">Visit site →</a>
    </div>
    ${{thumbHtml}}
  </div>
</div>`;
  }}).join('');
}}

function renderResults() {{
  const container = document.getElementById('results');
  const start = currentPage * RESULTS_PER_PAGE;
  const end = start + RESULTS_PER_PAGE;
  const resultsSlice = ALL_RESULTS.slice(start, end);
  
  if (resultsSlice.length === 0) {{
    container.innerHTML = '<div class="no-res">No results found — <a class="web-link" href="https://google.com/search?q={q_enc}">search Google directly →</a></div>';
  }} else {{
    container.innerHTML = buildCardsHTML(resultsSlice, '{q_enc}');
  }}
  
  updatePagination();
}}

function updatePagination() {{
  const totalPages = Math.ceil(ALL_RESULTS.length / RESULTS_PER_PAGE);
  const paginationDiv = document.getElementById('pagination');
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  const pageInfo = document.getElementById('page-info');
  
  if (totalPages > 1) {{
    paginationDiv.style.display = 'flex';
  }} else {{
    paginationDiv.style.display = 'none';
  }}
  
  prevBtn.disabled = currentPage === 0;
  nextBtn.disabled = currentPage >= totalPages - 1;
  pageInfo.textContent = `Page ${{currentPage + 1}}`;
}}

document.addEventListener('DOMContentLoaded', function() {{
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  
  if (prevBtn) {{
    prevBtn.addEventListener('click', () => {{
      if (currentPage > 0) {{
        currentPage--;
        renderResults();
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
      }}
    }});
  }}
  
  if (nextBtn) {{
    nextBtn.addEventListener('click', () => {{
      const totalPages = Math.ceil(ALL_RESULTS.length / RESULTS_PER_PAGE);
      if (currentPage < totalPages - 1) {{
        currentPage++;
        renderResults();
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
      }}
    }});
  }}
  
  updateChips(currentQuery);
}});
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
#  ERROR PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _build_opal_error_html(query: str, error: str = "") -> str:
    q     = _html_mod.escape(query)
    q_enc = quote_plus(query)
    err   = _html_mod.escape(error)
    if oled_enabled():
        _bg, _fg, _mut, _accent = "#000000", "#e8edf8", "#6b7a99", "#d4af37"
        _bdr = "rgba(212,175,55,0.30)"
        _hov = "rgba(212,175,55,0.12)"
    else:
        _bg, _fg, _mut, _accent = "#080b14", "#dde4f0", "#6b7a99", "#4fc3f7"
        _bdr = "rgba(79,195,247,0.3)"
        _hov = "rgba(79,195,247,0.12)"
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{_bg};color:{_fg};font-family:'Segoe UI',system-ui,sans-serif;
     display:flex;flex-direction:column;align-items:center;justify-content:center;
     height:100vh;gap:12px}}
.icon{{font-size:36px;filter:drop-shadow(0 0 10px #f87171)}}
.title{{font-size:16px;font-weight:600;color:#f87171}}
.msg{{font-size:13px;color:{_mut};max-width:420px;text-align:center;line-height:1.6}}
.query{{color:{_accent}}}
.wiki{{margin-top:8px;display:inline-block;color:{_accent};font-size:13px;
       text-decoration:none;border:1px solid {_bdr};border-radius:8px;
       padding:6px 16px;transition:background .2s}}
.wiki:hover{{background:{_hov}}}
</style></head><body>
<div class="icon">◈</div>
<div class="title">Opal discovery offline</div>
<div class="msg">Something went wrong while exploring
  <span class="query">"{q}"</span>.
  {"<br><small style='color:#4b5563;margin-top:4px;display:block'>"+err+"</small>" if err else ""}
</div>
<a class="wiki" href="https://google.com/search?q={q_enc}">
  Try Google instead →
</a>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN RESULTS PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _build_cards_for_page(results: list, page: int, per_page: int, q_enc: str) -> str:
    start = page * per_page
    end = start + per_page
    return _build_cards(results[start:end], q_enc)


def _load_opal_query_types():
    config_path = _asset(os.path.join("legacy", "experimental_search", "opal_query_types.json"))
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log("CONFIG", f"Failed to load query types config: {e}")
        return {"query_types": {}, "default_type": "concept"}


def _build_opal_html(
    query:       str,
    results:     list,
    model:       str  = None,
    dark_mode:   bool = True,
    leo_summary: str  = "",
    related_links: list = None,
    images:      list = None,
    videos:      list = None,
    load_time:   float = None,
    from_cache:  bool = False,
) -> str:
    """Build the Opal Discovery results page."""
    if model is None:
        try:
            from ai_manager import AIManager
            ai_manager = AIManager()
            provider = ai_manager.get_current_provider()
            model = provider.config.get("model", "AI")
        except:
            model = "AI"
    q_esc  = _html_mod.escape(query)
    q_enc  = quote_plus(query)
    q_json = json.dumps(query)    # safe JS string literal
    
    results_json = json.dumps(results)
    query_types_config = _load_opal_query_types()
    query_types_json = json.dumps(query_types_config)

    # ── theme tokens ──────────────────────────────────────────────────────────
    fw = get_fernway()
    accent_p = fw.get("accent_primary", "#4fc3f7")
    accent_s = fw.get("accent_secondary", "#9c6ff7")
    opacity  = fw.get("transparency_level", 0.88)
    glow_int = fw.get("glow_intensity", 0.5)
    blur_str = fw.get("blur_strength", 20)
    
    if oled_enabled():
        css_vars = oled_css_vars(blur_str)
    elif dark_mode:
        css_vars = (
            f"--bg:#080b14;--surface:rgba(255,255,255,0.028);--surface2:rgba(255,255,255,0.055);"
            f"--border:rgba(100,120,200,{0.1 + 0.15 * glow_int});--accent:{accent_p};--accent2:{accent_s};"
            f"--text:#dde4f0;--muted:#6b7a99;--glow:rgba(79,195,247,{0.2 + 0.3 * glow_int});"
            f"--hdr-bg:rgba(8,11,20,{opacity});"
            f"--scrollbar:rgba(255,255,255,0.1);--link-accent:{accent_s};"
            f"--thumb-bg:rgba(255,255,255,0.04);--blur:{blur_str}px;"
        )
    else:
        css_vars = (
            f"--bg:#f0f4ff;--surface:rgba(0,0,0,0.03);--surface2:rgba(0,0,0,0.07);"
            f"--border:rgba(80,100,200,{0.1 + 0.1 * glow_int});--accent:{accent_p};--accent2:{accent_s};"
            f"--text:#1e1b4b;--muted:#6b7280;--glow:rgba(79,70,229,{0.2 + 0.2 * glow_int});"
            f"--hdr-bg:rgba(240,244,255,{opacity});"
            f"--scrollbar:rgba(0,0,0,0.15);--link-accent:{accent_s};"
            f"--thumb-bg:rgba(0,0,0,0.06);--blur:{blur_str}px;"
        )

    # ── result cards ──────────────────────────────────────────────────────────
    cards_html = _build_cards_for_page(results, 0, 8, q_enc)

    # ── images ────────────────────────────────────────────────────────────────
    from legacy.experimental_search.opal_html_v2 import _build_images
    img_html = _build_images(images)
    
    # ── related videos ─────────────────────────────────────────────────────────
    from legacy.experimental_search.opal_html_v2 import _build_videos
    vid_html = _build_videos(videos, query)

    # ── constellation ─────────────────────────────────────────────────────────
    bg_style = fw.get("background_style", "current")
    if dark_mode:
        line_col, dot_col = "#4fc3f7", "#4fc3f7"
    else:
        line_col, dot_col = "#4f46e5", "#4f46e5"
    constellation_js = get_background_js(bg_style, line_col, dot_col, dark_mode)

    # ── discovery chips (Wikipedia-oriented) ─────────────────────────────────
    # Chips are generated client-side in JS — no change needed here.

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{q_esc} — Opal Discovery</title>
<style>
/* ── reset ─────────────────────────────────────── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{{css_vars}}}
html,body{{
  height:100%;background:var(--bg);color:var(--text);
  font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;
  line-height:1.6;overflow-x:hidden
}}
#bg{{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none}}
::-webkit-scrollbar{{width:5px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--scrollbar);border-radius:3px}}

/* ── header ────────────────────────────────────── */
.hdr{{
  position:sticky;top:0;z-index:100;
  background:var(--hdr-bg);backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
  padding:10px 28px;display:flex;align-items:center;gap:18px
}}
.brand{{display:flex;align-items:center;gap:7px;text-decoration:none;
        white-space:nowrap;cursor:pointer}}
.brand-gem{{font-size:20px;filter:drop-shadow(0 0 7px var(--accent))}}
.brand-name{{
  font-size:11px;font-weight:700;letter-spacing:.12em;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent
}}
.sbar{{
  flex:1;max-width:580px;
  background:var(--surface2);border:1px solid var(--border);
  border-radius:24px;
  transition:border-color .2s,box-shadow .2s
}}
.sbar form{{display:flex;align-items:center;width:100%;height:100%;padding:0 12px}}
.sbar:focus-within{{border-color:var(--accent);box-shadow:0 0 0 3px var(--glow)}}
.sbar input{{
  flex:1;background:transparent;border:none;outline:none;
  color:var(--text);font-size:14px;padding:8px 0
}}
.sbar input::placeholder{{color:var(--muted)}}
.sbtn{{background:none;border:none;cursor:pointer;color:var(--muted);
       font-size:16px;padding:4px;transition:color .2s}}
.sbtn:hover{{color:var(--accent)}}

/* ── page layout ───────────────────────────────── */
.page{{max-width:740px;margin:0 auto;padding:22px 28px 70px}}

/* ── results header ────────────────────────────── */
.res-hdr{{
  font-size:11px;color:var(--muted);letter-spacing:.07em;text-transform:uppercase;
  margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:6px
}}
.web-badge{{
  font-size:10px;font-weight:700;letter-spacing:.06em;
  color:var(--accent);border:1px solid var(--accent);
  border-radius:4px;padding:1px 5px;text-transform:uppercase;opacity:.85
}}

/* ── result card ───────────────────────────────── */
.card{{
  background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:14px 18px;margin-bottom:10px;cursor:pointer;
  transition:all .15s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  transform: translateY(4px);
  animation: fade-in 0.15s ease-out forwards;
}}
.card:nth-child(1) {{ animation-delay: 0ms; }}
.card:nth-child(2) {{ animation-delay: 30ms; }}
.card:nth-child(3) {{ animation-delay: 60ms; }}
.card:nth-child(4) {{ animation-delay: 90ms; }}
.card:nth-child(5) {{ animation-delay: 120ms; }}
.card:nth-child(6) {{ animation-delay: 150ms; }}
.card:nth-child(7) {{ animation-delay: 180ms; }}
.card:nth-child(8) {{ animation-delay: 210ms; }}

/* ── skeleton cards for progressive loading ───────────────────────────────── */
.card.skeleton{{
  cursor:default;pointer-events:none;
  background:var(--surface2);
}}
.skeleton-text{{
  width:100%;height:14px;background:var(--surface);
  border-radius:4px;margin-bottom:8px;
  opacity: 0.6;
}}
.skeleton-title{{
  width:60%;height:18px;
}}
.skeleton-snip-1{{width:100%}}
.skeleton-snip-2{{width:90%}}
.skeleton-snip-3{{width:75%}}

@keyframes fade-in {{
  from {{ opacity: 0; transform: translateY(4px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.card:hover{{
  background:var(--surface2);border-color:rgba(79,195,247,.35);
  box-shadow:0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(79,195,247,0.15);
  transform:translateY(-3px);
}}

/* card inner layout: text body left, thumbnail right */
.card-inner{{display:flex;align-items:flex-start;gap:14px}}
.card-body{{flex:1;min-width:0}}

/* thumbnail */
.card-thumb{{
  width:76px;height:76px;border-radius:8px;object-fit:cover;flex-shrink:0;
  background:var(--thumb-bg);opacity:.9;
  border:1px solid var(--border);
  transition:opacity .2s
}}
.card:hover .card-thumb{{opacity:1}}

.card-meta{{display:flex;align-items:center;gap:6px;margin-bottom:5px}}
.fav{{border-radius:2px;opacity:.8;flex-shrink:0;width:14px;height:14px}}
.dom{{font-size:12px;color:var(--accent);font-weight:500}}
.durl{{
  font-size:11px;color:var(--muted);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;max-width:340px
}}
.card-title{{
  display:block;font-size:15px;font-weight:500;color:var(--accent);
  text-decoration:none;line-height:1.4;margin-bottom:5px;transition:color .15s
}}
.card-title:hover{{color:#a5b4fc}}
.card-snip{{
  font-size:13px;color:#8892aa;line-height:1.65;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden
}}
.read-link{{
  display:inline-block;margin-top:7px;font-size:11px;color:var(--link-accent);
  text-decoration:none;opacity:.75;transition:opacity .15s
}}
.read-link:hover{{opacity:1;text-decoration:underline}}

/* no results */
.no-res{{text-align:center;padding:48px;color:var(--muted)}}
.web-link{{color:var(--accent);text-decoration:none}}
.web-link:hover{{text-decoration:underline}}

/* ── related links ────────────────────────────── */
.rel-box{{
  margin-bottom:26px;display:flex;flex-direction:column;gap:10px
}}
.rel-card{{
  background:var(--surface2);border:1px solid var(--border);border-radius:12px;
  padding:12px 16px;display:flex;align-items:center;gap:12px;
  text-decoration:none;transition:transform .15s, border-color .15s, box-shadow .15s
}}
.rel-card:hover{{
  transform:translateY(-1px);border-color:rgba(79,195,247,.3);
  box-shadow:0 4px 12px rgba(0,0,0,.2);
}}
.rel-card.skeleton{{pointer-events:none;opacity:0.7}}
.rel-fav{{width:18px;height:18px;border-radius:3px;flex-shrink:0}}
.rel-info{{flex:1;min-width:0}}
.rel-name{{
  display:block;font-size:14px;font-weight:600;color:var(--accent);
  margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}}
.rel-desc{{
  font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}}
.rel-arrow{{color:var(--muted);font-size:14px;margin-left:auto}}

/* ── image results ─────────────────────────────── */
.img-grid{{
  display:grid;grid-template-columns:repeat(auto-fill, minmax(140px, 1fr));
  gap:12px;margin-bottom:28px;
}}
.img-item{{
  position:relative;aspect-ratio:1/1;border-radius:12px;
  overflow:hidden;background:var(--surface2);border:1px solid var(--border);
  cursor:pointer;transition:transform .2s, box-shadow .2s;
}}
.img-item:hover{{
  transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.4);
  border-color:rgba(79,195,247,0.3);
}}
.img-item img{{
  width:100%;height:100%;object-fit:cover;transition:opacity .3s;
}}
.img-meta{{
  position:absolute;bottom:0;left:0;right:0;padding:8px;
  background:linear-gradient(transparent, rgba(0,0,0,0.85));
  color:#fff;font-size:10px;opacity:0;transition:opacity .2s;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  pointer-events:none;
}}
.img-item:hover .img-meta{{opacity:1}}

/* ── related videos section ─────────────────────────────── */
.video-grid{{
  display:flex;overflow-x:auto;gap:14px;margin-bottom:28px;padding-bottom:8px;scrollbar-width:none;
}}
.video-grid::-webkit-scrollbar{{display:none;}}

.video-item{{
  min-width:220px;max-width:260px;flex-shrink:0;cursor:pointer;
  background:var(--surface);border:1px solid var(--border);border-radius:12px;
  overflow:hidden;transition:transform .2s, box-shadow .2s, border-color .2s;
}}
.video-item:hover{{
  transform:translateY(-3px);box-shadow:0 10px 28px rgba(0,0,0,0.45);
  border-color:rgba(79,195,247,.35);
}}

.video-thumb-wrapper{{
  position:relative;aspect-ratio:16/9;background:var(--surface2);
}}
.video-thumb{{
  width:100%;height:100%;object-fit:cover;
}}
.video-duration{{
  position:absolute;right:6px;bottom:6px;
  background:rgba(0,0,0,0.8);color:#fff;
  font-size:11px;padding:2px 6px;border-radius:4px;
}}
.video-info{{
  padding:10px 12px;
}}
.video-title{{
  font-size:13px;font-weight:600;color:var(--text);
  line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;margin-bottom:4px;
}}
.video-meta{{
  display:flex;gap:8px;
}}
.video-channel, .video-source{{
  font-size:11px;color:var(--muted);
}}

.view-all-btn{{
  color:var(--accent);text-decoration:none;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;opacity:0.8;
  transition:opacity 0.2s, transform 0.2s;
}}
.view-all-btn:hover{{opacity:1;transform:translateX(2px)}}
.show-all-wrap{{
  display:flex;justify-content:center;margin-top:-12px;margin-bottom:24px;
}}
.show-all-btn{{
  background:var(--surface2);border:1px solid var(--border);border-radius:8px;
  padding:8px 20px;font-size:12px;font-weight:600;color:var(--text);
  text-decoration:none;transition:background 0.2s, border-color 0.2s, transform 0.2s;
  display:flex;align-items:center;gap:8px;
}}
.show-all-btn:hover{{
  background:var(--surface);border-color:rgba(79,195,247,0.4);
  transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.2);
}}

/* ── discovery ─────────────────────────────────── */
.disc{{margin-top:32px;padding-top:22px;border-top:1px solid var(--border)}}
.disc-title{{
  font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:13px;display:flex;align-items:center;gap:6px
}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chip{{
  background:var(--surface);border:1px solid var(--border);border-radius:20px;
  padding:5px 13px;font-size:12px;color:var(--text);cursor:pointer;
  text-decoration:none;display:inline-block;
  transition:background .15s,border-color .15s,color .15s
}}
.chip:hover{{background:var(--surface2);border-color:rgba(79,195,247,.4);color:var(--accent)}}

/* ── pagination ─────────────────────────────────── */
.pagination{{
  display:flex;justify-content:center;align-items:center;gap:16px;margin-top:24px;
}}
.pagination-btn{{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:8px 16px;font-size:12px;font-weight:600;color:var(--text);
  cursor:pointer;transition:background 0.2s,border-color 0.2s,color 0.2s;
}}
.pagination-btn:hover:not(:disabled){{
  background:var(--surface2);border-color:rgba(79,195,247,.4);color:var(--accent);
}}
.pagination-btn:disabled{{
  opacity:0.4;cursor:not-allowed;
}}
.pagination-info{{
  font-size:12px;color:var(--muted);
}}

/* ── loading indicator ─────────────────────────────── */
.load-row{{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:24px;position:relative;z-index:1}}
.load-dots{{display:flex;gap:5px}}
.load-dot{{width:5px;height:5px;border-radius:50%;background:var(--muted);animation:dot-pulse 1s ease-in-out infinite}}
.load-dot:nth-child(2){{animation-delay:.15s}}
.load-dot:nth-child(3){{animation-delay:.3s}}
@keyframes dot-pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.3;transform:scale(.7)}}}}
.load-label{{font-size:11px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}}

/* ── load timer ─────────────────────────────────── */
.load-timer{{
  position:fixed;bottom:16px;left:16px;z-index:200;
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:6px 12px;font-size:11px;color:var(--muted);
  backdrop-filter:blur(12px);pointer-events:none;
}}
</style>
</head>
<body>

<header class="hdr">
  <div class="brand" onclick="history.back()">
    <span class="brand-gem">◈</span>
    <span class="brand-name">OPAL DISCOVERY</span>
  </div>
  <div class="sbar">
    <form onsubmit="doSearch(event)">
      <input id="q" type="text" value="{q_esc}" placeholder="Explore further…" autocomplete="off">
      <button class="sbtn" type="submit">⟶</button>
    </form>
  </div>
</header>

<canvas id="bg"></canvas>

<div class="page">

<div id="img-container">{img_html}</div>

<div id="vid-container">{vid_html}</div>

  <div class="res-hdr">
    Discovery Results
    <span class="web-badge">Web</span>
  </div>
  <div id="results">{cards_html}</div>

  <div id="pagination" class="pagination">
    <button class="pagination-btn" id="prev-btn" disabled>&lt; Previous</button>
    <span class="pagination-info" id="page-info">Page 1</span>
    <button class="pagination-btn" id="next-btn">Next &gt;</button>
  </div>

  <div class="load-row" id="loading-indicator" style="display:none">
    <div class="load-dots">
      <div class="load-dot"></div>
      <div class="load-dot"></div>
      <div class="load-dot"></div>
    </div>
    <span class="load-label">Mapping information</span>
  </div>

</div>

<script>
let currentQuery = {q_json};
const OPAL  = "northstar://search?q=";
// Make ALL_RESULTS mutable, so we can add progressive results
let ALL_RESULTS = {results_json};
const QUERY_TYPES_CONFIG = {query_types_json};
const RESULTS_PER_PAGE = 5;
let currentPage = 0;

// Batch and debounce for addResult
let _result_batch = [];
let _result_debounce_timer = null;

function _flush_result_batch() {{
  if (_result_batch.length === 0) return;
  for (let result of _result_batch) {{
    ALL_RESULTS.push(result);
  }}
  _result_batch = [];
  renderResults();
  // Hide loading indicator if we have at least one result
  var indicator = document.getElementById('loading-indicator');
  if (indicator && ALL_RESULTS.length > 0) {{
    indicator.style.display = 'none';
  }}
}}

// Global function to add an individual progressive result
// This will either replace a skeleton card (if available) or append
function addResult(result) {{
  _result_batch.push(result);
  if (_result_debounce_timer) clearTimeout(_result_debounce_timer);
  // Flush after 150ms of inactivity or if we have 5 results
  if (_result_batch.length >= 5) {{
    _flush_result_batch();
  }} else {{
    _result_debounce_timer = setTimeout(_flush_result_batch, 150);
  }}
}}

{constellation_js}

function doSearch(e) {{
  e.preventDefault();
  var q = document.getElementById('q').value.trim();
  if (q) window.location.href = OPAL + encodeURIComponent(q);
}}

function detectQueryTypeJS(query) {{
  var qLower = query.toLowerCase();
  var queryTypes = QUERY_TYPES_CONFIG.query_types;
  var defaultType = QUERY_TYPES_CONFIG.default_type;
  var patternScoreWeight = QUERY_TYPES_CONFIG.pattern_score || 5.0;
  var keywordScoreWeight = QUERY_TYPES_CONFIG.keyword_score || 1.0;
  
  var bestType = defaultType;
  var bestScore = 0.0;
  
  for (var typeName in queryTypes) {{
    if (!queryTypes.hasOwnProperty(typeName)) continue;
    var typeData = queryTypes[typeName];
    var score = 0.0;
    
    // Check keywords
    var keywords = typeData.keywords || [];
    for (var i = 0; i < keywords.length; i++) {{
      if (qLower.indexOf(keywords[i]) !== -1) {{
        score += keywordScoreWeight;
      }}
    }}
    
    // Check patterns (regex)
    var patterns = typeData.patterns || [];
    for (var j = 0; j < patterns.length; j++) {{
      try {{
        var regex = new RegExp(patterns[j]);
        if (regex.test(qLower)) {{
          score += patternScoreWeight;
        }}
      }} catch (e) {{
        console.log("Pattern error:", patterns[j], e);
      }}
    }}
    
    // Update best type
    if (score > bestScore) {{
      bestScore = score;
      bestType = typeName;
    }}
  }}
  
  return {{
    type: bestType,
    data: queryTypes[bestType] || {{}},
    config: QUERY_TYPES_CONFIG
  }};
}}

function updateChips(query) {{
  var q = query.toLowerCase();
  var qWords = q.split(/\\s+/); // Split into words
  
  var typeInfo = detectQueryTypeJS(query);
  var modifiers = typeInfo.data.modifiers || [];
  
  // Calculate confidence and ambiguity level!
  var primaryCategory = typeInfo.type;
  var confidence = 0.5; // Default medium confidence
  var ambiguous = true;
  
  // If typeInfo has keywords/patterns matched, calculate a simple confidence!
  // For confidence: number of keyword matches + pattern matches (weighted 5x)
  var queryTypes = QUERY_TYPES_CONFIG.query_types;
  var typeData = queryTypes[primaryCategory] || {{}};
  var keywords = typeData.keywords || [];
  var patterns = typeData.patterns || [];
  var patternScoreWeight = QUERY_TYPES_CONFIG.pattern_score || 5.0;
  var keywordScoreWeight = QUERY_TYPES_CONFIG.keyword_score || 1.0;
  var score = 0.0;
  
  for (var i = 0; i < keywords.length; i++) {{
    if (q.indexOf(keywords[i]) !== -1) {{
      score += keywordScoreWeight;
    }}
  }}
  
  for (var j = 0; j < patterns.length; j++) {{
    try {{
      var regex = new RegExp(patterns[j]);
      if (regex.test(q)) {{
        score += patternScoreWeight;
      }}
    }} catch(e) {{}}
  }}
  
  if (score > 5) {{
    confidence = 0.9;
    ambiguous = false;
  }} else if (score > 2) {{
    confidence = 0.7;
    ambiguous = false;
  }} else {{
    confidence = 0.5;
    ambiguous = true;
  }}
  
  console.log("Opal query type:", primaryCategory, "confidence:", confidence, "ambiguous:", ambiguous);
  
  // Strictly stick to modifiers from typeinfo! Only fall back if ambiguous/confidence low!
  if (!modifiers.length) {{
    if (primaryCategory === "person") {{
      modifiers = [
        "biography of {query}",
        "{query} early life",
        "{query} achievements",
        "{query} quotes",
        "{query} net worth"
      ];
    }} else if (primaryCategory === "product") {{
      modifiers = [
        "{query} specs",
        "{query} review",
        "{query} battery",
        "{query} camera",
        "{query} gaming",
        "{query} benchmarks"
      ];
    }} else if (primaryCategory === "company") {{
      modifiers = [
        "history of {query}",
        "who founded {query}",
        "{query} products",
        "{query} news",
        "{query} stock",
        "{query} competitors"
      ];
    }} else if (primaryCategory === "entertainment") {{
      modifiers = [
        "{query} review",
        "{query} release date",
        "{query} cast",
        "{query} soundtrack",
        "{query} alternatives"
      ];
    }} else if (primaryCategory === "tutorial") {{
      modifiers = [
        "{query} step by step",
        "{query} for beginners",
        "{query} advanced",
        "{query} examples",
        "{query} best practices"
      ];
    }} else if (primaryCategory === "website") {{
      modifiers = [
        "history of {query}",
        "who founded {query}",
        "{query} alternatives",
        "{query} tutorial",
        "{query} creator tools"
      ];
    }} else {{
      // Concept
      modifiers = [
        "history of {query}",
        "{query} examples",
        "{query} organizations",
        "{query} modern applications",
        "{query} educational resources"
      ];
    }}
  }}
  
  // Generate topics and filter duplicates (remove those already containing query words as modifiers)
  var topics = [];
  var used = new Set();
  
  for (var i = 0; i < modifiers.length; i++) {{
    var t = modifiers[i].replace(/{{query}}/g, query);
    var tLower = t.toLowerCase();
    // Check if this modifier already appears in the query (avoid "specs specs")
    var alreadyInQuery = false;
    for (var j = 0; j < qWords.length; j++) {{
      if (tLower.indexOf(qWords[j]) !== -1 && qWords[j] !== query.toLowerCase()) {{
        // Check if the modifier word is already a suffix/prefix in query (e.g., query already has "specs")
        var modWords = t.toLowerCase().replace(query.toLowerCase(), "").trim().split(/\\s+/);
        for (var k = 0; k < modWords.length; k++) {{
          if (modWords[k] && qWords.indexOf(modWords[k]) !== -1) {{
            alreadyInQuery = true;
            break;
          }}
        }}
      }}
    }}
    if (!alreadyInQuery && !used.has(tLower)) {{
      used.add(tLower);
      topics.push(t);
    }}
    if (topics.length >= 6) break;
  }}
  
  var chips = document.getElementById('chips');
  if (!chips) return;
  chips.innerHTML = '';
  topics.forEach(function(t) {{
    var a = document.createElement('a');
    a.className   = 'chip';
    a.textContent = t;
    a.href        = OPAL + encodeURIComponent(t);
    chips.appendChild(a);
  }});
}}

function renderResults() {{
  const start = currentPage * RESULTS_PER_PAGE;
  const end = start + RESULTS_PER_PAGE;
  const resultsSlice = ALL_RESULTS.slice(start, end);
  const container = document.getElementById('results');
  
  if (!resultsSlice.length) {{
    container.innerHTML = '<div class="no-res">No results found — <a class="web-link" href="https://google.com/search?q={q_enc}">search Google directly →</a></div>';
  }} else {{
    container.innerHTML = buildCardsHTML(resultsSlice, '{q_enc}');
  }}
  
  updatePagination();
}}

function buildCardsHTML(results, qEnc) {{
  const h = (s) => s.replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[m]));
  return results.map(r => {{
    const title = h(r.title || '');
    const url = h(r.url || '#');
    const snippet = h(r.snippet || '');
    const domain = h(r.domain || '');
    const favicon = h(r.favicon || '');
    const displayUrl = h(r.display_url || '');
    const thumbnail = h(r.thumbnail || '');
    
    let thumbHtml = '';
    if (thumbnail) {{
      thumbHtml = `<img class="card-thumb" src="${{thumbnail}}" alt="" loading="lazy" onerror="this.style.display='none'">`;
    }}
    
    return `<div class="card" onclick="location.href='${{url}}'">
  <div class="card-inner">
    <div class="card-body">
      <div class="card-meta">
        <img class="fav" src="${{favicon}}" onerror="this.style.visibility='hidden'" width="14" height="14" alt="">
        <span class="dom">${{domain}}</span>
        <span class="durl">${{displayUrl}}</span>
      </div>
      <a class="card-title" href="${{url}}" onclick="event.stopPropagation()">${{title}}</a>
      <p class="card-snip">${{snippet}}</p>
      <a class="read-link" href="${{url}}" onclick="event.stopPropagation()">Visit site →</a>
    </div>
    ${{thumbHtml}}
  </div>
</div>`;
  }}).join('');
}}

function updatePagination() {{
  const totalPages = Math.ceil(ALL_RESULTS.length / RESULTS_PER_PAGE);
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  const pageInfo = document.getElementById('page-info');
  
  prevBtn.disabled = currentPage === 0;
  nextBtn.disabled = currentPage >= totalPages - 1;
  pageInfo.textContent = `Page ${{currentPage + 1}}`;
}}

document.getElementById('prev-btn').addEventListener('click', () => {{
  if (currentPage > 0) {{
    currentPage--;
    renderResults();
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }}
}});

document.getElementById('next-btn').addEventListener('click', () => {{
  const totalPages = Math.ceil(ALL_RESULTS.length / RESULTS_PER_PAGE);
  if (currentPage < totalPages - 1) {{
    currentPage++;
    renderResults();
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }}
}});

function showLoading(query) {{
  currentQuery = query;
  ALL_RESULTS = [];
  SEEN_URLS = new Set();
  var qInput = document.getElementById('q');
  if (qInput) qInput.value = query;
  
  var results = document.getElementById('results');
  if (results) results.innerHTML = '';
  
  var rel = document.getElementById('rel-container');
  if (rel) rel.innerHTML = '';
  
  var img = document.getElementById('img-container');
  if (img) img.innerHTML = '';
  
  var indicator = document.getElementById('loading-indicator');
  if (indicator) indicator.style.display = 'flex';
  
  updateChips(query);
}}

function injectResults(cardsHtml, relHtml, leoHtml) {{
  var results = document.getElementById('results');
  if (results) results.innerHTML = cardsHtml;
  
  var rel = document.getElementById('rel-container');
  if (rel) rel.innerHTML = relHtml;
  
  var indicator = document.getElementById('loading-indicator');
  if (indicator) indicator.style.display = 'none';
}}

/* ── Related Links injection (called by _on_opal_related_ready) ── */
function injectRelated(html) {{
  var container = document.getElementById('rel-container');
  if (!container) return;
  
  container.style.opacity = '0';
  container.style.transition = 'opacity 0.3s';
  
  setTimeout(function() {{
    container.innerHTML = html;
    container.style.opacity = '1';
  }}, 300);
}}

/* ── Image injection (called by _on_opal_images_ready) ── */
function injectImages(html) {{
  var container = document.getElementById('img-container');
  if (!container) return;
  container.innerHTML = html;
}}

/* ── Video injection (called by _on_opal_videos_ready) ── */
function injectVideos(html) {{
  var container = document.getElementById('vid-container');
  if (!container) return;
  container.innerHTML = html;
}}

var SEEN_URLS = new Set();

// Batch and debounce for addResult (with SEEN_URLS check)
var _result_batch_2 = [];
var _result_debounce_timer_2 = null;

function _flush_result_batch_2() {{
  if (_result_batch_2.length === 0) return;
  for (var i = 0; i < _result_batch_2.length; i++) {{
    var result = _result_batch_2[i];
    if (!result || !result.url) continue;
    var url = result.url.toLowerCase().replace(/\\/$/, '');
    if (SEEN_URLS.has(url)) continue;
    SEEN_URLS.add(url);
    ALL_RESULTS.push(result);
  }}
  _result_batch_2 = [];
  renderResults();
  
  // Hide loading indicator if we have at least one result
  var indicator = document.getElementById('loading-indicator');
  if (indicator && ALL_RESULTS.length > 0) {{
    indicator.style.display = 'none';
  }}
}}

function addResult(result) {{
  _result_batch_2.push(result);
  if (_result_debounce_timer_2) clearTimeout(_result_debounce_timer_2);
  // Flush after 150ms of inactivity or if we have 5 results
  if (_result_batch_2.length >= 5) {{
    _flush_result_batch_2();
  }} else {{
    _result_debounce_timer_2 = setTimeout(_flush_result_batch_2, 150);
  }}
}}

/* ── Discovery chips (Wikipedia-oriented) ────────────────────────── */
updateChips(currentQuery);
</script>
{'<div class="load-timer">🧠 Remembered</div>' if from_cache else ('<div class="load-timer">Loaded in ' + f'{load_time:.2f}s</div>' if load_time is not None else '')}
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: build related links section
# ─────────────────────────────────────────────────────────────────────────────




# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: build card HTML
# ─────────────────────────────────────────────────────────────────────────────

def _build_cards(results: list, q_enc: str) -> str:
    """Render result cards.  Each card optionally shows a right-side thumbnail."""
    if not results:
        return (
            f'<div class="no-res">No results found — '
            f'<a class="web-link" '
            f'href="https://google.com/search?q={q_enc}">'
            f'search Google directly →</a></div>'
        )

    h   = _html_mod.escape   # shorthand
    out = []

    for r in results:
        title       = h(r.get("title",       ""))
        url         = h(r.get("url",         "#"))
        snippet     = h(r.get("snippet",     ""))
        domain      = h(r.get("domain",      ""))
        favicon     = h(r.get("favicon",     ""))
        display_url = h(r.get("display_url", ""))
        thumbnail   = h(r.get("thumbnail",   ""))

        thumb_html = ""
        if thumbnail:
            thumb_html = (
                f'<img class="card-thumb" src="{thumbnail}" '
                f'alt="" loading="lazy" '
                f'onerror="this.style.display=\'none\'">'
            )

        out.append(f"""
<div class="card" onclick="location.href='{url}'">
  <div class="card-inner">
    <div class="card-body">
      <div class="card-meta">
        <img class="fav" src="{favicon}"
             onerror="this.style.visibility='hidden'"
             width="14" height="14" alt="">
        <span class="dom">{domain}</span>
        <span class="durl">{display_url}</span>
      </div>
      <a class="card-title" href="{url}" onclick="event.stopPropagation()">{title}</a>
      <p class="card-snip">{snippet}</p>
      <a class="read-link" href="{url}" onclick="event.stopPropagation()">
        Visit site →
      </a>
    </div>
    {thumb_html}
  </div>
</div>""")

    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: build Leo box
# ─────────────────────────────────────────────────────────────────────────────

def _build_leo_box(leo_summary: str, model: str) -> str:
    """Render the Leo Insight box.

    If leo_summary is "", render a skeleton with "Thinking…" placeholder.
    The JS function injectLeo() will fill it in once phase-2 fires.
    If leo_summary is non-empty, render the full text immediately.
    """
    h = _html_mod.escape

    if leo_summary:
        # Phase-2 already provided — render immediately
        text_html  = h(leo_summary)
        text_class = "leo-text"
        stat_text  = h(f"Leo · {model}")
        dot_html   = ""    # no pulsing dot when content is already there
    else:
        # Phase-1 skeleton — JS will fill this in
        text_html  = """
        <div class="leo-thinking" id="leo-text">
          Analyzing web data streams
          <div class="dot-flashing"></div>
        </div>
        """
        text_class = "" # Remove leo-text class from wrapper to avoid double styling
        stat_text  = h(f"Leo · {model}")
        dot_html   = '<span class="leo-dot"></span>'

    return f"""<div class="leo-box" id="leo-box">
  <div class="leo-hdr">
    <span class="leo-star">✦</span>
    <span class="leo-lbl">Leo Insight</span>
    <div class="leo-stat">
      {dot_html}
      <span id="leo-stat-txt">{stat_text}</span>
    </div>
  </div>
  <div class="{text_class or 'leo-text'}" id="leo-text-container">{text_html}</div>
</div>"""



# ─────────────────────────────────────────────
#  AI SETTINGS DIALOG
# ─────────────────────────────────────────────
class AISettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Leo AI Settings")
        self.setFixedWidth(380)
        from ai_manager import AIManager
        self.ai_manager = AIManager()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24); layout.setSpacing(18)

        # Provider Selection
        provider_layout = QVBoxLayout()
        provider_layout.setSpacing(6)
        provider_label = QLabel("AI Provider")
        provider_label.setObjectName("SettingsSection")
        provider_layout.addWidget(provider_label)
        
        self.provider_combo = QComboBox()
        self.provider_combo.setObjectName("SettingsDropdown")
        self.provider_combo.addItems(self.ai_manager.get_all_providers())
        self.provider_combo.setCurrentText(self.ai_manager.current_provider_name)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)
        layout.addLayout(provider_layout)

        # Dynamic Settings Container
        self.settings_container = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_container)
        self.settings_layout.setContentsMargins(0, 0, 0, 0); self.settings_layout.setSpacing(12)
        layout.addWidget(self.settings_container)

        self._update_settings_fields()

        layout.addStretch()

        # Buttons
        btns = QHBoxLayout()
        btns.setSpacing(10)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("SettingsToggle")
        cancel.clicked.connect(self.reject)
        
        save = QPushButton("Save Settings")
        save.setObjectName("AISendBtn")
        save.clicked.connect(self._save)
        
        btns.addWidget(cancel); btns.addWidget(save)
        layout.addLayout(btns)

        # Subtle dialog style that respects the theme
        self.setStyleSheet("""
            QDialog { background: palette(window); }
            QLabel#SettingsSection { margin-bottom: 2px; }
        """)

    def _on_provider_changed(self):
        self._update_settings_fields()

    def _update_settings_fields(self):
        # Clear existing
        for i in reversed(range(self.settings_layout.count())): 
            item = self.settings_layout.itemAt(i)
            if item.widget(): item.widget().setParent(None)
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget(): child.widget().setParent(None)

        provider_name = self.provider_combo.currentText()
        config = self.ai_manager.get_provider_config(provider_name)

        self.fields = {}
        
        def add_field(label_text, config_key, is_password=False, is_dropdown=False, dropdown_items=None):
            field_layout = QVBoxLayout()
            field_layout.setSpacing(5)
            lbl = QLabel(label_text)
            lbl.setObjectName("SettingsSection")
            field_layout.addWidget(lbl)
            
            if is_dropdown:
                widget = QComboBox()
                widget.setObjectName("SettingsDropdown")
                if dropdown_items:
                    widget.addItems(dropdown_items)
                widget.setCurrentText(config.get(config_key, ""))
                if not dropdown_items: # If empty (e.g. Ollama offline), allow manual entry via editable combo
                    widget.setEditable(True)
            else:
                widget = QLineEdit(config.get(config_key, ""))
                widget.setObjectName("AIInput")
                if is_password:
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
            
            field_layout.addWidget(widget)
            self.settings_layout.addLayout(field_layout)
            self.fields[config_key] = widget

        add_field("API Endpoint URL", "url")
        if provider_name != "Ollama":
            add_field("API Key", "api_key", is_password=True)
            add_field("Model Name", "model")
        else:
            models = self.ai_manager.get_ollama_models()
            add_field("Model Name", "model", is_dropdown=True, dropdown_items=models)

    def _save(self):
        provider_name = self.provider_combo.currentText()
        new_config = {}
        for k, widget in self.fields.items():
            if isinstance(widget, QComboBox):
                new_config[k] = widget.currentText()
            else:
                new_config[k] = widget.text()
        
        self.ai_manager.set_provider(provider_name)
        self.ai_manager.update_provider_config(provider_name, new_config)
        self.accept()


# ─────────────────────────────────────────────
#  AI PANEL
# ─────────────────────────────────────────────
class AIPanel(QWidget):
    def __init__(self, get_page_title_fn, parent=None):
        super().__init__(parent)
        self.get_page_title = get_page_title_fn
        self.worker = None; self._thinking = False; self._build_ui()

    def _build_ui(self):
        self.setObjectName("AIPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12); layout.setSpacing(8)
        header = QHBoxLayout()
        star = QLabel("✦"); star.setObjectName("AIStar")
        title = QLabel("Leo"); title.setObjectName("AITitle")
        header.addWidget(star); header.addWidget(title)
        
        self.ai_info = QLabel("")
        self.ai_info.setObjectName("AIStatusInfo")
        header.addWidget(self.ai_info)
        header.addStretch()
        
        self._update_ai_info()
        
        # Settings Button
        settings_btn = QPushButton("⚙"); settings_btn.setObjectName("AISettingsBtn")
        settings_btn.setFixedSize(24, 24)
        settings_btn.clicked.connect(self._show_settings)
        header.addWidget(settings_btn)
        
        clear_btn = QPushButton("Clear"); clear_btn.setObjectName("AIClearBtn")
        clear_btn.clicked.connect(self._clear); header.addWidget(clear_btn)
        layout.addLayout(header)
        self.chat = QTextEdit(); self.chat.setReadOnly(True)
        self.chat.setObjectName("AIChat")
        self.chat.setPlaceholderText("Ask me anything about this page or the web…")
        layout.addWidget(self.chat, 1)
        quick = QHBoxLayout(); quick.setSpacing(6)
        for label, prompt in [
            ("Summarize", "Summarize the current page content for me briefly."),
            ("Explain",   "Explain the main topic of this page in simple terms."),
            ("Key points","List the 5 most important key points from this page."),
        ]:
            btn = QPushButton(label); btn.setObjectName("QuickBtn")
            btn.clicked.connect(lambda _, p=prompt: self._send(p))
            quick.addWidget(btn)
        layout.addLayout(quick)
        input_row = QHBoxLayout(); input_row.setSpacing(6)
        self.input = QLineEdit(); self.input.setObjectName("AIInput")
        self.input.setPlaceholderText("Ask Leo…")
        self.input.returnPressed.connect(lambda: self._send(self.input.text()))
        input_row.addWidget(self.input)
        send_btn = QPushButton("⟶"); send_btn.setObjectName("AISendBtn")
        send_btn.clicked.connect(lambda: self._send(self.input.text()))
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)
        self.status = QLabel(""); self.status.setObjectName("AIStatus")
        layout.addWidget(self.status)

    def _update_ai_info(self):
        from ai_manager import AIManager
        ai_manager = AIManager()
        provider = ai_manager.current_provider_name
        config = ai_manager.get_provider_config(provider)
        model = config.get("model", "Unknown")
        self.ai_info.setText(f"{provider} • {model}")

    def _show_settings(self):
        dlg = AISettingsDialog(self)
        if dlg.exec():
            self._update_ai_info()

    def _send(self, prompt):
        if not prompt.strip(): return
        self.input.clear()
        page_title = self.get_page_title()
        context = f"The user is browsing: '{page_title}'" if page_title else ""
        self.chat.append(f'<span style="color:#7ecfff;font-weight:600;">You:</span> {prompt}')
        self.chat.append('<span style="color:#a8d8a8;font-weight:600;">Leo:</span> ')
        # Insert thinking indicator inline (45% opacity) so it replaces itself when streaming starts
        _cur = self.chat.textCursor()
        _cur.movePosition(_cur.MoveOperation.End)
        _cur.insertHtml('<span style="color:rgba(200,200,200,0.45);">⟳ Thinking…</span>')
        self.chat.setTextCursor(_cur)
        self.chat.ensureCursorVisible()
        self.status.setText(""); self._ai_response = ""; self._thinking = True
        self.worker = LeoAIWorker(prompt, context)
        self.worker.chunk_ready.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_chunk(self, token):
        self._ai_response += token
        cursor = self.chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if self._thinking:
            # Erase the inline "⟳ Thinking…" before streaming the first token
            cursor.movePosition(cursor.MoveOperation.Left,
                                cursor.MoveMode.KeepAnchor, len("⟳ Thinking…"))
            cursor.removeSelectedText()
            self._thinking = False
        cursor.insertText(token)
        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()

    def _on_done(self):
        from ai_manager import AIManager
        ai_manager = AIManager()
        provider = ai_manager.get_current_provider()
        model = provider.config.get("model", "Unknown Model")
        self.chat.append(""); self.status.setText(f"✓ Done  •  {model} via {provider.get_name()}")

    def _on_error(self, msg):
        if self._thinking:
            _cur = self.chat.textCursor()
            _cur.movePosition(_cur.MoveOperation.End)
            _cur.movePosition(_cur.MoveOperation.Left,
                              _cur.MoveMode.KeepAnchor, len("⟳ Thinking…"))
            _cur.removeSelectedText()
            self._thinking = False
        self.chat.append(f'<span style="color:#ff6b6b;">Error: {msg}</span>')
        self.status.setText("⚠ AI Provider error")

    def _clear(self):
        self.chat.clear(); self.status.setText("")


# ─────────────────────────────────────────────
#  DOWNLOADS — helpers
# ─────────────────────────────────────────────
def _format_size(bytes_val: int) -> str:
    if bytes_val < 0: return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_val < 1024: return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

def _format_speed(bps: float) -> str:
    if bps <= 0: return ""
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bps < 1024: return f"{bps:.1f} {unit}"
        bps /= 1024
    return f"{bps:.1f} GB/s"


class DownloadCard(QFrame):
    def __init__(self, download: QWebEngineDownloadRequest, parent=None):
        super().__init__(parent)
        self.download = download
        self.setObjectName("DownloadCard"); self.setFixedHeight(90)
        self._last_received = 0; self._last_time = 0.0
        self._build_ui(); self._connect_signals()
        self._speed_timer = QTimer(self)
        self._speed_timer.timeout.connect(self._sample_speed)
        if not download.isFinished():
            self._speed_timer.start(800)
        self._last_time = time.monotonic()
        self._last_received = download.receivedBytes()

    def _build_ui(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(12, 10, 12, 10); outer.setSpacing(5)
        top = QHBoxLayout(); top.setSpacing(8)
        self._icon_lbl = QLabel(self._file_icon()); self._icon_lbl.setObjectName("DlIcon")
        self._icon_lbl.setFixedSize(28, 28); self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self._icon_lbl)
        info_col = QVBoxLayout(); info_col.setSpacing(1); info_col.setContentsMargins(0,0,0,0)
        fname = os.path.basename(self.download.downloadFileName())
        self._name_lbl = QLabel(fname); self._name_lbl.setObjectName("DlName")
        self._name_lbl.setMaximumWidth(160); info_col.addWidget(self._name_lbl)
        self._meta_lbl = QLabel("Starting…"); self._meta_lbl.setObjectName("DlMeta")
        info_col.addWidget(self._meta_lbl); top.addLayout(info_col, 1)
        self._pause_btn = QPushButton("⏸"); self._pause_btn.setObjectName("DlPauseBtn")
        self._pause_btn.setFixedSize(28, 28); self._pause_btn.setToolTip("Pause")
        self._pause_btn.clicked.connect(self._toggle_pause); top.addWidget(self._pause_btn)
        self._open_btn = QPushButton("↗"); self._open_btn.setObjectName("DlOpenBtn")
        self._open_btn.setFixedSize(28, 28); self._open_btn.setToolTip("Open file")
        self._open_btn.setEnabled(False); self._open_btn.clicked.connect(self._open_file)
        top.addWidget(self._open_btn)
        self._folder_btn = QPushButton("📁"); self._folder_btn.setObjectName("DlFolderBtn")
        self._folder_btn.setFixedSize(28, 28); self._folder_btn.setToolTip("Show in folder")
        self._folder_btn.clicked.connect(self._show_in_folder); top.addWidget(self._folder_btn)
        outer.addLayout(top)
        self._bar = QProgressBar(); self._bar.setObjectName("DlBar")
        self._bar.setMaximumHeight(5); self._bar.setTextVisible(False); self._bar.setValue(0)
        outer.addWidget(self._bar)

    def _connect_signals(self):
        self.download.receivedBytesChanged.connect(self._on_progress)
        self.download.isFinishedChanged.connect(self._on_finished)
        self.download.isPausedChanged.connect(self._on_paused)

    def _file_icon(self) -> str:
        ext = os.path.splitext(self.download.downloadFileName())[1].lower()
        icons = {
            ".pdf":"📄",".zip":"🗜",".tar":"🗜",".gz":"🗜",".rar":"🗜",
            ".mp4":"🎬",".mkv":"🎬",".avi":"🎬",".mov":"🎬",
            ".mp3":"🎵",".wav":"🎵",".flac":"🎵",
            ".jpg":"🖼",".jpeg":"🖼",".png":"🖼",".gif":"🖼",".webp":"🖼",
            ".exe":"⚙",".dmg":"⚙",".pkg":"⚙",".deb":"⚙",".rpm":"⚙",
            ".py":"🐍",".js":"📜",".html":"🌐",".css":"🎨",
            ".doc":"📝",".docx":"📝",".txt":"📝",
            ".xls":"📊",".xlsx":"📊",".csv":"📊",
        }
        return icons.get(ext, "📦")

    def _on_progress(self):
        received = self.download.receivedBytes(); total = self.download.totalBytes()
        if total > 0:
            self._bar.setMaximum(100); self._bar.setValue(int(received*100/total))
        else:
            self._bar.setMaximum(0)
        size_str = _format_size(received)
        total_str = f" / {_format_size(total)}" if total > 0 else ""
        self._meta_lbl.setText(f"{size_str}{total_str}")

    def _sample_speed(self):
        if self.download.isFinished(): self._speed_timer.stop(); return
        now = time.monotonic(); received = self.download.receivedBytes(); dt = now - self._last_time
        if dt > 0:
            speed = (received - self._last_received) / dt
            self._last_received = received; self._last_time = now
            total = self.download.totalBytes()
            sz = _format_size(received); ts = f" / {_format_size(total)}" if total > 0 else ""
            sp = f"  •  {_format_speed(speed)}" if speed > 0 else ""
            self._meta_lbl.setText(f"{sz}{ts}{sp}")

    def _on_finished(self):
        self._speed_timer.stop(); self._bar.setMaximum(100); self._bar.setValue(100)
        self._pause_btn.setEnabled(False); self._open_btn.setEnabled(True)
        total = self.download.totalBytes(); received = self.download.receivedBytes()
        sz = _format_size(total if total > 0 else received)
        self._meta_lbl.setText(f"Done  •  {sz}")
        self.setObjectName("DownloadCardDone")
        self.style().unpolish(self); self.style().polish(self)

    def _on_paused(self):
        paused = self.download.isPaused()
        self._pause_btn.setText("▶" if paused else "⏸")
        self._pause_btn.setToolTip("Resume" if paused else "Pause")

    def _toggle_pause(self):
        if self.download.isPaused(): self.download.resume()
        else: self.download.pause()

    def _open_file(self):
        path = self.download.downloadDirectory() + "/" + self.download.downloadFileName()
        if sys.platform == "win32": os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])

    def _show_in_folder(self):
        path = self.download.downloadDirectory()
        if sys.platform == "win32": subprocess.Popen(["explorer", path])
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])


class DownloadsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DownloadsPanel")
        self._cards: list[DownloadCard] = []
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)
        header = QHBoxLayout()
        icon = QLabel("⬇"); icon.setObjectName("DlHeaderIcon")
        title = QLabel("Downloads"); title.setObjectName("DlHeaderTitle")
        header.addWidget(icon); header.addWidget(title); header.addStretch()
        self._clear_btn = QPushButton("Clear done"); self._clear_btn.setObjectName("DlClearBtn")
        self._clear_btn.clicked.connect(self._clear_completed); header.addWidget(self._clear_btn)
        layout.addLayout(header)
        div = QFrame(); div.setObjectName("DlDivider"); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); layout.addWidget(div)
        scroll = QScrollArea(); scroll.setObjectName("DlScroll"); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_widget = QWidget(); self._list_widget.setObjectName("DlList")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0,0,0,0); self._list_layout.setSpacing(6)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_widget); layout.addWidget(scroll, 1)
        self._empty_lbl = QLabel("No downloads yet."); self._empty_lbl.setObjectName("DlEmpty")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self._empty_lbl)

    def add_download(self, download: QWebEngineDownloadRequest):
        self._empty_lbl.hide()
        card = DownloadCard(download, self._list_widget)
        self._list_layout.insertWidget(0, card); self._cards.append(card)

    def _clear_completed(self):
        for card in self._cards[:]:
            if card.download.isFinished():
                self._list_layout.removeWidget(card); card.deleteLater(); self._cards.remove(card)
        if not self._cards: self._empty_lbl.show()

    @property
    def active_count(self) -> int:
        return sum(1 for c in self._cards if not c.download.isFinished())


class NotesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DownloadsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)
        header = QHBoxLayout()
        icon = QLabel("📝"); icon.setObjectName("DlHeaderIcon")
        title = QLabel("Notes"); title.setObjectName("DlHeaderTitle")
        header.addWidget(icon); header.addWidget(title); header.addStretch()
        self._add_btn = QPushButton("+ New"); self._add_btn.setObjectName("DlClearBtn")
        self._add_btn.clicked.connect(self._new_note); header.addWidget(self._add_btn)
        layout.addLayout(header)
        div = QFrame(); div.setObjectName("DlDivider"); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); layout.addWidget(div)
        scroll = QScrollArea(); scroll.setObjectName("DlScroll"); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_widget = QWidget(); self._list_widget.setObjectName("DlList")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0,0,0,0); self._list_layout.setSpacing(6)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_widget); layout.addWidget(scroll, 1)
        self._empty_lbl = QLabel("No notes yet."); self._empty_lbl.setObjectName("DlEmpty")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self._empty_lbl)

    def _load(self):
        notes = _load_notes()
        for note in notes:
            self._add_card(note)
        if notes: self._empty_lbl.hide()

    def _new_note(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("New Note")
        dialog.setModal(True)
        dialog.setMinimumSize(400, 320)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title_input = QLineEdit()
        title_input.setObjectName("FindInput")
        title_input.setPlaceholderText("Title")
        layout.addWidget(title_input)

        body_input = QTextEdit()
        body_input.setObjectName("AIChat")
        body_input.setPlaceholderText("Write your note...")
        layout.addWidget(body_input, 1)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("DlOpenBtn")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("DlClearBtn")
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

        save_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        title_input.returnPressed.connect(body_input.setFocus)
        title_input.setFocus()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        import datetime as _dt
        notes = _load_notes()
        notes.append({
            "title": title_input.text().strip() or "Untitled",
            "body": body_input.toPlainText(),
            "date": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        _save_notes(notes)
        self._refresh()

    def _add_card(self, note):
        self._empty_lbl.hide()
        card = QWidget(self._list_widget)
        card.setObjectName("DownloadCard")
        card_layout = QVBoxLayout(card); card_layout.setContentsMargins(10,8,10,8); card_layout.setSpacing(4)
        _note_data = {"title": note.get("title",""), "body": note.get("body",""), "date": note.get("date","")}
        top_row = QHBoxLayout()
        title_lbl = QLabel(_note_data["title"] or "Untitled")
        title_lbl.setObjectName("DlName"); title_lbl.setStyleSheet("font-weight:600")
        top_row.addWidget(title_lbl, 1)
        del_btn = QPushButton("✕"); del_btn.setObjectName("TabClose")
        del_btn.setFixedSize(20, 20); del_btn.setToolTip("Delete note")
        top_row.addWidget(del_btn)
        card_layout.addLayout(top_row)
        
        body_lbl = QLabel(_note_data["body"])
        body_lbl.setObjectName("DlMeta"); body_lbl.setWordWrap(True)
        card_layout.addWidget(body_lbl)
        date_lbl = QLabel(_note_data["date"])
        date_lbl.setObjectName("DlMeta"); date_lbl.setStyleSheet("font-size:10px;color:#6b7a99")
        card_layout.addWidget(date_lbl)
        
        def delete_fn():
            notes = _load_notes()
            notes = [x for x in notes if not (x.get("title","")==_note_data["title"] and x.get("body","")==_note_data["body"] and x.get("date","")==_note_data["date"])]
            _save_notes(notes)
            self._list_layout.removeWidget(card)
            card.deleteLater()
            self._check_empty()
        del_btn.clicked.connect(delete_fn)

        self._list_layout.insertWidget(0, card)

    def _refresh(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._load()

    def _check_empty(self):
        if self._list_layout.count() == 0:
            self._empty_lbl.show()


# ─────────────────────────────────────────────
#  PASSWORD BOOK
# ─────────────────────────────────────────────
_PB_SERVICE  = "NorthStarBrowser"
_PB_META_KEY = "__northstar_vault_meta__"
_PB_HASH_KEY = "__northstar_master_hash__"

try:
    import keyring as _keyring; _KEYRING_OK = True
except ImportError:
    _keyring = None; _KEYRING_OK = False

def _kb_set(key, value):
    if _KEYRING_OK: _keyring.set_password(_PB_SERVICE, key, value)
def _kb_get(key):
    return _keyring.get_password(_PB_SERVICE, key) if _KEYRING_OK else None
def _kb_delete(key):
    if _KEYRING_OK:
        try: _keyring.delete_password(_PB_SERVICE, key)
        except Exception: pass
def _pb_hash(pw): return hashlib.sha256(pw.encode()).hexdigest()
def _pb_load_meta():
    raw = _kb_get(_PB_META_KEY)
    if raw:
        try: return json.loads(raw)
        except: pass
    return []
def _pb_save_meta(meta): _kb_set(_PB_META_KEY, json.dumps(meta))
def _pb_entry_key(eid): return f"__entry_{eid}__"
def _pb_load_entry(eid):
    raw = _kb_get(_pb_entry_key(eid))
    if raw:
        try: return json.loads(raw)
        except: pass
    return None
def _pb_save_entry(entry): _kb_set(_pb_entry_key(entry["id"]), json.dumps(entry))
def _pb_delete_entry(eid): _kb_delete(_pb_entry_key(eid))
def _pb_generate_password(length=18):
    alpha = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        pw = "".join(secrets.choice(alpha) for _ in range(length))
        if (any(c.isupper() for c in pw) and any(c.islower() for c in pw)
                and any(c.isdigit() for c in pw)
                and any(c in "!@#$%^&*()-_=+" for c in pw)):
            return pw


class MasterPasswordDialog(QDialog):
    def __init__(self, mode="unlock", parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.mode = mode; self.result_pw = None; self._build_ui()

    def _build_ui(self):
        self.setFixedWidth(380)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        container = QFrame(); container.setObjectName("PaletteContainer")
        inner = QVBoxLayout(container); inner.setContentsMargins(24,24,24,24); inner.setSpacing(12)
        icon = QLabel("🔑"); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size:24pt;"); inner.addWidget(icon)
        title_text = "Create Master Password" if self.mode == "create" else "Unlock Password Book"
        hint_text  = ("This password protects your vault.\nStore it somewhere safe."
                      if self.mode == "create" else "Enter your master password to continue.")
        title = QLabel(title_text); title.setObjectName("AITitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter); inner.addWidget(title)
        hint = QLabel(hint_text); hint.setObjectName("AIStatus")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter); hint.setWordWrap(True)
        inner.addWidget(hint)
        self._pw_input = QLineEdit(); self._pw_input.setObjectName("AIInput")
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_input.setPlaceholderText("Master password…")
        self._pw_input.returnPressed.connect(self._confirm); inner.addWidget(self._pw_input)
        if self.mode == "create":
            self._pw_confirm = QLineEdit(); self._pw_confirm.setObjectName("AIInput")
            self._pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
            self._pw_confirm.setPlaceholderText("Confirm password…")
            self._pw_confirm.returnPressed.connect(self._confirm); inner.addWidget(self._pw_confirm)
        self._err = QLabel(""); self._err.setObjectName("PbError")
        self._err.setAlignment(Qt.AlignmentFlag.AlignCenter); inner.addWidget(self._err)
        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("ToastNo")
        cancel.clicked.connect(self.reject); btn_row.addWidget(cancel)
        ok = QPushButton("Unlock" if self.mode == "unlock" else "Create")
        ok.setObjectName("ToastYes"); ok.clicked.connect(self._confirm); btn_row.addWidget(ok)
        inner.addLayout(btn_row); outer.addWidget(container)

    def _confirm(self):
        pw = self._pw_input.text()
        if not pw: self._err.setText("Password cannot be empty."); return
        if self.mode == "create":
            if pw != self._pw_confirm.text(): self._err.setText("Passwords don't match."); return
            if len(pw) < 6: self._err.setText("Minimum 6 characters."); return
        self.result_pw = pw; self.accept()

    def show_centered(self, parent_widget):
        x = parent_widget.mapToGlobal(QPoint(
            (parent_widget.width() - self.width()) // 2,
            (parent_widget.height() - 300) // 2,
        ))
        self.move(x); self.show(); self._pw_input.setFocus()


class EntryDialog(QDialog):
    def __init__(self, entry=None, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.entry = entry or {}; self.result = None; self._build_ui()

    def _build_ui(self):
        self.setFixedWidth(400)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        container = QFrame(); container.setObjectName("PaletteContainer")
        inner = QVBoxLayout(container); inner.setContentsMargins(20,20,20,20); inner.setSpacing(10)
        title = QLabel("Edit Entry" if self.entry.get("id") else "New Entry")
        title.setObjectName("AITitle"); inner.addWidget(title)
        def field(ph, default="", echo=QLineEdit.EchoMode.Normal):
            w = QLineEdit(); w.setObjectName("AIInput"); w.setPlaceholderText(ph)
            w.setText(default); w.setEchoMode(echo); inner.addWidget(w); return w
        self._title = field("Site name", self.entry.get("title",""))
        self._url   = field("URL",       self.entry.get("url",""))
        self._user  = field("Username",  self.entry.get("username",""))
        pw_row = QHBoxLayout()
        self._pw = QLineEdit(); self._pw.setObjectName("AIInput"); self._pw.setPlaceholderText("Password")
        self._pw.setText(self.entry.get("password","")); self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw_row.addWidget(self._pw, 1)
        show_btn = QPushButton("👁"); show_btn.setObjectName("DlFolderBtn")
        show_btn.setFixedSize(32,32); show_btn.setCheckable(True)
        show_btn.toggled.connect(lambda on: self._pw.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        pw_row.addWidget(show_btn)
        gen_btn = QPushButton("⚡ Generate"); gen_btn.setObjectName("QuickBtn")
        gen_btn.clicked.connect(lambda: self._pw.setText(_pb_generate_password()))
        pw_row.addWidget(gen_btn); inner.addLayout(pw_row)
        self._notes = QLineEdit(); self._notes.setObjectName("AIInput")
        self._notes.setPlaceholderText("Notes (optional)")
        self._notes.setText(self.entry.get("notes","")); inner.addWidget(self._notes)
        self._err = QLabel(""); self._err.setObjectName("PbError"); inner.addWidget(self._err)
        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("ToastNo")
        cancel.clicked.connect(self.reject); btn_row.addWidget(cancel)
        save = QPushButton("Save"); save.setObjectName("ToastYes")
        save.clicked.connect(self._save); btn_row.addWidget(save)
        inner.addLayout(btn_row); outer.addWidget(container)

    def _save(self):
        title = self._title.text().strip(); url = self._url.text().strip()
        user  = self._user.text().strip(); pw = self._pw.text()
        if not title: self._err.setText("Site name is required."); return
        if not pw:    self._err.setText("Password is required.");   return
        self.result = {
            "id": self.entry.get("id") or secrets.token_hex(8),
            "title": title, "url": url, "username": user,
            "password": pw, "notes": self._notes.text().strip(),
        }; self.accept()

    def show_centered(self, parent_widget):
        x = parent_widget.mapToGlobal(QPoint(
            (parent_widget.width() - self.width()) // 2,
            max(40, (parent_widget.height() - 440) // 2),
        ))
        self.move(x); self.show()


class EntryCard(QFrame):
    copy_user    = pyqtSignal(str)
    copy_pw      = pyqtSignal(str)
    edit_entry   = pyqtSignal(dict)
    delete_entry = pyqtSignal(str)
    autofill     = pyqtSignal(str, str)

    def __init__(self, entry, parent=None):
        super().__init__(parent); self.entry = entry
        self.setObjectName("DownloadCard"); self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self); layout.setContentsMargins(10,8,10,8); layout.setSpacing(8)
        letter = (self.entry.get("title") or "?")[0].upper()
        icon = QLabel(letter); icon.setObjectName("PbEntryIcon")
        icon.setFixedSize(32,32); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        info = QVBoxLayout(); info.setSpacing(1); info.setContentsMargins(0,0,0,0)
        name = QLabel(self.entry.get("title","")); name.setObjectName("DlName"); info.addWidget(name)
        user = self.entry.get("username","")
        meta = QLabel(user or "no username"); meta.setObjectName("DlMeta"); info.addWidget(meta)
        layout.addLayout(info, 1)
        for symbol, tip, fn in [
            ("👤","Copy username", lambda: self.copy_user.emit(self.entry.get("username",""))),
            ("🔑","Copy password", lambda: self.copy_pw.emit(self.entry.get("password",""))),
            ("⬇","Auto-fill page",lambda: self.autofill.emit(
                self.entry.get("username",""), self.entry.get("password",""))),
            ("✏","Edit",          lambda: self.edit_entry.emit(self.entry)),
            ("✕","Delete",        lambda: self.delete_entry.emit(self.entry["id"])),
        ]:
            b = QPushButton(symbol); b.setObjectName("DlFolderBtn")
            b.setFixedSize(26,26); b.setToolTip(tip); b.clicked.connect(fn)
            layout.addWidget(b)


class PasswordBook(QWidget):
    status_message = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("DownloadsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._unlocked = False; self._cards = []
        self._build_ui()
        self._clip_timer = QTimer(self); self._clip_timer.setSingleShot(True)
        self._clip_timer.timeout.connect(self._clear_clipboard)

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)
        hdr = QHBoxLayout()
        icon = QLabel("🔑"); icon.setObjectName("DlHeaderIcon")
        title = QLabel("Password Book"); title.setObjectName("DlHeaderTitle")
        hdr.addWidget(icon); hdr.addWidget(title); hdr.addStretch()
        self._lock_btn = QPushButton("🔒"); self._lock_btn.setObjectName("DlClearBtn")
        self._lock_btn.setToolTip("Lock vault"); self._lock_btn.clicked.connect(self._lock)
        hdr.addWidget(self._lock_btn)
        add_btn = QPushButton("+ Add"); add_btn.setObjectName("DlClearBtn")
        add_btn.clicked.connect(self._add_entry); hdr.addWidget(add_btn)
        layout.addLayout(hdr)
        self._search = QLineEdit(); self._search.setObjectName("AIInput")
        self._search.setPlaceholderText("Search entries…")
        self._search.textChanged.connect(self._filter_entries); layout.addWidget(self._search)
        div = QFrame(); div.setObjectName("DlDivider"); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); layout.addWidget(div)
        scroll = QScrollArea(); scroll.setObjectName("DlScroll"); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_widget = QWidget(); self._list_widget.setObjectName("DlList")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0,0,0,0); self._list_layout.setSpacing(5)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_widget); layout.addWidget(scroll, 1)
        self._overlay = QLabel("🔒  Vault locked.\nClick to unlock.")
        self._overlay.setObjectName("DlEmpty"); self._overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay.setWordWrap(True); layout.addWidget(self._overlay)
        self._status = QLabel(""); self._status.setObjectName("AIStatus"); layout.addWidget(self._status)
        self._set_locked_ui(True)

    def _set_locked_ui(self, locked):
        self._lock_btn.setVisible(not locked); self._search.setVisible(not locked)
        scroll = self._list_widget.parent()
        if scroll: scroll.setVisible(not locked)
        self._overlay.setVisible(locked)
        if locked: self._overlay.setText("🔒  Vault locked.\nClick to unlock.")

    def try_unlock(self, parent_widget):
        stored_hash = _kb_get(_PB_HASH_KEY)
        if stored_hash is None:
            dlg = MasterPasswordDialog("create", parent_widget)
            dlg.show_centered(parent_widget)
            if dlg.exec() and dlg.result_pw:
                _kb_set(_PB_HASH_KEY, _pb_hash(dlg.result_pw))
                self._unlocked = True; self._load_entries(); self._set_locked_ui(False); return True
        else:
            dlg = MasterPasswordDialog("unlock", parent_widget)
            dlg.show_centered(parent_widget)
            if dlg.exec() and dlg.result_pw:
                if _pb_hash(dlg.result_pw) == stored_hash:
                    self._unlocked = True; self._load_entries(); self._set_locked_ui(False); return True
                else:
                    self._overlay.setText("❌  Wrong password.")
        return False

    def _lock(self):
        self._unlocked = False; self._clear_cards(); self._set_locked_ui(True)

    def is_unlocked(self): return self._unlocked

    def _load_entries(self):
        self._clear_cards()
        for m in _pb_load_meta():
            entry = _pb_load_entry(m["id"])
            if entry: self._add_card(entry)

    def _clear_cards(self):
        for c in self._cards:
            self._list_layout.removeWidget(c); c.deleteLater()
        self._cards.clear()

    def _add_card(self, entry):
        card = EntryCard(entry, self._list_widget)
        card.copy_user.connect(lambda u: self._copy_to_clip(u, "Username"))
        card.copy_pw.connect(lambda p: self._copy_to_clip(p, "Password"))
        card.edit_entry.connect(self._edit_entry)
        card.delete_entry.connect(self._delete_entry)
        card.autofill.connect(self.autofill)
        self._list_layout.addWidget(card); self._cards.append(card)

    def _add_entry(self):
        if not self._unlocked: return
        dlg = EntryDialog(parent=self.window()); dlg.show_centered(self.window())
        if dlg.exec() and dlg.result:
            entry = dlg.result; _pb_save_entry(entry)
            meta = _pb_load_meta()
            meta.append({k: entry[k] for k in ("id","title","url","username")})
            _pb_save_meta(meta); self._add_card(entry)
            self.status_message.emit(f"✦ Saved: {entry['title']}", 3000)

    def _edit_entry(self, entry):
        dlg = EntryDialog(entry=entry, parent=self.window()); dlg.show_centered(self.window())
        if dlg.exec() and dlg.result:
            updated = dlg.result; _pb_save_entry(updated)
            meta = _pb_load_meta()
            for m in meta:
                if m["id"] == updated["id"]:
                    m.update({k: updated[k] for k in ("title","url","username")})
            _pb_save_meta(meta); self._load_entries()
            self.status_message.emit(f"✦ Updated: {updated['title']}", 3000)

    def _delete_entry(self, entry_id):
        _pb_delete_entry(entry_id)
        _pb_save_meta([m for m in _pb_load_meta() if m["id"] != entry_id])
        self._load_entries(); self.status_message.emit("Entry deleted.", 2000)

    def _filter_entries(self, text):
        q = text.lower()
        for card in self._cards:
            visible = (not q
                       or q in card.entry.get("title","").lower()
                       or q in card.entry.get("url","").lower()
                       or q in card.entry.get("username","").lower())
            card.setVisible(visible)

    def _copy_to_clip(self, text, label):
        if not text: return
        QApplication.clipboard().setText(text)
        self._status.setText(f"📋 {label} copied — clears in 30s")
        self._clip_timer.start(30_000)

    def _clear_clipboard(self):
        QApplication.clipboard().setText(""); self._status.setText("🧹 Clipboard cleared.")

    def autofill(self, username, password):
        pass   # overridden by direct connection in NorthStar


# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
SETTINGS_FILE = os.path.join(_data_dir(), "northstar_settings.json")
SESSION_FILE = os.path.join(_data_dir(), "northstar_session.json")
SEARCH_ENGINES = {
    "Google":     "https://www.google.com/search?q={}",
    "DuckDuckGo": "https://duckduckgo.com/?q={}",
    "Bing":       "https://www.bing.com/search?q={}",
    "Brave":      "https://search.brave.com/search?q={}",
    "Ecosia":     "https://www.ecosia.org/search?q={}",
}
DEFAULT_SETTINGS = {
    "search_engine":"Google","homepage":"about:blank",
    "dark_mode":True,"restore_tabs":False,"devtools_enabled":True,
    "sidebar_expanded":False,"recent_commands":[],"keep_panels_open":False,
}

def _load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            s = json.load(f)
            for k, v in DEFAULT_SETTINGS.items(): s.setdefault(k, v)
            return s
    except Exception:
        return dict(DEFAULT_SETTINGS)

def _save_settings(s):
    try:
        with open(SETTINGS_FILE, "w") as f: json.dump(s, f, indent=2)
    except Exception: pass


def _resolve_search_url(search_engine_url=None):
    """Return a usable search-URL template.

    Prefers an explicitly supplied template; otherwise falls back to the
    engine currently selected in settings (not a hard-coded Google default).
    This keeps every new-tab render in sync with the Search Engine selector,
    including call sites that navigate to the home page without passing a
    template (Home button, bookmark refresh, etc.).
    """
    if search_engine_url:
        return search_engine_url
    try:
        name = _load_settings().get("search_engine", "Google")
    except Exception:
        name = "Google"
    return SEARCH_ENGINES.get(name, SEARCH_ENGINES["Google"])



def _load_session_tabs():
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            tabs = json.load(f)
        if not isinstance(tabs, list):
            return []
        valid_tabs = []
        for url in tabs[:100]:
            if not isinstance(url, str):
                continue
            scheme = urlparse(url).scheme.lower()
            if url == "northstar://newtab" or scheme in ("http", "https", "file", "ftp"):
                valid_tabs.append(url)
        return valid_tabs
    except FileNotFoundError:
        return []
    except (OSError, ValueError, TypeError) as e:
        _log("SESSION", f"Could not restore saved tabs: {e}")
        return []


def _save_session_tabs(tabs):
    temp_path = SESSION_FILE + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(tabs[:100], f)
        os.replace(temp_path, SESSION_FILE)
    except OSError as e:
        _log("SESSION", f"Could not save open tabs: {e}")


def _clear_saved_session():
    try:
        os.remove(SESSION_FILE)
    except FileNotFoundError:
        pass
    except OSError as e:
        _log("SESSION", f"Could not clear saved tabs: {e}")


# ─────────────────────────────────────────────
#  NOTES
# ─────────────────────────────────────────────
NOTES_FILE = os.path.join(_data_dir(), "northstar_notes.json")

def _load_notes():
    try:
        with open(NOTES_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def _save_notes(notes):
    try:
        with open(NOTES_FILE, "w") as f: json.dump(notes, f, indent=2)
    except Exception: pass

def _build_notes_html(dark_mode=True):
    notes = _load_notes()
    if oled_enabled():
        ot=oled_web_tokens()
        bg=ot["bg"]; surface=ot["surface"]; surface2=ot["surface2"]
        text=ot["text"]; muted=ot["muted"]; accent=ot["accent"]; border=ot["border"]
        input_bg=ot["input_bg"]; card_bg=ot["card_bg"]
    elif dark_mode:
        bg="#080b14"; surface="rgba(255,255,255,0.04)"; surface2="rgba(255,255,255,0.07)"
        text="#dde4f0"; muted="#6b7a99"; accent="#4fc3f7"; border="rgba(100,120,200,0.15)"
        input_bg="rgba(10,12,22,0.8)"; card_bg="rgba(14,16,28,0.9)"
    else:
        bg="#f0f4ff"; surface="rgba(0,0,0,0.03)"; surface2="rgba(0,0,0,0.07)"
        text="#1e1b4b"; muted="#6b7280"; accent="#4f46e5"; border="rgba(80,100,200,0.15)"
        input_bg="rgba(255,255,255,0.8)"; card_bg="rgba(248,250,255,0.9)"
    
    notes_html = ""
    for i, note in enumerate(notes):
        title = _html_mod.escape(note.get("title", "Untitled"))
        body = _html_mod.escape(note.get("body", ""))
        date = _html_mod.escape(note.get("date", ""))
        notes_html += f'''<div class="note-card" id="note-{i}">
        <div class="note-header"><span class="note-title">{title}</span><span class="note-date">{date}</span></div>
        <div class="note-body">{body}</div>
        <div class="note-actions">
        <button class="btn-sm" onclick="editNote({i})">Edit</button>
        <button class="btn-sm btn-danger" onclick="deleteNote({i})">Delete</button>
        </div></div>'''
    
    if not notes:
        notes_html = '<div class="empty">No notes yet. Click "New Note" to create one.</div>'
    
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="color-scheme" content="{"dark" if dark_mode else "light"}">
<title>Notes — NorthStar</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{bg};color:{text};font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.6;padding:24px 32px;overflow-y:auto}}
h1{{font-size:20px;font-weight:700;margin-bottom:4px}}
.subtitle{{color:{muted};font-size:12px;margin-bottom:24px}}
.note-card{{background:{card_bg};border:1px solid {border};border-radius:12px;padding:16px 20px;margin-bottom:12px}}
.note-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.note-title{{font-weight:600;font-size:15px}}
.note-date{{font-size:11px;color:{muted}}}
.note-body{{font-size:13px;color:{text};white-space:pre-wrap;margin-bottom:8px}}
.note-actions{{display:flex;gap:8px}}
.btn-sm{{background:{surface2};color:{text};border:1px solid {border};border-radius:6px;padding:4px 12px;font-size:12px;cursor:pointer}}
.btn-sm:hover{{border-color:{accent}}}
.btn-danger{{color:#f87171}}
.btn-danger:hover{{border-color:#f87171}}
.new-note{{background:{accent};color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer;font-weight:600;margin-bottom:16px}}
.new-note:hover{{opacity:.85}}
.empty{{color:{muted};text-align:center;padding:40px 0}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:999;align-items:center;justify-content:center}}
.modal.show{{display:flex}}
.modal-content{{background:{card_bg};border:1px solid {border};border-radius:12px;padding:20px;width:400px;max-height:80vh;overflow-y:auto}}
.modal-content h3{{margin-bottom:12px;font-size:16px}}
.modal-content input,.modal-content textarea{{width:100%;background:{input_bg};color:{text};border:1px solid {border};border-radius:8px;padding:8px 12px;font-size:13px;margin-bottom:8px;font-family:inherit}}
.modal-content textarea{{min-height:120px;resize:vertical}}
.modal-actions{{display:flex;gap:8px;justify-content:flex-end}}
.status{{position:fixed;bottom:20px;right:20px;background:{accent};color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .3s;z-index:999}}
.status.show{{opacity:1}}
</style></head><body>
<h1>📝 Notes</h1>
<p class="subtitle">Quick notes and ideas</p>
<button class="new-note" onclick="showNewNote()">+ New Note</button>
{notes_html}

<div class="modal" id="modal">
<div class="modal-content">
<h3 id="modal-title">New Note</h3>
<input type="text" id="note-title-input" placeholder="Title">
<textarea id="note-body-input" placeholder="Write your note..."></textarea>
<div class="modal-actions">
<button class="btn-sm" onclick="hideModal()">Cancel</button>
<button class="new-note" onclick="saveNote()">Save</button>
</div></div></div>

<div class="status" id="status"></div>

<script>
var editingIndex = -1;
function showNewNote(){{
  editingIndex = -1;
  document.getElementById('modal-title').textContent = 'New Note';
  document.getElementById('note-title-input').value = '';
  document.getElementById('note-body-input').value = '';
  document.getElementById('modal').classList.add('show');
}}
function editNote(i){{
  editingIndex = i;
  var notes = {json.dumps(notes)};
  document.getElementById('modal-title').textContent = 'Edit Note';
  document.getElementById('note-title-input').value = notes[i].title || '';
  document.getElementById('note-body-input').value = notes[i].body || '';
  document.getElementById('modal').classList.add('show');
}}
function hideModal(){{
  document.getElementById('modal').classList.remove('show');
}}
function saveNote(){{
  var title = document.getElementById('note-title-input').value;
  var body = document.getElementById('note-body-input').value;
  if(!title && !body){{ hideModal(); return; }}
  var action = editingIndex >= 0 ? 'update' : 'add';
  var f=document.createElement('iframe');
  f.style.display='none';
  f.src='northstar://notes/'+action+'?index='+editingIndex+'&title='+encodeURIComponent(title)+'&body='+encodeURIComponent(body);
  document.body.appendChild(f);
  f.onload=function(){{f.remove();location.reload();}};
  f.onerror=function(){{f.remove();location.reload();}};
}}
function deleteNote(i){{
  if(!confirm('Delete this note?')) return;
  var f=document.createElement('iframe');
  f.style.display='none';
  f.src='northstar://notes/delete?index='+i;
  document.body.appendChild(f);
  f.onload=function(){{f.remove();location.reload();}};
  f.onerror=function(){{f.remove();location.reload();}};
}}
</script>
</body></html>'''

def _set_startup_registry(enabled):
    """Add or remove NorthStar from Windows startup via registry."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            exe = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, "NorthStar", 0, winreg.REG_SZ, exe)
        else:
            try:
                winreg.DeleteValue(key, "NorthStar")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass


def _build_settings_html(dark_mode=True):
    fw = get_fernway()
    s = _load_settings()
    se = s.get("search_engine", "Google")
    homepage = s.get("homepage", "about:blank")
    restore = "checked" if s.get("restore_tabs") else ""
    launch = "checked" if s.get("launch_at_startup") else ""
    keep_panels_open = "checked" if s.get("keep_panels_open") else ""
    
    fw_settings = fw.get_all_settings()
    
    if oled_enabled():
        ot=oled_web_tokens()
        bg=ot["bg"]; surface=ot["surface"]; surface2=ot["surface2"]
        text=ot["text"]; muted=ot["muted"]; accent=ot["accent"]
        accent2=ot["accent2"]; border=ot["border"]
        input_bg=ot["input_bg"]; card_bg=ot["card_bg"]
    elif dark_mode:
        bg="#080b14"; surface="rgba(255,255,255,0.04)"; surface2="rgba(255,255,255,0.07)"
        text="#dde4f0"; muted="#6b7a99"; accent=fw_settings.get("accent_primary","#4fc3f7")
        accent2=fw_settings.get("accent_secondary","#9c6ff7"); border="rgba(100,120,200,0.15)"
        input_bg="rgba(10,12,22,0.8)"; card_bg="rgba(14,16,28,0.9)"
    else:
        bg="#f0f4ff"; surface="rgba(0,0,0,0.03)"; surface2="rgba(0,0,0,0.07)"
        text="#1e1b4b"; muted="#6b7280"; accent=fw_settings.get("accent_primary","#4f46e5")
        accent2=fw_settings.get("accent_secondary","#059669"); border="rgba(80,100,200,0.15)"
        input_bg="rgba(255,255,255,0.8)"; card_bg="rgba(248,250,255,0.9)"
    
    se_options = ""
    for name in SEARCH_ENGINES:
        sel = "selected" if name == se else ""
        se_options += f'<option value="{name}" {sel}>{name}</option>'
    
    def slider_row(label, key, min_v, max_v, val, scale=1):
        display = int(val * scale) if scale != 1 else int(val)
        return f'''<div class="row"><label>{label}</label>
        <input type="range" min="{min_v}" max="{max_v}" value="{display}" 
        data-key="{key}" data-scale="{scale}" class="slider" 
        oninput="document.getElementById('val_{key}').textContent=this.value"
        onchange="save('fw',this.dataset.key,this.value/this.dataset.scale)">
        <span id="val_{key}" class="val">{display}</span></div>'''
    
    def toggle_row(label, key, checked=False):
        c = "checked" if checked else ""
        return f'''<div class="row"><label>{label}</label>
        <label class="switch"><input type="checkbox" {c} onchange="save('fw','{key}',this.checked)"><span class="slider-track"></span></label></div>'''
    
    def dropdown_row(label, key, options, current, label_map=None):
        opts = ""
        for o in options:
            sel = "selected" if o == current else ""
            lbl = (label_map or {}).get(o, o.capitalize())
            opts += f'<option value="{o}" {sel}>{lbl}</option>'
        return f'''<div class="row"><label>{label}</label>
        <select onchange="save('fw','{key}',this.value)">{opts}</select></div>'''
    
    def color_row(label, key, color):
        return f'''<div class="row"><label>{label}</label>
        <input type="color" value="{color}" class="color-pick" 
        onchange="save('fw','{key}',this.value)"></div>'''
    
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="color-scheme" content="{"dark" if dark_mode else "light"}">
<title>Settings — NorthStar</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{bg};color:{text};font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.6;padding:24px 32px;overflow-y:auto}}
h1{{font-size:20px;font-weight:700;margin-bottom:4px}}
.subtitle{{color:{muted};font-size:12px;margin-bottom:24px}}
.section{{margin-bottom:28px}}
.section-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:{accent};margin-bottom:10px}}
.card{{background:{card_bg};border:1px solid {border};border-radius:12px;padding:16px 20px;margin-bottom:12px}}
.row{{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid {surface};gap:12px}}
.row:last-child{{border-bottom:none}}
.row label{{font-size:13px;color:{text};flex-shrink:0}}
.row select,.row input[type="text"]{{background:{input_bg};color:{text};border:1px solid {border};border-radius:8px;padding:6px 12px;font-size:13px;min-width:180px}}
.row select:focus,.row input:focus{{border-color:{accent};outline:none}}
.slider{{-webkit-appearance:none;width:140px;height:6px;border-radius:3px;background:{surface2};outline:none}}
.slider::-webkit-slider-thumb{{-webkit-appearance:none;width:16px;height:16px;border-radius:50%;background:{accent};cursor:pointer}}
.val{{font-size:12px;color:{muted};min-width:32px;text-align:right}}
.switch{{position:relative;display:inline-block;width:40px;height:22px}}
.switch input{{opacity:0;width:0;height:0}}
.slider-track{{position:absolute;cursor:pointer;inset:0;background:{surface2};border-radius:11px;transition:.2s}}
.slider-track:before{{content:"";position:absolute;height:16px;width:16px;left:3px;bottom:3px;background:{muted};border-radius:50%;transition:.2s}}
.switch input:checked+.slider-track{{background:{accent};border-color:{accent}}}
.switch input:checked+.slider-track:before{{transform:translateX(18px);background:#fff}}
.color-pick{{width:32px;height:32px;border:2px solid {border};border-radius:8px;cursor:pointer;padding:0}}
.btn{{background:{accent};color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer;font-weight:600}}
.btn:hover{{opacity:.85}}
.btn-outline{{background:transparent;color:{text};border:1px solid {border};border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer}}
.btn-outline:hover{{border-color:{accent}}}
.bookmark-actions{{display:flex;gap:8px;flex-wrap:wrap}}
.bookmark-actions a{{text-decoration:none}}
.preset-row{{display:flex;gap:8px;margin-bottom:12px}}
.preset-btn{{background:{surface};color:{text};border:1px solid {border};border-radius:8px;padding:6px 14px;font-size:12px;cursor:pointer;font-weight:600}}
.preset-btn:hover{{border-color:{accent}}}
.preset-btn.active{{background:{accent};color:#fff;border-color:{accent}}}
.status{{position:fixed;bottom:20px;right:20px;background:{accent};color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .3s;z-index:999}}
.status.show{{opacity:1}}
</style></head><body>
<h1>⚙ Settings</h1>
<p class="subtitle">Browser preferences and appearance</p>

<div class="section">
<div class="section-title">Search</div>
<div class="card">
<div class="row"><label>Search Engine</label>
<select onchange="save('s','search_engine',this.value)">{se_options}</select></div>
<div class="row"><label>Homepage</label>
<input type="text" value="{homepage}" onchange="save('s','homepage',this.value||'about:blank')"></div>
</div></div>

<div class="section">
<div class="section-title">Startup</div>
<div class="card">
<div class="row"><label>Restore tabs on launch</label>
<label class="switch"><input type="checkbox" {restore} onchange="save('s','restore_tabs',this.checked)"><span class="slider-track"></span></label></div>
<div class="row"><label>Launch at startup</label>
<label class="switch"><input type="checkbox" {launch} onchange="save('s','launch_at_startup',this.checked)"><span class="slider-track"></span></label></div>
</div></div>

<div class="section">
<div class="section-title">Bookmarks</div>
<div class="card bookmark-actions">
<a class="btn" href="northstar://import-bookmarks">Import Bookmarks</a>
<a class="btn-outline" href="northstar://clear-bookmarks">Clear Bookmarks</a>
</div></div>

<div class="section">
<div class="section-title">Performance</div>
<div class="card">
<div class="preset-row">
<button class="preset-btn {"active" if fw_settings.get("performance_mode")=="minimal" else ""}" onclick="preset('minimal')">Minimal</button>
<button class="preset-btn {"active" if fw_settings.get("performance_mode")=="balanced" else ""}" onclick="preset('balanced')">Balanced</button>
<button class="preset-btn {"active" if fw_settings.get("performance_mode")=="atmospheric" else ""}" onclick="preset('atmospheric')">Atmospheric</button>
<button class="preset-btn" onclick="preset('default')">Default</button>
</div>
{slider_row("Glow Intensity","glow_intensity",0,100,fw_settings.get("glow_intensity",0.5),100)}
{slider_row("Blur Strength","blur_strength",0,50,fw_settings.get("blur_strength",20))}
{slider_row("Transparency","transparency_level",50,100,fw_settings.get("transparency_level",0.88),100)}
</div></div>

<div class="section">
<div class="section-title">Colors</div>
<div class="card">
{color_row("Primary Accent","accent_primary",fw_settings.get("accent_primary","#4fc3f7"))}
{color_row("Secondary Accent","accent_secondary",fw_settings.get("accent_secondary","#9c6ff7"))}
{color_row("Ambient Tertiary","ambient_tertiary",fw_settings.get("ambient_tertiary","#d18ae8"))}
</div></div>

<div class="section">
<div class="section-title">Motion</div>
<div class="card">
{slider_row("Animation Intensity","animation_intensity",0,150,fw_settings.get("animation_intensity",1.0),100)}
{slider_row("Transition Speed","transition_speed_ms",50,500,fw_settings.get("transition_speed_ms",240))}
{slider_row("Autohide Delay","autohide_delay_ms",50,1500,fw_settings.get("autohide_delay_ms",400))}
{toggle_row("Fade Animations","fade_animations_enabled",fw_settings.get("fade_animations_enabled",True))}
{toggle_row("Hover Effects","hover_animations_enabled",fw_settings.get("hover_animations_enabled",True))}
</div></div>

<div class="section">
<div class="section-title">Layout</div>
<div class="card">
<div class="row"><label>Keep panels open when clicking outside</label>
<label class="switch"><input type="checkbox" {keep_panels_open} onchange="save('s','keep_panels_open',this.checked)"><span class="slider-track"></span></label></div>
{dropdown_row("Tab Style","tab_style",["default","compact","glass"],fw_settings.get("tab_style","default"))}
{dropdown_row("Sidebar Style","sidebar_style",["default","floating","minimal"],fw_settings.get("sidebar_style","default"))}
{toggle_row("Sidebar Auto-hide","sidebar_auto_hide",fw_settings.get("sidebar_auto_hide",True))}
{dropdown_row("Toolbar Mode","toolbar_mode",["address","hover","always"],fw_settings.get("toolbar_mode","address"))}
{dropdown_row("Leo Appearance","leo_appearance",["glass","solid","minimal"],fw_settings.get("leo_appearance","glass"))}
{dropdown_row("Wallpaper Mode","wallpaper_mode",["static","carousel","video"],fw_settings.get("wallpaper_mode","static"),{"static":"Static (Constellations)","carousel":"Wallpaper Carousel","video":"Video Background"})}
{dropdown_row("Background Style","background_style",["classic","current","static","atmospheric"],fw_settings.get("background_style","current"),{"classic":"Classic Constellation","current":"Current Seeded","static":"Static Network","atmospheric":"Atmospheric Sky"})}
</div></div>

<div class="section">
<div class="section-title">OLED</div>
<div class="card">
{toggle_row("OLED Mode","oled_mode",fw_settings.get("oled_mode",False))}
<div class="row"><label style="font-weight:400;font-size:12px;color:{muted}">True blacks + refined gold accents. Pairs with "Video Background" &mdash; the black-hole live wallpaper.</label></div>
</div></div>

<div class="section">
<div class="section-title">Typography</div>
<div class="card">
{dropdown_row("Browser Font","browser_font",["Segoe UI","Arial","Helvetica","Verdana","Tahoma","Consolas","Courier New"],fw_settings.get("browser_font","Segoe UI"))}
</div></div>

<div class="section">
<div class="section-title">Privacy</div>
<div class="card">
<div class="row"><label>Enable DevTools (F12)</label>
<label class="switch"><input type="checkbox" {"checked" if s.get("devtools_enabled", True) else ""} onchange="save('s','devtools_enabled',this.checked)"><span class="slider-track"></span></label></div>
<div class="row"><label>Clear All Permissions</label>
<button class="btn-outline" onclick="clearPerms()">Clear</button></div>
<div class="row"><label>Cached files</label>
<button class="btn-outline" onclick="clearBrowserData('cache')">Clear…</button></div>
<div class="row"><label>Website cookies <small>(signs you out)</small></label>
<button class="btn-outline" onclick="clearBrowserData('cookies')">Clear…</button></div>
<div class="row"><label>Browsing history</label>
<button class="btn-outline" onclick="clearBrowserData('history')">Clear…</button></div>
</div></div>

<div class="status" id="status"></div>

<script>
function save(section, key, value){{
  var f=document.createElement('iframe');
  f.style.display='none';
  f.src='northstar://settings/save?section='+section+'&key='+key+'&value='+encodeURIComponent(value);
  document.body.appendChild(f);
  f.onload=function(){{f.remove();showStatus('Saved');}};
  f.onerror=function(){{f.remove();showStatus('Saved');}};
}}
function preset(mode){{
  var f=document.createElement('iframe');
  f.style.display='none';
  f.src='northstar://settings/preset?mode='+mode;
  document.body.appendChild(f);
  f.onload=function(){{f.remove();location.reload();}};
  f.onerror=function(){{f.remove();location.reload();}};
}}
function clearPerms(){{
  var f=document.createElement('iframe');
  f.style.display='none';
  f.src='northstar://settings/clear-permissions';
  document.body.appendChild(f);
  f.onload=function(){{f.remove();showStatus('Permissions cleared');}};
  f.onerror=function(){{f.remove();showStatus('Permissions cleared');}};
}}
function clearBrowserData(type){{
  var f=document.createElement('iframe');
  f.style.display='none';
  f.src='northstar://settings/clear-data?type='+encodeURIComponent(type);
  document.body.appendChild(f);
  f.onload=function(){{f.remove();}};
  f.onerror=function(){{f.remove();}};
}}
function showStatus(msg){{
  var el=document.getElementById('status');
  el.textContent=msg;el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'),2000);
}}
</script>
</body></html>'''


def _build_extensions_html(extensions: list, dark_mode: bool = True, backend: str = "content-script") -> str:
    fw = get_fernway()
    fw_settings = fw.get_all_settings()
    if oled_enabled():
        ot=oled_web_tokens()
        bg=ot["bg"]; card_bg=ot["card_bg"]; surface=ot["surface"]
        text=ot["text"]; muted=ot["muted"]; border=ot["border"]
        accent=ot["accent"]; accent2=ot["accent2"]
    elif dark_mode:
        bg="#080b14"; card_bg="rgba(14,16,28,0.9)"; surface="rgba(255,255,255,0.04)"
        text="#dde4f0"; muted="#6b7a99"; border="rgba(100,120,200,0.15)"
        accent=fw_settings.get("accent_primary","#4fc3f7")
        accent2=fw_settings.get("accent_secondary","#9c6ff7")
    else:
        bg="#f0f4ff"; card_bg="rgba(248,250,255,0.9)"; surface="rgba(0,0,0,0.03)"
        text="#1e1b4b"; muted="#6b7280"; border="rgba(80,100,200,0.15)"
        accent=fw_settings.get("accent_primary","#4f46e5")
        accent2=fw_settings.get("accent_secondary","#059669")

    cards = ""
    if not extensions:
        if backend == "native":
            cards = f'<div class="card empty">No extensions installed yet. Load a packed .crx/.zip or an unpacked folder, or browse Edge Add-ons for MV3 extensions.</div>'
        else:
            cards = f'<div class="card empty">No extensions installed yet. Click "Load Unpacked…" to load one, or browse Edge Add-ons for content-script ideas.</div>'
    for m in extensions:
        enabled = bool(m.get("enabled", True))
        ext_id = m.get("id", "")
        name = m.get("name", ext_id)
        ver = m.get("version", "?")
        desc = m.get("description", "")
        scripts = len((m.get("content_scripts") or []))
        backend = m.get("backend", "content-script")
        state = "On" if enabled else "Off"
        chk = "checked" if enabled else ""
        if backend == "native":
            meta_line = f"MV3 (native) · currently {state}"
        else:
            meta_line = f"{scripts} content script(s) · currently {state}"
        cards += f'''<div class="card ext">
        <div class="ext-head">
          <div class="ext-icon">🧩</div>
          <div class="ext-info">
            <div class="ext-name">{name} <span class="ext-ver">v{ver}</span></div>
            <div class="ext-desc">{desc or "No description."}</div>
            <div class="ext-meta">{meta_line}</div>
          </div>
          <div class="ext-actions">
            <label class="switch" title="Enable / disable">
              <input type="checkbox" {chk} onchange="setEnabled('{ext_id}',this.checked)">
              <span class="slider-track"></span>
            </label>
            <button class="danger" onclick="removeExt('{ext_id}')">Remove</button>
          </div>
        </div>
      </div>'''

    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="color-scheme" content="{"dark" if dark_mode else "light"}">
<title>Extensions — NorthStar</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{bg};color:{text};font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.6;padding:24px 32px;overflow-y:auto}}
h1{{font-size:20px;font-weight:700;margin-bottom:4px}}
.subtitle{{color:{muted};font-size:12px;margin-bottom:24px}}
.toolbar{{display:flex;gap:10px;margin-bottom:20px}}
button{{border:none;border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;font-weight:600}}
.primary{{background:{accent};color:#fff}}
.danger{{background:rgba(239,68,68,0.15);color:#f87171}}
.card{{background:{card_bg};border:1px solid {border};border-radius:12px;padding:16px 20px;margin-bottom:12px}}
.empty{{color:{muted};text-align:center;padding:36px}}
.ext-head{{display:flex;align-items:center;gap:14px}}
.ext-icon{{font-size:26px}}
.ext-info{{flex:1;min-width:0}}
.ext-name{{font-size:15px;font-weight:700}}
.ext-ver{{color:{muted};font-size:12px;font-weight:500}}
.ext-desc{{color:{muted};font-size:13px;margin:2px 0 4px}}
.ext-meta{{color:{accent};font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
.ext-actions{{display:flex;align-items:center;gap:10px;flex-shrink:0}}
.switch{{position:relative;width:42px;height:24px;flex-shrink:0}}
.switch input{{opacity:0;width:0;height:0}}
.slider-track{{position:absolute;cursor:pointer;inset:0;background:{surface};border-radius:24px;transition:.2s}}
.slider-track:before{{content:"";position:absolute;height:18px;width:18px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.2s}}
.switch input:checked + .slider-track{{background:{accent2}}}
.switch input:checked + .slider-track:before{{transform:translateX(18px)}}
</style>
</head>
<body>
<h1>Extensions</h1>
<div class="subtitle">{"Install and manage MV3 extensions (native engine)." if backend == "native" else "Install and manage NorthStar content-script extensions."}</div>
<div class="toolbar">
  <button class="primary" onclick="installExt()">{"Install .crx / .zip…" if backend == "native" else "Load Unpacked…"}</button>
  <button onclick="browseStore()">Browse Edge Add-ons</button>
</div>
{cards}
<div id="status"></div>
<script>
function post(route){{
  var f=document.createElement('iframe');
  f.style.display='none';
  f.src=route;
  document.body.appendChild(f);
  f.onload=function(){{f.remove();location.reload();}};
  f.onerror=function(){{f.remove();location.reload();}};
}}
function installExt(){{ post('northstar://extensions/install'); }}
function browseStore(){{ post('northstar://extensions/browse'); }}
function setEnabled(id,on){{ post('northstar://extensions/enable?id='+encodeURIComponent(id)+'&on='+on); }}
function removeExt(id){{ if(!confirm('Remove this extension?')) return; post('northstar://extensions/remove?id='+encodeURIComponent(id)); }}
</script>
</body></html>'''


class SettingsPanel(QWidget):
    changed = pyqtSignal(dict)

    def __init__(self, settings, parent=None):
        super().__init__(parent); self.setObjectName("DownloadsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._s = dict(settings); self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(16,14,16,14); layout.setSpacing(12)
        hdr = QHBoxLayout()
        icon = QLabel("⚙"); icon.setObjectName("DlHeaderIcon")
        title = QLabel("Settings"); title.setObjectName("DlHeaderTitle")
        hdr.addWidget(icon); hdr.addWidget(title); hdr.addStretch(); layout.addLayout(hdr)
        div = QFrame(); div.setObjectName("DlDivider"); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); layout.addWidget(div)
        scroll = QScrollArea(); scroll.setObjectName("DlScroll"); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(); inner.setObjectName("DlList")
        form = QVBoxLayout(inner); form.setContentsMargins(0,4,0,4); form.setSpacing(14)
        def section(label):
            lbl = QLabel(label); lbl.setObjectName("SettingsSection"); form.addWidget(lbl)
        def row(label, widget):
            r = QHBoxLayout()
            lbl = QLabel(label); lbl.setObjectName("SettingsLabel"); r.addWidget(lbl,1); r.addWidget(widget)
            form.addLayout(r)
        section("Search")
        self._se_combo = QPushButton(
            self._s.get("search_engine", "Google")
        ); self._se_combo.setObjectName("SettingsDropdown")
        self._se_combo.setFixedWidth(140)
        se_menu = QMenu(self._se_combo)
        for name in SEARCH_ENGINES: se_menu.addAction(name, lambda n=name: self._set_search(n))
        self._se_combo.setMenu(se_menu); row("Search engine", self._se_combo)
        section("Startup")
        self._home_input = QLineEdit(self._s["homepage"]); self._home_input.setObjectName("AIInput")
        self._home_input.setFixedWidth(200)
        self._home_input.editingFinished.connect(
            lambda: self._set("homepage", self._home_input.text().strip() or "about:blank"))
        row("Homepage URL", self._home_input)
        self._toggle_row(form, "Restore tabs on launch", "restore_tabs")
        self._toggle_row(form, "Launch at startup", "launch_at_startup")
        self._toggle_row(form, "Keep panels open when clicking outside", "keep_panels_open")
        section("Privacy")
        privacy_note = QLabel("Clear locally stored browser data. Clearing cookies may sign you out of websites.")
        privacy_note.setObjectName("SettingsHint")
        privacy_note.setWordWrap(True)
        form.addWidget(privacy_note)
        clear_cache_btn = QPushButton("Clear cache…")
        clear_cache_btn.setObjectName("SettingsAction")
        clear_cache_btn.setAccessibleName("Clear cached files")
        clear_cache_btn.clicked.connect(lambda: self._request_privacy_action("cache"))
        row("Cached files", clear_cache_btn)
        clear_cookies_btn = QPushButton("Clear cookies…")
        clear_cookies_btn.setObjectName("SettingsAction")
        clear_cookies_btn.setAccessibleName("Clear website cookies")
        clear_cookies_btn.clicked.connect(lambda: self._request_privacy_action("cookies"))
        row("Website cookies", clear_cookies_btn)
        clear_history_btn = QPushButton("Clear history…")
        clear_history_btn.setObjectName("SettingsAction")
        clear_history_btn.setAccessibleName("Clear browsing history")
        clear_history_btn.clicked.connect(lambda: self._request_privacy_action("history"))
        row("Browsing history", clear_history_btn)
        form.addStretch(); scroll.setWidget(inner); layout.addWidget(scroll, 1)

    def _request_privacy_action(self, action):
        window = self.window()
        handler = getattr(window, "_clear_browser_data", None)
        if callable(handler):
            handler(action)

    def _toggle_row(self, parent_layout, label, key):
        btn = QPushButton("On" if self._s.get(key) else "Off")
        btn.setObjectName("SettingsToggle"); btn.setFixedWidth(56)
        btn.setCheckable(True); btn.setChecked(bool(self._s.get(key)))
        btn.toggled.connect(lambda on, k=key, b=btn: (b.setText("On" if on else "Off"), self._set(k, on)))
        r = QHBoxLayout(); lbl = QLabel(label); lbl.setObjectName("SettingsLabel")
        r.addWidget(lbl,1); r.addWidget(btn); parent_layout.addLayout(r); return btn

    def _set(self, key, value):
        self._s[key] = value; _save_settings(self._s); self.changed.emit(dict(self._s))

    def _set_search(self, name): self._se_combo.setText(name); self._set("search_engine", name)
    def update_settings(self, s):
        self._s = dict(s)
        self._se_combo.setText(self._s.get("search_engine", "Google"))


class FernwayPanel(QWidget):
    """Atmospheric customization panel for Fernway."""
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.setObjectName("DownloadsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.fw = manager
        self._controls = {} # Store refs to update them on presets
        self._build_ui()
        
        # Connect to manager to update UI if settings change from presets
        self.fw.setting_changed.connect(self._on_setting_changed)

    def _on_setting_changed(self, key, value):
        if key in self._controls:
            ctrl = self._controls[key]
            if isinstance(ctrl, QSlider):
                # Scale back for slider
                scale = 100 if key in ["glow_intensity", "transparency_level", "animation_intensity"] else 1
                ctrl.blockSignals(True)
                ctrl.setValue(int(value * scale))
                ctrl.blockSignals(False)
                # Update label if it exists
                if hasattr(ctrl, "_val_lbl"):
                    ctrl._val_lbl.setText(f"{value:.2f}" if scale > 1 else str(int(value)))
            elif isinstance(ctrl, QPushButton) and key.endswith("_primary") or key.endswith("_secondary") or key.endswith("tertiary"):
                ctrl.setStyleSheet(f"background-color: {value};")
            elif isinstance(ctrl, QPushButton):
                # Handle dropdowns
                if key == "wallpaper_mode":
                    wp_mode_label_map = {
                        "static": "Static (Constellations)",
                        "carousel": "Wallpaper Carousel",
                        "video": "Video Background",
                    }
                    ctrl.setText(wp_mode_label_map.get(value, value.capitalize()))
                elif "style" in key or "appearance" in key:
                    ctrl.setText(str(value).capitalize())

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(16,14,16,14); layout.setSpacing(12)
        
        # Header
        hdr = QHBoxLayout()
        icon = QLabel("✦"); icon.setObjectName("DlHeaderIcon")
        title = QLabel("Fernway Atmosphere"); title.setObjectName("DlHeaderTitle")
        hdr.addWidget(icon); hdr.addWidget(title); hdr.addStretch(); layout.addLayout(hdr)
        
        div = QFrame(); div.setObjectName("DlDivider"); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); layout.addWidget(div)
        
        scroll = QScrollArea(); scroll.setObjectName("DlScroll"); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        inner = QWidget(); inner.setObjectName("DlList")
        form = QVBoxLayout(inner); form.setContentsMargins(0,4,0,4); form.setSpacing(18)
        
        def section(label):
            lbl = QLabel(label); lbl.setObjectName("SettingsSection"); form.addWidget(lbl)
            
        def row(label, widget):
            r = QHBoxLayout()
            lbl = QLabel(label); lbl.setObjectName("SettingsLabel"); r.addWidget(lbl, 1); r.addWidget(widget)
            form.addLayout(r)

        # ── Performance Modes ────────────────────────
        section("Performance")
        modes_layout = QHBoxLayout()
        for mode in ["Minimal", "Balanced", "Atmospheric"]:
            btn = QPushButton(mode); btn.setObjectName("FernwayModeBtn")
            btn.clicked.connect(lambda _, m=mode.lower(): self.fw.set_performance_mode(m))
            modes_layout.addWidget(btn)
        
        # Add "Default" button to reset everything
        default_btn = QPushButton("Default"); default_btn.setObjectName("FernwayModeBtn")
        default_btn.clicked.connect(self.fw.reset_to_defaults)
        modes_layout.addWidget(default_btn)
        
        form.addLayout(modes_layout)

        # ── Atmosphere ──────────────────────────────
        section("Atmosphere")
        
        # Wallpaper Mode Selector
        wp_mode_label_map = {
            "static": "Static (Constellations)",
            "carousel": "Wallpaper Carousel",
            "video": "Video Background",
        }
        self._add_dropdown(form, "Wallpaper Mode", "wallpaper_mode", ["static", "carousel", "video"], wp_mode_label_map)
        
        # Background Style Selector
        bg_label_map = {
            "classic": "Classic Constellation",
            "current": "Current Seeded",
            "static": "Static Network",
            "atmospheric": "Atmospheric Sky"
        }
        self._add_dropdown(form, "Background Style", "background_style", ["classic", "current", "static", "atmospheric"], bg_label_map)
        
        self._add_slider(form, "Glow Intensity", "glow_intensity", 0, 100, 100)
        self._add_slider(form, "Blur Strength", "blur_strength", 0, 50, 1)
        self._add_slider(form, "Transparency", "transparency_level", 50, 100, 100)

        # OLED Mode
        oled_btn = QPushButton("On" if self.fw.get("oled_mode") else "Off")
        oled_btn.setObjectName("SettingsToggle"); oled_btn.setFixedWidth(56); oled_btn.setCheckable(True)
        oled_btn.setChecked(bool(self.fw.get("oled_mode")))
        oled_btn.toggled.connect(lambda on: (oled_btn.setText("On" if on else "Off"), self.fw.set("oled_mode", on)))
        row("OLED Mode", oled_btn)

        # ── Colors ──────────────────────────────────
        section("Colors")
        self._add_color_row(form, "Primary Accent", "accent_primary")
        self._add_color_row(form, "Secondary Accent", "accent_secondary")
        self._add_color_row(form, "Ambient Tertiary", "ambient_tertiary")

        # ── Motion ──────────────────────────────────
        section("Motion")
        self._add_slider(form, "Animation Intensity", "animation_intensity", 0, 150, 100)
        self._add_slider(form, "Transition Speed", "transition_speed_ms", 50, 500, 1)
        self._add_slider(form, "Autohide Delay", "autohide_delay_ms", 50, 1500, 1)
        
        fade_btn = QPushButton("On" if self.fw.get("fade_animations_enabled") else "Off")
        fade_btn.setObjectName("SettingsToggle"); fade_btn.setFixedWidth(56); fade_btn.setCheckable(True)
        fade_btn.setChecked(self.fw.get("fade_animations_enabled"))
        fade_btn.toggled.connect(lambda on: (fade_btn.setText("On" if on else "Off"), self.fw.set("fade_animations_enabled", on)))
        row("Fade Animations", fade_btn)

        hover_btn = QPushButton("On" if self.fw.get("hover_animations_enabled") else "Off")
        hover_btn.setObjectName("SettingsToggle"); hover_btn.setFixedWidth(56); hover_btn.setCheckable(True)
        hover_btn.setChecked(self.fw.get("hover_animations_enabled"))
        hover_btn.toggled.connect(lambda on: (hover_btn.setText("On" if on else "Off"), self.fw.set("hover_animations_enabled", on)))
        row("Hover Effects", hover_btn)

        # ── Layout ──────────────────────────────────
        section("Layout")
        self._add_dropdown(form, "Tab Style", "tab_style", ["default", "compact", "glass"])
        self._add_dropdown(form, "Sidebar Style", "sidebar_style", ["default", "floating", "minimal"])
        
        # Sidebar Auto-hide toggle
        sh_val = bool(self.fw.get("sidebar_auto_hide", True))
        sh_btn = QPushButton("On" if sh_val else "Off")
        sh_btn.setObjectName("SettingsToggle"); sh_btn.setFixedWidth(56); sh_btn.setCheckable(True)
        sh_btn.setChecked(sh_val)
        sh_btn.toggled.connect(lambda on: (sh_btn.setText("On" if on else "Off"), self.fw.set("sidebar_auto_hide", on)))
        row("Sidebar Auto-hide", sh_btn)

        # Toolbar Mode switcher
        self._add_dropdown(form, "Toolbar Mode", "toolbar_mode", ["address", "hover", "always"])

        self._add_dropdown(form, "Leo Appearance", "leo_appearance", ["glass", "solid", "minimal"])

        # ── Typography ──────────────────────────────
        section("Typography")
        fonts = ["Segoe UI", "Segoe UI Variable", "Arial", "Helvetica", "Calibri", "Consolas", "Cascadia Code", "Fira Code", "JetBrains Mono", "Inter", "Roboto", "Ubuntu"]
        font_map = {f: f for f in fonts}
        self._add_dropdown(form, "Browser Font", "browser_font", fonts, font_map)

        # ── Privacy ──────────────────────────────────
        section("Privacy")
        clear_perm_btn = QPushButton("Clear All Permissions")
        clear_perm_btn.setObjectName("SettingsToggle"); clear_perm_btn.setFixedWidth(160)
        clear_perm_btn.clicked.connect(lambda: (_perm_manager.clear_all(), clear_perm_btn.setText("Cleared ✓")))
        row("Site Permissions", clear_perm_btn)

        form.addStretch()
        scroll.setWidget(inner); layout.addWidget(scroll, 1)

    def _add_slider(self, layout, label, key, min_val, max_val, scale):
        r = QVBoxLayout()
        r.setSpacing(4)
        lbl_row = QHBoxLayout()
        lbl = QLabel(label); lbl.setObjectName("SettingsLabel")
        val_lbl = QLabel(f"{self.fw.get(key):.2f}" if scale > 1 else str(int(self.fw.get(key))))
        val_lbl.setObjectName("AIStatusInfo")
        lbl_row.addWidget(lbl); lbl_row.addStretch(); lbl_row.addWidget(val_lbl)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName("FernwaySlider")
        slider.setRange(min_val, max_val)
        slider.setValue(int(self.fw.get(key) * scale))
        slider._val_lbl = val_lbl # Store ref for updates
        self._controls[key] = slider
        
        slider.valueChanged.connect(lambda v: (self.fw.set(key, int(v / scale) if scale == 1 else v / scale), val_lbl.setText(f"{v / scale:.2f}" if scale > 1 else str(v))))
        
        r.addLayout(lbl_row); r.addWidget(slider)
        layout.addLayout(r)

    def _add_color_row(self, layout, label, key):
        r = QHBoxLayout()
        lbl = QLabel(label); lbl.setObjectName("SettingsLabel")
        
        btn = QPushButton()
        btn.setObjectName("FernwayColorBtn")
        btn.setFixedSize(24, 24)
        color = self.fw.get(key)
        btn.setStyleSheet(f"background-color: {color};")
        self._controls[key] = btn
        
        def pick_color():
            c = QColorDialog.getColor(QColor(self.fw.get(key)), self)
            if c.isValid():
                hex_color = c.name()
                self.fw.set(key, hex_color)
                btn.setStyleSheet(f"background-color: {hex_color};")

        btn.clicked.connect(pick_color)
        r.addWidget(lbl, 1); r.addWidget(btn)
        layout.addLayout(r)

    def _add_dropdown(self, layout, label, key, options, label_map=None):
        r = QHBoxLayout()
        lbl = QLabel(label); lbl.setObjectName("SettingsLabel")
        
        # Default custom labels for toolbar mode
        default_label_map = {
            "address": "Address Bar",
            "hover": "Hover",
            "always": "Always"
        }
        
        # Use provided label map if available, else default
        label_map = label_map or default_label_map
        
        current_val = self.fw.get(key)
        if current_val is None:
            btn_text = label_map.get(None, "None")
        else:
            btn_text = label_map.get(current_val, current_val.capitalize())
        btn = QPushButton(btn_text)
        btn.setObjectName("SettingsDropdown"); btn.setFixedWidth(180)
        self._controls[key] = btn
        menu = QMenu(btn)
        
        for opt in options:
            if opt is None:
                display_text = label_map.get(opt, "None")
            else:
                display_text = label_map.get(opt, opt.capitalize())
            menu.addAction(display_text, lambda o=opt, d=display_text: (btn.setText(d), self.fw.set(key, o)))
        btn.setMenu(menu)
        r.addWidget(lbl, 1); r.addWidget(btn)
        layout.addLayout(r)


# ─────────────────────────────────────────────
#  HISTORY PANEL — OPTIMISED (virtualised render)
# ─────────────────────────────────────────────
HISTORY_FILE = os.path.join(_data_dir(), "northstar_history.json")
_MAX_HISTORY = 2000
_HISTORY_RENDER_LIMIT = 100   # OPT: cap rendered rows for performance


def _load_history():
    try:
        with open(HISTORY_FILE) as f: return json.load(f)
    except Exception: return []

def _save_history(entries):
    try:
        with open(HISTORY_FILE, "w") as f: json.dump(entries[-_MAX_HISTORY:], f)
    except Exception: pass


class HistoryPanel(QWidget):
    navigate = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("DownloadsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._entries = _load_history(); self._dirty = False
        self._visible_limit = _HISTORY_RENDER_LIMIT
        self._save_timer = QTimer(self); self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(5000); self._save_timer.timeout.connect(self._flush)
        self._build_ui()

    def _flush(self):
        if self._dirty:   # OPT: skip if nothing changed
            _save_history(self._entries); self._dirty = False

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)
        hdr = QHBoxLayout()
        icon = QLabel("🕐"); icon.setObjectName("DlHeaderIcon")
        title = QLabel("History"); title.setObjectName("DlHeaderTitle")
        hdr.addWidget(icon); hdr.addWidget(title); hdr.addStretch()
        clear_btn = QPushButton("Clear all"); clear_btn.setObjectName("DlClearBtn")
        clear_btn.clicked.connect(self._clear_all); hdr.addWidget(clear_btn); layout.addLayout(hdr)
        self._search = QLineEdit(); self._search.setObjectName("AIInput")
        self._search.setPlaceholderText("Search history…")
        self._search.setAccessibleName("Search browsing history")
        # OPT: debounce search renders
        self._search_timer = QTimer(self); self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(120); self._search_timer.timeout.connect(self._render)
        self._search.textChanged.connect(lambda _: self._search_timer.start())
        layout.addWidget(self._search)
        self._range = QComboBox()
        self._range.setObjectName("HistoryRange")
        self._range.setAccessibleName("Filter history by date")
        self._range.addItem("All time", 0)
        self._range.addItem("Today", 1)
        self._range.addItem("Last 7 days", 7)
        self._range.addItem("Last 30 days", 30)
        self._range.currentIndexChanged.connect(lambda _: self._render())
        layout.addWidget(self._range)
        div = QFrame(); div.setObjectName("DlDivider"); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); layout.addWidget(div)
        scroll = QScrollArea(); scroll.setObjectName("DlScroll"); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_w = QWidget(); self._list_w.setObjectName("DlList")
        self._list_l = QVBoxLayout(self._list_w); self._list_l.setContentsMargins(0,0,0,0)
        self._list_l.setSpacing(2); self._list_l.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_w); layout.addWidget(scroll, 1)
        self._load_more = QPushButton("Load more")
        self._load_more.setObjectName("DlClearBtn")
        self._load_more.setAccessibleName("Load more history entries")
        self._load_more.clicked.connect(self._show_more)
        layout.addWidget(self._load_more)
        self._empty = QLabel("No history yet."); self._empty.setObjectName("DlEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self._empty)
        self._render()

    def add_entry(self, url, title):
        if not url.startswith("http"): return
        now = int(time.time())
        if self._entries and self._entries[-1].get("url") == url:
            self._entries[-1]["title"] = title or url; self._entries[-1]["ts"] = now
        else:
            self._entries.append({"url": url, "title": title or url, "ts": now})
        self._dirty = True
        if not self._save_timer.isActive(): self._save_timer.start()
        if self.isVisible(): self._render()

    def _render(self):
        q = self._search.text().lower()
        range_days = self._range.currentData()
        today = datetime.date.today()
        filtered = []
        for entry in reversed(self._entries):
            if q and q not in entry.get("url", "").lower() and q not in entry.get("title", "").lower():
                continue
            if range_days:
                entry_date = datetime.datetime.fromtimestamp(entry["ts"]).date()
                if range_days == 1 and entry_date != today:
                    continue
                if range_days > 1 and entry_date < today - datetime.timedelta(days=range_days - 1):
                    continue
            filtered.append(entry)

        # OPT: disable updates during bulk widget operations to prevent flicker/lag
        self._list_w.setUpdatesEnabled(False)
        try:
            # OPT: clear by reparenting layout rather than per-widget deleteLater
            while self._list_l.count():
                item = self._list_l.takeAt(0)
                if item.widget(): item.widget().deleteLater()

            self._empty.setText("No history yet." if not self._entries else "No matching history.")
            self._empty.setVisible(not filtered)
            prev_date = None

            # OPT: cap at _HISTORY_RENDER_LIMIT to avoid lag with large histories
            visible = filtered[:self._visible_limit]
            self._load_more.setVisible(len(filtered) > len(visible))
            for entry in visible:
                dt = datetime.datetime.fromtimestamp(entry["ts"])
                try: date_str = dt.strftime("%A, %B %#d") if sys.platform=="win32" else dt.strftime("%A, %B %-d")
                except ValueError: date_str = dt.strftime("%A, %B %d")
                if date_str != prev_date:
                    sep = QLabel(date_str); sep.setObjectName("HistoryDateSep")
                    self._list_l.addWidget(sep); prev_date = date_str
                self._list_l.addWidget(self._make_row(entry))
        finally:
            self._list_w.setUpdatesEnabled(True)

    def _show_more(self):
        self._visible_limit += _HISTORY_RENDER_LIMIT
        self._render()

    def _make_row(self, entry):
        frame = QFrame(); frame.setObjectName("HistoryRow")
        h = QHBoxLayout(frame); h.setContentsMargins(8,4,8,4); h.setSpacing(8)
        info = QVBoxLayout(); info.setSpacing(0)
        title_lbl = QLabel(entry.get("title","")[:60] or entry["url"])
        title_lbl.setObjectName("DlName")
        url_lbl = QLabel(entry["url"][:70]); url_lbl.setObjectName("DlMeta")
        info.addWidget(title_lbl); info.addWidget(url_lbl); h.addLayout(info, 1)
        dt = datetime.datetime.fromtimestamp(entry["ts"])
        time_lbl = QLabel(dt.strftime("%H:%M")); time_lbl.setObjectName("HistoryTime")
        h.addWidget(time_lbl)
        frame.mousePressEvent = lambda e, u=entry["url"]: self.navigate.emit(u)
        frame.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        return frame

    def _clear_all(self):
        self._entries.clear(); self._dirty = False
        self._save_timer.stop(); _save_history(self._entries); self._render()

    def reload_from_disk(self):
        self._entries = _load_history(); self._render()


# ─────────────────────────────────────────────
#  FIND BAR
# ─────────────────────────────────────────────
class FindBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("FindBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(40); self.hide(); self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self); layout.setContentsMargins(10,4,10,4); layout.setSpacing(6)
        self._input = QLineEdit(); self._input.setObjectName("FindInput")
        self._input.setPlaceholderText("Find in page…"); self._input.setFixedWidth(220)
        self._input.textChanged.connect(self._search); self._input.returnPressed.connect(self._next)
        layout.addWidget(self._input)
        self._count_lbl = QLabel(""); self._count_lbl.setObjectName("FindCount")
        self._count_lbl.setFixedWidth(70); layout.addWidget(self._count_lbl)
        for symbol, tip, fn in [("↑","Previous",self._prev),("↓","Next",self._next)]:
            b = QPushButton(symbol); b.setObjectName("FindNavBtn"); b.setFixedSize(28,28)
            b.setToolTip(tip); b.setAccessibleName(tip); b.clicked.connect(fn); layout.addWidget(b)
        layout.addStretch()
        close_btn = QPushButton("✕"); close_btn.setObjectName("FindNavBtn"); close_btn.setFixedSize(28,28)
        close_btn.setToolTip("Close (Escape)"); close_btn.clicked.connect(self.close_bar)
        close_btn.setAccessibleName("Close find bar")
        layout.addWidget(close_btn)

    def open_bar(self, view):
        self._view = view; self.show(); self._input.setFocus()
        self._input.selectAll(); self._reposition()

    def close_bar(self):
        if hasattr(self,'_view') and self._view: self._view.findText("")
        self.hide()

    def _reposition(self):
        if not self.parent(): return
        pw = self.parent().width(); ph = self.parent().height()
        w = min(500, pw - 40); self.setFixedWidth(w)
        self.move((pw-w)//2, ph - self.height() - 4)

    def _search(self, text):
        if not hasattr(self,'_view') or not self._view: return
        self._view.findText(text); self._count_lbl.setText("")

    def _next(self):
        if not hasattr(self,'_view') or not self._view: return
        self._view.findText(self._input.text())

    def _prev(self):
        if not hasattr(self,'_view') or not self._view: return
        self._view.findText(self._input.text(), QWebEnginePage.FindFlag.FindBackward)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape: self.close_bar()
        elif e.key() == Qt.Key.Key_Return and e.modifiers() & Qt.KeyboardModifier.ShiftModifier: self._prev()
        else: super().keyPressEvent(e)


# ─────────────────────────────────────────────
#  STARSHARE™
# ─────────────────────────────────────────────
SS_DISCOVERY_PORT = 55398; SS_TRANSFER_PORT = 55399
SS_MAGIC = b"NSTR"; SS_MAX_BYTES = 256*1024*1024
SS_MAX_HEADER_BYTES = 64*1024
SS_MAX_PENDING_TRANSFERS = 8
SS_BLOCKED_EXT = {".exe",".bat",".cmd",".com",".scr",".msi",".ps1",
                  ".vbs",".js",".jse",".wsf",".wsh",".pif",".reg",".dll",".sys",".drv"}
_SS_INSTANCE_ID = str(_uuid_mod.uuid4())[:8]

def _ss_hostname():
    try: return socket.gethostname()
    except Exception: return "NorthStar Device"

def _ss_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception: return "127.0.0.1"


class StarShareBeacon(QThread):
    peer_found = pyqtSignal(str, str, str)
    peer_left  = pyqtSignal(str)   # emits peer_id when a goodbye packet is received

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._ip = _ss_local_ip()
        self._name = _ss_hostname()

    def run(self):
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        tx.settimeout(1)

        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass

        rx.bind(("", SS_DISCOVERY_PORT))
        rx.settimeout(1)

        payload = SS_MAGIC + json.dumps({
            "id": _SS_INSTANCE_ID,
            "name": self._name,
            "ip": self._ip
        }).encode()

        while self._running:
            # send beacon
            try:
                tx.sendto(payload, ("<broadcast>", SS_DISCOVERY_PORT))
            except Exception as e:
                _log("SS_BEACON", f"broadcast error: {e}")

            # wait for responses (blocking)
            try:
                data, addr = rx.recvfrom(512)
                if data[:4] == SS_MAGIC:
                    info = json.loads(data[4:].decode())
                    peer_id = info.get("id", "")
                    peer_ip = info.get("ip") or addr[0]

                    if peer_id != _SS_INSTANCE_ID:
                        if info.get("bye"):
                            self.peer_left.emit(peer_id)
                        else:
                            self.peer_found.emit(
                                peer_id,
                                info.get("name", addr[0]),
                                peer_ip
                            )
            except socket.timeout:
                pass  # normal

        # Broadcast a goodbye packet before shutting down so peers remove us immediately.
        # Send it 3 times — UDP is unreliable and this costs nothing.
        goodbye = SS_MAGIC + json.dumps({
            "id": _SS_INSTANCE_ID,
            "bye": True
        }).encode()
        for _ in range(3):
            try:
                tx.sendto(goodbye, ("<broadcast>", SS_DISCOVERY_PORT))
            except Exception:
                break

        tx.close()
        rx.close()

    def stop(self):
        self._running = False
        self.quit()
        self.wait(2000)

class StarShareServer(QThread):
    transfer_request = pyqtSignal(str, str, int, str)
    transfer_data    = pyqtSignal(str, bytes)
    transfer_done    = pyqtSignal(str)
    transfer_error   = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent); self._running = True
        self._pending = {}; self._lock = threading.Lock()
        self._client_slots = threading.BoundedSemaphore(8)

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: srv.bind(("", SS_TRANSFER_PORT))
        except OSError: return
        srv.listen(4); srv.settimeout(1)
        while self._running:
            try:
                conn, addr = srv.accept()
                if not self._client_slots.acquire(blocking=False):
                    conn.close()
                    continue
                try:
                    conn.settimeout(15)
                    t = threading.Thread(
                        target=self._handle_client,
                        args=(conn, addr),
                        daemon=True,
                    )
                    t.start()
                except Exception:
                    self._client_slots.release()
                    conn.close()
                    raise
            except socket.timeout: pass
            except Exception as e: _log("SS_SERVER", f"accept error: {e}")
        srv.close()

    def _handle_client(self, conn, addr):
        try:
            self._handle(conn, addr)
        finally:
            self._client_slots.release()

    def _handle(self, conn, addr):
        try:
            magic = self._recv_exact(conn, 4)
            if magic != SS_MAGIC:
                conn.close()
                return
            hlen = struct.unpack(">I", self._recv_exact(conn,4))[0]
            if not 0 < hlen <= SS_MAX_HEADER_BYTES:
                raise ValueError("Invalid StarShare header size")
            hdr  = json.loads(self._recv_exact(conn, hlen).decode())
            if not isinstance(hdr, dict):
                raise ValueError("Invalid StarShare transfer header")
            fsize = hdr.get("size")
            if isinstance(fsize, bool) or not isinstance(fsize, int) or not 0 <= fsize <= SS_MAX_BYTES:
                raise ValueError("Invalid StarShare file size")
            filename = hdr.get("filename", "file")
            conn_id = hdr.get("conn_id", str(id(conn)))
            sender = hdr.get("sender_name", addr[0])
            if not isinstance(filename, str) or not filename or len(filename) > 255:
                raise ValueError("Invalid StarShare filename")
            filename = os.path.basename(filename.replace("\\", "/"))
            if not filename:
                raise ValueError("Invalid StarShare filename")
            if not isinstance(sender, str) or len(sender) > 128:
                raise ValueError("Invalid StarShare sender")
            if not isinstance(conn_id, str) or not conn_id or len(conn_id) > 128:
                raise ValueError("Invalid StarShare connection ID")
            with self._lock:
                if len(self._pending) >= SS_MAX_PENDING_TRANSFERS:
                    raise ConnectionError("Too many pending StarShare transfers")
                if conn_id in self._pending:
                    raise ValueError("Duplicate StarShare connection ID")
                self._pending[conn_id] = (conn, fsize)
            self.transfer_request.emit(sender, filename, fsize, conn_id)
        except Exception as e:
            self.transfer_error.emit("", str(e)); conn.close()

    def accept_transfer(self, conn_id, save_path):
        def _do():
            with self._lock: pending = self._pending.pop(conn_id, None)
            if not pending: return
            conn, fsize = pending
            try:
                conn.settimeout(120)
                conn.sendall(b"\x01")
                with open(save_path,"wb") as f:
                    remaining = fsize
                    while remaining:
                        chunk = conn.recv(min(65536, remaining))
                        if not chunk:
                            raise ConnectionError(
                                f"StarShare transfer ended with {remaining} bytes remaining"
                            )
                        f.write(chunk); self.transfer_data.emit(conn_id, chunk)
                        remaining -= len(chunk)
                self.transfer_done.emit(conn_id)
            except Exception as e: self.transfer_error.emit(conn_id, str(e))
            finally: conn.close()
        threading.Thread(target=_do, daemon=True).start()

    def decline_transfer(self, conn_id):
        with self._lock: pending = self._pending.pop(conn_id, None)
        if pending:
            conn, _ = pending
            try: conn.sendall(b"\x00")
            except: pass
            conn.close()

    @staticmethod
    def _recv_exact(conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n-len(buf))
            if not chunk: raise ConnectionError("Connection closed")
            buf += chunk
        return buf

    def stop(self):
        self._running = False
        with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for conn, _ in pending:
            conn.close()
        self.wait(2000)


class StarShareSender(QThread):
    progress = pyqtSignal(int); done = pyqtSignal(); error = pyqtSignal(str); declined = pyqtSignal()

    def __init__(self, target_ip, payload_path, filename, sender_name, ftype="file"):
        super().__init__()
        self.target_ip = target_ip; self.payload_path = payload_path
        self.filename = filename; self.sender_name = sender_name; self.ftype = ftype

    def run(self):
        sock = None
        try:
            fsize = os.path.getsize(self.payload_path)
            conn_id = _SS_INSTANCE_ID + "-" + str(int(time.time()))
            hdr = json.dumps({"sender_name":self.sender_name,"filename":self.filename,
                              "size":fsize,"type":self.ftype,"conn_id":conn_id}).encode()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.settimeout(10)
            sock.connect((self.target_ip, SS_TRANSFER_PORT))
            sock.sendall(SS_MAGIC); sock.sendall(struct.pack(">I",len(hdr))); sock.sendall(hdr)
            sock.settimeout(30); resp = sock.recv(1)
            if resp != b"\x01":
                self.declined.emit()
                return
            sock.settimeout(120); sent = 0
            with open(self.payload_path,"rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk: break
                    sock.sendall(chunk)
                    sent += len(chunk)
                    self.progress.emit(sent)
            sock.close()
            sock = None
            self.done.emit()
        except Exception as e: self.error.emit(str(e))
        finally:
            if sock is not None:
                sock.close()


# ─────────────────────────────────────────────
#  PERMISSION SYSTEM
# ─────────────────────────────────────────────
_PERMISSIONS_FILE = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "NorthStar", "northstar_permissions.json"
)

_PERMISSION_LABELS = {
    QWebEnginePage.Feature.MediaAudioCapture:       "Microphone",
    QWebEnginePage.Feature.MediaVideoCapture:       "Camera",
    QWebEnginePage.Feature.MediaAudioVideoCapture:  "Camera & Microphone",
    QWebEnginePage.Feature.DesktopVideoCapture:     "Screen Sharing",
    QWebEnginePage.Feature.DesktopAudioVideoCapture:"Screen Sharing (with audio)",
    QWebEnginePage.Feature.Notifications:           "Notifications",
    QWebEnginePage.Feature.Geolocation:             "Location",
    QWebEnginePage.Feature.ClipboardReadWrite:      "Clipboard",
    # Newer permissionRequested signal uses QWebEnginePermission.PermissionType
    QWebEnginePermission.PermissionType.MediaAudioCapture:       "Microphone",
    QWebEnginePermission.PermissionType.MediaVideoCapture:       "Camera",
    QWebEnginePermission.PermissionType.MediaAudioVideoCapture:  "Camera & Microphone",
    QWebEnginePermission.PermissionType.DesktopVideoCapture:     "Screen Sharing",
    QWebEnginePermission.PermissionType.DesktopAudioVideoCapture:"Screen Sharing (with audio)",
    QWebEnginePermission.PermissionType.Notifications:           "Notifications",
    QWebEnginePermission.PermissionType.Geolocation:             "Location",
    QWebEnginePermission.PermissionType.ClipboardReadWrite:      "Clipboard",
}

# Permissions that are safe to auto-grant without showing a toast.
# Clipboard reads/writes require an explicit user gesture (button click) at
# the JS level, so silently granting them makes "Copy" buttons on sites
# like ChatGPT/Gemini work without nagging the user on every click.
_AUTO_GRANT_PERMISSIONS = {
    QWebEnginePage.Feature.ClipboardReadWrite,
    QWebEnginePermission.PermissionType.ClipboardReadWrite,
}

_PERMISSION_ICONS = {
    QWebEnginePage.Feature.MediaAudioCapture:       "🎤",
    QWebEnginePage.Feature.MediaVideoCapture:       "📷",
    QWebEnginePage.Feature.MediaAudioVideoCapture:  "📷🎤",
    QWebEnginePage.Feature.DesktopVideoCapture:     "🖥",
    QWebEnginePage.Feature.DesktopAudioVideoCapture:"🖥🎤",
    QWebEnginePage.Feature.Notifications:           "🔔",
    QWebEnginePage.Feature.Geolocation:             "📍",
    QWebEnginePermission.PermissionType.MediaAudioCapture:       "🎤",
    QWebEnginePermission.PermissionType.MediaVideoCapture:       "📷",
    QWebEnginePermission.PermissionType.MediaAudioVideoCapture:  "📷🎤",
    QWebEnginePermission.PermissionType.DesktopVideoCapture:     "🖥",
    QWebEnginePermission.PermissionType.DesktopAudioVideoCapture:"🖥🎤",
    QWebEnginePermission.PermissionType.Notifications:           "🔔",
    QWebEnginePermission.PermissionType.Geolocation:             "📍",
}


class PermissionManager:
    """Manages per-origin permission decisions with persistence."""

    def __init__(self):
        self._grants: dict[str, dict[str, bool]] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(_PERMISSIONS_FILE):
                with open(_PERMISSIONS_FILE, "r") as f:
                    self._grants = json.load(f)
        except Exception:
            self._grants = {}

    def _save(self):
        os.makedirs(os.path.dirname(_PERMISSIONS_FILE), exist_ok=True)
        with open(_PERMISSIONS_FILE, "w") as f:
            json.dump(self._grants, f, indent=2)

    def _key(self, origin: str, perm_type) -> str:
        val = perm_type.value if hasattr(perm_type, 'value') else int(perm_type)
        return f"{origin}::{val}"

    def get_saved(self, origin: str, perm_type) -> bool | None:
        """Return saved decision or None if no saved decision."""
        return self._grants.get(self._key(origin, perm_type))

    def save_decision(self, origin: str, feature: QWebEnginePage.Feature, allow: bool):
        self._grants[self._key(origin, feature)] = allow
        self._save()

    def remove_saved(self, origin: str, feature: QWebEnginePage.Feature):
        self._grants.pop(self._key(origin, feature), None)
        self._save()

    def clear_all(self):
        self._grants.clear()
        self._save()


class PermissionToast(QFrame):
    """Toast notification for permission requests — matches StarShareToast style."""
    decided = pyqtSignal(bool, bool)  # (allow, remember)

    _POPUP_W = 340
    _MARGIN  = 16

    def __init__(self, origin: str, feature, parent=None):
        super().__init__(parent)
        self.origin = origin
        self.feature = feature
        self.setObjectName("StarShareToast")
        self.setFixedWidth(self._POPUP_W)

        label = _PERMISSION_LABELS.get(feature, "Permission")
        icon = _PERMISSION_ICONS.get(feature, "🔒")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        top = QHBoxLayout(); top.setSpacing(8)
        icon_lbl = QLabel(icon); icon_lbl.setObjectName("ToastIcon")
        icon_lbl.setFixedWidth(18)
        msg = QLabel(f"<b>{origin}</b> wants to use your {label.lower()}")
        msg.setWordWrap(True); msg.setObjectName("ToastMsg")
        top.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(msg, 1)
        outer.addLayout(top)

        self._remember_cb = QPushButton("Remember for this site")
        self._remember_cb.setCheckable(True)
        self._remember_cb.setChecked(True)
        self._remember_cb.setObjectName("ToastDetail")
        self._remember_cb.setContentsMargins(26, 0, 0, 0)
        outer.addWidget(self._remember_cb)

        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        self._cd_lbl = QLabel("10s"); self._cd_lbl.setObjectName("ToastCd")
        btn_row.addWidget(self._cd_lbl)
        btn_row.addStretch()
        allow = QPushButton("Allow"); allow.setObjectName("ToastYes")
        allow.setFixedHeight(30); allow.setMinimumWidth(80)
        allow.clicked.connect(lambda: self._decide(True))
        deny = QPushButton("Deny"); deny.setObjectName("ToastNo")
        deny.setFixedHeight(30); deny.setMinimumWidth(72)
        deny.clicked.connect(lambda: self._decide(False))
        btn_row.addWidget(allow); btn_row.addWidget(deny)
        outer.addLayout(btn_row)

        self._secs = 10
        self._expire = QTimer(self); self._expire.setSingleShot(True)
        self._expire.timeout.connect(lambda: self._decide(False))
        self._expire.start(10_000)
        self._tick_t = QTimer(self); self._tick_t.timeout.connect(self._tick)
        self._tick_t.start(1_000)

        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self._repin()
        return False

    def _repin(self):
        p = self.parent()
        if not p: return
        self.adjustSize()
        x = p.width()  - self.width()  - self._MARGIN
        y = p.height() - self.height() - self._MARGIN
        self.move(max(0, x), max(0, y))
        self.raise_()

    def _tick(self):
        self._secs -= 1
        self._cd_lbl.setText(f"{self._secs}s")

    def _decide(self, allow):
        self._expire.stop(); self._tick_t.stop()
        remember = self._remember_cb.isChecked()
        self.decided.emit(allow, remember)
        self._dismiss()

    def _dismiss(self):
        p = self.parent()
        if p: p.removeEventFilter(self)
        self.hide(); self.deleteLater()


# Global permission manager instance
_perm_manager = PermissionManager()


class StarShareToast(QFrame):
    accepted = pyqtSignal(str, str); declined = pyqtSignal(str)

    _POPUP_W = 340          # fixed width — wide enough for buttons + info
    _MARGIN  = 16           # gap from window edges

    def __init__(self, sender, filename, fsize, conn_id, parent=None):
        super().__init__(parent)
        self.conn_id  = conn_id
        self.filename = filename
        self.setObjectName("StarShareToast")
        self.setFixedWidth(self._POPUP_W)

        # ── grab file extension as a readable type label ──────────────────
        ext  = os.path.splitext(filename)[1].lower()          # e.g. ".pdf"
        ftype = ext.lstrip(".").upper() if ext else "File"    # e.g. "PDF"

        # ── layout ────────────────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        # Row 1 — who / intent
        top = QHBoxLayout(); top.setSpacing(8)
        icon = QLabel("✦"); icon.setObjectName("ToastIcon")
        icon.setFixedWidth(18)
        who = QLabel(f"<b>{sender}</b> wants to send you a file")
        who.setWordWrap(True); who.setObjectName("ToastMsg")
        top.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(who, 1)
        outer.addLayout(top)

        # Row 2 — file details
        detail = QLabel(
            f"<span style='font-weight:600'>{filename}</span>"
            f"<br><span style='opacity:.7'>{ftype} &nbsp;·&nbsp; {_format_size(fsize)}</span>"
        )
        detail.setObjectName("ToastDetail")
        detail.setWordWrap(True)
        detail.setContentsMargins(26, 0, 0, 0)   # indent under icon
        outer.addWidget(detail)

        # Row 3 — buttons + countdown
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        self._cd_lbl = QLabel("30s"); self._cd_lbl.setObjectName("ToastCd")
        btn_row.addWidget(self._cd_lbl)
        btn_row.addStretch()
        acc = QPushButton("Accept ✦"); acc.setObjectName("ToastYes")
        acc.setFixedHeight(30); acc.setMinimumWidth(90)
        acc.clicked.connect(self._accept)
        dec = QPushButton("Decline"); dec.setObjectName("ToastNo")
        dec.setFixedHeight(30); dec.setMinimumWidth(72)
        dec.clicked.connect(self._decline)
        btn_row.addWidget(acc); btn_row.addWidget(dec)
        outer.addLayout(btn_row)

        # ── timers ────────────────────────────────────────────────────────
        self._secs = 30
        self._expire = QTimer(self); self._expire.setSingleShot(True)
        self._expire.timeout.connect(self._decline); self._expire.start(30_000)
        self._tick_t = QTimer(self); self._tick_t.timeout.connect(self._tick)
        self._tick_t.start(1_000)

        # ── install resize filter on parent so we stay pinned ─────────────
        if parent:
            parent.installEventFilter(self)

    # keep popup pinned to bottom-right whenever the parent resizes
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self._repin()
        return False

    def _repin(self):
        p = self.parent()
        if not p: return
        self.adjustSize()
        x = p.width()  - self.width()  - self._MARGIN
        y = p.height() - self.height() - self._MARGIN
        self.move(max(0, x), max(0, y))
        self.raise_()

    def _tick(self):
        self._secs -= 1
        self._cd_lbl.setText(f"{self._secs}s")

    def _accept(self):
        self._stop()
        save_path, _ = QFileDialog.getSaveFileName(
            self.window(), "Save received file",
            os.path.join(os.path.expanduser("~"), "Downloads", self.filename))
        if save_path: self.accepted.emit(self.conn_id, save_path)
        else:         self.declined.emit(self.conn_id)
        self._dismiss()

    def _decline(self):
        self._stop(); self.declined.emit(self.conn_id); self._dismiss()

    def _stop(self):
        self._expire.stop(); self._tick_t.stop()

    def _dismiss(self):
        p = self.parent()
        if p: p.removeEventFilter(self)
        self.hide(); self.deleteLater()


class StarShareDeviceCard(QFrame):
    send_to     = pyqtSignal(str, str)
    went_offline = pyqtSignal(str)   # emits peer_id when the expire timer fires

    def __init__(self, peer_id, name, ip, parent=None):
        super().__init__(parent); self.peer_id = peer_id; self.peer_ip = ip
        self.setObjectName("SSDeviceCard"); self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QHBoxLayout(self); layout.setContentsMargins(10,8,10,8); layout.setSpacing(10)
        self._dot = QLabel("●"); self._dot.setObjectName("SSPulse"); layout.addWidget(self._dot)
        info = QVBoxLayout(); info.setSpacing(1)
        self._name_lbl = QLabel(name); self._name_lbl.setObjectName("DlName")
        info.addWidget(self._name_lbl); layout.addLayout(info, 1)
        send_btn = QPushButton("Send ✦"); send_btn.setObjectName("ToastYes")
        send_btn.setFixedHeight(28); send_btn.setFixedWidth(72)
        send_btn.clicked.connect(lambda: self.send_to.emit(self.peer_id, self.peer_ip))
        layout.addWidget(send_btn)
        self._expire_timer = QTimer(self); self._expire_timer.setSingleShot(True)
        self._expire_timer.timeout.connect(self._mark_offline); self._expire_timer.start(8000)

    def refresh(self, name, ip):
        self._name_lbl.setText(name); self.peer_ip = ip
        self._dot.setObjectName("SSPulse"); self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot); self._expire_timer.start(8000)

    def _mark_offline(self):
        self._dot.setObjectName("SSPulseOff"); self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)
        self.went_offline.emit(self.peer_id)   # FIX: notify panel to remove stale card


class StarSharePanel(QWidget):
    status_message = pyqtSignal(str, int)

    def __init__(self, server, parent=None):
        super().__init__(parent); self.setObjectName("DownloadsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._server = server; self._devices = {}; self._senders = []; self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)
        hdr = QHBoxLayout()
        icon = QLabel("✦"); icon.setObjectName("DlHeaderIcon")
        title = QLabel("StarShare™"); title.setObjectName("DlHeaderTitle")
        hdr.addWidget(icon); hdr.addWidget(title); hdr.addStretch(); layout.addLayout(hdr)
        div = QFrame(); div.setObjectName("DlDivider"); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); layout.addWidget(div)
        type_row = QHBoxLayout(); type_row.setSpacing(4)
        self._type_url  = QPushButton("🔗 URL")
        self._type_file = QPushButton("📁 File")
        self._type_shot = QPushButton("📸 Screenshot")
        for btn in (self._type_url, self._type_file, self._type_shot):
            btn.setObjectName("QuickBtn"); btn.setCheckable(True); type_row.addWidget(btn)
        self._type_file.setChecked(True)
        self._type_url.clicked.connect(lambda: self._select_type("url"))
        self._type_file.clicked.connect(lambda: self._select_type("file"))
        self._type_shot.clicked.connect(lambda: self._select_type("screenshot"))
        layout.addLayout(type_row); self._share_type = "file"
        self._empty_lbl = QLabel("Scanning for NorthStar devices…")
        self._empty_lbl.setObjectName("DlEmpty"); self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_lbl)
        scroll = QScrollArea(); scroll.setObjectName("DlScroll"); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._dev_widget = QWidget(); self._dev_widget.setObjectName("DlList")
        self._dev_layout = QVBoxLayout(self._dev_widget)
        self._dev_layout.setContentsMargins(0,0,0,0); self._dev_layout.setSpacing(4)
        self._dev_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._dev_widget); layout.addWidget(scroll, 1)
        self._prog_lbl = QLabel(""); self._prog_lbl.setObjectName("AIStatus"); layout.addWidget(self._prog_lbl)
        self._prog_bar = QProgressBar(); self._prog_bar.setObjectName("DlBar")
        self._prog_bar.setMaximumHeight(5); self._prog_bar.setTextVisible(False)
        self._prog_bar.hide(); layout.addWidget(self._prog_bar)

    def _select_type(self, t):
        self._share_type = t
        for btn, bt in ((self._type_url,"url"),(self._type_file,"file"),(self._type_shot,"screenshot")):
            btn.setChecked(bt==t)

    def on_peer_found(self, peer_id, name, ip):
        if peer_id in self._devices: self._devices[peer_id].refresh(name, ip)
        else:
            card = StarShareDeviceCard(peer_id, name, ip, self._dev_widget)
            card.send_to.connect(self._on_send_to)
            card.went_offline.connect(self._remove_device)   # FIX: wire up removal
            self._dev_layout.addWidget(card)
            self._devices[peer_id] = card; self._empty_lbl.hide()

    def _remove_device(self, peer_id):
        """FIX: remove a device card once its beacon expires (StarShare disabled)."""
        card = self._devices.pop(peer_id, None)
        if card:
            self._dev_layout.removeWidget(card)
            card.hide()        # hide immediately — deleteLater() is deferred
            card.deleteLater()
        if not self._devices:
            self._empty_lbl.setText("Scanning for NorthStar devices…")
            self._empty_lbl.show()

    def _on_send_to(self, peer_id, peer_ip):
        t = self._share_type
        if t == "url": self._send_url(peer_ip)
        elif t == "file": self._send_file(peer_ip)
        elif t == "screenshot": self._send_screenshot(peer_ip)

    def _send_file(self, peer_ip):
        path, _ = QFileDialog.getOpenFileName(self.window(), "Select file to send")
        if not path: return
        ext = os.path.splitext(path)[1].lower()
        if ext in SS_BLOCKED_EXT: self.status_message.emit(f"✕ Blocked file type: {ext}", 4000); return
        if os.path.getsize(path) > SS_MAX_BYTES: self.status_message.emit("✕ File exceeds 256 MB", 4000); return
        self._do_send(peer_ip, path, os.path.basename(path), "file")

    def _send_url(self, peer_ip):
        tab = self.window()._current_tab() if hasattr(self.window(),'_current_tab') else None
        url = tab.view.url().toString() if tab else ""
        if not url.startswith("http"): self.status_message.emit("No URL to share.", 3000); return
        tmp = os.path.join(os.path.expanduser("~"), ".northstar_share_url.txt")
        with open(tmp,"w") as f: f.write(url)
        self._do_send(peer_ip, tmp, "shared_url.txt", "url")

    def _send_screenshot(self, peer_ip):
        tab = self.window()._current_tab() if hasattr(self.window(),'_current_tab') else None
        if not tab: self.status_message.emit("No active tab.", 3000); return
        tmp = os.path.join(os.path.expanduser("~"), ".northstar_screenshot.png")
        tab.view.grab().save(tmp, "PNG")
        self._do_send(peer_ip, tmp, "screenshot.png", "screenshot")

    def _do_send(self, peer_ip, path, filename, ftype):
        sender = StarShareSender(peer_ip, path, filename, _ss_hostname(), ftype)
        total  = os.path.getsize(path)
        sender.progress.connect(lambda b: self._on_send_progress(b, total))
        sender.done.connect(self._on_send_done); sender.error.connect(self._on_send_error)
        sender.declined.connect(lambda: self.status_message.emit("Transfer declined.", 3000))
        self._senders.append(sender)
        self._prog_bar.setValue(0); self._prog_bar.setMaximum(100); self._prog_bar.show()
        self._prog_lbl.setText(f"Sending {filename}…"); sender.start()

    def _on_send_progress(self, sent, total):
        if total > 0: self._prog_bar.setValue(int(sent*100/total))
        self._prog_lbl.setText(f"Sending… {_format_size(sent)} / {_format_size(total)}")

    def _on_send_done(self):
        self._prog_bar.hide(); self._prog_lbl.setText("✓ Sent successfully")
        self.status_message.emit("✦ StarShare: transfer complete.", 4000)

    def _on_send_error(self, msg):
        self._prog_bar.hide(); self._prog_lbl.setText(f"✕ Error: {msg}")
        self.status_message.emit(f"StarShare error: {msg}", 5000)


# ─────────────────────────────────────────────
#  COMMAND PALETTE
# ─────────────────────────────────────────────
COMMANDS = [
    ("New Tab","Ctrl+T"),("Close Tab","Ctrl+W"),("Reload Page","Ctrl+R"),
    ("Hard Reload","Ctrl+Shift+R"),("Focus Address Bar","Ctrl+L"),
    ("Go Back","Alt+Left"),("Go Forward","Alt+Right"),
    ("Toggle AI Panel","Ctrl+Shift+A"),("Toggle Downloads","Ctrl+J"),
    ("Toggle Password Book","Ctrl+Shift+K"),("Open History","Ctrl+H"),
    ("StarShare","Ctrl+Shift+S"),("Find in Page","Ctrl+F"),
    ("Settings","Ctrl+,"),("Zoom In","Ctrl++"),("Zoom Out","Ctrl+-"),
    ("Reset Zoom","Ctrl+0"),
    ("Bookmark Page","Ctrl+D"),("Fullscreen","F11"),
    ("Developer Tools","F12"),
]

class CommandPalette(QDialog):
    command_selected = pyqtSignal(str)

    _CATEGORIES = {
        "New Tab": "Tabs", "Close Tab": "Tabs",
        "Reload Page": "Navigation", "Hard Reload": "Navigation",
        "Focus Address Bar": "Navigation", "Go Back": "Navigation", "Go Forward": "Navigation",
        "Toggle AI Panel": "Panels", "Toggle Downloads": "Panels",
        "Toggle Password Book": "Panels", "Open History": "Panels", "Settings": "Panels",
        "StarShare": "Panels", "Find in Page": "Page",
        "Zoom In": "Page", "Zoom Out": "Page", "Reset Zoom": "Page",
        "Bookmark Page": "Page", "Fullscreen": "Window", "Developer Tools": "Window",
    }

    def __init__(self, parent=None, recent_commands=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self._recent_commands = list(recent_commands or [])
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self._build_ui()

    def _build_ui(self):
        self.setFixedWidth(520)
        self.setMaximumHeight(640)
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        container = QFrame(); container.setObjectName("PaletteContainer")
        inner = QVBoxLayout(container); inner.setContentsMargins(12,12,12,12); inner.setSpacing(8)
        self.search = QLineEdit(); self.search.setObjectName("PaletteSearch")
        self.search.setPlaceholderText("⌘  Type a command…"); self.search.textChanged.connect(self._filter)
        self.search.setAccessibleName("Search browser commands")
        self.search.installEventFilter(self)
        self.search.returnPressed.connect(self._activate_current)
        inner.addWidget(self.search)
        self.list = QListWidget(); self.list.setObjectName("PaletteList")
        self.list.setAccessibleName("Matching browser commands")
        self.list.itemActivated.connect(self._run); inner.addWidget(self.list)
        layout.addWidget(container); self._filter("")

    @staticmethod
    def _match_score(query, name):
        """Return a useful score for ordered character matches; -1 means no match."""
        query = "".join(query.lower().split())
        candidate = name.lower()
        if not query:
            return 0
        cursor = 0
        score = 0
        previous = -2
        for char in query:
            found = candidate.find(char, cursor)
            if found < 0:
                return -1
            score += 10
            if found == previous + 1:
                score += 12
            elif found == 0 or candidate[found - 1] in " _-":
                score += 8
            score -= found - cursor
            previous = found
            cursor = found + 1
        return score - len(candidate) // 8

    def _populate(self, groups):
        self.list.clear()
        for heading, commands in groups:
            if not commands:
                continue
            header = QListWidgetItem(heading.upper())
            header.setData(Qt.ItemDataRole.UserRole + 1, "header")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(header)
            for name, shortcut in commands:
                item = QListWidgetItem(f"  {name}   {shortcut}")
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setData(Qt.ItemDataRole.UserRole + 1, "command")
                item.setToolTip(f"{name} ({shortcut})")
                self.list.addItem(item)
        self._select_next(1)

    def _filter(self, text):
        scored = [(self._match_score(text, name), name, shortcut)
                  for name, shortcut in COMMANDS]
        matches = [(name, shortcut) for score, name, shortcut in scored if score >= 0]
        matches.sort(key=lambda command: (
            -self._match_score(text, command[0]), COMMANDS.index(command)))
        groups = []
        recent = [command for name in self._recent_commands
                  for command in matches if command[0] == name]
        if not text.strip():
            groups.append(("Recent", recent[:5]))
        remaining = [command for command in matches if command not in recent]
        for category in ("Tabs", "Navigation", "Panels", "Page", "Window"):
            grouped = [command for command in remaining
                       if self._CATEGORIES.get(command[0], "Other") == category]
            if grouped:
                groups.append((category, grouped))
        self._populate(groups)

    def _select_next(self, direction):
        row = self.list.currentRow()
        if row < 0:
            row = 0 if direction > 0 else self.list.count() - 1
        else:
            row += direction
        while 0 <= row < self.list.count():
            item = self.list.item(row)
            if item.data(Qt.ItemDataRole.UserRole + 1) == "command":
                self.list.setCurrentRow(row)
                return
            row += direction

    def _activate_current(self):
        item = self.list.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole + 1) == "command":
            self._run(item)

    def _run(self, item):
        if item.data(Qt.ItemDataRole.UserRole + 1) != "command":
            return
        self.command_selected.emit(item.data(Qt.ItemDataRole.UserRole)); self.close()

    def eventFilter(self, obj, event):
        if obj == self.search and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down:
                self._select_next(1)
                return True
            if event.key() == Qt.Key.Key_Up:
                self._select_next(-1)
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape: self.close()
        elif e.key() == Qt.Key.Key_Return:
            self._activate_current()
        elif e.key() == Qt.Key.Key_Down:
            self._select_next(1)
        elif e.key() == Qt.Key.Key_Up:
            self._select_next(-1)
        else: super().keyPressEvent(e)

    def show_centered(self, parent_widget):
        x = parent_widget.mapToGlobal(QPoint((parent_widget.geometry().width()-self.width())//2, 80))
        self.move(x)
        _ns_opacity(self).setOpacity(0.0)
        self.show()
        self.search.setFocus()
        _ns_fade_widget(self)


# ─────────────────────────────────────────────
#  NEW TAB PAGE — MEMOISED
# ─────────────────────────────────────────────
NORTHSTAR_HOME = "northstar://newtab"

# Official Microsoft Edge Add-ons storefront (opened in the current tab;
# content scripts are loaded via "Load Unpacked…").
EDGE_ADDONS_URL = "https://microsoftedge.microsoft.com/addons"

# OPT: cache the last generated HTML so repeated calls with identical args are free
_newtab_cache: dict = {}

def _build_newtab_html(bookmarks: list, dark_mode: bool = False, search_engine_url: str = "https://www.google.com/search?q={}") -> str:
    """
    Antimatter Design — New Tab Redesign
    Core philosophy: Remove visual noise. Let content float.
    """
    # ── Fernway Integration ──────────────────────────────────────────────────
    fw = get_fernway()
    
    # Include Fernway settings in cache key so changes trigger a re-render
    fw_all = fw.get_all_settings()
    fw_hashable_items = []
    for k, v in fw_all.items():
        if isinstance(v, (str, int, float, bool)):
            fw_hashable_items.append((k, v))
    fw_state = tuple(sorted(fw_hashable_items))
    cache_key = (dark_mode, search_engine_url, tuple((b.get("title",""), b.get("url","")) for b in bookmarks), fw_state)
    
    if cache_key in _newtab_cache:
        return _newtab_cache[cache_key]

    _disk_key = f"newtab_{hash(cache_key) & 0xFFFF_FFFF_FFFF_FFFF}"
    _cached_html = _startup_cache.get(_disk_key)
    if _cached_html is not None:
        _newtab_cache[cache_key] = _cached_html
        return _cached_html
    
    # ── Wallpaper Carousel ───────────────────────────────────────────────
    import random
    wallpaper_mode = fw.get("wallpaper_mode", "static")
    wallpaper_count = len(_global_wallpaper_files)
    # Shuffle wallpaper indices for this new tab page
    wallpaper_indices = list(range(wallpaper_count))
    random.shuffle(wallpaper_indices)

    # ── Daily Quote ─────────────────────────────────────────────────────
    _quotes_file = _asset("quotes.json")
    _quote_text = "The best way to predict the future is to invent it."
    _quote_author = "Alan Kay"
    try:
        import datetime as _dt
        day_of_year = _dt.datetime.now().timetuple().tm_yday
        with open(_quotes_file, 'r', encoding='utf-8') as f:
            _quotes_list = json.load(f)
        if _quotes_list:
            idx = (day_of_year - 1) % len(_quotes_list)
            _quote_text = _quotes_list[idx].get("quote", _quote_text)
            _quote_author = _quotes_list[idx].get("author", _quote_author)
    except Exception:
        pass
    
    accent_p = fw.get("accent_primary", "#4fc3f7")
    accent_s = fw.get("accent_secondary", "#9c6ff7")
    opacity  = 0.70 if (wallpaper_mode in ("carousel", "video") and wallpaper_count > 0) else fw.get("transparency_level", 0.88)
    glow_int = fw.get("glow_intensity", 0.5)
    blur_str = fw.get("blur_strength", 16)  # Antimatter uses 12-18px
    bg_style = fw.get("background_style", "current")
    
    # ── Colour tokens ────────────────────────────────────────────────────────
    if oled_enabled():
        ot           = oled_web_tokens(opacity)
        body_bg      = ot["bg"]
        card_bg      = f"rgba(0,0,0,{opacity})"
        glass2       = f"rgba(16,14,8,{min(1.0, opacity + 0.06)})"
        text_main    = "#e8edf8"
        text_dim     = f"rgba(232,237,248,{0.5 + 0.2 * glow_int})"
        text_sub     = "rgba(200,210,240,0.35)"
        accent       = ot["accent"]
        input_bg     = ot["input_bg"]
        input_bd     = "rgba(212,175,55,0.30)"
        input_ph     = "rgba(200,210,240,0.42)"
        bm_bg        = "rgba(255,255,255,0.04)"
        bm_bd        = "rgba(212,175,55,0.22)"
        bm_hover     = ot["accent2"]
        bm_ltr       = ot["accent2"]
        divider      = "rgba(212,175,55,0.18)"
    elif dark_mode:
        body_bg    = "#05060a"
        card_bg    = f"rgba(12, 14, 24, {opacity})"
        glass2     = f"rgba(18, 20, 32, {min(1.0, opacity + 0.06)})"
        text_main  = "#f0f4f8"
        text_dim   = f"rgba(220, 228, 244, {0.45 + 0.2 * glow_int})"
        text_sub   = "rgba(220, 228, 244, 0.38)"
        accent     = accent_p
        input_bg   = "rgba(8, 10, 18, 0.75)"
        input_bd   = f"rgba(110, 130, 210, {0.08 + 0.12 * glow_int})"
        input_ph   = "rgba(220, 228, 244, 0.35)"
        bm_bg      = "rgba(18, 20, 32, 0.35)"
        bm_bd      = f"rgba(110, 130, 210, {0.08 + 0.09 * glow_int})"
        bm_hover   = accent
        bm_ltr     = accent_s
        divider    = f"rgba(110, 130, 210, {0.08 + 0.1 * glow_int})"
    else:
        body_bg    = "#f4f6fb"
        card_bg    = f"rgba(255, 255, 255, {opacity})"
        glass2     = f"rgba(248, 250, 255, {min(1.0, opacity + 0.10)})"
        text_main  = "#0a0c14"
        text_dim   = f"rgba(18, 24, 40, {0.45 + 0.2 * glow_int})"
        text_sub   = "rgba(18, 24, 40, 0.38)"
        accent     = accent_p
        input_bg   = "rgba(255, 255, 255, 0.75)"
        input_bd   = f"rgba(90, 110, 200, {0.08 + 0.1 * glow_int})"
        input_ph   = "rgba(18, 24, 40, 0.35)"
        bm_bg      = "rgba(248, 250, 255, 0.55)"
        bm_bd      = f"rgba(90, 110, 200, {0.08 + 0.08 * glow_int})"
        bm_hover   = accent
        bm_ltr     = accent_s
        divider    = f"rgba(90, 110, 200, {0.08 + 0.08 * glow_int})"

    # ── Bookmark cards ───────────────────────────────────────────────────────
    bm_cards = ""
    for bookmark_index, bm in enumerate(bookmarks):
        title = bm.get("title", "")
        url   = bm.get("url", "")
        url_safe = _html_mod.escape(url, quote=True)
        title_safe = _html_mod.escape(title)
        title_attr = _html_mod.escape(title, quote=True)
        title_initial = _html_mod.escape(title[:1].upper()) if title else "?"
        # Determine icon
        is_special = url.startswith("northstar://newtab") or url.startswith("opal://") or title in ("New Tab", "Opal Discovery")
        if is_special:
            icon_html = '<span class="bm-icon">✦</span>'
        else:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc
                favicon_data = _global_favicon_data_cache.get(domain)
                if favicon_data:
                    icon_html = (
                        '<img class="bm-icon-img" src="data:image/png;base64,'
                        f'{favicon_data}" alt="">'
                    )
                else:
                    icon_html = f'<span class="bm-icon">{title_initial}</span>'
            except Exception:
                icon_html = f'<span class="bm-icon">{title_initial}</span>'
        
        bm_cards += (
            f'<div class="bm-item"><a class="bm-card" href="{url_safe}" title="{title_attr}&#10;{_html_mod.escape(url, quote=True)}">'
            f'<div class="bm-icon-wrap">{icon_html}</div>'
            f'<span class="bm-title">{title_safe}</span>'
            f'</a><div class="bm-actions" aria-label="Manage {title_attr} shortcut">'
            f'<button type="button" data-move="up" data-url="{url_safe}" aria-label="Move {title_attr} up" {"disabled" if bookmark_index == 0 else ""}>↑</button>'
            f'<button type="button" data-move="down" data-url="{url_safe}" aria-label="Move {title_attr} down" {"disabled" if bookmark_index == len(bookmarks) - 1 else ""}>↓</button>'
            f'<button type="button" data-remove="{url_safe}" aria-label="Remove {title_attr} shortcut">×</button>'
            f'</div></div>'
        )

    _bm_empty = (
        f'<div class="empty-state">'
        f'<p class="empty">No bookmarks yet \u2014 press Ctrl+D on any page.</p>'
        f'<p class="empty-sub">or <a class="text-btn" href="northstar://import-bookmarks" id="import-bookmarks-btn">Import Bookmarks</a></p>'
        f'</div>'
    )
    bm_section = (
        f'<div class="bm-grid{" bm-grid-empty" if not bm_cards else ""}">'
        '<div class="bm-heading"><span>Bookmarks</span>'
        '<button type="button" id="bm-edit" aria-pressed="false">Manage</button></div>'
        f'{bm_cards if bm_cards else _bm_empty}</div>'
    )

    scheme = "dark" if dark_mode else "light"

    # ── Pattern colours ───────────────────────────────────────────────────────
    dot_col  = accent
    line_col = accent

    selected_search_url = search_engine_url or SEARCH_ENGINES["Google"]
    selected_search_name = next(
        (name for name, template in SEARCH_ENGINES.items() if template == selected_search_url),
        "Search",
    )
    _se_js = selected_search_url.replace("{}", "__Q__")

    # ── Wallpaper Carousel Settings ─────────────────────────────────────
    wallpaper_indices_js = json.dumps(wallpaper_indices)

    # ── Greeting ─────────────────────────────────────────────────────────────
    _hour = int(datetime.datetime.now().hour)
    if _hour < 12:      _greeting = "Good morning"
    elif _hour < 17:    _greeting = "Good afternoon"
    else:               _greeting = "Good evening"

    video_html = ""
    if wallpaper_mode == "video":
        video_html = (
            '<video id="wallpaper-video" autoplay muted loop playsinline '
            'style="position:fixed;top:0;left:0;width:100%;height:100%;'
            'object-fit:cover;z-index:1;pointer-events:none;'
            'filter:blur(8px);transform:scale(1.05);">'
            '<source src="' + oled_wallpaper_video_src() + '" type="video/webm">'
            '</video>'
        )

    # ── HTML ─────────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="{scheme}">
<title>Northstar One: Brand New Light</title>
<style>
/* ── Reset ── */
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}

    /* ── Page ── */
    html,body{{
        height:100vh;
        width:100vw;
        overflow:hidden;
        background:{body_bg};
        color:{text_main};
        font-family:'Segoe UI',system-ui,ui-sans-serif,sans-serif;
        display:flex;
        align-items:center;
        justify-content:center;
        position:relative;
        flex-direction:column;
        margin:0;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}


/* ── Wallpaper Carousel ── */
#wallpaper-carousel{{
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    z-index:1;
    pointer-events:none;
}}
.wallpaper-slide{{
    position:absolute;
    top:0;
    left:0;
    width:100%;
    height:100%;
    background-size:cover;
    background-position:center;
    background-repeat:no-repeat;
    opacity:0;
    transition:opacity 1s ease-in-out;
    z-index:0;
    filter: blur(5px); /* Blur the wallpaper */
    transform: scale(1.05); /* Slight scale to fix blur edge artifacts */
}}
.wallpaper-slide.active{{
    opacity:1;
}}
#wallpaper-carousel::before{{
    content:'';
    position:absolute;
    inset:0;
    z-index:1;
    background:linear-gradient(to bottom, rgba(0,0,0,0.05), rgba(0,0,0,0.15));
}}
#wallpaper-carousel::after{{
    content:'';
    position:absolute;
    inset:0;
    z-index:1;
    background:radial-gradient(circle at center, transparent 0%, rgba(0,0,0,0.10) 100%);
}}

/* ── Constellation canvas ── */
#bg{{
    position:fixed;
    top:0;
    left:0;
    width:100%;
    height:100%;
    z-index:0;
    pointer-events:none;
    display: { 'none' if wallpaper_mode == 'video' or (wallpaper_mode == 'carousel' and wallpaper_count > 0) else 'block' };
}}

/* ── Card ── */
.card{{
    position:relative;
    z-index:10;
    width:min(680px,94vw);
    background:{card_bg};
    border:1px solid {divider};
    border-radius:24px;
    padding:28px 48px 24px;
    box-shadow:0 8px 32px rgba(0,0,0,0.125);
}}

/* ── Logo ── */
.logo{{
    display:flex;
    align-items:center;
    justify-content:center;
    gap:10px;
    margin-bottom:18px;
}}
.logo-star{{
    font-size:28px;
    color:{accent};
    filter:drop-shadow(0 0 8px {accent}33);
}}
.logo-name{{
    font-size:17px;
    font-weight:700;
    letter-spacing:4px;
    color:{accent};
    opacity:.85;
    text-transform:uppercase;
}}

/* ── Clock ── */
.clock{{
    text-align:center;
    margin-bottom:16px;
}}
.clock-time{{
    font-size:72px;
    font-weight:200;
    color:{text_main};
    letter-spacing:-2px;
    line-height:1;
}}
.clock-date{{
    font-size:11px;
    color:{text_dim};
    margin-top:4px;
    letter-spacing:2px;
    text-transform:uppercase;
}}

/* ── Greeting ── */
.greeting{{
    text-align:center;
    font-size:15px;
    color:{text_dim};
    margin-bottom:10px;
    font-weight:400;
    letter-spacing:0.03em;
}}

/* ── Weather ── */
.weather-widget{{
    display:flex;
    align-items:center;
    justify-content:center;
    gap:8px;
    margin-top:12px;
    padding-top:8px;
    font-size:13px;
    color:{text_dim};
}}

/* ── Divider ── */
.divider{{
    height:1px;
    background:{divider};
    margin:14px 0 16px;
}}

/* ── Opal Discovery Label ── */
.opal-label{{
    text-align:center;
    font-size:11px;
    letter-spacing:0.18em;
    color:{text_sub};
    font-weight:600;
    text-transform:uppercase;
    margin-bottom:10px;
}}

/* ── Search ── */
.search-wrap{{
    position:relative;
    margin-bottom:20px;
}}
.search-icon{{
    position:absolute;
    left:18px;
    top:50%;
    transform:translateY(calc(-50% - 3px));
    color:{text_sub};
    font-size:23px;
    line-height:1;
    pointer-events:none;
    user-select:none;
}}
.search-opal-icon{{
    position:absolute;
    right:18px;
    top:50%;
    transform:translateY(-50%);
    color:{accent};
    font-size:14px;
    font-weight:700;
    pointer-events:none;
    user-select:none;
}}
.search{{
    display:block;
    width:100%;
    background:{input_bg};
    border:1px solid {input_bd};
    border-radius:24px;
    padding:16px 52px;
    font-size:16px;
    font-family:inherit;
    color:{text_main};
    outline:none;
    transition:all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}}
.search::placeholder{{
    color:{input_ph}}}
.search:focus{{
    border-color:{accent};
    background:{glass2};
    box-shadow:0 0 0 3px {accent}1a;
}}

/* ── Bookmarks ── */
.bm-grid{{
    display:flex;
    flex-wrap:wrap;
    justify-content:center;
    position:relative;
    height:88px;
    max-height:88px;
    overflow-y:auto;
    align-content:flex-start;
    gap:12px;
}}
.bm-grid-empty{{height:auto;max-height:none;}}
.bm-heading{{
    position:absolute;
    top:-25px;
    right:0;
    display:flex;
    align-items:center;
    justify-content:space-between;
    color:{text_sub};
    font-size:10px;
    letter-spacing:.14em;
    text-transform:uppercase;
    z-index:2;
}}
.bm-heading button,.bm-actions button{{
    border:1px solid {bm_bd};
    border-radius:7px;
    background:{bm_bg};
    color:{text_main};
    padding:4px 8px;
    cursor:pointer;
}}
.bm-item{{
    position:relative;
    display:flex;
    flex:0 0 84px;
    flex-direction:column;
    align-items:center;
    width:84px;
    height:88px;
    gap:4px;
}}
.bm-actions{{display:none;gap:3px}}
.bm-editing .bm-actions{{
    position:absolute;
    top:2px;
    right:2px;
    display:flex;
    flex-direction:column;
}}
.bm-actions button{{width:18px;height:18px;padding:0;font-size:11px;}}
.bm-actions button:hover,.bm-heading button:hover{{border-color:{bm_hover}}}
.bm-card{{
    display:flex;
    flex:0 0 88px;
    flex-direction:column;
    align-items:center;
    gap:8px;
    width:84px;
    height:88px;
    background:{bm_bg};
    border:1px solid {bm_bd};
    border-radius:14px;
    padding:14px 8px 10px;
    cursor:pointer;
    text-align:center;
    text-decoration:none;
    color:inherit;
    transition:all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}}
.bm-card:hover{{
    border-color:{bm_hover};
    transform:translateY(-3px) scale(1.02);
    background:rgba(255,255,255,0.06);
    box-shadow:0 8px 24px rgba(0,0,0,0.15);
}}
.bm-icon-wrap{{
    width:40px;
    height:40px;
    border-radius:12px;
    background:{divider};
    display:flex;
    align-items:center;
    justify-content:center;
}}
.bm-icon{{
    font-size:18px;
    font-weight:700;
    color:{bm_ltr};
}}
.bm-icon-img{{
    width:24px;
    height:24px;
    object-fit:contain;
    border-radius:4px;
}}
.bm-title{{
    display:block;
    width:100%;
    font-size:10px;
    color:{text_dim};
    line-height:1.4;
    white-space:nowrap;
    text-overflow:ellipsis;
    overflow:hidden;
}}
.empty{{
    font-size:12px;
    color:{text_sub};
    font-style:italic;
    margin-top:10px;
}}
.empty-state{{
    width:100%;
    text-align:center;
}}
.empty-sub{{
    font-size:12px;
    color:{text_sub};
    margin-top:4px;
}}
.text-btn{{
    color:{accent};
    text-decoration:none;
    font-style:normal;
    cursor:pointer;
    border-bottom:1px dashed transparent;
    transition:border-color 0.2s, color 0.2s;
}}
.text-btn:hover{{
    border-bottom-color:{accent};
    color:{accent};
    filter:brightness(1.15);
}}

/* ── Quote Section ── */
.quote-section{{
    position:relative;
    z-index:10;
    margin-top:28px;
    text-align:center;
}}
.quote-text{{
    font-size:13px;
    color:{text_main};
    line-height:1.7;
    font-style:italic;
    max-width:520px;
    text-shadow:0 1px 4px rgba(0,0,0,0.65);
}}
.quote-author{{
    font-size:11px;
    color:{text_dim};
    margin-top:8px;
    letter-spacing:1px;
    text-shadow:0 1px 4px rgba(0,0,0,0.65);
}}

/* ── Bookmark context menu ── */
#bm-ctx{{
    display:none;
    position:fixed;
    z-index:999;
    background:{card_bg};
    border:1px solid {bm_bd};
    border-radius:10px;
    box-shadow:0 8px 32px rgba(0,0,0,0.25);
    padding:6px 0;
    min-width:170px;
    font-family:inherit;
    font-size:13px;
    backdrop-filter:blur(12px);
}}
#bm-ctx.visible{{display:block}}
.ctx-item{{
    display:flex;
    align-items:center;
    gap:10px;
    padding:10px 16px;
    cursor:pointer;
    color:{text_main};
    transition:background 0.15s;
    user-select:none;
}}
.ctx-item:hover{{background:{divider}}}
.ctx-item-icon{{
    font-size:13px;
    color:#e55555;
    flex-shrink:0;
}}
.ctx-item-label{{color:#e55555}}
</style>
</head>
<body>
<div id="wallpaper-carousel"></div>
<canvas id="bg"></canvas>
{video_html}

<div id="bm-ctx">
  <div class="ctx-item" id="ctx-remove">
    <span class="ctx-item-icon">✕</span>
    <span class="ctx-item-label">Remove bookmark</span>
  </div>
</div>

<div class="card">
  <div class="logo"><span class="logo-star">✦</span><span class="logo-name">NorthStar</span></div>
  <div class="clock">
    <div class="clock-time" id="ct">--:--</div>
    <div class="clock-date" id="cd"></div>
  </div>
  <div class="greeting">{_greeting}</div>
  <div class="divider"></div>
  <div class="opal-label">{_html_mod.escape(selected_search_name)} Search</div>
  <div class="search-wrap">
    <span class="search-icon">⌕</span>
    <input class="search" id="sq" type="text" placeholder="Search or enter address…" aria-label="Search or enter an address" autocomplete="off" autofocus
           onkeydown="if(event.key==='Enter'){{var q=encodeURIComponent(this.value);window.location.href='{_se_js}'.replace('__Q__',q)}}">
    <span class="search-opal-icon">◈</span>
  </div>
  {bm_section}
  <div class="weather-widget">
    <span class="weather-icon"></span>
    <span class="weather-text"></span>
  </div>
</div>

<div class="quote-section">
  <p class="quote-text" id="qt">"{_html_mod.escape(_quote_text)}"</p>
  <p class="quote-author" id="qa">— {_html_mod.escape(_quote_author)}</p>
</div>

<script>
(function(){{
  var v = document.getElementById('wallpaper-video');
  if (v) {{ v.play().catch(function(){{}}); }}
}})();
{get_background_js(bg_style, line_col, dot_col, dark_mode)}

/* ── Wallpaper Carousel ───────────────────────────────────────────────────── */
(function(){{
  var WALLPAPER_INDICES = {wallpaper_indices_js};
  var WALLPAPER_MODE = '{wallpaper_mode}';
  var SLIDE_DURATION = 30000; // 30 seconds per slide
  var currentIndex = 0;
  var carousel = document.getElementById('wallpaper-carousel');
  var preloadedImage = null;

  // Preload images for smooth transitions
  function preloadImage(src) {{
    preloadedImage = new Image();
    preloadedImage.src = src;
  }}

  if (WALLPAPER_MODE === 'carousel' && WALLPAPER_INDICES.length > 0) {{
    // Keep inactive slides unloaded to avoid reading the entire wallpaper set.
    WALLPAPER_INDICES.forEach(function(index, i) {{
      var slide = document.createElement('div');
      slide.className = 'wallpaper-slide' + (i === 0 ? ' active' : '');
      if (i === 0) {{
        slide.style.backgroundImage = 'url(northstar://wallpaper/' + index + ')';
      }}
      carousel.appendChild(slide);
    }});

    // Start carousel
    if (WALLPAPER_INDICES.length > 1) {{
      function nextSlide() {{
        var slides = carousel.querySelectorAll('.wallpaper-slide');
        slides[currentIndex].classList.remove('active');
        currentIndex = (currentIndex + 1) % slides.length;
        slides[currentIndex].style.backgroundImage =
          'url(northstar://wallpaper/' + WALLPAPER_INDICES[currentIndex] + ')';
        slides[currentIndex].classList.add('active');
        preloadImage(
          'northstar://wallpaper/' + WALLPAPER_INDICES[(currentIndex + 1) % slides.length]
        );
      }}
      preloadImage('northstar://wallpaper/' + WALLPAPER_INDICES[1]);
      setInterval(nextSlide, SLIDE_DURATION);
    }}
  }}
}})();

/* ── Clock ────────────────────────────────────────────────────────────────── */
(function(){{
  var D=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  var M=['January','February','March','April','May','June','July','August','September','October','November','December'];
  var ct=document.getElementById('ct');
  var cd=document.getElementById('cd');
  var prevMin=-1;

  function p(n){{return n<10?'0'+n:String(n)}}

  function tick(){{
    var now=new Date();
    var h=now.getHours(), m=now.getMinutes();
    ct.textContent=p(h)+':'+p(m);
    if(m!==prevMin){{
      prevMin=m;
      cd.textContent=D[now.getDay()]+', '+M[now.getMonth()]+' '+now.getDate()+', '+now.getFullYear();
    }}
  }}

  tick();

  var now=new Date();
  var msToNextMin=(60-now.getSeconds())*1000-now.getMilliseconds();
  setTimeout(function(){{tick();setInterval(tick,60000);}},msToNextMin);

  document.getElementById('sq').focus();
}})();

/* ── New-tab bookmark shortcut manager ────────────────────────────────────── */
(function(){{
  var editButton = document.getElementById('bm-edit');
  if (!editButton) return;
  editButton.addEventListener('click', function() {{
    var editing = document.body.classList.toggle('bm-editing');
    editButton.textContent = editing ? 'Done' : 'Manage';
    editButton.setAttribute('aria-pressed', String(editing));
  }});
  document.querySelectorAll('[data-move]').forEach(function(button) {{
    button.addEventListener('click', function() {{
      window.location.href = 'northstar://move-bookmark?url=' +
        encodeURIComponent(button.getAttribute('data-url')) +
        '&direction=' + button.getAttribute('data-move');
    }});
  }});
  document.querySelectorAll('[data-remove]').forEach(function(button) {{
    button.addEventListener('click', function() {{
      window.location.href = 'northstar://remove-bookmark?url=' +
        encodeURIComponent(button.getAttribute('data-remove'));
    }});
  }});
}})();

/* ── Bookmark right-click context menu ────────────────────────────────────── */
(function(){{
  var menu = document.getElementById('bm-ctx');
  var removeBtn = document.getElementById('ctx-remove');
  var targetUrl = '';


  document.querySelectorAll('.bm-card').forEach(function(card){{
    card.addEventListener('contextmenu', function(e){{
      e.preventDefault();
      targetUrl = card.getAttribute('href');
      var x = e.clientX, y = e.clientY;
      var mw = 170, mh = 48;
      if(x + mw > window.innerWidth) x = window.innerWidth - mw - 8;
      if(y + mh > window.innerHeight) y = window.innerHeight - mh - 8;
      menu.style.left = x + 'px';
      menu.style.top = y + 'px';
      menu.classList.add('visible');
    }});
  }});

  removeBtn.addEventListener('click', function(){{
    menu.classList.remove('visible');
    if(targetUrl)
      window.location.href = 'northstar://remove-bookmark?url=' + encodeURIComponent(targetUrl);
  }});

  document.addEventListener('click', function(e){{
    if(!menu.contains(e.target)) menu.classList.remove('visible');
  }});

  document.addEventListener('scroll', function(){{ menu.classList.remove('visible'); }}, true);
}})();
</script>
</body>
</html>"""

    _newtab_cache[cache_key] = html
    _startup_cache.put(_disk_key, html)
    return html

def _invalidate_newtab_cache():
    """Call whenever bookmarks or dark-mode changes."""
    _newtab_cache.clear()
    _startup_cache.invalidate()   # wipe disk cache so stale HTML isn't served


# ─────────────────────────────────────────────
#  POPUP & NAVIGATION POLICY
# ─────────────────────────────────────────────
class PopupPolicyManager:
    """Centralized manager for determining if a popup/new-window should be allowed.
    
    Uses lightweight trust heuristics:
    1.  User Interaction: Was the request preceded by a recent click/keypress?
    2.  Window Type: Is it a standard browser tab/window or a suspicious background popup?
    """
    INTERACTION_THRESHOLD_MS = 1200  # 1.2s grace period after user action

    def __init__(self):
        self._last_interaction_ts = 0.0

    def record_interaction(self):
        """Called on mouse/key events to mark the session as user-active."""
        self._last_interaction_ts = time.time()

    def is_user_active(self) -> bool:
        """Check if the user interacted with the browser very recently."""
        return (time.time() - self._last_interaction_ts) * 1000 < self.INTERACTION_THRESHOLD_MS

    def should_allow_popup(self, window_type: QWebEnginePage.WebWindowType) -> bool:
        """Decide if a new window/tab request should proceed."""
        # 1. Always allow if triggered by recent user interaction (click/key)
        if self.is_user_active():
            return True
            
        # 2. Allow standard background tabs if they seem legitimate (e.g. for downloads)
        # Some sites use hidden background tabs to trigger downloads without navigation.
        if window_type == QWebEnginePage.WebWindowType.WebBrowserBackgroundTab:
            return True
            
        # 3. Default: block suspicious automatic popups
        return False


class ClipboardBridge(QObject):
    """Exposes host-side clipboard operations to page JS via QWebChannel.

    Unlike navigator.clipboard / execCommand, this path is NOT subject to
    Chromium's clipboard permission model, user-gesture requirements, or the
    page's Content-Security-Policy — so it works reliably on sites like
    ChatGPT whose copy buttons otherwise silently fail under QtWebEngine.
    """
    @pyqtSlot(str)
    def copy(self, text):
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(text if text is not None else "")
        except Exception:
            pass

    @pyqtSlot(result=str)
    def paste(self):
        try:
            from PyQt6.QtWidgets import QApplication
            return QApplication.clipboard().text()
        except Exception:
            return ""


class _RequestLogger(QWebEngineUrlRequestInterceptor):
    """Print every network request a website makes (and how it resolved).

    Installed on every main browser page so the user can watch the exact
    requests pages send right in the terminal.  This is read-only: it only
    prints and never blocks or rewrites the request.
    """
    def interceptRequest(self, info):
        try:
            url = info.requestUrl().toString()
            resource = info.resourceType().name      # e.g. ResourceTypeScript
            nav = info.navigationType().name        # e.g. NavigationTypeLink
            method = info.requestMethod().data().decode("utf-8", "replace")
            print(f"[req] {method:<6} {nav:<21} {resource:<24} {url}")
        except Exception:
            print(f"[req] {info.requestUrl().toString()}")


class NorthStarPage(QWebEnginePage):
    """Custom QWebEnginePage to handle smarter popup/new-tab behavior."""
    new_window_requested = pyqtSignal(str)  # emits URL that should open in a new tab

    def __init__(self, profile, parent_view, policy_manager):
        super().__init__(profile, parent_view)
        self._view = parent_view
        self._profile = profile
        self.policy_manager = policy_manager
        self._request_logger = _RequestLogger(self)
        try:
            self.setUrlRequestInterceptor(self._request_logger)
        except Exception:
            pass
        if parent_view:
            self.setParent(parent_view)

        # Expose the host clipboard to page JS through a QWebChannel.  The page
        # shim calls window.northstar.copy(text) — CSP/gesture/permission-proof.
        self._clip_bridge = ClipboardBridge(self)
        self._clip_channel = QWebChannel(self)
        self._clip_channel.registerObject("northstar", self._clip_bridge)
        try:
            self.setWebChannel(self._clip_channel)
        except Exception:
            pass

    def shutdown(self):
        """Tear down renderer-facing resources so the page can be GC'd cleanly.

        Called when its tab is closing.  Nulls the web channel (which holds a
        registered bridge the renderer can keep alive) and the request logger,
        then drops the explicit page parent so nothing lingers after deleteLater.
        """
        try:
            self.setWebChannel(None)
        except Exception:
            pass
        self._clip_channel = None
        self._clip_bridge = None
        self._request_logger = None
        try:
            self.setParent(None)
        except Exception:
            pass

    def javaScriptConsoleMessage(self, level, msg, line, src):
        # Always surface [nsclip] diagnostic traces; everything else only in debug.
        if "[nsclip]" in msg or _DEBUG:
            levels = {0: "I", 1: "W", 2: "E"}
            print(f"[JS:{levels.get(level.value, '?')}] {msg}")

    def createWindow(self, type: QWebEnginePage.WebWindowType) -> QWebEnginePage:
        """Called when a page wants to open a new tab/window (target="_blank",
        window.open, etc.). Returns a silent page that captures the first
        navigation URL and emits it via new_window_requested so the main
        window can open a real tab."""
        class _CapturePage(QWebEnginePage):
            def acceptNavigationRequest(self, url, nav_type, is_main):
                if is_main:
                    url_str = url.toString()
                    if url_str:
                        QTimer.singleShot(0, lambda u=url_str: self.parent().new_window_requested.emit(u))
                    return False
                return True
        cap = _CapturePage(self._profile, self)
        return cap

    def acceptNavigationRequest(self, url: QUrl, _type: QWebEnginePage.NavigationType, isMainFrame: bool) -> bool:
        """Track interaction intent to distinguish user-initiated navigation."""
        if _type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            self.policy_manager.record_interaction()
        return super().acceptNavigationRequest(url, _type, isMainFrame)

    def featurePermissionRequestCanceled(self, url: QUrl, feature: QWebEnginePage.Feature):
        pass

    # NOTE: featurePermissionRequested is intentionally NOT overridden.
    # Overriding it (even with super()) installs a PyQt6 C++ trampoline that
    # changes the Mojo IPC dispatch and causes renderer crashes when sites use
    # unrecognized Permissions Policy features (e.g. 'speaker' in Google Meet
    # iframes). Camera/mic/notification permissions are handled by BrowserTab
    # connecting to the permissionRequested signal directly.


# ─────────────────────────────────────────────
#  BROWSER TAB
# ─────────────────────────────────────────────
class BrowserTab(QWidget):
    title_changed             = pyqtSignal(str)
    url_changed               = pyqtSignal(str)
    load_progress             = pyqtSignal(int)
    remove_bookmark_requested = pyqtSignal(str)   # emits bookmark URL to remove
    move_bookmark_requested = pyqtSignal(str, str)
    import_bookmarks_requested = pyqtSignal()     # user clicked "Import Bookmarks" in newtab
    clear_bookmarks_requested = pyqtSignal()
    new_window_requested      = pyqtSignal(str)   # website requested a new tab with this URL
    icon_changed              = pyqtSignal(QPixmap)   # emits favicon pixmap

    def __init__(self, profile, policy_manager=None, parent=None):
        super().__init__(parent)
        self.setObjectName("BrowserTab")
        self.setMouseTracking(True)
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        self.view = QWebEngineView()
        self.view.setMouseTracking(True)
        self.view.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.view.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        
        # Use our custom page with the shared policy manager
        self.policy_manager = policy_manager or PopupPolicyManager()
        page = NorthStarPage(profile, self.view, self.policy_manager)
        self.view.setPage(page)
        
        self.view.titleChanged.connect(self.title_changed)
        self.view.urlChanged.connect(lambda url: self.url_changed.emit(url.toString()))
        self.view.loadProgress.connect(self.load_progress)
        self.view.loadFinished.connect(self._on_load_finished)
        self.view.iconChanged.connect(lambda icon: self.icon_changed.emit(icon.pixmap(24,24)))
        page.fullScreenRequested.connect(self._on_fullscreen_requested)
        page.navigationRequested.connect(self._on_nav_requested)
        page.featurePermissionRequested.connect(self._on_feature_permission)
        page.permissionRequested.connect(self._on_permission_requested)
        page.new_window_requested.connect(self.new_window_requested.emit)
        
        # Track raw input events for finer-grained interaction detection
        self.view.installEventFilter(self)
        
        layout.addWidget(self.view)

    def eventFilter(self, obj, event):
        """Intercept input events on the web view to track user activity."""
        if obj == self.view:
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
                self.policy_manager.record_interaction()
            # Block F12 (DevTools) if disabled in settings
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_F12:
                win = self.window()
                if win and hasattr(win, '_settings') and not win._settings.get("devtools_enabled", True):
                    return True
        return super().eventFilter(obj, event)

    def _on_nav_requested(self, request):
        """Intercept northstar:// search URLs before the engine tries to load them."""
        url = request.url().toString()
        if url.startswith("northstar://remove-bookmark"):
            request.reject()
            params = parse_qs(urlparse(url).query)
            bm_url = params.get("url", [""])[0]
            if bm_url:
                self.remove_bookmark_requested.emit(bm_url)
            return
        if url.startswith("northstar://move-bookmark"):
            request.reject()
            params = parse_qs(urlparse(url).query)
            bm_url = params.get("url", [""])[0]
            direction = params.get("direction", [""])[0]
            if bm_url and direction in ("up", "down"):
                self.move_bookmark_requested.emit(bm_url, direction)
            return
        if url.startswith("northstar://import-bookmarks"):
            request.reject()
            self.import_bookmarks_requested.emit()
            return
        if url.startswith("northstar://clear-bookmarks"):
            request.reject()
            self.clear_bookmarks_requested.emit()
            return
        if url.startswith("northstar://search"):
            request.reject()
            params = parse_qs(urlparse(url).query)
            q = params.get("q", [""])[0].strip()
            if q:
                win = self.window()
                if hasattr(win, "_opal_search"):
                    QTimer.singleShot(0, lambda: win._opal_search(q, self))
            return
        if url.startswith("opal://discovery/images"):
            request.reject()
            params = parse_qs(urlparse(url).query)
            q = params.get("q", [""])[0].strip()
            if q:
                win = self.window()
                if hasattr(win, "_opal_show_images"):
                    QTimer.singleShot(0, lambda: win._opal_show_images(q, self))
            return
        # All other navigations: do nothing, PyQt6 accepts by default

    def _on_fullscreen_requested(self, request):
        request.accept()
        win = self.window()
        if hasattr(win,'_enter_fullscreen'):
            if request.toggleOn(): win._enter_fullscreen()
            else: win._exit_fullscreen()

    def _on_load_finished(self, ok):
        if not ok:
            return

    def navigate(self, url, bookmarks=None, search_engine_url=None, dark_mode=False):
        try:
            if not url.strip(): return
            if url == NORTHSTAR_HOME or url.strip("/") == "northstar://newtab":
                global _global_bookmarks, _global_dark_mode, _global_search_engine_url
                _global_bookmarks = bookmarks or []
                _global_dark_mode = dark_mode
                _global_search_engine_url = _resolve_search_url(search_engine_url)
                self.view.load(QUrl(NORTHSTAR_HOME)); return
            parsed = urlparse(url)
            if parsed.scheme in ("http","https","file","ftp","northstar","opal","chrome","about","data","javascript"):
                qurl = QUrl(url)
            elif "." in url and " " not in url:
                qurl = QUrl("https://" + url)
            else:
                tmpl = _resolve_search_url(search_engine_url)
                qurl = QUrl(tmpl.format(quote(url)))
            self.view.load(qurl)
        except Exception as _nav_err:
            try:
                _crash_msg = f"[NorthStar] BrowserTab.navigate error: {_nav_err}\n{_traceback_mod.format_exc()}"
                sys.stderr.write(_crash_msg + "\n")
                sys.stderr.flush()
                with open(_CRASH_LOG, "a", encoding="utf-8") as _f:
                    _f.write(_crash_msg + "\n")
            except Exception:
                pass

    def zoom_in(self):   self.view.setZoomFactor(min(self.view.zoomFactor()+0.1, 3.0))
    def zoom_out(self):  self.view.setZoomFactor(max(self.view.zoomFactor()-0.1, 0.3))
    def zoom_reset(self):self.view.setZoomFactor(1.0)

    def _on_feature_permission(self, url, feature):
        if feature not in _PERMISSION_LABELS:
            return
        # Auto-grant safe permissions (clipboard) so copy buttons on sites
        # like ChatGPT/Gemini work without a per-origin prompt.
        if feature in _AUTO_GRANT_PERMISSIONS:
            try:
                self.view.page().setFeaturePermission(
                    url, feature,
                    QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                )
            except Exception:
                pass
            return
        try:
            parsed = urlparse(url.toString())
            origin = f"{parsed.scheme}://{_root_domain(parsed.netloc)}"
            saved = _perm_manager.get_saved(origin, feature)
            if saved is not None:
                self.view.page().setFeaturePermission(
                    url, feature,
                    QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                    if saved else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
                )
                return
            win = self.window()
            if not win:
                self.view.page().setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
                return
            toast = PermissionToast(origin, feature, win)
            def on_decided(allow, remember):
                try:
                    if remember:
                        _perm_manager.save_decision(origin, feature, allow)
                    self.view.page().setFeaturePermission(
                        url, feature,
                        QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                        if allow else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
                    )
                except Exception:
                    pass
            toast.decided.connect(on_decided)
            toast.show()
            QTimer.singleShot(0, toast._repin)
        except Exception:
            pass

    def _on_permission_requested(self, request):
        """Handle the newer permissionRequested signal (Qt6 6.8+)."""
        try:
            feature = request.permissionType()
            if feature not in _PERMISSION_LABELS:
                request.deny()
                return

            # Auto-grant safe permissions (clipboard) so copy buttons on sites
            # like ChatGPT/Gemini work without a per-origin prompt.
            if feature in _AUTO_GRANT_PERMISSIONS:
                try:
                    request.grant()
                except Exception:
                    pass
                return

            parsed = urlparse(request.origin().toString())
            origin = f"{parsed.scheme}://{_root_domain(parsed.netloc)}"
            url = request.origin()
            saved = _perm_manager.get_saved(origin, feature)
            if saved is not None:
                if saved:
                    request.grant()
                else:
                    request.deny()
                return

            win = self.window()
            if not win:
                request.deny()
                return

            # Store feature as int for setFeaturePermission compatibility
            feature_val = feature.value if hasattr(feature, 'value') else int(feature)

            toast = PermissionToast(origin, feature, win)
            def on_decided(allow, remember):
                try:
                    if remember:
                        _perm_manager.save_decision(origin, feature, allow)
                    self.view.page().setFeaturePermission(
                        url, feature_val,
                        QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                        if allow else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
                    )
                except Exception:
                    pass
            toast.decided.connect(on_decided)
            toast.show()
            QTimer.singleShot(0, toast._repin)
        except Exception as e:
            _log("PERM", f"Error in _on_permission_requested: {e}")


# ─────────────────────────────────────────────
#  STYLESHEET — OPTIMISED
#
#  The QSS is split into:
#    _BASE_QSS  — structural rules that never change (margins, radii, font-size…)
#    _theme_patch(dark, oled) — colour tokens that differ per mode.
#      dark/light tokens come from _theme_tokens() and are emitted by _theme_qss();
#      OLED Mode delegates to oled_theme.py (oled_qss_tokens + popup chrome).
#
#  _apply_style() now calls setStyleSheet once with base+patch concatenated.
#  Subsequent calls rebuild only the ~200-char patch, not 3 000 chars.
# ─────────────────────────────────────────────
_BASE_QSS_TEMPLATE = """
* { font-family: '__FONT__', 'Segoe UI Variable', 'SF Pro Display', sans-serif; outline: none; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTabWidget::pane { border: none; }
QTabBar { background: transparent; }
QTabBar::tab { height: 0px; width: 0px; padding: 0; border: none; }
#LoadProgress { background: transparent; border: none; }
#SidebarAdCount { font-size: 8pt; font-weight: 600; background: transparent; padding: 0; }
#TabScroll, #TabBtnContainer { background: transparent; border: none; }
#TabFav { font-size: 10pt; font-weight: 700; background: transparent; }
#TabLabel { font-size: 7pt; background: transparent; padding-bottom: 2px; }
#TabClose { background: transparent; border: none; border-radius: 4px; font-size: 10pt; font-weight: 400; padding: 0; }
#TabClose:hover { background: rgba(220,80,80,0.35); color: #ff6b6b; }
#AIStar { font-size: 14pt; }
#AITitle { font-size: 11pt; font-weight: 700; letter-spacing: 0.4px; }
#AIChat { font-size: 10pt; padding: 10px; line-height: 1.6; }
#AIInput { border-radius: 10px; padding: 8px 12px; font-size: 10pt; }
#AISendBtn { border: none; border-radius: 10px; padding: 8px 14px; font-size: 12pt; font-weight: 700; color: #ffffff; }
#AIClearBtn { background: transparent; border-radius: 7px; padding: 3px 10px; font-size: 9pt; }
#QuickBtn { border-radius: 8px; padding: 5px 8px; font-size: 9pt; }
#AIStatus { font-size: 9pt; }
#AIStatusInfo { font-size: 8pt; margin-left: 8px; }
#DlHeaderIcon { font-size: 12pt; }
#DlHeaderTitle { font-size: 11pt; font-weight: 700; letter-spacing: 0.4px; }
#DlDivider { border: none; }
#DlScroll { background: transparent; border: none; }
#DlList { background: transparent; }
#DlEmpty { font-size: 10pt; font-style: italic; padding: 24px; }
#DlClearBtn { background: transparent; border-radius: 7px; padding: 3px 10px; font-size: 9pt; }
#DownloadCard { border-radius: 10px; }
#DownloadCard:hover { border-color: rgba(100,120,200,0.35); }
#DownloadCardDone { border-radius: 10px; }
#DlIcon { font-size: 14pt; background: transparent; }
#DlName { font-size: 10pt; font-weight: 600; background: transparent; }
#DlMeta { font-size: 9pt; background: transparent; }
#DlPauseBtn { border-radius: 6px; font-size: 10pt; padding: 0; }
#DlOpenBtn { color: #ffffff; border: none; border-radius: 6px; font-size: 10pt; padding: 0; }
#DlOpenBtn:disabled { color: rgba(200,210,240,0.4); }
#DlFolderBtn { border-radius: 6px; font-size: 10pt; padding: 0; }
#DlBar { border-radius: 2px; border: none; }
#DlBar::chunk { border-radius: 2px; }
#BmBarBtn { background: transparent; border: none; border-radius: 6px; padding: 3px 9px; font-size: 10pt; }
QStatusBar { font-size: 9pt; }
#HoverStatusBar {
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 9pt;
    font-family: '__FONT__', 'Segoe UI Variable', sans-serif;
}
#PaletteContainer { border-radius: 16px; }
#PaletteSearch { border-radius: 11px; padding: 11px 16px; font-size: 11pt; }
#PaletteList { background: transparent; border: none; font-size: 10pt; }
#PaletteList::item { padding: 9px 8px; border-radius: 8px; }
#PaletteList::item:disabled { color: rgba(200,210,240,0.55); font-size: 8pt; font-weight: 700; padding-top: 12px; }
#SettingsHint { font-size: 9pt; background: transparent; }
#SettingsAction { border-radius: 8px; padding: 5px 10px; font-size: 9pt; }
#HistoryRange { border-radius: 8px; padding: 6px 10px; font-size: 9pt; }
QSplitter::handle { }
#PbEntryIcon { border-radius: 8px; font-size: 11pt; font-weight: 700; }
#PbError { color: #ff6b6b; font-size: 9pt; }
#SettingsSection { font-size: 8pt; font-weight: 700; letter-spacing: 2px; background: transparent; padding-top: 4px; }
#SettingsLabel { font-size: 10pt; background: transparent; }
#SettingsDropdown { border-radius: 8px; padding: 4px 10px; font-size: 10pt; text-align: left; }
#SettingsDropdown::menu-indicator { width: 0; }
#SettingsToggle { border-radius: 8px; padding: 3px 8px; font-size: 10pt; font-weight: 600; }
#HistoryRow { border-radius: 8px; }
#HistoryDateSep { font-size: 8pt; font-weight: 700; letter-spacing: 1.5px; background: transparent; padding: 8px 8px 2px 8px; }
#HistoryTime { font-size: 8pt; background: transparent; }
#FindBar { border-radius: 10px; }
#FindInput { border-radius: 8px; padding: 4px 10px; font-size: 10pt; }
#FindCount { font-size: 9pt; background: transparent; }
#FindNavBtn { border-radius: 6px; font-size: 10pt; }
#SSDeviceCard { border-radius: 10px; }
#SSPulse    { font-size: 10pt; background: transparent; }
#SSPulseOff { font-size: 10pt; background: transparent; }
#StarShareToast {
    border-radius: 12px;
    border: 1px solid #d1d5e0;
    background: #ffffff;
}
#ToastIcon  { font-size: 13pt; background: transparent; }
#ToastMsg   { font-size: 10pt; }
#ToastDetail{ font-size: 9pt; }
#ToastYes   { border: none; border-radius: 8px; padding: 0 14px; font-size: 10pt; font-weight: 600; color: #ffffff; }
#ToastNo    { border-radius: 8px; padding: 0 12px; font-size: 10pt; }
#ToastCd    { font-size: 9pt; }
#FernwaySlider::groove:horizontal { border: 1px solid rgba(255,255,255,0.08); height: 4px; background: rgba(255,255,255,0.05); border-radius: 2px; }
#FernwaySlider::handle:horizontal { background: #4fc3f7; border: none; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
#FernwayColorBtn { border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); }
#FernwayColorBtn:hover { border-color: rgba(255,255,255,0.3); }
#FernwayModeBtn { border-radius: 8px; padding: 6px 12px; font-size: 9pt; font-weight: 600; }
"""

def _base_qss() -> str:
    fw = get_fernway()
    font = fw.get("browser_font", "Segoe UI")
    return _BASE_QSS_TEMPLATE.replace("__FONT__", font)

def _theme_patch(dark: bool, oled: bool = False) -> str:
    """QSS colour patch for the browser chrome.

    OLED Mode short-circuits to the true-black/gold token set from
    oled_theme.py (plus popup chrome), leaving the standard theme intact.
    """
    if oled:
        fw = get_fernway()
        oled_tokens = oled_qss_tokens(fw)
        return _theme_qss(oled_tokens) + oled_popup_qss() + oled_toolbar_qss()
    return _theme_qss(_theme_tokens(dark, get_fernway()))


def _with_alpha(color: str, alpha: float) -> str:
    """Return *color* with its alpha channel forced to *alpha* (0.0-1.0).

    Accepts `rgba(r,g,b,a)`, `rgb(r,g,b)` and `#rrggbb` / `#rgb`. Anything
    unparseable is returned unchanged.
    """
    c = (color or "").strip()
    m = re.match(r"^rgba?\(\s*([^)]*)\)$", c, re.IGNORECASE)
    if m:
        parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
        while len(parts) < 3:
            parts.append("0")
        return f"rgba({parts[0]},{parts[1]},{parts[2]},{alpha:.2f})"
    if c.startswith("#"):
        h = c[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) >= 6:
            try:
                r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
                return f"rgba({r},{g},{b},{alpha:.2f})"
            except ValueError:
                pass
    return c


def _theme_tokens(dark: bool, fw) -> dict:
    # Base colors from Fernway
    accent_p = fw.get("accent_primary", "#4fc3f7")
    accent_s = fw.get("accent_secondary", "#9c6ff7")
    accent_t = fw.get("ambient_tertiary", "#d18ae8")
    bg_tint  = fw.get("background_tint", "rgba(8, 11, 20, 0.05)")
    
    # Derived transparency and effects
    opacity = fw.get("transparency_level", 0.88)
    glow_int = fw.get("glow_intensity", 0.5)
    blur_str = fw.get("blur_strength", 20)
    
    # Styles
    tab_style = fw.get("tab_style", "default")
    sidebar_style = fw.get("sidebar_style", "default")
    leo_style = fw.get("leo_appearance", "glass")
    
    if dark:
        bg_base = "06070d"
        glass=f"rgba(14,16,28,{opacity})"; glass2=f"rgba(22,24,42,{min(1.0, opacity+0.08)})"
        hover="rgba(35,38,64,0.90)"; active="rgba(48,52,88,0.95)"
        border=f"rgba(100,120,200,{0.1 + 0.2 * glow_int})"; glow=f"rgba(79,195,247,{0.2 + 0.6 * glow_int})"
        accent=accent_p; accent2=accent_s; accent3=accent_t
        text="#e8edf8"; text2="rgba(200,210,240,0.55)"; input_bg="rgba(10,12,22,0.80)"
        scroll=f"rgba(79,195,247,{0.1 + 0.3 * glow_int})"
        dl_done_bg="rgba(20,40,28,0.80)"; dl_done_bdr="rgba(79,195,130,0.40)"
        logo_grad=f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {accent},stop:0.5 {accent2},stop:1 {accent3})"
        menu_bg="rgba(22,24,42,0.80)"
    else:
        bg_base = "e8ecf5"
        glass=f"rgba(255,255,255,{opacity})"; glass2=f"rgba(240,242,255,{min(1.0, opacity+0.12)})"
        hover="rgba(220,225,255,0.85)"; active="rgba(200,208,255,0.92)"
        border=f"rgba(80,100,200,{0.1 + 0.15 * glow_int})"; glow=f"rgba(79,119,189,{0.2 + 0.5 * glow_int})"
        accent=accent_p; accent2=accent_s; accent3=accent_t
        text="#0e1120"; text2="rgba(20,30,80,0.50)"; input_bg="rgba(255,255,255,0.80)"
        scroll=f"rgba(79,119,189,{0.1 + 0.25 * glow_int})"
        dl_done_bg="rgba(230,255,240,0.85)"; dl_done_bdr="rgba(30,160,80,0.35)"
        logo_grad=f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {accent},stop:0.5 {accent2},stop:1 {accent3})"
        menu_bg="rgba(240,242,255,0.80)"

    grad = f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {accent},stop:1 {accent2})"
    
    toolbar_bg = glass
    
    # Fixed toolbar opacity at 0.875
    if dark:
        toolbar_bg = "rgba(14,16,28,0.8)"
    else:
        toolbar_bg = "rgba(255,255,255,0.8)"
    # The bookmarks bar mirrors the toolbar hue but stays at 80% opacity.
    bookmarks_bar_bg = _with_alpha(toolbar_bg, 0.80)
    # ── TAB STYLE PATCH ──────────────────────────────────
    tab_radius = "10px" if tab_style == "default" else "4px" if tab_style == "compact" else "14px"
    tab_border = border if tab_style != "glass" else "1px solid rgba(255,255,255,0.12)"
    
    # ── SIDEBAR STYLE PATCH ──────────────────────────────
    if dark:
        _sidebar_glass = "rgba(14,16,28,0.8)"
    else:
        _sidebar_glass = "rgba(255,255,255,0.8)"
    sidebar_bg = _sidebar_glass if sidebar_style == "default" else "transparent" if sidebar_style == "minimal" else glass2
    sidebar_border = f"1px solid {border}" if sidebar_style != "minimal" else "none"
    sidebar_qss = f"background:{sidebar_bg};border-right:{sidebar_border};"
    
    if sidebar_style == "floating":
        sidebar_qss = f"""
            background:{_sidebar_glass}; 
            border-right:1px solid {border}; 
            border-top-right-radius:22px;
            border-bottom-right-radius:22px;
            margin:0;
        """
    
    # ── LEO STYLE PATCH ──────────────────────────────────
    leo_bg = glass if leo_style == "glass" else f"#{bg_base}" if leo_style == "solid" else "transparent"
    leo_border = f"1px solid {border}" if leo_style != "minimal" else "none"

    return {
        "bg_base": bg_base,
        "glass": glass, "glass2": glass2,
        "hover": hover, "active": active,
        "border": border, "glow": glow,
        "accent": accent, "accent2": accent2, "accent3": accent3,
        "text": text, "text2": text2,
        "input_bg": input_bg, "scroll": scroll,
        "dl_done_bg": dl_done_bg, "dl_done_bdr": dl_done_bdr,
        "logo_grad": logo_grad, "grad": grad,
        "toolbar_bg": toolbar_bg,
        "menu_bg": menu_bg,
        "bookmarks_bar_bg": bookmarks_bar_bg,
        "tab_radius": tab_radius, "tab_border": tab_border,
        "sidebar_qss": sidebar_qss,
        "leo_bg": leo_bg, "leo_border": leo_border,
    }


def _theme_qss(t: dict) -> str:
    bg_base = t["bg_base"]; glass = t["glass"]; glass2 = t["glass2"]
    hover = t["hover"]; active = t["active"]; border = t["border"]; glow = t["glow"]
    accent = t["accent"]; accent2 = t["accent2"]; accent3 = t["accent3"]
    text = t["text"]; text2 = t["text2"]; input_bg = t["input_bg"]; scroll = t["scroll"]
    dl_done_bg = t["dl_done_bg"]; dl_done_bdr = t["dl_done_bdr"]
    logo_grad = t["logo_grad"]; grad = t["grad"]; toolbar_bg = t["toolbar_bg"]
    menu_bg = t.get("menu_bg") or _with_alpha(toolbar_bg, 0.80)
    bookmarks_bar_bg = t.get("bookmarks_bar_bg") or _with_alpha(toolbar_bg, 0.80)
    tab_radius = t["tab_radius"]; tab_border = t["tab_border"]
    sidebar_qss = t["sidebar_qss"]; leo_bg = t["leo_bg"]; leo_border = t["leo_border"]

    stylesheet = f"""
QMainWindow,#ContentCol{{background:#{bg_base};}}
QPushButton:focus,QComboBox:focus,QListWidget:focus{{border:1px solid {glow};}}
#ContentCol{{border-radius:0px;}}
#BrowserTab{{background:#{bg_base};}}
QMainWindow::separator{{background:{border};width:1px;height:1px;}}
QScrollBar::handle:vertical{{background:{scroll};}}
#Sidebar{{{sidebar_qss}}}
#SidebarDiv{{background:{border};max-height:1px;}}
#SidebarLogo{{background:{logo_grad};color:#fff;border:none;border-radius:10px;font-size:12pt;font-weight:700;}}
#SidebarAdCount{{color:{accent};}}
#NewTabBtn{{background:{glass2};color:{accent};border:1px solid {glow};border-radius:8px;font-size:12pt;font-weight:300;}}
#NewTabBtn:hover{{color:#fff;border-color:{accent};}}
#TabCard{{background:{glass2};border:1px solid {tab_border};border-radius:{tab_radius};}}
#TabCard:hover{{border-color:{glow};}}
#TabCardActive{{background:{active};border:2px solid {glow};border-radius:{tab_radius};}}
#TabCard #FluidOverlay{{background:{hover};border-radius:{tab_radius};}}
#TabFav,#TabLabel{{color:{text};font-size:8pt;}}
#TabLabel{{color:{text2};}}
#TabClose{{color:{text2};font-size:14pt;font-weight:700;background:#d63b3b;border:none;border-radius:{tab_radius};}}
#TabClose:hover{{color:#fff;background:#e84545;border-radius:{tab_radius};}}
#SidebarBtn{{background:transparent;color:{text2};border:1px solid transparent;border-radius:8px;font-size:11pt;}}
#SidebarBtn[expanded="true"]{{text-align:left;padding-left:10px;font-size:9pt;}}
#SidebarBtn:hover{{color:{text};border-color:{border};}}
#SidebarBtn:pressed{{background:{active};color:{accent};}}
#SidebarBtn:focus,#NavBtn:focus,#BmBtn:focus,#WndMin:focus,#WndMax:focus,#WndClose:focus{{
    border:1px solid {glow};
}}
#SidebarNavBtn{{background:transparent;color:{text2};border:1px solid transparent;border-radius:8px;font-size:11pt;text-align:left;}}
#SidebarNavBtn:hover{{color:{text};background:{hover};}}
#SidebarNavBtn:pressed{{background:{active};color:{accent};}}
#SidebarTopNav{{background:transparent;}}
#SidebarBotNav{{background:transparent;}}
#TabLabel{{color:{text2};font-size:11px;}}
#TabSpinner{{color:{accent};font-size:14pt;}}
#TabClose{{color:{text2};font-size:9pt;background:transparent;border:none;border-radius:{tab_radius};}}
#TabClose:hover{{color:#fff;background:rgba(220,80,80,0.4);border-radius:{tab_radius};}}
#FluidOverlay{{background:{hover};border-radius:8px;}}
#SidebarLogo #FluidOverlay{{background:rgba(255,255,255,0.15);border-radius:10px;}}
#NewTabBtn #FluidOverlay{{background:{active};border-radius:8px;}}
#Toolbar{{background:{toolbar_bg};border-bottom:1px solid {border};}}
#BookmarksBar{{background:{bookmarks_bar_bg};}}
#NavBtn{{background:transparent;color:{text2};border:none;border-radius:9px;font-size:12pt;}}
#NavBtn:hover{{background:{hover};color:{text};}}
#NavBtn:pressed{{background:{active};color:{accent};}}
#BmBtn{{background:transparent;color:{text2};border:none;border-radius:9px;font-size:13pt;}}
#BmBtn:hover{{background:{hover};color:{accent3};}}
#WndMin,#WndMax{{background:transparent;color:{text2};border:none;border-radius:8px;font-size:10pt;}}
#WndMin:hover,#WndMax:hover{{background:{hover};color:{text};}}
#WndClose{{background:transparent;color:{text2};border:none;border-radius:8px;font-size:10pt;}}
#WndClose:hover{{background:qradialgradient(cx:0.5,cy:0.5,radius:0.5,fx:0.5,fy:0.5,stop:0 rgba(255,60,60,0.95),stop:0.55 rgba(220,40,40,0.85),stop:1 rgba(160,20,20,0.60));color:#fff;border:1px solid rgba(255,100,100,0.45);}}
#AddressBar{{background:{input_bg};color:{text};border:1px solid {border};border-radius:11px;padding:7px 14px;font-size:10pt;}}
#AddressBar:focus{{border:2px solid {glow};background:{glass2};}}
#AddressBar:hover:!focus{{border-color:{glow};}}
#LoadProgress::chunk{{background:{grad};}}
#AIPanel{{background:{leo_bg};border-left:{leo_border};}}
#AIStar{{color:{accent};}}
#AITitle{{color:{text};}}
#AIChat{{background:{input_bg};color:{text};border:1px solid {border};border-radius:10px;}}
#AIInput{{background:{input_bg};color:{text};border:1px solid {border};}}
#AIInput:focus{{border-color:{glow};}}
#AISendBtn{{background:{grad};}}
#AISendBtn:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {accent2},stop:1 {accent3});}}
#AIClearBtn{{color:{text2};border:1px solid {border};}}
#AIClearBtn:hover{{background:{hover};color:{text};}}
#QuickBtn{{background:{glass2};color:{text2};border:1px solid {border};}}
#QuickBtn:hover{{background:{hover};color:{accent};border-color:{glow};}}
#AIStatus{{color:{text2};}}
#AIStatusInfo{{color:{text2};}}
#DownloadsPanel{{background:{glass2};border:2px solid {glow};border-radius:14px;}}
#DlHeaderIcon{{color:{accent};}}
#DlHeaderTitle{{color:{text};}}
#DlDivider{{background:{border};}}
#DlEmpty{{color:{text2};}}
#DlClearBtn{{color:{text2};border:1px solid {border};}}
#DlClearBtn:hover{{background:{hover};color:{text};}}
#DownloadCard{{background:{glass2};border:1px solid {border};}}
#DownloadCardDone{{background:{dl_done_bg};border:1px solid {dl_done_bdr};}}
#DlName{{color:{text};}}
#DlMeta{{color:{text2};}}
#DlPauseBtn{{background:{hover};color:{text};border:1px solid {border};}}
#DlPauseBtn:hover{{background:{active};border-color:{glow};}}
#DlPauseBtn:disabled{{color:{text2};}}
#DlOpenBtn{{background:{grad};}}
#DlOpenBtn:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {accent2},stop:1 {accent3});}}
#DlOpenBtn:disabled{{background:{hover};}}
#DlFolderBtn{{background:{hover};color:{text2};border:1px solid {border};}}
#DlFolderBtn:hover{{background:{active};color:{text};border-color:{glow};}}
#DlBar{{background:{border};}}
#DlBar::chunk{{background:{grad};}}
#BmBarBtn:hover{{background:{glass2};color:{text};}}
QStatusBar{{background:{glass};border-top:1px solid {border};color:{text2};}}
#HoverStatusBar{{background:{glass2};border:1px solid {border};color:{text2};}}
#PaletteContainer{{background:{glass2};border:1px solid {glow};}}
#PaletteSearch{{background:{input_bg};color:{text};border:1px solid {border};}}
#PaletteSearch:focus{{border-color:{glow};}}
#PaletteList{{color:{text};}}
#PaletteList::item:selected{{background:{active};color:{accent};}}
#PaletteList::item:hover{{background:{hover};}}
QSplitter::handle{{background:{border};}}
QMenu{{background:{menu_bg};color:{text};border:1px solid {border};border-radius:8px;padding:5px;}}
QMenu::item{{background:transparent;padding:6px 22px 6px 10px;border-radius:5px;}}
QMenu::item:selected{{background:{active};color:{accent};}}
QMenu::item:disabled{{color:{text2};}}
QMenu::separator{{height:1px;background:{border};margin:4px 8px;}}
#PbEntryIcon{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(79,195,247,0.20),stop:1 rgba(156,111,247,0.20));color:{text};}}
#SettingsSection{{color:{accent};}}
#SettingsLabel{{color:{text};}}
#SettingsHint{{color:{text2};}}
#SettingsDropdown{{background:{glass2};color:{text};border:1px solid {border};}}
#SettingsDropdown:hover{{border-color:{glow};}}
#SettingsAction{{background:{glass2};color:{text};border:1px solid {border};}}
#SettingsAction:hover{{border-color:{glow};background:{hover};}}
#SettingsToggle{{background:{glass2};color:{text2};border:1px solid {border};}}
#SettingsToggle:checked{{background:{grad};color:#fff;border-color:transparent;}}
#SettingsToggle:hover{{border-color:{glow};}}
#HistoryRow:hover{{background:{hover};}}
#HistoryRange{{background:{glass2};color:{text};border:1px solid {border};}}
#HistoryRange:focus{{border-color:{glow};}}
#HistoryDateSep{{color:{accent};}}
#HistoryTime{{color:{text2};}}
#FindBar{{background:{glass2};border:1px solid {glow};}}
#FindInput{{background:{input_bg};color:{text};border:1px solid {border};}}
#FindInput:focus{{border-color:{glow};}}
#FindCount{{color:{text2};}}
#FindNavBtn{{background:{hover};color:{text2};border:1px solid {border};}}
#FindNavBtn:hover{{background:{active};color:{text};border-color:{glow};}}
#SSDeviceCard{{background:{glass2};border:1px solid {border};}}
#SSDeviceCard:hover{{border-color:{glow};}}
#SSPulse{{color:#4fc3f7;}}
#SSPulseOff{{color:{text2};}}
#StarShareToast{{background:{glass2};border:1px solid {glow};border-radius:12px;}}
#ToastIcon{{color:{glow};background:transparent;}}
#ToastMsg{{color:{text};}}
#ToastDetail{{color:{text2};}}
#ToastYes{{background:{grad};}}
#ToastYes:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {accent2},stop:1 {accent3});}}
#ToastNo{{background:transparent;color:{text2};border:1px solid {border};}}
#ToastNo:hover{{background:{hover};color:{text};}}
#ToastCd{{color:{text2};}}
#FernwaySlider::groove:horizontal {{ border: 1px solid {border}; height: 4px; background: {glass}; border-radius: 2px; }}
#FernwaySlider::handle:horizontal {{ background: {accent}; border: none; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
#FernwayModeBtn {{ background: {glass}; color: {text}; border: 1px solid {border}; }}
#FernwayModeBtn:hover {{ background: {hover}; border-color: {accent}; }}
#FernwayModeBtn:checked {{ background: {active}; border-color: {glow}; color: {accent}; }}
 """
    if not get_fernway().get("hover_animations_enabled", True):
        stylesheet = re.sub(
            r"(?m)^[ \t]*[^{}\n]*:hover[^{}\n]*\{[^{}\n]*\}[ \t]*$",
            "",
            stylesheet,
        )
    return stylesheet


# ─────────────────────────────────────────────
#  DIM OVERLAY — background focus effect
# ─────────────────────────────────────────────
class _DimOverlay(QWidget):
    """Translucent overlay that softly dims content behind open panels.

    • Transparent to mouse events — does not block any underlying widget.
    • Opacity is animated in/out via QGraphicsOpacityEffect.
    • Tracks how many panels are open; undims only when all are closed.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background:#000000;")
        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(0.0)
        self.setGraphicsEffect(self._eff)
        self._anim  = None
        self._count = 0   # open-panel reference counter
        self.hide()

    def panel_opened(self):
        """Call each time a panel becomes visible."""
        self._count += 1
        if self._count == 1:
            fw = get_fernway()
            # Use blur_strength to influence how much the background dims
            # Higher blur_strength -> darker atmosphere
            base_dim = 0.05
            added_dim = (fw.get("blur_strength", 20) / 50) * 0.15
            self._fade_to(base_dim + added_dim)

    def panel_closed(self):
        """Call each time a panel is fully hidden."""
        self._count = max(0, self._count - 1)
        if self._count == 0:
            self._fade_to(0.0, hide_when_done=True)

    def _fade_to(self, target, hide_when_done=False):
        if self._anim:
            self._anim.stop()
        self.show()
        self.lower()   # stay below every floating panel
        m = _get_motion_params()
        self._anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim.setDuration(m["dim_ms"])
        self._anim.setStartValue(self._eff.opacity())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        if hide_when_done:
            # Only actually hide if no panel reopened during the fade
            self._anim.finished.connect(
                lambda: self.hide() if self._count == 0 else None)
        self._anim.start()


# ─────────────────────────────────────────────
#  PICTURE-IN-PICTURE WINDOW
# ─────────────────────────────────────────────
class _YouTubeRefererInterceptor(QWebEngineUrlRequestInterceptor):
    """Inject a Referer header on YouTube embed requests.

    Since late 2025 YouTube requires a valid HTTP Referer for embedded
    players; without it the iframe fails with "Video player configuration
    error" (Error 153).  QWebEngineView.setUrl() can't set request headers,
    so we intercept the page's requests and add one.  Installed per-page so
    it never touches the main browser tabs.
    """

    def interceptRequest(self, info):
        host = info.requestUrl().host().lower()
        if ("youtube.com" in host or "youtube-nocookie.com" in host
                or "vimeo.com" in host):
            info.setHttpHeader(QByteArray(b"Referer"),
                               QByteArray(("https://" + info.requestUrl().host()).encode()))


class PiPWindow(QWidget):
    """Floating always-on-top window for Picture-in-Picture video."""
    
    def __init__(self, parent=None, profile=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint  # pinned by default (toggle via 📌)
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(240, 160)
        self.resize(380, 220)
        self._always_on_top = True
        
        self._drag_pos = None
        self._video_url = None
        self._edge = None
        self._resize_start = None
        self._resize_geo = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Title bar (drag handle + controls) ──────────────────────
        self._bar = QWidget(self)
        self._bar.setFixedHeight(30)
        self._bar.setStyleSheet("background:#15161a;border-bottom:1px solid #000;")
        bar_l = QHBoxLayout(self._bar)
        bar_l.setContentsMargins(10, 0, 6, 0)
        bar_l.setSpacing(6)
        self._title_lbl = QLabel("Picture-in-Picture")
        self._title_lbl.setStyleSheet("color:#cfd2da;font-size:12px;")
        self._title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Let mouse events fall through to the bar so the whole title bar drags.
        self._title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        bar_l.addWidget(self._title_lbl)
        self._pin_btn = QPushButton("📌")
        self._pin_btn.setFixedSize(28, 22)
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(True)
        self._pin_btn.setToolTip("Always on top")
        self._pin_btn.setStyleSheet(self._pin_style(True))
        self._pin_btn.clicked.connect(self._toggle_always_on_top)
        bar_l.addWidget(self._pin_btn)
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(28, 22)
        self._close_btn.setToolTip("Close")
        self._close_btn.setStyleSheet(
            "background:#2a2c33;color:#fff;border:none;border-radius:4px;font-size:12px;"
        )
        self._close_btn.clicked.connect(self.close)
        bar_l.addWidget(self._close_btn)
        layout.addWidget(self._bar)

        # WebEngine view for video. Reuse the main browser profile when given
        # so YouTube/Vimeo embeds inherit the same User-Agent + consent cookies
        # (otherwise they fail with "Video player configuration error" / #153).
        self._view = QWebEngineView(self)
        if profile is not None:
            self._view.setPage(QWebEnginePage(profile, self._view))
        # Force a Referer on YouTube embeds (Error 153/152 fix).
        self._referer_interceptor = _YouTubeRefererInterceptor(self._view)
        self._view.page().setUrlRequestInterceptor(self._referer_interceptor)
        self._view.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        layout.addWidget(self._view, 1)

        # Size grip for resizing (bottom-right)
        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(16, 16)
        self._grip.setStyleSheet("background:transparent;")

        self._video_url = None
        self._drag_pos = None
        self._edge = None
        self._resize_start = None
        self._resize_geo = None

        # Drag (title bar) + edge-resize (video) via event filter so the
        # WebEngine view still receives normal clicks for playback.
        self._view.installEventFilter(self)
        self._bar.installEventFilter(self)
        self.installEventFilter(self)
        self.setMouseTracking(True)
    
    def load_video(self, url: str):
        self._video_url = url
        self._view.setUrl(QUrl(url))
    
    def load_html(self, html: str, base_url: str = ""):
        self._view.setHtml(html, QUrl(base_url))
    
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._grip.move(self.width() - 16, self.height() - 16)
    
    def _edge_at(self, pos):
        """Determine which edge/corner the mouse is at for resizing."""
        margin = 10
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        on_left = x < margin
        on_right = x > w - margin
        on_top = y < margin
        on_bottom = y > h - margin
        if on_top and on_left: return Qt.LeftEdge | Qt.TopEdge
        if on_top and on_right: return Qt.RightEdge | Qt.TopEdge
        if on_bottom and on_left: return Qt.LeftEdge | Qt.BottomEdge
        if on_bottom and on_right: return Qt.RightEdge | Qt.BottomEdge
        if on_top: return Qt.TopEdge
        if on_bottom: return Qt.BottomEdge
        if on_left: return Qt.LeftEdge
        if on_right: return Qt.RightEdge
        return None
    
    def _cursor_for_edge(self, edge):
        if edge is None: return Qt.CursorShape.SizeAllCursor
        if edge & Qt.TopEdge and edge & Qt.LeftEdge: return Qt.CursorShape.SizeFDiagCursor
        if edge & Qt.TopEdge and edge & Qt.RightEdge: return Qt.CursorShape.SizeBDiagCursor
        if edge & Qt.BottomEdge and edge & Qt.LeftEdge: return Qt.CursorShape.SizeBDiagCursor
        if edge & Qt.BottomEdge and edge & Qt.RightEdge: return Qt.CursorShape.SizeFDiagCursor
        if edge & Qt.TopEdge or edge & Qt.BottomEdge: return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.SizeHorCursor
    
    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if getattr(self, "_title_lbl", None) is not None:
            self._title_lbl.setText(title)

    def _pin_style(self, on):
        if on:
            return "background:#3a5a40;color:#fff;border:none;border-radius:4px;font-size:13px;"
        return "background:#2a2c33;color:#9aa0aa;border:none;border-radius:4px;font-size:13px;"

    def _toggle_always_on_top(self, checked):
        self._always_on_top = checked
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self._pin_btn.setStyleSheet(self._pin_style(checked))
        self.show()

    def _resize_step(self, gpos):
        """Apply an in-progress edge resize from a global position."""
        delta = gpos - self._resize_start
        geo = QRect(self._resize_geo)
        if self._edge & Qt.LeftEdge:
            geo.setLeft(geo.left() + delta.x())
        if self._edge & Qt.RightEdge:
            geo.setRight(geo.right() + delta.x())
        if self._edge & Qt.TopEdge:
            geo.setTop(geo.top() + delta.y())
        if self._edge & Qt.BottomEdge:
            geo.setBottom(geo.bottom() + delta.y())
        if geo.width() >= self.minimumWidth() and geo.height() >= self.minimumHeight():
            self.setGeometry(geo)

    def _end_resize(self):
        self._edge = None
        self._resize_start = None
        self._resize_geo = None
        self.releaseMouse()

    def eventFilter(self, obj, ev):
        t = ev.type()
        # Title-bar drag — and, while the mouse is grabbed by this window,
        # any in-progress drag/resize events arriving on the window itself.
        if obj is self._bar or obj is self:
            if t == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton and not self._edge:
                self._drag_pos = ev.globalPosition().toPoint() - self.pos()
                self.grabMouse()
            elif t == QEvent.Type.MouseMove and self._drag_pos is not None:
                if ev.buttons() & Qt.MouseButton.LeftButton:
                    self.move(ev.globalPosition().toPoint() - self._drag_pos)
            elif t == QEvent.Type.MouseButtonRelease and self._drag_pos is not None:
                self._drag_pos = None
                self.releaseMouse()
            elif t == QEvent.Type.MouseMove and self._edge is not None:
                if ev.buttons() & Qt.MouseButton.LeftButton:
                    self._resize_step(ev.globalPosition().toPoint())
            elif t == QEvent.Type.MouseButtonRelease and self._edge is not None:
                self._end_resize()
        # Edge-resize when pressing near a border of the video view.
        elif obj is self._view:
            if t == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton:
                edge = self._edge_at(ev.position().toPoint())
                if edge:
                    self._edge = edge
                    self._resize_start = ev.globalPosition().toPoint()
                    self._resize_geo = self.geometry()
                    self.grabMouse()  # keep every event on this window
                    return True
            elif t == QEvent.Type.MouseMove:
                if self._edge is not None:
                    if ev.buttons() & Qt.MouseButton.LeftButton:
                        self._resize_step(ev.globalPosition().toPoint())
                    return True
                self._view.setCursor(self._cursor_for_edge(self._edge_at(ev.position().toPoint())))
            elif t == QEvent.Type.MouseButtonRelease and self._edge is not None:
                self._end_resize()
                return True
        return super().eventFilter(obj, ev)

    def closeEvent(self, e):
        # Clean up parent's reference
        parent = self.parent()
        if parent and hasattr(parent, '_pip_window'):
            parent._pip_window = None
        super().closeEvent(e)


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────
class _PanelDismissFilter(QObject):
    def __init__(self, window):
        super().__init__(window)
        self._window = window

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.MouseButtonPress
                and not self._window._settings.get("keep_panels_open", False)):
            self._window._dismiss_panels_outside_click(event)
        return False


class NorthStar(QMainWindow):
    favicon_ready = pyqtSignal(object, bytes, str)  # button, png data, domain cache key
    install_extension_requested = pyqtSignal()      # browser thread → GUI thread
    browse_addons_requested = pyqtSignal()          # browser thread → GUI thread
    extensions_action_requested = pyqtSignal(str, str, object)  # action, id, value

    # Panels listed here are exempt from "click anywhere to dismiss".
    # The Password Book holds a search field and an entry list, so it
    # stays open when you click elsewhere on the page. Close it with the
    # 🔑 sidebar button (or the 🔒 lock button inside the panel).
    _STICKY_PANELS = ("password_book",)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Northstar One: Brand New Light"); self.resize(1280, 820)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._drag_pos = None

        _icon_path = _asset("northstar.ico")
        if os.path.exists(_icon_path): self.setWindowIcon(QIcon(_icon_path))

        self._settings = _load_settings(); self._dark_mode = True  # light mode removed
        self._history = []
        self._bookmarks = _load_bookmarks()
        self._bookmark_urls = {b.get("url") for b in self._bookmarks}
        self._favicon_cache: dict = {}
        self._favicon_data_cache: dict = _load_favicon_cache()
        global _global_favicon_data_cache
        _global_favicon_data_cache = dict(self._favicon_data_cache)
        self._favicon_pending_domains = set()
        self._favicon_waiting_buttons = {}
        self._favicon_pending_lock = threading.Lock()
        self._favicon_executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="NorthStarFavicons"
        )
        self._favicon_cache_save_thread = None
        self._favicon_cache_save_timer = QTimer(self)
        self._favicon_cache_save_timer.setSingleShot(True)
        self._favicon_cache_save_timer.setInterval(250)
        self._favicon_cache_save_timer.timeout.connect(self._persist_favicon_cache_async)
        self.favicon_ready.connect(self._on_favicon_ready)
        self.install_extension_requested.connect(self._install_extension)
        self.browse_addons_requested.connect(self._browse_edge_addons)
        self.extensions_action_requested.connect(self._on_extensions_action)

        self.profile = QWebEngineProfile("NorthStarProfile", self)
        
        # Register the NorthStar URL scheme handler (wallpapers + video wallpapers)
        self.northstar_handler = NorthStarUrlSchemeHandler()
        self.profile.installUrlSchemeHandler(b"northstar", self.northstar_handler)

        # Pre-create storage dirs and verify they're writable before handing
        # them to Chromium — on Windows, a locked/antivirus-quarantined dir
        # causes "Access is denied" errors that break the whole cache layer.
        _storage_path = os.path.join(_data_dir(), "WebEngine")
        _cache_path   = os.path.join(_data_dir(), "WebEngineCache")
        _use_disk_cache = True
        for _p in (_storage_path, _cache_path):
            try:
                os.makedirs(_p, exist_ok=True)
                # Quick write-test so we know Windows won't deny Chromium.
                _probe = os.path.join(_p, ".write_probe")
                with open(_probe, "w") as _f: _f.write("ok")
                os.remove(_probe)
            except OSError as _e:
                _use_disk_cache = False   # Fall back to memory cache below.
                if _DEBUG:
                    print(f"[startup] WebEngine dir not writable ({_p}): {_e} — using memory cache")
                break

        self.profile.setPersistentStoragePath(_storage_path)
        self.profile.setCachePath(_cache_path)
        if _use_disk_cache:
            self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
            self.profile.setHttpCacheMaximumSize(100 * 1024 * 1024)  # 100 MB
        else:
            # Directory not writable (permissions / antivirus / locked file).
            # Memory cache still gives in-session speed gains without any
            # file-system access that could trigger "Access is denied".
            self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)

        self.profile.downloadRequested.connect(self._on_download_requested)

        s = self.profile.settings()
        for attr, val in [
            (QWebEngineSettings.WebAttribute.AutoLoadImages,               True),
            (QWebEngineSettings.WebAttribute.JavascriptEnabled,            True),
            (QWebEngineSettings.WebAttribute.PluginsEnabled,               True),
            (QWebEngineSettings.WebAttribute.WebGLEnabled,                 True),
            (QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled,   True),
            (QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly,   False),
            (QWebEngineSettings.WebAttribute.FullScreenSupportEnabled,     True),
            (QWebEngineSettings.WebAttribute.AllowRunningInsecureContent,  True),
            (QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True),
            (QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,   True),
            (QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture,  False),
        ]:
            s.setAttribute(attr, val)

        # Set a standard User-Agent to avoid being blocked by CDNs/Wikimedia.
        # Built dynamically from the running engine so the Chrome/QtWebEngine
        # version stays truthful across upgrades (e.g. 6.8.2 → 6.10+ for MV3).
        self.profile.setHttpUserAgent(_northstar_user_agent())
        s.setDefaultTextEncoding("UTF-8")

        # ── Extension system (MV3 native engine on Qt >= 6.10, content-script
        # fallback below) ──
        # Lazy-import the extensions module: it pulls in extra PyQt6 machinery
        # that doesn't need to be parsed before the window appears.  Instantiate
        # after the profile is fully configured so the manager can inject/remove
        # content scripts or hand the profile to Qt's extension manager.  Enabled
        # extensions are re-applied on the next event-loop tick (below), never on
        # the hot path that blocks first paint.
        from extensions import ExtensionManager
        self.extensions = ExtensionManager(_data_dir(), self.profile)
        self.extensions.changed.connect(self._on_extensions_changed)
        # Re-applying enabled extensions (content-script injection / native MV3
        # enable) can touch the disk and the QtWebEngine extension manager.  Do
        # it on the next event-loop tick so it never blocks the window paint;
        # the UI thread is free to draw the chrome + newtab first.
        QTimer.singleShot(0, self.extensions.install_all_enabled)

        self._ss_server = StarShareServer(self)
        # FIX: beacon starts as None; created/destroyed by _toggle_starshare so
        # it only runs while the StarShare panel is open (no idle CPU cost).
        self._ss_beacon = None

        # ── NorthStar Search V1 (lazy — created on first use) ─────
        self._ns_search = None
        self._search_manager = None
        
        # ── Content Enrichment Pipeline (lazy — created on first use) ──
        self._enrichment = None
        
        # Set of in-flight OpalSearchWorker instances; keeps them alive until done
        self._opal_workers: set = set()
        
        # Centralized popup/navigation policy manager
        self.popup_policy = PopupPolicyManager()
        
        self.fernway = get_fernway()

        # Debounce timer for style updates
        self._style_debounce_timer = QTimer(self)
        self._style_debounce_timer.setSingleShot(True)
        self._style_debounce_timer.setInterval(100)
        self._style_debounce_reload = False
        
        def _debounced_apply_style():
            self._apply_style(reload=self._style_debounce_reload)
            self._style_debounce_reload = False
            
        self._style_debounce_timer.timeout.connect(_debounced_apply_style)
        
        def _on_fernway_setting_changed(k, v):
            self._style_debounce_reload = self._should_reload_after_setting_change()
            if k in ("wallpaper_mode", "background_style", "wallpaper", "oled_mode"):
                _invalidate_newtab_cache()
            if self._style_debounce_timer.isActive():
                self._style_debounce_timer.stop()
            self._style_debounce_timer.start()
            
        def _on_fernway_mode_changed(m):
            self._style_debounce_reload = self._should_reload_after_setting_change()
            if self._style_debounce_timer.isActive():
                self._style_debounce_timer.stop()
            self._style_debounce_timer.start()
            
        self.fernway.setting_changed.connect(_on_fernway_setting_changed)
        self.fernway.mode_changed.connect(_on_fernway_mode_changed)

        # Auto-hide sidebar timer
        self._sidebar_timer = QTimer(self)
        self._sidebar_timer.setSingleShot(True)
        self._sidebar_timer.setInterval(int(self.fernway.get("autohide_delay_ms", 400)))
        self._sidebar_timer.timeout.connect(self._hide_sidebar)
        self.setMouseTracking(True)

        # Polling timer for floating sidebar unhide (more reliable than event filtering)
        self._edge_timer = QTimer(self)
        self._edge_timer.setInterval(150)
        self._edge_timer.timeout.connect(self._check_edge_hover)
        self._edge_timer.start()

        self._build_ui()
        self._app = QApplication.instance()
        if self._app:
            self._panel_dismiss_filter = _PanelDismissFilter(self)
            self._app.installEventFilter(self._panel_dismiss_filter)
        self._pip_window = None
        # Install clipboard fallback shim so copy buttons on sites that use
        # navigator.clipboard.writeText() (ChatGPT, Gemini, Claude, ...) work
        # even when the page hasn't been granted the ClipboardReadWrite
        # permission.  Falls back to the legacy execCommand('copy') path,
        # which succeeds as long as it's invoked from a user gesture.
        QTimer.singleShot(0, lambda: self._install_clipboard_shim())
        QTimer.singleShot(0, lambda: self._setup_shortcuts())
        # OPT: apply style once using base+patch; subsequent calls only rebuild patch
        self._apply_style()
        restored_tabs = _load_session_tabs() if self._settings.get("restore_tabs") else []
        if restored_tabs:
            for saved_url in reversed(restored_tabs):
                self._new_tab(saved_url, switch_to=False)
            self.tabs.setCurrentIndex(0)
        else:
            self._new_tab(NORTHSTAR_HOME)
        current_tab = self._current_tab()
        current_url = current_tab.view.url().toString() if current_tab else ""
        self._set_toolbar_overlay(self._is_newtab_url(current_url))

        self._dl_badge_timer = QTimer(self); self._dl_badge_timer.timeout.connect(self._update_dl_badge)
        self._resize_timer = QTimer(self); self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(40); self._resize_timer.timeout.connect(self._repin_panels)

        self._ss_server.transfer_request.connect(self._on_ss_incoming)
        self._ss_server.transfer_done.connect(
            lambda cid: self.status_bar.showMessage("✦ StarShare: file received.", 4000))
        self._ss_server.start()

        # Connect application state change to handle alt-tab focus issues
        app = QApplication.instance()
        app.applicationStateChanged.connect(self._on_application_state_changed)
        
        # OPT: pre-warm the Chromium renderer process in the background so
        # subsequent tab loads don't pay the cold-start penalty (~200–500 ms).
        # Scheduled via singleShot(0) so it runs after the event loop starts
        # and the main window has already painted its first frame.
        self._preload_view = None
        QTimer.singleShot(0, self._preload_web_engine)
        
    def changeEvent(self, e):
        super().changeEvent(e)
        # Intentionally do NOT call view.update() on alt-tab.
        # QWebEngineView handles its own repaint when the window regains
        # focus; forcing update() restarts CSS animations on newtab pages
        # (cardFloat, quoteFade) causing visible flicker.
        pass

    def _on_application_state_changed(self, state):
        # Intentionally do NOT call _refresh_web_views() here.
        # QWebEngineView repaints itself on ApplicationActive; calling
        # update() on every tab restarts the newtab CSS animations and
        # produces an opacity-0 -> opacity-1 flash on alt-tab.
        if (state != Qt.ApplicationState.ApplicationActive
                and not self._settings.get("keep_panels_open", False)):
            self._dismiss_panels_except(None)

    # ── DOWNLOAD HANDLING ────────────────────
    def _check_edge_hover(self):
        """Poll mouse position to unhide bars when near edges."""
        # Only check if the window is active
        if not self.isActiveWindow():
            return

        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        
        # 1. Sidebar Edge Logic (Left)
        # Only slide if auto-hide is enabled OR style is floating
        if self.fernway.get("sidebar_auto_hide") or self.fernway.get("sidebar_style") == "floating":
            # Calculate the top UI area height (toolbar + bookmarks bar)
            top_area_height = self._toolbar_widget.height() + self._bookmarks_bar.height()
            # Only trigger hover zone below the top UI
            if top_area_height <= local_pos.y() <= self.height():
                if 0 <= local_pos.x() < 30:
                    self._show_sidebar()
                elif local_pos.x() > self.sidebar.width() + 80:
                    if not self._sidebar_timer.isActive() and self.sidebar.width() > 0:
                        self._sidebar_timer.start()



    # ── EVENT FILTERING ──────────────────────
    def eventFilter(self, obj, e):
        return super().eventFilter(obj, e)

    def _dismiss_panels_outside_click(self, event):
        target = QApplication.widgetAt(event.globalPosition().toPoint())
        self._dismiss_panels_except(target)

    def _dismiss_panels_except(self, target):
        if QApplication.activeModalWidget():
            return
        panels = [
            getattr(self, name, None)
            for name in (
                "downloads_panel", "notes_panel", "fernway_panel",
                "password_book", "history_panel", "starshare_panel",
                "settings_panel", "ai_panel", "find_bar",
            )
        ]
        visible_panels = [panel for panel in panels if panel and panel.isVisible()]
        if not visible_panels:
            return

        sticky = {getattr(self, name, None) for name in self._STICKY_PANELS}
        clicked_panel = next(
            (panel for panel in visible_panels
             if target is not None
             and (target is panel or panel.isAncestorOf(target))),
            None,
        )
        for panel in visible_panels:
            if panel is clicked_panel:
                continue
            if panel in sticky:
                continue
            if panel is self.find_bar:
                panel.close_bar()
            elif panel is self.ai_panel:
                if getattr(panel, "_outside_close_pending", False):
                    continue
                panel._outside_close_pending = True
                self._toggle_ai()
                animation = getattr(panel, "_ns_exit_anim", None)
                if animation is not None:
                    animation.finished.connect(
                        lambda p=panel: setattr(p, "_outside_close_pending", False)
                    )
                else:
                    panel._outside_close_pending = False
            else:
                if panel is self.starshare_panel and self._ss_beacon:
                    self._ss_beacon.stop()
                    self._ss_beacon = None
                _ns_panel_hide(panel, on_hidden=self._dim.panel_closed)

    def mouseMoveEvent(self, e):
        # We now use _check_edge_hover (polling) for sidebar unhiding.
        super().mouseMoveEvent(e)

    def _show_sidebar(self):
        self._sidebar_timer.stop()
        if self.sidebar.minimumWidth() >= self._sidebar_target_width(): return
        # Don't restart if show animation is already running (avoids opacity flash)
        if getattr(self, "_sidebar_showing", False): return
        
        m = _get_motion_params()
        if hasattr(self, "_sidebar_anim"): self._sidebar_anim.stop()
        if hasattr(self, "_sidebar_anim_max"): self._sidebar_anim_max.stop()
        if hasattr(self, "_sidebar_fade_anim"): self._sidebar_fade_anim.stop()
        
        # Disconnect old finished signals to prevent accumulation
        if hasattr(self, "_sidebar_anim"):
            try: self._sidebar_anim.finished.disconnect(self._repin_panels)
            except (TypeError, RuntimeError): pass
            try: self._sidebar_anim.finished.disconnect()
            except (TypeError, RuntimeError): pass
        if hasattr(self, "_sidebar_anim_max"):
            try: self._sidebar_anim_max.finished.disconnect()
            except (TypeError, RuntimeError): pass
        
        # Animation for minimumWidth
        self._sidebar_anim = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self._sidebar_anim.setDuration(m["in_ms"])
        self._sidebar_anim.setStartValue(self.sidebar.minimumWidth())
        self._sidebar_anim.setEndValue(self._sidebar_target_width())
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Animation for maximumWidth (to make the slide effect smooth)
        self._sidebar_anim_max = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self._sidebar_anim_max.setDuration(m["in_ms"])
        self._sidebar_anim_max.setStartValue(self.sidebar.maximumWidth())
        self._sidebar_anim_max.setEndValue(self._sidebar_target_width())
        self._sidebar_anim_max.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Update geometry once at the end
        self._sidebar_showing = True
        self._sidebar_anim.finished.connect(self._repin_panels)
        self._sidebar_anim.finished.connect(lambda: setattr(self, '_sidebar_showing', False))
        if self.fernway.get("sidebar_style") == "floating":
            self._sidebar_anim.finished.connect(
                lambda: self.sidebar.setGeometry(0, 0, self._sidebar_target_width(), self.height())
            )
        
        self._sidebar_anim.start()
        self._sidebar_anim_max.start()
        
        if self.fernway.get("fade_animations_enabled", True):
            self._sidebar_eff.setOpacity(0.0)
            self._sidebar_eff.setEnabled(True)
            self._sidebar_fade_anim = QPropertyAnimation(self._sidebar_eff, b"opacity")
            self._sidebar_fade_anim.setDuration(m["fade_ms"])
            self._sidebar_fade_anim.setStartValue(0.0)
            self._sidebar_fade_anim.setEndValue(1.0)
            self._sidebar_fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._sidebar_fade_anim.finished.connect(lambda: self._sidebar_eff.setEnabled(False) if self._sidebar_fade_anim and self._sidebar_fade_anim.endValue() == 1.0 else None)
            self._sidebar_fade_anim.start()
        else:
            self._sidebar_eff.setEnabled(False)
            self._sidebar_eff.setOpacity(1.0)

    def _hide_sidebar(self):
        self._sidebar_showing = False
        if self.sidebar.underMouse(): 
            self._sidebar_timer.start()
            return
        
        # Cancel tab entry animation if running, teleport card to final position
        if hasattr(self, '_tab_entry_anim') and self._tab_entry_anim is not None:
            self._tab_entry_anim.stop()
            self._tab_entry_anim = None
        if hasattr(self, '_tab_entry_overshoot') and self._tab_entry_overshoot is not None:
            self._tab_entry_overshoot.stop()
            self._tab_entry_overshoot = None
        if hasattr(self, '_tab_entry_card') and self._tab_entry_card is not None:
            if hasattr(self, '_tab_entry_end_pos') and self._tab_entry_end_pos is not None:
                try:
                    self._tab_entry_card.move(self._tab_entry_end_pos)
                except RuntimeError:
                    pass
            self._tab_entry_card = None
            self._tab_entry_end_pos = None
        
        m = _get_motion_params()
        if hasattr(self, "_sidebar_anim"): self._sidebar_anim.stop()
        if hasattr(self, "_sidebar_anim_max"): self._sidebar_anim_max.stop()
        if hasattr(self, "_sidebar_fade_anim"): self._sidebar_fade_anim.stop()

        # Disconnect old finished signals to prevent accumulation
        if hasattr(self, "_sidebar_anim"):
            try: self._sidebar_anim.finished.disconnect(self._repin_panels)
            except (TypeError, RuntimeError): pass
            try: self._sidebar_anim.finished.disconnect()
            except (TypeError, RuntimeError): pass
        if hasattr(self, "_sidebar_anim_max"):
            try: self._sidebar_anim_max.finished.disconnect()
            except (TypeError, RuntimeError): pass

        # Animation for minimumWidth
        self._sidebar_anim = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self._sidebar_anim.setDuration(m["out_ms"])
        self._sidebar_anim.setStartValue(self.sidebar.minimumWidth())
        self._sidebar_anim.setEndValue(0)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Animation for maximumWidth (to make the slide effect smooth)
        self._sidebar_anim_max = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self._sidebar_anim_max.setDuration(m["out_ms"])
        self._sidebar_anim_max.setStartValue(self.sidebar.maximumWidth())
        self._sidebar_anim_max.setEndValue(0)
        self._sidebar_anim_max.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Ensure it actually hides by connecting finished to set max width to 0
        self._sidebar_anim_max.finished.connect(
            lambda: self.sidebar.setMaximumWidth(0) if self.sidebar.minimumWidth() == 0 else None)
        
        # Update geometry once at the end
        self._sidebar_anim.finished.connect(self._repin_panels)
        if self.fernway.get("sidebar_style") == "floating":
            self._sidebar_anim.finished.connect(lambda: self.sidebar.setGeometry(0, 0, 0, self.height()))
        
        self._sidebar_anim.start()
        self._sidebar_anim_max.start()
        
        if self.fernway.get("fade_animations_enabled", True):
            self._sidebar_eff.setEnabled(True)
            self._sidebar_fade_anim = QPropertyAnimation(self._sidebar_eff, b"opacity")
            self._sidebar_fade_anim.setDuration(m["fade_ms"])
            self._sidebar_fade_anim.setStartValue(self._sidebar_eff.opacity())
            self._sidebar_fade_anim.setEndValue(0.0)
            self._sidebar_fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._sidebar_fade_anim.start()
        else:
            self._sidebar_eff.setEnabled(False)
            self._sidebar_eff.setOpacity(1.0)

    def _on_download_requested(self, download):
        suggested = download.downloadFileName()
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save File", os.path.join(download.downloadDirectory(), suggested))
        if not save_path: download.cancel(); return
        download.setDownloadDirectory(os.path.dirname(save_path))
        download.setDownloadFileName(os.path.basename(save_path))
        download.accept()
        if not self.downloads_panel.isVisible(): self._toggle_downloads(force_show=True)
        self.downloads_panel.add_download(download)
        self.status_bar.showMessage(f"⬇ Downloading: {os.path.basename(save_path)}", 4000)
        if not self._dl_badge_timer.isActive(): self._dl_badge_timer.start(1000)

    def _update_dl_badge(self):
        active = self.downloads_panel.active_count
        if active > 0:
            self._dl_btn.setText(f"⬇{active}"); self._dl_btn.setToolTip(f"{active} active download(s)  (Ctrl+J)")
        else:
            self._dl_btn.setText("⬇"); self._dl_btn.setToolTip("Downloads (Ctrl+J)"); self._dl_badge_timer.stop()

    # ── UI CONSTRUCTION ──────────────────────
    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        central.setMouseTracking(True); central.installEventFilter(self)
        root = QHBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.sidebar = self._build_sidebar()
        # If not floating, add to layout. If floating, it will overlay.
        if self.fernway.get("sidebar_style") != "floating":
            root.addWidget(self.sidebar)
        else:
            # For floating: make it an overlay, parented to central, no layout!
            self.sidebar.setParent(central)
            self.sidebar.show()
            self.sidebar.raise_()
            # Set initial geometry after layout is ready and window is maximized
            def init_floating_geo():
                self.sidebar.setGeometry(0, 0, 0, self.height())
            QTimer.singleShot(300, init_floating_geo)
            
        content_col = QWidget(); content_col.setObjectName("ContentCol")
        content_col.setMouseTracking(True); content_col.installEventFilter(self)
        self._content_col = content_col   # FIX: expose for toast overlay parenting
        self._col_layout = col_layout = QVBoxLayout(content_col); col_layout.setContentsMargins(0,0,0,0); col_layout.setSpacing(0)
        self._toolbar_widget = self._build_toolbar()
        self._toolbar_widget.setMouseTracking(True); self._toolbar_widget.installEventFilter(self)
        # Toolbar starts in layout mode (normal, opaque)
        self._toolbar_overlay_mode = False
        col_layout.addWidget(self._toolbar_widget)

        def _reposition_toolbar():
            if self._toolbar_overlay_mode:
                sb_w = self.sidebar.width() if self.fernway.get("sidebar_style") != "floating" else 0
                self._toolbar_widget.setGeometry(sb_w, 0, content_col.width() - sb_w, 45)
                self._toolbar_widget.raise_()
                if hasattr(self, 'progress'):
                    self.progress.setGeometry(sb_w, 45, content_col.width() - sb_w, 3)
                    self.progress.raise_()
        self._reposition_toolbar = _reposition_toolbar
        
        # ── Separate Bookmarks Bar (overlay, not in layout) ─────────────────
        self._bookmarks_bar = QWidget(content_col); self._bookmarks_bar.setObjectName("BookmarksBar")
        self._bookmarks_bar.setGeometry(0, 45, content_col.width(), 0)
        self._bookmarks_bar.raise_()
        bm_bar_layout = QHBoxLayout(self._bookmarks_bar); bm_bar_layout.setContentsMargins(10,4,10,4); bm_bar_layout.setSpacing(4)
        self._bookmarks_bar_layout = bm_bar_layout
        
        self.progress = QProgressBar(); self.progress.setObjectName("LoadProgress")
        self.progress.setMaximumHeight(3); self.progress.setTextVisible(False); self.progress.hide()
        col_layout.addWidget(self.progress)
        self.splitter = QSplitter(Qt.Orientation.Horizontal); self.splitter.setHandleWidth(1)
        self.splitter.setMouseTracking(True); self.splitter.installEventFilter(self)
        self.tabs = QTabWidget(); self.tabs.setTabsClosable(False); self.tabs.setMovable(False)
        self.tabs.setMouseTracking(True); self.tabs.installEventFilter(self)
        self.tabs.setDocumentMode(True); self.tabs.tabBar().hide()
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.splitter.addWidget(self.tabs)
        self.ai_panel = AIPanel(self._get_current_title)
        self.ai_panel.setMinimumWidth(300); self.ai_panel.setMaximumWidth(420); self.ai_panel.hide()
        self.splitter.addWidget(self.ai_panel); self.splitter.setSizes([980, 0])
        col_layout.addWidget(self.splitter); root.addWidget(content_col, 1)

        # Background dim overlay — sits below all floating panels
        self._dim = _DimOverlay(content_col)

        # Floating overlays
        self.fernway_panel   = FernwayPanel(self.fernway, content_col); self.fernway_panel.hide()
        self.downloads_panel = DownloadsPanel(content_col); self.downloads_panel.hide()
        self.notes_panel = NotesPanel(content_col); self.notes_panel.hide()
        self.password_book   = PasswordBook(content_col);   self.password_book.hide()
        self.password_book.status_message.connect(lambda msg, ms: self.status_bar.showMessage(msg, ms))
        self.password_book.autofill = self._do_autofill
        self.settings_panel  = SettingsPanel(self._settings, content_col); self.settings_panel.hide()
        self.settings_panel.changed.connect(self._on_settings_changed)
        self.history_panel   = HistoryPanel(content_col); self.history_panel.hide()
        self.history_panel.navigate.connect(
            lambda url: self._current_tab().navigate(url) if self._current_tab() else None)
        self.find_bar        = FindBar(content_col); self.find_bar.hide()
        self.starshare_panel = StarSharePanel(self._ss_server, content_col); self.starshare_panel.hide()
        self.starshare_panel.status_message.connect(lambda msg, ms: self.status_bar.showMessage(msg, ms))

        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)
        grip = QSizeGrip(self.status_bar); self.status_bar.addPermanentWidget(grip)
        # Hide the bar when it has nothing to say; show it only for timed messages.
        self.status_bar.hide()
        self.status_bar.messageChanged.connect(
            lambda msg: self.status_bar.show() if msg else self.status_bar.hide())

        # Floating hover-URL label — Chrome-style overlay at bottom-left.
        # Appears on linkHovered, disappears when the cursor leaves the link.
        self._hover_label = QLabel("", content_col)
        self._hover_label.setObjectName("HoverStatusBar")
        self._hover_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._hover_label.setMaximumWidth(600)
        self._hover_label.hide()
        self._hover_hide_timer = QTimer(self)
        self._hover_hide_timer.setSingleShot(True)
        self._hover_hide_timer.setInterval(120)   # tiny grace period avoids flicker
        self._hover_hide_timer.timeout.connect(self._hover_label.hide)

    def _build_sidebar(self):
        self._sidebar_expanded = bool(self._settings.get("sidebar_expanded", False))
        self._sidebar_collapsed_w = 56
        self._sidebar_expanded_w = 220
        sidebar = QWidget(); sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(self._sidebar_target_width())
        sidebar.setMouseTracking(True)
        
        # Opacity effect for fade animations
        self._sidebar_eff = QGraphicsOpacityEffect(sidebar)
        sidebar.setGraphicsEffect(self._sidebar_eff)
        self._sidebar_eff.setOpacity(1.0) # Start opaque
        
        layout = QVBoxLayout(sidebar); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        
        # ── Top: Logo + New Tab ────────────────────────────────────────────
        top_nav = QWidget(); top_nav.setObjectName("SidebarTopNav")
        top_layout = QVBoxLayout(top_nav); top_layout.setContentsMargins(5,8,5,4); top_layout.setSpacing(2)
        
        self._sidebar_logo = QPushButton("✦"); self._sidebar_logo.setObjectName("SidebarLogo")
        self._sidebar_logo.setFixedSize(46, 46)
        self._sidebar_logo.setToolTip("Collapse sidebar" if self._sidebar_expanded else "Expand sidebar")
        self._sidebar_logo.setAccessibleName("Toggle sidebar width")
        self._sidebar_logo.clicked.connect(
            lambda: self._set_sidebar_expanded(not self._sidebar_expanded)
        )
        self._sidebar_logo.setCursor(Qt.CursorShape.PointingHandCursor)
        top_layout.addWidget(self._sidebar_logo)
        
        self._sidebar_newtab = QPushButton("+"); self._sidebar_newtab.setObjectName("NewTabBtn")
        self._sidebar_newtab.setFixedSize(46, 46); self._sidebar_newtab.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sidebar_newtab.setToolTip("New tab (Ctrl+T)")
        self._sidebar_newtab.setAccessibleName("Open new tab")
        self._sidebar_newtab.clicked.connect(lambda: self._new_tab()); top_layout.addWidget(self._sidebar_newtab)
        
        div = QFrame(); div.setObjectName("SidebarDiv"); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); top_layout.addWidget(div)
        self._sidebar_divider = div
        
        layout.addWidget(top_nav)
        
        # ── Middle: Tab cards (scrollable) ─────────────────────────────────
        scroll = QScrollArea(); scroll.setObjectName("TabScroll"); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._tab_btn_container = QWidget(); self._tab_btn_container.setObjectName("TabBtnContainer")
        self._tab_btn_layout = QVBoxLayout(self._tab_btn_container)
        self._tab_btn_layout.setContentsMargins(4,4,4,0); self._tab_btn_layout.setSpacing(2)
        self._tab_btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._tab_btn_container); layout.addWidget(scroll, 1)
        
        # ── Bottom: All nav buttons together ───────────────────────────────
        bot_nav = QWidget(); bot_nav.setObjectName("SidebarBotNav")
        bot_layout = QVBoxLayout(bot_nav); bot_layout.setContentsMargins(5,0,5,8); bot_layout.setSpacing(2)
        
        div2 = QFrame(); div2.setObjectName("SidebarDiv"); div2.setFrameShape(QFrame.Shape.HLine)
        div2.setFixedHeight(1); bot_layout.addWidget(div2)
        
        self._sidebar_bottom = []
        for icon, tip, fn, attr in [
            ("✦", "Leo AI (Ctrl+Shift+A)", self._toggle_ai, "_ai_btn"),
            ("⬇", "Downloads (Ctrl+J)", self._toggle_downloads, "_dl_btn"),
            ("📝", "Notes", self._toggle_notes, "_notes_btn"),
            ("🕐", "History (Ctrl+H)", self._toggle_history, "_hist_btn"),
            ("🔑", "Password Book (Ctrl+Shift+K)", self._toggle_password_book, "_pb_btn"),
            ("✦⇄", "StarShare™ (Ctrl+Shift+S)", self._toggle_starshare, "_ss_btn"),
            ("⚙", "Settings (Ctrl+,)", self._open_settings, "_set_btn"),
            ("⌘", "Command Palette (Ctrl+P)", self._show_palette, "_palette_btn"),
        ]:
            btn = QPushButton(icon); btn.setObjectName("SidebarBtn")
            btn.setFixedSize(self._sidebar_target_width() - 12 if self._sidebar_expanded else 46, 46)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tip); btn.setAccessibleName(tip.split(" (")[0]); btn.clicked.connect(fn)
            btn._nav_label = tip
            btn._nav_icon = icon
            btn._nav_text = tip.split(" (")[0]
            if self._sidebar_expanded:
                btn.setText(f"{icon}  {btn._nav_text}")
                btn.setProperty("expanded", True)
            bot_layout.addWidget(btn)
            if attr: setattr(self, attr, btn)
            self._sidebar_bottom.append(btn)
        
        layout.addWidget(bot_nav)
        
        self._tab_buttons = []; self._closed_tab_urls = []; self._pinned_tabs = set()
        self._resize_sidebar_cards()

        return sidebar

    def _sidebar_target_width(self):
        return self._sidebar_expanded_w if self._sidebar_expanded else self._sidebar_collapsed_w

    def _set_sidebar_expanded(self, expanded):
        self._sidebar_expanded = bool(expanded)
        self._settings["sidebar_expanded"] = self._sidebar_expanded
        _save_settings(self._settings)
        self._resize_sidebar_cards()
        target_width = self._sidebar_target_width()
        self._sidebar_logo.setToolTip("Collapse sidebar" if expanded else "Expand sidebar")
        for button in self._sidebar_bottom:
            button.setText(
                f"{button._nav_icon}  {button._nav_text}" if expanded
                else button._nav_icon
            )
            button.setFixedSize(target_width - 12 if expanded else 46, 46)
            button.setProperty("expanded", expanded)
            button.style().unpolish(button)
            button.style().polish(button)
        auto_hide = self.fernway.get("sidebar_auto_hide") or self.fernway.get("sidebar_style") == "floating"
        if not auto_hide:
            self.sidebar.setMinimumWidth(target_width)
            self.sidebar.setMaximumWidth(target_width)
        elif self.sidebar.width() > 0:
            self.sidebar.setMinimumWidth(target_width)
            self.sidebar.setMaximumWidth(target_width)
        if self.fernway.get("sidebar_style") == "floating" and self.sidebar.width() > 0:
            self.sidebar.setGeometry(0, 0, target_width, self.height())
        self._repin_panels()

    def _resize_sidebar_cards(self):
        if not hasattr(self, "_tab_buttons"):
            return
        expanded = self._sidebar_expanded
        card_width = self._sidebar_expanded_w - 8 if expanded else 46
        for card in self._tab_buttons:
            card.setFixedWidth(card_width)
            fav = card.findChild(QLabel, "TabFav")
            if fav:
                size = 28 if expanded else 42
                fav.setFixedSize(size, size)
                fav.move(8 if expanded else (card_width - size) // 2, (46 - size) // 2)
                pixmap = fav.pixmap()
                if pixmap and not pixmap.isNull():
                    fav.setPixmap(pixmap.scaled(
                        size, size, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ))
            label = card.findChild(QLabel, "TabLabel")
            if label:
                label.setGeometry(44, 0, card_width - 70, 46)
                label.setVisible(expanded and self.fernway.get("tab_style", "default") not in ("compact", "glass"))
            close = card.findChild(QPushButton, "TabClose")
            if close:
                close.move(card_width - close.width() - 3, 2)

    def _add_tab_button(self, index, title, favicon=None):
        expanded = self._sidebar_expanded
        card_w = self._sidebar_expanded_w - 8 if expanded else 46
        card_h = 46
        
        card = QWidget(); card.setObjectName("TabCard"); card.setFixedSize(card_w, card_h)
        card.setProperty("active", False)
        
        _hide_lbl = not expanded  # Hide labels when collapsed
        
        # Favicon: 42x42, centered
        fav_size = 28 if expanded else 42
        fav = QLabel(card); fav.setObjectName("TabFav")
        fav.setFixedSize(fav_size, fav_size)
        fav.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fav.move((card_w - fav_size) // 2, (card_h - fav_size) // 2)
        if favicon and not favicon.isNull():
            scaled_pixmap = favicon.scaled(fav_size, fav_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            fav.setPixmap(scaled_pixmap)
        else:
            if title in ("New Tab", "Opal Discovery"):
                display = "✦"
            else:
                display = title[0].upper() if title and title.strip() else "•"
            fav.setText(display)
        label = QLabel(card)
        label.setObjectName("TabLabel")
        label.setText((title[:18] + "…") if len(title) > 18 else (title or "New Tab"))
        label.setGeometry(44, 0, card_w - 70, card_h)
        label.setVisible(expanded and self.fernway.get("tab_style", "default") not in ("compact", "glass"))
        
        # Close button: small pill at top-right, appears on hover
        close_size = 18
        close_btn = QPushButton("×", card); close_btn.setObjectName("TabClose")
        close_btn.setFixedSize(close_size, close_size)
        close_btn.move(card_w - close_size - 3, 2)
        close_btn.hide()
        close_btn.setToolTip("Close tab")
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 9px; font-size: 9pt; color: #888; }"
            "QPushButton:hover { background: rgba(220,80,80,0.4); color: #fff; border-radius: 9px; }"
        )
        card.setProperty("pinned", False)
        card.setAccessibleName(f"Tab: {title or 'New Tab'}")
        
        def _show_close(e):
            if not card.property("pinned"):
                close_btn.show()
        def _hide_close(e):
            close_btn.hide()
        card.enterEvent = _show_close
        card.leaveEvent = _hide_close
        
        card.mousePressEvent = lambda e, i=index: self._sidebar_tab_click(i)
        card.contextMenuEvent = lambda e, c=card: self._tab_card_context_menu(c, e.globalPos())
        self._tab_btn_layout.insertWidget(0, card); self._tab_buttons.insert(0, card)
        close_btn.clicked.connect(lambda _, c=card: self._close_tab_by_card(c))
        
        # Fly-down animation from divider line
        if index == 0:
            self._animate_tab_entry(card)

    def _animate_tab_entry(self, card):
        """Fly-down animation: card drops from divider, overshoots 4px, floats back."""
        m = _get_motion_params()
        
        # Cancel any previous entry animation
        if hasattr(self, '_tab_entry_anim') and self._tab_entry_anim is not None:
            self._tab_entry_anim.stop()
        if hasattr(self, '_tab_entry_overshoot') and self._tab_entry_overshoot is not None:
            self._tab_entry_overshoot.stop()
        
        # Force layout so we know the card's final position
        self._tab_btn_container.layout().activate()
        QApplication.processEvents()
        
        # Get divider's position in scroll area coordinates
        scroll = card.parentWidget().parentWidget()  # the scroll area
        div_global = self._sidebar_divider.mapToGlobal(QPoint(0, self._sidebar_divider.height()))
        target_pos = card.mapFromGlobal(div_global)
        
        start_y = target_pos.y()
        end_y = card.y()
        
        # Phase 1: Fly down to end_y + 4 (overshoot)
        self._tab_entry_anim = QPropertyAnimation(card, b"pos")
        self._tab_entry_anim.setDuration(int(m["in_ms"] * 1.2))
        self._tab_entry_anim.setStartValue(QPoint(card.x(), start_y))
        self._tab_entry_anim.setEndValue(QPoint(card.x(), end_y + 4))
        self._tab_entry_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Phase 2: Float back up 4px to actual position
        self._tab_entry_overshoot = QPropertyAnimation(card, b"pos")
        self._tab_entry_overshoot.setDuration(int(m["in_ms"] * 0.8))
        self._tab_entry_overshoot.setStartValue(QPoint(card.x(), end_y + 4))
        self._tab_entry_overshoot.setEndValue(QPoint(card.x(), end_y))
        self._tab_entry_overshoot.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        self._tab_entry_anim.finished.connect(self._tab_entry_overshoot.start)
        
        # Store card ref for cancellation on sidebar hide
        self._tab_entry_card = card
        self._tab_entry_end_pos = QPoint(card.x(), end_y)
        
        self._tab_entry_anim.start()

    def _close_tab_by_card(self, card):
        if card in self._tab_buttons: self._close_tab(self._tab_buttons.index(card))
        
    def _on_icon_changed(self, tab, icon):
        idx = self.tabs.indexOf(tab)
        if 0 <= idx < len(self._tab_buttons):
            card = self._tab_buttons[idx]
            fav = card.findChild(QLabel, "TabFav")
            if fav:
                if icon and not icon.isNull():
                    scaled_pixmap = icon.scaled(24,24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    fav.setPixmap(scaled_pixmap)
                else:
                    # Reset to text
                    title = tab.view.title()
                    if title in ("New Tab", "Opal Discovery"):
                        fav.setText("✦")
                    else:
                        display = title[0].upper() if title and title.strip() else "•"
                        fav.setText(display)

    def _repaint_under_popup(self):
        """Clear anything a closed popup may have left behind.

        A styled QMenu is a separate native popup window drawn on top of the
        frameless main window. When it closes, a hairline of its own border
        can survive in the backing store, and the QWebEngineView underneath
        does not repaint that strip by itself, so a stray line is left on
        screen. Force a repaint of the content area to wipe it out.
        """
        content = getattr(self, "_content_col", None)
        if content is None:
            return
        content.update()
        try:
            view = getattr(self._current_tab(), "view", None)
        except Exception:
            view = None
        if view is not None:
            view.update()

    def _repaint_region(self, rect):
        """Repaint a rectangle of the content area to wipe stale pixels.

        The bookmarks bar is drawn with a translucent background over the
        page, so when it is cleared Qt can leave the old pixels behind
        instead of blending the page back in.
        """
        content = getattr(self, "_content_col", None)
        if content is None or rect is None or rect.isEmpty():
            return
        content.update(rect)
        try:
            view = getattr(self._current_tab(), "view", None)
        except Exception:
            view = None
        if view is not None:
            offset = view.mapTo(content, QPoint(0, 0))
            view.update(rect.translated(-offset))

    def _tab_card_context_menu(self, card, pos):
        if card not in self._tab_buttons: return
        idx = self._tab_buttons.index(card)
        tab = self.tabs.widget(idx)
        pinned = tab in self._pinned_tabs if tab else False
        menu = QMenu(self)
        menu.addAction("Duplicate Tab",        lambda: self._duplicate_tab(idx))
        menu.addAction("Unpin Tab" if pinned else "Pin Tab", lambda: self._toggle_pin_tab(idx))
        menu.addSeparator()
        close_act = menu.addAction("Close Tab", lambda: self._close_tab(idx))
        close_act.setEnabled(not pinned)
        menu.exec(pos)
        self._repaint_under_popup()

    def _duplicate_tab(self, idx):
        tab = self.tabs.widget(idx)
        if tab:
            url = tab.view.url().toString()
            self._new_tab(url if url and not url.startswith("about:") else NORTHSTAR_HOME)

    def _toggle_pin_tab(self, idx):
        tab = self.tabs.widget(idx)
        if not tab: return
        if tab in self._pinned_tabs:
            self._pinned_tabs.discard(tab)
        else:
            self._pinned_tabs.add(tab)
        if 0 <= idx < len(self._tab_buttons):
            card = self._tab_buttons[idx]
            close_btn = card.findChild(QPushButton, "TabClose")
            pin_lbl   = card.findChild(QLabel,      "TabPin")
            pinned = tab in self._pinned_tabs
            card.setProperty("pinned", pinned)
            if close_btn: close_btn.setVisible(not pinned)
            if pin_lbl:   pin_lbl.setVisible(pinned)

    def _reopen_closed_tab(self):
        if self._closed_tab_urls:
            self._new_tab(self._closed_tab_urls.pop())

    def _remove_tab_button(self, index):
        if 0 <= index < len(self._tab_buttons):
            card = self._tab_buttons.pop(index)
            self._tab_btn_layout.removeWidget(card); card.deleteLater()
        self._refresh_tab_buttons()

    def _refresh_tab_buttons(self):
        active = self.tabs.currentIndex()
        for i, card in enumerate(self._tab_buttons):
            # OPT: only update lambda if indices might have shifted
            # (In this simplified version, we just re-set it, but we could be more surgical)
            card.mousePressEvent = lambda e, idx=i: self._sidebar_tab_click(idx)
            
            is_active = (i == active)
            new_name = "TabCardActive" if is_active else "TabCard"
            if card.objectName() != new_name:
                card.setProperty("active", is_active)
                card.setObjectName(new_name)
                card.setAccessibleDescription("Active tab" if is_active else "Inactive tab")
                # OPT: unpolish/polish is expensive, only do it if the name actually changed
                card.style().unpolish(card)
                card.style().polish(card)

    def _refresh_tab_label_visibility(self):
        hide = self.fernway.get("tab_style", "default") in ("compact", "glass") or not self._sidebar_expanded
        for card in self._tab_buttons:
            lbl = card.findChild(QLabel, "TabLabel")
            if lbl:
                if hide:
                    lbl.hide()
                else:
                    lbl.show()
                    title = card.toolTip() or "New"
                    short = (title[:18]+"…") if len(title)>18 else title
                    lbl.setText(short)

    def _sidebar_tab_click(self, index):
        self.tabs.setCurrentIndex(index); self._refresh_tab_buttons()

    def _update_tab_button_title(self, index, title):
        if 0 <= index < len(self._tab_buttons):
            card = self._tab_buttons[index]
            # OPT: avoid redundant tooltip updates
            if card.toolTip() == (title or "New Tab"):
                return
                
            letter = title[0].upper() if title and title.strip() else "•"
            fav = card.findChild(QLabel, "TabFav"); lbl = card.findChild(QLabel, "TabLabel")
            if fav and fav.pixmap() is None:
                fav.setText(letter)
            if lbl:
                hide_lbl = self.fernway.get("tab_style", "default") in ("compact", "glass") or not self._sidebar_expanded
                if hide_lbl:
                    lbl.hide()
                else:
                    lbl.show()
                    short = (title[:18]+"…") if len(title)>18 else (title or "New")
                    if lbl.text() != short:
                        lbl.setText(short)
            card.setToolTip(title or "New Tab")
            card.setAccessibleName(f"Tab: {title or 'New Tab'}")

    def _build_toolbar(self):
        bar = QWidget(); bar.setObjectName("Toolbar"); bar.setFixedHeight(45)
        bar.mousePressEvent       = self._toolbar_mouse_press
        bar.mouseMoveEvent        = self._toolbar_mouse_move
        bar.mouseReleaseEvent     = self._toolbar_mouse_release
        bar.mouseDoubleClickEvent = self._toolbar_double_click
        layout = QHBoxLayout(bar); layout.setContentsMargins(10,6,10,6); layout.setSpacing(2)
        def nav_btn(symbol, tip, fn):
            b = QPushButton(symbol); b.setObjectName("NavBtn"); b.setFixedSize(30,30)
            b.setToolTip(tip); b.setAccessibleName(tip.split(" (")[0])
            b.clicked.connect(fn); return b
        layout.addWidget(nav_btn("←","Back (Alt+Left)",   self._go_back))
        layout.addWidget(nav_btn("→","Forward (Alt+Right)",self._go_forward))
        layout.addWidget(nav_btn("⟳","Reload (Ctrl+R)",   self._reload))
        layout.addWidget(nav_btn("⌂","Home",              self._go_home))
        layout.addSpacing(6)
        
        # ── Address / Bookmarks Switcher ──────────────────
        self._toolbar_stack = QStackedWidget()
        
        # Area 1: Address Bar
        self.address = QLineEdit(); self.address.setObjectName("AddressBar")
        self.address.setPlaceholderText("Search or enter address…")
        self.address.setAccessibleName("Address and search bar")
        self.address.returnPressed.connect(self._navigate_from_bar)
        self.address.setClearButtonEnabled(True)
        self.address.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._toolbar_stack.addWidget(self.address)
        
        # Area 2: Inline Bookmarks
        self._inline_bm_container = QWidget()
        inline_layout = QHBoxLayout(self._inline_bm_container); inline_layout.setContentsMargins(0,0,0,0); inline_layout.setSpacing(4)
        self._inline_bm_layout = inline_layout
        self._toolbar_stack.addWidget(self._inline_bm_container)
        
        layout.addWidget(self._toolbar_stack, 1); layout.addSpacing(4)
        
        # Toggle Button
        self._switch_btn = QPushButton("📋"); self._switch_btn.setObjectName("NavBtn"); self._switch_btn.setFixedSize(30,30)
        self._switch_btn.setToolTip("Show Bookmarks (Ctrl+B)")
        self._switch_btn.setAccessibleName("Toggle bookmarks and address bar")
        self._switch_btn.clicked.connect(self._toggle_toolbar_mode)
        layout.addWidget(self._switch_btn); layout.addSpacing(4)
        
        self._bm_btn = QPushButton("★"); self._bm_btn.setObjectName("BmBtn"); self._bm_btn.setFixedSize(30,30)
        self._bm_btn.setToolTip("Bookmark this page (Ctrl+D)")
        self._bm_btn.setAccessibleName("Bookmark this page")
        self._bm_btn.clicked.connect(self._toggle_bookmark); layout.addWidget(self._bm_btn); layout.addSpacing(4)

        self._ext_btn = QPushButton("🧩"); self._ext_btn.setObjectName("NavBtn"); self._ext_btn.setFixedSize(30,30)
        self._ext_btn.setToolTip("Extensions")
        self._ext_btn.setAccessibleName("Extensions")
        self._ext_btn.clicked.connect(self._show_extensions_menu); layout.addWidget(self._ext_btn); layout.addSpacing(4)
        
        self._pip_btn = QPushButton("⧉"); self._pip_btn.setObjectName("NavBtn"); self._pip_btn.setFixedSize(30,30)
        self._pip_btn.setToolTip("Picture-in-Picture (Ctrl+Shift+P)")
        self._pip_btn.setAccessibleName("Picture in picture")
        self._pip_btn.clicked.connect(self._toggle_pip); layout.addWidget(self._pip_btn); layout.addSpacing(4)
        wnd_row = QHBoxLayout(); wnd_row.setContentsMargins(0,0,0,0); wnd_row.setSpacing(1)
        def wnd_btn(symbol, obj, tip, fn):
            b = QPushButton(symbol); b.setObjectName(obj); b.setFixedSize(30,30)
            b.setToolTip(tip); b.setAccessibleName(tip)
            b.clicked.connect(fn); return b
        wnd_row.addWidget(wnd_btn("─","WndMin","Minimise",self.showMinimized))
        self._max_btn = wnd_btn("□","WndMax","Maximise",self._toggle_maximise); wnd_row.addWidget(self._max_btn)
        wnd_row.addWidget(wnd_btn("✕","WndClose","Close",self.close)); layout.addLayout(wnd_row)
        return bar

    def _toggle_toolbar_mode(self):
        # Only toggle between address and inline bookmarks for the address mode
        current_mode = self.fernway.get("toolbar_mode", "address")
        if current_mode == "address":
            # Toggle the stack without changing the mode setting
            if self._toolbar_stack.currentIndex() == 0:
                self._toolbar_stack.setCurrentIndex(1)
                self._switch_btn.setText("🔍")
                self._switch_btn.setToolTip("Show Address Bar")
                self._update_inline_bookmarks()
            else:
                self._toolbar_stack.setCurrentIndex(0)
                self._switch_btn.setText("📋")
                self._switch_btn.setToolTip("Show Bookmarks")

    def _favicon_for_url(self, url: str, size: int = 16) -> QIcon:
        """Return a lazily decoded cached QIcon, or an empty icon."""
        try:
            domain = urlparse(url).netloc
        except Exception:
            domain = ""
        if not domain:
            return QIcon()
        cache_key = f"{domain}:{size}"
        cached = self._favicon_cache.get(cache_key)
        if cached is not None:
            return cached
        encoded = self._favicon_data_cache.get(domain)
        if encoded:
            try:
                pixmap = QPixmap()
                if pixmap.loadFromData(base64.b64decode(encoded)):
                    pixmap = pixmap.scaled(
                        size, size, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    cached = QIcon(pixmap)
                    self._favicon_cache[cache_key] = cached
                    return cached
            except (ValueError, TypeError):
                pass
        return QIcon()

    def _load_favicons_async(self, buttons_with_urls):
        """Download favicons for bookmark buttons in background threads."""
        for btn, url in buttons_with_urls:
            try:
                domain = urlparse(url).netloc
            except Exception:
                continue
            if not domain:
                continue
            cache_key = f"{domain}:16"
            if cache_key in self._favicon_cache:
                cached = self._favicon_cache[cache_key]
                if not cached.isNull():
                    btn.setIcon(cached)
                    btn.setIconSize(QSize(16, 16))
                continue
            with self._favicon_pending_lock:
                if domain in self._favicon_pending_domains:
                    self._favicon_waiting_buttons[domain].append(btn)
                    continue
                self._favicon_pending_domains.add(domain)
                self._favicon_waiting_buttons[domain] = [btn]
            self._favicon_executor.submit(self._download_favicon, btn, url, domain)

    def _download_favicon(self, btn, url, domain):
        """Download a single favicon in a background thread."""
        data = b""
        try:
            import requests
            r = requests.get(
                f"https://www.google.com/s2/favicons?domain={domain}&sz=32",
                timeout=3,
            )
            if r.status_code == 200:
                data = r.content
        except Exception:
            pass
        self.favicon_ready.emit(btn, data, domain)

    def _on_favicon_ready(self, btn, data, domain):
        """Apply downloaded favicon to a button (runs in GUI thread)."""
        with self._favicon_pending_lock:
            self._favicon_pending_domains.discard(domain)
            buttons = self._favicon_waiting_buttons.pop(domain, [btn])
        if not data:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            pixmap = pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon = QIcon(pixmap)
            self._favicon_cache[f"{domain}:16"] = icon
            # Persist raw data for next session
            if domain not in self._favicon_data_cache:
                encoded = base64.b64encode(data).decode("ascii")
                self._favicon_data_cache[domain] = encoded
                _global_favicon_data_cache[domain] = encoded
                _invalidate_newtab_cache()
                self._favicon_cache_save_timer.start()
            for waiting_btn in buttons:
                waiting_btn.setIcon(icon)
                waiting_btn.setIconSize(QSize(16, 16))

    def _persist_favicon_cache_async(self):
        writer = self._favicon_cache_save_thread
        if writer is not None and writer.is_alive():
            self._favicon_cache_save_timer.start()
            return
        snapshot = dict(self._favicon_data_cache)
        self._favicon_cache_save_thread = threading.Thread(
            target=_save_favicon_cache,
            args=(snapshot,),
            daemon=True,
        )
        self._favicon_cache_save_thread.start()

    def _show_bookmark_context_menu(self, btn, pos):
        """Right-click context menu for a toolbar bookmark button."""
        url = getattr(btn, '_bm_url', '')
        if not url:
            return
        menu = QMenu(self)
        menu.addAction("Open in New Tab", lambda: self._new_tab(url))
        menu.addAction("Remove Bookmark", lambda: self._remove_bookmark(url))
        menu.exec(btn.mapToGlobal(pos))
        self._repaint_under_popup()

    def _update_bookmarks_bar(self):
        while self._bookmarks_bar_layout.count():
            item = self._bookmarks_bar_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        left, _, right, _ = self._bookmarks_bar_layout.getContentsMargins()
        spacing = max(0, self._bookmarks_bar_layout.spacing())
        available_w = max(0, self._bookmarks_bar.width() - left - right)
        buttons = []
        visible_buttons = []
        for bm in self._bookmarks:
            title = bm.get("title") or bm.get("url")
            display = title[:15] + ".." if len(title) > 15 else title
            btn = QPushButton(display, self._bookmarks_bar)
            btn.setObjectName("BmBarBtn")
            btn.setToolTip(f"{title}\n{bm.get('url')}")
            btn.setIcon(self._favicon_for_url(bm.get("url", "")))
            btn.setIconSize(QSize(16, 16))
            btn._bm_url = bm.get("url", "")
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, b=btn: self._show_bookmark_context_menu(b, pos))
            btn.clicked.connect(lambda _, u=bm.get("url"): self._current_tab().navigate(u))

            btn.ensurePolished()
            buttons.append((btn, bm, btn.sizeHint().width()))

        total_w = sum(width for _, _, width in buttons)
        total_w += spacing * max(0, len(buttons) - 1)
        if total_w <= available_w:
            visible_count = len(buttons)
        else:
            arrow_width = 30
            space_for_buttons = max(0, available_w - arrow_width - spacing)
            visible_count = 0
            used_w = 0
            for _, _, button_width in buttons:
                required_w = button_width + (spacing if visible_count else 0)
                if used_w + required_w > space_for_buttons:
                    break
                used_w += required_w
                visible_count += 1

        for index, (btn, bm, _) in enumerate(buttons):
            if index < visible_count:
                self._bookmarks_bar_layout.addWidget(btn)
                visible_buttons.append((btn, bm.get("url", "")))
            else:
                btn.deleteLater()

        overflow_list = self._bookmarks[visible_count:]
        if overflow_list:
            more_btn = QPushButton("»"); more_btn.setObjectName("NavBtn"); more_btn.setFixedSize(30,30)
            more_btn.clicked.connect(lambda: self._show_bookmarks_overflow(overflow_list, more_btn))
            self._bookmarks_bar_layout.addWidget(more_btn)
            
        self._bookmarks_bar_layout.addStretch()
        self._bookmarks_bar_layout_width = self._bookmarks_bar.width()
        self._load_favicons_async(visible_buttons)
        # The bar sits on a translucent background, so the buttons that were
        # just replaced can leave their old pixels behind. Wipe the strip.
        self._repaint_region(self._bookmarks_bar.geometry())

    def _set_toolbar_overlay(self, on):
        """Switch toolbar between overlay (newtab) and layout (regular pages) mode."""
        if on == self._toolbar_overlay_mode:
            return
        self._toolbar_overlay_mode = on
        content_col = self._content_col
        col_layout = self._col_layout
        toolbar = self._toolbar_widget
        # Suppress visual updates during layout switch to prevent flicker
        content_col.setUpdatesEnabled(False)
        try:
            if on:
                # Pull toolbar out of layout → floating overlay with transparency
                col_layout.removeWidget(toolbar)
                toolbar.setParent(content_col)
                toolbar.raise_()
                # Use the same global #Toolbar QSS as the layout mode so the
                # overlay matches search-results pages exactly (theme-aware bg
                # and border). Only the position differs (floating vs. inline).
                self._reposition_toolbar()
            else:
                # Put toolbar back into layout → normal opaque toolbar
                toolbar.setStyleSheet("")
                toolbar.setParent(content_col)
                col_layout.insertWidget(0, toolbar)
                toolbar.setFixedHeight(45)
                toolbar.show()
                # Progress bar stays in layout — just clear any floating geometry
                if hasattr(self, 'progress'):
                    self.progress.setGeometry(0, 0, 0, 0)
            # Re-apply toolbar mode to re-set up hover handlers after reparenting
            self._apply_toolbar_mode()
        finally:
            content_col.setUpdatesEnabled(True)

    def _is_newtab_url(self, url):
        return url and (url.startswith("northstar://newtab") or url.rstrip("/") == "northstar://newtab")

    def _apply_toolbar_mode(self):
        """Update the toolbar mode based on Fernway settings."""
        mode = self.fernway.get("toolbar_mode", "address")
        
        # Stop the previous hover behavior before changing modes.
        if hasattr(self, '_bm_hover_timer'):
            self._bm_hover_timer.stop()
        self._bm_hover_active = False
        hover_anim = getattr(self, "_bm_hover_anim", None)
        if hover_anim is not None:
            hover_anim.stop()
            self._bm_hover_anim = None
        if not hasattr(self, "_bm_hover_poll_timer"):
            self._bm_hover_poll_timer = QTimer(self)
            self._bm_hover_poll_timer.setInterval(50)
            self._bm_hover_poll_timer.timeout.connect(self._update_bookmark_hover)
        self._bm_hover_poll_timer.stop()
        if not hasattr(self, "_bm_hover_timer"):
            self._bm_hover_timer = QTimer(self)
            self._bm_hover_timer.setSingleShot(True)
            self._bm_hover_timer.timeout.connect(self._finish_bookmark_hover)
        
        if mode == "address":
            # Original behavior: stack with address/inline bookmarks, toggle button visible
            self._toolbar_stack.setVisible(True)
            self._switch_btn.setVisible(True)
            self._bookmarks_bar.hide()
            
            if self._toolbar_stack.currentIndex() == 1:
                self._switch_btn.setText("🔍")
                self._switch_btn.setToolTip("Show Address Bar")
                self._update_inline_bookmarks()
            else:
                self._switch_btn.setText("📋")
                self._switch_btn.setToolTip("Show Bookmarks")
                
        elif mode == "hover" or mode == "always":
            # Use separate bookmarks bar as overlay below toolbar
            self._toolbar_stack.setCurrentIndex(0)
            self._toolbar_stack.setVisible(True)
            self._switch_btn.setVisible(False)
            
            pw = self._content_col.width() if self._content_col.width() > 0 else self.width()
            self._position_bookmarks_bar(pw)
            
            # Update bookmarks bar
            self._update_bookmarks_bar()
            QTimer.singleShot(100, self._update_bookmarks_bar)
            
            if mode == "always":
                self._position_bookmarks_bar(pw)
                self._bookmarks_bar.show()
                self._bookmarks_bar.raise_()
            else:  # hover mode
                self._bookmarks_bar.setGeometry(
                    0, self._toolbar_widget.y() + self._toolbar_widget.height(), pw, 0
                )
                self._bookmarks_bar.hide()
                self._bm_hover_poll_timer.start()

    def _position_bookmarks_bar(self, width=None):
        """Keep the overlay directly below the toolbar in content coordinates."""
        width = width or self._content_col.width()
        toolbar_bottom = self._toolbar_widget.y() + self._toolbar_widget.height()
        bar = self._bookmarks_bar
        animation = getattr(self, "_bm_hover_anim", None)
        mode = self.fernway.get("toolbar_mode", "address")
        if mode == "always":
            height = 40
        elif mode == "hover" and animation is None and not self._bm_hover_active:
            height = 0
        else:
            height = bar.height()
        bar.setGeometry(0, toolbar_bottom, width, height)
        if animation is not None:
            animation.setEndValue(QRect(
                0, toolbar_bottom, width,
                40 if getattr(self, "_bm_hover_anim_show", False) else 0,
            ))
        self._bookmarks_bar.raise_()

    def _pointer_over_bookmark_toolbar(self):
        """Check the full toolbar row, including spacing between its controls."""
        if not self._toolbar_widget.isVisible() or not self._content_col.isVisible():
            return False
        cursor = self._content_col.mapFromGlobal(QCursor.pos())
        toolbar_top = self._toolbar_widget.y()
        toolbar_bottom = toolbar_top + self._toolbar_widget.height()
        toolbar_hot_zone = QRect(
            0, toolbar_top, self._content_col.width(), toolbar_bottom - toolbar_top
        )
        if toolbar_hot_zone.contains(cursor):
            return True
        return (
            self._bookmarks_bar.isVisible()
            and self._bookmarks_bar.geometry().contains(cursor)
        )

    def _update_bookmark_hover(self):
        """Reveal bookmarks while the pointer is over any part of the toolbar."""
        if self.fernway.get("toolbar_mode") != "hover":
            self._bm_hover_poll_timer.stop()
            return
        if self._pointer_over_bookmark_toolbar():
            self._bm_hover_timer.stop()
            if not self._bm_hover_active:
                self._bm_hover_active = True
                self._position_bookmarks_bar()
                self._animate_bookmarks_bar(True)
        elif self._bm_hover_active and not self._bm_hover_timer.isActive():
            self._bm_hover_timer.start(200)

    def _animate_bookmarks_bar(self, show):
        """Slide the hover bookmarks bar open by animating its overlay geometry."""
        bar = self._bookmarks_bar
        previous = getattr(self, "_bm_hover_anim", None)
        if previous is not None:
            previous.stop()

        width = self._content_col.width()
        toolbar_bottom = self._toolbar_widget.y() + self._toolbar_widget.height()
        current_geometry = bar.geometry()
        start_geometry = QRect(0, toolbar_bottom, width, current_geometry.height())
        end_geometry = QRect(0, toolbar_bottom, width, 40 if show else 0)
        bar.setGeometry(start_geometry)
        if show:
            bar.show()
            bar.raise_()
        elif not bar.isVisible():
            return

        animation = QPropertyAnimation(bar, b"geometry", self)
        animation.setDuration(_get_motion_params()["in_ms"])
        animation.setStartValue(start_geometry)
        animation.setEndValue(end_geometry)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._bm_hover_anim_show = show
        if not show:
            def hide_after_fade():
                if (self.fernway.get("toolbar_mode") == "hover"
                        and not self._bm_hover_active
                        and not self._pointer_over_bookmark_toolbar()):
                    bar.hide()
                    bar.setGeometry(
                        0, self._toolbar_widget.y() + self._toolbar_widget.height(),
                        self._content_col.width(), 0,
                    )
                    self._repaint_region(QRect(
                        0, self._toolbar_widget.y() + self._toolbar_widget.height(),
                        self._content_col.width(), 40,
                    ))
                if self._bm_hover_anim is animation:
                    self._bm_hover_anim = None
                    self._bm_hover_anim_show = False

            animation.finished.connect(hide_after_fade)
        else:
            animation.finished.connect(
                lambda: self._finish_bookmarks_bar_animation(animation)
            )
        self._bm_hover_anim = animation
        animation.start()

    def _finish_bookmarks_bar_animation(self, animation):
        if self._bm_hover_anim is animation:
            self._bm_hover_anim = None
            self._bm_hover_anim_show = False

    def _finish_bookmark_hover(self):
        if self.fernway.get("toolbar_mode") != "hover":
            self._bm_hover_active = False
            return
        if self._pointer_over_bookmark_toolbar():
            self._bm_hover_timer.stop()
            self._bm_hover_active = True
            self._position_bookmarks_bar()
            self._animate_bookmarks_bar(True)
        else:
            self._bm_hover_active = False
            self._animate_bookmarks_bar(False)

    def _update_inline_bookmarks(self):
        # Clear existing
        while self._inline_bm_layout.count():
            item = self._inline_bm_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        # We need to measure how many fit.
        # This is a bit tricky with dynamic width, so we'll use a simple approach:
        # Fill until overflow.
        available_w = self._toolbar_stack.width() - 40 # space for 'more' button
        current_w = 0
        
        overflow_list = []
        visible_buttons = []
        for i, bm in enumerate(self._bookmarks):
            title = bm.get("title") or bm.get("url")
            # Truncate
            display = title[:15] + ".." if len(title) > 15 else title
            
            btn = QPushButton(display); btn.setObjectName("BmBarBtn")
            btn.setToolTip(f"{title}\n{bm.get('url')}")
            btn.setIcon(self._favicon_for_url(bm.get("url", "")))
            btn.setIconSize(QSize(16, 16))
            btn._bm_url = bm.get("url", "")
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, b=btn: self._show_bookmark_context_menu(b, pos))
            btn.clicked.connect(lambda _, u=bm.get("url"): self._current_tab().navigate(u))
            
            # Simple width estimation (avg char width + padding)
            btn_w = len(display) * 7 + 24
            if current_w + btn_w < available_w:
                self._inline_bm_layout.addWidget(btn)
                current_w += btn_w + 4
                visible_buttons.append((btn, bm.get("url", "")))
            else:
                overflow_list.append(bm)
                
        if overflow_list:
            more_btn = QPushButton("»"); more_btn.setObjectName("NavBtn"); more_btn.setFixedSize(30,30)
            more_btn.clicked.connect(lambda: self._show_bookmarks_overflow(overflow_list, more_btn))
            self._inline_bm_layout.addWidget(more_btn)
            
        self._inline_bm_layout.addStretch()
        self._load_favicons_async(visible_buttons)

    def _show_bookmarks_overflow(self, bookmarks, target_widget):
        menu = QMenu(self)
        for bm in bookmarks:
            title = bm.get("title") or bm.get("url")
            act = menu.addAction(title)
            act.triggered.connect(lambda _, u=bm.get("url"): self._current_tab().navigate(u))
        menu.exec(target_widget.mapToGlobal(QPoint(0, target_widget.height())))
        self._repaint_under_popup()

    def _toolbar_mouse_press(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _toolbar_mouse_move(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            if self.isMaximized():
                ratio = e.position().x() / self.width(); self.showNormal()
                self.move(int(e.globalPosition().x() - self.width()*ratio), 0)
                self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def _toolbar_mouse_release(self, e): self._drag_pos = None

    def _toolbar_double_click(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._toggle_maximise()

    def _toggle_maximise(self):
        if self.isMaximized(): self.showNormal(); self._max_btn.setText("□"); self._max_btn.setToolTip("Maximise")
        else: self.showMaximized(); self._max_btn.setText("❐"); self._max_btn.setToolTip("Restore")

    def _setup_shortcuts(self):
        for key, fn in {
            "Ctrl+T":       lambda: self._new_tab(),
            "Ctrl+Shift+T": self._reopen_closed_tab,
            "Ctrl+W":       self._close_current_tab,
            "Ctrl+R":       self._reload,
            "Ctrl+Shift+R": self._hard_reload,
            "Ctrl+L":       self._focus_address,
            "Alt+Left":     self._go_back,
            "Alt+Right":    self._go_forward,
            "Ctrl+Shift+A": self._toggle_ai,
            "Ctrl+J":       self._toggle_downloads,
            "Ctrl+Shift+K": self._toggle_password_book,
            "Ctrl+H":       self._toggle_history,
            "Ctrl+F":       self._toggle_find,
            "Ctrl+Shift+S": self._toggle_starshare,
            "Ctrl+,":       self._open_settings,
            "Ctrl+P":       self._show_palette,
            "Ctrl++":       self._zoom_in,
            "Ctrl+=":       self._zoom_in,
            "Ctrl+-":       self._zoom_out,
            "Ctrl+0":       self._zoom_reset,
            "Ctrl+Shift+P": self._toggle_pip,   
            "Ctrl+D":       self._toggle_bookmark,
            "F11":          self._toggle_fullscreen,
            "Escape":       self._on_escape,
        }.items():
            QShortcut(QKeySequence(key), self).activated.connect(fn)

    # ── TAB MANAGEMENT ───────────────────────
    def _new_tab(self, url=NORTHSTAR_HOME, switch_to=True):
        tab = BrowserTab(self.profile, policy_manager=self.popup_policy)
        tab.title_changed.connect(lambda t, tab=tab: self._on_title_changed(tab, t))
        tab.url_changed.connect(self._on_url_changed)
        tab.load_progress.connect(self._on_load_progress)
        tab.icon_changed.connect(lambda icon, tab=tab: self._on_icon_changed(tab, icon))
        tab.remove_bookmark_requested.connect(self._on_remove_bookmark_from_newtab)
        tab.move_bookmark_requested.connect(self._on_move_bookmark_from_newtab)
        tab.import_bookmarks_requested.connect(self._on_import_bookmarks_from_newtab)
        tab.clear_bookmarks_requested.connect(self._on_clear_bookmarks_requested)
        tab.new_window_requested.connect(lambda url, tab=tab: self._new_tab(url))
        tab.view.page().linkHovered.connect(self._on_link_hovered)
        tab.view.installEventFilter(self)
        idx = self.tabs.insertTab(0, tab, "New Tab"); self._add_tab_button(0, "New Tab")
        if switch_to:
            self.tabs.setCurrentIndex(0)
        se = SEARCH_ENGINES.get(self._settings.get("search_engine", "Google"), "https://www.google.com/search?q={}")
        tab.navigate(url, self._bookmarks, search_engine_url=se, dark_mode=self._dark_mode)
        return tab

    def _close_tab(self, idx):
        tab = self.tabs.widget(idx)
        if not tab or tab in self._pinned_tabs:
            return   # pinned or invalid — ignore close
        
        if self.tabs.count() == 1:
            self._new_tab()
            idx += 1   # _new_tab inserted at index 0, old tab shifted to idx+1

        if hasattr(tab, 'view') and tab.view:
            url = tab.view.url().toString()
            if url and url not in (NORTHSTAR_HOME, "northstar://newtab", "about:blank", ""):
                self._closed_tab_urls.append(url)
                if len(self._closed_tab_urls) > 20:
                    self._closed_tab_urls.pop(0)
            
            # ── AGGRESSIVE MEDIA STOP ────────────────────────────────────────
            page = tab.view.page()
            if page:
                page.setAudioMuted(True)
                page.triggerAction(QWebEnginePage.WebAction.Stop)
                tab.view.load(QUrl("about:blank"))
                # Disconnect all signals before replacing page
                try:
                    page.new_window_requested.disconnect()
                except (TypeError, AttributeError):
                    pass
                try:
                    page.featurePermissionRequestCanceled.disconnect()
                except (TypeError, AttributeError):
                    pass
                # Explicitly release the page's web channel + interceptor so the
                # renderer cannot keep the bridge/alive after the tab is gone.
                if hasattr(page, "shutdown"):
                    page.shutdown()
                # Replace page to detach from view
                tab.view.setPage(None)

        self._pinned_tabs.discard(tab)
        self._remove_tab_button(idx); self.tabs.removeTab(idx); self._refresh_tab_buttons()
        
        # ── EXPLICIT DESTRUCTION ─────────────────────────────────────────────
        tab.deleteLater()

    def _close_current_tab(self): self._close_tab(self.tabs.currentIndex())
    def _current_tab(self): return self.tabs.currentWidget()

    def _on_tab_changed(self, idx):
        tab = self.tabs.widget(idx)
        if tab:
            url = tab.view.url().toString()
            if self.address.text() != url:
                self.address.setText(url)
            # Only toggle toolbar overlay once the new tab actually has a URL.
            # Skipping on about:blank prevents the flicker when a new tab is
            # just-inserted (url is empty) and is about to load northstar://newtab.
            if url and url not in ("about:blank", ""):
                self._set_toolbar_overlay(self._is_newtab_url(url))
        self._refresh_tab_buttons()

    def _on_title_changed(self, tab, title):
        idx = self.tabs.indexOf(tab)
        if idx >= 0:
            # OPT: Tab bar is hidden, so setTabText is redundant.
            # We only need to update the custom sidebar tab button.
            self._update_tab_button_title(idx, title)

    def _on_link_hovered(self, url: str):
        """Show / hide the floating hover-URL label à la Chrome."""
        if url:
            self._hover_hide_timer.stop()
            # Truncate very long URLs so the label never crowds the window.
            display = url if len(url) <= 80 else url[:77] + "…"
            self._hover_label.setText(display)
            self._hover_label.adjustSize()
            self._reposition_hover_label()
            self._hover_label.show()
            self._hover_label.raise_()
        else:
            # Small delay prevents flickering when moving between adjacent links.
            self._hover_hide_timer.start()

    def _reposition_hover_label(self):
        """Pin the hover label to the bottom-left corner of the content area."""
        parent = self._hover_label.parent()
        if parent:
            margin = 6
            x = margin
            y = parent.height() - self._hover_label.height() - margin
            self._hover_label.move(x, y)

    def _on_url_changed(self, url):
        try:
            tab = self._current_tab()
            if tab and tab.view.url().toString() == url:
                if self.address.text() != url:
                    self.address.setText(url)
                    self.address.setCursorPosition(0)
                
                # Toggle toolbar overlay mode for newtab vs regular pages
                self._set_toolbar_overlay(self._is_newtab_url(url))
                
                # OPT: avoid redundant history entries for the same URL in a row
                if not self._history or self._history[-1] != url:
                    self._history.append(url)
                    if len(self._history) > 500: self._history = self._history[-500:]
                    self.history_panel.add_entry(url, tab.view.title())
                
                self._refresh_bookmark_btn()
        except Exception as _url_err:
            try:
                _crash_msg = f"[NorthStar] _on_url_changed error: {_url_err}\n{_traceback_mod.format_exc()}"
                sys.stderr.write(_crash_msg + "\n")
                sys.stderr.flush()
                with open(_CRASH_LOG, "a", encoding="utf-8") as _f:
                    _f.write(_crash_msg + "\n")
            except Exception:
                pass

    def _on_load_progress(self, pct):
        if pct < 100:
            if not self.progress.isVisible(): self.progress.show()
            self.progress.setValue(pct)
        elif self.progress.isVisible():
            self.progress.hide()

    # ── LAZY INITIALIZERS ─────────────────────────────
    def _get_ns_search(self):
        if self._ns_search is None:
            from legacy.experimental_search.northstar_search import NorthStarSearch
            self._ns_search = NorthStarSearch()
        return self._ns_search

    def _get_search_manager(self):
        if self._search_manager is None:
            from legacy.experimental_search.search import SearchManager
            self._search_manager = SearchManager()
        return self._search_manager

    def _get_enrichment(self):
        if self._enrichment is None:
            from content import EnrichmentManager, FirecrawlContentProvider
            self._enrichment = EnrichmentManager(worker_count=2)
            self._enrichment.add_provider(FirecrawlContentProvider())
            self._enrichment.on_profile_ready = self._on_enrichment_ready
            self._enrichment.start()
        return self._enrichment

    # ── NAVIGATION ───────────────────────────
    def _navigate_from_bar(self):
        try:
            tab = self._current_tab()
            if not tab:
                return
            text = self.address.text().strip()
            if not text:
                return
            if self._get_ns_search().is_url(text):
                # Real URL — navigate normally
                tab.navigate(self._get_ns_search().format_url(text))
            else:
                # Route searches through the provider selected in Settings.
                search_url = SEARCH_ENGINES.get(
                    self._settings.get("search_engine", "Google"),
                    SEARCH_ENGINES["Google"],
                )
                tab.navigate(text, search_engine_url=search_url)
        except Exception as _nav_err:
            try:
                _crash_msg = f"[NorthStar] _navigate_from_bar error: {_nav_err}\n{_traceback_mod.format_exc()}"
                sys.stderr.write(_crash_msg + "\n")
                sys.stderr.flush()
                with open(_CRASH_LOG, "a", encoding="utf-8") as _f:
                    _f.write(_crash_msg + "\n")
            except Exception:
                pass

    def _opal_search(self, query: str, tab=None):
        """Launch an Opal Discovery search in the given (or current) tab."""
        tab = tab or self._current_tab()
        # Guard: ensure tab still exists (e.g. if closed during search trigger)
        try:
            if not tab or not hasattr(tab, 'view') or tab.view is None:
                return
        except RuntimeError:
            return

        dark = self._dark_mode
        url = tab.view.url().toString()
        if url.startswith("opal://discovery/results"):
            # Already in Discovery shell, just show loading state via JS
            tab.view.page().runJavaScript(f"if(typeof showLoading==='function') showLoading({json.dumps(query)});")
        else:
            # Full shell load
            tab.view.setHtml(
                _build_opal_loading_html(query, dark_mode=dark),
                QUrl("opal://discovery/results"),
            )
        
        worker = OpalSearchWorker(query, self._get_ns_search(), self._get_search_manager())

        def _on_ready(q, r, leo_summary, _w=worker):
            _log("UI", f"Phase 1 ready: {len(r)} results for {q!r}")
            
            # Enqueue URLs for background enrichment
            for result in r:
                url = result.get("url", "")
                if url and url.startswith("http"):
                    self._get_enrichment().enqueue(url)
            
            try:
                if not tab or not hasattr(tab, 'view') or tab.view is None:
                    return
                # Always do a full load with pagination!
                videos = getattr(_w, '_videos', None)
                load_time = getattr(_w, '_load_time', None)
                from_cache = getattr(_w, '_from_cache', False)
                tab.view.setHtml(
                    _build_opal_html(q, r, related_links=None, dark_mode=dark, leo_summary="", videos=videos, load_time=load_time, from_cache=from_cache),
                    QUrl("opal://discovery/results"),
                )
            except RuntimeError:
                return

        def _on_failed(err, _w=worker):
            _log("UI_ERR", f"Opal search failed: {err}")
            try:
                if not tab or not hasattr(tab, 'view') or tab.view is None:
                    return
                tab.view.setHtml(
                    _build_opal_error_html(query, err),
                    QUrl("opal://discovery/results"),
                )
            except RuntimeError:
                pass
            self._opal_workers.discard(_w)

        def _on_result(q, result_dict, _t=tab):
            try:
                if not _t or not hasattr(_t, 'view') or _t.view is None:
                    return
                # Inject the individual progressive result!
                safe_result = json.dumps(result_dict)
                _t.view.page().runJavaScript(f"if(typeof addResult==='function') addResult({safe_result});")
            except RuntimeError:
                return

        worker.results_ready.connect(_on_ready)
        worker.result_ready.connect(_on_result)
        worker.failed.connect(_on_failed)
        worker.finished.connect(lambda: self._opal_workers.discard(worker))
        worker.images_ready.connect(
            lambda q, i, _t=tab: self._on_opal_images_ready(_t, q, i)
        )
        worker.videos_ready.connect(
            lambda q, v, _t=tab: self._on_opal_videos_ready(_t, q, v)
        )
        self._opal_workers.add(worker)
        worker.start()

    def _on_opal_images_ready(self, tab, query: str, images: list) -> None:
        """Inject Image Results into the already-rendered Opal page via JS."""
        try:
            if not tab or not hasattr(tab, 'view') or tab.view is None:
                return
            url = tab.view.url().toString()
        except RuntimeError:
            return

        if not url.startswith("opal://"):
            return
        
        _log("UI", f"Received {len(images)} images for {query!r}. Generating HTML...")
        # Build the HTML fragment with the experimental Opal renderer.
        from legacy.experimental_search.opal_html_v2 import _build_images
        html_fragment = _build_images(images)
        _log("UI", f"Generated HTML length: {len(html_fragment)}")
        
        safe_html = json.dumps(html_fragment)
        tab.view.page().runJavaScript(
            f"if(typeof injectImages==='function') {{ injectImages({safe_html}); }} else {{ console.error('injectImages not found'); }}"
        )
        
    def _on_opal_videos_ready(self, tab, query: str, videos: list) -> None:
        """Inject Related Videos into the already-rendered Opal page via JS."""
        try:
            if not tab or not hasattr(tab, 'view') or tab.view is None:
                return
            url = tab.view.url().toString()
        except RuntimeError:
            return

        if not url.startswith("opal://"):
            return
        
        _log("UI", f"Received {len(videos)} videos for {query!r}. Generating HTML...")
        from legacy.experimental_search.opal_html_v2 import _build_videos
        html_fragment = _build_videos(videos, query)
        _log("UI", f"Generated HTML length: {len(html_fragment)}")
        
        safe_html = json.dumps(html_fragment)
        tab.view.page().runJavaScript(
            f"if(typeof injectVideos==='function') {{ injectVideos({safe_html}); }} else {{ console.error('injectVideos not found'); }}"
        )

    def _on_enrichment_ready(self, url: str) -> None:
        """Called when a page profile is enriched in the background."""
        profile = self._get_enrichment().get_profile(url)
        if profile:
            _log("ENRICH", f"Profile ready for {url}: {profile.title or 'No title'}")



    def _opal_show_images(self, query: str, tab=None):
        """Show a dedicated full-screen image results page for the query."""
        tab = tab or self._current_tab()
        try:
            if not tab or not hasattr(tab, 'view') or tab.view is None:
                return
        except RuntimeError:
            return

        _log("UI", f"Opening full image results for {query!r}")
        dark = self._dark_mode
        
        # 1. Show a loading state if we're not already there
        # (We reuse the same worker/logic but with a different rendering target)
        worker = OpalSearchWorker(query, self._get_ns_search(), self._get_search_manager())
        
        def _on_images(q, images, _t=tab):
            if not _t or not hasattr(_t, 'view') or _t.view is None: return
            from legacy.experimental_search.opal_html_v2 import _build_image_results_page
            full_html = _build_image_results_page(q, images, dark_mode=dark)
            _t.view.setHtml(full_html, QUrl(f"opal://discovery/images?q={quote_plus(q)}"))
            self._opal_workers.discard(worker)

        def _on_failed(err):
            _log("UI_ERR", f"Image search failed: {err}")
            self._opal_workers.discard(worker)

        worker.images_ready.connect(_on_images)
        worker.failed.connect(_on_failed)
        worker.finished.connect(lambda: self._opal_workers.discard(worker))
        
        self._opal_workers.add(worker)
        worker.start()

    def _go_back(self):
        tab = self._current_tab()
        if tab: tab.view.back()
    def _go_forward(self):
        tab = self._current_tab()
        if tab: tab.view.forward()
    def _reload(self):
        tab = self._current_tab()
        if tab:
            tab.view.reload()
    def _hard_reload(self):
        tab = self._current_tab()
        if tab:
            tab.view.page().triggerAction(QWebEnginePage.WebAction.ReloadAndBypassCache)
    def _go_home(self):
        tab = self._current_tab()
        if tab:
            home = self._settings.get("homepage", NORTHSTAR_HOME) or NORTHSTAR_HOME
            tab.navigate(home, self._bookmarks, dark_mode=self._dark_mode)
    def _focus_address(self): self.address.setFocus(); self.address.selectAll()
    def _zoom_in(self):
        tab = self._current_tab()
        if tab: tab.zoom_in()
    def _zoom_out(self):
        tab = self._current_tab()
        if tab: tab.zoom_out()
    def _zoom_reset(self):
        tab = self._current_tab()
        if tab: tab.zoom_reset()
    def _get_current_title(self):
        tab = self._current_tab(); return tab.view.title() if tab else ""

    # ── BOOKMARKS ────────────────────────────
    def _bookmark_current(self):
        tab = self._current_tab()
        if not tab: return
        url = tab.view.url().toString(); title = tab.view.title() or url
        if url.startswith("northstar://") or not url.startswith("http"):
            self.status_bar.showMessage("Cannot bookmark this page.", 3000); return
        if url in self._bookmark_urls:
            self.status_bar.showMessage(f"✦ Already bookmarked: {title[:50]}", 3000); return
        self._bookmarks.append({"title":title,"url":url}); self._bookmark_urls.add(url)
        _save_bookmarks(self._bookmarks); _invalidate_newtab_cache()   # OPT: invalidate cache
        self.status_bar.showMessage(f"✦ Bookmarked: {title[:50]}", 3000)
        self._refresh_bookmark_btn()
        # Update bookmarks displays
        mode = self.fernway.get("toolbar_mode", "address")
        if mode == "address" and self._toolbar_stack.currentIndex() == 1:
            self._update_inline_bookmarks()
        elif mode in ("hover", "always"):
            self._update_bookmarks_bar()

    def _remove_bookmark(self, url):
        self._bookmarks = [b for b in self._bookmarks if b.get("url") != url]
        self._bookmark_urls.discard(url); _save_bookmarks(self._bookmarks)
        _invalidate_newtab_cache()
        self._refresh_bookmark_btn()
        # Update bookmarks displays
        mode = self.fernway.get("toolbar_mode", "address")
        if mode == "address" and self._toolbar_stack.currentIndex() == 1:
            self._update_inline_bookmarks()
        elif mode in ("hover", "always"):
            self._update_bookmarks_bar()

    def _on_remove_bookmark_from_newtab(self, url):
        """Called when the user removes a bookmark via the newtab right-click menu."""
        self._remove_bookmark(url)
        self._refresh_newtab_pages()
        self.status_bar.showMessage("✦ Bookmark removed.", 3000)

    def _on_move_bookmark_from_newtab(self, url, direction):
        index = next((i for i, bookmark in enumerate(self._bookmarks)
                      if bookmark.get("url") == url), -1)
        if index < 0:
            return
        target = index - 1 if direction == "up" else index + 1
        if not 0 <= target < len(self._bookmarks):
            return
        self._bookmarks[index], self._bookmarks[target] = (
            self._bookmarks[target], self._bookmarks[index]
        )
        _save_bookmarks(self._bookmarks)
        _invalidate_newtab_cache()
        self._refresh_bookmark_displays()
        self._refresh_newtab_pages()
        self.status_bar.showMessage("Bookmark shortcut reordered.", 2500)

    def _refresh_newtab_pages(self):
        search_url = SEARCH_ENGINES.get(
            self._settings.get("search_engine", "Google"),
            SEARCH_ENGINES["Google"],
        )
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if tab and self._is_newtab_url(tab.view.url().toString()):
                tab._last_html = None
                tab.navigate(
                    NORTHSTAR_HOME,
                    self._bookmarks,
                    search_engine_url=search_url,
                    dark_mode=self._dark_mode,
                )

    def _refresh_bookmark_displays(self):
        mode = self.fernway.get("toolbar_mode", "address")
        if mode == "address" and self._toolbar_stack.currentIndex() == 1:
            self._update_inline_bookmarks()
        elif mode in ("hover", "always"):
            self._update_bookmarks_bar()

    def _on_clear_bookmarks_requested(self):
        if not self._bookmarks:
            self.status_bar.showMessage("No bookmarks to clear.", 3000)
            return
        answer = QMessageBox.question(
            self,
            "Clear Bookmarks",
            "Are you sure you want to clear all bookmarks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._bookmarks.clear()
        self._bookmark_urls.clear()
        _save_bookmarks(self._bookmarks)
        _invalidate_newtab_cache()
        self._refresh_bookmark_btn()
        mode = self.fernway.get("toolbar_mode", "address")
        if mode == "address" and self._toolbar_stack.currentIndex() == 1:
            self._update_inline_bookmarks()
        elif mode in ("hover", "always"):
            self._update_bookmarks_bar()
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if tab and self._is_newtab_url(tab.view.url().toString()):
                tab._last_html = None
                tab.navigate(NORTHSTAR_HOME, self._bookmarks, dark_mode=self._dark_mode)
        self.status_bar.showMessage("All bookmarks cleared.", 3000)

    def _on_import_bookmarks_from_newtab(self):
        """Auto-detect installed browsers and import their bookmarks. If
        more than one browser is found, present a picker. Always offers an
        "Import from file…" fallback that uses a Netscape HTML export.
        """
        sources = _detect_installed_browsers()

        chosen = self._prompt_bookmark_source(sources)

        if not chosen:
            return

        self._import_bookmark_sources(chosen)

    def _import_bookmark_sources(self, chosen):
        # Flatten chosen sources into one list, dedup across them.
        seen: set = set()
        merged: list = []
        for _name, bms in chosen:
            for bm in bms:
                if bm["url"] in seen:
                    continue
                seen.add(bm["url"])
                merged.append(bm)

        if not merged:
            self.status_bar.showMessage("✦ No bookmarks found in selected source(s).", 4000)
            return

        added = 0
        for bm in merged:
            if bm["url"] in self._bookmark_urls:
                continue
            self._bookmarks.append(bm)
            self._bookmark_urls.add(bm["url"])
            added += 1

        if added:
            _save_bookmarks(self._bookmarks)
            _invalidate_newtab_cache()
            self._refresh_bookmark_btn()
            mode = self.fernway.get("toolbar_mode", "address")
            if mode == "address" and self._toolbar_stack.currentIndex() == 1:
                self._update_inline_bookmarks()
            elif mode in ("hover", "always"):
                self._update_bookmarks_bar()
            tab = self._current_tab()
            if tab:
                tab._last_html = None
                tab.navigate(NORTHSTAR_HOME, self._bookmarks, dark_mode=self._dark_mode)

        skipped = len(merged) - added
        if len(chosen) == 1:
            src_name = chosen[0][0]
        else:
            src_name = f"{len(chosen)} browsers"
        if added and skipped:
            self.status_bar.showMessage(
                f"✦ Imported {added} from {src_name} ({skipped} duplicate{'s' if skipped != 1 else ''} skipped).",
                4000,
            )
        elif added:
            self.status_bar.showMessage(
                f"✦ Imported {added} from {src_name}.", 4000,
            )
        else:
            self.status_bar.showMessage(f"✦ All {src_name} bookmarks already imported.", 4000)

    def _prompt_bookmark_source(self, sources: list) -> list:
        """Show a small menu-style picker. Returns a list of (name, [bms])
        tuples the user selected, or [] if cancelled.
        """
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        if not sources:
            act_none = menu.addAction("No supported browsers detected.")
            act_none.setEnabled(False)
        else:
            menu.addSection("Import from")
            for name, bms in sources:
                act = menu.addAction(f"{name}   ({len(bms)} bookmark{'s' if len(bms) != 1 else ''})")
                act.setData(("browser", name, bms))
            menu.addSeparator()
            act_all = menu.addAction(f"All detected   ({sum(len(b) for _, b in sources)} total)")
            act_all.setData(("all", None, None))

        menu.addSeparator()
        act_file = menu.addAction("Import from HTML file…")
        act_file.setData(("file", None, None))
        menu.addAction("Cancel")

        chosen = menu.exec(QCursor.pos())
        self._repaint_under_popup()
        if chosen is None or not chosen.isEnabled():
            return []
        payload = chosen.data()
        if not payload:
            return []
        kind = payload[0]
        if kind == "browser":
            return [(payload[1], payload[2])]
        if kind == "all":
            return list(sources)
        if kind == "file":
            parsed = self._import_bookmarks_from_file()
            return [("file", parsed)] if parsed else []
        return []

    def _import_bookmarks_from_file(self) -> list:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Bookmarks from File",
            "",
            "Bookmarks HTML (*.html *.htm);;All Files (*)",
        )
        if not path:
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                html_text = f.read()
        except Exception as e:
            self.status_bar.showMessage(f"✦ Import failed: {e}", 4000)
            return []
        return _parse_netscape_bookmarks(html_text)

    def _is_bookmarked(self):
        tab = self._current_tab()
        return tab.view.url().toString() in self._bookmark_urls if tab else False

    def _refresh_bookmark_btn(self):
        bm = self._is_bookmarked(); self._bm_btn.setText("✦" if bm else "☆")
        self._bm_btn.setToolTip("Remove bookmark (Ctrl+D)" if bm else "Bookmark this page (Ctrl+D)")

    def _toggle_bookmark(self):
        tab = self._current_tab()
        if not tab: return
        if self._is_bookmarked(): self._remove_bookmark(tab.view.url().toString())
        else: self._bookmark_current()

    def _toggle_pip(self):
        """Toggle Picture-in-Picture for the current tab's video."""
        tab = self._current_tab()
        if not tab: return

        if self._pip_window is not None:
            try:
                if self._pip_window.isVisible():
                    self._pip_window.close()
                    self._pip_window = None
                    return
            except RuntimeError:
                self._pip_window = None

        js = """
        (async function() {
            try {
                if (document.pictureInPictureElement) {
                    await document.exitPictureInPicture();
                    return 'closed';
                }
                const videos = Array.from(document.querySelectorAll('video'));
                const video = videos.find(v => !v.paused && v.readyState >= 2)
                    || videos.find(v => v.readyState >= 2 && v.videoWidth && v.videoHeight)
                    || videos[0];
                if (!video || !document.pictureInPictureEnabled
                    || typeof video.requestPictureInPicture !== 'function') {
                    return video ? (video.currentSrc || video.src || '') : '';
                }
                await video.requestPictureInPicture();
                return 'opened';
            } catch (error) {
                const video = document.querySelector('video');
                return video ? (video.currentSrc || video.src || '') : '';
            }
        })();
        """
        tab.view.page().runJavaScript(
            js,
            lambda result: self._on_pip_request_result(result, tab),
        )

    def _on_pip_request_result(self, result, tab):
        if result in ("opened", "closed"):
            return
        if not tab or not hasattr(tab, "view") or tab.view is None:
            return
        self._open_pip(result or "", tab)
    
    def _open_pip(self, video_url, tab):
        """Open PiP window with the extracted video URL."""
        page_url = tab.view.url().toString()
        
        # Try to get a playable URL
        embed_url = self._get_embed_url(video_url, page_url)
        
        if embed_url:
            # Pass None as parent to make the PiP window a top-level window.
            # This decouples it from the main window's resize/move events.
            self._pip_window = PiPWindow(None, profile=self.profile)
            pip_window = self._pip_window
            pip_window.destroyed.connect(
                lambda *_: self._clear_pip_window_reference(pip_window)
            )
            self._pip_window.setWindowTitle("PiP — " + (tab.view.title() or "Video"))
            self._pip_window.load_video(embed_url)
            geo = self.geometry()
            self._pip_window.move(geo.right() - 340, geo.bottom() - 220)
            self._pip_window.show()
        else:
            self.status_bar.showMessage(
                "No playable video was found on this page.", 4000
            )

    def _clear_pip_window_reference(self, window):
        if self._pip_window is window:
            self._pip_window = None

    
    def _get_embed_url(self, video_url, page_url):
        """Convert video URL to a playable embed URL if possible."""
        import re

        vu = (video_url or "").strip()
        pu = (page_url or "").strip()

        # If it's already a direct mp4/webm/etc URL (real http(s), not a blob:),
        # use it directly.  MSE players (YouTube, many sites) expose a `blob:`
        # src on the <video> element, which is NOT directly playable.
        if vu and vu.startswith("http") and not vu.startswith("blob:") and any(
            ext in vu.lower() for ext in ['.mp4', '.webm', '.m3u8', '.mpd']
        ):
            return vu

        # YouTube / Vimeo: detect from BOTH the video element src and the page
        # URL, so a blob: video src no longer shadows the real page URL.
        yt_match = re.search(
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            vu + " " + pu,
        )
        if yt_match:
            # youtube-nocookie.com + a matching `origin` param is the combo
            # that satisfies YouTube's late-2025 Referer/Origin embed check
            # (otherwise the iframe fails with Error 152 / "video not available").
            return (f"https://www.youtube-nocookie.com/embed/{yt_match.group(1)}"
                    f"?autoplay=1&origin=https://www.youtube-nocookie.com")

        vimeo_match = re.search(r'vimeo\.com/(\d+)', vu + " " + pu)
        if vimeo_match:
            return f"https://player.vimeo.com/video/{vimeo_match.group(1)}?autoplay=1"

        # Any other directly-playable http(s) (non-blob) URL.
        if vu and vu.startswith("http") and not vu.startswith("blob:"):
            return vu

        return None
    
    def _open_pip_fallback(self, tab):
        """Fallback: capture the current page screenshot in PiP window."""
        # Pass None as parent to make the PiP window a top-level window.
        # This decouples it from the main window's resize/move events.
        self._pip_window = PiPWindow(None, profile=self.profile)
        pip_window = self._pip_window
        pip_window.destroyed.connect(
            lambda *_: self._clear_pip_window_reference(pip_window)
        )
        self._pip_window.setWindowTitle("PiP — " + (tab.view.title() or "Page"))
        # Get the current page's URL for proper base
        page_url = tab.view.url().toString()
        
        # Take a screenshot of the page instead of loading HTML
        import base64
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QBuffer, QByteArray
        pix = tab.view.grab()
        img = pix.toImage()

        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        b64 = base64.b64encode(buf.data().data()).decode()
        buf.close()
        
        scaled_html = f"""<!DOCTYPE html>
<html><head><style>
body{{margin:0;padding:0;background:#000;overflow:hidden;display:flex;align-items:center;justify-content:center;height:100vh;}}
img{{max-width:100%;max-height:100%;object-fit:contain;}}
</style></head><body>
<img src="data:image/png;base64,{b64}">
</body></html>"""
        self._pip_window.load_html(scaled_html, page_url)
        self._pip_window.show()

    # ── PANEL TOGGLES ────────────────────────
    def _toggle_ai(self):
        # The AI panel is a splitter child, not a floating overlay, so
        # _ns_panel_show/_ns_panel_hide (which animate `pos`) fight the
        # splitter's layout and leave the panel blank.  We use a fade-only
        # animation here and let the splitter handle positioning.
        if self.ai_panel.isVisible():
            self._ai_panel_last_width = self.splitter.sizes()[1]
            total = sum(self.splitter.sizes())
            eff = _ns_opacity(self.ai_panel)
            m = _get_motion_params()
            fade_out = QPropertyAnimation(eff, b"opacity", self.ai_panel)
            fade_out.setDuration(m["out_ms"])
            fade_out.setStartValue(eff.opacity())
            fade_out.setEndValue(0.0)
            fade_out.setEasingCurve(QEasingCurve.Type.InOutCubic)
            def _on_hidden():
                self.ai_panel.hide()
                self.splitter.setSizes([total, 0])
            fade_out.finished.connect(_on_hidden)
            fade_out.start()
            self.ai_panel._ns_exit_anim = fade_out
        else:
            total = sum(self.splitter.sizes())
            restore = max(getattr(self, '_ai_panel_last_width', 340), 300)
            eff = _ns_opacity(self.ai_panel)
            eff.setOpacity(0.0)
            self.ai_panel.show()
            self.splitter.setSizes([total - restore, restore])
            m = _get_motion_params()
            fade_in = QPropertyAnimation(eff, b"opacity", self.ai_panel)
            fade_in.setDuration(m["fade_ms"])
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.InOutCubic)
            fade_in.finished.connect(lambda: (eff.setOpacity(1.0), self.ai_panel.update()))
            fade_in.start()
            self.ai_panel._ns_enter_anim = fade_in

    # OPT: panel positioning uses single setGeometry() call
    def _geometry_for(self, parent, w, h, right_offset=8):
        """Return (x,y,w,h) for a panel pinned top-right of parent, accounting for sidebar width."""
        ph = parent.height()
        # Account for the sidebar's current width
        sidebar_width = self.sidebar.minimumWidth() if self.sidebar.minimumWidth() > 0 else 0
        x = parent.width() - w - right_offset
        y = 45 + 3 + 4   # toolbar + progress + gap
        h = min(h, ph - 60)
        return x, y, w, h

    def _toggle_downloads(self, force_show=False):
        if force_show or not self.downloads_panel.isVisible():
            self._pin_panel(self.downloads_panel, 360, 480)
            _ns_panel_show(self.downloads_panel, raise_fn=self.downloads_panel.raise_)
            self._dim.panel_opened()
        else:
            _ns_panel_hide(self.downloads_panel, on_hidden=self._dim.panel_closed)

    def _toggle_notes(self, force_show=False):
        if force_show or not self.notes_panel.isVisible():
            self._pin_panel(self.notes_panel, 360, 480)
            _ns_panel_show(self.notes_panel, raise_fn=self.notes_panel.raise_)
            self._dim.panel_opened()
        else:
            _ns_panel_hide(self.notes_panel, on_hidden=self._dim.panel_closed)

    def _pin_panel(self, panel, w, h, extra_right=0):
        parent = panel.parent()
        if not parent: return
        x, y, w, h = self._geometry_for(parent, w, h, right_offset=8+extra_right)
        panel.setGeometry(x, y, w, h)   # OPT: one call vs. setFixedWidth+setFixedHeight+move

    def _toggle_password_book(self, force_show=False):
        if force_show or not self.password_book.isVisible():
            offset = 376 if self.downloads_panel.isVisible() else 8
            parent = self.password_book.parent()
            if parent:
                x, y, w, h = self._geometry_for(parent, 380, 520, right_offset=offset)
                self.password_book.setGeometry(x, y, w, h)
            _ns_panel_show(self.password_book, raise_fn=self.password_book.raise_)
            self._dim.panel_opened()
            if not self.password_book.is_unlocked(): self.password_book.try_unlock(self)
        else:
            _ns_panel_hide(self.password_book, on_hidden=self._dim.panel_closed)

    def _do_autofill(self, username, password):
        tab = self._current_tab()
        if not tab: return
        u = username.replace("\\","\\\\").replace('"','\\"')
        p = password.replace("\\","\\\\").replace('"','\\"')
        js = f"""(function(){{
            function fill(type,value){{
                var inputs=document.querySelectorAll('input[type="'+type+'"],input[type="text"],input[type="email"]');
                for(var i=0;i<inputs.length;i++){{
                    var el=inputs[i];
                    if(type==='password'&&el.type!=='password')continue;
                    var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                    setter.call(el,value);
                    el.dispatchEvent(new Event('input',{{bubbles:true}}));
                    el.dispatchEvent(new Event('change',{{bubbles:true}}));
                    break;
                }}
            }}
            fill('email',"{u}");fill('password',"{p}");
        }})();"""
        tab.view.page().runJavaScript(js)
        self.status_bar.showMessage("⬇ Auto-filled login form.", 3000)

    def _toggle_history(self, force_show=False):
        if force_show or not self.history_panel.isVisible():
            parent = self.history_panel.parent()
            if parent:
                right = 8 + sum(p.width()+8 for p in (self.downloads_panel, self.password_book, self.settings_panel) if p.isVisible())
                x, y, w, h = self._geometry_for(parent, 400, 560, right_offset=right)
                self.history_panel.setGeometry(x, y, w, h)
            _ns_panel_show(self.history_panel, raise_fn=self.history_panel.raise_)
            self._dim.panel_opened()
            self.history_panel._render()
        else:
            _ns_panel_hide(self.history_panel, on_hidden=self._dim.panel_closed)

    def _toggle_starshare(self, force_show=False):
        if force_show or not self.starshare_panel.isVisible():
            parent = self.starshare_panel.parent()
            if parent:
                right = 8 + sum(p.width()+8 for p in (self.downloads_panel,self.password_book,self.history_panel,self.settings_panel) if p.isVisible())
                x, y, w, h = self._geometry_for(parent, 380, 500, right_offset=right)
                self.starshare_panel.setGeometry(x, y, w, h)
            _ns_panel_show(self.starshare_panel, raise_fn=self.starshare_panel.raise_)
            self._dim.panel_opened()
            # FIX: guard against double-start — bail out if beacon already running
            if self._ss_beacon and self._ss_beacon.isRunning():
                return
            self._ss_beacon = StarShareBeacon(self)
            self._ss_beacon.peer_found.connect(self._on_ss_peer_found)
            self._ss_beacon.peer_left.connect(self.starshare_panel._remove_device)
            self._ss_beacon.start()
        else:
            # FIX: always stop and discard the beacon when the panel closes
            # (beacon is a background thread — stop it immediately, before the
            #  animated hide begins, so no orphaned discovery traffic lingers)
            if self._ss_beacon:
                self._ss_beacon.stop()
                self._ss_beacon = None
            _ns_panel_hide(self.starshare_panel, on_hidden=self._dim.panel_closed)

    def _on_ss_peer_found(self, peer_id, name, ip):
        self.starshare_panel.on_peer_found(peer_id, name, ip)

    def _on_ss_incoming(self, sender, filename, fsize, conn_id):
        toast = StarShareToast(sender, filename, fsize, conn_id, self)
        toast.accepted.connect(lambda cid, path: self._ss_server.accept_transfer(cid, path))
        toast.declined.connect(self._ss_server.decline_transfer)
        toast.show()
        QTimer.singleShot(0, toast._repin)   # repin after show() so size is known

    def closeEvent(self, event):
        if self._app and hasattr(self, "_panel_dismiss_filter"):
            self._app.removeEventFilter(self._panel_dismiss_filter)
        # FIX: beacon may be None if StarShare panel was never opened
        if self._ss_beacon:
            self._ss_beacon.stop()
            self._ss_beacon = None
        self._ss_server.stop()
        self._favicon_executor.shutdown(wait=False, cancel_futures=True)
        if self._settings.get("restore_tabs", False):
            open_tabs = []
            for index in range(self.tabs.count()):
                tab = self.tabs.widget(index)
                if not tab:
                    continue
                url = tab.view.url().toString()
                scheme = urlparse(url).scheme.lower()
                if url == NORTHSTAR_HOME or scheme in ("http", "https", "file", "ftp"):
                    open_tabs.append(url)
            _save_session_tabs(open_tabs)
        else:
            _clear_saved_session()
        # Stop enrichment workers (only if they were started)
        if self._enrichment is not None:
            self._enrichment.stop()
        if hasattr(self,'history_panel'): self.history_panel._flush()
        super().closeEvent(event)

    def _toggle_fernway(self, force_show=False):
        if self.fernway_panel.isVisible() and not force_show:
            _ns_panel_hide(self.fernway_panel, on_hidden=self._dim.panel_closed)
        else:
            self._pin_panel(self.fernway_panel, 360, 520)
            self._dim.panel_opened()
            _ns_panel_show(self.fernway_panel, raise_fn=self.fernway_panel.raise_)
            # Hide other panels
            for p in (self.settings_panel, self.downloads_panel, self.notes_panel,
                      self.password_book, self.history_panel, self.starshare_panel):
                if p.isVisible(): _ns_panel_hide(p, on_hidden=self._dim.panel_closed)

    def _open_settings(self):
        """Navigate to the settings page."""
        tab = self._current_tab()
        if tab:
            tab.navigate("northstar://settings", dark_mode=self._dark_mode)

    def _clear_browser_data(self, data_type):
        descriptions = {
            "cache": ("Clear cached files",
                      "Remove cached images and files? This may make websites load more slowly next time."),
            "cookies": ("Clear website cookies",
                        "Remove all website cookies? This will sign you out of many websites."),
            "history": ("Clear browsing history",
                        "Remove all browsing history stored by NorthStar?"),
        }
        title, prompt = descriptions.get(data_type, (None, None))
        if not title:
            return
        answer = QMessageBox.question(
            self, title, prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if data_type == "cache":
            self.profile.clearHttpCache()
        elif data_type == "cookies":
            self.profile.cookieStore().deleteAllCookies()
        elif data_type == "history":
            self.history_panel._clear_all()
        self.status_bar.showMessage(f"{title} requested.", 3000)

    def _open_extensions_page(self):
        """Navigate to the extensions management page."""
        tab = self._current_tab()
        if tab:
            tab.navigate("northstar://extensions", dark_mode=self._dark_mode)

    def _show_extensions_menu(self):
        """Extensions dropdown: manage, load unpacked, or browse the store."""
        menu = QMenu(self)
        menu.addAction("Manage Extensions", self._open_extensions_page)
        menu.addAction("Load Unpacked…",      self._install_extension)
        if getattr(self.extensions.backend, "name", "") == "native":
            menu.addAction("Install .crx / .zip…", self._install_crx_extension)
        menu.addSeparator()
        menu.addAction("Browse Edge Add-ons", self._browse_edge_addons)
        menu.exec(self._ext_btn.mapToGlobal(QPoint(0, self._ext_btn.height())))
        self._repaint_under_popup()

    def _on_extensions_action(self, action, ext_id, value):
        """Handle enable/remove routed from the northstar://extensions page
        (queued to the GUI thread — the native backend's QWebEngineExtensionManager
        must only be called on the owning thread)."""
        try:
            if action == "enable":
                self.extensions.set_enabled(ext_id, bool(value))
            elif action == "remove":
                self.extensions.remove(ext_id)
        except Exception as e:
            self.statusBar().showMessage(f"Extension action failed: {e}", 5000)

    def _on_extensions_changed(self):
        """Refresh after an async native install/load/uninstall resolves."""
        err = self.extensions.take_last_error()
        if err:
            self.statusBar().showMessage(f"Extension: {err}", 6000)
        tab = self._current_tab()
        if tab and tab.view.url().toString().startswith("northstar://extensions"):
            tab.navigate("northstar://extensions", dark_mode=self._dark_mode)

    def _browse_edge_addons(self):
        """Open the official Edge Add-ons storefront in the current tab."""
        tab = self._current_tab()
        if tab:
            tab.navigate(EDGE_ADDONS_URL, dark_mode=self._dark_mode)
        self.statusBar().showMessage("Browsing Edge Add-ons…", 3000)

    def _install_extension(self):
        """Pick an unpacked extension folder and install it on the GUI thread."""
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self, "Select extension folder (containing manifest.json)"
        )
        if not folder:
            return
        try:
            meta = self.extensions.install_from_dir(folder)
        except Exception as e:
            self.statusBar().showMessage(f"Extension install failed: {e}", 5000)
            return
        if meta:
            if meta.get("pending"):
                # Native MV3 install is async — installFinished → changed →
                # _on_extensions_changed refreshes the page when it lands.
                self.statusBar().showMessage(
                    f"Installing {meta.get('name','?')} (MV3)…", 3000
                )
                return
            self.statusBar().showMessage(
                f"Installed extension: {meta.get('name','?')} v{meta.get('version','?')}", 5000
            )
            if self._current_tab():
                self._current_tab().navigate("northstar://extensions", dark_mode=self._dark_mode)

    def _install_crx_extension(self):
        """Install a packed .crx / .zip (native MV3 backend only)."""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Select extension file (.crx / .zip)", "",
            "Chrome Extensions (*.crx *.zip);;All files (*.*)"
        )
        if not path:
            return
        try:
            meta = self.extensions.install_from_dir(path)
        except Exception as e:
            self.statusBar().showMessage(f"Extension install failed: {e}", 5000)
            return
        if meta and meta.get("pending"):
            self.statusBar().showMessage(
                f"Installing {meta.get('name','?')} (MV3)…", 3000
            )

    def _toggle_settings(self, force_show=False):
        if force_show or not self.settings_panel.isVisible():
            self._pin_panel(self.settings_panel, 360, 480)
            _ns_panel_show(self.settings_panel, raise_fn=self.settings_panel.raise_)
            self._dim.panel_opened()
        else:
            _ns_panel_hide(self.settings_panel, on_hidden=self._dim.panel_closed)

    def _toggle_find(self):
        if self.find_bar.isVisible(): self.find_bar.close_bar()
        else:
            tab = self._current_tab()
            if tab: self.find_bar.open_bar(tab.view)

    def _on_settings_changed(self, s):
        # Light mode is removed — always stay dark regardless of any saved value.
        s = dict(s); s["dark_mode"] = True
        self._dark_mode = True
        selected_engine = s.get("search_engine", "Google")
        if selected_engine not in SEARCH_ENGINES:
            selected_engine = "Google"
        s["search_engine"] = selected_engine
        search_engine_changed = selected_engine != self._settings.get("search_engine")
        if search_engine_changed:
            _invalidate_newtab_cache()
        if s.get("launch_at_startup") != self._settings.get("launch_at_startup"):
            _set_startup_registry(s.get("launch_at_startup", False))
        if not s.get("restore_tabs", False):
            _clear_saved_session()
        self._settings = s
        self.settings_panel.update_settings(s)
        if search_engine_changed:
            self._refresh_newtab_pages()
        else:
            QTimer.singleShot(0, self._reload_current_page)

    # ── COMMAND PALETTE ──────────────────────
    def _show_palette(self):
        palette = CommandPalette(
            self, self._settings.get("recent_commands", [])
        )
        palette.command_selected.connect(self._run_command)
        palette.show_centered(self)

    def _run_command(self, name):
        actions = {
            "New Tab":           lambda: self._new_tab(),
            "Close Tab":         self._close_current_tab,
            "Reload Page":       self._reload,
            "Hard Reload":       self._hard_reload,
            "Focus Address Bar": self._focus_address,
            "Go Back":           self._go_back,
            "Go Forward":        self._go_forward,
            "Toggle AI Panel":      self._toggle_ai,
            "Toggle Downloads":     self._toggle_downloads,
            "Toggle Password Book": self._toggle_password_book,
            "Open History":         self._toggle_history,
            "StarShare":            self._toggle_starshare,
            "Find in Page":         self._toggle_find,
            "Settings":             self._open_settings,
            "Zoom In":           self._zoom_in,
            "Zoom Out":          self._zoom_out,
            "Reset Zoom":        self._zoom_reset,
            "Bookmark Page":     self._toggle_bookmark,
            "Fullscreen":        self._toggle_fullscreen,
        }
        fn = actions.get(name)
        if fn:
            recent = self._settings.get("recent_commands", [])
            self._settings["recent_commands"] = [name] + [
                command for command in recent if command != name
            ]
            self._settings["recent_commands"] = self._settings["recent_commands"][:5]
            _save_settings(self._settings)
            fn()

    # ── STYLESHEET — SPLIT BASE+PATCH ────────
    def _sync_oled_palette(self, oled=False):
        """True-black QPalette in OLED Mode; restore the system palette after."""
        app = QApplication.instance()
        if not app:
            return
        if not hasattr(self, "_system_palette") or self._system_palette is None:
            self._system_palette = QPalette(app.palette())
        if not hasattr(self, "_oled_palette") or self._oled_palette is None:
            self._oled_palette = QPalette()
            self._oled_palette.setColor(QPalette.ColorRole.Window,    QColor("#000000"))
            self._oled_palette.setColor(QPalette.ColorRole.Base,      QColor("#000000"))
            self._oled_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#0a0a0a"))
            self._oled_palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8edf8"))
            self._oled_palette.setColor(QPalette.ColorRole.Text,      QColor("#e8edf8"))
            self._oled_palette.setColor(QPalette.ColorRole.Button,    QColor("#0a0a0a"))
            self._oled_palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8edf8"))
            self._oled_palette.setColor(QPalette.ColorRole.Highlight, QColor("#d4af37"))
            self._oled_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
            self._oled_palette.setColor(QPalette.ColorRole.ToolTipBase,    QColor("#121212"))
            self._oled_palette.setColor(QPalette.ColorRole.ToolTipText,    QColor("#e8edf8"))
            self._oled_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(200, 210, 240, 140))
            self._oled_palette.setColor(QPalette.ColorRole.Link,      QColor("#e8cd77"))
        app.setPalette(self._oled_palette if oled else self._system_palette)

    def _apply_style(self, reload=True):
        # OPT: only the 200-char patch changes between light/dark;
        # the 1500-char base is constant and stored in _BASE_QSS.
        dark = self._dark_mode
        self._sync_oled_palette(oled_enabled())
        full_qss = _base_qss() + _theme_patch(dark, oled=oled_enabled())
        if self.styleSheet() != full_qss:
            self.setStyleSheet(full_qss)
        app = QApplication.instance()
        if app:
            app.setFont(QFont(self.fernway.get("browser_font", "Segoe UI"), 10))
            
        # Update autohide delay
        self._sidebar_timer.setInterval(int(self.fernway.get("autohide_delay_ms", 400)))
        
        # Update toolbar mode
        self._apply_toolbar_mode()
        
        # Refresh tab label visibility for compact/glass styles
        self._refresh_tab_label_visibility()
            
        # Ensure sidebar visibility/auto-hide state
        is_floating = self.fernway.get("sidebar_style") == "floating"
        auto_hide = self.fernway.get("sidebar_auto_hide", True)
        
        if is_floating or auto_hide:
            # Starts hidden and uses polling unhide
            self.sidebar.show()
            self.sidebar.setMinimumWidth(0)
            self.sidebar.setMaximumWidth(0)
            if hasattr(self, "_edge_timer"): self._edge_timer.start()
        else:
            target_w = self._sidebar_target_width()
            self.sidebar.setMinimumWidth(target_w)
            self.sidebar.setMaximumWidth(target_w)
            self.sidebar.show()
            if hasattr(self, "_edge_timer"): self._edge_timer.stop()

        self._apply_web_theme(reload=reload)
        if reload:
            self._reload_current_page()

    def _reload_current_page(self):
        tab = self._current_tab()
        if (tab and tab.view.url().toString()
                and not tab.view.url().toString().startswith("northstar://settings")):
            tab.view.reload()

    def _should_reload_after_setting_change(self):
        tab = self._current_tab()
        return bool(
            tab and not tab.view.url().toString().startswith("northstar://settings")
        )

    def _apply_web_theme(self, reload=True):
        oled = oled_enabled()
        bg_color = QColor("#000000") if oled else (QColor("#06070d") if self._dark_mode else QColor("#ffffff"))
        scheme   = "dark" if (oled or self._dark_mode) else "light"

        # OPT: only update page background if changed
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab and tab.view.page().backgroundColor() != bg_color:
                tab.view.page().setBackgroundColor(bg_color)

        script_src = f"""
(function(){{
  if(!document.documentElement)return;
  document.documentElement.style.colorScheme='{scheme}';
  var m=document.querySelector('meta[name="color-scheme"]');
  if(!m){{
    m=document.createElement('meta');m.name='color-scheme';
    if(document.head){{document.head.appendChild(m);}}
    else{{document.addEventListener('DOMContentLoaded',function(){{if(document.head)document.head.appendChild(m);}});}}
  }}
  m.content='{scheme}';
}})();
"""
        script = QWebEngineScript(); script.setName("northstar_theme")
        script.setSourceCode(script_src)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        scripts = self.profile.scripts()
        for s in scripts.toList():
            if s.name() == "northstar_theme": scripts.remove(s); break
        scripts.insert(script)

    def _install_clipboard_shim(self):
        """Inject the page-side clipboard shim + QWebChannel transport.

        The shim overrides navigator.clipboard.writeText / write so copy buttons
        on sites like ChatGPT land in the REAL host clipboard via
        window.northstar.copy() (a QWebChannel bridge).  This path is immune to
        Chromium's clipboard-permission model, user-gesture requirements, AND the
        page's Content-Security-Policy — the three things that make copy buttons
        silently fail under QtWebEngine.  execCommand and the async API remain as
        fallbacks.  [nsclip] console traces make failures diagnosable.
        """
        scripts = self.profile.scripts()

        # 1) The official qwebchannel.js (decoded from the embedded base64).
        try:
            import base64 as _b64
            _qc_js = _b64.b64decode(QWEBCHANNEL_JS_B64).decode("utf-8")
        except Exception:
            _qc_js = ""
        if _qc_js:
            for s in scripts.toList():
                if s.name() == "qwebchannel_js": scripts.remove(s); break
            _sc = QWebEngineScript()
            _sc.setName("qwebchannel_js")
            _sc.setSourceCode(_qc_js)
            _sc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            _sc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            _sc.setRunsOnSubFrames(False)
            scripts.insert(_sc)

        # 2) Init script: once the page's webchannel transport is ready, expose
        #    our registered bridge object as window.northstar.
        _init_src = """
(function() {
  if (window.__nsWCInit) return;
  window.__nsWCInit = true;
  function init() {
    if (typeof qt !== 'undefined' && qt.webChannelTransport) {
      new QWebChannel(qt.webChannelTransport, function(channel) {
        window.northstar = channel.objects.northstar;
      });
    } else {
      setTimeout(init, 60);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else { init(); }
})();
"""
        for s in scripts.toList():
            if s.name() == "qwebchannel_init": scripts.remove(s); break
        _sc = QWebEngineScript()
        _sc.setName("qwebchannel_init")
        _sc.setSourceCode(_init_src)
        _sc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        _sc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        _sc.setRunsOnSubFrames(False)
        scripts.insert(_sc)

        # 3) The clipboard shim itself.
        shim_src = """
(function() {
  if (window.__nsClipboardShim) return;
  window.__nsClipboardShim = true;
  function log(m){ try { console.log('[nsclip] ' + m); } catch(e){} }

  var NC = navigator.clipboard;
  log('install hasClip=' + !!NC +
      ' writeText=' + !!(NC && NC.writeText) +
      ' write=' + !!(NC && NC.write) +
      ' ClipboardItem=' + !!(window.ClipboardItem));

  function legacyWrite(text) {
    try {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-1000px';
      ta.style.left = '-1000px';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try { ta.setSelectionRange(0, ta.value.length); } catch (e) {}
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      return ok;
    } catch (e) { return false; }
  }

  // PRIMARY: host-side Qt clipboard via the QWebChannel bridge
  // (window.northstar.copy).  CSP/gesture/permission-proof.
  function hostCopy(text) {
    try {
      if (window.northstar && window.northstar.copy) {
        window.northstar.copy(text);
        return true;
      }
    } catch (e) {}
    // Fallback: northstar:// scheme (may be blocked by page CSP).
    try {
      var enc = encodeURIComponent(text);
      if (enc.length > 1500000) return false;
      try { fetch('northstar://clipboard?text=' + enc, {method:'GET', mode:'no-cors'}).catch(function(){}); } catch(e) {}
      var img = new Image();
      img.src = 'northstar://clipboard?text=' + enc;
      return true;
    } catch (e) { return false; }
  }

  var origWrite = NC && NC.writeText ? NC.writeText.bind(NC) : null;
  var origWriteItems = NC && NC.write ? NC.write.bind(NC) : null;

  if (!NC) {
    NC = {
      writeText: function(t) { return legacyWrite(String(t)) ? Promise.resolve(undefined) : Promise.reject(new Error('copy failed')); },
      write:     function(items) { return Promise.reject(new Error('write not supported')); },
      readText:  function() { return Promise.reject(new Error('read not supported')); }
    };
    try { Object.defineProperty(navigator, 'clipboard', { configurable: true, value: NC }); } catch (e) {}
  }

  function doWrite(text) {
    var s = String(text == null ? '' : text);
    if (hostCopy(s)) { log('writeText: host(webchannel) OK'); return Promise.resolve(undefined); }
    if (legacyWrite(s)) { log('writeText: execCommand OK'); return Promise.resolve(undefined); }
    try {
      return (origWrite ? origWrite(s) : Promise.reject(new Error('no writeText')))
        .catch(function() { return undefined; });
    } catch (e) {
      return Promise.resolve(undefined);
    }
  }

  try {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, get: function() { return NC; } });
  } catch (e) {}

  NC.writeText = doWrite;

  if (origWriteItems) {
    NC.write = function(items) {
      return new Promise(function(resolve, reject) {
        function fallback() {
          try { origWriteItems(items).then(resolve, reject); }
          catch (err) { reject(err); }
        }
        try {
          var item = (items && items[0]) || null;
          if (item && item.types && item.types.length) {
            var plain = (item.types.filter(function(t){ return t === 'text/plain'; })[0]) || item.types[0];
            item.getType(plain).then(function(blob) {
              blob.text().then(function(txt) {
                if (hostCopy(txt)) { log('write(ClipboardItem): host(webchannel) OK'); resolve(undefined); return; }
                if (legacyWrite(txt)) { log('write(ClipboardItem): execCommand OK'); resolve(undefined); return; }
                fallback();
              }).catch(function() { fallback(); });
            }).catch(function() { fallback(); });
            return;
          }
          fallback();
        } catch (e) { fallback(); }
      });
    };
  }
  log('install complete');
})();
"""
        for s in scripts.toList():
            if s.name() == "northstar_clipboard_shim": scripts.remove(s); break
        script = QWebEngineScript()
        script.setName("northstar_clipboard_shim")
        script.setSourceCode(shim_src)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)  # also patch iframe-based editors
        scripts.insert(script)

    def resizeEvent(self, event):
        super().resizeEvent(event); 
        self._resize_timer.start()  # debounced
        # Reposition floating toolbar immediately
        if hasattr(self, '_reposition_toolbar'):
            self._reposition_toolbar()
        # Reposition bookmarks bar overlay on resize
        mode = self.fernway.get("toolbar_mode", "address")
        if mode in ("hover", "always"):
            pw = self._content_col.width() if self._content_col.width() > 0 else self.width()
            self._position_bookmarks_bar(pw)
        # For floating sidebar: update height, but AFTER webview has finished rendering!
        if self.fernway.get("sidebar_style") == "floating":
            def update_height_after_render():
                current_w = self.sidebar.minimumWidth()
                self.sidebar.setGeometry(0, 0, current_w, self.height())
            QTimer.singleShot(50, update_height_after_render)

    def _repin_panels(self):
        """OPT: repin all visible panels in one pass using setGeometry()."""
        # Reposition floating toolbar
        if hasattr(self, '_reposition_toolbar'):
            self._reposition_toolbar()
            self._toolbar_widget.raise_()
        if (self.fernway.get("toolbar_mode") in ("hover", "always")
                and self._bookmarks_bar.width()
                != getattr(self, "_bookmarks_bar_layout_width", -1)):
            self._update_bookmarks_bar()
        # If sidebar is floating, ensure it's raised but do NOT modify geometry
        # during a resize event to prevent interfering with webview rendering!
        if self.fernway.get("sidebar_style") == "floating":
            self.sidebar.raise_()

        # Keep dim overlay covering the full content column (needed after resize)
        p = self._dim.parent()
        if p:
            self._dim.setGeometry(0, 0, p.width(), p.height())
        if self._hover_label.isVisible():
            self._reposition_hover_label()
        if self.downloads_panel.isVisible():
            self._pin_panel(self.downloads_panel, 360, 480)
        if self.notes_panel.isVisible():
            self._pin_panel(self.notes_panel, 360, 480)
        if self.fernway_panel.isVisible():
            self._pin_panel(self.fernway_panel, 360, 520)
        
        # Calculate stacking offsets for multiple panels
        def get_offset(panels):
            return 8 + sum(p.width() + 8 for p in panels if p.isVisible())

        if self.password_book.isVisible():
            parent = self.password_book.parent()
            if parent:
                offset = get_offset([self.downloads_panel, self.fernway_panel])
                x, y, w, h = self._geometry_for(parent, 380, 520, right_offset=offset)
                self.password_book.setGeometry(x, y, w, h)
        if self.history_panel.isVisible():
            parent = self.history_panel.parent()
            if parent:
                offset = get_offset([self.downloads_panel, self.fernway_panel, self.password_book, self.settings_panel])
                x, y, w, h = self._geometry_for(parent, 400, 560, right_offset=offset)
                self.history_panel.setGeometry(x, y, w, h)
        if self.settings_panel.isVisible():
            self._pin_panel(self.settings_panel, 360, 480)
        if self.starshare_panel.isVisible():
            parent = self.starshare_panel.parent()
            if parent:
                offset = get_offset([self.downloads_panel, self.fernway_panel, self.password_book, self.history_panel, self.settings_panel])
                x, y, w, h = self._geometry_for(parent, 380, 500, right_offset=offset)
                self.starshare_panel.setGeometry(x, y, w, h)
        if self.find_bar.isVisible():
            self.find_bar._reposition()

    def _toggle_fullscreen(self):
        if self.isFullScreen(): self._exit_fullscreen()
        else: self._enter_fullscreen()

    def _enter_fullscreen(self):
        self.showFullScreen(); self.sidebar.hide(); self._toolbar_widget.hide()
        self.status_bar.hide()
        self._max_btn.setText("❐")

    def _exit_fullscreen(self):
        self.showNormal(); self.sidebar.show(); self._toolbar_widget.show()
        self.status_bar.show(); self._max_btn.setText("□")

    def _on_escape(self):
        if self.isFullScreen(): self._exit_fullscreen()
        # Restore address bar if escaping from bookmarks mode
        if hasattr(self, "_toolbar_stack") and self._toolbar_stack.currentIndex() == 1:
            self._toggle_toolbar_mode()

    # ── WEB ENGINE PRELOADER ─────────────────
    def _preload_web_engine(self):
        """Spin up a hidden QWebEngineView to warm the Chromium renderer.

        The renderer subprocess (QtWebEngineProcess) is launched lazily on the
        very first QWebEngineView. By doing it here — right after the main
        window is shown — any tabs the user opens immediately afterwards are
        served by an already-running renderer rather than waiting for its cold
        start (~200–500 ms on typical hardware).
        """
        if self._preload_view is not None:
            return
        self._preload_view = QWebEngineView()
        page = QWebEnginePage(self.profile, self._preload_view)
        self._preload_view.setPage(page)
        # Keep it invisible but give it a tiny geometry so the renderer
        # initialises its compositing pipeline fully.
        self._preload_view.setFixedSize(1, 1)
        self._preload_view.show()
        self._preload_view.hide()
        self._preload_view.load(QUrl("about:blank"))
        # Release 3 s later — the renderer is already started by then.
        QTimer.singleShot(3_000, self._release_preload_view)

    def _release_preload_view(self):
        if self._preload_view is not None:
            self._preload_view.deleteLater()
            self._preload_view = None


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
def main():
    _IGNORED = ("web-share","WebEnginePage still not deleted","QFont::setPointSize",
                "SandboxOriginDatabase","quota_database","Failed to reset the quota database",
                "Could not open the quota database")
    def _msg_handler(msg_type, context, message):
        if any(s in message for s in _IGNORED): return
        if _DEBUG: print(message)
    qInstallMessageHandler(_msg_handler)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # OPT: load settings and bookmarks in parallel (both are small JSON reads,
    # but every ms counts during the critical startup path).
    with ThreadPoolExecutor(max_workers=2) as _pool:
        _fut_settings  = _pool.submit(_load_settings)
        _fut_bookmarks = _pool.submit(_load_bookmarks)
        startup_settings  = _fut_settings.result()
        startup_bookmarks = _fut_bookmarks.result()

    # Ensure startup registry matches setting
    _set_startup_registry(startup_settings.get("launch_at_startup", False))

    # Preserve the configured Chromium flags while applying the dark-mode flag.
    # Remove the legacy switch so only the current dark-mode feature controls it.
    _existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    _dark_flag = (
        "--enable-features=WebContentsForceDark:inversion_method/cielab_based_inversion/"
        "image_behavior/none/foreground_inversion_threshold/150/background_inversion_threshold/205"
    )
    if _dark_flag not in _existing_flags:
        _existing_flags = (_existing_flags + " " + _dark_flag).strip()
    _existing_flags = _existing_flags.replace("--force-dark-mode", "").strip()
    if _existing_flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _existing_flags
    else:
        os.environ.pop("QTWEBENGINE_CHROMIUM_FLAGS", None)

    # Leave WebEngine renderer and persistent storage cleanup to Qt/Chromium;
    # other application instances may own similarly named processes or data.
    # ── Start Qt ─────────────────────────────────────────────────────────────
    app = QApplication(sys.argv)

    # Configure defaultProfile BEFORE NorthStar() so Chromium sees the correct
    # paths when it initialises the renderer on the first _new_tab() call.
    profile = QWebEngineProfile.defaultProfile()
    profile.setCachePath(cache_dir)
    profile.setPersistentStoragePath(storage_dir)

    app.setApplicationName("NorthStar"); app.setOrganizationName("NorthStar Browser")
    _icon_path = _asset("northstar.ico")
    if os.path.exists(_icon_path): app.setWindowIcon(QIcon(_icon_path))
    app.setFont(QFont(get_fernway().get("browser_font", "Segoe UI"), 10))
    _t0 = time.perf_counter()
    window = NorthStar(); window.setMinimumSize(800, 500); window.showMaximized()
    _t1 = time.perf_counter()
    if _DEBUG:
        print(f"[startup] NorthStar() constructed + shown in {(_t1 - _t0) * 1000:.0f} ms")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
