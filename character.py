"""TODO: implement your character's immutable, canonical public identity."""
from src.api import CharacterDefinition


class Character:
    """Character(agent_id); expose a read-only str agent_id property."""

    def __init__(self, agent_id: str) -> None:
        if not isinstance(agent_id, str):
            raise TypeError("agent_id must be a string!")
        self.__agent_id = agent_id

    @property
    def agent_id(self) -> str:
        return self.__agent_id