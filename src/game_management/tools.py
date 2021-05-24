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

    return ', '.join([f"{compute_proper_nickname(person)}{show_number(d[person])}" for person in d.keys()])


class Phase(Enum):
    initialised = 1  # game initialised, but not started
    get_hints = 2  # game just started, collecting hints
    filter_hints = 3  # hints are displayed to non-guessers for reviewing
    show_hints = 4  # (non-duplicate) hints are displayed to guesser
    evaluation = 5  # answer and summary are computed and shown
    finished = 6  # the game is over and can be wiped from memory now
    stopped = 7  # game does not accept correction anymore


# Helping methods
def make_simple(word: str):
    word = word.lower()
    replacelist = [('-', ''), (' ',''), ('é', 'e'), ('í', 'i'), ('ß', 'ss'), ('ph','f')]
    for (a, b) in replacelist:
        word.replace(a, b)

    return word


def evaluate(word: str, guess: str) -> bool:
    return make_simple(word) == make_simple(guess)


def compute_proper_nickname(member: discord.Member):
    return member.nick if member.nick else member.name
