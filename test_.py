import json

from superannotate_core.app import Project, Folder, Item
from superannotate_core.infrastructure.session import Session
from superannotate_core.infrastructure.repositories import AnnotationRepository

session = Session(
    team_id=32022,
    token="f5f34d28c0100c5dcc6805a965dc8c0a72bdcfe61ac14be808cb1abcec3f09e14677b5787900316ft=32022",
    api_url="https://api.devsuperannotate.com"
)


def test_():
    project_x = Project.get_by_id(project_id=704461, session=session)
    repo = AnnotationRepository(session=session)
    # small_annotations = asyncio.run(repo.download_small_annotations(
    #     project_id=project_x.id,
    #     folder_id=project_x.folder_id,
    #     item_ids=[30140645, 30697250],
    #     download_path='/Users/narekmkhitaryan/SuperAnnotate/superannotate-sdk-core/tmp_downloads',
    # ))
    # project_x.download_annotations(download_path="/Users/narekmkhitaryan/SuperAnnotate/superannotate-sdk-core/tmp_downloads")

    folder_x = Folder.get(project_id=project_x.id, pk=project_x.folder_id, session=session)
    # folder_x.get_annotations()
    folder_x._project = project_x
    # path = folder_x.download_annotations(download_path='/Users/narekmkhitaryan/SuperAnnotate/superannotate-sdk-core/tmp_downloads')

    small_annotation = json.load(open("/Users/narekmkhitaryan/SuperAnnotate/superannotate-python-sdk/tests/data_set/sample_vector_annotations_with_tag_classes/example_image_1.jpg___objects.json"))
    large_annotation = json.load(open("/Users/narekmkhitaryan/SuperAnnotate/superannotate-python-sdk/tests/data_set/sample_big_json_vector/aearth_mov_001.jpg.json"))
    res = folder_x.upload_annotations(
        annotations=[(48079872, large_annotation)],
    )
    print()