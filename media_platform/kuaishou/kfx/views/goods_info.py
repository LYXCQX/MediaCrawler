import asyncio
import os
from http.cookies import SimpleCookie
from typing import Union

from MediaCrawler import config
from MediaCrawler.main import CrawlerFactory
from MediaCrawler.media_platform.kuaishou.kfx.logic.entity import goods_add_shelves_req
from MediaCrawler.tools.utils import logger
from ..logic.Enum.goods_emnu import QueryType
from ..logic.common import COMMON_HEADERS, HOST
from ..logic.entity.goods_req import ThemeGoodsReq, HotRankingReq, GoodsInfoHomeReq
from ..logic.entity.goods_res import GoodsResponse
from ..models import accounts, goods_db
import random
import time

from ...client import KuaiShouClient


# route
async def get_goods_info(
        query_type: int,
        request_entity: Union[ThemeGoodsReq, HotRankingReq, GoodsInfoHomeReq]
):
    """
    获取商品信息
    Args:
        query_type: 查询类型
        request_entity: 请求实体，可能是以下类型之一：
            - ThemeGoodsReq: 主题商品请求
            - HotRankingReq: 热门排行请求
            - GoodsInfoHomeReq: 商品主页信息请求
    """
    _accounts = await accounts.load()
    random.shuffle(_accounts)
    query_type = QueryType.get_by_type(query_type)
    crawler = CrawlerFactory.create_crawler(platform='dy')
    await crawler.start()
    for account in _accounts:
        cookie_dict = SimpleCookie()
        cookie_dict.load(account.get('cookie', ''))
        headers = COMMON_HEADERS.copy()
        headers.update({
            "Cookie": account.get('cookie', ''),
            "Origin": HOST,
            "Referer": query_type.referer,
        })
        ks_client = KuaiShouClient(
            proxies=None,
            headers=headers,
            playwright_page=None,
            cookie_dict=cookie_dict,
        )
        ks_client._host = query_type.host
        pub_count = account.get('pub_count', 100)
        if account.get('expired', 0) == 1:
            continue
        keywords = account.get('keywords', '').split(',')
        account_id = account.get('id', '')
        # 组装请求实体
        req = create_request_entity(query_type, request_entity, 0)
        req.key_word = keywords.pop(0) if keywords else req.key_word
         # 获取今日关键词统计
        today_keywords_stats = await goods_db.get_keywords_statistics(date=time.strftime('%Y-%m-%d'), l_user_id=account_id)
        empty_count = 0
        total_pub_succ = 0
        word_pub_succ = today_keywords_stats.get(req.key_word, 0)
        # 获取今日已添加的商品ID列表
        today_items = await goods_db.query_by_l_user_id(account_id, date=time.strftime('%Y-%m-%d'))
        today_item_ids = {item['relItemId'] for item in today_items}
                      
        while total_pub_succ < pub_count:
            res = await ks_client.post(query_type.uri, request_entity.to_dict())
            res = GoodsResponse.model_validate(res)
            sleep_time = int(os.getenv('QUERY_SLEEP_TIME', 10))
            logger.info(f'获取商品信息成功，账号: {account_id},休眠{sleep_time}秒, 实体: {request_entity.to_dict()}, 返回: {res}')
            
            if res == {} or res.result != 1:
                empty_count += 1
                await asyncio.sleep(sleep_time)
            else:
                req.pcursor = res.pcursor
                empty_count = 0
                for goods in res.data:
                    # 校验数据是否符合
                    if check_goods(query_type, request_entity, goods,today_item_ids):
                        if word_pub_succ >= int(os.getenv('KEYWORD_PUB_LIMIT')):
                            logger.info(f'账号: {account_id}在关键字{req.key_word}已经发布了{word_pub_succ}条,超出配置: {os.getenv("KEYWORD_PUB_LIMIT")}')
                            word_pub_succ = 0  # 如果达到关键词发布限制，则重置关键词发布成功次数
                            req.key_word = keywords.pop(0) if keywords else req.key_word
                            req.pcursor = 0
                            break
                        elif total_pub_succ > pub_count:
                            logger.info(f'账号: {account_id}已经发布了{total_pub_succ}条,超出配置: {pub_count}')
                            break
                        total_pub_succ += 1
                        word_pub_succ += 1
                        if goods.isAdd == 0:
                            shelves_req = goods_add_shelves_req.GoodsAddShelvesReq.from_other(goods,query_type)
                            shelver_res = await ks_client.post('/gateway/distribute/match/shelf/item/save', shelves_req.to_dict())
                            shelver_res_data = shelver_res.get('data', None)
                            if shelver_res_data and shelver_res_data.get('remindContent', None) == '该店铺正处于电商新手期，每日支付订单量上限约为1500单，请确认是否继续添加':
                                await ks_client.post('/gateway/distribute/match/shelf/item/save', shelves_req.to_dict())
                        config.KEYWORDS = req.key_word
                        await crawler.search()
                        # todo 下载视频 处理视频，发布视频
                        goods['l_user_id'] = account_id
                        goods_db.save(goods)
            if empty_count > 3:
                logger.info(f'连续三次没查到数据，继续下一个{request_entity.to_dict()}')
                break
    return False, '请先添加账号'


# 组装请求实体
# 根据查询类型，组装不同的请求实体
# Args:
#     query_type: 查询类型
#     request_entity: 请求实体
# Returns:
#     组装后的请求实体

def create_request_entity(query_type, request_entity, pcursor):
    if query_type == QueryType.SHELF_COLLECTION:
        pass
    elif query_type == QueryType.HOT_SELLING_LIST:
        return HotRankingReq(request_entity.theme_id, request_entity.channel_id)
    elif query_type == QueryType.SEASONAL_HOT_SALE or query_type == QueryType.LOW_PRICE_FIRST_CHOICE or query_type == QueryType.HIGH_COMMISSION_GOODS or query_type == QueryType.SHORT_VIDEO_HOT_SALE:
        return ThemeGoodsReq(request_entity.theme_id, request_entity.sub_theme_id, request_entity.order_type,
                             request_entity.key_word, pcursor)
    return request_entity


# 校验返回数据是否符合规则
def check_goods(query_type, request_entity: GoodsInfoHomeReq, goods,today_item_ids):
    commission_rate_start = os.getenv('COMMISSION_RATE_START')
    if query_type not in [QueryType.KEYWORD_COLLECTION, QueryType.CUSTOM_PRODUCT_ID, QueryType.CATEGORY_COLLECTION,
                          QueryType.ALL_PRODUCTS]:
        if request_entity.price_start is not None and goods.zkFinalPrice < request_entity.price_start:
            logger.info(
                f'商品价格不匹配，商品价格: {goods.zkFinalPrice}, 小于设置的最小商品价格: {request_entity.price_start}')
            return False
        elif request_entity.price_end is not None and goods.zkFinalPrice > request_entity.price_end:
            logger.info(
                f'商品价格不匹配，商品价格: {goods.zkFinalPrice}, 大于设置的最大商品价格: {request_entity.price_end}')
            return False
        elif request_entity.rate_start is not None and goods.commissionRate < request_entity.rate_start:
            logger.info(
                f'商品佣金比率不匹配，商品佣金比率: {goods.commissionRate}%, 小于设置的最小佣金比率: {request_entity.rate_start}%')
            return False
        elif request_entity.rate_end is not None and goods.commissionRate > request_entity.rate_end:
            logger.info(
                f'商品佣金比率不匹配，商品佣金比率: {goods.commissionRate}%, 大于设置的最大佣金比率: {request_entity.rate_end}')
            return False
    if commission_rate_start is not None and float(goods.profitAmount) < float(commission_rate_start):
        logger.info(f'商品{goods.itemTitle}佣金不匹配，商品佣金: {goods.profitAmount}, 小于设置的最小佣金: {commission_rate_start}')
        return False
    elif goods.relItemId in today_item_ids:
        logger.info(f'商品 {goods.itemTitle} 今日已发布，跳过')
        return False
    return True
