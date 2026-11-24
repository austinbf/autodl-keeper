"""Run AutoDL keepalive from a scheduled GitHub Actions job."""
import argparse
import os
import time

from keeper_plugin import list_instances, run_sequence

DAY = 86400


def due_instances(instances, now):
    due = []
    for item in instances:
        if item["status"] != "shutdown":
            continue
        stopped_at = item["stopped_at"]
        release_at = item["release_at"]
        if stopped_at is not None and now - stopped_at >= 8 * DAY:
            due.append(item["uuid"])
        elif release_at is not None and release_at <= now + 3 * DAY:
            due.append(item["uuid"])
    return due


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    token = os.getenv("AUTHORIZATION", "").strip()
    if not token:
        parser.exit(1, "请配置 GitHub Actions Secret AUTHORIZATION。\n")
    try:
        instances = list_instances(token)
        due = due_instances(instances, time.time())
        print(f"检查 {len(instances)} 台实例，{len(due)} 台需要保活。", flush=True)
        if args.check_only:
            print("只读检查完成。", flush=True)
        elif due:
            run_sequence(token, due, lambda message: print(message, flush=True))
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")
    except Exception:
        parser.exit(1, "AutoDL 请求失败，请检查令牌和 GitHub runner 的网络。\n")


if __name__ == "__main__":
    main()
