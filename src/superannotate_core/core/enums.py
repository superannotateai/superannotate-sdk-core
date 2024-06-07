import typing
from enum import Enum, IntEnum
from types import DynamicClassAttribute


class classproperty:  # noqa
    def __init__(self, getter):
        self.getter = getter

    def __get__(self, instance, owner):
        return self.getter(owner)


ApprovalStatus = IntEnum("ApprovalStatus", {"None": 0, "Disapproved": 1, "Approved": 2})


class AnnotationTypes(str, Enum):
    BBOX = "bbox"
    EVENT = "event"
    POINT = "point"
    POLYGON = "polygon"
    POLYLINE = "polyline"


class ProjectType(IntEnum):
    Vector = 1
    Pixel = 2
    Video = 3
    Document = 4
    Tiled = 5
    Other = 6
    PointCloud = 7
    GenAI = 8
    UnsupportedType1 = 9
    UnsupportedType2 = 10

    @classproperty
    def images(self):
        return self.Vector, self.Pixel.value, self.Tiled.value


class UserRole(Enum):
    Superadmin = 1
    Admin = 2
    Annotator = 3
    QA = 4
    Customer = 5
    Viewer = 6


class UploadStateEnum(IntEnum):
    INITIAL = 1
    BASIC = 2
    EXTERNAL = 3


class ImageQuality(Enum):
    original = 100
    compressed = 60


class ProjectStatus(Enum):
    Undefined = -1
    NotStarted = 1
    InProgress = "InProgress", 2
    Completed = "Completed", 3
    OnHold = "OnHold", 4


class SegmentationStatus(IntEnum):
    NotStarted = 1
    InProgress = 2
    Completed = 3
    Failed = 4


class GroupTypeEnum(str, Enum):
    RADIO = "radio"
    CHECKLIST = "checklist"
    NUMERIC = "numeric"
    TEXT = "text"
    OCR = "ocr"


#
# class ClassTypeEnum(IntEnum):
#     object = 1
#     tag = 2
#     relationship = 3


class FolderStatus(IntEnum):
    Undefined = -1
    NotStarted = 1
    InProgress = 2
    Completed = 3
    OnHold = 4


class ExportStatus(Enum):
    inProgress = 1
    complete = 2
    canceled = 3
    error = 4


class AnnotationStatus(IntEnum):
    NotStarted = 1
    InProgress = 2
    QualityCheck = 3
    Returned = 4
    Completed = 5
    Skipped = 6


class ClassTypeEnum(IntEnum):
    object = 1
    tag = 2
    relationship = 3

    @classmethod
    def get_value(cls, name):
        for enum in list(cls):
            if enum.__doc__.lower() == name.lower():
                return enum.value
        return cls.object.value


class IntegrationTypeEnum(Enum):
    aws = 1
    gcp = 2
    azure = 3
    custom = 4
