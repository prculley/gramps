#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2015,2017  Nick Hall
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
Place Type class for Gramps
"""

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from .secondaryobj import SecondaryObject
from .datebase import DateBase
from .citationbase import CitationBase
from .const import IDENTICAL, EQUAL, DIFFERENT
from ..const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


DM_NAME = 0                 # index into DATAMAP tuple
DM_GRP = 1                  # index into DATAMAP tuple
DM_SHOW = 2                 # index into DATAMAP tuple


#-------------------------------------------------------------------------
#
# Place Type
#
#-------------------------------------------------------------------------
class PlaceType(SecondaryObject, CitationBase, DateBase):
    """
    Place Type class.

    This class is for keeping information about place types.
    This class is similar to GrampsType based classes, but has other features.
    It supports 3 ranges of types;
        1)the positive Gramps core types
        2)the negative 'numbered' custom types where the number can be
          presumed to be a definitive identifier (GOV types for example)
        3)the negative fully custom named types (usually entered manually)
    The break between the two negative types is CUSTOM, which value also serves
    as a temporary value during the creation of the fully custom named types.

    The types are further categorized into groups.  Some groups are core,
    others are assigned based on the custom place hierarchy types.

    Because the type names can now be modified in the GUI as well as hidden
    from menus and have groups modified, the DATAMAP dict is now modified in
    place when changes are made and new types are added.

    As a consequence, the place type menus in the GUI combobox are built
    as needed at runtime.

    The DATAMAP is also stored in the db and exported/imported with the XML.
    """
    # CUSTOM is also a seperator between numbered and completely custom places
    CUSTOM = -0x20000000
    _CUSTOM = CUSTOM
    UNKNOWN = 0
    _DEFAULT = UNKNOWN
    COUNTRY = 1
    STATE = 2
    COUNTY = 3
    CITY = 4
    PARISH = 5
    LOCALITY = 6
    STREET = 7
    PROVINCE = 8
    REGION = 9
    DEPARTMENT = 10
    NEIGHBORHOOD = 11
    DISTRICT = 12
    BOROUGH = 13
    MUNICIPALITY = 14
    TOWN = 15
    VILLAGE = 16
    HAMLET = 17
    FARM = 18
    BUILDING = 19
    NUMBER = 20

    G_COUNTRY = 0x1
    G_REGION = 0x2
    G_PLACE = 0x4
    G_UNPOP = 0x8
    G_BUILDING = 0x10
    # The following is defined to support expanded menus when a more
    # comprehensive group system is needed.
    G_OTHER = 0x20

    _DEFAULT = UNKNOWN

    # The data map (dict) contains a tuple with key as a type (int)
    #   text (string) - the users name for this type
    #   groups (int) bit field describing the groups the type belongs to.
    #   visible (bool) - shows up in menu if true
    # the values shown here (with positive keys) are the standard ones.
    # This is updated with user or app level changes and is stored in the db
    # as metadata.
    # The items with positive keys, cannot be deleted via the GUI
    _DATAMAP = (
        (UNKNOWN, (_("Unknown"), 0, True)),
        (CUSTOM, ('', 0, False)),
        (COUNTRY, (_("Country"), G_COUNTRY, True)),
        (STATE, (_("State"), G_REGION, True)),
        (COUNTY, (_("County"), G_REGION, True)),
        (CITY, (_("City"), G_PLACE, True)),
        (PARISH, (_("Parish"), G_REGION, True)),
        (LOCALITY, (_("Locality"), G_PLACE, True)),
        (STREET, (_("Street"), 0, True)),
        (PROVINCE, (_("Province"), G_REGION, True)),
        (REGION, (_("Region"), G_REGION, True)),
        (DEPARTMENT, (_("Department"), G_REGION, True)),
        (NEIGHBORHOOD, (_("Neighborhood"), G_PLACE, True)),
        (DISTRICT, (_("District"), G_PLACE, True)),
        (BOROUGH, (_("Borough"), G_PLACE, True)),
        (MUNICIPALITY, (_("Municipality"), G_PLACE, True)),
        (TOWN, (_("Town"), G_PLACE, True)),
        (VILLAGE, (_("Village"), G_PLACE, True)),
        (HAMLET, (_("Hamlet"), G_PLACE, True)),
        (FARM, (_("Farm"), G_PLACE, True)),
        (BUILDING, (_("Building"), G_BUILDING, True)),
        (NUMBER, (_("Number"), 0, True)),
    )

    _GROUPMAP = (
        (G_PLACE, (_("Places"), "Place")),
        (G_UNPOP, (_("Unpopulated Places"), "Unpop")),
        (G_COUNTRY, (_("Countries"), "Country")),
        (G_REGION, (_("Regions"), "Region")),
        (G_BUILDING, (_("Buildings"), "Building")),
    )

    DATAMAP = dict(_DATAMAP)    # initialize the working dicts
    GROUPMAP = dict(_GROUPMAP)
    status = 0                  # indicates that status is default

    _E2IMAP = {
        "Unknown": UNKNOWN,
        "Country": COUNTRY,
        "State": STATE,
        "County": COUNTY,
        "City": CITY,
        "Parish": PARISH,
        "Locality": LOCALITY,
        "Street": STREET,
        "Province": PROVINCE,
        "Region": REGION,
        "Department": DEPARTMENT,
        "Neighborhood": NEIGHBORHOOD,
        "District": DISTRICT,
        "Borough": BOROUGH,
        "Municipality": MUNICIPALITY,
        "Town": TOWN,
        "Village": VILLAGE,
        "Hamlet": HAMLET,
        "Farm": FARM,
        "Building": BUILDING,
        "Number": NUMBER,
    }

    _I2EMAP = {num: txt for (txt, num) in _E2IMAP.items()}

    __slots__ = ('__value', '__string')

    def __init__(self, source=None, **kwargs):
        """
        Create a new PlaceType instance, copying from the source if present.

        :param source: source data to initialize the type
        :type source: PlaceType, or int or string or tuple
        """
        self.__value = self.UNKNOWN
        self.__string = ''
        DateBase.__init__(self)
        CitationBase.__init__(self)
        if source:
            self.set(source)
        for key in kwargs:
            if key in ["value", "date", "citation_list"]:
                setattr(self, key, kwargs[key])
            else:
                raise AttributeError(
                    "PlaceType does not have property '%s'" % key)

    def serialize(self):
        """
        Convert the object to a serialized tuple of data.

        :returns: Returns the serialized tuple of data.
        :rtype: tuple
        """
        return (
            self.__value,
            DateBase.serialize(self),
            CitationBase.serialize(self),
        )

    def unserialize(self, data):
        """
        Convert a serialized tuple of data to an object.

        :param data: serialized tuple of data from an object.
        :type data: tuple
        :returns: Returns the PlaceType containing the unserialized data.
        :rtype: PlaceType
        """
        (self.__value, date, citation_list) = data
        DateBase.unserialize(self, date)
        CitationBase.unserialize(self, citation_list)
        return self

    @classmethod
    def get_schema(cls):
        """
        Returns the JSON Schema for this class.

        :returns: Returns a dict containing the schema.
        :rtype: dict
        """
        from .date import Date
        return {
            "type": "object",
            "title": _("Place Type"),
            "properties": {
                "_class": {"enum": [cls.__name__]},
                "value": {"type": "integer",
                          "title": _("Value")},
                "date": {"oneOf": [{"type": "null"}, Date.get_schema()],
                         "title": _("Date")},
                "citation_list": {"type": "array",
                                  "title": _("Citations"),
                                  "items": {"type": "string",
                                            "maxLength": 50}},
            }
        }

    @classmethod
    def reset_to_defaults(cls):
        """ Reset the maps to their default value
        """
        cls.DATAMAP = dict(cls._DATAMAP)
        cls.GROUPMAP = dict(cls._GROUPMAP)
        cls.status = 0

    @staticmethod
    def get_text_data_list():
        """
        Return the list of all textual attributes of the object.

        :returns: Returns the list of all textual attributes of the object.
        :rtype: list
        """
        return []

    @staticmethod
    def get_text_data_child_list():
        """
        Return the list of child objects that may carry textual data.

        :returns: list of child objects that may carry textual data.
        :rtype: list
        """
        return []

    def get_referenced_handles(self):
        """
        Return the list of (classname, handle) tuples for all directly
        referenced primary objects.

        :returns: Returns the list of (classname, handle) tuples for referenced
                  objects.
        :rtype: list
        """
        return self.get_referenced_citation_handles()

    @staticmethod
    def get_handle_referents():
        """
        Return the list of child objects which may, directly or through their
        children, reference primary objects.

        :returns: Returns the list of objects referencing primary objects.
        :rtype: list
        """
        return []

    def is_equivalent(self, other):
        """
        Return if this PlaceType is equivalent, that is agrees in type and
        date, to other.

        :param other: The PlaceType to compare this one to.
        :type other: PlaceType
        :returns: Constant indicating degree of equivalence.
        :rtype: int
        """
        if self.__value != other.value or self.date != other.date:
            return DIFFERENT
        if self.is_equal(other):
            return IDENTICAL
        return EQUAL

    def __eq__(self, other):
        if isinstance(other, int):
            return self.__value == other
        return self.is_equal(other)

    def __ne__(self, other):
        if isinstance(other, int):
            return self.__value != other
        return not self.is_equal(other)

    def __str__(self):
        if self.__value == self.CUSTOM:
            return self.__string
        return self.DATAMAP.get(self.__value,
                                self.DATAMAP[self.UNKNOWN])[DM_NAME]

    def __int__(self):
        return self.__value

    def is_empty(self):
        """ Determine if this PlaceType is empty (not changed from initial
        value)
        """
        return (self.__value == PlaceType.UNKNOWN and
                self.date.is_empty() and not self.citation_list)

    def is_custom(self):
        """ This type is a temporary value assigned to indicate that the type
        is stored as a string in self.__string

        :returns: True if the temp value is in use.
        :rtype: bool
        """
        return self.__value == self.CUSTOM

    def is_manual_custom(self):
        """ This type is assigned manually; the type number should not be
        exported in XML as it might conflict with other manual assignements
        when importing from other databases.  In this case the types are
        exported by type name and on import are either matched by name or
        created anew.

        :returns: True if the value is manualy assigned.
        :rtype: bool
        """
        return self.__value < self.CUSTOM

    def is_numbered(self):
        """ This type is either a fixed Gramps type, or can reasonably be
        expected to have a custom type number that would not change its
        name or meaning.  An example would be GOV types.

        :returns: True if the value is in the numbered region.
        :rtype: bool
        """
        return self.__value > self.CUSTOM

    def is_custom_numbered(self):
        """ This type can reasonably be expected to have a custom type number
        that would not change its name or meaning.  An example would be
        GOV types.

        :returns: True if the value is in the numbered region.
        :rtype: bool
        """
        return self.__value > self.CUSTOM and self.__value < 0

    def __and__(self, other):
        """ This allows the '&' between the PlaceType and
        the PlaceType.G_xxx values for testing group membership.

        :param other: the PlaceType int value to compare.
        :type other: int
        :returns: int value of bitwise and, can treat as bool for testing.
        :rtype: int
        """
        return self.DATAMAP.get(self.__value, 0)[DM_GRP] & other

    def set_from_xml_str(self, value):
        """
        This method sets the type instance based on the untranslated string
        (obtained e.g. from XML) or the translated string.

        :param value: the string name of a type.
        :type value: string
        """
        if value.capitalize() in self._E2IMAP:  # test for original PlaceType
            self.__value = self._E2IMAP[value]
            return
        # see if we already have a matching custom value
        for key, tup in self.DATAMAP.items():
            if value.lower() == tup[DM_NAME].lower():
                self.__value = key
                return
        # Must be a completely new type
        self.__value = self.new()
        name = self.valid_name(value, p_type=self.__value)
        self.DATAMAP[self.__value] = (name, self.G_PLACE, True)
        if not self.status:
            self.status = 1

    def xml_str(self):
        """
        Return the untranslated string (e.g. suitable for XML) corresponding
        to the type.

        :returns: XML string.
        :rtype: string
        """
        if self.__value == self.CUSTOM:
            return ''
        if self.__value in self._I2EMAP:
            return self._I2EMAP[self.__value]
        return self.DATAMAP.get(self.__value,
                                self.DATAMAP[self.UNKNOWN])[DM_NAME]

    def set(self, value):
        """
        Set the value/string properties from the passed in value.

        :param value: the PlaceType, tuple, int or str to set.
        :type value: PlaceType, tuple, int or string
        """
        if isinstance(value, tuple):
            # tuple len==1 known type (val,)
            # tuple len==2 known type if not CUSTOM (val, strg)
            # tuple len==2 new type if CUSTOM grouped as G_PLACE
            val = self._DEFAULT
            if value:
                val = value[0]
                if len(value) == 2:
                    if val == self.CUSTOM and value[1]:
                        self.__string = value[1]        # save for later
                        return
                if val in self.DATAMAP:
                    self.__value = val
                    return
            self.__value = val
            if val > self.CUSTOM:  # is it one of the GOV or standard types?
                # Add to the place types.
                name = self.valid_name(value[1], p_type=val)
                self.DATAMAP[val] = (name, (
                    value[2] if len(value) == 3 else self.G_PLACE), True)
                if not self.status:
                    self.status = 1
        elif isinstance(value, int):
            self.__value = value
        elif isinstance(value, self.__class__):
            self.__value = value.value
            DateBase.__init__(self, value)
            CitationBase.__init__(self, value)
        elif isinstance(value, str):
            self.set_from_xml_str(value)
        else:
            raise ValueError

    def register_custom(self):
        """
        Save the manual CUSTOM value in our datamap with a G_PLACE
        grouping and a newly chosen negative int value.
        We assume that the string is not already in the datamap, which should
        be the case if using the usual MonitoredDataType combo to create the
        place type.
        We don't save changes here, so must save in db elsewhere.
        """
        self.__value = self.new()
        name = self.valid_name(self.__string, p_type=self.__value)
        self.DATAMAP[self.__value] = (name, self.G_PLACE, True)
        if not self.status:
            self.status = 1

    def get(self):
        """ supports MonitoredDataType

        :returns: self (PlaceType).
        :rtype: PlaceType
        """
        return self

    def merge(self, acquisition):
        """
        Merge the content of acquisition into this PlaceType.

        Lost: type, date of acquisition.

        :param acquisition: the PlaceType to merge with.
        :type acquisition: PlaceType
        """
        self._merge_citation_list(acquisition)

    @classmethod
    def new(cls):
        """
        Pick a new type value to use in assigning a place type
        It should not conflict with currently assigned types
        Will start with largest number that fits in single int symbol
        and work down.

        :returns: a type value for potential use as the int PlaceType.
        :rtype: int
        """
        for val in range(-0x3fffffff, cls.CUSTOM, 1):
            if val not in cls.DATAMAP:
                return val
        raise ValueError

    @classmethod
    def get_menu(cls):
        """ This creates a menu structure suitable for StandardCustomSelector.
        It processes the DATAMAP and GROUPMAP into a menu.  Both of these are
        updated from the db as needed when types or groups are changed.
        This is called by the StandardCustomSelector.

        :returns: A menu suitable for StandardCustomSelector.
        :rtype: list
        """
        menu = []
        items = []
        # do common items
        common_only = True
        for typ, tup in cls.DATAMAP.items():
            if typ >= 100 or typ < 0:
                if typ != cls.CUSTOM:
                    common_only = False
                continue    # exclude the ADMx and custom values here
            items.append(typ)
        if common_only:
            return None
        menu.append((_("Common"), items))
        # now do all the other defined groups.
        for grp, grp_nams in cls.GROUPMAP.items():
            cont = False
            _mt = True
            items = []
            for typ, tup in sorted(cls.DATAMAP.items(),
                                   key=lambda x: x[1][DM_NAME]):
                # exclude UNKNOWN, hidden items, and CUSTOM
                if (typ and tup[DM_SHOW] and typ != cls.CUSTOM and
                    # put unassigned items in G_OTHER (if defined) or
                    # include items in current group
                    ((not tup[DM_GRP] and grp == cls.G_OTHER) or
                     tup[DM_GRP] & grp)):
                    items.append(typ)
                    if typ < 0 or typ > 512:
                        _mt = False
                    if len(items) == 20:    # Add 'cont.' for large groups
                        if cont:
                            menu.append((_("%s cont.") % grp_nams[0], items))
                        else:
                            menu.append((grp_nams[0], items))
                        cont = True
                        items = []
            if items and not _mt:
                if cont:
                    menu.append((_("%s cont.") % grp_nams[0], items))
                else:
                    menu.append((grp_nams[0], items))
        return menu

    def get_custom(self):
        """ for compatibility with GrampsType

        :returns: The CUSTOM type value.
        :rtype: int
        """
        return self.CUSTOM

    @classmethod
    def get_map(cls):
        """ Provided to make the class a bit more like GrampsType

        :returns: a dict of type:name elements
        :rtype: dict
        """
        return {key: val[0] for key, val in cls.DATAMAP.items()}

    @classmethod
    def valid_name(cls, name, p_type=0):
        """ Check for a valid, non-duplicated name and return a good one.

        :param p_type: the int value of a potential type from new() or GOV.
        :type p_type: int
        :returns: Valid PlaceType name.
        :rtype: string
        """
        suffix_n = 1
        suffix = ''
        while True:
            for tup in cls.DATAMAP.values():
                if (name + suffix).lower() == tup[DM_NAME].lower():  # conflict
                    if p_type < 0 and p_type > cls.CUSTOM:     # a GOV type
                        name += str(-p_type)
                        break
                    else:
                        suffix = '_' + str(suffix_n)
                        suffix_n += 1
                        break
            else:
                return name + suffix

    @classmethod
    def add_group(cls, name):
        """ adds a new group, usually based on hierarchy types.  Only supports
        30 - (standard base groups) possible additional groups.
        We don't save changes here, so must save in db elsewhere.
        If group already exists, no change

        :param name: the new group name.
        :type p_type: string
        :returns: the group number
        :rtype: int
        """
        nam_low = name.lower()
        for typ, tup in cls.GROUPMAP.items():
            if nam_low == tup[0].lower() or nam_low == tup[1].lower():
                return typ
        for gnum in range(cls.G_OTHER + 1, 30):
            if (1 << gnum) not in cls.GROUPMAP:
                cls.GROUPMAP[1 << gnum] = (name, name)
                if not cls.status:
                    cls.status = 1
                return 1 << gnum
        raise AttributeError

    @classmethod
    def set_db_data(cls, data):
        """
        loads customized place type data from the db
        If the current state is default, then loads it all.
        Otherwise the db place type data is merged into the current state;
        this happens when we load a second db.

        :param data: The customized place type data
        :type data: tuple
        """
        if not data:
            return
        if not cls.status:
            # default state
            cls.DATAMAP = data[0]
            cls.GROUPMAP = data[1]
            cls.status = 1
            return
        groupmap = data[1]
        datamap = data[0]
        db_group_to_group = {}
        for typ, tup in groupmap.items():
            # add/merge the groups, saving the new group numbers in dict
            db_group_to_group[typ] = cls.add_group(tup[1])
        for typ, ntup in datamap.items():
            # add/merge the types
            if typ > PlaceType.CUSTOM:
                # type number is good
                if typ in cls.DATAMAP:
                    continue  # found it, no change to DATAMAP
                n_typ = typ
            else:
                # type number is invalid, use name
                _ok = False
                for tup in cls.DATAMAP.values():
                    if ntup[DM_NAME].lower() == tup[DM_NAME].lower():
                        _ok = True  # found it, need to continue outer loop
                        break
                else:
                    # must be new type
                    n_typ = cls.new()
                if _ok:     # if we found the type, no change to DATAMAP
                    continue
            name = cls.valid_name(ntup[DM_NAME], p_type=n_typ)
            groups = 0  # start with no groups
            for grp in db_group_to_group:
                if grp & ntup[DM_GRP]:  # if type is member of group
                    # set our group with our group # as converted from db #
                    groups |= db_group_to_group[grp]
            cls.DATAMAP[n_typ] = (name, groups, True)
        cls.status += 1  # keep track of state, number of open dbs

    @classmethod
    def get_db_data(cls, close):
        """
        Gets customized place type data into a tuple for the db

        :param close: True if the db is closing
        :type close: bool
        :returns: tuple object to store in db metadata
        :rtype: tuple
        """
        ret_data = (cls.DATAMAP, cls.GROUPMAP)
        if close:
            if cls.status:
                cls.status -= 1
                if cls.status == 0:
                    PlaceType.reset_to_defaults()
        return ret_data

    value = property(__int__, set, None, "Returns or sets integer value")
