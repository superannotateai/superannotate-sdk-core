from typing import List
from typing import TypedDict

from superannotate_core.infrastructure.repositories.base import BaseRepositry


class SubsetSchema(TypedDict, total=False):
    id: int
    name: str


class SubsetRepository(BaseRepositry):
    URL_LIST = "/project/{project_id}/subset"
    URL_CREATE = "project/{project_id}/subset/bulk"
    URL_ADD_ITEMS_TO_SUBSET = "project/{project_id}/subset/{subset_id}/change"

    def list(self, project_id: int) -> List[SubsetSchema]:
        data = self._session.paginate(url=self.URL_LIST.format(project_id=project_id))
        return data

    def create_multiple(self, project_id: int, names: List[str]) -> List[SubsetSchema]:
        res = self._session.request(
            method="POST",
            url=self.URL_CREATE.format(project_id=project_id),
            json={"names": names},
        )
        res.raise_for_status()
        return res.json()

    def add_items(
        self,
        project_id: int,
        subset_id: int,
        item_ids: List[int],
    ):
        """
        :return: tuple with succeeded, skipped and failed items lists.
        :rtype: tuple
        """

        data = {"action": "ATTACH", "item_ids": item_ids}
        response = self._session.request(
            url=self.URL_ADD_ITEMS_TO_SUBSET.format(
                project_id=project_id, subset_id=subset_id
            ),
            method="POST",
            data=data,
        )
        if not response.ok:
            return [], item_ids, []
        else:
            data = response.json()
            successed = list(
                set(item_ids) - set(data["skipped"]).union(set(data["failed"]))
            )
            return successed, data["skipped"], data["failed"]
