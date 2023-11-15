from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Query
import uvicorn
from models import ExchangePairEnum, RateInfo
from provider import ProviderManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await ProviderManager.initialize_providers()
    yield
    # shutdown
    # например записать сколько было открыто подключений


app = FastAPI(lifespan=lifespan)


@app.get("/rates", response_model=set[RateInfo])
async def get_exchange_rate(
    exchange_pairs: Annotated[set[ExchangePairEnum], Query()] = {
        pair.value for pair in ExchangePairEnum
    },
):
    result = await ProviderManager().get_exchange_rate(exchange_pairs)
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
