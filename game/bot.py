class BotPlayer:
    def __init__(self, name="Bot"):
        self.name = name

    def play_turn(self, game):
        player = game.players[game.current_player_index]
        print(f"🤖 Turno del bot: {player.name}")

        # 1️⃣ ROBAR
        result = game.apply_action({
            "type": "DRAW",
            "source": "deck"
        })

        if not result["ok"]:
            return

        # 2️⃣ INTENTAR BAJAR JUEGO
        self.try_lay_meld(game, player)

        # 3️⃣ DESCARTAR (obligatorio)
        discard_index = self.choose_discard(player)
        game.apply_action({
            "type": "DISCARD",
            "card_index": discard_index
        })

    def try_lay_meld(self, game, player):
        from itertools import combinations
        from game.rules import detect_meld_type

        if game.turn_phase != "PLAY":
            return

        hand_size = len(player.hand)

        # 🔁 probar solo combinaciones válidas (3 a 5 cartas)
        for size in range(3, min(6, hand_size + 1)):
            for combo in combinations(range(hand_size), size):
                cards = [player.hand[i] for i in combo]

                meld_type = detect_meld_type(cards)
                if meld_type is None:
                    continue

                result = game.apply_action({
                    "type": "LAY_MELD",
                    "card_indices": list(combo)
                })

                if result["ok"]:
                    print(f"🤖 Baja un juego ({meld_type.name})")
                    return  # baja SOLO un juego por turno

    def choose_discard(self, player):
        # descartar la última carta es seguro
        return len(player.hand) - 1
