from .meld import MeldType

def is_valid_set(cards):
    if len(cards) < 3: return False
    jokers = [c for c in cards if c.is_joker]
    if len(jokers) > 1: return False
    values = [c.rank for c in cards if not c.is_joker]
    if not values: return True  
    return len(set(values)) == 1

def is_valid_run(cards):
    if len(cards) < 3:
        return False

    # Separar jokers y cartas reales
    jokers = [c for c in cards if c.is_joker]
    real_cards = [c for c in cards if not c.is_joker]

    if not real_cards:
        return True  # solo jokers → se acepta como run (depende de tus reglas)

    # Verificar mismo palo
    suit = real_cards[0].suit
    if not all(c.suit == suit for c in real_cards):
        return False

    # Obtenemos valores numéricos (1..13)
    values = sorted(c.value for c in real_cards)

    # Eliminar duplicados → no permitidos en run (salvo jokers)
    if len(values) != len(set(values)):
        return False

    n = len(cards)
    needed_real = n - len(jokers)

    if needed_real <= 0:
        return True

    # Intentamos cada posible carta como "la más baja" de la secuencia real
    for lowest in values:
        # Generamos la secuencia esperada empezando desde lowest
        expected = []
        current = lowest
        for _ in range(needed_real):
            expected.append(current)
            current = current % 13 + 1   # 13 → 1, 12 → 13, 1 → 2, etc.

        # ¿Podemos cubrir esta secuencia exacta con nuestras cartas reales?
        # (los jokers cubren lo que falte)
        missing = 0
        used = set()
        for val in expected:
            if val in values and val not in used:
                used.add(val)
            else:
                missing += 1

        if missing <= len(jokers):
            return True

    # Última chance: probar empezando desde el As hacia arriba
    # (algunos casos raros donde lowest no es el inicio real)
    # Pero normalmente el loop anterior ya lo cubre

    return False

def can_form_sequence(values, jokers):
    """
    Determina si se puede formar una escalera y sirve como validador.
    """
    # Si devuelve un valor (o None si no hay jokers), es válida
    if jokers == 0:
        # Validación estándar de escalera sin jokers
        v_sorted = sorted(values)
        # Caso As circular (K-A-2)
        if 1 in v_sorted and 13 in v_sorted:
            v_alt = sorted([v if v != 1 else 14 for v in v_sorted])
            return all(v_alt[i+1] - v_alt[i] == 1 for i in range(len(v_alt)-1))
        return all(v_sorted[i+1] - v_sorted[i] == 1 for i in range(len(v_sorted)-1))
    
    # Si hay jokers, chequeamos si existe un valor que complete el hueco
    return get_joker_needed_value(values, jokers) is not None

def get_joker_needed_value(values, jokers):
    """
    Lógica interna para encontrar qué carta reemplaza el Joker.
    """
    target_len = len(values) + jokers
    if target_len > 13: return None

    for start in range(1, 14):
        needed_vals = []
        for i in range(target_len):
            val = (start + i - 1) % 13 + 1
            if val not in values:
                needed_vals.append(val)
        
        if len(needed_vals) == jokers:
            return needed_vals[0] # Retorna el primer valor que falta
    return None

def detect_meld_type(cards):
    if is_valid_set(cards): return MeldType.SET
    if is_valid_run(cards): return MeldType.RUN
    return None

def is_valid_meld(cards):
    if sum(1 for c in cards if c.is_joker) > 1: return False
    return detect_meld_type(cards) is not None

def can_add_to_meld(meld, card):
    # 1. Límite de cartas (Seguridad total)
    if len(meld.cards) >= 13:
        return False

    # 2. Manejo de Identidad (¿Qué representa la carta?)
    # Obtenemos el rango real o el que representa el Joker
    r_nueva = card.rank if not card.is_joker else getattr(card, 'rep_rank', None)
    
    # Obtenemos todos los rangos que YA están en la mesa
    ranks_en_mesa = [c.rank if not c.is_joker else c.rep_rank for c in meld.cards]
    
    # 3. Reglas para Escaleras (RUN)
    if meld.is_run():
        # A) Evitar Duplicados (Chequeamos si el rango ya existe en la mesa)
        # Si r_nueva es None (Joker nuevo), saltamos esto y validamos abajo
        if r_nueva and str(r_nueva) in [str(r) for r in ranks_en_mesa]:
            return False
            
        # B) Mismo Palo
        # Buscamos una carta real para comparar el palo
        carta_real = next((c for c in meld.cards if not c.is_joker), None)
        if carta_real and not card.is_joker and card.suit != carta_real.suit:
            return False

    # 4. Reglas para Piernas (SET)
    elif meld.is_set():
        # En un SET no puede haber más de 4 cartas (una de cada palo) o 5 con Joker
        if len(meld.cards) >= 8: return False
        
        # Debe coincidir el rango con las cartas reales del juego
        carta_real = next((c for c in meld.cards if not c.is_joker), None)
        if carta_real and not card.is_joker and card.rank != carta_real.rank:
            return False

    # 5. Validación final de estructura
    # Si es un Joker nuevo (sin rep_rank aún), lo dejamos pasar para que el motor
    # le asigne un valor en el siguiente paso.
    if card.is_joker:
        # Solo permitimos un Joker por juego (según tu regla original)
        return not any(c.is_joker for c in meld.cards)

    test_cards = meld.cards + [card]
    return is_valid_meld(test_cards)

def run_joker_is_replaced(meld):
    """Verifica si el joker está cubriendo un valor que ya no hace falta."""
    if not meld.has_joker() or meld.is_set(): return False
    reales = [c.value for c in meld.cards if not c.is_joker]
    # Si la escalera es válida sin el joker, es que fue reemplazado o sobra
    return can_form_sequence(reales, 0)