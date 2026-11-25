"""Loopback-only control panel for keeper_plugin."""
import base64
import hashlib
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from threading import Lock, Thread

from keeper_plugin import list_instances, run_sequence
from keeper_schedule import INTERVAL, dpapi, load_config, save_config

HOST = "127.0.0.1"
PORT = 8765
ADDRESS = f"{HOST}:{PORT}"
ORIGIN = f"http://{ADDRESS}"
ASSETS = Path(__file__).with_name("edge_extension")
PUBLIC_KEY = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))["key"]
KEY_HASH = hashlib.sha256(base64.b64decode(PUBLIC_KEY)).hexdigest()[:32]
EXTENSION_ORIGIN = "chrome-extension://" + KEY_HASH.translate(
    str.maketrans("0123456789abcdef", "abcdefghijklmnop")
)
LOCK = Lock()
JOB = {"state": "idle", "events": []}
URGENT_WINDOW = 3 * 86400
HEALTH_CHECK_INTERVAL = 15 * 60
URGENT_RETRY_INTERVAL = 60 * 60


def run_job(token, uuids, automatic=False, urgent=None):
    def report(message):
        with LOCK:
            JOB["events"].append(message)

    state = "done"
    try:
        if automatic:
            token = dpapi(token, decrypt=True)
            if urgent is None:
                instances = list_instances(token)
                uuids = [item["uuid"] for item in instances if item["status"] == "shutdown"]
                report(f"八天自动保活 · {len(uuids)} 台待处理")
            else:
                uuids = list(urgent)
                report(f"释放时间不足三天 · 提前保活 {len(uuids)} 台")
        if uuids:
            run_sequence(token, uuids, report)
        if urgent is not None:
            refreshed = {item["uuid"]: item for item in list_instances(token)}
            for uuid, previous in urgent.items():
                release_at = refreshed.get(uuid, {}).get("release_at")
                if release_at and release_at > previous and release_at > time.time() + URGENT_WINDOW:
                    report(f"{uuid} · 已确认释放时间延后")
                else:
                    state = "failed"
                    report(f"{uuid} · 未确认释放时间延后，将在一小时后重试")
    except RuntimeError as exc:
        report(str(exc))
        state = "failed"
    except Exception:
        report("AutoDL 请求失败，请检查令牌、网络和实例状态。")
        state = "failed"
    finally:
        with LOCK:
            JOB["state"] = state
            JOB["completed_at"] = time.time()
            if automatic:
                config = load_config()
                config["last_state"] = state
                config["last_events"] = JOB["events"][:]
                save_config(config)


def find_urgent(instances, now):
    return {
        item["uuid"]: item["release_at"]
        for item in instances
        if item["status"] == "shutdown"
        and item.get("release_at") is not None
        and item["release_at"] <= now + URGENT_WINDOW
    }


def scheduler():
    next_check = 0
    while True:
        try:
            encrypted = None
            with LOCK:
                config = load_config()
                now = time.time()
                if config.get("token") and config.get("local_auto", True) and JOB["state"] != "running":
                    if config["next_at"] <= now:
                        config["next_at"] += (int((now - config["next_at"]) // INTERVAL) + 1) * INTERVAL
                        save_config(config)
                        JOB.update(state="running", events=[], automatic=True)
                        Thread(target=run_job, args=(config["token"], None, True), daemon=False).start()
                    elif now >= max(next_check, config.get("urgent_retry_at", 0)):
                        next_check = now + HEALTH_CHECK_INTERVAL
                        encrypted = config["token"]
            if encrypted:
                urgent = find_urgent(list_instances(dpapi(encrypted, decrypt=True)), time.time())
                if urgent:
                    with LOCK:
                        config = load_config()
                        if (config.get("token") == encrypted and config.get("local_auto", True)
                                and JOB["state"] != "running"):
                            config["urgent_retry_at"] = time.time() + URGENT_RETRY_INTERVAL
                            save_config(config)
                            JOB.update(state="running", events=[], automatic=True)
                            Thread(target=run_job, args=(encrypted, None, True, urgent), daemon=False).start()
                        else:
                            next_check = 0
        except Exception:
            print("无法检查 AutoDL 自动保活计划或释放时间", flush=True)
        time.sleep(10)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def reply(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.headers.get("Origin") == EXTENSION_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", EXTENSION_ORIGIN)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if self.headers.get("Host") != ADDRESS or self.headers.get("Origin") != EXTENSION_ORIGIN:
            return self.reply(403, {"error": "请求来源无效"})
        self.reply(204, b"")

    def do_GET(self):
        if self.headers.get("Host") != ADDRESS:
            return self.reply(403, {"error": "请使用本地页面地址"})
        files = {
            "/": ("index.html", "text/html"),
            "/app.js": ("app.js", "text/javascript"),
            "/style.css": ("style.css", "text/css"),
            "/icons/icon-32.png": ("icons/icon-32.png", "image/png"),
            "/favicon.ico": ("icons/icon-32.png", "image/png"),
        }
        if self.path == "/api/status":
            with LOCK:
                config = load_config()
                snapshot = {**JOB, "events": JOB["events"][:],
                            "configured": bool(config.get("token")),
                            "local_auto": config.get("local_auto", True),
                            "next_at": config.get("next_at") if config.get("local_auto", True) else None,
                            "last_state": config.get("last_state"),
                            "last_events": config.get("last_events", [])}
            return self.reply(200, snapshot)
        path = urlsplit(self.path).path
        if path in files:
            name, mime = files[path]
            content_type = f"{mime}; charset=utf-8" if mime.startswith("text/") else mime
            return self.reply(200, (ASSETS / name).read_bytes(), content_type)
        self.reply(404, {"error": "页面不存在"})

    def do_POST(self):
        if (self.headers.get("Host") != ADDRESS or self.headers.get("Origin") not in (ORIGIN, EXTENSION_ORIGIN)
                or self.headers.get_content_type() != "application/json"):
            return self.reply(403, {"error": "请求来源无效"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1048576:
                raise ValueError()
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, TypeError):
            return self.reply(400, {"error": "请求内容无效"})
        if self.path == "/api/forget":
            with LOCK:
                if JOB["state"] == "running":
                    return self.reply(409, {"error": "请等待当前批次结束"})
                save_config({})
            return self.reply(200, {})
        token = body.get("token")
        try:
            if self.path == "/api/configure":
                local_auto = body.get("local_auto", True)
                if not isinstance(local_auto, bool):
                    raise ValueError()
                with LOCK:
                    previous = load_config()
                token = (token or "").strip()
                if token:
                    if not token.isascii() or any(not 33 <= ord(c) <= 126 for c in token):
                        raise ValueError()
                    instances = list_instances(token)
                    encrypted = dpapi(token)
                elif previous.get("token"):
                    encrypted = previous["token"]
                    instances = list_instances(dpapi(encrypted, decrypt=True))
                else:
                    raise ValueError()
                with LOCK:
                    if JOB["state"] == "running":
                        return self.reply(409, {"error": "请等待当前批次结束"})
                    config = load_config()
                    if config.get("token") != previous.get("token"):
                        return self.reply(409, {"error": "令牌设置已变化，请重试"})
                    if local_auto and not config.get("local_auto", True):
                        config["next_at"] = time.time() + INTERVAL
                    config.update(token=encrypted, local_auto=local_auto)
                    config.setdefault("next_at", time.time() + INTERVAL)
                    save_config(config)
                return self.reply(200, {"instances": instances, "local_auto": local_auto})
            with LOCK:
                saved = load_config().get("token")
            if not saved:
                return self.reply(400, {"error": "请先保存令牌"})
            token = dpapi(saved, decrypt=True)
            if self.path == "/api/list":
                return self.reply(200, {"instances": list_instances(token)})
        except (ValueError, AttributeError):
            return self.reply(400, {"error": "请输入有效的网页登录令牌"})
        except Exception:
            return self.reply(502, {"error": "无法验证或读取令牌，请检查令牌和网络"})
        if self.path != "/api/run":
            return self.reply(404, {"error": "接口不存在"})
        uuids = body.get("uuids")
        if (not isinstance(uuids, list) or not uuids
                or any(not isinstance(x, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,80}", x) for x in uuids)
                or len(set(uuids)) != len(uuids)):
            return self.reply(400, {"error": "请选择有效的实例"})
        with LOCK:
            busy = JOB["state"] == "running"
            if not busy:
                JOB.update(state="running", events=[], automatic=False)
                Thread(target=run_job, args=(token, uuids), daemon=False).start()
        if busy:
            return self.reply(409, {"error": "已有批次正在运行"})
        self.reply(202, {"state": "running"})


if __name__ == "__main__":
    with ThreadingHTTPServer((HOST, PORT), Handler) as server:
        Thread(target=scheduler, daemon=True).start()
        print(f"AutoDL Keeper  {ORIGIN}", flush=True)
        server.serve_forever()
