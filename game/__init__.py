# game package — state machine, turn management, rules engine and main game loop.
from .state_machine import GameState, can_transition
from .turn_manager  import TurnManager, Player
from .rules         import RulesEngine, ShotResult


def __getattr__(name):
    if name == "Game":
        from .game import Game

        return Game
    raise AttributeError(f"module 'game' has no attribute {name!r}")
