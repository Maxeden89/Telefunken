from game.game import Game
from game.player import Player
from game.bot import BotPlayer

ana = Player("Ana")
bot_player = Player("Bot", is_bot=True)
bot_player.bot = BotPlayer(bot_player)

game = Game([ana, bot_player])

while not game.game_over:
    game.play_turn()
