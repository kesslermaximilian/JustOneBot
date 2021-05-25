import os

import discord
from discord.ext import commands

# setup of logging and env-vars
# logging must be initialized before environment, to enable logging in environment
from log_setup import logger
from environment import PREFIX, TOKEN
import database.db_access as dba

from game_management.game import find_game
import game_management.output as output
from game_management.tools import Group

"""
This bot is based on a template by nonchris
https://github.com/nonchris/discord-bot
The bot is now maintained by kesslermaximilian and nonchris on
https://github.com/kesslermaximilian/JustOneBot
"""

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)


# login message
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected')

    logger.info(f"Bot has connected, active on {len(bot.guilds)} guilds")

    print(f'Bot is connected to the following guilds:')
    print()
    member_count = 0
    for g in bot.guilds:
        print(f"{g.name} - {g.id} - Members: {g.member_count}")
        member_count += g.member_count
    print()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name=f"{PREFIX}help"))

    # Deleting all open resources from previous runs
    role_entries = dba.get_resources(resource_type="role")  # roles
    if role_entries:
        for entry in role_entries:
            for g in bot.guilds:
                if g.id == entry.guild_id:
                    try:
                        await g.get_role(entry.value).delete()
                        break  # Break the iteration over the guilds
                    except:
                        print('Role not found on this server')
            dba.del_resource(g.id, value=entry.value, resource_type="role")  # Delete role from database now

    text_channel_entries = dba.get_resources(resource_type="text_channel")  # Text Channels
    if text_channel_entries:
        for entry in text_channel_entries:
            for g in bot.guilds:
                if g.id == entry.guild_id:
                    try:
                        await g.get_channel(entry.value).delete()
                        break  # Break the iteration over the guilds
                    except:
                        print('TextChannel not found on this server')
            dba.del_resource(g.id, value=entry.value, resource_type="text_channel")  # Delete role from database now


@bot.event
async def on_message(message: discord.Message):
    always_commands = [f'{PREFIX}abort', f'{PREFIX}correct', f'{PREFIX}play']  # TODO starts with this...
    game = find_game(message.channel)
    if game is None:
        await bot.process_commands(message)
        return
    for always_command in always_commands:
        if message.content.startswith(always_command):
            await bot.process_commands(message)
            return
    await game.message_sender.send_message(embed=output.game_running_warning(), reaction=False, group=Group.warn)


# LOADING Extensions
bot.remove_command('help')  # unload default help message
initial_extensions = [
    'cogs.misc',
    'cogs.help',
    'cogs.just_one',
    'cogs.settings',
    'cogs.manage_moderators'
]

if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

    bot.run(TOKEN)
