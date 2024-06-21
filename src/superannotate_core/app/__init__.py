import asyncio
import logging
from functools import wraps
from operator import itemgetter
from pathlib import Path
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from requests import HTTPError
from superannotate_core.core import constants
from superannotate_core.core.conditions import Condition
from superannotate_core.core.conditions import CONDITION_EQ as EQ
from superannotate_core.core.conditions import EmptyCondition
from superannotate_core.core.entities import AnnotationClassEntity
from superannotate_core.core.entities import AttributeGroupSchema
from superannotate_core.core.entities import BaseItemEntity
from superannotate_core.core.entities import FolderEntity
from superannotate_core.core.entities import ImageEntity
from superannotate_core.core.entities import ProjectEntity
from superannotate_core.core.entities import ViedoEntity
from superannotate_core.core.enums import AnnotationStatus
from superannotate_core.core.enums import ApprovalStatus
from superannotate_core.core.enums import ClassTypeEnum
from superannotate_core.core.enums import FolderStatus
from superannotate_core.core.enums import ProjectType
from superannotate_core.core.enums import UploadStateEnum
from superannotate_core.core.exceptions import SAException
from superannotate_core.core.exceptions import SAInvalidInput
from superannotate_core.core.exceptions import SAValidationException
from superannotate_core.core.utils import chunkify
from superannotate_core.infrastructure.repositories import AnnotationClassesRepository
from superannotate_core.infrastructure.repositories import AnnotationRepository
from superannotate_core.infrastructure.repositories import FolderRepository
from superannotate_core.infrastructure.repositories import ItemRepository
from superannotate_core.infrastructure.repositories import ProjectRepository
from superannotate_core.infrastructure.repositories.item_repository import Attachment
from superannotate_core.infrastructure.repositories.item_repository import (
    AttachmentMeta,
)
from superannotate_core.infrastructure.repositories.utils import run_async
from superannotate_core.infrastructure.session import Session


logger = logging.getLogger(__name__)


def set_related_attribute(attr_name, many=False):
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            response = method(self, *args, **kwargs)
            if many:
                for i in response:
                    setattr(i, attr_name, self)
            else:
                setattr(response, attr_name, self)
            return response

        return wrapper

    return decorator


class Item(BaseItemEntity):
    @classmethod
    def attach(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        attachments: List[Attachment],
        annotation_status: AnnotationStatus,
        upload_state: UploadStateEnum,
        meta: Dict[str, AttachmentMeta] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        :return: uploaded and duplicated item names
        """
        return ItemRepository(session).attach(
            project_id=project_id,
            folder_id=folder_id,
            attachments=attachments,
            annotation_status=annotation_status,
            upload_state=upload_state,
            meta=meta,
        )

    @classmethod
    def get_by_id(
        cls, session: Session, project_id: int, folder_id, item_id: int
    ) -> "Item":
        _item = ItemRepository(session).get_by_id(
            project_id=project_id, folder_id=folder_id, item_id=item_id
        )
        return cls._from_entity(_item)

    @classmethod
    def get(
        cls,
        session,
        project_id: int,
        pk: Union[str, int],
        folder_id: int,
        include_custom_metadata=False,
    ):
        repo = ItemRepository(session)
        if isinstance(pk, int):
            item: BaseItemEntity = repo.get_by_id(
                project_id=project_id,
                folder_id=folder_id,
                item_id=pk,
            )
        elif isinstance(pk, str):
            if not folder_id:
                raise SAInvalidInput("To access iteam provide folder_id.")
            condition = (
                Condition("project_id", project_id, EQ)
                & Condition("folder_id", folder_id, EQ)
                & Condition("name", pk, EQ)
                & Condition("includeCustomMetadata", include_custom_metadata, EQ)
            )
            items = repo.list(condition)
            item: BaseItemEntity = next((i for i in items if i.name == pk), None)
        else:
            raise SAInvalidInput("Invalid primery key.")
        return cls._from_entity(item)

    @classmethod
    def list(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        *,
        condition: Condition = None,
        item_ids: List[int] = None,
        item_names: List[str] = None,
    ):
        repo = ItemRepository(session)
        _items = cls._list_items(
            repo,
            project_id,
            folder_id,
            item_ids=item_ids,
            item_names=item_names,
            condition=condition,
        )
        return [cls._from_entity(i) for i in _items]

    @classmethod
    def _list_items(
        cls,
        repo: ItemRepository,
        project_id: int,
        folder_id: int,
        *,
        item_ids: List[int] = None,
        item_names: List[str] = None,
        condition: Condition = None,
    ):
        if item_ids:
            _items = repo.list_by_ids(
                project_id=project_id, folder_id=folder_id, ids=item_ids
            )
        elif item_names:
            _items = repo.list_by_names(
                project_id=project_id, folder_id=folder_id, names=item_names
            )
        else:
            base_condition = Condition("project_id", project_id, EQ) & Condition(
                "folder_id", folder_id, EQ
            )
            if condition:
                base_condition = EmptyCondition if not condition else condition
                base_condition &= Condition("project_id", project_id, EQ)
                base_condition &= Condition("folder_id", folder_id, EQ)
            _items = repo.list(base_condition)
        return _items

    @classmethod
    async def alist_annotations(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        items: List[Union["BaseItemEntity", "Item", "VideoItem", "ImageItem"]],
    ):
        repo = AnnotationRepository(session)
        sort_response = AnnotationRepository(session=session).sort_annotations_by_size(
            project_id=project_id, folder_id=folder_id, item_ids=[i.id for i in items]
        )
        annotations = []

        large_item_ids = set(map(itemgetter("id"), sort_response["large"]))
        small_item_ids_chunks = []
        for chunk in sort_response["small"]:
            small_item_ids_chunks.append([i["id"] for i in chunk])

        large_items: List[BaseItemEntity] = list(
            filter(lambda item: item.id in large_item_ids, items)
        )
        if large_items:
            for chunk in chunkify(
                large_items, max(session.MAX_COROUTINE_COUNT // 2, 2)
            ):
                large_annotations = await asyncio.gather(
                    *[
                        cls.aget_large_annotation(
                            session=session,
                            project_id=project_id,
                            folder_id=folder_id,
                            item_id=item.id,
                        )
                        for item in chunk
                    ]
                )
                annotations.extend(large_annotations)
        if small_item_ids_chunks:
            for chunk in chunkify(small_item_ids_chunks, session.MAX_COROUTINE_COUNT):
                small_annotations = await asyncio.gather(
                    *[
                        repo.list_annotations(
                            project_id=project_id,
                            folder_id=folder_id,
                            item_ids=item_ids,
                        )
                        for item_ids in chunk
                    ]
                )
                for annotation_chunk in small_annotations:
                    annotations.extend(annotation_chunk)
        return annotations

    @classmethod
    async def _run_download_workers(
        cls,
        session: Session,
        large_items: List[BaseItemEntity],
        small_items: List[List[dict]],
        project_id: int,
        folder_id: int,
        download_path: Union[str, Path],
        annotation_repo: AnnotationRepository,
        callback: Callable = None,
    ):
        if large_items:
            for chunk in chunkify(
                large_items, max(session.MAX_COROUTINE_COUNT // 2, 2)
            ):
                tasks = []
                for item in chunk:
                    tasks.append(
                        annotation_repo.download_large_annotation(
                            project_id=project_id,
                            folder_id=folder_id,
                            item=item,
                            download_path=download_path,
                            callback=callback,
                        )
                    )
                await asyncio.gather(*tasks)

        if small_items:
            for chunks in chunkify(small_items, session.MAX_COROUTINE_COUNT):
                tasks = []
                for chunk in chunks:
                    tasks.append(
                        annotation_repo.download_small_annotations(
                            project_id=project_id,
                            folder_id=folder_id,
                            item_ids=[i["id"] for i in chunk],
                            download_path=download_path,
                            callback=callback,
                        )
                    )
                await asyncio.gather(*tasks)

    @classmethod
    async def adownload_annotations(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        items: List[Union["BaseItemEntity", "Item", "VideoItem", "ImageItem"]],
        download_path: Union[str, Path],
        callback: Callable = None,
    ):
        annotation_repo = AnnotationRepository(session)
        sort_response = annotation_repo.sort_annotations_by_size(
            project_id=project_id, folder_id=folder_id, item_ids=[i.id for i in items]
        )
        large_item_ids = set(map(itemgetter("id"), sort_response["large"]))
        large_items: List[BaseItemEntity] = list(
            filter(lambda item: item.id in large_item_ids, items)
        )
        small_items: List[List[dict]] = sort_response["small"]
        run_async(
            cls._run_download_workers(
                session,
                large_items,
                small_items,
                project_id,
                folder_id,
                download_path,
                annotation_repo,
                callback,
            )
        )

    @classmethod
    async def aget_large_annotation(
        cls, session: Session, project_id: int, folder_id: int, item_id: int
    ):
        repo = AnnotationRepository(session)
        return await repo.get_large_annotation(
            project_id=project_id, folder_id=folder_id, item_id=item_id
        )

    @classmethod
    def copy_items_by_names(
        cls,
        session: Session,
        project_id: int,
        source_folder_id: int,
        destination_folder_id: int,
        items: List[str],
        include_annotations=True,
    ) -> List[str]:
        skipped_item_namesa = ItemRepository(session).bulk_copy_by_names(
            project_id=project_id,
            source_folder_id=source_folder_id,
            destination_folder_id=destination_folder_id,
            item_names=items,
            include_annotations=include_annotations,
        )
        return skipped_item_namesa

    @classmethod
    def move_items_by_names(
        cls,
        session: Session,
        project_id: int,
        source_folder_id: int,
        destination_folder_id: int,
        items: List[str],
    ) -> List[str]:
        return ItemRepository(session).bulk_move_by_names(
            project_id=project_id,
            source_folder_id=source_folder_id,
            destination_folder_id=destination_folder_id,
            item_names=items,
        )

    @classmethod
    def bulk_set_annotation_status(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        annotation_status: AnnotationStatus,
        items: List[str] = None,
    ):
        ItemRepository(session).set_statuses(
            project_id=project_id,
            folder_id=folder_id,
            annotation_status=annotation_status,
            item_names=items,
        )

    @classmethod
    def bulk_set_approval_status(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        approval_status: ApprovalStatus,
        items: List[str] = None,
    ):
        ItemRepository(session).set_approval_statuses(
            project_id=project_id,
            folder_id=folder_id,
            approval_status=approval_status,
            item_names=items,
        )

    @classmethod
    def bulk_delete(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        *,
        item_ids: List[int],
        item_names: List[str] = None,
    ):
        repo = ItemRepository(session)

        if not item_ids:
            item_ids = [
                i.id
                for i in cls._list_items(
                    repo,
                    project_id,
                    folder_id,
                    item_ids=item_ids,
                    item_names=item_names,
                )
            ]
            if item_ids:
                repo.bulk_delete(
                    project_id=project_id, folder_id=folder_id, item_ids=item_ids
                )

    @classmethod
    def bulk_assign(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        user: str,
        *,
        condition: Condition = None,
        item_ids: List[int] = None,
        item_names: List[str] = None,
    ) -> int:
        """
        Returns successed items count.
        """

        repo = ItemRepository(session=session)
        if not item_names and (condition or item_ids):
            _items = cls._list_items(
                repo,
                project_id=project_id,
                folder_id=folder_id,
                condition=condition,
                item_ids=item_ids,
            )
            item_names = [i.name for i in _items]
        count = repo.assign_items(
            project_id=project_id,
            folder_id=folder_id,
            item_names=item_names,
            user_id=user,
        )
        return count

    @classmethod
    def bulk_unassign(
        cls,
        session: Session,
        project_id: int,
        folder_id: int,
        *,
        condition: Condition = None,
        item_ids: List[int] = None,
        item_names: List[str] = None,
    ) -> int:
        repo = ItemRepository(session=session)
        if not item_names and (condition or item_ids):
            _items = cls._list_items(
                repo,
                project_id=project_id,
                folder_id=folder_id,
                condition=condition,
                item_ids=item_ids,
            )
            item_names = [i.name for i in _items]
        count = repo.unassign_items(
            project_id=project_id,
            folder_id=folder_id,
            item_names=item_names,
        )
        return count


class ImageItem(Item, ImageEntity):
    ...


class VideoItem(Item, ViedoEntity):
    ...


PROJECT_ITEM_MAP = {
    ProjectType.Vector: ImageItem,
    ProjectType.Pixel: ImageItem,
    ProjectType.Video: VideoItem,
    ProjectType.Tiled: ImageItem,
    ProjectType.Document: ImageItem,
}


class AnnotationClass(AnnotationClassEntity):
    @classmethod
    def bulk_create(
        cls,
        session: Session,
        project_id: int,
        annotation_classes: List["AnnotationClassEntity"],
    ):
        try:
            _annotation_classes = AnnotationClassesRepository(session).bulk_create(
                project_id, annotation_classes
            )
            return [cls._from_entity(i) for i in _annotation_classes]
        except HTTPError as e:
            raise SAException(e.response.json()["error"])


class Folder(FolderEntity):
    def __init__(self, /, **data):
        project: Optional[Project] = data.pop("project", None)
        super().__init__(**data)
        self._project = project

    class Meta:
        NAME_MAX_LENGTH = 80
        SPECIAL_CHARACTERS = set('/\\:*?"<>|“')

    @property
    def project(self):
        if hasattr(self, "_project") and self._project:
            return self._project
        raise AttributeError(
            """
            To access data through the folder you have to access the folder through the project
            Project.get_by_id(1).get_folder(1).list_items()
            """
        )

    @project.setter
    def project(self, v):
        self._project = v

    def get_item(self, pk: Union[str, int], include_custom_metadata=False):
        _item = PROJECT_ITEM_MAP[self.project.type]
        return _item.get(
            self.session,
            project_id=self.project_id,
            folder_id=self.id,
            pk=pk,
            include_custom_metadata=include_custom_metadata,
        )

    def attach_items(
        self,
        attachments: List[Attachment],
        annotation_status: AnnotationStatus,
        meta: Dict[str, AttachmentMeta] = None,
    ) -> Tuple[List[str], List[str]]:
        if self.project.upload_state == UploadStateEnum.BASIC:
            raise SAValidationException(constants.ATTACHING_UPLOAD_STATE_ERROR)
        return Item.attach(
            self.session,
            project_id=self.project_id,
            folder_id=self.id,
            attachments=attachments,
            annotation_status=annotation_status,
            upload_state=UploadStateEnum.EXTERNAL,
            meta=meta,
        )

    def list_items(
        self,
        *,
        condition: Condition = None,
        item_ids: List[int] = None,
        item_names: List[str] = None,
    ) -> List[Union[BaseItemEntity, Item, VideoItem, ImageItem]]:
        _item = PROJECT_ITEM_MAP[self.project.type]
        return _item.list(
            self.session,
            project_id=self.project_id,
            folder_id=self.id,
            condition=condition,
            item_ids=item_ids,
            item_names=item_names,
        )

    def delete_items(self, *, item_ids: List[int] = None, item_names: List[str] = None):
        _item = PROJECT_ITEM_MAP[self.project.type]
        _item.bulk_delete(
            self.session,
            project_id=self.project_id,
            folder_id=self.id,
            item_ids=item_ids,
            item_names=item_names,
        )

    def get_annotations(
        self,
        *,
        condition: Condition = None,
        item_ids: List[int] = None,
        item_names: List[str] = None,
    ) -> List[dict]:
        items = self.list_items(
            condition=condition, item_ids=item_ids, item_names=item_names
        )
        annotations = []
        if items:
            annotations = run_async(
                Item.alist_annotations(
                    session=self.session,
                    project_id=self.project_id,
                    folder_id=self.id,
                    items=items,
                )
            )
        if item_names:
            #  keeping the same order
            name_to_index = {name: index for index, name in enumerate(item_names)}
            annotations = list(
                sorted(annotations, key=lambda x: name_to_index[x["metadata"]["name"]])
            )
        return annotations

    def download_annotations(
        self,
        download_path: Union[Path, str],
        *,
        condition: Condition = None,
        item_ids: List[int] = None,
        item_names: List[str] = None,
        callback: Callable = None,
    ):
        items = self.list_items(
            condition=condition, item_ids=item_ids, item_names=item_names
        )
        if items:
            run_async(
                Item.adownload_annotations(
                    session=self.session,
                    project_id=self.project_id,
                    folder_id=self.id,
                    items=items,
                    download_path=download_path,
                    callback=callback,
                )
            )

    def copy_items_by_name(
        self,
        destination_folder_id: int,
        items: List[str],
        include_annotations=True,
    ) -> List[str]:
        return Item.copy_items_by_names(
            self.session,
            project_id=self.project_id,
            source_folder_id=self.id,
            destination_folder_id=destination_folder_id,
            items=items,
            include_annotations=include_annotations,
        )

    def move_items_by_name(
        self, destination_folder_id: int, items: List[str]
    ) -> List[str]:
        return Item.move_items_by_names(
            self.session,
            project_id=self.project_id,
            source_folder_id=self.id,
            destination_folder_id=destination_folder_id,
            items=items,
        )

    def set_items_annotation_statuses(
        self, items: List[str], annotation_status: AnnotationStatus
    ):
        Item.bulk_set_annotation_status(
            session=self.session,
            project_id=self.project_id,
            folder_id=self.id,
            items=items,
            annotation_status=annotation_status,
        )

    def set_items_approval_statuses(
        self, items: List[str], approval_status: ApprovalStatus
    ):
        Item.bulk_set_approval_status(
            session=self.session,
            project_id=self.project_id,
            folder_id=self.id,
            items=items,
            approval_status=approval_status,
        )

    def assign(self, users: List[str]):
        _users = self.project.users
        verified_users = {i["user_id"] for i in _users}
        intersection = set(users).intersection(set(verified_users))
        unverified_contributor = set(users) - verified_users
        if unverified_contributor:  # todo update error message
            logger.warning(
                f"Skipping not a verified {','.join(unverified_contributor)} from assignees."
            )
        if intersection:
            FolderRepository(session=self._session).assign(
                project_id=self.project_id, folder_name=self.name, users=users
            )

    def unassign(self):
        FolderRepository(session=self._session).unsaaign(
            project_id=self.project_id,
            folder_id=self.id,
        )

    def assign_items(
        self,
        user: str,
        *,
        condition: Condition = None,
        item_names: List[str],
        item_ids: List[int],
    ):
        Item.bulk_assign(
            session=self.session,
            project_id=self.project_id,
            folder_id=self.id,
            user=user,
            condition=condition,
            item_names=item_names,
            item_ids=item_ids,
        )

    def unassign_items(
        self,
        *,
        condition: Condition = None,
        item_names: List[str] = None,
        item_ids: List[int] = None,
    ):
        Item.bulk_unassign(
            session=self.session,
            project_id=self.project_id,
            folder_id=self.id,
            condition=condition,
            item_names=item_names,
            item_ids=item_ids,
        )

    @classmethod
    def _clean_folder_name(cls, val: str):
        intersection = set(val).intersection(cls.Meta.SPECIAL_CHARACTERS)
        if len(intersection) > 0:
            val = "".join(
                "_" if char in cls.Meta.SPECIAL_CHARACTERS else char for char in val
            )
            logger.warning(
                "New folder name has special characters. Special characters will be replaced by underscores."
            )
        if len(val) > cls.Meta.NAME_MAX_LENGTH:
            raise SAValidationException(
                "The folder name is too long. The maximum length for this field is 80 characters."
            )
        return val

    @classmethod
    def get(cls, session: Session, project_id: int, pk: Union[str, int]):
        if isinstance(pk, int):
            return cls._from_entity(
                FolderRepository(session).get_by_id(project_id=project_id, folder_id=pk)
            )
        elif isinstance(pk, str):
            condition = Condition("project_id", project_id, EQ) & Condition(
                "namne", pk, EQ
            )
            repo = FolderRepository(session)
            folder = next(
                (cls._from_entity(i) for i in repo.list(condition) if i.name == pk),
                None,
            )
            if not folder:
                raise SAInvalidInput("Folder not found.")
            return folder
        else:
            raise SAInvalidInput("Invalid primary key.")

    # todo delete
    @classmethod
    def get_by_id(cls, session: Session, project_id: int, folder_id: int):
        return cls._from_entity(
            FolderRepository(session).get_by_id(
                project_id=project_id, folder_id=folder_id
            )
        )

    # todo delete
    @classmethod
    def get_by_name(cls, session: Session, project_id: int, name: str) -> "Folder":
        condition = Condition("project_id", project_id, EQ) & Condition(
            "namne", name, EQ
        )
        repo = FolderRepository(session)
        folder = next(
            (cls._from_entity(i) for i in repo.list(condition) if i.name == name), None
        )
        if not folder:
            raise SAInvalidInput("Folder not found.")
        return folder

    @classmethod
    def create(cls, session: Session, project_id: int, name: str):
        name = cls._clean_folder_name(name)
        return FolderRepository(session).create(project_id=project_id, name=name)

    @classmethod
    def list(cls, session: Session, condition: Condition):
        return [cls._from_entity(i) for i in FolderRepository(session).list(condition)]

    @classmethod
    def delete_folders(cls, session: Session, project_id: int, names: List[str]) -> int:
        repo = FolderRepository(session)
        existing_folders = repo.list(Condition("project_id", project_id, EQ))
        to_delete = []
        for folder in existing_folders:
            if folder.name in names:
                to_delete.append(folder.id)
        if to_delete:
            FolderRepository(session).bulk_delete(
                project_id=project_id, folder_ids=to_delete
            )
        return len(to_delete)

    @classmethod
    def update_folder(cls, session: Session, folder: "Folder") -> "Folder":
        return cls._from_entity(FolderRepository(session).update(folder))


class Project(ProjectEntity):
    @classmethod
    def get_by_id(cls, session, project_id):
        return cls._from_entity(ProjectRepository(session).get_by_id(project_id))

    @classmethod
    def get(cls, session: Session, pk: Union[str, int]) -> "Project":
        if isinstance(pk, int):
            project = cls._from_entity(ProjectRepository(session).get_by_id(pk))
        elif isinstance(pk, str):
            projects = cls.list(session, condition=Condition("name", pk, EQ))
            project = next(
                (project for project in projects if project.name == pk),
                None,
            )
            if not project:
                raise SAInvalidInput("Project not found.")
        else:
            raise SAInvalidInput("Invalid primery key.")
        return cls._from_entity(project)

    def get_item(self, pk: Union[str, int], include_custom_metadata=False):
        _item = PROJECT_ITEM_MAP[self.type]
        # TODO fix missing folder_id arg
        return _item.get(
            self.session,
            project_id=self.id,
            pk=pk,
            include_custom_metadata=include_custom_metadata,
        )

    @classmethod
    def create(cls, session, **data) -> "Project":
        return cls._from_entity(
            ProjectRepository(session).create(ProjectEntity(**data))
        )

    def create_folder(self, name: str) -> Folder:
        return Folder.create(self.session, project_id=self.id, name=name)

    def delete_folders(self, folder_names: List[str]) -> int:
        return Folder.delete_folders(
            self.session, project_id=self.id, names=folder_names
        )

    def set_folder_status(self, folder_name: str, status: FolderStatus) -> Folder:
        folder = Folder.get_by_name(self.session, self.id, folder_name)
        folder.status = status
        return Folder.update_folder(self.session, folder)

    @classmethod
    def list(cls, session: Session, condition: Condition) -> List["Project"]:
        return [cls._from_entity(i) for i in ProjectRepository(session).list(condition)]

    @set_related_attribute("project", many=True)
    def list_folders(self, condition: Condition = None) -> List[Folder]:
        if condition is None:
            condition = EmptyCondition()
        condition &= Condition("project_id", self.id, EQ)
        return Folder.list(self.session, condition)

    def download_annotations(
        self,
        download_path: Union[Path, str],
        *,
        condition: Condition = None,
        item_ids: List[int] = None,
        item_names: List[str] = None,
        callback: Callable = None,
    ):
        folders = self.list_folders()  # TODO check
        for folder in folders:
            current_download_path = download_path
            if not folder.is_root:
                current_download_path += f"/{folder.name}"
            folder.download_annotations(
                condition=condition,
                item_ids=item_ids,
                item_names=item_names,
                download_path=current_download_path,
                callback=callback,
            )

    @set_related_attribute("project")
    def get_folder(self, pk: Union[str, int]):
        if isinstance(pk, int):
            return Folder.get_by_id(self.session, project_id=self.id, folder_id=pk)
        elif isinstance(pk, str):
            if not pk:
                pk = "root"
            return Folder.get_by_name(self.session, self.id, pk)
        else:
            raise SAInvalidInput("Invalid primery key.")

    def create_annotation_class(
        self,
        name: str,
        class_type: ClassTypeEnum,
        color: str,
        attribute_groups: List[AttributeGroupSchema],
    ):
        payload = {
            "name": name,
            "type": class_type,
            "color": color,
            "attribute_groups": attribute_groups,
        }
        response = AnnotationClass.bulk_create(
            self.session, self.id, [AnnotationClass.from_json(payload)]
        )
        return response[0]

    def create_annotation_classes(self, annotation_classes: List[dict]):
        annotation_classes_prepared = [
            AnnotationClass.from_json(i) for i in annotation_classes
        ]
        return AnnotationClass.bulk_create(
            self.session, self.id, annotation_classes_prepared
        )
