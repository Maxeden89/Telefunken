from re import A

from game.deck import create_deck
from game.player import Player
from game.objectives import ROUND_OBJECTIVES
from game.meld import Meld, MeldType
from game.rules import detect_meld_type, is_valid_meld, can_add_to_meld

class Game:
    def __init__(self, players):
        self.players = players
        self.deck = create_deck()
        self.discard_pile = []
        self.melds = []
        self.round_number = 1
        self.current_player_index = 0
        self.max_purchases = 7
        self.turn_phase = "DRAW"
        self.game_over = False
        self.winner = None
        self.deal_cards()

    def _end_turn(self):
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.turn_phase = "DRAW"

    def _check_game_over(self, player):
        if len(player.hand) == 0:
            self.game_over = True
            self.winner = player
            self.calculate_scores()
            return True
        return False

    def deal_cards(self):
        for _ in range(11):
            for player in self.players:
                if self.deck:
                    player.hand.append(self.deck.pop())
        if self.deck:
            self.discard_pile.append(self.deck.pop())

    def apply_action(self, action):
        player = self.players[self.current_player_index]
        atype = action.get("type")

        if atype == "DRAW": return self._action_draw(player, action)
        if atype == "LAY_MELD": return self._action_lay_meld(player, action)
        if atype == "LAY_ALL_OBJECTIVE": return self._action_lay_all_objective(player, action)
        if atype == "ADD_TO_MELD": return self._action_add_to_meld(player, action)
        if atype == "DISCARD": return self._action_discard(player, action)
        if atype == "OUT_OF_TURN_PURCHASE": return self._action_out_of_turn_purchase(action)
        
        return {"ok": False, "message": "Acción desconocida"}

    def _action_draw(self, player, action):
        if self.turn_phase != "DRAW":
            return {"ok": False, "message": "No podés robar ahora"}
        
        if action.get("source") == "deck":
    # ✅ Si el mazo está vacío, reciclar el pozo
            if not self.deck:
                if len(self.discard_pile) > 1:
                    top = self.discard_pile.pop()
                    import random
                    random.shuffle(self.discard_pile)
                    self.deck = self.discard_pile[:]
                    self.discard_pile = [top]
                    print("DEBUG: Mazo reciclado del pozo")
            if self.deck:
                player.hand.append(self.deck.pop())
            self.turn_phase = "PLAY"
            return {"ok": True}
            
        if action.get("source") == "discard":
            res = self._handle_purchase(player, out_of_turn=False)
            if res["ok"]: self.turn_phase = "PLAY"
            return res
        
        return {"ok": False, "message": "Fuente inválida"}

    def _action_out_of_turn_purchase(self, action):
        """Compra fuera de turno — el jugador indicado compra la carta del pozo."""
        buyer_index = action.get("buyer_index")
        if buyer_index is None:
            return {"ok": False, "message": "Falta el índice del comprador"}

        buyer = self.players[buyer_index]
        print(f"DEBUG: {buyer.name} intenta comprar fuera de turno")

        res = self._handle_purchase(buyer, out_of_turn=True)
        if res["ok"]:
            print(f"DEBUG: {buyer.name} compró fuera de turno (+1 carta)")
        return res
    
    def _action_lay_all_objective(self, player, action):
        if self.turn_phase != "PLAY": 
            return {"ok": False, "message": "Primero robá una carta"}
        
        groups_indices = action.get("groups_indices", [])
        requirements = ROUND_OBJECTIVES.get(self.round_number, [])
        total_needed = sum(req[1] for req in requirements)
        min_cards = requirements[0][0] if requirements else 3
        
        print(f"\n--- DEBUG INICIO BAJAR TODO ---")
        print(f"Grupos recibidos: {len(groups_indices)} | Necesarios: {total_needed} | Mínimo cartas: {min_cards}")
        
        if len(groups_indices) < total_needed:
            return {"ok": False, "message": f"Necesitás {total_needed} juegos."}

        temp_melds = [] 
        
        for i, indices in enumerate(groups_indices):
            try:
                card_list = [player.hand[idx] for idx in indices]
            except IndexError:
                return {"ok": False, "message": f"Índices inválidos en el grupo {i+1}."}

            print(f"DEBUG: Grupo {i+1} → {[c.rank for c in card_list]}")

            if len(card_list) < min_cards:
                return {"ok": False, "message": f"El grupo {i+1} necesita al menos {min_cards} cartas."}

            m_type = detect_meld_type(card_list)
            
            if not m_type:
                ranks = [str(c.rank) for c in card_list if not c.is_joker]
                suits = [str(c.suit) for c in card_list if not c.is_joker]
                if len(set(ranks)) == 1: m_type = MeldType.SET
                elif len(set(suits)) == 1: m_type = MeldType.RUN

            print(f"DEBUG: Grupo {i+1} tipo detectado: {m_type}")

            if not m_type:
                return {"ok": False, "message": f"Grupo {i+1} no reconocido."}

            has_joker = any(c.is_joker for c in card_list)
            declared_rank = action.get(f"declared_joker_rank_{i}")

            if m_type == MeldType.RUN and has_joker and not declared_rank:
                print(f"!!! DEBUG: ENVIANDO ASK_JOKER_VALUE AL FRONTEND para grupo {i+1} !!!")
                return {
                    "ok": False,
                    "type": "ASK_JOKER_VALUE",
                    "options": self.get_joker_options(card_list),
                    "group_index": i,
                    "message": f"Elegí el valor del Comodín en el grupo {i+1}"
                }

            new_meld = Meld(card_list, m_type)

            if has_joker and declared_rank:
                j = next(c for c in card_list if c.is_joker)
                j.rep_rank = declared_rank
                cartas_reales = [c for c in card_list if not c.is_joker]
                if cartas_reales:
                    j.rep_suit = cartas_reales[0].suit
                    j.is_locked = True
                print(f"DEBUG: Joker BLINDADO como {j.rep_rank} en grupo {i+1}")

            res_joker = self._assign_joker_representation(new_meld)
            
            if res_joker and isinstance(res_joker, dict) and res_joker.get("need_choice"):
                return res_joker 

            if not is_valid_meld(card_list):
                return {"ok": False, "message": f"El grupo {i+1} no cumple las reglas."}

            temp_melds.append(new_meld)

        for meld in temp_melds:
            print(f"DEBUG: Moviendo juego {meld.type} a la mesa.")
            
            if meld.type == MeldType.RUN:
                piv = self._get_circular_pivote(meld.cards)
                meld.cards.sort(key=lambda c: (self._rank_to_value(c.rank if not c.is_joker else c.rep_rank) - piv) % 13)
                print(f"DEBUG: RUN ordenado con pivote {piv}")
            else:
                meld.cards.sort(key=lambda c: self._rank_to_value(c.rank if not c.is_joker else c.rep_rank))
            
            for card in meld.cards:
                if card in player.hand:
                    player.hand.remove(card)
            
            self.melds.append(meld)

        player.has_met_objective = True

        if len(player.hand) == 0:
            self._check_game_over(player)
            print(f"DEBUG: ¡Jugador {player.name} ganó bajando todo!")

        print(f"--- DEBUG ÉXITO: {len(temp_melds)} juegos bajados ---")
        return {"ok": True, "message": "¡Objetivo cumplido!"}

    def _action_lay_meld(self, player, action):
        if self.turn_phase != "PLAY": return {"ok": False, "message": "No es tu fase de juego"}

        indices = action.get("card_indices", [])
        cards = [player.hand[i] for i in indices]
        
        m_type = detect_meld_type(cards)
        has_joker = any(c.is_joker for c in cards)
        declared_rank = action.get("declared_joker_rank")

        print(f"\n--- DEBUG LAY ---")
        print(f"Tipo: {m_type} | Joker: {has_joker} | Declarado: {declared_rank}")

        if has_joker and not declared_rank:
            if str(m_type).endswith("RUN"):
                print("!!! DEBUG: ENVIANDO ASK_JOKER_VALUE AL FRONTEND !!!")
                return {
                    "ok": False,
                    "type": "ASK_JOKER_VALUE",
                    "options": self.get_joker_options(cards),
                    "message": "Elegí el valor del Comodín"
                }

        if not m_type or not is_valid_meld(cards): 
            return {"ok": False, "message": "Esa combinación no es válida"}

        new_meld = Meld(cards, m_type)
        
        if has_joker and declared_rank:
            j = next(c for c in cards if c.is_joker)
            j.rep_rank = declared_rank
            cartas_reales = [c for c in cards if not c.is_joker]
            if cartas_reales:
                j.rep_suit = cartas_reales[0].suit
                j.is_locked = True 
            print(f"DEBUG: Joker BLINDADO como {j.rep_rank}")

        self._assign_joker_representation(new_meld)
        
        if m_type == MeldType.RUN:
            piv = self._get_circular_pivote(new_meld.cards)
            new_meld.cards.sort(key=lambda c: (self._rank_to_value(c.rank if not c.is_joker else c.rep_rank) - piv) % 13)
            pesos = [(self._rank_to_value(c.rank if not c.is_joker else c.rep_rank) - piv) % 13 for c in new_meld.cards]
            print(f"DEBUG LAY: Escalera ordenada con pivote {piv}. Pesos: {pesos}")
        else:
            new_meld.cards.sort(key=lambda c: self._rank_to_value(c.rank if not c.is_joker else c.rep_rank))

        print(f"DEBUG: Juego finalizado con éxito: {[c.rank if not c.is_joker else c.rep_rank for c in new_meld.cards]}")
        
        self.melds.append(new_meld)
        
        for c in cards: 
            player.hand.remove(c)
            
        player.has_met_objective = True
        
        if len(player.hand) == 0:
            self._check_game_over(player)
            
        return {"ok": True, "message": "Juego bajado"}

    def _action_add_to_meld(self, player, action):
        print(f"DEBUG: Intentando agregar a juego index {action.get('meld_index')}")
        
        if self.turn_phase != "PLAY":
            return {"ok": False, "message": "No podés agregar cartas ahora"}
        if not getattr(player, "has_met_objective", False):
            return {
                "ok": False, 
                "message": "🚫 No podés usar la mesa hasta que bajes tus propios juegos."
            }
        
        meld_index = action.get("meld_index")
        card_indices = action.get("card_indices", [])

        if meld_index is None or not card_indices:
            return {"ok": False, "message": "Faltan datos"}

        try:
            meld = self.melds[meld_index]
            cards = [player.hand[i] for i in card_indices]
        except (IndexError, KeyError):
            return {"ok": False, "message": "Índices inválidos"}

        from game.rules import can_add_to_meld

        original_meld = meld.cards[:]
        original_hand = player.hand[:]
        had_joker_before = meld.has_joker()
        added_joker_from_hand = any(c.is_joker for c in cards)
        joker_stolen = False

        if had_joker_before and not added_joker_from_hand:
            j = meld.joker()
            val_subido = self._rank_to_value(cards[0].rank)
            val_joker = self._rank_to_value(j.rep_rank)

            if meld.is_set():
                replaces_joker = (val_subido == val_joker)
            else:
                replaces_joker = (val_subido == val_joker and cards[0].suit == j.rep_suit)

            if replaces_joker:
                if meld.is_run():
                    j_idx = meld.cards.index(j)
                    if 0 < j_idx < len(meld.cards) - 1:
                        return {"ok": False, "message": "⛔ El comodín está blindado en el centro."}

                choice = action.get("steal_decision")
                
                if choice is None:
                    return {
                        "ok": False, 
                        "type": "ASK_STEAL", 
                        "message": f"🃏 Reemplazo detectado ({j.rep_rank}). ¿Querés robar el comodín?"
                    }
                
                if choice == 's':
                    self.last_joker_stolen = j 
                    self.last_card_used_to_steal = cards[0]
                    self.last_meld_index = meld_index

                    for c in cards:
                        if c in player.hand: player.hand.remove(c)
                    
                    meld.cards.remove(j)
                    player.hand.append(j)
                    
                    self.last_joker_rep_rank = j.rep_rank
                    self.last_joker_rep_suit = j.rep_suit
                    
                    j.rep_rank = None
                    j.rep_suit = None
                    j.is_locked = False
                    
                    for c in cards:
                        if c not in meld.cards: meld.cards.append(c)
                    joker_stolen = True
                    print("🃏 Comodín robado con éxito.")
                
                else:
                    print("DEBUG: El usuario eligió NO robar. Agregando carta normalmente.")

        if not joker_stolen:
            has_new_joker = any(c.is_joker for c in cards)
            declared_rank = action.get("declared_joker_rank")

            if meld.is_run() and has_new_joker and not declared_rank:
                temp_cards = meld.cards + cards
                return {
                    "ok": False,
                    "type": "ASK_JOKER_VALUE",
                    "options": self.get_joker_options(temp_cards),
                    "message": "Elegí qué representa el Joker que estás agregando"
                }

            for c in cards:
                if not can_add_to_meld(meld, c):
                    return {"ok": False, "message": "La carta no encaja en este juego."}
                
                if c.is_joker and declared_rank:
                    c.rep_rank = declared_rank
                    c.rep_suit = meld.cards[0].suit
                    c.is_locked = True

                if c not in meld.cards:
                    meld.cards.append(c)
                if c in player.hand:
                    player.hand.remove(c)

        self._assign_joker_representation(meld)

        if meld.is_run():
            piv = self._get_circular_pivote(meld.cards)
            meld.cards.sort(key=lambda c: (self._rank_to_value(c.rank if not c.is_joker else c.rep_rank) - piv) % 13)
            final_ranks = [f"{c.rank if not c.is_joker else c.rep_rank}" for c in meld.cards]
            pesos = [(self._rank_to_value(c.rank if not c.is_joker else c.rep_rank) - piv) % 13 for c in meld.cards]
            print(f"DEBUG ADD: Orden final tras agregar: {final_ranks}")
            print(f"DEBUG ADD: Pesos finales (relativos al pivote {piv}): {pesos}")
        else:
            meld.cards.sort(key=lambda c: self._rank_to_value(c.rank if not c.is_joker else c.rep_rank))

        if len(player.hand) == 0:
            self._check_game_over(player)
        return {"ok": True, "message": "¡Acción realizada!"}

    def _action_discard(self, player, action):
        idx = action.get("card_index")
        if idx is None or idx >= len(player.hand):
            return {"ok": False, "message": "Carta inválida"}

        card_to_discard = player.hand[idx]

        if card_to_discard.is_joker and hasattr(self, 'last_joker_stolen'):
            print("DEBUG: Rollback detectado. Restaurando el Joker a la mesa.")
            
            meld = self.melds[self.last_meld_index]
            
            if self.last_card_used_to_steal in meld.cards:
                meld.cards.remove(self.last_card_used_to_steal)
                player.hand.append(self.last_card_used_to_steal)
            
            card_to_discard.rep_rank = self.last_joker_rep_rank
            card_to_discard.rep_suit = self.last_joker_rep_suit
            card_to_discard.is_locked = True
            
            if card_to_discard not in meld.cards:
                meld.cards.append(card_to_discard)
            
            player.hand.remove(card_to_discard)

            if meld.is_run():
                piv = self._get_circular_pivote(meld.cards)
                meld.cards.sort(key=lambda c: (self._rank_to_value(c.rank if not c.is_joker else c.rep_rank) - piv) % 13)

            del self.last_joker_stolen
            del self.last_card_used_to_steal
            del self.last_meld_index
            
            self._end_turn()
            return {"ok": True, "message": "Robo cancelado: El Joker volvió a la mesa"}

        card = player.hand.pop(idx)
        self.discard_pile.append(card)

        if self._check_game_over(player):
            return {"ok": True, "game_over": True}

        self._end_turn()
        return {"ok": True, "message": "Acción realizada"}

    def _assign_joker_representation(self, meld):
        if not meld.has_joker(): return 
        joker = next(c for c in meld.cards if c.is_joker)
        
        if getattr(joker, 'is_locked', False) and joker.rep_rank: 
            return
        
        if meld.is_set():
            real_card = next(c for c in meld.cards if not c.is_joker)
            joker.rep_rank = str(real_card.rank)
            joker.rep_suit = real_card.suit
            return

        real_cards = [c for c in meld.cards if not c.is_joker]
        vals = sorted([self._rank_to_value(c.rank) for c in real_cards])
        
        if 1 in vals and 13 in vals:
            vals = sorted([v if v != 1 else 14 for v in vals])

        rep_val = None
        for i in range(len(vals) - 1):
            if vals[i+1] - vals[i] == 2:
                rep_val = vals[i] + 1
                break
        
        if rep_val is None:
            if vals[0] > 1: rep_val = vals[0] - 1
            else: rep_val = vals[-1] + 1

        final_v = (rep_val - 1) % 13 + 1
        joker.rep_rank = self._value_to_rank(final_v)
        joker.rep_suit = real_cards[0].suit
        print(f"DEBUG RUN: Joker auto-asignado como {joker.rep_rank}")

    def _get_circular_pivote(self, cards):
        vals = []
        for c in cards:
            r = c.rank if not c.is_joker else c.rep_rank
            vals.append(self._rank_to_value(r))
        
        vals_s = sorted(list(set(vals)))
        if not vals_s: return 1
        
        if max(vals_s) - min(vals_s) < 10:
            return min(vals_s)
            
        pivote = vals_s[0]
        max_gap = 0
        for i in range(len(vals_s)):
            v_act = vals_s[i]
            v_sig = vals_s[(i + 1) % len(vals_s)]
            gap = (v_sig - v_act) % 13
            if gap > max_gap:
                max_gap = gap
                pivote = v_sig
        
        print(f"DEBUG PIVOTE: Valores únicos {vals_s} | Gap Máximo detectado | Pivote elegido: {pivote}")
        return pivote
    
    def _rank_to_value(self, rank):
        m = {"1": 1, "J": 11, "Q": 12, "K": 13}
        return m.get(rank, int(rank) if str(rank).isdigit() else 0)

    def _value_to_rank(self, val):
        m = {1: "1", 11: "J", 12: "Q", 13: "K"}
        return m.get(val, str(val))

    def _handle_purchase(self, player, out_of_turn=False):
        if player.purchases_used >= self.max_purchases:
            return {"ok": False, "message": "Límite de compras alcanzado"}
        if not self.discard_pile:
            return {"ok": False, "message": "No hay descarte"}
            
        player.hand.append(self.discard_pile.pop())
        extra = 1 if out_of_turn else 2
        for _ in range(extra):
            if not self.deck and len(self.discard_pile) > 1:
                top = self.discard_pile.pop()
                import random
                random.shuffle(self.discard_pile)
                self.deck = self.discard_pile[:]
                self.discard_pile = [top]
            if self.deck:
                player.hand.append(self.deck.pop())
                player.purchases_used += 1
                msg = f"Compraste del pozo (+{extra} {'carta' if extra == 1 else 'cartas'})"
                print(f"DEBUG: {player.name} compró — out_of_turn={out_of_turn} | +{extra} cartas")
                return {"ok": True, "message": msg}

    def calculate_scores(self):
        resultados = []
        winner = next((p for p in self.players if len(p.hand) == 0), None)

        for p in self.players:
            if p == winner:
                puntos_ronda = 0
            else:
                card_points = sum(card.points for card in p.hand)
                purchase_penalty = p.purchases_used * 10
                puntos_ronda = card_points + purchase_penalty

            p.score += puntos_ronda

            resultados.append({
                "name": p.name,
                "points_this_round": puntos_ronda,
                "total_points": p.score
            })
        return resultados
    
    def get_joker_options(self, cards):
        real_cards = [c for c in cards if not c.is_joker]
        detected_suit = real_cards[0].suit if real_cards else None

        if not real_cards:
            return [{"rank": r, "suit": "clubs"} for r in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]]

        all_ranks = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        opciones_finales = []

        piv = self._get_circular_pivote(cards)
        vals_relativos = sorted([
            (self._rank_to_value(c.rank) - piv) % 13 
            for c in real_cards
        ])

        min_v = vals_relativos[0]
        max_v = vals_relativos[-1]

        prev_abs = (min_v - 1 + piv - 1) % 13 + 1
        next_abs = (max_v + piv) % 13 + 1

        opciones_finales.append(all_ranks[prev_abs - 1])
        opciones_finales.append(all_ranks[next_abs - 1])

        for i in range(min_v, max_v):
            if i not in vals_relativos:
                abs_v = (i + piv - 1) % 13 + 1
                opciones_finales = [all_ranks[abs_v - 1]]
                break

        ranks_unicos = sorted(list(set(opciones_finales)), key=lambda r: all_ranks.index(r))
        return [{"rank": r, "suit": detected_suit} for r in ranks_unicos]

    def start_next_round(self):
        self.round_number += 1
        if self.round_number > 7:
            self.round_number = 1
        
        self.deck = create_deck()
        self.melds = []
        self.discard_pile = [self.deck.pop()]
        
        for p in self.players:
            p.hand = []
            p.has_met_objective = False
            for _ in range(11):
                if self.deck:
                    p.hand.append(self.deck.pop())
        
        self.turn_phase = "DRAW"
        # ✅ El siguiente jugador empieza la nueva ronda
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.game_over = False
        self.winner = None

    def get_current_player(self):
        return self.players[self.current_player_index]