import random
import time

import discord
from discord.ext import commands
from enum import Enum
from typing import NewType, List
import utils as ut
import json
import asyncio


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


class WordPoolDistribution:
    def __init__(self, distribution):  # Saves a natural number for each word_pool
        self.distribution = distribution


def getword(word_pool_distribution: WordPoolDistribution):
    return 'Gandhi'
    with open('data/words.json') as file:
        words_dict = json.load(file)
        print(words_dict)

    # Now compute a pool of words to draw of:
    pool: [str] = []
    for (word_pool, weight) in word_pool_distribution.distribution:
        pool += (words_dict[word_pool]*weight)
    return pool[random.randint(0, len(pool))]

