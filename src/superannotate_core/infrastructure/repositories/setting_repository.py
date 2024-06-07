from typing import List

from superannotate_core.core.conditions import Condition
from superannotate_core.core.entities import Setting
from superannotate_core.infrastructure.repositories.base import BaseHttpRepositry


class SettingRepository(BaseHttpRepositry):
    URL_CREATE = "project"
    URL_LIST = "projects"
    URL_RETRIEVE = "project/{project_id}"

    def __init__(self, client, project_id: int):
        super().__init__(client)

        self._project_id = project_id

    def list(self, condition: Condition) -> List[Setting]:
        data = self._session.paginate(
            url=self.URL_LIST,
            query_params=condition.get_as_params_dict(),
        )
        return [Setting.from_json(i) for i in data]
