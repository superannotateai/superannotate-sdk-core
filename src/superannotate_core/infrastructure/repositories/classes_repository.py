from typing import List

from superannotate_core.core.conditions import Condition
from superannotate_core.core.entities import AnnotationClassEntity
from superannotate_core.infrastructure.repositories.base import BaseHttpRepositry


class AnnotationClassesRepository(BaseHttpRepositry):
    ENTITY = AnnotationClassEntity
    URL_LIST = "classes"
    URL_GET = "class/{}"

    def bulk_create(
        self, project_id: int, classes: List[AnnotationClassEntity]
    ) -> List[AnnotationClassEntity]:
        params = {
            "project_id": project_id,
        }
        response = self._session.request(
            self.URL_LIST,
            "post",
            params=params,
            json={"classes": [i.to_json(exclude_none=True) for i in classes]},
        )
        response.raise_for_status()
        return self.serialize_entiy(response.json())

    def list(self, condition: Condition = None) -> List[AnnotationClassEntity]:
        return self._session.paginate(
            url=f"{self.URL_LIST}?{condition.build_query()}"
            if condition
            else self.URL_LIST,
        )

    def delete(self, project_id: int, annotation_class_id: int):
        return self._session.request(
            self.URL_GET.format(annotation_class_id),
            "delete",
            params={"project_id": project_id},
        )
