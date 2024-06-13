from typing import Any
from typing import List

from superannotate_core.core.entities.base import BaseEntity
from superannotate_core.core.enums import ClassTypeEnum
from superannotate_core.core.enums import GroupTypeEnum
from typing_extensions import TypedDict


class AttributeSchema(TypedDict, total=False):
    id: int
    group_id: int
    project_id: str
    name: str
    default: Any


class AttributeGroupSchema(TypedDict, total=False):
    id: int
    group_id: int
    class_id: int
    group_type: GroupTypeEnum
    name: str
    isRequired: bool
    attributes: List[AttributeSchema]
    default_value: Any


class AnnotationClassEntity(BaseEntity):
    id: int
    project_id: int
    type: ClassTypeEnum
    name: str
    color: str
    attribute_groups: List[AttributeGroupSchema]

    def __repr__(self):
        return (
            f"AnnotationClass(id={self.id}, project_id={self.project_id}, type={self.type}, name={self.name}, "
            f"color={self.color}, attribute_groups={[','.join(repr(i)) for i in self.attribute_groups]})"
        )
