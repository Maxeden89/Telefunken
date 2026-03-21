def test_turn_rotation_3_players():
    game = Game(["Ana", "Bot", "Luis"])

    order = []
    for _ in range(6):
        order.append(game.current_player.name)
        game.end_turn()

    assert order == ["Ana", "Bot", "Luis", "Ana", "Bot", "Luis"]
