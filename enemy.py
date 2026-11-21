"""TODO: implement initial enemy data; introductory gameplay has no enemies."""
from src.api import EnemyDefinition, Position


class Enemy:
    """Expose read-only identity, position, and nonnegative encounter penalty."""

    def __init__(self, enemy_id: str, position: Position, encounter_penalty: int) -> None:
        if type(encounter_penalty) is not int:
            raise TypeError("encounter_penalty must be an integer!")
        if encounter_penalty < 0:
            raise ValueError("encounter_penalty cannot be negative!")
        self.__enemy_id = enemy_id
        self.__position = position
        self.__encounter_penalty = encounter_penalty

    @property
    def enemy_id(self) -> str:
        return self.__enemy_id

    @property
    def position(self) -> Position:
        return self.__position

    @property
    def encounter_penalty(self) -> int:
        return self.__encounter_penalty