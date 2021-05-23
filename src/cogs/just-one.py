import discord
from discord.ext import commands
from enum import Enum
from typing import NewType, List
import utils as ut


class Hint:
    def __init__(self, message: discord.Message):
        self.author = message.author
        self.hint_message = message.content
        self.valid = True

    def strike(self):
        self.valid = False

    def is_valid(self):
        return self.valid


class Phase(Enum):
    initialised = 1  # game initialised, but not started
    get_hints = 2  # game just started, collecting hints
    filter_hints = 3  # hints are displayed to non-guessers for reviewing
    show_hints = 4  # (non-duplicate) hints are displayed to guesser
    evaluation = 5  # answer and summary are computed
    finished = 6  # the game is over and can be wiped from memory now


class Game:
    def __init__(self, channel: discord.TextChannel, guesser: discord.Member, wordtype='default'):
        self.channel = channel
        self.guesser = guesser
        self.word = None
        self.hints = []
        self.wordtype = wordtype
        self.role = None
        self.sent_messages = []
        self.phase = Phase.initialised
        self.won = None
        print(f'Game started in channel {self.channel} by user {self.guesser}')

    async def remove_guesser_from_channel(self):
        # TODO: create a proper role for this channel and store it in self.role
        self.role = await self.channel.guild.create_role(name='JustOne-Guesser')
        # self.role.color = discord.Color.dark_purple()
        await self.channel.set_permissions(self.role, read_messages=False)
        # self.role = self.channel.guild.get_role(845819982986084352)
        await self.guesser.add_roles(self.role)

    async def start(self):
        await self.remove_guesser_from_channel()
        await self.show_word()
        self.phase = Phase.get_hints

    async def evaluate(self, message):
        self.phase = Phase.evaluation
        self.won = message.content == self.word
        await self.show_summary()
        self.phase = Phase.finished
        await self.clear()

    def add_hint(self, message):
        self.hints.append(Hint(message))

    async def add_guesser_to_channel(self):
        await self.guesser.remove_roles(self.role)
        await self.role.delete()

    async def show_word(self):
        self.word = getword(self.wordtype)  # generate a word
        message = await self.channel.send(
                    embed=ut.make_embed(
                        name='Neue Runde JustOne',
                        value=f'Das neue Wort lautet *{self.word}*.',
                        color=ut.green,
                        footer=f'Gebt Tipps ab, um {compute_proper_nickname(self.guesser)} zu helfen, das Wort zu erraten!'
                )
            )
        await message.add_reaction('\u2705')
        self.sent_messages.append(message)

    async def show_answers(self):
        # TODO : add reactions
        self.sent_messages.append(
            await self.channel.send(
                embed=ut.make_embed(
                    title='Tippphase beendet',
                    name='Wählt evtl. doppelte Tipps aus!',
                    color=ut.yellow
                )
            )
        )

        for hint in self.hints:
            message = await self.channel.send(
                embed=ut.make_embed(
                    name=hint.hint_message,
                    value=compute_proper_nickname(hint.author)
                )
            )
            await message.add_reaction('\u274C')
            self.sent_messages.append(message)

        message = await self.channel.send(
                     embed=ut.make_embed(
                          title='Keine doppelten Tipps?',
                          name='Dann klickt hier!'
                     )
        )
        await message.add_reaction('\u2705')
        self.sent_messages.append(message)
        self.phase = Phase.filter_hints

    async def show_hints(self):
        await self.add_guesser_to_channel()
        embedding = discord.Embed(
            title='Es ist Zeit, zu raten!',
            description='Die folgenden Tipps wurden abgegeben:'
        )

        for hint in self.hints:
            if hint.is_valid():
                embedding.add_field(name=hint.hint_message, value=f'({compute_proper_nickname(hint.author)})')

        self.sent_messages.append(await self.channel.send(embed=embedding))
        self.phase = Phase.show_hints

    async def show_summary(self):
        await self.channel.send(f' You have won the game: {self.won}')

    async def clear(self):
        # TODO: remove these messages from sent_messages, so we can call the method multiple times
        for message in self.sent_messages:
            await message.delete()


games = []


class JustOne(commands.Cog):
    """
    Manager for the popular Game 'JustOne'
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='one', help='Start a new round of just one in this text channel'
                                       'with the people of your voice channel')
    async def one(self, ctx: commands.Context):
        global games

        guesser = ctx.author
        text_channel = ctx.channel
        for game in games:
            if game.channel.id == text_channel.id:
                print('There is already a game running in this channel, aborting...')
                # TODO: maybe print a proper error message in the text channel as well?
                return

        game = Game(text_channel, guesser)
        games.append(game)
        await game.start()

    @commands.command(name='show_answers')
    async def show_answers(self, ctx: commands.Context):
        global games
        for game in games:
            if game.channel.id == ctx.channel.id:
                await game.show_answers()

    @commands.command(name='clear')
    async def clear(self, ctx: commands.Context):
        global games
        await games[0].clear()

    @commands.command(name='show_hints')
    async def show_hints(self, ctx: commands.Context):
        game = find_game(ctx.channel)
        if game is not None:
            await game.show_hints()

    """
    @commands.command()
    async def tips(self, ctx: commands.Context):
        global text_channel
        global valid_tips
        global tips
        await display_valid_tips(text_channel, tips)
    """

    @commands.Cog.listener()
    async def on_message(self, message):
        # Todo: Make on_message ignore all bot commands
        channel = message.channel
        # TODO: bot checking does not seem to work properly??
        if message.author.bot:
            print('Found a bot message. Ignoring')
            return
        # Todo: filter all commands and add them to sent_messages

        game = find_game(channel)
        if game is not None:
            if game.phase == Phase.get_hints:
                game.add_hint(message)
                await message.delete()
                return  # message has been properly processed as a hint
            if game.phase == Phase.show_hints:
                if message.author == game.guesser:
                    await game.evaluate(message)
                    await message.delete()
                    return  # message has been properly processed as the guess
                else:
                    game.sent_messages.append(message)


def find_game(channel: discord.TextChannel) -> Game:
    global games
    if games is None:
        return None
    for game in games:
        if game.phase != Phase.finished and game.channel.id == channel.id:
            return game


def compute_proper_nickname(member: discord.Member):
    if member.nick is None:
        return member.name
    else:
        return member.nick


def getword(wordtype):
    return 'Gandhi'


def setup(bot):
    bot.add_cog(JustOne(bot))