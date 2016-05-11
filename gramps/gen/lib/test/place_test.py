#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016 Gramps Development Team
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

""" Tests for gramps.gen.lib.place """

import unittest

from gramps.gen.lib import Place, PlaceName
from gramps.gen.lib.struct import from_struct

class PlaceTest(unittest.TestCase):
    def test_place_01(self):
        place1 = from_struct({
            "_class": "Place", 
            "alt_names": [
                {"_class": "PlaceName", 
                 "value": "My Town"},
                {"_class": "PlaceName", 
                 "value": "Another Town"},
                {"_class": "PlaceName", 
                 "value": ""},
            ]
        })
        place2 = from_struct({
            "_class": "Place", 
            "alt_names": [
                {"_class": "PlaceName", 
                 "value": "Another Town"},
            ]
        })
        place2.merge(place1) # pn1, pn2; pn3 should be ignored
        self.assertEqual(len(place2.alt_names), 2, place2.alt_names)

if __name__ == "__main__":
    unittest.main()
