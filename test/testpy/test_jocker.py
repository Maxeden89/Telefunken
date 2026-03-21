from game.card import Card
from game.meld import Meld
from game.rules import joker_is_stealable

def make_joker():
    return Card("1", None)

def test_middle_joker_is_not_stealable():
    meld = Meld([
        Card("K", "Clubs"),
        make_joker(),
        Card("2", "Clubs")
    ], "RUN")

    assert not joker_is_stealable(meld)


