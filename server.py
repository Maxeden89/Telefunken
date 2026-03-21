import asyncio
import json
import random
import string
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from game.game import Game
from game.player import Player

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SALAS EN MEMORIA ---
# salas = { "ABCD": { "game": Game, "players": { "ABCD_0": ws, ... }, "player_names": [...] } }
salas = {}


def generar_codigo():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


def get_card_data(card):
    """Convierte una carta a dict serializable."""
    if card.is_joker:
        return {
            "is_joker": True,
            "rank": "JOKER",
            "suit": None,
            "rep_rank": getattr(card, "rep_rank", None),
            "rep_suit": str(getattr(card, "rep_suit", None)) if getattr(card, "rep_suit", None) else None,
        }
    raw = card.suit.name if hasattr(card.suit, "name") else str(card.suit)
    suit_name = raw.split(".")[-1].strip().capitalize()
    return {
        "is_joker": False,
        "rank": card.rank,
        "suit": suit_name,
        "rep_rank": None,
        "rep_suit": None,
    }


def get_game_state(sala_data, for_player_index):
    """
    Construye el estado del juego para un jugador específico.
    Cada jugador solo ve sus propias cartas.
    """
    game = sala_data["game"]
    players = game.players

    # Info de todos los jugadores (sin sus cartas privadas)
    players_info = []
    for i, p in enumerate(players):
        players_info.append({
            "name": p.name,
            "index": i,
            "hand_count": len(p.hand),
            "purchases_used": p.purchases_used,
            "has_met_objective": p.has_met_objective,
            "score": p.score,
            "is_current": i == game.current_player_index,
        })

    # Solo las cartas del jugador que recibe el estado
    my_hand = []
    if for_player_index < len(players):
        for card in players[for_player_index].hand:
            my_hand.append(get_card_data(card))

    # Juegos en mesa
    melds = []
    for meld in game.melds:
        melds.append({
            "type": meld.type.name,
            "cards": [get_card_data(c) for c in meld.cards],
        })

    # Carta del pozo
    discard_top = None
    if game.discard_pile:
        discard_top = get_card_data(game.discard_pile[-1])

    return {
        "type": "game_state",
        "round_number": game.round_number,
        "turn_phase": game.turn_phase,
        "current_player_index": game.current_player_index,
        "players": players_info,
        "my_hand": my_hand,
        "my_index": for_player_index,
        "melds": melds,
        "discard_top": discard_top,
        "winner": players[game.winner].name if game.winner else None,
        "game_over": game.game_over,
    }


async def broadcast_state(codigo):
    """Manda el estado actualizado a cada jugador de la sala."""
    sala = salas.get(codigo)
    if not sala:
        return
    for player_index, ws in sala["connections"].items():
        try:
            state = get_game_state(sala, player_index)
            await ws.send_text(json.dumps(state))
        except Exception as e:
            print(f"Error enviando estado a jugador {player_index}: {e}")


async def send_to_player(codigo, player_index, msg: dict):
    """Manda un mensaje a un jugador específico."""
    sala = salas.get(codigo)
    if not sala:
        return
    ws = sala["connections"].get(player_index)
    if ws:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception as e:
            print(f"Error enviando mensaje a jugador {player_index}: {e}")


async def broadcast_message(codigo, msg: dict):
    """Manda un mensaje a todos los jugadores de la sala."""
    sala = salas.get(codigo)
    if not sala:
        return
    for ws in sala["connections"].values():
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            pass


@app.websocket("/ws/{codigo}/{player_index}")
async def websocket_endpoint(websocket: WebSocket, codigo: str, player_index: int):
    await websocket.accept()
    print(f"Jugador {player_index} conectado a sala {codigo}")

    sala = salas.get(codigo)
    if not sala:
        await websocket.send_text(json.dumps({"type": "error", "message": "Sala no encontrada"}))
        await websocket.close()
        return

    # Registramos la conexión
    sala["connections"][player_index] = websocket
    sala["connected"].add(player_index)

    # Avisamos a todos que se conectó
    player_name = sala["game"].players[player_index].name
    await broadcast_message(codigo, {
        "type": "player_joined",
        "message": f"{player_name} se conectó",
        "player_name": player_name,
        "connected_count": len(sala["connected"]),
        "total_players": len(sala["game"].players),
    })

    # Si todos están conectados, mandamos el estado inicial
    if len(sala["connected"]) == len(sala["game"].players):
        await broadcast_message(codigo, {"type": "game_start", "message": "¡Todos conectados! Arranca la partida."})
        await broadcast_state(codigo)

    try:
        while True:
            data = await websocket.receive_text()
            action = json.loads(data)
            print(f"Acción de jugador {player_index}: {action}")

            await handle_action(codigo, player_index, action)

    except WebSocketDisconnect:
        sala["connected"].discard(player_index)
        sala["connections"].pop(player_index, None)
        print(f"Jugador {player_index} desconectado de sala {codigo}")
        await broadcast_message(codigo, {
            "type": "player_disconnected",
            "message": f"{player_name} se desconectó",
        })


async def handle_action(codigo: str, player_index: int, action: dict):
    """Procesa una acción del juego y broadcast el nuevo estado."""
    sala = salas.get(codigo)
    if not sala:
        return

    game = sala["game"]
    action_type = action.get("type")

    # Verificamos que sea el turno de este jugador para acciones de juego
    acciones_de_turno = {"DRAW", "LAY_MELD", "LAY_ALL_OBJECTIVE", "ADD_TO_MELD", "DISCARD"}
    if action_type in acciones_de_turno and player_index != game.current_player_index:
        await send_to_player(codigo, player_index, {
            "type": "error",
            "message": "No es tu turno"
        })
        return

    # Aplicamos la acción al motor
    res = game.apply_action(action)

    if res["ok"]:
        # Si hay ganador, calculamos scores y avisamos
        if game.winner:
            await broadcast_message(codigo, {
                "type": "round_over",
                "winner": game.winner.name,
                "scores": [{"name": p.name, "score": p.score} for p in game.players],
            })

        # Mandamos estado actualizado a todos
        await broadcast_state(codigo)

        # Si el resultado tiene mensaje, lo mandamos
        if res.get("message"):
            await broadcast_message(codigo, {
                "type": "info",
                "message": res["message"],
            })

    else:
        if res.get("type") in ("ASK_JOKER_VALUE", "ASK_STEAL"):
    # ✅ Serializamos las opciones del Joker antes de mandar
            if "options" in res:
                options_serializables = []
                for opt in res["options"]:
                    if isinstance(opt, dict):
                        suit = opt.get("suit")
                        options_serializables.append({
                            "rank": opt.get("rank"),
                            "suit": suit.name if hasattr(suit, "name") else str(suit) if suit else None
                        })
                    else:
                        options_serializables.append(opt)
                res["options"] = options_serializables
            await send_to_player(codigo, player_index, res)
        else:
            await send_to_player(codigo, player_index, {
                "type": "error",
                "message": res.get("message", "Acción inválida"),
            })

    # Compra fuera de turno — acción especial
    if action_type == "OUT_OF_TURN_PURCHASE":
        res = game.apply_action(action)
        if res["ok"]:
            await broadcast_state(codigo)
            await broadcast_message(codigo, {
                "type": "info",
                "message": res["message"],
            })
        else:
            await send_to_player(codigo, player_index, {
                "type": "error",
                "message": res.get("message", "No se pudo comprar"),
            })


@app.post("/sala/crear")
async def crear_sala(data: dict):
    """Crea una nueva sala de juego."""
    nombres = data.get("nombres", [])
    if len(nombres) < 2 or len(nombres) > 5:
        return {"ok": False, "message": "Se necesitan entre 2 y 5 jugadores"}

    codigo = generar_codigo()
    while codigo in salas:
        codigo = generar_codigo()

    players = [Player(nombre) for nombre in nombres]
    game = Game(players)

    salas[codigo] = {
        "game": game,
        "connections": {},   # { player_index: websocket }
        "connected": set(),  # índices conectados
    }

    print(f"Sala {codigo} creada con jugadores: {nombres}")

    return {
        "ok": True,
        "codigo": codigo,
        "jugadores": [{"index": i, "name": p.name} for i, p in enumerate(players)],
    }


@app.post("/sala/siguiente_ronda/{codigo}")
async def siguiente_ronda(codigo: str):
    """Avanza a la siguiente ronda."""
    sala = salas.get(codigo)
    if not sala:
        return {"ok": False, "message": "Sala no encontrada"}

    sala["game"].start_next_round()
    await broadcast_state(codigo)
    await broadcast_message(codigo, {"type": "new_round", "message": f"Ronda {sala['game'].round_number} iniciada"})
    return {"ok": True}


@app.get("/sala/{codigo}")
async def info_sala(codigo: str):
    """Info básica de una sala."""
    sala = salas.get(codigo)
    if not sala:
        return {"ok": False, "message": "Sala no encontrada"}
    return {
        "ok": True,
        "codigo": codigo,
        "jugadores": [p.name for p in sala["game"].players],
        "connected": len(sala["connected"]),
        "round": sala["game"].round_number,
    }


@app.get("/")
async def root():
    return {"status": "Telefunken server running 🃏"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)