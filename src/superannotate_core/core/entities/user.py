from typing_extensions import TypedDict

from superannotate_core.core.enums import UserRole


class ContributorEntity(TypedDict):
    first_name: str
    last_name: str
    user_id: str
    user_role: UserRole