# 🃏 Juego de Cartas: Telefunken Pro (Multijugador Online)

## 📝 Descripción general
Este proyecto es una versión digital y multijugador del clásico juego de cartas **Telefunken** (estilo canasta). Permite a los usuarios jugar partidas en tiempo real con amigos, respetando las reglas tradicionales y exclusivas de esta modalidad.

---

### 🎯 Objetivo
El objetivo principal fue transformar la experiencia de un juego de mesa físico a un entorno digital accesible, permitiendo que la distancia no sea un impedimento para jugar. El proyecto nació de la necesidad personal de jugar con amigos y el desafío de construir la lógica desde cero.

---

### 🐍 Desarrollo y Lógica con Python
Para que el juego funcione correctamente, se utilizó Python para programar toda la inteligencia y reglas del motor:

* **Gestión de jugadas:** Validación de escaleras circulares (Q-K-1-2-3) y tríos.
* **Sistema de Comodines:** Reglas de blindaje y movimientos permitidos.
* **Sincronización:** Uso de WebSockets para que todos los jugadores vean los movimientos al mismo tiempo sin retrasos.

---

### ✨ Funcionalidades Destacadas (Interactivo)

<details>
<summary><b>📖 Menú de Instrucciones</b> (Click para ver)</summary>
Acceso directo desde el menú principal presionando el icono <b>"?"</b> para conocer las reglas detalladas sin salir del juego.
</details>

<details>
<summary><b>⏱️ Sistema de Compras</b> (Click para ver)</summary>
Opción de comprar cartas fuera de turno con un temporizador automático de 10 segundos que gestiona la prioridad entre jugadores.
</details>

<details>
<summary><b>🖱️ Interfaz Interactiva</b> (Click para ver)</summary>
Sistema de "arrastrar y soltar" (drag & drop) para acomodar las cartas a gusto del jugador, igual que en la vida real.
</details>

<details>
<summary><b>🌐 Multiplataforma</b> (Click para ver)</summary>
Gracias al despliegue en la nube (Render), se puede jugar desde la computadora, tablet o móvil mediante un navegador web.
</details>

---

### 💡 Conclusión
El desarrollo de este juego demuestra que es posible llevar reglas complejas a un entorno web funcional. Las pruebas reales con jugadores confirmaron que el sistema de sincronización en tiempo real es robusto y que la lógica de las cartas responde exactamente como en el juego físico.

---

### 🕹️ Cómo jugar
1. **Acceso:** Ingresa al enlace del juego o ejecuta el servidor localmente.
2. **Menú Principal:** Revisa las reglas en el botón de ayuda **'?'**.
3. **Partida:** Crea o únete a una sala con tus amigos.
4. **Interacción:** Arrastra tus cartas para formar juegos y mantente atento al temporizador.

---

### 🛠️ Tecnologías utilizadas
| Tecnología | Función |
| :--- | :--- |
| **Python** | Motor principal del juego |
| **FastAPI** | Servidor y comunicación rápida |
| **JS/HTML/CSS** | Interfaz visual y experiencia de usuario |
| **Render** | Despliegue y hosting online |

---
