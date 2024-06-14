from typing import List

from superannotate_core.core.conditions import Condition
from superannotate_core.core.entities import FolderEntity
from superannotate_core.infrastructure.repositories.base import BaseHttpRepositry


class FolderRepository(BaseHttpRepositry):
    ENTITY = FolderEntity
    URL_BASE = "folder"
    URL_LIST = "folders"
    URL_GET_BY_NAME = "folder/getFolderByName"
    URL_BULK_DELETE = "image/delete/images"
    URL_RETRIEVE = "folder/getFolderById/{folder_id}"
    URL_UPDATE = "folder/{folder_id}"
    URL_ASSIGN_FOLDER = "folder/editAssignment"

    def get_by_id(self, project_id: int, folder_id: int) -> FolderEntity:
        params = {"folder_id": folder_id, "project_id": project_id}
        response = self._session.request(self.URL_RETRIEVE, "get", params=params)
        response.raise_for_status()
        return self.serialize_entiy(response.json())

    def get_by_name(self, project_id: int, name: str):
        params = {"project_id": project_id, "name": name}
        response = self._session.request(self.URL_GET_BY_NAME, "get", params=params)
        response.raise_for_status()
        return self.serialize_entiy(response.json())

    def create(self, project_id: int, name: str):
        data = {"name": name}
        params = {"project_id": project_id}
        response = self._session.request(
            self.URL_BASE, "post", json=data, params=params
        )

        response.raise_for_status()
        return self.serialize_entiy(response.json())

    def list(self, condition: Condition) -> List[FolderEntity]:
        data = self._session.paginate(
            url=self.URL_LIST,
            query_params=condition.get_as_params_dict(),
        )
        return self.serialize_entiy(data)

    def update(self, entity: FolderEntity) -> FolderEntity:
        params = {"project_id": entity.project_id}
        response = self._session.request(
            self.URL_UPDATE.format(folder_id=entity.id),
            "put",
            json=entity.to_json(),
            params=params,
        )
        response.raise_for_status()
        return self.serialize_entiy(response.json())

    def bulk_delete(self, project_id: int, folder_ids: List[int]) -> None:
        params = {"project_id": project_id, "folder_ids": folder_ids}

        response = self._session.request(
            self.URL_BULK_DELETE, "put", json={"folder_ids": folder_ids}, params=params
        )
        response.raise_for_status()

    def assign(
        self,
        project_id: int,
        folder_name: str,
        users: List[str],
    ):
        response = self._session.request(
            self.URL_ASSIGN_FOLDER,
            "post",
            params={"project_id": project_id},
            data={"folder_name": folder_name, "assign_user_ids": users},
        )
        response.raise_for_status()

    def unsaaign(self, project_id: int, folder_id: int):
        response = self._session.request(
            self.URL_ASSIGN_FOLDER,
            "post",
            params={"project_id": project_id},
            data={"folder_id": folder_id, "remove_user_ids": ["all"]},
        )
        response.raise_for_status()
