#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013-2015  Nick Hall
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Location utility functions
"""
from ..lib.date import Date, Today
from ..lib.placetype import PlaceType
from ..lib.placehiertype import PlaceHierType
from ..lib.attrtype import AttributeType
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext


#-------------------------------------------------------------------------
#
# get_location_list
#
#-------------------------------------------------------------------------
def get_location_list(db, place, date=None, lang='', hier=PlaceHierType.ADMIN):
    """
    Return a list of place names, types, and handles for display.
    the list is in order of smallest (most enclosed) to largest place.
    The list will match the date, lang and hierarchy type.
    """
    if date is None:
        date = __get_latest_date(place)
    visited = [place.handle]
    name, abbrs = __get_name(place, date, lang)
    lines = [(name, __get_type(place, date), place.handle, abbrs)]
    while True:
        handle = None
        for placeref in place.get_placeref_list():
            ref_date = placeref.get_date_object()
            if placeref.get_type() == hier and (ref_date.is_empty() or
                                                date.match_exact(ref_date)):
                handle = placeref.ref
                break
        if handle is None or handle in visited:
            break
        place = db.get_place_from_handle(handle)
        if place is None:
            break
        visited.append(handle)
        name, abbrs = __get_name(place, date, lang)
        lines.append((name, __get_type(place, date), place.handle, abbrs))
    return lines


def __get_name(place, date, lang):
    """ Gets the name for a given date and language.  Returns the str name and
    a list of abbreviations (PlaceAbbrevType)
    """
    endonym = None
    for place_name in place.get_names():
        name_date = place_name.get_date_object()
        if name_date.is_empty() or date.match_exact(name_date):
            if place_name.get_language() == lang:
                return place_name.get_value(), place_name.get_abbrevs()
            if endonym is None:
                endonym = place_name.get_value()
                abbs = place_name.get_abbrevs()
    return (endonym, abbs) if endonym is not None else ('?', [])


def __get_type(place, date):
    for place_type in place.get_types():
        type_date = place_type.get_date_object()
        if type_date.is_empty() or date.match_exact(type_date):
            return place_type
    return PlaceType(PlaceType.UNKNOWN)


def __get_latest_date(place):
    latest_date = None
    for place_name in place.get_names():
        date = place_name.get_date_object()
        if date.is_empty() or date.modifier == Date.MOD_AFTER:
            return Today()
        else:
            if date.is_compound():
                date1, date2 = date.get_start_stop_range()
                date = Date(*date2)
            if date.modifier == Date.MOD_BEFORE:
                date = date - 1
            if latest_date is None or date > latest_date:
                latest_date = date
    return latest_date

#-------------------------------------------------------------------------
#
# get_main_location
#
#-------------------------------------------------------------------------
def get_main_location(db, place, date=None):
    """
    Find all places in the hierarchy above the given place, and return the
    result as a dictionary of place types and names.
    """
    return dict([(int(place_type), name)
                 for name, place_type, dummy_hndl, dummy_abbrs
                 in get_location_list(db, place, date)
                 if not place_type.is_custom()])

#-------------------------------------------------------------------------
#
# get_locations
#
#-------------------------------------------------------------------------
def get_locations(db, place):
    """
    Determine each possible route up the place hierarchy, and return a list
    containing dictionaries of place types and names.
    """
    locations = []
    todo = [(place, [(int(place.get_type()), __get_all_names(place))],
            [place.handle])]
    while len(todo):
        place, tree, visited = todo.pop()
        for parent in place.get_placeref_list():
            if parent.ref not in visited:
                parent_place = db.get_place_from_handle(parent.ref)
                if parent_place is not None:
                    parent_tree = tree + [(int(parent_place.get_type()),
                                           __get_all_names(parent_place))]
                    parent_visited = visited + [parent.ref]
                    todo.append((parent_place, parent_tree, parent_visited))
        if len(place.get_placeref_list()) == 0:
            locations.append(dict(tree))
    return locations

def __get_all_names(place):
    return [name.get_value() for name in place.get_names()]

#-------------------------------------------------------------------------
#
# located_in
#
#-------------------------------------------------------------------------
def located_in(db, handle1, handle2):
    """
    Determine if the place identified by handle1 is located within the place
    identified by handle2.
    """
    place = db.get_place_from_handle(handle1)
    todo = [(place, [handle1])]
    while len(todo):
        place, visited = todo.pop()
        for parent in place.get_placeref_list():
            if parent.ref == handle2:
                return True
            if parent.ref not in visited:
                parent_place = db.get_place_from_handle(parent.ref)
                if parent_place is not None:
                    parent_visited = visited + [parent.ref]
                    todo.append((parent_place, parent_visited))
    return False


#-------------------------------------------------------------------------
#
# get_code (postal code)
#
#-------------------------------------------------------------------------
def get_code(place):
    """
    Returns the postal code(s) from a place that are found in attributes.
    """
    txt = ''
    for attr in place.get_attribute_list():
        if attr.type == AttributeType.POSTAL:
            txt += (_(", ") if txt else '') + attr.value
    return txt
