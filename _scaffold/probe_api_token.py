# -*- coding: utf-8 -*-
"""probe_api_token.py —— 查清「带 token 访问 /api/health 返回 401」的原因

模拟 smoke_test §17b 的步骤：开局域网（自动生成口令）→ 启动服务 → 带 token 请求。
把服务端实际持有的 token、实际监听端口都打出来对照。
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication          # noqa: E402
import Mahjong_Calculator as M                       # noqa: E402

SETTINGS = os.path.join(HERE, "_probe_settings.json")
LOG = []


def say(*a):
    line = " ".join(str(x) for x in a)
    LOG.append(line)
    print(line)


def main():
    if os.path.exists(SETTINGS):
        os.remove(SETTINGS)
    M.settings_path = lambda: SETTINGS
    M.QMessageBox.information = staticmethod(lambda *a, **k: None)
    M.QMessageBox.warning = staticmethod(lambda *a, **k: None)

    app = QApplication(sys.argv)
    w = M.MahjongFanWindow()
    say("初始: api_port=%s api_lan=%s api_token=%r api_auto_start=%s"
        % (w.api_port, w.api_lan, w.api_token, w.api_auto_start))
    say("初始: api_server=%r" % (w.api_server,))

    w.api_token = ""
    w._api_lan_toggle(True)
    say("开局域网后: api_lan=%s api_token=%r" % (w.api_lan, w.api_token))

    ok = w._api_start(silent=True)
    srv = w.api_server
    say("启动返回=%s running=%s" % (ok, w._api_running()))
    say("窗口侧: api_port=%s api_token=%r" % (w.api_port, w.api_token))
    say("服务侧: host=%s port=%s port_actual=%s token=%r"
        % (getattr(srv, "host", None), getattr(srv, "port", None),
           getattr(srv, "port_actual", None), getattr(srv, "token", None)))

    u_query = ("http://127.0.0.1:%d/api/health?token=%s"
               % (w.api_port, w.api_token))
    u_head = "http://127.0.0.1:%d/api/health" % w.api_port
    for label, url, hdr in (("query 带 token", u_query, {}),
                            ("header 带 token", u_head,
                             {"X-Api-Token": w.api_token}),
                            ("服务侧 token 直连", u_query, {})):
        tok = w.api_token if label != "服务侧 token 直连" else str(srv.token)
        if label == "服务侧 token 直连":
            url = "http://127.0.0.1:%d/api/health?token=%s" % (w.api_port, tok)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr),
                                        timeout=5) as r:
                body = r.read().decode("utf-8", "replace")
            say("%s → HTTP %s %s" % (label, r.status, body[:90]))
        except urllib.error.HTTPError as e:
            say("%s → HTTP %s %s" % (label, e.code,
                                     e.read().decode("utf-8", "replace")[:120]))
        except Exception as exc:            # noqa: BLE001
            say("%s → 异常 %r" % (label, exc))

    # 看看谁在监听了哪些端口（windows: netstat）
    try:
        import subprocess
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                             capture_output=True, text=True, timeout=25).stdout
        hits = [l.strip() for l in out.splitlines()
                if "LISTENING" in l and (":%d" % w.api_port) in l]
        say("netstat LISTENING %d → %s" % (w.api_port, hits or "无"))
    except Exception as exc:                # noqa: BLE001
        say("netstat 跳过: %r" % (exc,))

    w._api_stop(silent=True, remember=False)
    with open(os.path.join(HERE, "_probe_api_token_out.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
