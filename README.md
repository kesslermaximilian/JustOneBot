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
## Add the bot to your server
If you want to use this bot, add it by following the link https://discord.com/api/oauth2/authorize?client_id=847593289619603497&permissions=268463184&scope=bot. The bot does not require administrator privileges, but has to be able to create / delete channels, roles and messages to handle the round correctly.

## Permissions
To function correctly, you have to grant the bot the permissions above link asks for. However, in certain situations this is not enough:
- If the channel you want to play a game in is visible to users by default, you can ignore the below, the bot will have the required permissions if you accepted the invite link as you got it.
- In case you want the bot to work in default-hidden categories or channels, you _explicitly_ have to allow your bot to 
    - See the corresponding channels
    - Have the right to manage channels and roles in the corresponding category / channel
- In case the bot lacks permissions at any time the bot throws an according 'fatal error', aborting the current round and informing the members on the server that the bot won't work with the current permission settings.
    - The error message is really scary, but as long as the bot's permissions did not change _during_ a round the bot was playing, everything is actually fine (except that the bot won't work in the current channel)
    - the bot will still try to restore all settings as they have been before the round started. This works except you took permissions from the bot during an ongoing round of the game.
    - But, of course, if e.g. the bot locks out a guesser from a channel and you _then_ remove the bot's permissions to edit the channel access, the bot can't edit the permissions to let the guesser in again.  
    - Just don't mess with the bot's permissions during a round and you will be alright

# Development
This bot is based on (https://github.com/nonchris/discord-bot) and uses `discord.py`. If you want to base on this project yourself, feel free to do so, for further details see below or at Chris' repository.

## setup
`pip install -r requirements.txt`  
`export TOKEN="your-key"`  
`python3 main.py`  
_Remember using a virtual environment!_


## Version control via git
- We use git tags and `git describe` to automatically read in the current git commit the bot is running on. This information is displayed in the `j!help` message in the footer. This way, it is possible to easily relate a running version of the bot to the exact source code the bot uses.
- This version can be overwritten by setting the environment variable via `export VERSION=` in the terminal (in the `src` directory of the bot, see below)
- Note that if you did not clone (or similar) this repository with git, the importing of the version will fail. You can then just remove all git-related lines in `environment.py` and still run the bot correctly by manually setting whatever version you like.


### optional env variables
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
