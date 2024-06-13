import asyncio
from typing import Callable
from typing import Iterable
from typing import List
from urllib.parse import urljoin

import aiohttp
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

    def sort_annotatoins_by_size(
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
            large=[i["data"] for i in data.get("small", {}).values()],
            small=data.get("large", []),
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
        url = urljoin(self._session.assets_provider_url, self.URL_GET_ANNOTATIONS)
        query_params = {
            "project_id": project_id,
            "folder_id": folder_id,
            "annotation_type": "MAIN",
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
