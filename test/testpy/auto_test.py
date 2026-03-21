from game.game import Game
import random

print("Auto test iniciado")

def auto_play_turn(game):
    player = game.players[game.current_player_index]

    # 1) Robar
    if game.discard_pile and random.choice([True, False]):
        game.deck.append(game.discard_pile.pop())  # simula compra simple
    else:
        player.hand.append(game.deck.pop())

    # 2) Intentar bajar juegos aleatorios
    if not player.has_met_objective and len(player.hand) >= 3:
        random.shuffle(player.hand)
        cards = player.hand[:3]
        ok, _ = game.try_lay_down(player, [cards])
        if ok:
            player.has_met_objective = True

    # 3) Descartar
    if player.hand:
        discard = random.choice(player.hand)
        player.hand.remove(discard)
        game.discard_pile.append(discard)

    # 4) Siguiente jugador
    game.current_player_index = (game.current_player_index + 1) % len(game.players)

def auto_game():
    game = Game(["Ana", "Luis", "Bot"])
    game.start_game()

    for _ in range(500):  # 500 turnos automáticos
        auto_play_turn(game)

    print("✅ Simulación terminada sin crashes")

if __name__ == "__main__":
    auto_game()
