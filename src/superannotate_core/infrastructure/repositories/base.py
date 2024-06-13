from abc import ABC
from typing import List
from typing import Union


class BaseRepositry(ABC):
    def __init__(self, session):
        self._session = session


class BaseHttpRepositry(BaseRepositry):
    def serialize_entiy(self, data: Union[List[dict], dict]):
        entitiy_class = getattr(self, "ENTITY")
        if not entitiy_class:
            raise Exception("Repository entity object not specified")
        if isinstance(data, list):
            response = []
            for i in data:
                entity = entitiy_class.from_json(i)
                entity.session = self._session
                response.append(entity)
        else:
            response = entitiy_class.from_json(data)
            response.session = self._session
        return response
