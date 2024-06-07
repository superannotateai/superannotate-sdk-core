from typing import List

from superannotate_core.core.conditions import Condition
from superannotate_core.core.entities import ProjectEntity
from superannotate_core.infrastructure.repositories.base import BaseHttpRepositry


class ProjectRepository(BaseHttpRepositry):
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
        return self.serialize_entiy(response.json())

    def list(self, condition: Condition) -> List[ProjectEntity]:
        data = self._session.paginate(
            url=self.URL_LIST,
            query_params=condition.get_as_params_dict() if condition else {},
        )
        return self.serialize_entiy(data)

    def create(self, entity: ProjectEntity) -> ProjectEntity:
        response = self._session.request(
            self.URL_CREATE, "post", data=entity.to_json()
        )
        response.raise_for_status()
        return self.serialize_entiy(response.json())

    def update(self, entity: ProjectEntity) -> ProjectEntity:
        response = self._session.request(
            self.URL_RETRIEVE.format(entity.id),
            "put",
            data=entity.to_json(),
        )
        response.raise_for_status()
        return self.serialize_entiy(response.json())

    def delete(self, pk: int) -> None:
        return self._session.request(self.URL_RETRIEVE.format(pk), "delete")