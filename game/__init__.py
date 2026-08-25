# game package — state machine, turn management, rules engine and main game loop.
from .game         import Game
from .state_machine import GameState, can_transition
from .turn_manager  import TurnManager, Player
from .rules         import RulesEngine, ShotResult
