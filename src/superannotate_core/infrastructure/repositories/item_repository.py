import time
from typing import Dict
from typing import List
from typing import Tuple

from superannotate_core.core import constants
from superannotate_core.core.conditions import Condition
from superannotate_core.core.conditions import CONDITION_EQ as EQ
from superannotate_core.core.entities import BaseItemEntity
from superannotate_core.core.enums import AnnotationStatus
from superannotate_core.core.enums import ApprovalStatus
from superannotate_core.core.enums import UploadStateEnum
from superannotate_core.core.exceptions import SAValidationException
from superannotate_core.core.utils import chunkify
from superannotate_core.infrastructure.repositories.base import BaseHttpRepositry
from superannotate_core.infrastructure.repositories.limits_repository import (
    LimitsRepository,
)
from typing_extensions import TypedDict


class Attachment(TypedDict, total=False):
    name: str
    url: str
    integration: str
    integration_id: int


class AttachmentMeta(TypedDict, total=False):
    width: float
    height: float
    integration_id: int


class Polling:
    def __init__(self, project_id: int, polling_id: int, trashold: int):
        self.project_id = project_id
        self.polling_id = polling_id
        self.trashold = trashold
        self.cursor = 0

    def update(self, val: int):
        self.cursor += int(val)
        if self.is_finished():
            return 1
        else:
            return 0

    def is_finished(self):
        return self.cursor >= self.trashold


class ItemRepository(BaseHttpRepositry):
    ENTITY = BaseItemEntity
    CHUNK_SIZE = 2000
    ATTACH_CHUNK_SIZE = 500
    ASSIGN_CHUNK_SIZE = ATTACH_CHUNK_SIZE
    BACK_OFF_FACTOR = 0.3

    URL_LIST = "items"
    URL_ATTACH = "image/ext-create"
    URL_MOVE_MULTIPLE = "image/move"
    URL_GET_BY_ID = "image/{item_id}"
    URL_LIST_BY_NAMES = "images/getBulk"
    URL_DELETE_ITEMS = "image/delete/images"
    URL_LIST_BY_IDS = "images/getImagesByIds"
    URL_COPY_PROGRESS = "images/copy-image-progress"
    URL_SET_APPROVAL_STATUSES = "/items/bulk/change"
    URL_BULK_COPY_BY_NAMES = "images/copy-image-or-folders"
    URL_SET_ANNOTATION_STATUSES = "image/updateAnnotationStatusBulk"
    URL_ASSIGN_ITEMS = "images/editAssignment/"

    def _validate_limitations(
        self,
        project_id: int,
        folder_id: int,
        attachments_count: int,
        folder_limit=True,
        project_limit=True,
        user_limit=True,
    ):
        limits = LimitsRepository(self._session).get_limitations(
            project_id=project_id, folder_id=folder_id
        )
        if (
            folder_limit
            and attachments_count > limits["folder_limit"]["remaining_image_count"]
        ):
            raise SAValidationException(constants.ATTACH_FOLDER_LIMIT_ERROR_MESSAGE)
        elif (
            project_limit
            and attachments_count > limits["project_limit"]["remaining_image_count"]
        ):
            raise SAValidationException(constants.ATTACH_PROJECT_LIMIT_ERROR_MESSAGE)
        elif user_limit and (
            "user_limit" in limits
            and attachments_count > limits["user_limit"]["remaining_image_count"]
        ):
            raise SAValidationException(constants.ATTACH_USER_LIMIT_ERROR_MESSAGE)

    def get_by_id(
        self, project_id: int, folder_id: int, item_id: int
    ) -> BaseItemEntity:
        params = {"project_id": project_id, "folder_id": folder_id}
        response = self._session.request(
            self.URL_GET_BY_ID.format(item_id=item_id), "get", params=params
        )
        response.raise_for_status()
        return self.serialize_entiy(response.json())

    def list(self, condition: Condition = None) -> List[BaseItemEntity]:
        data = self._session.paginate(
            url=self.URL_LIST,
            chunk_size=self.CHUNK_SIZE,
            query_params=condition.get_as_params_dict() if condition else {},
        )
        return self.serialize_entiy(data)

    def update(self, project_id: int, item: BaseItemEntity):
        response = self._session.request(
            self.URL_GET_BY_ID.format(item.id),
            "put",
            data=item.dict(),
            params={"project_id": project_id},
        )
        return self.serialize_entiy(response.json())

    def list_by_ids(
        self,
        project_id: int,
        folder_id: int,
        ids: List[int],
    ):
        items = []
        for i in range(0, len(ids), self.CHUNK_SIZE):
            response = self._session.request(
                self.URL_LIST_BY_IDS,
                "post",
                json={
                    "image_ids": ids[i : i + self.CHUNK_SIZE],  # noqa
                },
                params={"project_id": project_id, "folder_id": folder_id},
            )
            response.raise_for_status()
            items.extend(response.json()["images"])
        return self.serialize_entiy(items)

    def list_by_names(
        self,
        project_id: int,
        folder_id: int,
        names: List[str],
    ):
        chunk_size = 200
        items = []
        for i in range(0, len(names), chunk_size):
            response = self._session.request(
                self.URL_LIST_BY_NAMES,
                "post",
                json={
                    "project_id": project_id,
                    "team_id": self._session.team_id,
                    "folder_id": folder_id,
                    "names": names[i : i + chunk_size],  # noqa
                },
            )
            response.raise_for_status()
            items.extend(response.json())
        return self.serialize_entiy(items)

    def attach(
        self,
        project_id: int,
        folder_id: int,
        attachments: List[Attachment],
        annotation_status: AnnotationStatus,
        upload_state: UploadStateEnum,
        meta: Dict[str, AttachmentMeta] = None,
    ) -> Tuple[List[str], List["str"]]:
        attached, duplicated = [], []
        self._validate_limitations(project_id, folder_id, len(attachments))

        for i in range(0, len(attachments), self.ATTACH_CHUNK_SIZE):
            _attachments = attachments[i : i + self.ATTACH_CHUNK_SIZE]
            existing_items = self.list_by_names(
                project_id=project_id,
                folder_id=folder_id,
                names=[attachment["name"] for attachment in _attachments],
            )
            duplicated.extend([image.name for image in existing_items])
            _data, _metadata = [], {}
            for _attachment in _attachments:
                if _attachment["name"] not in duplicated:
                    _data.append(
                        {"name": _attachment["name"], "path": _attachment["url"]}
                    )
                    _metadata[_attachment["name"]] = {
                        "width": None,
                        "height": None,
                        "_integration_id": _attachment.get("integration_id"),
                    }

            data = {
                "project_id": project_id,
                "folder_id": folder_id,
                "team_id": self._session.team_id,
                "images": _data,
                "annotation_status": annotation_status,
                "upload_state": upload_state,
                "meta": meta if meta else _metadata,
            }
            # todo define output
            response = self._session.request(self.URL_ATTACH, "post", json=data)
            if response.ok:
                attached.extend([i["name"] for i in _data])
        return attached, duplicated

    def bulk_copy_by_names(
        self,
        project_id: int,
        source_folder_id: int,
        destination_folder_id: int,
        item_names: List[str] = None,
        include_annotations: bool = False,
        include_pin: bool = False,
    ) -> List[str]:
        """
        Returns list of skipped item names.
        """
        skipped = set()  # skipped
        if not item_names:
            existing_item_names = [
                i.name
                for i in self.list(
                    Condition("project_id", project_id, EQ)
                    & Condition("folder_id", source_folder_id, EQ)
                )
            ]
        else:
            existing_item_names = [
                i.name
                for i in self.list_by_names(
                    project_id=project_id, folder_id=source_folder_id, names=item_names
                )
            ]
            skipped.update(set(item_names) - set(existing_item_names))
        for i in range(0, len(existing_item_names), self.ATTACH_CHUNK_SIZE):
            _item_names = existing_item_names[i : i + self.ATTACH_CHUNK_SIZE]
            existing_items = self.list_by_names(
                project_id=project_id,
                folder_id=destination_folder_id,
                names=[_item_name for _item_name in _item_names],
            )
            skipped.update({image.name for image in existing_items})
        items_to_copy = list(set(existing_item_names) - skipped)
        self._validate_limitations(
            project_id=project_id,
            folder_id=destination_folder_id,
            attachments_count=len(items_to_copy),
            user_limit=False,
        )
        for i in range(0, len(items_to_copy), self.ATTACH_CHUNK_SIZE):
            _item_names = items_to_copy[i : i + self.ATTACH_CHUNK_SIZE]
            response = self._session.request(
                self.URL_BULK_COPY_BY_NAMES,
                "post",
                params={"project_id": project_id},
                json={
                    "is_folder_copy": False,
                    "image_names": _item_names,
                    "destination_folder_id": destination_folder_id,
                    "source_folder_id": source_folder_id,
                    "include_annotations": include_annotations,
                    "keep_pin_status": include_pin,
                },
            )
            response.raise_for_status()
            polling = Polling(
                project_id=project_id,
                polling_id=response.json()["poll_id"],
                trashold=len(_item_names),
            )
            self.await_copy(polling)
        return list(skipped)

    def await_copy(self, polling: Polling):
        await_time = polling.trashold * 0.3
        timeout_start = time.time()
        while time.time() < timeout_start + await_time:
            response = self._session.request(
                self.URL_COPY_PROGRESS,
                "get",
                params={
                    "project_id": polling.project_id,
                    "poll_id": polling.polling_id,
                },
            )
            response.raise_for_status()
            data = response.json()
            done_count, skipped = data["done"], data["skipped"]
            polling.update(done_count)
            polling.update(skipped)
            if polling.is_finished():
                break
            time.sleep(4)
        return True

    def bulk_move_by_names(
        self,
        project_id: int,
        source_folder_id: int,
        destination_folder_id: int,
        item_names: List[str] = None,
    ) -> List[str]:
        if not item_names:
            item_names = [
                i.name
                for i in self.list(
                    Condition("project_id", project_id, EQ)
                    & Condition("folder_id", source_folder_id, EQ)
                )
            ]
        self._validate_limitations(
            project_id=project_id,
            folder_id=destination_folder_id,
            attachments_count=len(item_names),
            user_limit=False,
        )
        skipped = []
        for i in range(0, len(item_names), self.CHUNK_SIZE):
            response = self._session.request(
                self.URL_MOVE_MULTIPLE,
                "post",
                params={"project_id": project_id},
                json={
                    "image_names": item_names[i : i + self.CHUNK_SIZE],
                    "destination_folder_id": destination_folder_id,
                    "source_folder_id": source_folder_id,
                },
            )
            response.raise_for_status()
            skipped.extend(response.json()["skipped"])
        return skipped

    def set_statuses(
        self,
        project_id: int,
        folder_id: int,
        annotation_status: AnnotationStatus,
        item_names: List[str] = None,
    ):
        if not item_names:
            item_names = [
                i.name
                for i in self.list(
                    Condition("project_id", project_id, EQ)
                    & Condition("folder_id", folder_id, EQ)
                )
            ]
        response = self._session.request(
            self.URL_SET_ANNOTATION_STATUSES,
            "put",
            params={"project_id": project_id},
            json={
                "folder_id": folder_id,
                "annotation_status": annotation_status,
                "image_names": item_names,
            },
        )
        response.raise_for_status()

    def set_approval_statuses(
        self,
        project_id: int,
        folder_id: int,
        approval_status: ApprovalStatus,
        item_names: List[str] = None,
    ):
        if not item_names:
            item_names = [
                i.name
                for i in self.list(
                    Condition("project_id", project_id, EQ)
                    & Condition("folder_id", folder_id, EQ)
                )
            ]
        response = self._session.request(
            self.URL_SET_APPROVAL_STATUSES,
            "post",
            params={"project_id": project_id, "folder_id": folder_id},
            json={
                "item_names": item_names,
                "change_actions": {
                    "APPROVAL_STATUS": approval_status
                    if approval_status.value
                    else None
                },
            },
        )
        response.raise_for_status()

    def bulk_delete(self, project_id: int, folder_id: int, item_ids: List[int]):
        self._session.request(
            self.URL_DELETE_ITEMS,
            "put",
            params={"project_id": project_id, "folder_id": folder_id},
            data={"image_ids": item_ids},
        )
        return True

    def assign_items(
        self,
        project_id: int,
        folder_id: int,
        user_id: str,
        item_names: List[str],
    ) -> int:
        """
        Returns successed items count.
        """
        _count = 0
        for chunk in chunkify(item_names, self.ASSIGN_CHUNK_SIZE):
            response = self._session.request(
                self.URL_ASSIGN_ITEMS,
                "put",
                params={"project_id": project_id},
                data={
                    "image_names": chunk,
                    "assign_user_id": user_id,
                    "folder_id": folder_id,
                },
            )
            response.raise_for_status()
            _count += response.json()["successCount"]
        return _count

    def unassign_items(
        self,
        project_id: int,
        folder_id: int,
        item_names: List[str],
    ):
        for chunk in chunkify(item_names, self.ASSIGN_CHUNK_SIZE):
            response = self._session.request(
                self.URL_ASSIGN_ITEMS,
                "put",
                params={"project_id": project_id},
                data={
                    "image_names": chunk,
                    "remove_user_ids": ["all"],
                    "folder_id": folder_id,
                },
            )
            response.raise_for_status()
