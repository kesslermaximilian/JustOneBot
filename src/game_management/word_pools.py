import database.db_access as dba
import random

from discord.ext import commands
from typing import List, Union, Tuple
import json
from environment import DEFAULT_DISTRIBUTION

# This file handles the wordpools.json file and provides functions to read from it


class WordPoolDistribution:  # Class used to manage the distribution of wordpools
    """
    Wrapper class representing a distribution of the word pools to be drawn of. Settings might be expanded in the future
    so that guilds can save word pools with names for faster switching between them
    """
    def __init__(self, distribution):  # Saves a natural number for each word_pool
        """
        Constructor for a WordPoolDistribution

        @param distribution: List[(str,int)] representing pairs of (wordpool name, weight)
                Currently, wordpool name can be one of the following:
                classic_main, classic_weird, extension_main, extension_weird, nsfw, gandhi
                For more, see available_word_pools() in this file
        """
        self.distribution = distribution

    def get_distribution(self):  # Returns the distribution of itself. Method for future in case return type changes
        return self.distribution

    def __str__(self):
        """
        Nice representation of WordPoolDistribution for the logger
        @return: String that contains info about the WordPoolDistribution
        """
        return ', '.join([f"{pool} ({weight})" for (pool, weight) in self.distribution])


def available_word_pools() -> List[str]:
    """
    @return: List[str]: A list of the existing word pools (in the json file) - sorted
    """
    return sorted(get_wordpools().keys())


def get_description(wordpool_name: str) -> Union[str, None]:
    """
    Get the description of a word pool
    @param wordpool_name: str. The str name of the word pool to get a description from
    @return: Union[str, None] Description of the wordpool if wordpool exists. None otherwise.
    """
    #  Give back the description of a wordpool using its string name
    if wordpool_name in available_word_pools():
        return get_wordpools()[wordpool_name]['description']
    return None


def get_pools_with_description() -> List[Tuple[str, str]]:
    """
    :return: List of Tuples containing pool name and description
    """
    return [(pool, get_description(pool)) for pool in available_word_pools()]


def get_words(wordpool_name: str) -> Union[List[str], None]:
    """
    Get the words in a word pool.
    @param wordpool_name: str name of the word pool.
    @return: List[str]. The list of words from this wordpool. None, if pool does not exist.
    """
    # Give back the words contained in a wordpool using its string name
    if wordpool_name in available_word_pools():
        return get_wordpools()[wordpool_name]['words']


def getword(word_pool_distribution: WordPoolDistribution):
    """
    Draw a word from the wordpools.
    @param word_pool_distribution: The wordpool distribution to be drawn of
    @return: A random word drawn from the wordpools according to the distribution as fallows:
            We create a pool where each word is contained as often as the weight of its wordpool (so excluded if the
            wordpool is not part of the WordPoolDistribution), and draw uniformly from it.
            This is useful to weight smaller lists and thus draw from them more often, however also getting more
            repeations within that list.
    """
    # Choose a word using the given distribution of wordpools
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
    """
    Get the wordpools
    @return: A dictionary containing the information of the wordpools
    """
    with open('data/wordpools.json') as file:
        wordpool_dict = json.load(file)
    return wordpool_dict


def compute_current_distribution(ctx: commands.Context) -> WordPoolDistribution:
    """
    Compute the current word pool distribution from the settings of the database server-specifically
    @param ctx: The context (containing the server) from which to read the settings
    @return: A WordPoolDistribution according to the current settings of the server
    """
    # Computes the current WordPoolDistribution using the entries of the database (the enabled wordpools)
    distribution: List[(str, int)] = []
    if dba.get_settings_for(ctx.guild.id) is None:
        return WordPoolDistribution(DEFAULT_DISTRIBUTION)  # Just draw from this list
    for setting in dba.get_settings_for(ctx.guild.id):
        distribution.append((setting.value, setting.weight))
    return WordPoolDistribution(distribution)



