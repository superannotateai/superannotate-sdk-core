from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import TypedDict

from superannotate_core.core.exceptions import SAException
from superannotate_core.infrastructure.repositories.base import BaseRepositry


class UploadResponseSchema(TypedDict):
    succeeded_items: Optional[List[Any]]
    failed_items: Optional[List[str]]
    error: Optional[Any]


class CustomFieldRepository(BaseRepositry):
    URL_CREATE_CUSTOM_SCHEMA = "/project/{project_id}/custom/metadata/schema"
    URL_UPLOAD_CUSTOM_VALUE = "/project/{project_id}/custom/metadata/item"
    CHUNK_SIZE = 5000

    def create_fields(self, project_id: int, fields: dict) -> dict:
        response = self._session.request(
            self.URL_CREATE_CUSTOM_SCHEMA.format(project_id=project_id),
            "post",
            json={"data": fields},
        )
        if not response.ok:
            if response.status_code == 400:
                res_data = response.json()
                error = error = (
                    res_data["error"] if "error" in res_data else res_data["errors"]
                )
                if isinstance(error, list):
                    error = "-" + "\n-".join(error)
                raise SAException(error)
            else:
                response.raise_for_status()
        return response.json()

    def get_fields(self, project_id: int) -> dict:
        response = self._session.request(
            self.URL_CREATE_CUSTOM_SCHEMA.format(project_id=project_id), "get"
        )
        response.raise_for_status()
        return response.json()

    def delete_fields(self, project_id: int, field_names: List[str]):
        response = self._session.request(
            self.URL_CREATE_CUSTOM_SCHEMA.format(project_id=project_id),
            "delete",
            json={"custom_fields": field_names},
        )
        response.raise_for_status()

    def upload_fields(
        self,
        project_id: int,
        folder_id: int,
        item_name_fields_map: Dict[str, Dict],
    ) -> Tuple[List[str], List[str]]:
        """
        @return: tuple of succeeded and failed item names
        """
        failed_items = []
        for idx in range(0, len(item_name_fields_map), self.CHUNK_SIZE):
            response = self._session.request(
                self.URL_UPLOAD_CUSTOM_VALUE.format(project_id=project_id),
                "post",
                params={"folder_id": folder_id},
                json={"data": item_name_fields_map},
            )
            response.raise_for_status()
            failed_items.extend(response.json()["failed_items"])
        succeeded_items = list(item_name_fields_map.keys() ^ set(failed_items))
        return succeeded_items, failed_items

    def delete_values(
        self,
        project_id: int,
        folder_id: int,
        item_name_fields_map: Dict[str, List[str]],
    ):
        return self._session.request(
            self.URL_UPLOAD_CUSTOM_VALUE.format(project_id=project_id),
            "delete",
            params={"folder_id": folder_id},
            json={"data": item_name_fields_map},
        )
