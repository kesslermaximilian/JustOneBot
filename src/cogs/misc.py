import discord
from discord.ext import commands

import utils as ut


class Misc(commands.Cog):
    """
    Various useful Commands for everyone
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ping', help="Check if Bot available")
    async def ping(self, ctx):
        print(f"ping: {round(self.bot.latency * 1000)}")

        await ctx.send(
            embed=ut.make_embed(
                name='Poll-Bot is available',
                value=f'`{round(self.bot.latency * 1000)}ms`')
        )

    @commands.command()
    async def op(self,ctx):
        if ctx.guild.get_role(845742294409412608) in ctx.author.roles:
            await ctx.author.add_roles(ctx.guild.get_role(845701730200453150))
        else:
            await ctx.channel.send(
                embed=ut.make_embed(
                    title="Nein, so nicht!",
                    value="Du kriegst von mir keine Admin-Rechte!",
                    color=ut.red
                )
            )


    @commands.command()
    async def deop(self,ctx):
        role = ctx.guild.get_role(845701730200453150)
        if role in ctx.author.roles:
            await ctx.author.remove_roles(role)


def setup(bot):
    bot.add_cog(Misc(bot))
