# 创建解析器
import argparse
import json

from autodl import instance_list, power_on_last, shutdown_all

parser = argparse.ArgumentParser(description="Control the AutoDL system.")
actions = parser.add_mutually_exclusive_group()
actions.add_argument('--list', action='store_true', help='List instance IDs and states')
actions.add_argument('--power_on_last', action='store_true', help='Activate the power_on_last function')
actions.add_argument('--shutdown_all', action='store_true', help='Activate the shutdown_all function')

def add_parser():
    args = parser.parse_args()
    if args.list:
        print(json.dumps([
            {"uuid": item["uuid"], "status": item["status"]}
            for item in instance_list()
        ], indent=2))
    elif args.power_on_last:
        power_on_last()
    elif args.shutdown_all:
        shutdown_all()

if __name__ == '__main__':
    try:
        add_parser()
    except RuntimeError as exc:
        parser.exit(1, f'{exc}\n')