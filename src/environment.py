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

# loading optional env variables
PREFIX = load_env("PREFIX", "j!")
VERSION = load_env("VERSION", "unknown")  # version of the bot
OWNER_NAME = load_env("OWNER_NAME", "unknown")   # owner name with tag e.g. pi#3141
OWNER_ID = int(load_env("OWNER_ID", "100000000000000000"))  # discord id of the owner
CHECK_EMOJI = '\u2705'
DISMISS_EMOJI = '\u274C'
SKIP_EMOJI = '\u23ed'
PLAY_AGAIN_CLOSED_EMOJI = '\U0001f501'
PLAY_AGAIN_OPEN_EMOJI = '\u21a9'
DEFAULT_TIMEOUT = 600
ROLE_NAME = 'JustOne-Guesser'
DEFAULT_DISTRIBUTION = [('classic_main', 1)]
DEBUG_MODE = True

#  "classic_main", "classic_weird", "extension_main", "extension_weird", "nsfw", "gandhi"]
