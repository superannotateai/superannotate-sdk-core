from typing import List

from superannotate_core.core.conditions import Condition
from superannotate_core.core.entities import SettingEntity
from superannotate_core.infrastructure.repositories.base import BaseHttpRepository


class SettingRepository(BaseHttpRepository):
    ENTITY = SettingEntity
    URL_SETTINGS = "project/{}/settings"

    def list(self, project_id: int, condition: Condition = None) -> List[SettingEntity]:
        response = self._session.paginate(
            self.URL_SETTINGS.format(project_id),
            query_params=condition.get_as_params_dict() if condition else None,
        )
        return self.serialize_entity(response)

    def set_settings(
        self, project_id: int, settings: List[SettingEntity]
    ) -> List[SettingEntity]:
        response = self._session.request(
            self.URL_SETTINGS.format(project_id),
            "put",
            json={
                "settings": [
                    SettingEntity.to_json(setting, exclude_none=True)
                    for setting in settings
                ]
            },
        )
        response.raise_for_status()
        return self.serialize_entity(response.json())
