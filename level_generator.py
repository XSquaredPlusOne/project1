"""TODO: build a canonical level using the injected terrain generator."""
import random
from collections import deque

from src.api import (
    ArtifactDefinition, CharacterDefinition, EnemyDefinition, GenerationFailure,
    LevelDefinition, LevelSpecification, Position, Terrain, TerrainGeneratorContract,
    TerrainTopology,
)


class LevelGenerator:
    """Use the supplied TerrainGeneratorContract; do not instantiate a replacement."""

    def __init__(self, terrain_generator: TerrainGeneratorContract) -> None:
        self.__terrain_generator = terrain_generator

    def generate_level(self, specification: LevelSpecification, seed: int) -> LevelDefinition:
        rng = random.Random(seed)
        terrain = self.__terrain_generator.generate_terrain(specification.terrain_spec, seed)
        floor = [(r, c) for r, row in enumerate(terrain.terrain_rows)
                 for c, cell in enumerate(row) if cell == "."]
        if len(floor) < 2:
            raise GenerationFailure("LevelGenerator", "terrain has fewer than two open tiles")

        floor_set = set(floor)
        degrees = {cell: sum(n in floor_set for n in self._neighbors(cell, terrain))
                   for cell in floor}
        if sum(1 for d in degrees.values() if d >= 3) < specification.min_branch_tiles:
            raise GenerationFailure("LevelGenerator", "terrain lacks the required branch tiles")
        if sum(1 for d in degrees.values() if d == 1) > specification.max_dead_end_tiles:
            raise GenerationFailure("LevelGenerator", "terrain has too many dead ends")

        if specification.terrain_spec.topology in (
                TerrainTopology.STRAIGHT_PATH, TerrainTopology.BENT_PATH):
            endpoints = [cell for cell, degree in degrees.items() if degree == 1]
            if len(endpoints) != 2:
                raise GenerationFailure("LevelGenerator", "path terrain lacks two endpoints")
        else:
            endpoints = None

        for _ in range(max(1, specification.max_attempts)):
            start, exit_pos = rng.sample(endpoints or floor, 2)
            distance = self._route_length(floor_set, start, exit_pos, terrain)
            if distance is None:
                continue
            if not (specification.min_route_moves <= distance <= specification.max_route_moves):
                continue
            if specification.require_alternate_path and not self._has_alternate(
                    floor_set, start, exit_pos, terrain):
                continue
            placed = self._entity_cells(rng, floor, {start, exit_pos}, specification)
            if placed is None:
                continue
            artifact_cells, enemy_cells = placed
            break
        else:
            raise GenerationFailure("LevelGenerator", "no attempt produced a conforming level")

        artifacts = tuple(
            ArtifactDefinition(f"{specification.level_id}-artifact-{index}",
                               Position(r, c),
                               rng.randint(specification.artifact_value_min,
                                           specification.artifact_value_max))
            for index, (r, c) in enumerate(artifact_cells))
        enemies = tuple(
            EnemyDefinition(f"{specification.level_id}-enemy-{index}",
                            Position(r, c),
                            rng.randint(specification.enemy_penalty_min,
                                        specification.enemy_penalty_max))
            for index, (r, c) in enumerate(enemy_cells))

        return LevelDefinition(
            level_id=specification.level_id,
            profile_id=specification.profile_id,
            seed=seed,
            terrain=terrain,
            start=Position(*start),
            exit=Position(*exit_pos),
            character=CharacterDefinition(specification.agent_id),
            artifacts=artifacts,
            enemies=enemies,
        )

    def _entity_cells(self, rng, floor, reserved, spec):
        pool = [cell for cell in floor
                if spec.allow_entities_on_endpoints or cell not in reserved]
        needed = spec.artifact_count + spec.enemy_count
        if needed == 0:
            return [], []
        if not pool:
            return None
        if spec.allow_entity_overlap:
            picks = [rng.choice(pool) for _ in range(needed)]
        else:
            if needed > len(pool):
                return None
            picks = rng.sample(pool, needed)
        return picks[:spec.artifact_count], picks[spec.artifact_count:]

    def _route_length(self, floor_set, start, goal, terrain, blocked=frozenset()):
        seen = {start}
        frontier = deque([(start, 0)])
        while frontier:
            cell, distance = frontier.popleft()
            if cell == goal:
                return distance
            for nxt in self._neighbors(cell, terrain):
                if nxt in seen or nxt not in floor_set or nxt in blocked:
                    continue
                seen.add(nxt)
                frontier.append((nxt, distance + 1))
        return None

    def _has_alternate(self, floor_set, start, goal, terrain):
        shortest = self._shortest_path(floor_set, start, goal, terrain)
        if shortest is None or len(shortest) < 3:
            return False
        for blocked in shortest[1:-1]:
            if self._route_length(floor_set, start, goal, terrain,
                                  blocked=frozenset({blocked})) is not None:
                return True
        return False

    def _shortest_path(self, floor_set, start, goal, terrain):
        frontier = deque([[start]])
        seen = {start}
        while frontier:
            path = frontier.popleft()
            cell = path[-1]
            if cell == goal:
                return path
            for nxt in self._neighbors(cell, terrain):
                if nxt in seen or nxt not in floor_set:
                    continue
                seen.add(nxt)
                frontier.append(path + [nxt])
        return None

    @staticmethod
    def _neighbors(cell, terrain: Terrain):
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = cell[0] + dr, cell[1] + dc
            if 0 <= nr < terrain.rows and 0 <= nc < terrain.columns:
                yield (nr, nc)