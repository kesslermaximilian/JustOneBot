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
    initialised = 1  # game initialised, but not started
    get_hints = 2  # game just started, collecting hints
    filter_hints = 3  # hints are displayed to non-guessers for reviewing
    show_hints = 4  # (non-duplicate) hints are displayed to guesser
    evaluation = 5  # answer and summary are computed and shown
    finished = 6  # the game is over and can be wiped from memory now
    stopped = 7  # game does not accept correction anymore


    # initialised = 0  # game initialised but not started. future: maybe construct a game but not start it
    # preparation = 10  # sending info message that game started, preparing admin channel if needed
    # wait_for_admin = 20  # waiting for the admin to react in extra channel
    # show_word = 30  # Show the word
    # wait_collect_hints = 40  # Collecting hints in main channel
    # show_all_hints_to_players = 50  # Printing the hits one-by one to the players (except the guesser)
    # wait_hints_reviewed = 60  # Waiting for confirmation that hints are reviewed
    # compute_valid_hints = 70  # Fetching reactions to the shown hints and setting them to invalid if needed
    # inform_admin_to_reenter = 80



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
    return member.nick if member.nick else member.name
