from enum import Enum


class Suit(Enum):
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"
    SPADES = "spades"
    JOKER = "joker"


class Card:
    
    def __init__(self, rank=None, suit=None, is_joker=False):
        self.is_joker = is_joker

        if is_joker:
            self.rank = "JOKER"
            self.suit = None
            self.value = None
            self.points = 50
            
            self.rep_rank = None
            self.rep_suit = None
            
        else:
            self.rank = rank
            self.suit = suit
            self.value = self._rank_to_value(rank)
            self.points = self._calculate_points()

    def _rank_to_value(self, rank):
        if rank == "1":
            return 1
        if rank == "J":
            return 11
        if rank == "Q":
            return 12
        if rank == "K":
            return 13
        return int(rank)

    def _calculate_points(self):
        if self.is_joker:
            return 50
        if self.rank == "1":
            return 11
        if self.value >= 10:
            return 10
        return self.value

    def __repr__(self):
        if self.is_joker:
            if self.rep_rank:
                if self.rep_suit:
                    # RUN → muestra palo
                    return f"🃏({self.rep_rank} of {self.rep_suit.value})"
                else:
                    # SET → solo valor
                    return f"🃏({self.rep_rank})"
            return "🃏"
        return f"{self.rank} of {self.suit.value}"

