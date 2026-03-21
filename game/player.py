class Player:
    def __init__(self, name, is_bot=False, bot=None):
        self.name = name
        self.is_bot = is_bot
        self.bot = bot
        
        self.hand = []
        self.melds = []               # juegos bajados
        self.purchases_used = 0       # 👈 ESTO FALTABA
        self.score = 0
        self.has_met_objective = False

    def hand_score(self):
        score = 0
        for card in self.hand:
            if card.is_joker:
                score += 50
            elif card.rank == 1:      # As
                score += 11
            elif 2 <= card.rank <= 9:
                score += card.rank
            else:
                score += 10
        return score





    def can_meet_objective(self, objective):
    
        from game.meld_validation import detect_meld_type
        from itertools import combinations

    # objective ejemplo: [(5, 1)]  → un juego de 5
        required_size, required_count = objective[0]

        valid_cards = set()

    # probamos combinaciones de 3 a tamaño objetivo
        for size in range(3, required_size + 1):
            for combo in combinations(self.hand, size):
                if detect_meld_type(list(combo)):
                    valid_cards.update(combo)

        return len(valid_cards) >= required_size
   

