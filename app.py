import flet as ft
import asyncio
import json
import websockets
import httpx
import base64   
import os

def svg_to_b64(svg: str) -> str:
    return base64.b64encode(svg.encode()).decode()

SUITS_SVG = {
    "Spades": svg_to_b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M50 5 C50 5 5 45 5 65 C5 80 20 85 35 78 C30 88 25 95 15 98 L85 98 C75 95 70 88 65 78 C80 85 95 80 95 65 C95 45 50 5 50 5Z" fill="black"/></svg>'),
    "Clubs": svg_to_b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="35" r="22" fill="black"/><circle cx="25" cy="60" r="22" fill="black"/><circle cx="75" cy="60" r="22" fill="black"/><rect x="40" y="55" width="20" height="35" fill="black"/><rect x="30" y="85" width="40" height="10" fill="black"/></svg>'),
    "Hearts": svg_to_b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M50 85 Q5 55 5 30 Q5 5 30 5 Q42 5 50 18 Q58 5 70 5 Q95 5 95 30 Q95 55 50 85 Z" fill="#e53935"/></svg>'),
    "Diamonds": svg_to_b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><polygon points="50,5 95,50 50,95 5,50" fill="#e53935"/></svg>'),
}

SUITS_COLOR = {
    "Hearts": ft.colors.RED_700,
    "Diamonds": ft.colors.RED_700,
    "Spades": ft.colors.BLACK,
    "Clubs": ft.colors.BLACK,
}

# ✅ URL del servidor — cambiá por la URL de Railway cuando desplegues
SERVER_URL = "https://telefunken-1.onrender.com"
WS_URL = "wss://telefunken-1.onrender.com"


# --- CONFIGURACIÓN DE ESTILO DE CARTAS ---
def get_card_style(card: dict):
    if card.get("is_joker"):
        return None, ft.colors.PURPLE_500
    suit_name = card.get("suit", "")
    svg = SUITS_SVG.get(suit_name)
    color = SUITS_COLOR.get(suit_name, ft.colors.BLACK)
    return svg, color


async def main(page: ft.Page):
    page.title = "Telefunken Pro"
    page.bgcolor = ft.colors.GREEN_900
    page.padding = 20
    page.window_width = 1100
    page.window_height = 850

    # --- ESTADO DEL CLIENTE ---
    state = {
        "codigo": None,           # Código de sala
        "my_index": None,         # Índice de este jugador
        "game_state": None,       # Último estado recibido del servidor
        "selected_indices": [],
        "pending_melds": [],
        "dragging_index": None,
        "timer_active": False,
        "timer_seconds": 0,
        "timer_task": None,
        "pozo_bloqueado": False,
        "ws": None,               # WebSocket activo
    }

    # --- CONTENEDORES UI ---
    mesa_container = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    mano_container = ft.Row(wrap=True, spacing=10, alignment=ft.MainAxisAlignment.CENTER, tight=True)
    info_text = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5)
    descarte_btn = ft.Container(width=75, height=110, bgcolor=ft.colors.WHITE24, border_radius=10)

    # --- TIMER WIDGET ---
    timer_text = ft.Text("30", size=20, weight="bold", color=ft.colors.WHITE)
    timer_widget = ft.Container(
        content=timer_text,
        bgcolor=ft.colors.GREEN_700,
        border_radius=25,
        width=50, height=50,
        alignment=ft.Alignment(0, 0),
        visible=False,
    )

    # =========================================
    # PANTALLA DE INICIO — Crear/Unirse a sala
    # =========================================
    def mostrar_pantalla_inicio():
        page.controls.clear()

        titulo = ft.Text("TELEFUNKEN", size=48, weight="bold", color=ft.colors.AMBER_400)
        subtitulo = ft.Text("el juego de cartas", size=14, color=ft.colors.WHITE54)

        # --- CREAR SALA ---
        campos_nombres = [ft.TextField(label=f"Jugador {i+1}", width=200) for i in range(2)]
        slider_jugadores = ft.Slider(min=2, max=5, divisions=3, value=2, label="{value}")

        def on_slider_change(e):
            n = int(e.control.value)
            campos_nombres.clear()
            for i in range(n):
                campos_nombres.append(ft.TextField(label=f"Jugador {i+1}", width=200))
            col_nombres.controls = campos_nombres
            page.update()

        slider_jugadores.on_change = on_slider_change
        col_nombres = ft.Column(campos_nombres, spacing=8)

        async def crear_sala(e):
            nombres = [c.value.strip() or f"Jugador {i+1}" for i, c in enumerate(campos_nombres)]
            async with httpx.AsyncClient() as client:
                res = await client.post(f"{SERVER_URL}/sala/crear", json={"nombres": nombres})
                data = res.json()
            if data["ok"]:
                state["codigo"] = data["codigo"]
                # Buscamos nuestro índice — el que creó es el jugador 0
                state["my_index"] = 0
                mostrar_sala_espera(data["codigo"], data["jugadores"])
            else:
                mostrar_mensaje(data.get("message", "Error"))

        btn_crear = ft.FilledButton("Crear Sala", on_click=crear_sala, bgcolor=ft.colors.GREEN_700)

        # --- UNIRSE A SALA ---
        campo_codigo = ft.TextField(label="Código de sala", width=200)
        campo_nombre = ft.TextField(label="Tu nombre", width=200)

        async def unirse_sala(e):
            codigo = campo_codigo.value.strip().upper()
            nombre = campo_nombre.value.strip() or "Jugador"
            if not codigo:
                mostrar_mensaje("Ingresá el código de sala")
                return

            async with httpx.AsyncClient() as client:
                res = await client.get(f"{SERVER_URL}/sala/{codigo}")
                data = res.json()

            if not data.get("ok"):
                mostrar_mensaje("Sala no encontrada")
                return

            # Encontramos el primer índice disponible
            jugadores = data["jugadores"]
            connected = data["connected"]
            my_index = connected  # El próximo en conectarse

            if my_index >= len(jugadores):
                mostrar_mensaje("La sala está llena")
                return

            state["codigo"] = codigo
            state["my_index"] = my_index
            mostrar_sala_espera(codigo, [{"index": i, "name": n} for i, n in enumerate(jugadores)])

        btn_unirse = ft.FilledButton("Unirse", on_click=unirse_sala, bgcolor=ft.colors.BLUE_700)

        page.add(
            ft.Column([
                ft.Container(height=40),
                ft.Column([titulo, subtitulo], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=30),
                ft.Row([
                    # Panel Crear
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Crear Sala", size=18, weight="bold", color=ft.colors.WHITE),
                            ft.Text("Jugadores:", size=12, color=ft.colors.WHITE54),
                            slider_jugadores,
                            col_nombres,
                            ft.Container(height=10),
                            btn_crear,
                        ], spacing=8),
                        bgcolor=ft.colors.WHITE10,
                        border_radius=12,
                        padding=20,
                        width=280,
                    ),
                    ft.Container(width=30),
                    # Panel Unirse
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Unirse a Sala", size=18, weight="bold", color=ft.colors.WHITE),
                            campo_codigo,
                            campo_nombre,
                            ft.Container(height=10),
                            btn_unirse,
                        ], spacing=8),
                        bgcolor=ft.colors.WHITE10,
                        border_radius=12,
                        padding=20,
                        width=280,
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        )
        page.update()

    def mostrar_sala_espera(codigo, jugadores):
        """Pantalla de espera mientras todos se conectan."""
        page.controls.clear()
        page.add(
            ft.Column([
                ft.Text("Esperando jugadores...", size=24, weight="bold", color=ft.colors.WHITE),
                ft.Text(f"Código de sala:", size=16, color=ft.colors.WHITE54),
                ft.Container(
                    content=ft.Text(codigo, size=48, weight="bold", color=ft.colors.AMBER_400),
                    bgcolor=ft.colors.WHITE10,
                    border_radius=12,
                    padding=ft.Padding(30, 10, 30, 10),
                ),
                ft.Text("Compartí este código con tus amigos", size=14, color=ft.colors.WHITE54),
                ft.Container(height=20),
                ft.Column([
                    ft.Text(f"👤 {j['name']}", color=ft.colors.WHITE, size=16)
                    for j in jugadores
                ]),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               alignment=ft.MainAxisAlignment.CENTER, expand=True)
        )
        page.update()

        # Conectamos el WebSocket
        asyncio.create_task(conectar_websocket())

    # =========================================
    # WEBSOCKET — Conexión y recepción
    # =========================================
    async def conectar_websocket():
        codigo = state["codigo"]
        my_index = state["my_index"]
        ws_uri = f"{WS_URL}/ws/{codigo}/{my_index}"

        try:
            async with websockets.connect(ws_uri) as ws:
                state["ws"] = ws
                print(f"Conectado al servidor: {ws_uri}")

                async for message in ws:
                    data = json.loads(message)
                    await procesar_mensaje(data)

        except Exception as e:
            print(f"Error WebSocket: {e}")
            mostrar_mensaje(f"Error de conexión: {e}")

    async def procesar_mensaje(data: dict):
        msg_type = data.get("type")

        if msg_type == "game_state":
            state["game_state"] = data
            # Si la pantalla de juego no está visible, la mostramos
            if not any(isinstance(c, ft.Column) and c.expand for c in page.controls):
                mostrar_pantalla_juego()
            else:
                actualizar_interfaz()

        elif msg_type == "game_start":
            mostrar_pantalla_juego()
            mostrar_mensaje(data.get("message", "¡Arranca la partida!"))

        elif msg_type == "player_joined":
            mostrar_mensaje(data.get("message", ""))
            # Actualizamos la sala de espera si corresponde
            page.update()

        elif msg_type == "round_over":
            detener_timer()
            winner = data.get("winner")
            scores = data.get("scores", [])
            lineas = "\n".join([f"{s['name']}: {s['score']} pts" for s in scores])
            dialogo_final = ft.AlertDialog(
                title=ft.Text("🏁 ¡FIN DE LA RONDA!"),
                content=ft.Text(f"Ganador: {winner}\n\nPuntajes:\n{lineas}"),
                actions=[ft.FilledButton("Siguiente Ronda", on_click=siguiente_ronda)]
            )
            page.overlay.append(dialogo_final)
            dialogo_final.open = True
            page.update()

        elif msg_type == "new_round":
            state["selected_indices"].clear()
            state["pending_melds"].clear()
            state["pozo_bloqueado"] = False
            if page.overlay:
                for c in page.overlay:
                    if isinstance(c, ft.AlertDialog):
                        c.open = False
            mostrar_mensaje(data.get("message", "Nueva ronda"))
            page.update()

        elif msg_type == "info":
            mostrar_mensaje(data.get("message", ""))

        elif msg_type == "error":
            mostrar_mensaje(data.get("message", "Error"))

        elif msg_type == "ASK_JOKER_VALUE":
            accion_original = state.get("last_action", {})
            group_idx = data.get("group_index")

            def al_elegir(rango):
                accion = accion_original.copy()
                if group_idx is not None:
                    accion[f"declared_joker_rank_{group_idx}"] = rango
                else:
                    accion["declared_joker_rank"] = rango
                page.run_task(enviar_accion, accion)

            mostrar_dialogo_joker(
                titulo="VALOR DEL COMODÍN",
                mensaje=data.get("message", "Elegí el valor del Joker"),
                opciones=data.get("options", []),
                on_choice=al_elegir
            )

        elif msg_type == "ASK_STEAL":
            mostrar_dialogo_joker(
                titulo="SUSTITUCIÓN",
                mensaje=data.get("message", ""),
                on_si=lambda: page.run_task(enviar_accion, {"type": "ADD_TO_MELD", "steal_decision": "s", **state.get("last_action", {})}),
                on_no=lambda: page.run_task(enviar_accion, {"type": "ADD_TO_MELD", "steal_decision": "n", **state.get("last_action", {})})
            )

        # Timer — el servidor manda el estado y el cliente maneja el timer localmente
        gs = state.get("game_state")
        if gs:
            fase = gs.get("turn_phase", "DRAW")
            es_mi_turno = gs.get("current_player_index") == state["my_index"]
            if es_mi_turno:
                if not state["timer_active"]:
                    iniciar_timer(fase)
            else:
                detener_timer()

    async def on_joker_elegido(rango, original_data):
        """Reenvía la acción con el joker declarado."""
        accion = state.get("last_action", {}).copy()
        group_idx = original_data.get("group_index")
        if group_idx is not None:
            accion[f"declared_joker_rank_{group_idx}"] = rango
        else:
            accion["declared_joker_rank"] = rango
        await enviar_accion(accion)

    async def enviar_accion(accion: dict):
        """Manda una acción al servidor."""
        ws = state.get("ws")
        if ws:
            try:
                await ws.send(json.dumps(accion))
            except Exception as e:
                print(f"Error enviando acción: {e}")
                mostrar_mensaje("Error de conexión")

    async def siguiente_ronda(e):
        async with httpx.AsyncClient() as client:
            await client.post(f"{SERVER_URL}/sala/siguiente_ronda/{state['codigo']}")

    # =========================================
    # TIMER
    # =========================================
    def get_timer_duracion(fase):
        gs = state.get("game_state", {})
        round_number = gs.get("round_number", 1)
        if fase == "DRAW":
            return 10
        return 30 + (round_number - 1) * 15

    def get_timer_color(segundos, fase):
        if fase == "DRAW":
            return ft.colors.BLUE_700 if segundos > 5 else ft.colors.RED_700
        if segundos <= 5:
            return ft.colors.RED_700
        elif segundos <= 15:
            return ft.colors.AMBER_700
        return ft.colors.GREEN_700

    def actualizar_timer_ui(segundos, fase):
        timer_text.value = str(segundos)
        timer_widget.bgcolor = get_timer_color(segundos, fase)
        timer_widget.visible = True
        try:
            page.update()
        except Exception:
            pass

    def detener_timer():
        state["timer_active"] = False
        if state["timer_task"] is not None:
            try:
                state["timer_task"].cancel()
            except Exception:
                pass
            state["timer_task"] = None
        timer_widget.visible = False
        try:
            page.update()
        except Exception:
            pass

    async def countdown(fase):
        try:
            while state["timer_active"] and state["timer_seconds"] > 0:
                await asyncio.sleep(1)
                if not state["timer_active"]:
                    return
                state["timer_seconds"] -= 1
                actualizar_timer_ui(state["timer_seconds"], fase)
            if state["timer_active"] and state["timer_seconds"] <= 0:
                state["timer_active"] = False
                if fase == "DRAW":
                    await enviar_accion({"type": "DRAW", "source": "deck"})
                else:
                    gs = state.get("game_state", {})
                    my_hand = gs.get("my_hand", [])
                    if my_hand:
                        await enviar_accion({"type": "DISCARD", "card_index": 0})
        except asyncio.CancelledError:
            pass

    def iniciar_timer(fase):
        detener_timer()
        segundos = get_timer_duracion(fase)
        state["timer_seconds"] = segundos
        state["timer_active"] = True
        actualizar_timer_ui(segundos, fase)
        state["timer_task"] = page.run_task(countdown, fase)

    # =========================================
    # UI DEL JUEGO
    # =========================================
    def mostrar_pantalla_juego():
        page.controls.clear()
        page.add(
            ft.Column([
                info_text,
                ft.Divider(color="white24"),
                mesa_container,
                ft.Divider(color="white24"),
                ft.Row([
                    ft.Column([ft.Text("Pozo"), descarte_btn], horizontal_alignment="center"),
                    btn_mazo, btn_descarte_btn,
                    ft.VerticalDivider(),
                    btn_preparar, btn_cancelar, btn_bajar,
                    ft.VerticalDivider(),
                    btn_tirar
                ], alignment=ft.MainAxisAlignment.CENTER, height=140),
                mano_container
            ], expand=True)
        )
        actualizar_interfaz()

    def actualizar_interfaz():
        render_hand()
        render_table()
        page.update()

    def mostrar_mensaje(texto):
        page.snack_bar = ft.SnackBar(ft.Text(texto))
        page.snack_bar.open = True
        page.update()

    def mostrar_dialogo_joker(titulo, mensaje, opciones=None, on_choice=None, on_si=None, on_no=None):
        def cerrar_dialogo():
            dialogo.open = False
            page.update()

        controles = []
        acciones = []

        if opciones:
            controles.append(ft.Text(mensaje, weight="bold"))
            opciones_row = ft.Row(wrap=True, spacing=10, alignment=ft.MainAxisAlignment.CENTER)

            suits_icons = {"hearts": "♥", "diamonds": "♦", "spades": "♠", "clubs": "♣"}
            suits_colors = {
                "hearts": ft.colors.RED_600, "diamonds": ft.colors.RED_600,
                "spades": ft.colors.BLACK, "clubs": ft.colors.BLACK
            }

            for opt in opciones:
                if isinstance(opt, dict):
                    val_rank = str(opt.get("rank", ""))
                    s_raw = str(opt.get("suit", "clubs")).lower()
                else:
                    val_rank = str(opt)
                    s_raw = "clubs"

                val_suit = next((s for s in ["hearts", "diamonds", "spades"] if s in s_raw), "clubs")
                icon = suits_icons.get(val_suit, "♣")
                color = suits_colors.get(val_suit, ft.colors.BLACK)

                opciones_row.controls.append(
                    ft.GestureDetector(
                        on_tap=lambda e, v=val_rank: [cerrar_dialogo(), on_choice(v) if on_choice else None],
                        content=ft.Container(
                            content=ft.Stack([
                                ft.Container(content=ft.Text(val_rank, size=22, weight="bold", color=color), padding=ft.Padding(10, 5, 0, 0)),
                                ft.Container(content=ft.Text(icon, size=45, color=color), alignment=ft.Alignment(0, 0)),
                            ]),
                            width=85, height=130, bgcolor=ft.colors.WHITE, border_radius=10,
                            border=ft.Border.all(1, ft.colors.BLACK26)
                        )
                    )
                )
            controles.append(opciones_row)
        else:
            controles.append(ft.Text(mensaje, size=16))
            acciones = [
                ft.FilledButton("SÍ", on_click=lambda _: [cerrar_dialogo(), on_si() if on_si else None], bgcolor=ft.colors.GREEN_700),
                ft.TextButton("NO", on_click=lambda _: [cerrar_dialogo(), on_no() if on_no else None])
            ]

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo, weight="bold"),
            content=ft.Column(controles, tight=True),
            actions=acciones if not opciones else None
        )
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    # =========================================
    # ACCIONES — mandan al servidor
    # =========================================
    def preparar_juego(e):
        if not state["selected_indices"]:
            mostrar_mensaje("Seleccioná cartas primero")
            return
        state["pending_melds"].append(list(state["selected_indices"]))
        state["selected_indices"].clear()
        actualizar_interfaz()

    def cancelar_todo(e):
        state["pending_melds"] = []
        state["selected_indices"].clear()
        actualizar_interfaz()

    def agregar_a_juego_click(e):
        meld_idx = e.control.data
        indices = list(state["selected_indices"])
        if not indices:
            mostrar_mensaje("Seleccioná una carta primero")
            return
        accion = {"type": "ADD_TO_MELD", "meld_index": meld_idx, "card_indices": indices}
        state["last_action"] = accion
        page.run_task(enviar_accion, accion)
        state["selected_indices"].clear()

    def realizar_robo(e):
        if e.control.data == "discard" and state["pozo_bloqueado"]:
            mostrar_mensaje("El pozo fue comprado, robá del mazo")
            return
        detener_timer()
        state["pozo_bloqueado"] = False
        page.run_task(enviar_accion, {"type": "DRAW", "source": e.control.data})

    def realizar_descarte(e):
        gs = state.get("game_state", {})
        if gs.get("turn_phase") == "DRAW":
            mostrar_mensaje("Primero robá una carta")
            return
        if not state["selected_indices"]:
            return
        detener_timer()
        page.run_task(enviar_accion, {"type": "DISCARD", "card_index": state["selected_indices"][0]})
        state["selected_indices"].clear()

    def realizar_bajar_juego(e):
        gs = state.get("game_state", {})
        my_player = next((p for p in gs.get("players", []) if p["index"] == state["my_index"]), None)
        if not my_player:
            return

        if my_player["has_met_objective"]:
            if state["pending_melds"]:
                indices = state["pending_melds"][0]
                state["pending_melds"] = []
            else:
                indices = list(state["selected_indices"])
            if not indices:
                mostrar_mensaje("Seleccioná cartas para bajar")
                return
            accion = {"type": "LAY_MELD", "card_indices": indices}
            state["last_action"] = accion
            page.run_task(enviar_accion, accion)
            state["selected_indices"].clear()
        else:
            if not state["pending_melds"]:
                mostrar_mensaje("Primero prepará tus grupos con 'Preparar Juego'")
                return
            accion = {"type": "LAY_ALL_OBJECTIVE", "groups_indices": list(state["pending_melds"])}
            state["last_action"] = accion
            page.run_task(enviar_accion, accion)
            state["pending_melds"] = []
            state["selected_indices"].clear()

    # =========================================
    # RENDERIZADO — usa state["game_state"]
    # =========================================
    def render_hand():
        mano_container.controls.clear()
        gs = state.get("game_state")
        if not gs:
            return

        my_hand = gs.get("my_hand", [])
        state["dragging_index"] = None

        for i, card in enumerate(my_hand):
            icon, color = get_card_style(card)
            is_selected = i in state["selected_indices"]
            esta_preparada = any(i in grupo for grupo in state["pending_melds"])
            order_index = state["selected_indices"].index(i) + 1 if is_selected else 0

            # Rank display
            if card.get("is_joker"):
                rep = card.get("rep_rank")
                display_rank = f"J({rep})" if rep else "🃏"
            else:
                display_rank = card.get("rank", "?")

            badge = ft.Container(
                content=ft.Text(str(order_index), size=10, color="white", weight="bold"),
                alignment=ft.Alignment(0, 0),
                width=20, height=20,
                bgcolor=ft.colors.BLUE_700,
                border_radius=10,
                right=5, top=5,
                visible=is_selected
            )

            check_preparada = ft.Container(
                content=ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN_400, size=20),
                right=5, bottom=5,
                visible=esta_preparada
            )

            def on_tap_carta(e, idx=i):
                if any(idx in grupo for grupo in state["pending_melds"]):
                    return
                if idx in state["selected_indices"]:
                    state["selected_indices"].remove(idx)
                else:
                    state["selected_indices"].append(idx)
                render_hand()

            def on_drag_complete(dst_idx):
                src_idx = state.get("dragging_index")
                if src_idx is None or src_idx == dst_idx:
                    return
                my_hand_local = state["game_state"]["my_hand"]
                my_hand_local[src_idx], my_hand_local[dst_idx] = my_hand_local[dst_idx], my_hand_local[src_idx]

                def remap(idx):
                    if idx == src_idx: return dst_idx
                    if src_idx < dst_idx:
                        if src_idx < idx <= dst_idx: return idx - 1
                    else:
                        if dst_idx <= idx < src_idx: return idx + 1
                    return idx

                state["selected_indices"] = [remap(x) for x in state["selected_indices"]]
                state["pending_melds"] = [[remap(x) for x in grupo] for grupo in state["pending_melds"]]
                state["dragging_index"] = None
                actualizar_interfaz()

            carta_visual = ft.Container(
                content=ft.Stack([
                    ft.Container(ft.Text(display_rank, size=16, weight="bold", color=color), padding=5),
                    ft.Container(content=ft.Image(src=f"data:image/svg+xml;base64,{icon}", width=45, height=45, fit="contain",) if icon else ft.Text("🃏", size=32), alignment=ft.Alignment(0, 0),),
                    badge,
                    check_preparada,
                ]),
                width=75, height=110,
                bgcolor=ft.colors.GREEN_100 if esta_preparada else (ft.colors.AMBER_50 if is_selected else ft.colors.WHITE),
                border_radius=10,
                opacity=0.5 if esta_preparada else 1.0,
                border=ft.Border.all(3, ft.colors.GREEN_700 if esta_preparada else (ft.colors.BLUE_400 if is_selected else ft.colors.BLACK26)),
            )

            draggable = ft.Draggable(
                group="cartas",
                content=ft.GestureDetector(on_tap=on_tap_carta, content=carta_visual),
                content_feedback=ft.Container(content=carta_visual, opacity=0.5),
                on_drag_start=lambda e, idx=i: state.update({"dragging_index": idx})
            )

            mano_container.controls.append(
                ft.DragTarget(
                    group="cartas",
                    content=draggable,
                    on_accept=lambda e, dst=i: on_drag_complete(dst),
                )
            )
        page.update()

    def render_table():
        mesa_container.controls.clear()
        gs = state.get("game_state")
        if not gs:
            return

        objetivos = {1: "1 juego de 3+", 2: "2 juegos de 3+", 3: "1 de 4+", 4: "2 de 4+",
                     5: "1 de 5+", 6: "2 de 5+", 7: "1 de 6+"}

        round_number = gs.get("round_number", 1)
        current_idx = gs.get("current_player_index", 0)
        players = gs.get("players", [])
        current_player = next((p for p in players if p["index"] == current_idx), {})
        my_player = next((p for p in players if p["index"] == state["my_index"]), {})

        # Indicador turno
        es_mi_turno = current_idx == state["my_index"]
        turno_txt = "🟢 TU TURNO" if es_mi_turno else f"⏳ Turno de {current_player.get('name', '')}"
        turno_color = ft.colors.GREEN_300 if es_mi_turno else ft.colors.WHITE54

        # Indicador objetivo
        if my_player.get("has_met_objective"):
            objetivo_widget = ft.Container(
                content=ft.Text("✅ OBJETIVO CUMPLIDO", size=14, weight="bold", color=ft.colors.GREEN_900),
                bgcolor=ft.colors.GREEN_300, border_radius=8,
                padding=ft.Padding(12, 4, 12, 4),
            )
        else:
            grupos_txt = f"📦 Grupos: {len(state['pending_melds'])}" if state["pending_melds"] else "🎯 Pendiente"
            objetivo_widget = ft.Container(
                content=ft.Text(grupos_txt, size=14, color=ft.colors.ORANGE_200),
                bgcolor=ft.colors.ORANGE_900, border_radius=8,
                padding=ft.Padding(12, 4, 12, 4),
            )

        # Info de todos los jugadores
        jugadores_row = ft.Row(spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        for p in players:
            es_current = p["index"] == current_idx
            es_yo = p["index"] == state["my_index"]
            jugadores_row.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            f"{'👤 ' if es_yo else ''}{p['name']}",
                            color=ft.colors.YELLOW_400 if es_current else ft.colors.WHITE70,
                            size=13, weight="bold" if es_current else "normal"
                        ),
                        ft.Text(f"🃏 {p['hand_count']} cartas", size=11, color=ft.colors.WHITE54),
                        ft.Text(f"🛒 {p['purchases_used']}/7", size=11, color=ft.colors.WHITE54),
                    ], spacing=2, tight=True),
                    bgcolor=ft.colors.WHITE24 if es_current else ft.colors.WHITE10,
                    border_radius=8,
                    padding=ft.Padding(8, 6, 8, 6),
                    border=ft.Border.all(1, ft.colors.YELLOW_400) if es_current else None,
                )
            )

        info_text.controls = [
            ft.Text(
                f"RONDA {round_number}/7 | OBJETIVO: {objetivos.get(round_number, 'Fin')}",
                size=22, weight="bold", color="white"
            ),
            jugadores_row,
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=15, controls=[
                ft.Text(turno_txt, color=turno_color, size=14, weight="bold"),
                objetivo_widget,
                timer_widget,
            ]),
        ]

        # Juegos en mesa
        juegos_row = ft.Row(wrap=True, spacing=10)
        for i, meld in enumerate(gs.get("melds", [])):
            meld_row = ft.Row(wrap=True, spacing=4)
            for card in meld["cards"]:
                icon, color = get_card_style(card)
                if card.get("is_joker"):
                    rep = card.get("rep_rank", "JK")
                    display_rank = f"J({rep})"
                else:
                    display_rank = card.get("rank", "?")

                meld_row.controls.append(
                    ft.Container(
                        content=ft.Stack([
                            ft.Container(ft.Text(display_rank, size=9, weight="bold", color=color), padding=2),
                            ft.Container(
                                content=ft.Image(
                                    src=f"data:image/svg+xml;base64,{icon}",
                                    width=28, height=28,
                                    fit="contain",
                                ) if icon else ft.Text("🃏", size=16),
                                alignment=ft.Alignment(0, 0)
                            ),
                        ]),
                        width=45, height=65, bgcolor=ft.colors.WHITE, border_radius=5,
                        border=ft.Border.all(2, ft.colors.PURPLE_400) if card.get("is_joker") else None
                    )
                )

            juegos_row.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"Juego {i+1}", color=ft.colors.YELLOW_400, weight="bold", size=12),
                            ft.IconButton(ft.icons.ADD_CIRCLE_OUTLINE, icon_color=ft.colors.YELLOW_400,
                                          icon_size=22, data=i, on_click=agregar_a_juego_click)
                        ], tight=True),
                        meld_row,
                    ], spacing=5, tight=True),
                    bgcolor=ft.colors.WHITE10, border_radius=8, padding=8,
                    border=ft.Border.all(1, ft.colors.WHITE24)
                )
            )

        mesa_container.controls.append(
            ft.Stack([
                ft.Container(
                    content=ft.Text(
                        "TELEFUNKEN",
                        size=120,
                        weight="bold",
                        color=ft.colors.with_opacity(0.06, ft.colors.WHITE),
                    ),
                    alignment=ft.Alignment(0, 0),
                    expand=True,
                    height=200,
                ),
                juegos_row,
            ])
        )
        

        # Pozo
        discard_top = gs.get("discard_top")
        if discard_top:
            icon, color = get_card_style(discard_top)
            rank = discard_top.get("rank", "?")
            descarte_btn.padding = 5
            descarte_btn.bgcolor = ft.colors.WHITE
            descarte_btn.content = ft.Column([
                ft.Text(rank, color=color, weight="bold", size=16),
                ft.Image(
                    src=f"data:image/svg+xml;base64,{icon}",
                    width=45, height=45,
                    fit="contain",
                ) if icon else ft.Text("🃏", size=35, color=ft.colors.PURPLE_500),
            ], 
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            tight=True,
            )
        else:
            descarte_btn.content = None
            descarte_btn.bgcolor = ft.colors.WHITE24

        info_text.update()
        page.update()

    # =========================================
    # BOTONES
    # =========================================
    btn_mazo = ft.FilledButton("Mazo", on_click=realizar_robo, data="deck")
    btn_descarte_btn = ft.FilledButton("Descarte", on_click=realizar_robo, data="discard")
    btn_preparar = ft.FilledButton("Preparar Juego", icon=ft.icons.ADD, on_click=preparar_juego)
    btn_cancelar = ft.FilledButton("Cancelar", icon=ft.icons.RESTART_ALT, on_click=cancelar_todo, bgcolor=ft.colors.RED_300)
    btn_bajar = ft.FilledButton("Bajar Juego", on_click=realizar_bajar_juego, bgcolor=ft.colors.GREEN_700)
    btn_tirar = ft.FilledButton("Descartar", on_click=realizar_descarte, bgcolor=ft.colors.RED_700)

    # =========================================
    # ARRANQUE — Pantalla de inicio
    # =========================================
    mostrar_pantalla_inicio()


# --- AL FINAL DE TU ARCHIVO ---
if __name__ == "__main__":
    import os
    ft.app(
        target=main,
        view=ft.AppView.WEB_BROWSER, # Obligatorio para la web
        host="0.0.0.0",              # Obligatorio para Render
        port=int(os.getenv("PORT", 8000)) # Escucha el puerto que Render te asigne
    )