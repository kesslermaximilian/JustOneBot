import database.db_access as dba
import random

from discord.ext import commands
from typing import List, Union
import json


# This file handles the wordpools.json file and provides functions to read from it


class WordPoolDistribution:  # Class used to manage the distribution of wordpools
    def __init__(self, distribution):  # Saves a natural number for each word_pool
        self.distribution = distribution

    def get_distribution(self):  # Returns the distribution of itself. Method for future in case return type changes
        return self.distribution


def available_word_pools():  # Give back a list of the existing word pools (in the json file)
    return get_wordpools().keys()


def get_description(wordpool_name: str) -> Union[str, None]:
    #  Give back the description of a wordpool using its string name
    if wordpool_name in available_word_pools():
        return get_wordpools()[wordpool_name]['description']
    return None


def get_words(wordpool_name: str) -> Union[List[str], None]:
    # Give back the words contained in a wordpool using its string name
    if wordpool_name in available_word_pools():
        return get_wordpools()[wordpool_name]['words']


def getword(word_pool_distribution: WordPoolDistribution):  # Choose a word using the given distribution of wordpools
    # Create the custom wordpool to draw a word from:
    pool: [str] = []
    for (wordpool, weight) in word_pool_distribution.get_distribution():
        words = get_words(wordpool)
        if words:
            pool += (get_words(wordpool) * weight)
        else:
            print('Ignoring wrongly given wordpool')

    return pool[random.randint(0, len(pool)-1)]  # draw word and return it


def get_wordpools() -> dict:  # Reads the json file and returns a dictionary containing the wordpools. Internal function
    with open('data/wordpools.json') as file:
        wordpool_dict = json.load(file)
    return wordpool_dict


def compute_current_distribution(ctx: commands.Context) -> WordPoolDistribution:
    # Computes the current WordPoolDistribution using the entries of the database (the enabled wordpools)
    distribution: List[(str, int)] = []
    if dba.get_settings_for(ctx.guild.id) is None:
        return WordPoolDistribution(STANDARD_WORD_POOL_DISTRIBUTIONS['DEFAULT'])
    for setting in dba.get_settings_for(ctx.guild.id):
        distribution.append((setting.value, setting.weight))
    return WordPoolDistribution(distribution)



