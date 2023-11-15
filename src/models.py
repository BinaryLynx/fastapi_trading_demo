from enum import Enum
from typing import List
from pydantic import BaseModel


class ExchangePair(BaseModel):
    symbol: str


class ExchangePairs(BaseModel):
    symbols: set[ExchangePair]


class ExchangePairEnum(str, Enum):
    # BTC_USD = "BTCUSD"
    # ETH_USD = "ETHUSD"
    # USDTTRC_USD = "USDTTRCUSD"
    # USDTERC_USD = "USDTERCUSD"
    BTC_RUB = "BTCRUB"
    ETH_RUB = "ETHRUB"
    # USDTTRC_RUB = "USDTTRCRUB"
    # USDTERC_RUB = "USDTERCRUB"


class ProviderEnum(str, Enum):
    # Coingecko = "Coingecko"
    Binance = "Binance"


class RateInfo(BaseModel):
    provider: ProviderEnum
    pair: ExchangePairEnum
    rate: float
