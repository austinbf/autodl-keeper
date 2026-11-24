"""Callable AutoDL batch runner for the local control panel."""
import time
from datetime import datetime, timedelta

from autodl import get_instance, instance_list, manage_power


def api_date(value):
    if isinstance(value, dict):
        value = value.get("Time") if value.get("Valid") else None
    if not isinstance(value, str) or value.startswith("0001-"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def list_instances(token):
    instances = []
    for item in instance_list(token=token):
        dates = []
        for field, label in (("expired_at", "租期到期"), ("machine_expired_at", "主机下架")):
            value = api_date(item.get(field))
            if value:
                dates.append((value.timestamp(), label))
        release_at = None
        stopped = api_date(item.get("stopped_at"))
        if item["status"] == "shutdown" and stopped:
            region = item.get("region_name") or ""
            days = 7 if "潮汐" in region else 60 if item["uuid"].startswith("pro-") else 15
            release_at = (stopped + timedelta(days=days)).timestamp()
            dates.append((release_at, "关机释放（估算）"))
        deadline, reason = min(dates, default=(None, None))
        instances.append({
            "uuid": item["uuid"], "status": item["status"],
            "sub_status": item.get("sub_status"),
            "disk_health": item.get("disk_health_status"),
            "deadline": deadline, "deadline_reason": reason, "release_at": release_at,
            "stopped_at": stopped.timestamp() if stopped else None,
        })
    return instances


def wait_for(token, uuid, target):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            item = get_instance(uuid, token=token)
            if item and item["status"] == target:
                return item
        except Exception:
            # A transient list failure should not interrupt verification.
            pass
        time.sleep(5)
    raise RuntimeError(f"等待 {uuid} 进入 {target} 超时")


def run_sequence(token, uuids, report):
    available = {item["uuid"]: item["status"] for item in list_instances(token)}
    if any(available.get(uuid) != "shutdown" for uuid in uuids):
        raise RuntimeError("请选择当前账号中已关机的实例")

    for uuid in uuids:
        item = get_instance(uuid, token=token)
        if not item or item["status"] != "shutdown":
            raise RuntimeError(f"{uuid} 的状态已变化，批次停止")
        report(f"{uuid} · 请求无卡开机")
        try:
            manage_power("power_on", uuid, "non_gpu", token=token)
            running = wait_for(token, uuid, "running")
            if running.get("start_mode") != "non_gpu":
                raise RuntimeError(f"{uuid} 未确认无卡模式")
            report(f"{uuid} · 已确认无卡运行")
        finally:
            for attempt in range(3):
                try:
                    item = get_instance(uuid, token=token)
                    if not item or item["status"] != "shutdown":
                        manage_power("power_off", uuid, token=token)
                    wait_for(token, uuid, "shutdown")
                    break
                except Exception as exc:
                    if attempt == 2:
                        raise RuntimeError(f"{uuid} 关机未确认，请在 AutoDL 控制台检查") from exc
                    time.sleep(5)
        report(f"{uuid} · 已确认关机")
