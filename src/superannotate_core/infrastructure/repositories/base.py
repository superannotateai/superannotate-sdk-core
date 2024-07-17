from abc import ABC
from typing import List
from typing import Union


class BaseRepositry(ABC):
    def __init__(self, session):
        self._session = session


class BaseHttpRepository(BaseRepositry):
    def serialize_entity(self, data: Union[List[dict], dict]):
        entity_class = getattr(self, "ENTITY")
        if not entity_class:
            raise Exception("Repository entity object not specified")
        if isinstance(data, list):
            response = []
            for i in data:
                entity = entity_class.from_json(i)
                entity.session = self._session
                response.append(entity)
        else:
            response = entity_class.from_json(data)
            response.session = self._session
        return response
