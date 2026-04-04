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

salas = {}


def generar_codigo():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


def get_card_data(card):
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
    game = sala_data["game"]
    players = game.players

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

    my_hand = []
    if for_player_index < len(players):
        for card in players[for_player_index].hand:
            my_hand.append(get_card_data(card))

    melds = []
    for meld in game.melds:
        melds.append({
            "type": meld.type.name,
            "cards": [get_card_data(c) for c in meld.cards],
        })

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
    sala = salas.get(codigo)
    if not sala:
        return
    for ws in sala["connections"].values():
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            pass


async def preguntar_siguiente_jugador(codigo: str):
    """Pregunta al siguiente jugador pendiente si quiere la carta del pozo."""
    sala = salas.get(codigo)
    if not sala:
        return

    pendientes = sala.get("compra_pendiente", [])

    if not pendientes or not sala["game"].discard_pile:
        sala["compra_pendiente"] = []
        await broadcast_state(codigo)
        return

    idx = pendientes[0]
    jugador = sala["game"].players[idx]

    await send_to_player(codigo, idx, {
        "type": "ASK_OUT_OF_TURN",
        "buyer_index": idx,
        "player_name": jugador.name,
    })


@app.websocket("/ws/{codigo}/{player_index}")
async def websocket_endpoint(websocket: WebSocket, codigo: str, player_index: int):
    await websocket.accept()
    print(f"Jugador {player_index} conectado a sala {codigo}")

    sala = salas.get(codigo)
    if not sala:
        await websocket.send_text(json.dumps({"type": "error", "message": "Sala no encontrada"}))
        await websocket.close()
        return

    sala["connections"][player_index] = websocket
    sala["connected"].add(player_index)

    player_name = sala["game"].players[player_index].name
    await broadcast_message(codigo, {
        "type": "player_joined",
        "message": f"{player_name} se conectó",
        "player_name": player_name,
        "connected_count": len(sala["connected"]),
        "total_players": len(sala["game"].players),
    })

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
    sala = salas.get(codigo)
    if not sala:
        return

    game = sala["game"]
    action_type = action.get("type")

    # ✅ Respuesta a compra fuera de turno
    if action_type == "OUT_OF_TURN_RESPONSE":
        decision = action.get("decision")
        buyer_index = action.get("buyer_index")
        pendientes = sala.get("compra_pendiente", [])

        if not pendientes or pendientes[0] != buyer_index:
            return

        if decision == "si":
            # Jugador en turno → DRAW del descarte (+2 cartas)
            # Jugador fuera de turno → OUT_OF_TURN_PURCHASE (+1 carta)
            es_turno_actual = buyer_index == game.current_player_index
            if es_turno_actual:
                res = game.apply_action({"type": "DRAW", "source": "discard"})
            else:
                res = game.apply_action({
                    "type": "OUT_OF_TURN_PURCHASE",
                    "buyer_index": buyer_index
                })

            if res["ok"]:
                sala["compra_pendiente"] = []
                sala["compra_bloqueada"] = True
                await broadcast_state(codigo)
                await broadcast_message(codigo, {
                    "type": "info",
                    "message": res.get("message", f"{game.players[buyer_index].name} compró del pozo")
                })
            else:
                await send_to_player(codigo, buyer_index, {
                    "type": "error",
                    "message": res.get("message", "No se pudo comprar")
                })
                sala["compra_pendiente"] = pendientes[1:]
                await preguntar_siguiente_jugador(codigo)
        else:
            sala["compra_pendiente"] = pendientes[1:]
            await preguntar_siguiente_jugador(codigo)
        return

    # Verificamos turno para acciones normales
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
        if game.winner:
            await broadcast_message(codigo, {
                "type": "round_over",
                "winner": game.winner.name,
                "scores": [{"name": p.name, "score": p.score} for p in game.players],
            })

        await broadcast_state(codigo)

        if res.get("message"):
            await broadcast_message(codigo, {
                "type": "info",
                "message": res["message"],
            })

        # ✅ Después de un descarte → preguntar SOLO al jugador en turno y los demás
        # El jugador que descartó NO se pregunta — ya terminó su turno
        if action_type == "DISCARD" and not game.winner:
            n = len(game.players)
            if n >= 2 and game.discard_pile:
                # current_player_index ya avanzó al siguiente jugador
                # Preguntamos en orden: primero el del turno, luego los demás
                jugadores_a_preguntar = []
                for offset in range(n - 1):
                    idx = (game.current_player_index + offset) % n
                    jugadores_a_preguntar.append(idx)

                sala["compra_pendiente"] = jugadores_a_preguntar
                sala["compra_bloqueada"] = False
                await preguntar_siguiente_jugador(codigo)

    else:
        if res.get("type") in ("ASK_JOKER_VALUE", "ASK_STEAL"):
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


@app.post("/sala/crear")
async def crear_sala(data: dict):
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
        "connections": {},
        "connected": set(),
        "compra_pendiente": [],
        "compra_bloqueada": False,
    }

    print(f"Sala {codigo} creada con jugadores: {nombres}")

    return {
        "ok": True,
        "codigo": codigo,
        "jugadores": [{"index": i, "name": p.name} for i, p in enumerate(players)],
    }


@app.post("/sala/siguiente_ronda/{codigo}")
async def siguiente_ronda(codigo: str):
    sala = salas.get(codigo)
    if not sala:
        return {"ok": False, "message": "Sala no encontrada"}

    sala["game"].start_next_round()
    sala["compra_pendiente"] = []
    sala["compra_bloqueada"] = False
    await broadcast_state(codigo)
    await broadcast_message(codigo, {"type": "new_round", "message": f"Ronda {sala['game'].round_number} iniciada"})
    return {"ok": True}


@app.get("/sala/{codigo}")
async def info_sala(codigo: str):
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