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
            logger.info(f"{guild.name}: Can't find role with ID {entry.value} - removing.")
            dba.del_setting(guild.id, entry.value, entry.setting)
            continue

        roles.append(role)
    return roles


def is_moderator(member: discord.Member) -> bool:
    """
    Takes a member and checks if any mod role matches with roles the member has

    :param member: member to check

    :return: True if member has a mod role, False else
    """

    # if member is an admin, he can do what ever he likes to do
    if member.guild_permissions.administrator:
        return True

    # load mod roles
    # extract only role-ids from role objects
    mod_role_ids = set([r.id for r in get_mod_roles(member.guild)])
    member_role_ids = set([r.id for r in member.roles])
    # intersecting sets to see if any role id is in both sets which means that user has mod perms
    intersect = mod_role_ids & member_role_ids

    return True if intersect else False
