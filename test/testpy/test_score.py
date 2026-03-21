from game.card import Card, Suit
from game.player import Player

p = Player("Test")

p.hand = [
    Card("A", Suit.HEARTS),
    Card(5, Suit.CLUBS),
    Card("K", Suit.SPADES),
    Card(is_joker=True)
]

print(p.hand_score())  # 10 + 5 + 10 + 50 = 75
