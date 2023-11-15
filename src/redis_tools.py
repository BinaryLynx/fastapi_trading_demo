import redis

# import redis.asyncio переделать под асинхронность

from models import RateInfo


class RedisTools:
    __redis_connection = redis.Redis(host="redis", port=6379)
    __expire_seconds = 5

    @classmethod
    def set_rate_info(cls, pair: str, rate_info: RateInfo):
        cls.__redis_connection.set(pair, rate_info, ex=cls.__expire_seconds)

    @classmethod
    def get_rate_info(cls, pair: str):
        return cls.__redis_connection.get(pair)

    @classmethod
    def get_rates_info(cls, pairs: set[str]):
        return [cls.__redis_connection.get(pair) for pair in pairs]

    @classmethod
    def get_keys(cls):
        return cls.__redis_connection.keys(pattern="*")
