import json
import logging
import time
from datetime import datetime, timezone, timedelta

import requests

import os
from dotenv import load_dotenv

from ssh_tools import run_ssh

load_dotenv()  # 这一行加载.env文件中的变量

# 设置日志格式
logging.basicConfig(
    # filename='app.log',
    # filemode='a',  # 追加模式
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

def request_headers(token=None):
    token = (os.getenv('AUTHORIZATION', '') if token is None else token).strip()
    if not token:
        raise RuntimeError('请设置 AUTHORIZATION')
    return {
        'authorization': token,
        'appversion': 'v5.17.1',
        'content-type': 'application/json;charset=UTF-8',
    }


def manage_power(action, instance_uuid, payload=None, *, token=None):
    url = f"https://www.autodl.com/api/v1/instance/{action}"

    data = {
        "instance_uuid": instance_uuid
    }

    if payload is not None:
        data['payload'] = payload
    # Convert the dictionary to a JSON string.
    data_json = json.dumps(data)

    # Make the POST request.
    response = requests.post(url, headers=request_headers(token), data=data_json, timeout=20, allow_redirects=False)

    # Print the response text.
    # print(response.text)
    response.raise_for_status()
    result = response.json()
    if result.get('code') != 'Success':
        raise RuntimeError('AutoDL 电源操作失败')
    return result


def _iter_instances(token):
    url = "https://www.autodl.com/api/v1/instance"
    headers = request_headers(token)
    page_size = 10
    page = 1
    seen = set()
    while True:
        payload = {
            "date_from": "",
            "date_to": "",
            "page_index": page,
            "page_size": page_size,
            "status": [],
            "charge_type": [],
        }
        response = requests.request(
            "POST", url, headers=headers, data=json.dumps(payload),
            timeout=20, allow_redirects=False,
        )
        response.raise_for_status()
        result = response.json()
        if result["code"] != "Success":
            raise RuntimeError("AutoDL 实例查询失败，请检查令牌")
        batch = result["data"]["list"] or []
        if not batch:
            return
        if all(item["uuid"] in seen for item in batch):
            raise RuntimeError(f"AutoDL 第 {page} 页未返回新的实例，无法确认列表完整")
        for item in batch:
            uuid = item["uuid"]
            if uuid not in seen:
                seen.add(uuid)
                yield item
        if len(batch) < page_size:
            return
        page += 1


def instance_list(*, token=None):
    return list(_iter_instances(token))


def get_instance(uuid, *, token=None):
    return next((item for item in _iter_instances(token) if item["uuid"] == uuid), None)


def shutdown_all():
    instances = instance_list()
    for instance in instances:
        uuid = instance['uuid']
        status = instance['status']
        if status == 'running':
            res = manage_power('power_off', uuid)
            if res['code'] == 'Success':
                logger.info(f'{uuid} power_off')
            else:
                logger.info(f'{uuid} power_off failed')
        else:
            logger.info(f'{uuid} status is {status}, not running, no need to power_off')



def power_on_last():
    """
    启动最后一个关机的实例
    :return:
    """
    logger.info('power_on_last')
    instances = instance_list()
    instances = [item for item in instances if item['status'] == 'shutdown']
    if not instances:
        logger.info('没有已关机的实例')
        return
    for data in instances:
        data['stop_time'] = change_timestamp(data['stopped_at']['Time'])

    instances = sorted(instances, key=lambda x: x['stop_time'])
    data = instances[0]
    status = data['status']
    uuid = data['uuid']
    if status == 'shutdown':
        res = manage_power('power_on', uuid, 'non_gpu')
        if res['code'] == 'Success':
            logger.info(f'{uuid} power_on')
        else:
            logger.info(f'{uuid} power_on failed')


def change_timestamp(time_str):
    if time_str == '0001-01-01T00:00:00Z':
        return 0
    # 将时间字符串解析为datetime对象
    dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

    # 如果时间字符串中包含时区信息，则可以将其保留在datetime对象中
    # 如果不包含时区信息，可以手动添加所需的时区信息
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))  # 时区信息表示+08:00
    return dt.timestamp()

def power_api():
    """
    开启服务器，并且运行程序
    :return:
    """
    instances = instance_list()
    for data in instances:
        data['stop_time'] = change_timestamp(data['stopped_at']['Time'])

    instances = sorted(instances, key=lambda x: x['stop_time'], reverse=True)
    # for data in instances:
    #     print(data)
    #     print(data['uuid'], data['status'], data['gpu_idle_num'], data['stopped_at']['Time'], data['stop_time'])

    # 过滤data['gpu_idle_num'] == 0的设备
    instances = filter(lambda x: x['gpu_idle_num'] > 0, instances)
    instances = list(instances)
    if len(instances) > 0:
        data = instances[0]
        status = data['status']
        uuid = data['uuid']
        gpu_idle_num = data['gpu_idle_num']
        root_password = data['root_password']
        proxy_host = data['proxy_host']
        ssh_port = data['ssh_port']

        if status == 'shutdown':
            res = manage_power('power_on', uuid)
            if res['code'] == 'Success':
                logger.info(f'{uuid} power_on')
                # 等待实例启动完成
                while True:
                    instance = get_instance(uuid)
                    if instance['status'] == 'running':
                        break
                    time.sleep(1)
                    print('wait for instance running')

                # 获取实例信息
                run_ssh(proxy_host, ssh_port, 'root', root_password, '/root/frp_me/frpc -c /root/frp_me/frpc.ini')
                run_ssh(proxy_host, ssh_port, 'root', root_password, '/root/miniconda3/bin/python /root/autodl-fs/codegen/app.py')

            else:
                logger.info(f'{uuid} power_on failed')
        else:
            logger.info(f'{uuid} status is {status}, not shutdown, no need to power_on')


if __name__ == '__main__':
    pass
    # instances = instance_list()
    # for data in instances:
    #     data['stop_time'] = change_timestamp(data['stopped_at']['Time'])
    #
    # instances = sorted(instances, key=lambda x: x['stop_time'], reverse=True)
    # for data in instances:
    #     print(data)
    #     print(data['uuid'], data['status'], data['gpu_idle_num'], data['stopped_at']['Time'], data['stop_time'])

    # 过滤data['gpu_idle_num'] == 0的设备
    # for data in instances:
    #     print(data)
    #     print(data['uuid'], data['status'], data['gpu_idle_num'], data['stopped_at']['Time'], data['stop_time'], data['root_password'], data['proxy_host'], data['ssh_port'])

    # shutdown_all(instances)
    # power_on_last()
    # 解析命令行参数
