def test_round_ends_when_player_has_no_cards():
    game = Game(["Ana", "Bot"])
    game.players[0].hand = []

    game.check_round_end()

    assert game.round_over

def test_scoring_does_not_change_after_round_end():
    game = Game(["Ana", "Bot"])
    scores = [p.score for p in game.players]

    game.check_round_end()
    game.check_round_end()

    assert scores == [p.score for p in game.players]
