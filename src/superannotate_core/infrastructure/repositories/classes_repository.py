import json
from typing import List

from superannotate_core.core.conditions import Condition
from superannotate_core.core.entities import AnnotationClassEntity
from superannotate_core.core.utils import chunkify
from superannotate_core.infrastructure.repositories.base import BaseHttpRepository


class AnnotationClassesRepository(BaseHttpRepository):
    ENTITY = AnnotationClassEntity
    URL_LIST = "classes"
    URL_GET = "class/{}"
    CHUNK_SIZE = 500

    def bulk_create(
        self, project_id: int, classes: List[AnnotationClassEntity]
    ) -> List[AnnotationClassEntity]:
        params = {
            "project_id": project_id,
        }
        chunked_classes = chunkify(classes, self.CHUNK_SIZE)

        created_classes: List[AnnotationClassEntity] = []
        for chunk in chunked_classes:
            # TODO backend return empty [] if class already exist, discus it
            response = self._session.request(
                self.URL_LIST,
                "post",
                params=params,
                json={"classes": [i.to_json(exclude_none=True) for i in chunk]},
            )
            response.raise_for_status()
            created_classes.extend(self.serialize_entity(response.json()))
        return created_classes

    def list(
        self, project_id: int, condition: Condition = None
    ) -> List[AnnotationClassEntity]:
        params = {
            "project_id": project_id,
        }
        classes = self._session.paginate(
            url=f"{self.URL_LIST}?{condition.build_query()}"
            if condition
            else self.URL_LIST,
            query_params=params,
        )
        return self.serialize_entity(classes)

    def delete(self, project_id: int, annotation_class_id: int):
        response = self._session.request(
            self.URL_GET.format(annotation_class_id),
            "delete",
            params={"project_id": project_id},
        )
        return self.serialize_entity(response.json())

    def download(self, project_id: int, path: str, condition: Condition = None):
        classes = [entity.dict() for entity in self.list(project_id, condition)]
        classes_json_path = f"{path}/classes.json"
        with open(classes_json_path, "w", encoding="utf-8") as file:
            json.dump(classes, file, indent=4)
        return classes_json_path
