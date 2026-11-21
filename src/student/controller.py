"""TODO: select one public action from each immutable world observation."""
from collections import deque
from heapq import heappop, heappush
from itertools import count

from src.api import Position, WorldAction, WorldActionType, WorldSnapshot


class AgentController:
    """A new controller is constructed for each run; arrival still needs EXIT."""

    def __init__(self) -> None:
        pass

    def choose_action(self, state: WorldSnapshot, agent_id: str) -> WorldAction:
        start = state.agent_position
        goal = state.exit_position
        allowed = set(state.allowed_actions)

        planned = self._plan_artifact_or_exit(state, allowed)
        if planned is not None:
            return planned

        if start == goal and WorldActionType.EXIT in allowed:
            return WorldAction(WorldActionType.EXIT)

        static, patrol_cells = self._enemy_maps(state)
        can_engage = WorldActionType.ENGAGE in allowed

        safe = self._bfs(
            state, start, goal, patrol_cells | set(static), set(), allow_engage=False,
        )
        risky = (self._bfs(state, start, goal, patrol_cells, static, allow_engage=True)
                 if can_engage else None)

        if risky is None:
            route = safe
        elif safe is None:
            route = risky
        else:
            safe_cost = len(safe) + 1
            risky_cost = len(risky) + 1 + sum(
                static[cell].encounter_penalty for cell in risky if cell in static)
            route = safe if safe_cost <= risky_cost else risky

        if safe is not None and WorldActionType.COLLECT in allowed:
            collected = set(state.collected_artifact_ids)
            for artifact in state.level.artifacts:
                if (artifact.position == start and artifact.artifact_id not in collected
                        and artifact.value > state.deduction_rate):
                    return WorldAction(WorldActionType.COLLECT, target_id=artifact.artifact_id)

        if route:
            nxt = route[0]
            if nxt in static:
                return WorldAction(WorldActionType.ENGAGE, target_id=static[nxt].enemy_id)
            return self._step(start, nxt)

        if WorldActionType.WAIT in allowed:
            return WorldAction.wait()
        for fallback in self._neighbors(start):
            if (state.is_traversable(fallback) and fallback not in patrol_cells
                    and fallback not in static):
                action = self._step(start, fallback)
                if action.action_type in allowed:
                    return action
        if can_engage:
            for position, enemy in static.items():
                if start.manhattan_distance(position) == 1:
                    return WorldAction(WorldActionType.ENGAGE, target_id=enemy.enemy_id)
        return WorldAction.wait()

    def _plan_artifact_or_exit(self, state, allowed):
        direct = self._search_plan(state, None, allowed)
        if direct is None:
            return None

        collected = set(state.collected_artifact_ids)
        selected_actions = None
        selected_benefit = -1
        if WorldActionType.COLLECT in allowed:
            for artifact in state.level.artifacts:
                if artifact.artifact_id in collected:
                    continue
                candidate = self._search_plan(state, artifact, allowed)
                if candidate is None:
                    continue
                actions, cost = candidate
                benefit = artifact.value - state.deduction_rate * (cost - direct[1])
                if benefit >= 0 and benefit > selected_benefit:
                    selected_actions = actions
                    selected_benefit = benefit
        actions = direct[0] if selected_actions is None else selected_actions
        return actions[0] if actions else None

    def _search_plan(self, state, artifact, allowed):
        if WorldActionType.EXIT not in allowed:
            return None

        patrols = state.level.patrols
        observations = {item.enemy_id: item for item in state.enemy_observations}
        phases = []
        for patrol in patrols:
            observation = observations.get(patrol.enemy_id)
            phase = (observation.phase if observation is not None and observation.phase is not None
                     else (patrol.initial_phase + state.turn) % patrol.period)
            phases.append(phase)
        phases = tuple(phases)

        patrol_ids = {patrol.enemy_id for patrol in patrols}
        defeated = set(state.defeated_enemy_ids)
        enemies = tuple(
            enemy for enemy in state.level.enemies
            if enemy.enemy_id not in patrol_ids and enemy.enemy_id not in defeated
        )
        collected = False
        start = (state.agent_position, phases, 0, collected, 0)
        remaining_turns = state.max_turns - state.turn
        if state.deadline_turn is not None:
            remaining_turns = min(remaining_turns, state.deadline_turn - state.turn)
        if remaining_turns < 1:
            return None

        def patrol_positions(current_phases):
            return {
                patrol.positions[phase]
                for patrol, phase in zip(patrols, current_phases)
            }

        def recover(key, previous):
            actions = []
            while key != start:
                key, action = previous[key]
                actions.append(action)
            actions.reverse()
            return tuple(actions)

        serial = count()
        frontier = [(0, 0, next(serial), start)]
        costs = {start: 0}
        previous = {}
        while frontier:
            cost, turns, _, current = heappop(frontier)
            if costs.get(current) != cost:
                continue
            position, current_phases, defeated_mask, has_collected, _ = current
            if (position == state.exit_position
                    and (artifact is None or has_collected)
                    and turns < remaining_turns):
                actions = recover(current, previous) + (WorldAction(WorldActionType.EXIT),)
                return actions, cost + 1
            if turns >= remaining_turns:
                continue

            next_phases = tuple(
                (phase + 1) % patrol.period for phase, patrol in zip(current_phases, patrols)
            )
            current_patrols = patrol_positions(current_phases)
            next_patrols = patrol_positions(next_phases)
            next_turn = turns + 1

            def enqueue(next_position, next_mask, next_collected, action, step_cost):
                next_state = (next_position, next_phases, next_mask, next_collected, next_turn)
                next_cost = cost + step_cost
                if next_cost >= costs.get(next_state, float("inf")):
                    return
                costs[next_state] = next_cost
                previous[next_state] = (current, action)
                heappush(frontier, (next_cost, next_turn, next(serial), next_state))

            active_positions = {
                enemy.position for index, enemy in enumerate(enemies)
                if not defeated_mask & (1 << index)
            }
            for neighbor in self._neighbors(position):
                if (not state.is_traversable(neighbor) or neighbor in active_positions
                        or neighbor in current_patrols or neighbor in next_patrols):
                    continue
                action = self._step(position, neighbor)
                if action.action_type in allowed:
                    enqueue(neighbor, defeated_mask, has_collected, action, 1)

            if WorldActionType.ENGAGE in allowed and position not in next_patrols:
                for index, enemy in enumerate(enemies):
                    if (not defeated_mask & (1 << index)
                            and position.manhattan_distance(enemy.position) == 1):
                        action = WorldAction(WorldActionType.ENGAGE, target_id=enemy.enemy_id)
                        enqueue(position, defeated_mask | (1 << index), has_collected,
                                action, 1 + enemy.encounter_penalty)

            if WorldActionType.WAIT in allowed and position not in next_patrols:
                enqueue(position, defeated_mask, has_collected, WorldAction.wait(), 1)

            if (artifact is not None and not has_collected and position == artifact.position
                    and WorldActionType.COLLECT in allowed and position not in next_patrols):
                action = WorldAction(WorldActionType.COLLECT, target_id=artifact.artifact_id)
                enqueue(position, defeated_mask, True, action, 1)

        return None

    def _enemy_maps(self, state: WorldSnapshot):
        static = {}
        patrol_cells = set()
        defeated = set(state.defeated_enemy_ids)
        enemies = {enemy.enemy_id: enemy for enemy in state.level.enemies}
        for obs in state.enemy_observations:
            if obs.enemy_id in defeated or obs.position is None:
                continue
            if obs.phase is None:
                static[obs.position] = enemies[obs.enemy_id]
            else:
                patrol_cells.add(obs.position)
        return static, patrol_cells

    def _bfs(self, state, start, goal, blocked, engagable, allow_engage):
        frontier = deque([[start]])
        seen = {start}
        while frontier:
            path = frontier.popleft()
            cell = path[-1]
            if cell == goal:
                return path[1:]
            for nxt in self._neighbors(cell):
                if nxt in seen or not state.is_traversable(nxt) or nxt in blocked:
                    continue
                if not allow_engage and nxt in engagable:
                    continue
                seen.add(nxt)
                frontier.append(path + [nxt])
        return None

    @staticmethod
    def _neighbors(cell: Position):
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            yield Position(cell.row + dr, cell.column + dc)

    @staticmethod
    def _step(here: Position, nxt: Position) -> WorldAction:
        if nxt.row > here.row:
            return WorldAction(WorldActionType.MOVE_SOUTH)
        if nxt.row < here.row:
            return WorldAction(WorldActionType.MOVE_NORTH)
        if nxt.column > here.column:
            return WorldAction(WorldActionType.MOVE_EAST)
        return WorldAction(WorldActionType.MOVE_WEST)