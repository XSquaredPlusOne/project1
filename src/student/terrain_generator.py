"""TODO: generate canonical terrain deterministically from specification and seed."""
import random

from src.api import GenerationFailure, Terrain, TerrainGenerationSpec, TerrainTopology


class TerrainGenerator:
    """Keep state local; identical inputs must also agree across fresh instances."""

    def __init__(self) -> None:
        pass

    def generate_terrain(self, specification: TerrainGenerationSpec, seed: int) -> Terrain:
        rng = random.Random(seed)
        for _ in range(specification.max_attempts):
            grid = self._grow(specification, rng)
            if grid is not None:
                return Terrain(tuple("".join(row) for row in grid))
        raise GenerationFailure("TerrainGenerator", "no attempt satisfied the specification")

    def _grow(
        self, spec: TerrainGenerationSpec, rng: random.Random,
    ) -> list[list[str]] | None:
        rows, columns = spec.rows, spec.columns
        grid = [["#"] * columns for _ in range(rows)]

        if spec.topology is TerrainTopology.STRAIGHT_PATH:
            low = max(2, spec.min_open_tiles)
            high = min(spec.max_open_tiles, max(rows, columns))
            if low > high:
                return None
            length = rng.randint(low, high)
            axes = []
            if length <= rows:
                axes.append("vertical")
            if length <= columns:
                axes.append("horizontal")
            axis = rng.choice(axes)
            if axis == "vertical":
                column = rng.randrange(columns)
                start = rng.randrange(rows - length + 1)
                for row in range(start, start + length):
                    grid[row][column] = "."
            else:
                row = rng.randrange(rows)
                start = rng.randrange(columns - length + 1)
                for column in range(start, start + length):
                    grid[row][column] = "."
            return grid

        if spec.topology is TerrainTopology.BENT_PATH:
            low = max(3, spec.min_open_tiles)
            high = spec.max_open_tiles
            if rows < 2 or columns < 2 or low > high:
                return None
            target = rng.randint(low, high)
            top = rng.randrange(rows - 1)
            left = rng.randrange(columns - 1)
            square = [
                (top, left), (top, left + 1),
                (top + 1, left), (top + 1, left + 1),
            ]
            missing = rng.randrange(4)
            path = [cell for index, cell in enumerate(square) if index != missing]
            floor = set(path)
            endpoints = [
                cell for cell in path
                if sum(neighbor in floor for neighbor in self._orthogonal(cell, rows, columns)) == 1
            ]
            while len(floor) < target:
                candidates = []
                for endpoint in sorted(endpoints):
                    for child in self._orthogonal(endpoint, rows, columns):
                        if child in floor:
                            continue
                        touching = [
                            neighbor for neighbor in self._orthogonal(child, rows, columns)
                            if neighbor in floor
                        ]
                        if touching == [endpoint]:
                            candidates.append((endpoint, child))
                if not candidates:
                    return None
                endpoint, child = rng.choice(candidates)
                endpoints.remove(endpoint)
                endpoints.append(child)
                floor.add(child)
            for row, column in floor:
                grid[row][column] = "."
            return grid

        if spec.topology is TerrainTopology.BRANCHING_TREE:
            low = max(4, spec.min_open_tiles)
            high = spec.max_open_tiles
            roots = [
                (row, column)
                for row in range(rows)
                for column in range(columns)
                if sum(1 for _ in self._orthogonal((row, column), rows, columns)) >= 3
            ]
            if not roots or low > high:
                return None
            target = rng.randint(low, high)
            root = rng.choice(roots)
            neighbors = list(self._orthogonal(root, rows, columns))
            floor = {root, *rng.sample(neighbors, 3)}
            for row, column in floor:
                grid[row][column] = "."
            return self._extend_tree(grid, floor, target, rng)

        target = rng.randint(spec.min_open_tiles, spec.max_open_tiles)
        if target == 0:
            return grid
        start = (rng.randrange(rows), rng.randrange(columns))
        floor = {start}
        grid[start[0]][start[1]] = "."
        while len(floor) < target:
            frontier = sorted({
                child
                for cell in floor
                for child in self._orthogonal(cell, rows, columns)
                if child not in floor
            })
            if not frontier:
                return None
            child = rng.choice(frontier)
            floor.add(child)
            grid[child[0]][child[1]] = "."
        return grid

    def _extend_tree(
        self, grid: list[list[str]], floor: set[tuple[int, int]], target: int,
        rng: random.Random,
    ) -> list[list[str]] | None:
        rows, columns = len(grid), len(grid[0])
        while len(floor) < target:
            candidates = []
            for cell in sorted(floor):
                for child in self._orthogonal(cell, rows, columns):
                    if child in floor:
                        continue
                    touching = [
                        neighbor for neighbor in self._orthogonal(child, rows, columns)
                        if neighbor in floor
                    ]
                    if touching == [cell]:
                        candidates.append((cell, child))
            if not candidates:
                return None
            _, child = rng.choice(candidates)
            floor.add(child)
            grid[child[0]][child[1]] = "."
        return grid

    @staticmethod
    def _orthogonal(cell: tuple[int, int], rows: int, columns: int):
        row, column = cell
        for row_delta, column_delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row, next_column = row + row_delta, column + column_delta
            if 0 <= next_row < rows and 0 <= next_column < columns:
                yield next_row, next_column
