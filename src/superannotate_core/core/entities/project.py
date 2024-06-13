from __future__ import annotations

from typing import Any
from typing import List

from superannotate_core.core.entities.base import AliasHandler
from superannotate_core.core.entities.base import BaseEntity
from superannotate_core.core.entities.user import ContributorEntity
from superannotate_core.core.enums import ProjectStatus
from superannotate_core.core.enums import ProjectType


class FolderEntity(BaseEntity):
    id: int
    project_id: int
    name: str
    status: int
    team_id: int
    is_root: bool
    folder_users: List[dict]
    completedCount: int

    def __repr__(self):
        return (
            f"Folder(id={self.id}, team_id={self.team_id}, project_id={self.project_id}, name={self.name}, "
            f"status={self.status}, is_root={self.is_root}, "
            f"folder_users={self.folder_users}, completedCount={self.completedCount})"
        )


class Setting(BaseEntity):
    id: int
    project_id: int
    attribute: str
    value: Any

    def __repr__(self):
        return (
            f"Setting(id={self.id}, project_id={self.project_id}, "
            f"attribute={self.attribute}, value={self.value}, "
        )


class ProjectEntity(BaseEntity):
    id: int
    team_id: int
    name: str
    type: ProjectType
    description: str
    instructions_link: str
    creator_id: str
    entropy_status: int
    sharing_status: int
    status: ProjectStatus
    folder_id: int
    sync_status: int
    upload_state: int
    users: List[ContributorEntity]

    class Meta:
        alias_handler = AliasHandler(
            {
                "imageCount": "item_count",
                "completedImagesCount": "completed_images_count",
                "rootFolderCompletedImagesCount": "root_folder_completed_images_count",
            }
        )

    def __repr__(self):
        return (
            f"Project(id={self.id}, team_id={self.team_id}, name={self.name}, "
            f"type={self.type}, description={self.description}, "
            f"instructions_link={self.instructions_link}, creator_id={self.creator_id}, "
            f"entropy_status={self.entropy_status}, sharing_status={self.sharing_status}, "
            f"status={self.status}, folder_id={self.folder_id}, sync_status={self.sync_status}, "
            f"upload_state={self.upload_state}, users={self.users}"
        )
