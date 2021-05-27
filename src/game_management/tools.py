import discord
from enum import Enum
from typing import List


class Hint:
    def __init__(self, message: discord.Message):
        self.author = message.author
        self.hint_message = message.content
        self.valid = True
        self.message_id = 0

    def strike(self):
        self.valid = False

    def is_valid(self):
        return self.valid


def hints2name_list(hint_list: List[Hint]):
    d: dict = {}
    for hint in hint_list:
        try:
            d[hint.author] = d[hint.author] + 1
        except KeyError:
            d[hint.author] = 1

    def show_number(value: int):
        return "" if value == 1 else f" ({value})"

    return ',  '.join([f"{compute_proper_nickname(person)}{show_number(d[person])}" for person in d.keys()])


class Phase(Enum):
    initialised = 0  # game initialised but not started. future: maybe construct a game but not start it
    preparation = 10  # sending info message that game started, preparing admin channel if needed
    wait_for_admin = 20  # waiting for the admin to react in extra channel
    show_word = 30  # Show the word
    wait_collect_hints = 40  # Collecting hints in main channel
    show_all_hints_to_players = 50  # Printing the hits one-by one to the players (except the guesser)
    wait_for_hints_reviewed = 60  # Waiting for confirmation that hints are reviewed
    compute_valid_hints = 70  # Fetching reactions to the shown hints and setting them to invalid if needed
    inform_admin_to_reenter = 80  # Sending info to admin in admin channel that he can reenter the main channel
    remove_role_from_guesser = 90
    show_valid_hints = 100  # Showing the valid hints in main channel
    wait_for_guess = 110  # Waiting for a guess
    show_guess = 120  # future: Make mode to show the guess and have it being confirmed
    show_summary = 130  # Show the summary of the round
    aborting = 140  # Abort the game
    stopping = 150  # When the game is being stopped, aka deleting all messages etc.
    stopped = 160  # Game is stopped, nothing can be changed anymore

    # The next three phases will be run in parallel and thus NOT be the value of self.phase at any time.
    # They are just declared so that the TaskManager can properly handle them.
    # While they are executed, game will still be in Phase show_summary
    wait_for_play_again_in_closed_mode = 1000
    wait_for_play_again_in_open_mode = 1001
    wait_for_stop_game_after_timeout = 1002
    clear_messages = 1003
    play_new_game = 1004


class Key(Enum):
    invalid = 0  # Used to denote that no key is given, don't use this
    admin_wait = 1  # Wait message in admin mode before round starts (in default channel)
    admin_welcome = 2  # Message sent in the admin channel to welcome the admin
    show_word = 3  # Message that shows the word to players
    end_hint_phase = 4  # Message that indicates end of get_hints phase and start of reviewing of hints
    filter_hint_finished = 5  # Confirm message after reviewing the hints
    admin_inform_reenter = 6  # Info message for the admin to reenter the main channel
    show_hints_to_guesser = 7  # Message that shows hints to guesser
    summary = 8  # Message that shows summary
    abort = 10  # Abort message (if any)
    guess = 11  # The guess


class Group(Enum):
    default = 1  # Default output of the bot
    filter_hint = 2
    user_chat = 3
    own_command_invocation = 4
    other_bot = 5
    warn = 6


# Helping methods
def make_simple(word: str):
    word = word.lower()
    replace_list = [('-', ''), (' ', ''), ('é', 'e'), ('í', 'i'), ('ß', 'ss'), ('ph', 'f')]
    for (a, b) in replace_list:
        word.replace(a, b)

    return word


def evaluate(word: str, guess: str) -> bool:
    return make_simple(word) == make_simple(guess)


def compute_proper_nickname(member: discord.Member):
    if type(member) == discord.Member:
        return member.nick if member.nick else member.name
    else:
        return member.name
