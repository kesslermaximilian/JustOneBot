"""
Written by:
https://github.com/nonchris/
"""

import logging
from typing import Union, List

from sqlalchemy import select, and_, delete

import database.db as db

logger = logging.getLogger('my-bot')


def get_settings_for(guild_id: int, setting="wordlist", session=db.open_session()) -> Union[List[db.Settings], None]:
    """
    Searches db for setting in a guild that matches the setting name

    :param guild_id: id of the guild to search for
    :param setting: name of the setting to search for
    :param session: session to search with, helpful if object shall be edited, since the same session is needed fo this.

    :return: list of settings that match the given given setting name
    """

    sel_statement = select(db.Settings).where(
        and_(
            db.Settings.guild_id == guild_id,
            db.Settings.setting == setting
        )
    )
    entries = session.execute(sel_statement).all()
    return [entry[0] for entry in entries] if entries else None


def get_setting(guild_id: int, value: str,
                setting="wordlist", session=db.open_session()) -> Union[db.Settings, None]:
    """
    Searches db for one specific setting and returns if if exists

    :param guild_id: id of the guild to search for
    :param value: value of the setting to search for
    :param setting: name of the setting to search for
    :param session: session to search with, helpful if object shall be edited, since the same session is needed fo this.

    :return: database entry if exists with those specific parameters, else None
    """

    sel_statement = select(db.Settings).where(
        and_(
            db.Settings.guild_id == guild_id,
            db.Settings.setting == setting,
            db.Settings.value == value
        )
    )
    entry = session.execute(sel_statement).first()
    return entry[0] if entry else None


def add_setting(guild_id: int, value: str, setting="wordlist", set_by=0, session=db.open_session(), weight=1):
    """
    Add an entry to the settings database

    :param guild_id: id the setting is in
    :param value: value of the setting - probably name of a word-list
    :param set_by: userid of the member who entered that setting - could be neat for logs
    :param setting: setting type to add
    :param weight: weight of the setting, actually only needed for wordlist settings
    :param session: session to search with, helpful if object shall be edited, since the same session is needed fo this.
    """
    entry = db.Settings(guild_id=guild_id, setting=setting, value=value, set_by=set_by, weight=weight)
    session.add(entry)
    session.commit()


def del_setting(guild_id: int, value: str, setting="wordlist", session=db.open_session()):
    """
    Delete an entry from the settings table

    :param guild_id: id the setting is in
    :param value: value of the setting - probably name of a word-list
    :param setting: setting type to delete
    :param session: session to search with, helpful if object shall be edited, since the same session is needed fo this.
    """

    statement = delete(db.Settings).where(
        and_(
            db.Settings.guild_id == guild_id,
            db.Settings.setting == setting,
            db.Settings.value == value
        )
    )
    session.execute(statement)
    session.commit()


def get_resources_for(guild_id: int, resource_type="role", session=db.open_session()) -> Union[List[db.Settings], None]:
    """
    Searches db for resource in a guild that matches the setting name

    :param guild_id: id of the guild to search for
    :param resource_type: name of the resource to search for
    :param session: session to search with, helpful if object shall be edited, since the same session is needed fo this.

    :return: list of resources that match the given given setting name
    """

    sel_statement = select(db.Resources).where(
        and_(
            db.Resources.guild_id == guild_id,
            db.Resources.resource_type == resource_type
        )
    )
    entries = session.execute(sel_statement).all()
    return [entry[0] for entry in entries] if entries else None


def get_resources(resource_type="role", session=db.open_session()) -> Union[List[db.Resources], None]:
    """
    Searches db for resource of the given type

    :param resource_type: name of the resource to search for
    :param session: session to search with, helpful if object shall be edited, since the same session is needed fo this.
    :return: list of resources that match the given role_type
    """

    sel_statement = select(db.Resources).where(
        and_(
            db.Resources.resource_type == resource_type
        )
    )
    entries = session.execute(sel_statement).all()
    return [entry[0] for entry in entries] if entries else None


def add_resource(guild_id: int, value: int, resource_type="role", session=db.open_session()):
    """
    Add an entry to the settings database

    :param guild_id: id the resource is in
    :param value: value of the resource - probably a role or a text_channel
    :param resource_type: setting type to add
    :param session: session to search with, helpful if object shall be edited, since the same session is needed fo this.
    """
    entry = db.Resources(guild_id=guild_id, resource_type=resource_type, value=value)
    session.add(entry)
    session.commit()


def del_resource(guild_id: int, value: int, resource_type="role", session=db.open_session()):
    """
    Delete a resource from the settings table

    :param guild_id: id the setting is in
    :param value: value of the resource - probably a role or a text_channel
    :param resource_type: setting type to delete
    :param session: session to search with, helpful if object shall be edited, since the same session is needed fo this.
    """

    statement = delete(db.Resources).where(
        and_(
            db.Resources.guild_id == guild_id,
            db.Resources.resource_type == resource_type,
            db.Resources.value == value
        )
    )
    session.execute(statement)
    session.commit()
