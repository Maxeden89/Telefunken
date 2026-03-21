def test_valid_run_with_joker_middle():
    cards = [
        Card("K", "Clubs"),
        Joker(),
        Card("2", "Clubs"),
    ]
    assert is_valid_meld(cards)

def test_invalid_run_with_two_jokers():
    cards = [Card("5","Spades"), Joker(), Joker()]
    assert not is_valid_meld(cards)
