from MediaCrawler.media_platform.kuaishou.kfx.logic.sql.driver import CommonAccount
from MediaCrawler.media_platform.kuaishou.kfx.logic.sql.goods_info_db import GoodsInfoStore

accounts = CommonAccount("../data/sql_lab/kuaishou/kuaishou_kfx.db")
goods_db = GoodsInfoStore("../data/sql_lab/kuaishou/kuaishou_kfx.db")
