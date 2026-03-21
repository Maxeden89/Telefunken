from enum import Enum

class ActionType(Enum):
    DRAW_DECK = "DRAW_DECK"
    DRAW_DISCARD = "DRAW_DISCARD"
    LAY_MELD = "LAY_MELD"
    ADD_TO_MELD = "ADD_TO_MELD"
    DISCARD = "DISCARD"
    END_TURN = "END_TURN"
