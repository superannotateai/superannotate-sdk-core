import inspect
import typing
from abc import ABC
from enum import Enum
from typing import Any

from typing_extensions import TypedDict
from typing_extensions import Union


class Extra(str, Enum):
    ALLOW = "allow"
    IGNORE = "ignore"


class AliasHandler:
    """
    A utility class to handle alias mapping for dictionary keys.
    """

    def __init__(self, from_to_mapping: dict):
        """
        Initialize the AliasHandler with the provided alias mapping.

        Args:
            from_to_mapping (dict): A dictionary mapping original keys to their alias keys.
        """
        self._from_to_mapping = from_to_mapping

    def handle(
        self, data: dict, reverse_mapping: bool = False, raise_exception: bool = False
    ):
        """
        Handle alias mapping for dictionary keys.

        Args:
            data (dict): The dictionary to be processed.
            reverse_mapping (dict, optional): Dictionary for reverse mapping.
            raise_exception (bool, optional): If True, raise KeyError if a key in from_to_mapping is not found in data.

        Returns:
            dict: The dictionary with keys mapped according to the alias mapping.

        Raises:
            KeyError: If raise_exception is True and a key in from_to_mapping is not found in data.
        """
        mapping = (
            self._from_to_mapping
            if not reverse_mapping
            else {v: k for k, v in self._from_to_mapping.items()}
        )
        for from_key, to_key in mapping.items():
            if from_key not in data:
                if raise_exception:
                    raise KeyError(from_key)
            else:
                data[to_key] = data.pop(from_key)
        return data


class BaseEntity(ABC):
    """
    require to define schema
    class Meta:
        model = Entity
    """

    class Meta:
        model: TypedDict
        alias_handler: AliasHandler

    def __new__(cls, *args, **kwargs):
        super().__new__(cls, *args, **kwargs)

    def __init__(self, /, **data: Any):
        self.from_json(data)
        self._session = None
        self.schema = self.__class__.__annotations__

    @classmethod
    def _from_entity(cls, entity):
        obj = cls.from_json(entity.dict(cls=cls))
        setattr(obj, "session", getattr(entity, "session"))
        return obj

    @staticmethod
    def _serialzie_enum(annotation, val):
        if isinstance(val, Enum):
            val = val.value
        try:
            val = annotation[val]
        except (ValueError, KeyError):
            val = annotation(val)
        return val

    @property
    def session(self):
        return self._session

    @session.setter
    def session(self, val):
        self._session = val

    def dict(
        self,
        exclude: Union[set, list] = None,
        exclude_none=False,
        use_enum_values=False,
        cls=None,
    ) -> dict:
        if not exclude:
            exclude = set()
        else:
            exclude = set(exclude)
        data = {}
        if cls:
            annotations = typing.get_type_hints(cls)
        else:
            annotations = typing.get_type_hints(self.__class__)
        for field in annotations:
            annotation = annotations[field]
            if field in exclude:
                continue
            if field not in annotations:
                continue
            try:
                val = self.__getattribute__(field)
            except AttributeError:
                val = None
            if exclude_none and val is None:
                continue
            try:
                # todo check is iterable
                if isinstance(val, list):
                    for idx, _val in enumerate(val):
                        if isinstance(_val, BaseEntity):
                            val[idx] = _val.dict()
                elif isinstance(val, BaseEntity):
                    val = val.dict()
                elif isinstance(annotation, typing._GenericAlias):
                    ...
                elif inspect.isclass(annotation) and issubclass(annotation, Enum):
                    if use_enum_values:
                        val = self._serialzie_enum(annotation, val).value
                    else:
                        val = self._serialzie_enum(annotation, val).name
            except Exception as e:
                print()
            finally:
                data[field] = val
        return data

    @classmethod
    def from_json(cls, data: dict):
        alias_handler = getattr(cls, "ALIAS_HANDLER", None)
        if alias_handler:
            data = alias_handler.handle(data, raise_exception=False)
        annotations = typing.get_type_hints(cls)
        instnace = object.__new__(cls)
        for field in annotations:
            value = data.pop(field, None)
            try:
                if value:
                    annotation = annotations[field]
                    if isinstance(annotation, typing._GenericAlias):
                        ...
                    elif inspect.isclass(annotation) and issubclass(annotation, Enum):
                        value = cls._serialzie_enum(annotation, value)
                    else:
                        value = annotation(value)
            except Exception as e:
                raise
            setattr(instnace, field, value)
        meta = getattr(cls, "Meta")
        exta = getattr(meta, "extra", None)
        if exta == Extra.ALLOW:
            for field, value in data.items():
                setattr(instnace, field, value)
        return instnace

    def to_json(self, exclude_none=False, use_enum_values: bool = True):
        kwargs = {"use_enum_values": use_enum_values, "exclude_none": exclude_none}
        alias_handler = getattr(self, "ALIAS_HANDLER", None)
        if alias_handler:
            return alias_handler.handle(self.dict(**kwargs), reverse_mapping=True)
        else:
            return self.dict(**kwargs)


class TimedEntity(BaseEntity):
    createdAt: str
    updatedAt: str
