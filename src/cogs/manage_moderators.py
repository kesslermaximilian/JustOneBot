import logging
from typing import List, Union

from discord.ext import commands
import discord

import utils as ut
import database.db as db
import database.db_access as dba
from environment import PREFIX
from cogs.settings import is_arg
from permission_management.moderator import get_mod_roles

help_toggle_mod_usage = f"`{PREFIX}mrole [role id | @role]`"


class Access(commands.Cog):
    """
    Manage who can configure the bot on your server
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @commands.command(name="mod-role", aliases=["mrole", "config-role", "selrole", "toggle_role", "crole"],
                      help="Allow roles to select the default wordpools.\n\n"
                           "This command _toggles_ the permissions for a role. \n"
                           f"Use the same command to remove it\n\n"
                           f"Use: {help_toggle_mod_usage}\n\n"

                           f"_administrator permissions required_")
    async def toggle_mod(self, ctx: commands.Context, *role):
        if not is_arg(role, 1):
            await ctx.send(
                embed=ut.make_embed(
                    name=f"This command needs one additional argument:\n\n",
                    value=f"Use: {help_toggle_mod_usage}\n\n",
                    color=ut.yellow
                ))
            return

        # get role by extracting id and tying to get role on guild
        id_input = ut.extract_id_from_message(role[0])

        role: discord.Role = ctx.guild.get_role(id_input)
        if not role:
            await ctx.send(
                embed=ut.make_embed(
                    name="No ID given",
                    value=f"This command needs a role ID or a role mention as argument to work.\n\n"
                          f"Use: {help_toggle_mod_usage}\n\n",
                    color=ut.yellow
                )
            )

        # try to get entry like this from database
        session = db.open_session()
        entry = dba.get_setting(ctx.guild.id, str(id_input), setting='mod-role', session=session)
        # wiping entry if exists to delete privileges
        if entry:
            session.delete(entry)
            session.commit()
            await ctx.send(
                embed=ut.make_embed(
                    name='Removed privileges',
                    value=f"Successfully removed mod privileges for {role.mention}",
                    color=ut.orange
                )
            )
            return

        # we need to add a user if we reach this point - let's go
        dba.add_setting(ctx.guild.id, str(id_input), setting='mod-role', set_by=ctx.author.id)
        await ctx.send(
            embed=ut.make_embed(
                name='Added privileges',
                value=f"Successfully added mod privileges for {role.mention}\n"
                      f"Everyone with this role is now able to configure the preset wordpools the bot chooses from.\n",
                footer="Use the same command again to remove those privileges again.",
                color=ut.green
            )
        )

    @commands.command(name='mroles', alias=['modroles', "modroles", "mod-roles"],
                      help='Display all roles that can configure the default wordpools')
    async def list_moderators(self, ctx):

        roles = get_mod_roles(ctx.guild)
        if not roles:
            await ctx.send(
                embed=ut.make_embed(
                    name='No moderator-roles configured',
                    value=f'{help_toggle_mod_usage} grants a role moderator permissions',
                    color=ut.yellow
                )
            )
            return

        text = '\n'.join([f'{r.mention} ID: {r.id}' for r in roles])
        await ctx.send(
            embed=ut.make_embed(
                name='Roles that can edit the used wordpools:',
                value=text
            )
        )


def setup(bot: commands.Bot):
    bot.add_cog(Access(bot))
