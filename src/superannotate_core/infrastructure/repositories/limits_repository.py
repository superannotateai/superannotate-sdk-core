from typing import TypedDict

from superannotate_core.infrastructure.repositories.base import BaseRepositry


class Limit(TypedDict):
    max_image_count: int
    remaining_image_count: int


class UserLimits(TypedDict):
    user_limit: Limit
    project_limit: Limit
    folder_limit: Limit


class LimitsRepository(BaseRepositry):
    URL_GET_LIMITS = "project/{project_id}/limitationDetails"

    def get_limitations(self, project_id: int, folder_id) -> UserLimits:
        response = self._session.request(
            self.URL_GET_LIMITS.format(project_id=project_id),
            "get",
            params={"folder_id": folder_id},
        )
        response.raise_for_status()
        return response.json()
