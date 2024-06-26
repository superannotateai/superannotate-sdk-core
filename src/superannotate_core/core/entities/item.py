from __future__ import annotations

from superannotate_core.core.entities.base import Extra
from superannotate_core.core.entities.base import TimedEntity
from superannotate_core.core.enums import AnnotationStatus
from superannotate_core.core.enums import ApprovalStatus
from superannotate_core.core.enums import SegmentationStatus


class BaseItemEntity(TimedEntity):
    id: int
    name: str
    path: str  # Item’s path in SuperAnnotate project
    url: str  # Publicly available HTTP address
    annotator_email: str
    qa_email: str
    annotation_status: AnnotationStatus
    entropy_value: float  # Priority score of given item todo check
    custom_metadata: dict

    class Meta:
        extra = Extra.ALLOW


class ImageEntity(BaseItemEntity):
    prediction_status: SegmentationStatus
    segmentation_status: SegmentationStatus
    approval_status: ApprovalStatus
    is_pinned: bool
    meta: dict


class ViedoEntity(BaseItemEntity):
    approval_status: ApprovalStatus


class DocumentEntity(BaseItemEntity):
    approval_status: ApprovalStatus


class TiledEntity(BaseItemEntity):
    ...


class ClassificationEntity(BaseItemEntity):
    ...


class PointCloudEntity(BaseItemEntity):
    ...
