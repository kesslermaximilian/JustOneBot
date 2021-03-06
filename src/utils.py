import re
from typing import Union, List, Tuple

import discord
from discord.ext import commands
from discord.errors import Forbidden

from environment import PREFIX

"""
The color presets, send_message() and make_embed() functions are included in the discord-bot template by nonchris
https://github.com/nonchris/discord-bot
"""


# color scheme for embeds as rbg
blue_light = discord.Color.from_rgb(20, 255, 255)  # default color
green = discord.Color.from_rgb(142, 250, 60)   # success green
yellow = discord.Color.from_rgb(245, 218, 17)  # waring like 'hey, that's not cool'
orange = discord.Color.from_rgb(245, 139, 17)  # waring - rather critical like 'no more votes left'
red = discord.Color.from_rgb(255, 28, 25)      # error red


async def send_embed(ctx, embed):
    """
    Handles the sending of embeds
    -> Takes context and embed to send
    - tries to send embed in channel
    - tries to send normal message when that fails
    - tries to send embed private with information abot missing permissions
    If this all fails: https://youtu.be/dQw4w9WgXcQ
    """
    try:
        await ctx.send(embed=embed)
    except Forbidden:
        try:
            await ctx.send("Hey, seems like I can't send embeds. Please check my permissions :)")
        except Forbidden:
            await ctx.author.send(
                f"Hey, seems like I can't send any message in {ctx.channel.name} on {ctx.guild.name}\n"
                f"May you inform the server team about this issue? :slight_smile:", embed=embed)


# creating and returning an embed with keyword arguments
# please note that name and value can't be empty - name and value contain a zero width non-joiner
def make_embed(title="", color=blue_light, name="‌", value="‌", footer=None) -> discord.Embed:
    """
    Function to generate generate an embed in one function call

    :param title: Headline of embed
    :param color: RGB Tuple (Red, Green, Blue)
    :param name: Of field (sub-headline)
    :param value: Text of field (actual text)
    :param footer: Text in footer
    :return: Embed ready to send
    """
    # make color object
    emb = discord.Embed(title=title, color=color)
    emb.add_field(name=name, value=value)
    if footer:
        emb.set_footer(text=footer)

    return emb


def extract_id_from_message(content: str) -> Union[int, None]:
    """
    Scans string to extract user/guild/message id\n
    Can extract IDs from mentions or plaintext
    :return: extracted id
    """
    # matching string that has 18 digits surrounded by non-digits or start/end of string
    match = re.match(r'(\D+|^)(\d{18})(\D+|$)', content)

    return int(match.group(2)) if match else None


def get_default_permission_message(missing_perm='administrator',
                                   help_string=f'Use `{PREFIX}help` for more information',
                                   color=yellow,
                                   error_title="You can't do that."
                                   ) -> discord.Embed:
    """
    Generates central permission error message

    :param missing_perm: The permission the member misses, e.g. 'bot moderator' or 'admin'
    :param help_string: String like 'Use !command_x to add permissions for that role'
    :param color: simply the discord.Color for this embed
    :param error_title: To mix things up and use other titles if you want

    :return: Embed with permission message and additional help string
    """
    return make_embed(
        name=error_title,
        value=f"Hey, I'm sorry but you need {missing_perm} permissions to do this.\n"
              f"{help_string}",
        color=color
    )


def get_members_from_args(guild: discord.Guild, potential_members: Union[List[str], Tuple[str]]) -> List[discord.Member]:
    """
    Iterate over list and try
    :param guild: guild to search in
    :param potential_members: tuple or list with strings that could contain members (e.g. from command collected args)

    :return: list with all discord.Members that were extracted - can be empty
    """

    if not potential_members:  # see if something is given
        return []

    # go trough args (str)
    members_list: List[discord.Member] = []
    for arg in potential_members:

        # try to extract an id from string
        m_id: int = extract_id_from_message(arg)

        if not m_id:  # no id found - next string
            continue

        # try to get a member
        m: discord.Member = guild.get_member(m_id)

        if not m:  # searched id could be faulty - checking if member was returned
            continue
        # found a member - appending
        members_list.append(m)

    return members_list  # could be empty...


def get_expected_number_of_tips_from_args(args):
    if len(args) == 0:
        return 0  # Returning 0 so that the game uses default
    else:
        try:
            arg = int(args[-1])
            return arg if arg < 10 else 0
        except TypeError:
            return 0
        except ValueError:
            return 0
