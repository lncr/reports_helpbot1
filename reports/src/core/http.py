from asyncio import sleep
from typing import Literal

from httpx import AsyncClient, Headers, HTTPError, QueryParams, ReadTimeout, Response
from loguru import logger

from src.core.dto import BaseDTO


async def send_request(
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    url: str,
    params: QueryParams | None = None,
    data: BaseDTO | None = None,
    headers: Headers | None = None,
    follow_redirects: bool = False,
    no_retries: bool = False,
) -> Response:
    while True:
        async with AsyncClient(timeout=10) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data.model_dump(mode="json") if data is not None else None,
                    headers=headers,
                    follow_redirects=follow_redirects,
                )
            except ReadTimeout as e:
                if no_retries:
                    raise e
                logger.warning(e)
                await sleep(1)
                continue

        try:
            response.raise_for_status()
        except HTTPError as e:
            if no_retries:
                raise e
            try:
                logger.warning(f"{method} {url} -> {response.json()}")
            except Exception:  # noqa: BLE001
                logger.warning(e)
            await sleep(1)
        else:
            return response
