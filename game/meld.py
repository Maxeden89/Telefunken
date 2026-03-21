from enum import Enum


class MeldType(Enum):
    SET = "set"
    RUN = "run"


class Meld:
    def __init__(self, cards, meld_type):
        self.cards = cards
        self.type = meld_type
        self.joker_value = None 
    # -------------------------
    # TIPO DE JUEGO
    # -------------------------
    def is_set(self):
        return self.type == MeldType.SET

    def is_run(self):
        return self.type == MeldType.RUN

    # -------------------------
    # COMODÍN
    # -------------------------
    def has_joker(self):
        return any(c.is_joker for c in self.cards)

    def joker(self):
        for c in self.cards:
            if c.is_joker:
                return c
        return None
    
    def is_joker_protected(self):
        """
        El comodín está protegido si:
        - es una escalera (RUN)
        - y está en el medio del juego (después de ordenar por valor)
        """
        if not self.is_run():
            return False

        # ordenar cartas por valor, joker al final
        ordered = sorted(
            self.cards,
            key=lambda c: c.value if not c.is_joker else 99
        )

        # índice del joker en la lista ordenada
        joker_positions = [i for i, c in enumerate(ordered) if c.is_joker]
        if not joker_positions:
            return False

        idx = joker_positions[0]
        # 🔹 protegido solo si NO está en extremos
        return 0 < idx < len(ordered) - 1




    def __repr__(self):
        return f"{self.type.value.upper()}: {self.cards}"

    def can_add(self, card):
        if self.type == "SET":
            values = {c.rank for c in self.cards if not c.is_joker}
            return card.rank in values or card.is_joker

        if self.type == "RUN":
            if card.suit != self.cards[0].suit and not card.is_joker:
                return False
            return True

        return False

    def add(self, card):
        self.cards.append(card)
