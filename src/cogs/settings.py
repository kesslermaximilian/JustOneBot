"""
Written by:
https://github.com/nonchris/
"""

from typing import List, Tuple

from discord.ext import commands

import utils as ut
import database.db as db
import database.db_access as dba
from environment import PREFIX

from environment import AVAILABLE_WORD_POOLS as available_word_lists

# TODO: Load this list by reading the json and using dict.key()
# available_word_lists = ["classic_main", "classic_weird", "extension_main", "extension_weird", "nsfw", "ghandi"]


def get_lists_names() -> List[str]:
    """
    Cheap getter of all lists available, maybe useful for external access to make accesses more beautiful
    """
    return available_word_lists


def get_list_formatted(format_symbol="_", join_style="\n") -> str:
    """
    Get the available lists in a custom, beautiful string

    :param format_symbol: Choose the markdown style each list is highlighted in
    :param join_style: string that's used to join all words together. Want comma or line break? - You choice!
    """
    replace_str = "\_"
    nice_list = [f'{format_symbol}{word.replace("_", replace_str)}{format_symbol}' for word in available_word_lists]
    return join_style.join(nice_list)


def get_set_lists(guild_id) -> str:
    """
    Get a beautiful string of all activated lists for that guild

    :returns: formatted string containing list or hint that list is empty
    """
    active_settings = dba.get_settings_for(guild_id, setting="wordlist")
    return "\n".join([s.value for s in active_settings]) if active_settings \
        else f"None - use `{PREFIX}enlist [list_name]` to add a list\n" \
             f"Or enter `{PREFIX}help settings` for more information"


async def validate_list_name(ctx: commands.Context, selection: Tuple, command_name="enlist") -> str:
    """
    Verifies if selection is given and if selection matches internal lists.

    :param ctx: discord command context
    :param selection: the tuple gained from command call
    :param command_name: Command name to be displayed in the potential help string

    :return: name of setting if valid else empty string

    """
    if not selection:
        await ctx.send(embed=ut.make_embed(
            name="Missing argument", color=ut.yellow,
            value="Hey, you need to give a wordlist.\n"
                  f"e.g. `{PREFIX}{command_name} classic_weird`"
        )
        )
        return ""

    # TODO: check if more than one input maybe enable two list at once?
    selected_list = selection[0]
    if selected_list not in available_word_lists:
        await ctx.send(embed=ut.make_embed(
            name="Wrong argument", color=ut.yellow,
            value="Hey, you need to enter a wordlist.\n"
                  f"e.g. `{PREFIX}{command_name} classic_weird`.\n"
                  f"Use `{PREFIX}lists` for a list of all available word-lists."
        )
        )
        return ""

    return selected_list


class Settings(commands.Cog):
    """Configure the lists used for your games"""

    def __init__(self, bot):
        self.vot = bot

    @commands.command(name="available", aliases=["available-list", "avl"],
                      help="Show all lists available on your server")
    async def display_available(self, ctx):
        await ctx.send(embed=ut.make_embed(
            name="Lists available",
            value=f"{get_list_formatted()}\n\n"
                  f"Use `{PREFIX}enlist [list_name]` to enable a list on your server"
        )
        )

    @commands.command(name="lists", alias=["show_lists"], help="Shows all activated list on your server")
    async def show_lists(self, ctx):
        # building a list which only contains values of the setting (list name), but only if list has entries
        active_lists = get_set_lists(ctx.guild.id)
        await ctx.send(embed=ut.make_embed(
            name="Your active lists are:", value=active_lists, color=ut.blue_light,
        )
        )

    @commands.command(name="enlist", aliases=["enable-list"],
                      help=f"Options: {get_list_formatted(join_style=', ')}\n"
                           f"Each list will be added to your selection.\n\n"
                           f"Usage: `{PREFIX}enlist [listname]`\n"
                           f"Default: _classic-main_\n"
                      # f"Use `{PREFIX}showlists` to see all enables lists\n"
                      # f"Use `{PREFIX}delist [listname]` to disable a list"
                      )
    async def enable_list(self, ctx: commands.Context, *selection):

        selected_list = await validate_list_name(ctx, selection, command_name="enlist")
        if not selected_list:
            return

        # search for matching entries that already match in database
        already_active = dba.get_setting(ctx.guild.id, selected_list, setting="wordlist")
        if already_active:
            await ctx.send(embed=ut.make_embed(
                name="Already entered", color=ut.green,
                value="Hey, this list is already used on this server.\n"
                      f"Use `{PREFIX}lists` to see all other options."
            )
            )
            return

        # creating database entry
        dba.add_setting(ctx.guild.id, selected_list, setting="wordlist", set_by=ctx.author.id)
        await ctx.send(embed=ut.make_embed(
            name="Successfully added", color=ut.green,
            value=f"The list *{selected_list}* was activated.\n\n"
                  f"Your active lists are now:\n\n{get_set_lists(ctx.guild.id)}"
        )
        )

    @commands.command(name="delist", alias=["dellist"], help="Deactivate a wordlist for your server\n\n"
                                                             f"Usage: `{PREFIX}delist [list_name]`")
    async def deactivate_list(self, ctx, *selection):

        selected_list = await validate_list_name(ctx, selection, command_name="delist")

        # deleting entry from database
        dba.del_setting(ctx.guild.id, selected_list, setting="wordlist")
        active_lists = get_set_lists(ctx.guild.id)
        await ctx.send(embed=ut.make_embed(
            name="Successfully removed",
            value=f"The list *{selected_list}* was removed.\n\n"
                  f"Your active lists are now:\n\n"
                  f"{active_lists}"
        )
        )


def setup(bot: commands.Bot):
    bot.add_cog(Settings(bot))
