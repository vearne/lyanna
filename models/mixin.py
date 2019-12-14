import asyncio
import markupsafe
import mistune
import aioredis
from aioredis.commands import Redis

import config
from .var import redis_var

markdown = mistune.Markdown()


_redis = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        try:
            redis = redis_var.get()
        except LookupError:
            # Hack for debug mode
            loop = asyncio.get_event_loop()
            redis = await aioredis.create_redis_pool(
                config.REDIS_URL, minsize=5, maxsize=20, loop=loop)
        _redis = redis
    return _redis


class ContentMixin:
    id: int

    @property
    async def redis(self) -> Redis:
        return await get_redis()

    def get_db_key(self, key: str) -> str:
        return f'{self.__class__.__name__}/{self.id}/props/{key}'

    async def set_props_by_key(self, key: str, value: str) -> bool:
        key = self.get_db_key(key)
        return await (await self.redis).set(key, value)  # noqa: W606

    async def get_props_by_key(self, key: str) -> bytes:
        key = self.get_db_key(key)
        return await (await self.redis).get(key) or b''  # noqa: W606

    async def set_content(self, content: str) -> bool:
        return await self.set_props_by_key('content', content)

    async def save(self, *args, **kwargs):
        if (content := kwargs.pop('content', None)) is not None:
            await self.set_content(content)
        return await super().save(*args, **kwargs)  # type: ignore

    @property
    async def content(self) -> str:
        if (rv := await self.get_props_by_key('content')):
            return rv.decode('utf-8')
        return ''

    @property
    async def html_content(self):
        if not (content := str(markupsafe.escape(await self.content))):
            return ''
        return markdown(content.replace('&gt;', '>'))
