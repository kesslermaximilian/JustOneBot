import os
import logging


def load_env(key: str, default: str) -> str:
    """
    os.getenv() wrapper that handles the case of None-types for not-set env-variables\n

    :param key: name of env variable to load
    :param default: default value if variable couldn't be loaded
    :return: value of env variable or default value
    """
    value = os.getenv(key)
    if value:
        return value
    print(f"Can't load env-variable for: '{key}' - falling back to DEFAULT {key}='{default}'")
    logger.warning(f"Can't load env-variable for: '{key}' - falling back to DEFAULT {key}='{default}'")
    return default


logger = logging.getLogger('my-bot')

TOKEN = os.getenv("TOKEN")  # reading in the token from config.py file


STANDARD_WORD_POOL_DISTRIBUTIONS: dict = {"VANILLA" : [('classic_main', 1), ('classic_weird', 1)],
"VANNILLA_EXTENDED" : [('classic_main', 1), ('classic_weird', 1), ('extension_main', 1), ('extension_weird', 1)],
"DEFAULT" : [('classic_main', 1), ('extension_main', 1)],
"INCLUDE_NSFW" : [('classic_main', 1), ('extension_main', 1), ('nsfw', 1)],
"MORE_NSFW" : [('classic_main', 1), ('extension_main', 1), ('nsfw', 8)],
"ONLY_NSFW" : [('nsfw', 1)],
"VANILLA_GANDHI" : [('classic_main', 1), ('classic_weird', 1), ('gandhi',10)],
"VANNILLA_EXTENDED_GANDHI" : [('classic_main', 1), ('classic_weird', 1), ('extension_main', 1), ('extension_weird', 1), ('gandhi',20)],
"DEFAULT_GANDHI" : [('classic_main', 1), ('extension_main', 1), ('gandhi',20)],
"INCLUDE_NSFW_GANDHI" : [('classic_main', 1), ('extension_main', 1), ('nsfw', 1), ('gandhi',25)],
"MORE_NSFW_GANDHI" : [('classic_main', 1), ('extension_main', 1), ('nsfw', 8), ('gandhi',40)],
"ONLY_NSFW_GANDHI" : [('nsfw', 1), ('gandhi',3)]
}


# loading optional env variables
PREFIX = load_env("PREFIX", "~")
VERSION = load_env("VERSION", "alpha")  # version of the bot
OWNER_NAME = load_env("OWNER_NAME", "Roman Seifert, Maximilian Keßler feat. Chris")   # owner name with tag e.g. pi#3141
OWNER_ID = int(load_env("OWNER_ID", "100000000000000000"))  # discord id of the owner
CHECK_EMOJI = '\u2705'
DISMISS_EMOJI = '\u274C'
DEFAULT_TIMEOUT = 300


#  "classic_main", "classic_weird", "extension_main", "extension_weird", "nsfw", "gandhi"]
