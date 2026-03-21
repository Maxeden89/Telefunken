from game.card import Card
from enum import Enum
import random


class Suit(Enum):
    HEARTS = "Hearts"
    DIAMONDS = "Diamonds"
    CLUBS = "Clubs"
    SPADES = "Spades"
    JOKER = "Joker"


def create_deck():
    deck = []
    ranks = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

    for _ in range(2):  # dos mazos
        for suit in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
            for rank in ranks:
                deck.append(Card(rank=rank, suit=suit))

        # 2 comodines por mazo
        deck.append(Card(is_joker=True))
        deck.append(Card(is_joker=True))

    random.shuffle(deck)
    return deck
