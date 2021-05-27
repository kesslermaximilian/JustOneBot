# Features
This discord bot is used to play the popular party game [JustOne](https://www.rprod.com/en/games/just-one). It was implemented as a project at the Pfingstakademie of the CdE in 2021, where [nonchris](https://github.com/nonchris) held a course about programming discord bots in python. Roman ([Pyth42goras](https://github.com/Pyth42goras)) and I then programmed this bot as a project, with much help by Chris. We are very thankful for such a great course, and that he helped us in major parts with this project, which we could not have achieved without him. The bot is currently running in german, an english mode is to be added.

## Game 
- Start a game in an arbitrary channel using `j!play`. The bot will now automatically guide you through the game and take care of:
     - Removing the guessing person from the channel, so she cannot see its contents anymore
     - Draw a word and show it to the other participants in the channel
     - The bot now collects hints from the players. Just send them into the channel, the bot will delete them so that others cannot (yet) see them. Note that due to Discord API restrictions, this does not happen instantly, so if you really want to, you can (sometimes) read the messages anyways. Howevere, if you don't try to, the bot should be fast enough
     - After collecting all hints the bot shows all given hints and players have to eliminate the doubled ones by reacting to the messages. Then, confirm your selection
     - Now, the guesser can reenter the channel and is shown all available hints. 
     - Guess with sending your message to the channel. The bot will then automatically evaluate your guess and print a summary of the last round.
- The bot takes into account the case of an administrator participating in the round, which - obviously - cannot be expelled from the channel temporarily. The bot then creates an extra waiting channel for the admin in which he has to confirm the starting of the round so that he can't accidentally read the word. Note, however, that the bot cannot prevent the admin from coming back, trust is needed (as with everything involving admins)

## Wordpools
Choose between six different wordpools to draw words from. You can enable and even weight them. You decide!

## Moderators
Manage who can access the bots settings, i.e. the enabling/ disabling of the wordpools by setting moderator roles for the bot. Only administrators can manage the moderator roles of the bot (and are moderators as well, of course)

# Use this bot
If you want to use this bot, add it by following the link https://discord.com/api/oauth2/authorize?client_id=845738810134233178&permissions=268463184&scope=bot. The bot does not require administrator privileges, but has to be able to create / delete channels, roles and messages to handle the round correctly.

# Development
This bot is based on (https://github.com/nonchris/discord-bot) and uses `discord.py`. If you want to base on this project yourself, feel free to do so, for further details see below or at Chris' repository.

## setup
`pip install -r requirements.txt`  
`export TOKEN="your-key"`  
`python3 main.py`  
_Remember using a virtual environment!_

#### optional env variables
| parameter |  description |
| ------ |  ------ |
| `export Prefix="j!"`  | Command prefix |
| `export VERSION="unknown"` | Version the bot is running |
| `export OWNER_NAME="unknwon"` | Name of the bot owner |
| `export OWNER_ID="100000000000000000"` | ID of the bot owner |

The shown values are the default values that will be loaded if nothing else is specified.


### dependencies 
This project is based on `discord.py V1.x` minimum required: V1.5.1

## Contribute
Want to contribute to this project? We are happy for any advice or request for other features / modes that the bot supports. Also, you can send us your custom word list we can add it to the bot (if the words are appropriate). You can also report issues or bugs here at GitHub.


# Enjoy
We hope you enjoy playing the game. If so, consider buying it as a card game as well to support the inventors of the game.
