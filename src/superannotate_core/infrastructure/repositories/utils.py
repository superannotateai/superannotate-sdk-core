import os
import io
import copy
import json
import typing
import asyncio
import logging
from typing import Callable
from threading import Thread

import aiohttp

logger = logging.getLogger(__name__)


class AsyncThread(Thread):
    def __init__(
            self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None
    ):
        super().__init__(
            group=group,
            target=target,
            name=name,
            args=args,
            kwargs=kwargs,
            daemon=daemon,
        )
        self._exc = None
        self._response = None

    @property
    def response(self):
        return self._response

    def run(self):
        try:
            self._response = super().run()
        except BaseException as e:
            self._exc = e

    def join(self, timeout=None) -> typing.Any:
        Thread.join(self, timeout=timeout)
        if self._exc:
            raise self._exc
        return self._response


def run_async(f):
    response = [None]

    def wrapper(func: typing.Callable):
        response[0] = asyncio.run(func)  # noqa
        return response[0]

    thread = AsyncThread(target=wrapper, args=(f,))
    thread.start()
    thread.join()
    return response[0]


class AIOHttpSession(aiohttp.ClientSession):
    RETRY_STATUS_CODES = [401, 403, 502, 503, 504]
    RETRY_LIMIT = 3
    BACKOFF_FACTOR = 0.3

    @staticmethod
    def _copy_form_data(data: aiohttp.FormData) -> aiohttp.FormData:
        form_data = aiohttp.FormData(quote_fields=False)
        for field in data._fields:  # noqa
            if isinstance(field[2], io.IOBase):
                field[2].seek(0)
            form_data.add_field(
                value=field[2],
                content_type=field[1].get("Content-Type", ""),
                **field[0],
            )
        return form_data

    async def request(self, *args, **kwargs) -> aiohttp.ClientResponse:
        attempts = self.RETRY_LIMIT
        delay = 0
        for _ in range(attempts):
            delay += self.BACKOFF_FACTOR
            try:
                response = await super()._request(*args, **kwargs)
                if attempts <= 1 or response.status not in self.RETRY_STATUS_CODES:
                    if not response.ok:
                        logger.error(await response.text())
                        response.raise_for_status()
                    return response
                if isinstance(kwargs["data"], aiohttp.FormData):
                    raise RuntimeError(await response.text())
            except (aiohttp.ClientError, RuntimeError) as e:
                if attempts <= 1:
                    raise
                data = kwargs.get("data", {})
                if isinstance(data, aiohttp.FormData):
                    kwargs["data"] = self._copy_form_data(data)
            attempts -= 1
            await asyncio.sleep(delay)


_seconds = 2 ** 10
TIMEOUT = aiohttp.ClientTimeout(
    total=_seconds, sock_connect=_seconds, sock_read=_seconds
)


class StreamedAnnotations:
    DELIMITER = b"\\n;)\\n"

    def __init__(
            self,
            headers: dict,
            callback: Callable = None,
            map_function: Callable = None,
    ):
        self._headers = headers
        self._annotations = []
        self._callback: Callable = callback
        self._map_function = map_function
        self._items_downloaded = 0

    async def fetch(
            self,
            method: str,
            session: AIOHttpSession,
            url: str,
            data: dict = None,
            params: dict = None,
    ):
        kwargs = {"params": params, "json": {}}
        if "folder_id" in kwargs["params"]:
            kwargs["json"] = {"folder_id": kwargs["params"].pop("folder_id")}
        if data:
            kwargs["json"].update(data)
        response = await session.request(method, url, **kwargs, timeout=TIMEOUT)  # noqa
        buffer = b""
        async for line in response.content.iter_any():
            slices = (buffer + line).split(self.DELIMITER)
            for _slice in slices[:-1]:
                yield json.loads(_slice)
            buffer = slices[-1]
        if buffer:
            yield json.loads(buffer)

    async def list_annotations(
            self,
            method: str,
            url: str,
            data: typing.Iterable[int] = None,
            params: dict = None,
            verify_ssl=False,
    ):
        params = copy.copy(params)
        params["limit"] = len(list(data))
        annotations = []
        async with AIOHttpSession(
                headers=self._headers,
                timeout=TIMEOUT,
                connector=aiohttp.TCPConnector(ssl=verify_ssl, keepalive_timeout=2 ** 32),
                # raise_for_status=True,
        ) as session:
            async for annotation in self.fetch(
                    method,
                    session,
                    url,
                    self._process_data(data),
                    params=copy.copy(params),
            ):
                annotations.append(
                    self._callback(annotation) if self._callback else annotation
                )

        return annotations

    async def download_annotations(
            self,
            method: str,
            url: str,
            download_path,
            data: typing.List[int],
            params: dict = None,
    ):
        params = copy.copy(params)
        params["limit"] = len(data)
        async with AIOHttpSession(
                headers=self._headers,
                timeout=TIMEOUT,
                connector=aiohttp.TCPConnector(ssl=False, keepalive_timeout=2 ** 32),
                # raise_for_status=True,
        ) as session:
            async for annotation in self.fetch(
                    method,
                    session,
                    url,
                    self._process_data(data),
                    params=params,
            ):
                self._annotations.append(
                    self._callback(annotation) if self._callback else annotation
                )
                self._store_annotation(
                    download_path,
                    annotation,
                    self._callback,
                )
                self._items_downloaded += 1

    @staticmethod
    def _store_annotation(path, annotation: dict, callback: Callable = None):
        os.makedirs(path, exist_ok=True)
        with open(f"{path}/{annotation['metadata']['name']}.json", "w") as file:
            annotation = callback(annotation) if callback else annotation
            json.dump(annotation, file)

    def _process_data(self, data):
        if data and self._map_function:
            return self._map_function(data)
        return data
