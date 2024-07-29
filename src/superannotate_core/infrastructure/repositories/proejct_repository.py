from typing import List

from superannotate_core.core.conditions import Condition
from superannotate_core.core.entities import ProjectEntity
from superannotate_core.infrastructure.repositories.base import BaseHttpRepository


class ProjectRepository(BaseHttpRepository):
    ENTITY = ProjectEntity
    URL_CREATE = "project"
    URL_LIST = "projects"
    URL_RETRIEVE = "project/{project_id}"

    def get_by_id(self, pk: int) -> ProjectEntity:
        response = self._session.request(
            self.URL_RETRIEVE.format(project_id=pk),
            "get",
        )
        response.raise_for_status()
        return self.serialize_entity(response.json())

    def list(self, condition: Condition) -> List[ProjectEntity]:
        data = self._session.paginate(
            url=self.URL_LIST,
            query_params=condition.get_as_params_dict() if condition else {},
        )
        return self.serialize_entity(data)

    def create(self, project: ProjectEntity) -> ProjectEntity:
        response = self._session.request(
            self.URL_CREATE, "post", json=project.to_json(exclude_none=True)
        )
        response.raise_for_status()
        return self.serialize_entity(response.json())

    def update(self, project: ProjectEntity) -> ProjectEntity:
        response = self._session.request(
            self.URL_RETRIEVE.format(project_id=project.id),
            "put",
            json=project.to_json(exclude_none=True),
        )
        response.raise_for_status()
        return self.serialize_entity(response.json())

    def delete(self, project_id: int) -> None:
        response = self._session.request(
            self.URL_RETRIEVE.format(project_id=project_id), "delete"
        )
        response.raise_for_status()
        return response.json()
