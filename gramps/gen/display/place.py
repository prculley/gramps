#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2014-2017  Nick Hall
# Copyright (C) 2019       Paul Culley
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
Class handling displaying of places.
"""

#---------------------------------------------------------------
#
# Python imports
#
#---------------------------------------------------------------

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from ..config import config
from ..utils.location import get_location_list
from ..lib import PlaceType as P_T
from ..lib import PlaceHierType
from ..const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


#-------------------------------------------------------------------------
#
# PlaceFormat class
#
#-------------------------------------------------------------------------
class PlaceFormat:
    """
    This class stores the basic information about the place format
    """
    def __init__(self, name, hier, language='', reverse=False, rules=None):
        self.name = name            # str name of format
        self.hier = hier            # PlaceHierType of format
        self.language = language    # Language desired of format
        self.reverse = reverse      # Order of place title names is reversed
        if rules is None:
            rules = []
        self.rules = rules          # list of rules for the format


#-------------------------------------------------------------------------
#
# PlaceRule class
#
#-------------------------------------------------------------------------
class PlaceRule:
    """
    This class stores the place format rules.
    """
    V_NONE = 0    # visibility of item; None
    V_STNUM = 1   # visibility of street/number; visible, street first
    V_NUMST = 2   # visibility of street/number; visible, number first
    V_ALL = 3     # visibility of item; All
    V_SMALL = 4   # visibility of item; Only smallest of group or type
    V_LARGE = 5   # visibility of item; Only largest of group or type
    T_GRP = 0     # What does rule work with; Place Group
    T_TYP = 1     # What does rule work with; Place Type
    T_ST_NUM = 2  # What does rule work with; Street and number
    A_NONE = -2   # indicates no abbrev, val is added to PlaceAbbrevType
    A_FIRST = -3  # indicates first abbrev, val is added to PlaceAbbrevType

    VIS_MAP = {
        V_NONE: _('Hidden'),
        V_SMALL: _("Show Smallest"),
        V_LARGE: _("Show Largest"),
        V_ALL: _("Show All"),
        V_STNUM: _("Number Street"),
        V_NUMST: _("Street Number")
    }

    def __init__(self, where, r_type, r_value, vis, abb):
        """ Place Format Rule """
        self.where = where      # None, or place handle
        self.type = r_type      # on of T_ group, type, or street/num
        self.value = r_value    # int, PlaceType group or type number
        self.vis = vis          # int, one of the V_ values above
        self.abb = abb  # PlaceAbbrevType with extra values, A_NONE, A_FIRST


#-------------------------------------------------------------------------
#
# PlaceDisplay class
#
#-------------------------------------------------------------------------
class PlaceDisplay:
    """
    This is the place title display and format storage class.
    """
    def __init__(self):
        self.place_formats = []
#         if os.path.exists(PLACE_FORMATS):
#             try:
#                 self.load_formats()
#                 return
#             except BaseException:
#                 print(_("Error in '%s' file: cannot load.") % PLACE_FORMATS)
        # initialize the default format
        _pf = PlaceFormat(_('Full'), PlaceHierType(PlaceHierType.ADMIN))
        self.place_formats.append(_pf)

    def display_event(self, _db, event, fmt=-1):
        """
        This displays an event's place title according to the specified
        format.
        """
        if not event:
            return ""
        place_handle = event.get_place_handle()
        if place_handle:
            place = _db.get_place_from_handle(place_handle)
            return self.display(_db, place, event.get_date_object(), fmt)
        return ""

    def display(self, _db, place, date=None, fmt=-1):
        """
        This is the place title display routine.  It displays a place title
        according to the format and rules defined in PlaceFormat.
        """
        if not place:
            return ""
        if not config.get('preferences.place-auto'):
            return place.title
        if fmt == -1:
            fmt = config.get('preferences.place-format')
        if fmt > len(self.place_formats) - 1:
            fmt = 0
            config.set('preferences.place-format', 0)
        _pf = self.place_formats[fmt]
        lang = _pf.language
        all_places = get_location_list(_db, place, date, lang, hier=_pf.hier)

        # Apply format to place list
        # start with everything shown
        places = {key: val[0] for key, val in enumerate(all_places)}
        for rule in _pf.rules:
            if rule.where:
                # this rule applies to a specific place
                for plac in all_places:
                    if plac[2] == rule.where:  # test if handles match
                        break   # rule is good for this place
                else:           # no match found for handle
                    continue    # skip this rule
            first = False
            if rule.type == PlaceRule.T_GRP:
                if rule.vis == PlaceRule.V_LARGE:
                    # go from largest down
                    for indx in range(len(all_places) - 1, -1, -1):
                        plac = all_places[indx]
                        if plac[1] & rule.value:
                            # match on group
                            if first:   # If we found first one already
                                places.pop(indx, None)  # remove this one
                            else:
                                first = True
                                self._show(plac, rule, places, indx)
                else:
                    # work from smallest up
                    for indx, plac in enumerate(all_places):
                        if plac[1] & rule.value:
                            # match on group
                            if rule.vis == PlaceRule.V_SMALL:
                                if first:   # If we found first one already
                                    places.pop(indx, None)  # remove this one
                                else:
                                    first = True
                                    self._show(plac, rule, places, indx)
                            elif rule.vis == PlaceRule.V_ALL:
                                self._show(plac, rule, places, indx)
                            else:   # rule.vis == PlaceRule.V_NONE:
                                places.pop(indx, None)  # remove this one
            elif rule.type == PlaceRule.T_TYP:
                if rule.vis == PlaceRule.V_LARGE:
                    # go from largest down
                    for indx in range(len(all_places) - 1, -1, -1):
                        plac = all_places[indx]
                        if plac[1].value == rule.value:
                            # match on group
                            if first:   # If we found first one already
                                places.pop(indx, None)  # remove this one
                            else:
                                first = True
                                self._show(plac, rule, places, indx)
                else:
                    # work from smallest up
                    for indx, plac in enumerate(all_places):
                        if plac[1].value == rule.value:
                            # match on group
                            if rule.vis == PlaceRule.V_SMALL:
                                if first:   # If we found first one already
                                    places.pop(indx, None)  # remove this one
                                else:
                                    first = True
                                    self._show(plac, rule, places, indx)
                            elif rule.vis == PlaceRule.V_ALL:
                                self._show(plac, rule, places, indx)
                            else:   # rule.vis == PlaceRule.V_NONE:
                                places.pop(indx, None)  # remove this one
            else:
                # we have a rule about street/number
                _st = _num = None
                for indx, plac in enumerate(all_places):
                    p_type = plac[1].value
                    if((p_type == P_T.STREET or p_type == P_T.NUMBER) and
                       rule.vis == PlaceRule.V_NONE):
                        places.pop(indx, None)  # remove this one
                    elif p_type == P_T.STREET:
                        _st = indx
                    elif p_type == P_T.NUMBER:
                        _num = indx
                if _st is not None and _num is not None:
                    if((rule.vis == PlaceRule.V_NUMST and _num < _st) or
                       (rule.vis == PlaceRule.V_STNUM and _num > _st)):
                        continue    # done with rule
                    # need to swap final names
                    street = places[_st]
                    places[_st] = places[_num]
                    places[_num] = street

        # make sure that the smallest place is included for places not
        # deeply enclosed.
        g_mask = ~(P_T.G_PLACE | P_T.G_UNPOP | P_T.G_OTHER | P_T.G_BUILDING)
        if 0 not in places and all_places[0][1] & g_mask:
            places[0] = all_places[0][0]

        names = ''
        for indx in (range(len(all_places) - 1, -1, -1) if _pf.reverse else
                     range(len(all_places))):
            name = places.get(indx, None)
            if name:
                # TODO for Arabic, should the next line's comma be translated?
                names += (", " + name) if names else name

        return names

    @staticmethod
    def _show(place, rule, places, indx):
        """
        Place is to be shown, but need to deal with abbreviations.
        place is a tuple of place to show
        rule.abb is the selected abbreviation instruction
        places is list of place tuples to show
        """
        do_abb = int(rule.abb)
        name, dummy_type, dummy_hndl, abblist = place
        if do_abb == PlaceRule.A_FIRST:
            if abblist:
                name = abblist[0].get_value()
        elif do_abb != PlaceRule.A_NONE:
            for abb in abblist:
                if rule.abb == abb.get_type():
                    name = abb.get_value()
        places[indx] = name

    def get_formats(self):
        """ return the available formats as a list """
        return self.place_formats

    def set_formats(self, formats):
        """ set a list of place formats """
        self.place_formats = formats

    def load_formats(self, formats):
        """ load formats from db """
        length = len(self.place_formats)
        for new_fmt in formats:
            for index in range(length):
                if new_fmt.name == self.place_formats[index].name:
                    continue
                self.place_formats.append(new_fmt)

displayer = PlaceDisplay()
