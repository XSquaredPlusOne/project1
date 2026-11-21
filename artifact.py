"""TODO: implement initial artifact data; introductory gameplay has no artifacts."""
from src.api import Position


class Artifact:
    """Expose read-only canonical identity, position, and nonnegative value."""

    def __init__(self, artifact_id: str, position: Position, value: int) -> None:
        if type(value) is not int:
            raise TypeError("Artifact value must be an integer!")
        if value < 0:
            raise ValueError("Artifact value cannot be negative!")
        self.__artifact_id = artifact_id
        self.__position = position
        self.__value = value

    @property
    def artifact_id(self) -> str:
        return self.__artifact_id

    @property
    def position(self) -> Position:
        return self.__position

    @property
    def value(self) -> int:
        return self.__value