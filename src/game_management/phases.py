import discord
from game_management.tools import Phase
from game_management.game import Game
from log_setup import logger


class PhaseHandler:
    def __init__(self, game: Game):
        self.game = game
        self.task_dictionary = {
            Phase.initialised: None,
            Phase.preparation: game.preparation,
            Phase.wait_for_admin: game.wait_for_admin,
            Phase.show_word: game.show_word,

            Phase.compute_valid_hints: game.compute_valid_hints,
            Phase.inform_admin_to_reenter: game.inform_admin_to_reenter,
            Phase.remove_role_from_guesser: game.remove_role_from_guesser,
            Phase.show_valid_hints: game.show_valid_hints,
            Phase.wait_for_guess: game.wait_for_guess,
            Phase.show_summary: game.show_summary,
            Phase.wait_for_play_again_in_closed_mode: game.wait_for_play_again_in_closed_mode,
            # Phase.wait_for_play_again_in_open_mode: game.wait_for_play_again_in_open_mode # future
            Phase.stopping: game.stopping,
        }

    def cancel_all(self):
        for phase in self.task_dictionary.keys():
            if int(phase) < 1000:
                self.task_dictionary[phase].cancel()

    def advance_to_phase(self, phase: Phase):
        if self.game.phase > phase:
            logger.error(f'{self.game.game_prefix()}Tried to advance to Phase {phase}, but game is already '
                         f'in phase {self.game.phase}, cannot go back in time. Aborting phase start.')
            return
        elif self.game.phase == phase:
            logger.warn(f'{self.game.game_prefix()}Tried to advance to Phase {phase}, but game is already in that phase.'
                        f'Canot start phase a second time.')
            return
        else:  # Start the new phase
            self.game.phase = phase
            self.cancel_all()
            self.task_dictionary[phase].start()

    def start_task(self, phase: Phase):
        if self.task_dictionary[phase].is_running():
            logger.error(f'{self.game.game_prefix()}Task {phase} is already running, cannot start it twice. '
                         f'Aborting task start.')
            return
        else:
            self.task_dictionary[phase].start()
            logger.info(f'Started task {phase}')
