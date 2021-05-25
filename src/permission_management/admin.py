import discord


def is_guild_admin(member: discord.Member) -> bool:
    """
    Shorthand for member.guild_permissions.administrator
    :param member: discord.Memeber to check if admin
    """
    return member.guild_permissions.administrator
