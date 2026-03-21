from game.game import Game
from game.player import Player
from game.card import Card
from game.meld import Meld

def make_joker():
    c = Card("A", "Spades")
    c.is_joker = True
    return c

#def test_run_edge_joker_auto_steal():
    # jugadores
    ana = Player("Ana")
    luis = Player("Luis")

    ana.is_bot = True
    
    game = Game([ana, luis])

    # forzamos turno de Ana
    game.current_player_index = 0
    game.turn_phase = "PLAY"
    game.has_drawn = True

    # meld en mesa: RUN 🃏 Q K
    joker = make_joker()
    meld = Meld([
        joker,
        Card("Q", "Clubs"),
        Card("K", "Clubs")
    ], "RUN")

    game.melds = [meld]

    # Ana tiene la carta que reemplaza al comodín
    ana.hand = [Card("J", "Clubs")]

    # acción: agregar carta
    res = game.apply_action({
        "type": "ADD_TO_MELD",
        "meld_index": 0,
        "card_indices": [0]
    })

    assert res["ok"] is True

    # ✅ el comodín vuelve a la mano
    assert any(c.is_joker for c in ana.hand)

    # ✅ el meld ya no tiene comodín
    assert not meld.has_joker()

    # ✅ el meld quedó correcto
    values = [c.rank for c in meld.cards]
    assert values == ["J", "Q", "K"]
