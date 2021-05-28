import os
import logging

from environment import DEBUG_MODE

# path for databases or config files
if not os.path.exists('data/'):
    os.mkdir('data/')

# set logging format
formatter = logging.Formatter("[{asctime}] [{levelname}] [{name}] {message}", style="{")

# logger for writing to file
file_logger = logging.FileHandler('data/events.log')
file_logger.setLevel(logging.INFO)  # everything into the logging file
file_logger.setFormatter(formatter)

# logger for console prints
console_logger = logging.StreamHandler()
console_logger.setLevel(logging.WARNING)  # only important stuff to the terminal
console_logger.setFormatter(formatter)

# debug logger for console
debug_logger = logging.StreamHandler()
debug_logger.setLevel(logging.DEBUG)
debug_logger.setFormatter(formatter)

# debug logger for file
file_debug_logger = logging.FileHandler('data/debug.log')
file_debug_logger.setLevel(logging.DEBUG)
file_debug_logger.setFormatter(formatter)

# get new logger
logger = logging.getLogger('my-bot')
if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

# register loggers
logger.addHandler(file_logger)
logger.addHandler(console_logger)
logger.addHandler(debug_logger)
logger.addHandler(file_debug_logger)


def channel_prefix(channel):
    return f'[Channel {channel.id}] '
