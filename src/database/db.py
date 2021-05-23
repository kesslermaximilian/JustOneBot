"""
From SQLAlchemy quickstart gist by
https://github.com/nonchris/

Link to gist:
https://gist.github.com/nonchris/046f58bcefdcea5606f670b74f375254

discord bot template:
https://github.com/nonchris/discord-bot
"""

# core interface to the database
import os
import logging

import sqlalchemy.orm
from sqlalchemy import create_engine, Boolean
# base contains a metaclass that produces the right table
from sqlalchemy.ext.declarative import declarative_base
# setting up a class that represents our SQL Database
from sqlalchemy import Column, Integer, String
# prints if a table was created - neat check for making sure nothing is overwritten
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

if not os.path.exists('data/'):
    os.mkdir('data/')

engine = create_engine('sqlite:///data/main.db', echo=True)
Base: declarative_base = declarative_base()

logger = logging.getLogger('my-bot')


class Settings(Base):
    __tablename__ = 'SETTINGS'

    # setting names:
    # wordlist, mod-role

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer)    # ID of guild setting is for
    channel_id = Column(Integer)  # to make settings per channel possible
    setting = Column(String)  # type of setting - example: wordlist
    value = Column(String)    # setting value - example: name of a list
    active = Column(Boolean)  # future: maybe don't delete unused settings and rather deactivate them -> better logging?
    config_name = Column(String)  # future: name that the setting belongs to - later option for multiple presets
    weight = Column(Integer)  # future: weight for wordlist setting, not needed for e.g. mod-role setting
    set_by = Column(Integer)  # user id of person who set entry

    def __repr__(self):
        return f"<Setting: guild='{self.guild_id}', setting='{self.setting}'," \
               f"value='{self.value}', set_by='{self.set_by}'>"


# TODO: PUT YOUR ADDITIONAL TABLES HERE


@event.listens_for(Base.metadata, 'after_create')
def receive_after_create(target, connection, tables, **kw):
    """listen for the 'after_create' event"""
    logger.info('A table was created' if tables else 'No table was created')
    print('A table was created' if tables else 'No table was created')


def open_session() -> sqlalchemy.orm.Session:
    """
    :return: new active session
    """
    return sessionmaker(bind=engine)()


# creating db which doesn't happen when it should?
database = Base.metadata.create_all(bind=engine)
