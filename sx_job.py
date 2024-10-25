import asyncio

from apscheduler.schedulers.background import BackgroundScheduler

from media_platform.douyin.send_message import main


# 定义定时任务，每5分钟执行一次
def job():
    asyncio.run(main())


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, 'interval', minutes=5, max_instances=1)
    scheduler.start()
    job()
