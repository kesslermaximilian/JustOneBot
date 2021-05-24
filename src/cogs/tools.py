import random
import time

import discord
from discord.ext import commands
from enum import Enum
from typing import NewType, List
import utils as ut
import json
import asyncio
import database.db_access as dba
from environment import AVAILABLE_WORD_POOLS
from environment import STANDARD_WORD_POOL_DISTRIBUTIONS

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

    def get_distribution(self):
        return self.distribution


def getword(word_pool_distribution: WordPoolDistribution):  # Choose a word using the given distribution of wordpools
    with open('data/words.json') as file:
        words_dict = json.load(file)
        print(words_dict)

    # Create the custom wordpool to draw a word from:
    pool: [str] = []
    for (word_pool, weight) in word_pool_distribution.get_distribution():
        if word_pool in AVAILABLE_WORD_POOLS:
            pool += (words_dict[word_pool]*weight)
        else:
            print('found wrong word pool, ignoring')
    return pool[random.randint(0, len(pool))]  # draw word and return it


def compute_current_distribution(ctx: commands.Context):
    distribution: List[(str, int)] = []
    if dba.get_settings_for(ctx.guild.id) is None:
        return WordPoolDistribution(STANDARD_WORD_POOL_DISTRIBUTIONS['DEFAULT'])
    for setting in dba.get_settings_for(ctx.guild.id):
        distribution.append((setting.value, 1))
    return WordPoolDistribution(distribution)
