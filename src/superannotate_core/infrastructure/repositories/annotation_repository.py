import asyncio
import copy
import io
import json
from pathlib import Path
from typing import Callable
from typing import Iterable
from typing import List
from typing import Union
from urllib.parse import urljoin

import aiohttp
from superannotate_core.core.entities import BaseItemEntity
from superannotate_core.core.utils import chunkify
from superannotate_core.infrastructure.repositories.base import BaseRepositry
from superannotate_core.infrastructure.repositories.utils import AIOHttpSession
from superannotate_core.infrastructure.repositories.utils import StreamedAnnotations
from typing_extensions import TypedDict


class SortedAnnotationsResponse(TypedDict):
    small: List[List[dict]]
    large: List[List[dict]]


class AnnotationRepository(BaseRepositry):
    URL_GET_ANNOTATIONS = "items/annotations/download"
    URL_CLASSIFY_ITEM_SIZE = "items/annotations/download/method"
    URL_DOWNLOAD_LARGE_ANNOTATION = "items/{item_id}/annotations/download"
    URL_START_FILE_SYNC = "items/{item_id}/annotations/sync"
    URL_START_FILE_SYNC_STATUS = "items/{item_id}/annotations/sync/status"
    URL_UPLOAD_ANNOTATIONS = "items/annotations/upload"
    URL_START_FILE_UPLOAD_PROCESS = "items/{item_id}/annotations/upload/multipart/start"
    URL_START_FILE_SEND_PART = "items/{item_id}/annotations/upload/multipart/part"
    URL_START_FILE_SEND_FINISH = "items/{item_id}/annotations/upload/multipart/finish"

    def sort_annotations_by_size(
        self, project_id: int, folder_id: int, item_ids: List[int]
    ) -> SortedAnnotationsResponse:
        response_data: dict = {"small": [], "large": []}
        response = self._session.request(
            url=urljoin(self._session.assets_provider_url, self.URL_CLASSIFY_ITEM_SIZE),
            method="post",
            params={"limit": len(item_ids)},
            json={
                "project_id": project_id,
                "item_ids": item_ids,
            },  # todo add "folder_id": folder_id,
            build_url=False,
        )
        response.raise_for_status()
        data = response.json()
        return SortedAnnotationsResponse(
            small=[i["data"] for i in data.get("small", {}).values()],
            large=data.get("large", []),
        )

    async def list_annotations(
        self,
        project_id: int,
        folder_id: int,
        item_ids: Iterable[int],
        callback: Callable = None,
    ) -> List[dict]:
        query_params = {
            "team_id": self._session.team_id,
            "project_id": project_id,
            "folder_id": folder_id,
        }
        handler = StreamedAnnotations(
            headers=self._session.default_headers,
            map_function=lambda x: {"image_ids": x},
            callback=callback,
        )
        return await handler.list_annotations(
            method="post",
            url=urljoin(self._session.assets_provider_url, self.URL_GET_ANNOTATIONS),
            data=item_ids,
            params=query_params,
        )

    async def _sync_large_annotation(
        self, project_id: int, folder_id: int, item_id: int
    ):
        sync_params = {
            "team_id": self._session.team_id,
            "project_id": project_id,
            "folder_id": folder_id,
            "desired_transform_version": "export",
            "desired_version": self._session.ANNOTATION_VERSION,
            "current_transform_version": self._session.ANNOTATION_VERSION,
            "current_source": "main",
            "desired_source": "secondary",
        }
        sync_url = urljoin(
            self._session.assets_provider_url,
            self.URL_START_FILE_SYNC.format(item_id=item_id),
        )
        async with AIOHttpSession(
            connector=aiohttp.TCPConnector(ssl=False),
            headers=self._session.default_headers,
            # raise_for_status=True,
        ) as session:
            _response = await session.request("post", sync_url, params=sync_params)
            sync_params.pop("current_source")
            sync_params.pop("desired_source")

            synced = False
            sync_status_url = urljoin(
                self._session.assets_provider_url,
                self.URL_START_FILE_SYNC_STATUS.format(item_id=item_id),
            )
            while synced != "SUCCESS":
                synced = await session.get(sync_status_url, params=sync_params)
                synced = await synced.json()
                synced = synced["status"]
                await asyncio.sleep(5)
        return synced

    async def get_large_annotation(
        self, project_id: int, folder_id: int, item_id: int
    ) -> dict:
        url = urljoin(
            self._session.assets_provider_url,
            self.URL_DOWNLOAD_LARGE_ANNOTATION.format(item_id=item_id),
        )
        query_params = {
            "team_id": self._session.team_id,
            "project_id": project_id,
            "folder_id": folder_id,
            "version": self._session.ANNOTATION_VERSION,
        }
        await self._sync_large_annotation(
            project_id=project_id, folder_id=folder_id, item_id=item_id
        )

        async with AIOHttpSession(
            connector=aiohttp.TCPConnector(ssl=False),
            headers=self._session.default_headers,
            # raise_for_status=True,
        ) as session:
            start_response = await session.request("post", url, params=query_params)
            large_annotation = await start_response.json()
            return large_annotation

    async def download_small_annotations(
        self,
        project_id: int,
        folder_id: int,
        item_ids: List[int],
        download_path: str,
        callback: Callable = None,
    ):
        query_params = {
            "team_id": self._session.team_id,
            "project_id": project_id,
            "folder_id": folder_id,
        }
        handler = StreamedAnnotations(
            headers=self._session.default_headers,
            map_function=lambda x: {"image_ids": x},
            callback=callback,
        )

        return await handler.download_annotations(
            method="post",
            url=urljoin(self._session.assets_provider_url, self.URL_GET_ANNOTATIONS),
            data=item_ids,
            params=query_params,
            download_path=download_path,
        )

    async def download_large_annotation(
        self,
        project_id: int,
        folder_id: int,
        item: BaseItemEntity,
        download_path: Union[str, Path],
        callback: Callable = None,
    ):
        item_id = item.id
        item_name = item.name
        query_params = {
            "team_id": self._session.team_id,
            "project_id": project_id,
            "folder_id": folder_id,
            "version": self._session.ANNOTATION_VERSION,
        }

        await self._sync_large_annotation(
            project_id=project_id, folder_id=folder_id, item_id=item_id
        )

        url = urljoin(
            self._session.assets_provider_url,
            self.URL_DOWNLOAD_LARGE_ANNOTATION.format(item_id=item_id),
        )
        async with AIOHttpSession(
            connector=aiohttp.TCPConnector(ssl=False),
            headers=self._session.default_headers,
            raise_for_status=True,
        ) as session:
            start_response = await session.request("post", url, params=query_params)
            res = await start_response.json()

            Path(download_path).mkdir(exist_ok=True, parents=True)
            dest_path = Path(download_path) / (item_name + ".json")
            with open(dest_path, "w") as fp:
                if callback:
                    res = callback(res)
                json.dump(res, fp)

    async def _upload_small_annotations(
        self,
        project_id: int,
        folder_id: int,
        small_items_to_upload: List[dict],
        failed_ids: List[int],
    ):
        params = [
            ("team_id", self._session.team_id),
            ("project_id", project_id),
            ("folder_id", folder_id),
            *[("image_ids[]", i["item_id"]) for i in small_items_to_upload],
        ]
        url = urljoin(
            self._session.assets_provider_url, f"{self.URL_UPLOAD_ANNOTATIONS}"
        )
        headers = copy.copy(self._session.default_headers)
        del headers["Content-Type"]
        async with AIOHttpSession(
            connector=aiohttp.TCPConnector(ssl=False),
            headers=headers,
            raise_for_status=False,
        ) as session:
            form_data = aiohttp.FormData(
                quote_fields=False,
            )
            tmp_data = {}
            for i in small_items_to_upload:
                tmp_data[i["item_id"]] = io.StringIO()
                json.dump(
                    {"data": i["annotation"]}, tmp_data[i["item_id"]], allow_nan=False
                )
                tmp_data[i["item_id"]].seek(0)

            for key, data in tmp_data.items():
                form_data.add_field(
                    str(key),
                    data,
                    filename=str(key),
                    content_type="application/json",
                )
            response = await session.request("post", url, params=params, data=form_data)
            res_data = await response.json()
            failed_ids.extend([int(i) for i in res_data["failedItems"]])

    async def upload_small_annotations(
        self, project_id: int, folder_id: int, small_items_to_upload: List[dict]
    ):
        annotation_chunk_size = 10 * 1024 * 1024
        url_threshold = 4 * 1024 - 120
        chunk_count_limit = 5000
        list_of_chunks: List[List[dict]] = []
        chunk: List[dict] = []
        chunk_total_size = 0
        chunk_total_count = 0
        failed_ids: List[int] = []
        for item_to_upload in small_items_to_upload:
            annotation_chunk_size_reached = (
                chunk_total_size + item_to_upload["item_size"] >= annotation_chunk_size
            )
            uri_length_threshold_reached = (
                sum([len(str(item_to_upload["item_id"])) for item_to_upload in chunk])
                >= url_threshold - (len(chunk) + 1) * 14
            )
            if (
                annotation_chunk_size_reached
                or uri_length_threshold_reached
                or len(chunk) == chunk_count_limit
            ):
                list_of_chunks.append(chunk)
                chunk: List[dict] = []
                chunk_total_size = 0
                chunk_total_count = 0
            chunk.append(item_to_upload)
            chunk_total_size += item_to_upload["item_size"]
            chunk_total_count += 1
        if chunk:
            list_of_chunks.append(chunk)
        list_grouped_chunks = chunkify(list_of_chunks, 4)
        for chunks_group in list_grouped_chunks:
            await asyncio.gather(
                *[
                    self._upload_small_annotations(
                        project_id, folder_id, chunk, failed_ids
                    )
                    for chunk in chunks_group
                ]
            )
        return failed_ids

    async def _upload_large_annotation(
        self, project_id: int, folder_id: int, item: dict, failed_ids: List[int]
    ):
        chunk_size = 5 * 1024 * 1024
        buff = io.StringIO()
        json.dump(item["annotation"], buff, allow_nan=False)
        buff.seek(0)
        async with AIOHttpSession(
            connector=aiohttp.TCPConnector(ssl=False),
            headers=self._session.default_headers,
            raise_for_status=True,
        ) as session:
            params = {
                "team_id": self._session.team_id,
                "project_id": project_id,
                "folder_id": folder_id,
            }
            url = urljoin(
                self._session.assets_provider_url,
                self.URL_START_FILE_UPLOAD_PROCESS.format(item_id=item["item_id"]),
            )
            start_response = await session.request("post", url, params=params)
            process_info = await start_response.json()
            params["path"] = process_info["path"]
            headers = copy.copy(self._session.default_headers)
            headers["upload_id"] = process_info["upload_id"]
            chunk_id = 1
            data_sent = False
            while True:
                chunk = buff.read(chunk_size)
                params["chunk_id"] = chunk_id
                if chunk:
                    data_sent = True
                    await session.request(
                        "post",
                        urljoin(
                            self._session.assets_provider_url,
                            self.URL_START_FILE_SEND_PART.format(
                                item_id=item["item_id"]
                            ),
                        ),
                        params=params,
                        headers=headers,
                        data=json.dumps({"data_chunk": chunk}, allow_nan=False),
                    )
                    chunk_id += 1
                if not chunk and not data_sent:
                    failed_ids.extend(item["item_id"])
                if len(chunk) < chunk_size:
                    break
            del params["chunk_id"]
            await session.request(
                "post",
                urljoin(
                    self._session.assets_provider_url,
                    self.URL_START_FILE_SEND_FINISH.format(item_id=item["item_id"]),
                ),
                headers=headers,
                params=params,
            )
            del params["path"]
            await session.request(
                "post",
                urljoin(
                    self._session.assets_provider_url,
                    self.URL_START_FILE_SYNC.format(item_id=item["item_id"]),
                ),
                params=params,
                headers=headers,
            )
            while True:
                response = await session.request(
                    "get",
                    urljoin(
                        self._session.assets_provider_url,
                        self.URL_START_FILE_SYNC_STATUS.format(item_id=item["item_id"]),
                    ),
                    params=params,
                    headers=headers,
                )
                data = await response.json()
                status = data.get("status")
                if status == "SUCCESS":
                    break
                elif status.startswith("FAILED"):
                    failed_ids.extend(item["item_id"])
                    break
                await asyncio.sleep(15)
        return failed_ids

    async def upload_large_annotations(
        self, project_id: int, folder_id: int, large_items_to_upload: List[dict]
    ) -> List[int]:
        failed_ids: List[int] = []
        chunked_large_items_to_upload = chunkify(large_items_to_upload, 4)
        for chunk in chunked_large_items_to_upload:
            await asyncio.gather(
                *[
                    self._upload_large_annotation(
                        project_id, folder_id, item, failed_ids
                    )
                    for item in chunk
                ]
            )
        return failed_ids
