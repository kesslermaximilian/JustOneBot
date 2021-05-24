"""
Written by:
https://github.com/nonchris/
"""

from typing import List, Tuple, Union

from discord.ext import commands
import discord

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


def is_arg_int(arg: str) -> bool:
    try:
        return bool(int(arg))
    except TypeError:
        return False


def is_second_arg(selection: Tuple) -> bool:
    if len(selection) < 2:
        return False
    return True


def get_weight_arg(selection: Tuple) -> Tuple[int, str]:
    if not is_second_arg(selection):
        return 1, "Using standard weight of one, because no explicit weight was given."

    weight = selection[1]
    if not is_arg_int(weight):
        return 1, "Assuming standard weight of one since your weight was no integer"

    if int(weight) > 100:
        return 1, f"Your weight was set to one, since {weight} is crazy :P"

    return int(weight), f"Registered weight {weight} for this list"


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
                      help="Zeigt alle verfügbaren Wörterpools an")
    async def display_available(self, ctx):
        embed = discord.Embed(
            title="Verfügbare Wörterpools",
            value=f'Verwendet `{PREFIX}enlist [list_name]`, um einen Pool hinzuzufügen',
            color=ut.green
        )
        embed.add_field(
            name='classic_main',
            value='Enthält die klassichen und gängigeren Wörter von *Just One*. Etwa 500 Stück'
        )
        embed.add_field(
            name='classic_weird',
            value='Enthält die etwas ausgefalleneren Wörter der Grundedition von *Just One*. Etwa 50 Stück'
        )
        embed.add_field(
            name='extension_main',
            value='Enthält die gängigeren Wörter der Erweiterung von *Just One*. Etwa 500 Stück'
        )
        embed.add_field(
            name='extension_weird',
            value='Enthält die etwas ausgefalleneren Wörter der Ereweiterung von *Just One*. Etwa 50 Stück'
        )
        embed.add_field(
            name='nsfw',
            value='Enthält *hust* etwas *hust* explizitere Wörter, die aus *WordSlam: Midnight* stammen. Etwa 100 Stück'
        )
        embed.add_field(
            name='gandhi',
            value='Enthält nur das Wort "Gandhi". Genau ein Wort.'
        )
        embed.add_field(
            name='Benutzung',
            value=f'Zum laden der einzelnen Wörterpools erfahrt ihr mehr unter `{PREFIX}help settings`.',
            inline=False
        )
        await ctx.send(embed=embed)

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

        # look if second
        weight, weight_msg = get_weight_arg(selection)

        # search for matching entries that already match in database
        session = db.open_session()
        already_active = dba.get_setting(ctx.guild.id, selected_list, setting="wordlist", session=session)
        # check if entry is there and has the same weight

        if already_active and already_active.weight == weight:
            await ctx.send(embed=ut.make_embed(
                name="Already entered", color=ut.green,
                value="Hey, this list is already used on this server.\n"
                      f"Use `{PREFIX}lists` to see all other options.\n",
                footer=weight_msg
            )
            )
            return

        # if entry exists but weight is different - updating weight
        if already_active:
            already_active.weight = weight
            session.add(already_active)
            session.commit()
            await ctx.send(embed=ut.make_embed(
                name="Updated weight", color=ut.green,
                value=f"List *{selected_list}* is already registered.\n"
                      f"Updated your weight to: {weight}"
            ))
            return
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
