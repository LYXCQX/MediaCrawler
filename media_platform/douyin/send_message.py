import asyncio
import logging
import time
from typing import List, Dict

from playwright.async_api import async_playwright

import config
from async_db import AsyncMysqlDB
from db import init_db
from var import media_crawler_db_var


async def get_all_comment() -> List[str]:
    async_db_conn: AsyncMysqlDB = media_crawler_db_var.get()
    
    # 查询 douyin_aweme_comment 表中 reply_state 为 1 的 sec_uid
    sql_comment: str = "SELECT DISTINCT sec_uid FROM douyin_aweme_comment WHERE reply_state = 1"
    rows_comment: List[Dict] = await async_db_conn.query(sql_comment)
    sec_uid_list = [row['sec_uid'] for row in rows_comment]
    
    # 查询 douyin_aweme 表中所有不重复的 sec_uid
    sql_aweme: str = "SELECT DISTINCT sec_uid FROM douyin_aweme"
    rows_aweme: List[Dict] = await async_db_conn.query(sql_aweme)
    sec_au_list = {row['sec_uid'] for row in rows_aweme}
    
    # 返回 sec_uid_list 中不在 sec_au_list 的 sec_uid
    result_list = [sec_uid for sec_uid in sec_uid_list if sec_uid not in sec_au_list]
    
    return result_list


async def send_message_to_douyin_user(page, message):
    button_sx = '.fwi7VMnj .FEvqkPxo .K8kpIsJm'
    button_sx1 = '.XB2sFwjg .K8kpIsJm'
    target_class = '.vgonMAXk._VnLWL_m'
    sending_class = '.semi-spin.im-message-spin.semi-spin-small'
    failed_class = '.xbd3MiWp'
    start_time = time.time()  # 记录开始时间
    
    # await page.wait_for_selector(button_sx, state='visible', timeout=60000)
    while not await page.is_visible(target_class):
        if time.time() - start_time > 60:  # 检查是否超过1分钟
            raise TimeoutError("Exceeded 1 minute while waiting for target class to be visible.")
        
        # 轮番点击两个按钮
        if await page.is_visible(button_sx):
            await page.click(button_sx)
        elif await page.is_visible(button_sx1):
            await page.click(button_sx1)
        
        await asyncio.sleep(1)  # 等待一秒再检查目标元素是否可见

    # 在目标元素可见后输入信息
    await page.fill('div.public-DraftEditor-content', message)
    await page.click('span.PygT7Ced.e2e-send-msg-btn')

    # 等待消息发送成功或失败
    while await page.is_visible(sending_class):
        await asyncio.sleep(1)  # 等待发送完成

    # if await page.is_visible(failed_class):
        # raise Exception("Message sending failed.")


async def main():
    await init_db()
    user_list = await get_all_comment()  # 从数据库获取用户列表
    message = config.GLOBAL_DRAINAGE_MESSAGE if config.DY_DRAINAGE_MESSAGE =='' else config.DY_DRAINAGE_MESSAGE

    # 动态获取屏幕分辨率
    # monitor = get_monitors()[0]
    # viewport = {"width": monitor.width, "height": monitor.height}

    async with async_playwright() as playwright:
        chromium = playwright.chromium
        user_data_dir = 'E:\IDEA\workspace\MediaCrawler\\browser_data\dy_user_data_dir'
        context = await chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            accept_downloads=True,
            headless=config.HEADLESS,
            proxy=None,  # type: ignore
            # viewport=viewport,  # 使用动态获取的视口大小
            user_agent=None
        )  # type: ignore
        # stealth.min.js is a js script to prevent the website from detecting the crawler.
        await context.add_init_script(path="libs/stealth.min.js")

        page = await context.new_page()  # 每次处理一个用户时创建一个新页面

        for sec_uid in user_list:
            try:
                await page.goto(f"https://www.douyin.com/user/{sec_uid}?from_tab_name=main")
                await send_message_to_douyin_user(page, message)

                async_db_conn: AsyncMysqlDB = media_crawler_db_var.get()
                update_sql = "UPDATE douyin_aweme_comment SET reply_state = 2, reply_content = %s WHERE sec_uid = %s"
                await async_db_conn.execute(update_sql, message, sec_uid)  # 直接传递参数
            except Exception as e:
                logging.error(f'用户私信异常{e}')

        await page.close()  # 处理完一个用户后关闭页面
        await context.close()

# 运行主函数
if __name__ == "__main__":
    asyncio.run(main())
