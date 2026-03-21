def test_add_to_meld_does_not_affect_other_players():
    game = setup_game_with_3_players()
    p1, p2, p3 = game.players

    before = len(p3.hand)
    game._action_add_to_meld(p1, action)

    assert len(p3.hand) == before
