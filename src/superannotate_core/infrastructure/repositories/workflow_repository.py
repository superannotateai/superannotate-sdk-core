from typing import List

from superannotate_core.core.entities.project import WorkflowEntity
from superannotate_core.infrastructure.repositories.base import BaseHttpRepository


class WorkflowRepository(BaseHttpRepository):
    ENTITY = WorkflowEntity
    URL_WORKFLOW_LIST = "project/{}/workflow"
    URL_WORKFLOW_ATTRIBUTE = "project/{}/workflow_attribute"

    def list_workflows(self, project_id: int):
        response = self._session.paginate(self.URL_WORKFLOW_LIST.format(project_id))
        return self.serialize_entity(response)

    def set_workflow(self, project_id: int, workflow: WorkflowEntity):
        return self._session.request(
            self.URL_WORKFLOW_LIST.format(project_id),
            "post",
            json={"steps": [WorkflowEntity.to_json(workflow, exclude_none=True)]},
        )

    def set_workflows(self, project_id: int, workflows: List[WorkflowEntity]):
        workflows = [WorkflowEntity.to_json(s, exclude_none=False) for s in workflows]
        response = self._session.request(
            self.URL_WORKFLOW_LIST.format(project_id),
            "post",
            json={"steps": workflows},
        )
        response.raise_for_status()
        return self.serialize_entity(response.json())

    def set_project_workflow_attributes(self, project_id: int, attributes: List[dict]):
        return self._session.request(
            self.URL_WORKFLOW_ATTRIBUTE.format(project_id),
            "post",
            json={"data": attributes},
        )
