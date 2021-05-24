import logging
from typing import List

import discord

import database.db_access as dba


logger = logging.getLogger('my-bot')


def get_mod_roles(guild: discord.Guild) -> List[discord.Member]:
    """
    Gets all roles that have moderator permissions inside the bot.\n
    Removes roles that the bot can't find from database

    :param guild: guild to search on

    :return: List of all (moderator) roles (discord object) that the bot can find on the guild
    """
    # load roles
    entries = dba.get_settings_for(guild.id, setting="mod-role")
    if not entries:
        return []
    roles = []
    for entry in entries:
        role = guild.get_role(int(entry.value))
        # if role can't be extracted it's probably deleted and should be removed
        if not role:
            logger.info(f"{guild.name}: Can't find role with ID {entry.id} - removing.")
            dba.del_setting(guild.id, entry.value, entry.setting)
            continue

        roles.append(role)
    return roles


