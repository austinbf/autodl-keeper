
import logging
import os
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from autodl import get_instance, manage_power

# 设置日志格式
logging.basicConfig(
    # filename='app.log',
    # filemode='a',  # 追加模式
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

@scheduler.scheduled_job(IntervalTrigger(minutes=5)) # minutes=5 hours=1
def change():
    instance_uuid = os.environ["AUTODL_INSTANCE_UUID"]
    instance = get_instance(instance_uuid)
    if instance is None or instance["status"] != "shutdown":
        logger.info("实例不存在或当前未关机，跳过本次操作")
        return
    logger.info("Powering on the instance...")
    manage_power('power_on', instance_uuid, 'non_gpu')
    # 这里记录一个日志，表示电源打开
    logger.info("Instance powered on. Waiting for 60 seconds before powering off...")
    time.sleep(60)  # 等待60秒后关闭电源
    # 这里记录一个日志，表示即将关闭电源
    logger.info("Powering off the instance...")
    manage_power('power_off', instance_uuid)
    # 这里记录一个日志，表示电源关闭
    logger.info("Instance powered off.")

if __name__ == '__main__':
    if not os.getenv("AUTODL_INSTANCE_UUID", "").strip():
        raise SystemExit("请设置 AUTODL_INSTANCE_UUID")
    if os.getenv('RUN_CHANGE_FUNCTION'):
        logger.info("直接运行日志")
        change()
    else:
        logger.info("开启定时器，并且不停止")
        scheduler.start()
        print('Scheduler started, press Ctrl+C to exit.')

        try:
            # 保持主线程活跃
            while True:
                time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            # 如果您运行的是长期进程，即使在守护模式下也应该执行此关闭操作
            scheduler.shutdown()  # 安全关闭调度器