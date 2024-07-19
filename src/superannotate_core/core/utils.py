import io
import json
import time

from superannotate_core.core.enums import ProjectType


def chunkify(lst, n):
    """Divide the list `lst` into chunks of size `n`."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def set_annotation_defaults(
    user_id, annotation_data: dict, project_type: ProjectType
) -> dict:
    default_data = {}
    annotation_data["metadata"]["lastAction"] = {
        "email": user_id,
        "timestamp": int(round(time.time() * 1000)),
    }
    instances = annotation_data.get("instances", [])
    if project_type in ProjectType.images:
        default_data["probability"] = 100

    if project_type == ProjectType.Video:
        for instance in instances:
            instance["meta"] = {
                **default_data,
                **instance["meta"],
                "creationType": "Preannotation",  # noqa
            }
    else:
        for idx, instance in enumerate(instances):
            instances[idx] = {
                **default_data,
                **instance,
                "creationType": "Preannotation",  # noqa
            }
    return annotation_data


def get_dict_size(data: dict) -> int:
    file = io.BytesIO()
    file.write(json.dumps(data).encode())
    file.seek(0)
    return file.getbuffer().nbytes


def get_clean_priority(priority: float):
    if len(str(priority)) > 8:
        priority = float(str(priority)[:8])
    if priority > 1000000:
        priority = 1000000
    if priority < 0:
        priority = 0
    if str(float(priority)).split(".")[1:2]:
        if len(str(float(priority)).split(".")[1]) > 5:
            priority = float(
                str(float(priority)).split(".")[0]
                + "."
                + str(float(priority)).split(".")[1][:5]
            )
    return priority
