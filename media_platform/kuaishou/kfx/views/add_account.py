from pydantic import BaseModel

from MediaCrawler.media_platform.kuaishou.kfx.models import accounts
from MediaCrawler.tools.utils import logger


class Param(BaseModel):
    id: str
    cookie: str

async def add_account(param: Param):
    '''
    添加快手账号
    '''
    if param.id == '' or param.cookie == '':
        logger.error(f'id or cookie is empty, id: {param.id}, cookie: {param.cookie}')
        return False, "id and cookie is required"

    await accounts.save(param.id, param.cookie, 0)
    logger.info(f'kuaishou add account, id: {param.id}, cookie: {param.cookie}')
    return True