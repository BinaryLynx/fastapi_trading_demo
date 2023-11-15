from abc import ABC, abstractmethod
import asyncio
import json
import uuid

from fastapi import HTTPException, status
from websockets import ConnectionClosed
from models import ExchangePairEnum, ExchangePairs, ProviderEnum, RateInfo
from websockets.client import connect
from websockets.protocol import State
import itertools

from redis_tools import RedisTools


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Provider(ABC):
    """Класс провайдера: для каждого сайта (Binance, Coingecko) создается конкретный дочерний класс. Класс отвечает за непосредственное взаимодействие с сайтами."""

    available_exchange_pairs = {}

    @abstractmethod
    def __init__(self) -> None:
        self.name = "provider name"
        self.url = "provider url"
        self.websocket = None
        self.timeout = None

    @abstractmethod
    async def connect():
        pass

    @abstractmethod
    async def get_exchange_rate(self, exchange_pairs: set[str]):
        pass

    @abstractmethod
    async def get_available_exchange_pairs():
        pass


class CoingeckoProvider(Provider):
    pass


class BinanceProvider(Provider):
    available_exchange_pairs = {
        ExchangePairEnum.BTC_RUB.value,
        ExchangePairEnum.ETH_RUB.value,
    }

    def __init__(self) -> None:
        self.name = "Binance"
        self.url = "wss://ws-api.binance.com:443/ws-api/v3"
        self.websocket = None
        self.timeout = None

    async def get_available_exchange_pairs(self):
        message = {
            "id": "5494febb-d167-46a2-996d-70533eb4d976",
            "method": "exchangeInfo",
        }
        try:
            await self.websocket.send(json.dumps(message))
            response = await self.websocket.recv()
        except ConnectionClosed:
            print(type(e).__name__, e.args)
            raise
        except TypeError:
            print(type(e).__name__, e.args)
            raise
        except Exception as e:
            print(type(e).__name__, e.args)
            raise

        self.available_exchange_pairs = ExchangePairs(**response.json())

    async def ping(self):
        message = {
            "id": str(uuid.uuid4()),
            "method": "ping",
        }
        await self.websocket.send(json.dumps(message))
        message = await self.websocket.recv()
        return message

    async def connect(self):
        try:
            self.websocket = await connect(self.url, open_timeout=self.timeout)
        except TimeoutError:
            print("CONNECTION TIMEOUT")
            return False
        except Exception as e:
            print(type(e).__name__, e.args)
            return False
        return True

    async def get_exchange_rate(self, exchange_pairs: set[str]):
        if not exchange_pairs <= self.available_exchange_pairs:
            raise TypeError  # Поменять на кастомную ошибку: сервис не педоставляет информацию по данной паре

        message = {
            "id": str(uuid.uuid4()),
            "method": "ticker.price",
            "params": {"symbols": list(exchange_pairs)},
        }
        try:
            await self.websocket.send(json.dumps(message))
            response = await self.websocket.recv()
        except ConnectionClosed:
            print(type(e).__name__, e.args)
            raise
        except TypeError:
            print(type(e).__name__, e.args)
            raise
        except Exception as e:
            print(type(e).__name__, e.args)
            raise
        response = json.loads(response)
        if response["status"] != 200:
            raise TypeError  # Выбрать ошибку получше

        result = {
            {"provider": self.name, "pair": res["symbol"], "rate": float(res["price"])}
            for res in response["result"]
        }

        await self.write_to_redis(result)

        return result

    async def write_to_redis(self, rates: set[RateInfo]):
        for rate in rates:
            RedisTools.set_rate_info(rate["pair"], rate)


class ProviderFactory(metaclass=Singleton):
    """Создает экземпляры провайдеров"""

    def create(self, provider_type: ProviderEnum) -> Provider:
        if provider_type == ProviderEnum.Binance:
            instance = BinanceProvider()
            return instance
        elif provider_type == ProviderEnum.Coingecko:
            instance = CoingeckoProvider()
            return instance


class ProviderManager(metaclass=Singleton):
    """Управляет доступными провайдерами. Здесь определена логика переподключения, выбора доступного провайдера, выбор способа возврата ответа клиенту. Предполагается что клиент будет использовать интерфейс этого класса"""

    def __init__(self) -> None:
        self.providers = {
            provider_type.value: ProviderFactory().create(provider_type)
            for provider_type in ProviderEnum
        }
        self.reconnect_attempts = 2

    async def initialize_providers(self):
        """Получить доступные торговые пары для всех провайдеров"""
        tasks = [
            asyncio.create_task(provider.get_available_exchange_pairs())
            for provider in self.providers
        ]
        results = await asyncio.gather(*tasks)

    async def get_exchange_rate(self, exchange_pairs: set[str]):
        # Посмотреть какие пары уже есть в редис, каких нет. Недостающие - попробовать получить у провайдера
        pairs_to_fetch = exchange_pairs - set(
            s.decode("utf-8") for s in RedisTools.get_keys()
        )
        pairs_to_get_from_redis = exchange_pairs - pairs_to_fetch
        fetched_pairs = {}
        redis_pairs = RedisTools.get_rates_info(pairs_to_get_from_redis)
        # Попробовать получить результат с указанного кол-ва попыток
        if pairs_to_fetch:
            for provider_type in itertools.chain.from_iterable(
                itertools.repeat(ProviderEnum, self.reconnect_attempts)
            ):
                # Проверить есть ли уже объект для этого провайдера (в конечном счете интересует подключение-сокет)
                if not self.providers[provider_type.value]:
                    self.providers[provider_type.value] = ProviderFactory().create(
                        provider_type
                    )
                # Если не открыт сокет - попробовать открыть
                if not self.providers[provider_type.value].websocket or self.providers[
                    provider_type.value
                ].websocket.state not in (
                    State.OPEN,
                    State.CONNECTING,
                ):
                    socket_connection_result = await self.providers[
                        provider_type.value
                    ].connect()
                    if not socket_connection_result:
                        continue
                # если сокет открыт - попробовать получить результат по нему
                try:
                    fetched_pairs = await self.providers[
                        provider_type.value
                    ].get_exchange_rate(pairs_to_fetch)
                except Exception as e:
                    print(type(e).__name__, e.args)
                    continue

                break
            # Если все попытки завершились неудачно - вернуть ошибку
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"Failed to connect to services after {self.reconnect_attempts} attempts",
            )
        # Вернуть ответ
        return redis_pairs | fetched_pairs
