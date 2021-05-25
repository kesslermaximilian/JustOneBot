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


class Key(Enum):
    invalid = 0  # Used to denote that no key is given, don't use this
    show_word = 1
    admin_welcome = 2
    filter_hint_finished = 3
    guess = 4
    summary = 5


class Group(Enum):
    default = 1
    filter_hint = 2
    chat = 3
    command = 4
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
