#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2002-2006  Donald N. Allingham
# Copyright (C) 2015       Nick Hall
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

#-------------------------------------------------------------------------
#
# Standard Python modules
#
#-------------------------------------------------------------------------
from ....const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from .. import Rule
from ....lib import PlaceType

#-------------------------------------------------------------------------
#
# HasData
#
#-------------------------------------------------------------------------
class HasData(Rule):
    """
    Rule that checks for a place with a particular value
    """

    labels = [ _('Name:'),
                    _('Place type:'),
                    ]
    name = _('Places matching parameters')
    description = _('Matches places with particular parameters')
    category = _('General filters')
    allow_regex = True

    def prepare(self, db, user):
        self.place_type = self.list[1]

        if self.place_type:
            self.place_type = PlaceType()
            self.place_type.set_from_xml_str(self.list[1])

    def apply(self, _db, place):
        if not self.match_name(place):
            return False

        if self.place_type:
            for typ in place.get_types():  # place types list
                if typ.value == self.place_type.value:
                    return True
            return False

        return True

    def match_name(self, place):
        """
        Match any name in a list of names.
        """
        for name in place.get_names():
            if self.match_substring(0, name.get_value()):
                return True
        return False
