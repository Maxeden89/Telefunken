🃏  #Juego de Cartas: Telefunken Pro (Multijugador Online)

##Descripción general
Este proyecto es una versión digital y multijugador del clásico juego de cartas Telefunken (estilo canasta). Permite a los usuarios jugar partidas en tiempo real con amigos, respetando las reglas tradicionales y exclusivas de esta modalidad.

**Objetivo**
El objetivo principal fue transformar la experiencia de un juego de mesa físico a un entorno digital accesible, permitiendo que la distancia no sea un impedimento para jugar. El proyecto nació de la necesidad personal de jugar con amigos y el desafío de construir la lógica desde cero.

**Desarrollo y Lógica con Python**
Para que el juego funcione correctamente, se utilizó Python para programar toda la inteligencia y reglas del motor:

**Gestión de jugadas:** Validación de escaleras circulares (Q-K-1-2-3) y tríos.

**Sistema de Comodines:** Reglas de blindaje y movimientos permitidos.

**Sincronización:** Uso de WebSockets para que todos los jugadores vean los movimientos al mismo tiempo sin retrasos.

##Funcionalidades del Juego
**Menú de Instrucciones:** Acceso directo desde el menú principal presionando el icono ? para conocer las reglas.

**Sistema de Compras:** Opción de comprar cartas fuera de turno con un temporizador automático de 10 segundos.

**Interfaz Interactiva:** Sistema de "arrastrar y soltar" (drag & drop) para acomodar las cartas a gusto del jugador.

**Multiplataforma:** Gracias al despliegue en la nube (Render), se puede jugar desde la computadora, tablet o móvil.

##Conclusión
El desarrollo de este juego demuestra que es posible llevar reglas complejas a un entorno web funcional. Las pruebas reales con jugadores confirmaron que el sistema de sincronización en tiempo real es robusto y que la lógica de las cartas responde exactamente como en el juego físico, logrando una experiencia fluida y entretenida.

##Cómo jugar
**Acceso:** Ingresa al enlace del juego (si el desarrollador te lo proporciona) o ejecuta el servidor localmente.

**Menú Principal:** Revisa las reglas en el botón de ayuda **'?'**.

**Partida:** Crea o únete a una sala con tus amigos.

**Interacción:** Arrastra tus cartas para formar juegos y mantente atento al temporizador cuando alguien quiera comprar una carta.

##Tecnologías utilizadas
**Python:** El motor principal del juego.

**FastAPI:** Para el servidor y la comunicación rápida.

**HTML, CSS y JavaScript:** Para la parte visual y la experiencia del usuario.

**Render:** Para que el juego esté siempre online.
