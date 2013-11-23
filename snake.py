from collections import deque
import multiprocessing
from ctypes import c_char
import Queue

import pygame
from pygame.locals import *

import game
import game_objects
import level
import ai_jason

import process
from ai_vincent import VincentAI
ai_classes = [VincentAI, ai_jason.JasonAI,]
serializer = process.Serializer()

class Menu():
    def __init__(self, options, spacing=50):
        self.options = options
        self.font = pygame.font.SysFont("verdana", 30)
        self.font_color = pygame.Color(255, 255, 255)
        self.selector_color = pygame.Color(255, 255, 255)
        self.selector_padding = 20
        self.spacing = spacing
        self.frames_per_second = 10

    def show(self):
        clock = pygame.time.Clock()
        background = pygame.Surface(game.screen.get_size()).convert()
        background.fill(pygame.Color(0, 0, 0))

        menu_item_height = self.font.get_height() + self.spacing
        # menu_height = menu_item_height * len(self.options)
        # menu_top = (game.WINDOW_HEIGHT - menu_height) / 2
        menu_top = 300

        title_text = game.NAME
        title_color = pygame.Color(0, 255, 0)
        title_font = pygame.font.SysFont("impact", 70)
        title_top = 100
        subtitle_font = pygame.font.SysFont("georgia", 15)
        subtitle_text = "By Vincent and Jason"
        subtitle_top = 190

        option_selected = 0

        while True:
            clock.tick(self.frames_per_second)

            for event in pygame.event.get():
                if event.type == QUIT:
                    return False
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        return False
                    elif event.key == K_UP:
                        option_selected -= 1
                    elif event.key == K_DOWN:
                        option_selected += 1
                    elif event.key == K_RETURN:
                        return option_selected

            if option_selected < 0:
                option_selected = len(self.options)-1
            if option_selected >= len(self.options):
                option_selected = 0

            # Clear background
            game.screen.blit(background, (0, 0))

            # Draw title
            title = title_font.render(title_text, 1, title_color)
            title_pos = title.get_rect(centerx = game.WINDOW_WIDTH/2, y = title_top)
            game.screen.blit(title, title_pos)

            # Draw subtitle
            subtitle = subtitle_font.render(subtitle_text, 1, title_color)
            subtitle_pos = subtitle.get_rect(centerx = game.WINDOW_WIDTH/2, y = subtitle_top)
            game.screen.blit(subtitle, subtitle_pos)

            # Draw menu options
            for i, option in enumerate(self.options):
                text = self.font.render(option, 1, self.font_color)
                text_position = text.get_rect(centerx = game.WINDOW_WIDTH/2, y = menu_top + menu_item_height * i)
                game.screen.blit(text, text_position)

                # Draw selector
                if i == option_selected:
                    selector = pygame.Rect(text_position.left - self.selector_padding, text_position.top - self.selector_padding, text_position.width + self.selector_padding * 2, text_position.height + self.selector_padding * 2)
                    pygame.draw.rect(game.screen, self.selector_color, selector, 1)

            # Display!
            pygame.display.flip()

def main_loop():
    pygame.init()
    pygame.display.set_caption(game.NAME)
    clock = pygame.time.Clock()

    background = pygame.Surface(game.screen.get_size()).convert()
    background.fill(pygame.Color(0, 0, 0))

    player1_controls = [K_LEFT, K_RIGHT, K_UP, K_DOWN]
    player2_controls = [K_a, K_d, K_w, K_s]
    player3_controls = [K_j, K_l, K_i, K_k]
    player4_controls = [K_f, K_h, K_t, K_g]

    input_queue = multiprocessing.Queue()

    while True:
        # Choose player mode
        options = ["Single player", "Two players", "Three players", "Four players"]
        selection = Menu(options).show()
        if selection is False:
            return
        else:
            game.num_players = selection + 1

        # Choose level
        levels = level.get_levels()
        selection = Menu([lvl.name for lvl in levels]).show()
        if selection is False:
            continue
        else:
            game.level = levels[selection]

            # If single player, add an AI player
            if game.num_players == 1:
                game.num_players = 2
                game.init_level()

                # Load threaded AI
                if game.use_multiprocessing:
                    ai_engines = []
                    ai_processes = []
                    if game.use_multiprocessing:
                        ai_engines.append(ai_classes[game.ai_index])
                        shared_apples = multiprocessing.Array(process.GameObject,
                                list((apple.x, apple.y) for apple in game.apples))
                        shared_players = multiprocessing.Array(process.MovableGameObject,
                                list(((player.x, player.y), player.direction)
                                    for player in game.players))
                        shared_board = multiprocessing.Array(c_char * game.BOARD_HEIGHT,
                                serializer.serialize_board(game.board, process.board()))
                        ai_processes = [_class(player_index=i+game.num_players-1, board=shared_board, players=shared_players, apples=shared_apples, args=(input_queue,)) for i, _class in enumerate(ai_engines)]
                        map(lambda proc: proc.start(), ai_processes)
                else:
                    game.players[1].name = "Jason AI"
                    game.players[1].AI_engine = ai_jason.PlayerAI(game.players[1])
            else:
                game.init_level()

        # Start game loop
        return_to_menu = False
        game_status = None

        while not return_to_menu:
            clock.tick(game.frames_per_second)

            while game.use_multiprocessing:
                # Process key presses from AI threads.
                # Pulls values from input queue, creates pygame Events, and
                # submits to event queue.
                try:
                    pygame.event.post(pygame.event.Event(KEYDOWN, {'key':
                        input_queue.get_nowait(),}))
                except Queue.Empty, qe:
                    break

            # Get input
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    return_to_menu = True
                    # Shutdown all AI processes
                    map(lambda proc: proc.shutdown(), ai_processes)
                    break

                if event.type == KEYDOWN:
                    if event.key == K_SPACE:
                        game.players[0].grow = True
                    elif event.key == K_RETURN and game_status == "win":
                        game.init_level()
                        game_status = None
                        continue
                    elif event.key in player1_controls:
                        game.players[0].set_direction(player1_controls.index(event.key))
                    elif event.key in player2_controls and game.num_players > 1:
                        game.players[1].set_direction(player2_controls.index(event.key))
                    elif event.key in player3_controls and game.num_players > 2:
                        game.players[2].set_direction(player3_controls.index(event.key))
                    elif event.key in player4_controls and game.num_players > 3:
                        game.players[3].set_direction(player4_controls.index(event.key))

            # Update effects
            for effect in game.effects:
                effect.update()

            # Update game
            game.update()

            # Update shared board
            if game.use_multiprocessing:
                for i, v in enumerate(list((apple.x, apple.y) for apple in game.apples)):
                    shared_apples[i] = v

                for i, v in enumerate(list(((player.x, player.y),
                    player.direction) for player in game.players)):
                    shared_players[i] = v

                serializer.serialize_board(game.board, shared_board)

            # Draw the screen
            game.screen.blit(background, (0, 0))
            game.draw()
            for effect in game.effects:
                effect.draw()

            # Draw scoreboard
            score_icon_size = 30
            score_width = 150
            score_x = game.WINDOW_WIDTH/2 - game.num_players*score_width/2 + 60
            score_y = game.WINDOW_HEIGHT - game.SCOREBOARD_HEIGHT + (game.SCOREBOARD_HEIGHT-score_icon_size)/2
            for i, player in enumerate(game.players):
                rect = pygame.Rect(score_x + i*score_width, score_y, score_icon_size, score_icon_size)
                score = pygame.font.SysFont('impact', 30).render(str(player.kills), 1, pygame.Color(255, 255, 255))
                score_pos = score.get_rect(centerx=score_x + i*score_width + 50, centery=score_y + 15)
                game.screen.blit(score, score_pos)
                pygame.draw.rect(game.screen, player.color, rect)

            # Check for the win condition
            winners = filter(lambda p: p.kills >= game.level.kills_to_win, game.players)
            if winners:
                game_status = 'win'
                if len(winners) > 1:
                    text = pygame.font.SysFont("impact", 100).render("Draw!", 1, pygame.Color(255, 255, 255))
                else:
                    text = pygame.font.SysFont("impact", 100).render(winners[0].name + " wins!", 1, pygame.Color(255, 255, 255))
                text_pos = text.get_rect(centerx = game.WINDOW_WIDTH/2, centery = game.WINDOW_HEIGHT/2 - 50)
                game.screen.blit(text, text_pos)

                text = pygame.font.SysFont("verdana", 15).render("Press [ENTER] to play again, or [ESC] to return to the main menu.", 1, pygame.Color(255, 255, 255))
                text_pos = text.get_rect(centerx = game.WINDOW_WIDTH/2, centery = game.WINDOW_HEIGHT/2 + 40)
                game.screen.blit(text, text_pos)

            # Display!
            pygame.display.flip()

if __name__ == '__main__':
    main_loop()
