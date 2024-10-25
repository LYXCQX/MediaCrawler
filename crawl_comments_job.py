import asyncio
import time

from apscheduler.schedulers.background import BackgroundScheduler
from playwright.async_api import async_playwright

import config
import db
from main import CrawlerFactory
from media_platform.douyin.login import DouYinLogin
from proxy import IpInfoModel
from proxy.proxy_ip_pool import create_ip_pool
from tools import utils
from var import crawler_type_var


async def crawl() -> None:
    # parse cmd
    # await cmd_arg.parse_cmd()

    # init db
    if config.SAVE_DATA_OPTION == "db":
        await db.init_db()

    crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
    await crawler.start()

    if config.SAVE_DATA_OPTION == "db":
        await db.close()


# 定义定时任务，每5分钟执行一次
def job():
    asyncio.run(crawl())


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, 'interval', minutes=1, max_instances=1)
    scheduler.start()
    job()
    try:
        # 让主线程保持运行
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()