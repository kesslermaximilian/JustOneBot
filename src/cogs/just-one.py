import discord
from discord.ext import commands
from enum import Enum
from typing import NewType, List
import utils as ut
from environment import PREFIX, CHECK_EMOJI, DISMISS_EMOJI, DEFAULT_TIMEOUT


class Hint:
    def __init__(self, message: discord.Message):
        self.author = message.author
        self.hint_message = message.content
        self.valid = True
        self.message_id = 0

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
    def __init__(self, channel: discord.TextChannel, guesser: discord.Member, bot, wordtype='default'):
        self.channel = channel
        self.guesser = guesser
        self.guess = ""
        self.word = ""
        self.hints: List[Hint] = []
        self.wordtype = wordtype

        self.role: discord.Role = None
        self.sent_messages = []
        self.phase = Phase.initialised
        self.won = None
        self.bot = bot
        print(f'Game started in channel {self.channel} by user {self.guesser}')

    async def play(self):  # Main method to control the flow of a game
        await self.remove_guesser_from_channel()
        self.word = getword(self.wordtype)  # generate a word
        last_message = await self.show_word()  # Show the word

        self.phase = Phase.get_hints  # Now waiting for hints
        if not await self.wait_for_reaction_to_message(last_message):  # Wait for end of hint phase
            print('Did not get tips within 60 sec, fast-forwarding')
            return

        self.phase = Phase.filter_hints  # Now showing answers and filtering hints
        last_message = await self.show_answers()

        if not await self.wait_for_reaction_to_message(last_message):
            print('Did not get confirmation of marked double tips within time, fast-forwarding')
            return

        # Iterate over hints and check if they are valid

        for hint in self.hints:
            message = await self.channel.fetch_message(hint.message_id)
            for reaction in message.reactions:
                if reaction.emoji == DISMISS_EMOJI and reaction.count > 1:
                    hint.valid = False

        self.phase = Phase.show_hints
        await self.add_guesser_to_channel()
        print('Added user back to channel')
        await self.show_hints()

        guess = await self.wait_for_reaction_from_user(self.guesser)

        if guess is None:
            print('No guess found, aborting')
            return
        self.sent_messages.append(guess)

        self.guess = guess.content
        self.phase = Phase.evaluation  # Start evaluation phase
        self.won = guess.content == self.word  # TODO: have better comparing function
        await self.show_summary()
        self.phase = Phase.finished  # Start clearing, but new games can start yet
        await self.clear()
        # TODO: would be nice to actively get rid of the class, is this possible? (where is the scope?)

    async def show_word(self) -> discord.Message:
        return await self.send_message(
            embed=ut.make_embed(
                name='Neue Runde JustOne',
                value=f'Das neue Wort lautet *{self.word}*.',
                color=ut.green,
                footer=f'Gebt Tipps ab, um {compute_proper_nickname(self.guesser)} zu helfen, das Wort zu erraten!'),
            )

    async def show_answers(self):
        # Inform users that hint phase has ended
        await self.send_message(
            embed=ut.make_embed(
                title='Tippphase beendet',
                name='Wählt evtl. doppelte Tipps aus!',
                color=ut.yellow
            ),
            reaction=False
        )

        # Show all hints with possible reactions
        for hint in self.hints:
            hint_message = await self.send_message(
                embed=ut.make_embed(
                    name=hint.hint_message,
                    value=compute_proper_nickname(hint.author)
                ),
                emoji=DISMISS_EMOJI
            )
            hint.message_id = hint_message.id  # Store the message id in the corresponding hint

        # Show message to confirm that invalid tips have been removed
        return await self.send_message(
             embed=ut.make_embed(
                  title='Alle doppelten Tipps markiert?',
                  name='Dann bestätigt hier!'
             )
        )

    async def show_hints(self):
        embed = discord.Embed(
            title='Es ist Zeit, zu raten!',
            description='Die folgenden Tipps wurden abgegeben:'
        )

        for hint in self.hints:
            if hint.is_valid():
                embed.add_field(name=hint.hint_message, value=f'_{compute_proper_nickname(hint.author)}_')

        await self.send_message(embed, reaction=False)

    async def show_summary(self):
        s_color = ut.green if self.won else ut.red
        embed = discord.Embed(
            title = 'Gewonnen!' if self.won else "Verloren",
            description = f"Das Wort war: `{self.word}`\n {compute_proper_nickname(self.guesser)} hat `{self.guess}` geraten.",
            color = s_color,
        )

        for hint in self.hints:
            if hint.is_valid():
                embed.add_field(name=f'`{hint.hint_message}`', value=f'_{compute_proper_nickname(hint.author)}_')
            else:
                embed.add_field(name=f"~~`{hint.hint_message}`~~", value=f'_{compute_proper_nickname(hint.author)}_')

        if not self.won:
            embed.set_footer(text='Nutzt !correct um die Antwort als richtig zu markieren')

        await self.channel.send(embed=embed)

    async def abort(self, reason: str):  # Aborting the current round. Can be either called explicitly or by timeout
        await self.channel.send(
            embed=ut.make_embed(
                title="Runde abgebrochen",
                value="Die Runde wurde abgebrochen",
                footer=reason,
                color=ut.red
            )
        )
        await self.add_guesser_to_channel()
        await self.clear()

    async def clear(self):  # Used to clear chat after round has finished
        # TODO: remove these messages from sent_messages, so we can call the method multiple times
        for message in self.sent_messages:
            try:
                await message.delete()
            except discord.NotFound:
                print(f' The message with content {message.content} could not be deleted')
        # TODO: Is this the right thing to do?
        global games
        games.remove(self)

    # Helper methods to manage communication via messages and their reactions
    async def send_message(self, embed, reaction=True, emoji=CHECK_EMOJI) -> discord.Message:
        message = await self.channel.send(embed=embed)
        if reaction:  # Only add reaction if prompted to do so
            await message.add_reaction(emoji)
        self.sent_messages.append(message)
        return message

    async def wait_for_reaction_to_message(self, message: discord.Message, emoji=CHECK_EMOJI,
                                           timeout=DEFAULT_TIMEOUT) -> bool:
        def check(reaction, user):
            #  Only respond to reactions from non-bots with the correct emoji
            return not user.bot and str(reaction.emoji) == emoji and reaction.message == message

        print(f'waiting for reaction to message {message.content}')
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=timeout, check=check)
            print('found reaction')
        except TimeoutError:
            await self.abort('TimeOut error: Keine Reaktion')
            return False
        return True

    async def wait_for_reaction_from_user(self, member):
        def check(message):
            return message.author == self.guesser and message.channel == self.channel
        try:
            message = await self.bot.wait_for('message', timeout=DEFAULT_TIMEOUT, check=check)
        except TimeoutError:
            await self.abort('TimeOut error: Keine Antwort')
            return None
        return message

    # Helper methods to manage user access to channel
    async def remove_guesser_from_channel(self):
        # TODO: create a proper role for this channel and store it in self.role
        self.role = await self.channel.guild.create_role(name='JustOne-Guesser')
        # self.role.color = discord.Color.dark_purple()
        await self.channel.set_permissions(self.role, read_messages=False)
        # self.role = self.channel.guild.get_role(845819982986084352)
        await self.guesser.add_roles(self.role)

    async def add_guesser_to_channel(self):
        await self.guesser.remove_roles(self.role)
        await self.role.delete()
        print('Role deleted')

    # External methods called by listeners
    def add_hint(self, message):
        self.hints.append(Hint(message))

# End of Class Game


games = []  # Global variable (what a shame!)


class JustOne(commands.Cog):
    """
    Manager for the popular Game 'JustOne'
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='play', help='Start a new round of just one in this text channel'
                                       'with the people of your voice channel')
    async def play(self, ctx: commands.Context):
        global games

        guesser = ctx.author
        text_channel = ctx.channel
        for game in games:
            if game.channel.id == text_channel.id and not game.phase == Phase.finished:
                print('There is already a game running in this channel, aborting...')
                game.sent_messages.append(ctx.message)  # Delete the command at the end of the game
                await game.send_message(  # Show an error message that a game is running
                    embed=ut.make_embed(
                        title="Oops!",
                        value="In diesem Kanal läuft bereits eine Runde JustOne, du kannst keine neue starten",
                        color=ut.red
                    ),
                    reaction=False
                )
                break
        else:  # Execute this if no break was found, i.e. there is no game running
            game = Game(text_channel, guesser, bot=self.bot)
            games.append(game)
            await game.play()

    @commands.command(name='help_message')
    async def help_message(self, ctx):
        await help_message(ctx.channel, ctx.message.author)

    @commands.command(name='abort', help='Bricht die aktuelle Runde im Kanal ab')
    async def channel(self,ctx : commands.Context):
        game = find_game(ctx.channel)
        if game is None:
            return
        else:
            await game.abort('manueller Abbruch')

    @commands.command(name='show_answers')
    async def show_answers(self, ctx: commands.Context):
        global games
        for game in games:
            if game.channel.id == ctx.channel.id:
                await game.show_answers()

    @commands.command(name='clear')
    async def clear(self, ctx: commands.Context):
        game = find_game(ctx.channel)
        if game is None:
            return
        await game.clear()

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
        channel = message.channel
        game = find_game(channel)
        if game is None:
            return  # since no game is running in this channel, nothing has to be done

        if message.author.bot:
            print('Found a bot message. Ignoring')  # TODO: what if this was another bot?
            return

        if message.content.startswith(PREFIX):
            print('Found a own bot command, ignoring it')
            game.sent_messages.append(message)

        if game.phase == Phase.get_hints:
            game.add_hint(message)
            await message.delete()  # message has been properly processed as a hint
        elif game.phase == Phase.show_hints:
            if message.author != game.guesser:
                game.sent_messages.append(message)  # message was not relevant for game, but still deleting (for log)
        else:  # game is not in a phase to process messages (should be Phase.filter_hints)
            game.sent_messages.append(message)


# Helping methods

def find_game(channel: discord.TextChannel) -> Game:
    global games
    if games is None:
        return None
    for game in games:
        if game.phase != Phase.finished and game.channel.id == channel.id:
            return game


def compute_proper_nickname(member: discord.Member):
    return member.nick if member.nick else member.name


async def help_message(channel: discord.TextChannel, member: discord.Member) -> discord.Embed:  # Prints a proper help message for JustOne
    embed = discord.Embed(
        title=f'Was is JustOne?',
        description=f'Hello, {member.mention}. JustOne ist ein beliebtes Paryspiel von  *Ludovic Roudy* und *Bruno Sautter*\n'
                    f'Das Spiel ist kollaborativ, Ziel ist es, dass eine Person ein ihr unbekanntes Wort errät\n'
                    f'Dazu wird dieses Wort allen Mitspielern genannt, die sich einen Tipp - *ein* Wort - ausdenken '
                    f'dürfen. Doch Vorsicht! Geben 2 oder mehr Spieler den (semantisch) gleichen Tipp, so darf der '
                    f'ratende Spieler diesen nicht ansehen! Ihr dürft euch beim Ausdenken der Tipps also nicht '
                    f'untereinander absprechen. Seid also geschickt, um so eurem Ahnungslosen Freund zu helfen, das '
                    f'Lösungswort zu erraten',
        color=ut.orange,
        footer='Dieser Bot ist noch unstabil. Bei Bugs, gebt uns auf [GitHub]'
               '(https://github.com/kesslermaximilian/JustOneBot) Bescheid!)'
    )
    embed.add_field(
        name='Spielstart',
        value='Startet das Spiel in einem beliebigen Textkanal auf dem Server mit `!play`. '
              'Derjenige von euch, der den Befehl eingibt, ist auch derjenige, der Raten muss',
        inline=False
    )
    embed.add_field(
        name='Tippphase',
        value='Der ratende Spieler kann nun die Nachrichten des Textkanals nicht mehr lesen, macht euch also um'
              ' Schummler keine Sorgen! Ihr könnt nun alle *einen* Tipp abgeben, indem ihr einfach eine Nachricht'
              ' in den Kanal schickt. Der Bot löscht diese automatisch, damit ihr sie nicht gegenseitig seht.'
              ' Doch keine Sorge, der Bot merkt sich natürlich eure Tipps!',
        inline=False
    )
    embed.add_field(
        name='Fertig? Dann Tipps vergleichen!',
        value=f'Bestätigt nun dem Bot, dass ihr eure Tipps gegeben habt, indem ihr auf den {CHECK_EMOJI} klickt. '
              f'Der Bot zeigt euch nun die abgegebenen Antworten an, markiert alle doppelten, indem ihr mit '
              f'{DISMISS_EMOJI} reagiert. Bestätigt auch dann die Auswahl unter der letzten Nachricht mit einem'
              f' {CHECK_EMOJI}',
        inline=False
    )
    embed.add_field(
        name='Raten!',
        value='Die ratende Person kann nun den Channel automatisch wieder betreten und eine Antwort eingeben, der Bot'
              ' wertet diese automatisch aus und zeigt euch dann eine Zusammenfassung eurer Runde',
        inline=False
    )
    embed.add_field(
        name='Viel Spaß!',
        value='Waruf wartet ihr nowh! Sucht euch einen Kanal und beginnt eure Erste Runde *JustOne*',
        inline=False
    )

    await channel.send(embed=embed)

# Method to draw a word used for the game


def getword(wordtype):
    return 'Gandhi'

# Setup the bot if this extension is loaded


def setup(bot):
    bot.add_cog(JustOne(bot))


"""
Todo:
get_word : wie lese ich files ein etc
speichern / loggen von games
listener on_message channel spezifische an/ ausschalten.
help / settings
"""
