from typing import List

from superannotate_core.core.conditions import Condition
from superannotate_core.core.entities import SettingEntity
from superannotate_core.infrastructure.repositories.base import BaseHttpRepository


class SettingRepository(BaseHttpRepository):
    URL_CREATE = "project"
    URL_LIST = "projects"
    URL_RETRIEVE = "project/{project_id}"

    def __init__(self, client, project_id: int):
        super().__init__(client)

        self._project_id = project_id

    def list(self, condition: Condition) -> List[SettingEntity]:
        data = self._session.paginate(
            url=self.URL_LIST,
            query_params=condition.get_as_params_dict(),
        )
        return [SettingEntity.from_json(i) for i in data]
