# -*- python -*-
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011-2016  Serge Noiraud
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
Geography for places
"""
#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import time
import operator
from gi.repository import Gdk
KEY_TAB = Gdk.KEY_Tab
from gi.repository import Gtk
from collections import defaultdict

#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
import logging
_LOG = logging.getLogger("GeoGraphy.geoplaces")

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.lib import EventType
from gramps.gen.lib.placetype import PlaceType, DM_NAME
from gramps.gen.config import config
from gramps.gen.display.place import displayer as _pd
from gramps.gen.utils.place import conv_lat_lon
from gramps.gui.views.bookmarks import PlaceBookmarks
from gramps.plugins.lib.maps.geography import GeoGraphyView
from gramps.plugins.lib.maps import constants
from gramps.gui.utils import ProgressMeter

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------

_UI_DEF = [
    '''
      <placeholder id="CommonGo">
      <section>
        <item>
          <attribute name="action">win.Back</attribute>
          <attribute name="label" translatable="yes">_Back</attribute>
        </item>
        <item>
          <attribute name="action">win.Forward</attribute>
          <attribute name="label" translatable="yes">_Forward</attribute>
        </item>
      </section>
      </placeholder>
''',
    '''
      <section id='CommonEdit' groups='RW'>
        <item>
          <attribute name="action">win.PrintView</attribute>
          <attribute name="label" translatable="yes">Print...</attribute>
        </item>
      </section>
''',
    '''
      <section id="AddEditBook">
        <item>
          <attribute name="action">win.AddBook</attribute>
          <attribute name="label" translatable="yes">_Add Bookmark</attribute>
        </item>
        <item>
          <attribute name="action">win.EditBook</attribute>
          <attribute name="label" translatable="no">%s...</attribute>
        </item>
      </section>
''' % _('Organize Bookmarks'),  # Following are the Toolbar items
    '''
    <placeholder id='CommonNavigation'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-previous</property>
        <property name="action-name">win.Back</property>
        <property name="tooltip_text" translatable="yes">'''
    '''Go to the previous object in the history</property>
        <property name="label" translatable="yes">_Back</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-next</property>
        <property name="action-name">win.Forward</property>
        <property name="tooltip_text" translatable="yes">'''
    '''Go to the next object in the history</property>
        <property name="label" translatable="yes">_Forward</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
''',
    '''
    <placeholder id='BarCommonEdit'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">document-print</property>
        <property name="action-name">win.PrintView</property>
        <property name="tooltip_text" translatable="yes">'''
    '''Print or save the Map</property>
        <property name="label" translatable="yes">Print...</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
    ''']

# pylint: disable=no-member
# pylint: disable=maybe-no-member
# pylint: disable=unused-variable
# pylint: disable=unused-argument

#-------------------------------------------------------------------------
#
# GeoView
#
#-------------------------------------------------------------------------
class GeoPlaces(GeoGraphyView):
    """
    The view used to render places map.
    """
    CONFIGSETTINGS = (
        ('geography.path', constants.GEOGRAPHY_PATH),

        ('geography.zoom', 10),
        ('geography.zoom_when_center', 12),
        ('geography.show_cross', True),
        ('geography.lock', False),
        ('geography.center-lat', 0.0),
        ('geography.center-lon', 0.0),

        ('geography.map_service', constants.OPENSTREETMAP),
        ('geography.max_places', 5000),
        ('geography.use-keypad', True),
        ('geography.personal-map', ""),

        # specific to geoplaces :

        ('geography.color.unknown', '#008b00'),
        ('geography.color.custom', '#008b00'),
        ('geography.color.country', '#008b00'),
        ('geography.color.county', '#008b00'),
        ('geography.color.state', '#008b00'),
        ('geography.color.city', '#008b00'),
        ('geography.color.parish', '#008b00'),
        ('geography.color.locality', '#008b00'),
        ('geography.color.street', '#008b00'),
        ('geography.color.province', '#008b00'),
        ('geography.color.region', '#008b00'),
        ('geography.color.department', '#008b00'),
        ('geography.color.neighborhood', '#008b00'),
        ('geography.color.district', '#008b00'),
        ('geography.color.borough', '#008b00'),
        ('geography.color.municipality', '#008b00'),
        ('geography.color.town', '#008b00'),
        ('geography.color.village', '#008b00'),
        ('geography.color.hamlet', '#008b00'),
        ('geography.color.farm', '#008b00'),
        ('geography.color.building', '#008b00'),
        ('geography.color.number', '#008b00'),
        )

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        self.window_name = _('Places map')
        GeoGraphyView.__init__(self, self.window_name,
                                      pdata, dbstate, uistate,
                                      PlaceBookmarks,
                                      nav_group)
        self.dbstate = dbstate
        self.uistate = uistate
        self.place_list = []
        self.place_without_coordinates = []
        self.minlat = self.maxlat = self.minlon = self.maxlon = 0.0
        self.minyear = 9999
        self.maxyear = 0
        self.nbplaces = 0
        self.nbmarkers = 0
        self.sort = []
        self.generic_filter = None
        self.additional_uis.append(self.additional_ui())
        self.no_show_places_in_status_bar = False
        self.show_all = False
        self.itemoption = None
        self.menu = None
        self.cal = config.get('preferences.calendar-format-report')
        self.plc_color = []
        self.plc_custom_color = defaultdict(set)

    def get_title(self):
        """
        Used to set the titlebar in the configuration window.
        """
        return _('GeoPlaces')

    def get_stock(self):
        """
        Returns the name of the stock icon to use for the display.
        This assumes that this icon has already been registered
        as a stock icon.
        """
        return 'geo-show-place'

    def get_viewtype_stock(self):
        """Type of view in category
        """
        return 'geo-show-place'

    def additional_ui(self):
        """
        Specifies the UIManager XML code that defines the menus and buttons
        associated with the interface.
        """
        return _UI_DEF

    def navigation_type(self):
        """
        Indicates the navigation type. Navigation type can be the string
        name of any of the primary objects.
        """
        return 'Place'

    def goto_handle(self, handle=None):
        """
        Rebuild the tree with the given places handle as the root.
        """
        self.places_found = []
        self.build_tree()

    def show_all_places(self, menu, event, lat, lon):
        """
        Ask to show all places.
        """
        self.show_all = True
        self.nbmarkers = 0
        self._createmap(None)

    def build_tree(self):
        """
        This is called by the parent class when the view becomes visible. Since
        all handling of visibility is now in rebuild_trees, see that for more
        information.
        """
        if not self.dbstate.is_open():
            return
        active = self.uistate.get_active('Place')
        if active:
            self._createmap(active)
        else:
            self._createmap(None)

    def _create_one_place(self, place):
        """
        Create one entry for one place with a lat/lon.
        """
        if place is None:
            return
        if self.nbplaces >= self._config.get("geography.max_places"):
            return
        descr = _pd.display(self.dbstate.db, place)
        longitude = place.get_longitude()
        latitude = place.get_latitude()
        latitude, longitude = conv_lat_lon(latitude, longitude, "D.D8")
        self.load_kml_files(place)
        # place.get_longitude and place.get_latitude return
        # one string. We have coordinates when the two values
        # contains non null string.
        if longitude and latitude:
            colour = (int(place.get_type()), self.place_color.get(
                int(place.get_type()), self.place_color[PlaceType.UNKNOWN]))
            self._append_to_places_list(descr, None, "",
                                        latitude, longitude,
                                        None, None,
                                        EventType.UNKNOWN,
                                        None, # person.gramps_id
                                        place.gramps_id,
                                        None, # event.gramps_id
                                        None, # family.gramps_id
                                        color=colour
                                       )

    def _createmap(self, place_x):
        """
        Create all markers for each people's event in the database which has
        a lat/lon.
        """
        dbstate = self.dbstate
        self.place_list = []
        self.places_found = []
        self.place_without_coordinates = []
        self.minlat = 0.0
        self.maxlat = 0.0
        self.minlon = 0.0
        self.maxlon = 0.0
        self.minyear = 9999
        self.maxyear = 0
        self.without = 0
        latitude = ""
        longitude = ""
        self.nbmarkers = 0
        self.nbplaces = 0
        self.remove_all_markers()
        self.message_layer.clear_messages()
        self.message_layer.clear_font_attributes()
        self.kml_layer.clear()
        self.no_show_places_in_status_bar = False
        _col = self._config.get
        self.setup_colors()
        # base "villes de france" : 38101 places :
        # createmap : 8'50"; create_markers : 1'23"
        # base "villes de france" : 38101 places :
        # createmap : 8'50"; create_markers : 0'07" with pixbuf optimization
        # base "villes de france" : 38101 places :
        # gramps 3.4 python 2.7 (draw_markers are estimated when moving the map)
        # 38101 places: createmap: 04'32";
        #               create_markers: 0'04"; draw markers: N/A :: 0'03"
        # 65598 places: createmap: 10'03";
        #               create_markers: 0'07"; draw markers: N/A :: 0'05"
        # gramps 3.5 python 2.7 new marker layer
        # 38101 places: createmap: 03'09";
        #               create_markers: 0'01"; draw markers: 0'04"
        # 65598 places: createmap: 08'48";
        #               create_markers: 0'01"; draw markers: 0'07"
        _LOG.debug("%s", time.strftime("start createmap : "
                   "%a %d %b %Y %H:%M:%S", time.gmtime()))
        if self.show_all:
            self.show_all = False
            try:
                places_handle = dbstate.db.get_place_handles()
            except:
                return
            progress = ProgressMeter(self.window_name,
                                     can_cancel=False,
                                     parent=self.uistate.window)
            length = len(places_handle)
            progress.set_pass(_('Selecting all places'), length)
            for place_hdl in places_handle:
                place = dbstate.db.get_place_from_handle(place_hdl)
                self._create_one_place(place)
                progress.step()
            progress.close()
        elif self.generic_filter:
            user=self.uistate.viewmanager.user
            place_list = self.generic_filter.apply(dbstate.db, user=user)
            progress = ProgressMeter(self.window_name,
                                     can_cancel=False,
                                     parent=self.uistate.window)
            length = len(place_list)
            progress.set_pass(_('Selecting all places'), length)
            for place_handle in place_list:
                place = dbstate.db.get_place_from_handle(place_handle)
                self._create_one_place(place)
                progress.step()
            progress.close()
            # reset completely the filter. It will be recreated next time.
            self.generic_filter = None
        elif place_x != None:
            place = dbstate.db.get_place_from_handle(place_x)
            self._create_one_place(place)
            self.message_layer.add_message(
                 _("Right click on the map and select 'show all places'"
                   " to show all known places with coordinates. "
                   "You can change the markers color depending on place type. "
                   "You can use filtering."))
            if place.get_latitude() != "" and place.get_longitude() != "":
                latitude, longitude = conv_lat_lon(place.get_latitude(),
                                                   place.get_longitude(),
                                                   "D.D8")
                if latitude and longitude:
                    self.osm.set_center_and_zoom(float(latitude),
                                                 float(longitude),
                                                 int(config.get(
                                                 "geography.zoom_when_center")))
        else:
            self.message_layer.add_message(
                 _("Right click on the map and select 'show all places'"
                   " to show all known places with coordinates. "
                   "You can use the history to navigate on the map. "
                   "You can change the markers color depending on place type. "
                   "You can use filtering."))
        _LOG.debug(" stop createmap.")
        _LOG.debug("%s", time.strftime("begin sort : "
                   "%a %d %b %Y %H:%M:%S", time.gmtime()))
        self.sort = sorted(self.place_list,
                           key=operator.itemgetter(0)
                          )
        _LOG.debug("%s", time.strftime("  end sort : "
                   "%a %d %b %Y %H:%M:%S", time.gmtime()))
        if self.nbmarkers > 500: # performance issue. Is it the good value ?
            self.message_layer.add_message(
                 _("The place name in the status bar is disabled."))
            self.no_show_places_in_status_bar = True
        if self.nbplaces >= self._config.get("geography.max_places"):
            self.message_layer.set_font_attributes(None, None, "red")
            self.message_layer.add_message(
                 _("The maximum number of places is reached (%d).") %
                   self._config.get("geography.max_places"))
            self.message_layer.add_message(
                 _("Some information are missing."))
            self.message_layer.add_message(
                 _("Please, use filtering to reduce this number."))
            self.message_layer.add_message(
                 _("You can modify this value in the geography option."))
            self.message_layer.add_message(
                 _("In this case, it may take time to show all markers."))

        self._create_markers()

    def bubble_message(self, event, lat, lon, marks):
        self.menu = Gtk.Menu()
        menu = self.menu
        message = ""
        prevmark = None
        for mark in marks:
            if message != "":
                add_item = Gtk.MenuItem(label=message)
                add_item.show()
                menu.append(add_item)
                self.itemoption = Gtk.Menu()
                itemoption = self.itemoption
                itemoption.show()
                add_item.set_submenu(itemoption)
                modify = Gtk.MenuItem(label=_("Edit Place"))
                modify.show()
                modify.connect("activate", self.edit_place,
                               event, lat, lon, prevmark)
                itemoption.append(modify)
                center = Gtk.MenuItem(label=_("Center on this place"))
                center.show()
                center.connect("activate", self.center_here,
                               event, lat, lon, prevmark)
                itemoption.append(center)
                place = self.dbstate.db.get_place_from_gramps_id(mark[9])
                hdle = place.get_handle()
                bookm = Gtk.MenuItem(label=_("Bookmark this place"))
                bookm.show()
                bookm.connect("activate", self.add_bookmark_from_popup, hdle)
                itemoption.append(bookm)
            message = "%s" % mark[0]
            prevmark = mark
        add_item = Gtk.MenuItem(label=message)
        add_item.show()
        menu.append(add_item)
        self.itemoption = Gtk.Menu()
        itemoption = self.itemoption
        itemoption.show()
        add_item.set_submenu(itemoption)
        modify = Gtk.MenuItem(label=_("Edit Place"))
        modify.show()
        modify.connect("activate", self.edit_place, event, lat, lon, prevmark)
        itemoption.append(modify)
        center = Gtk.MenuItem(label=_("Center on this place"))
        center.show()
        center.connect("activate", self.center_here, event, lat, lon, prevmark)
        itemoption.append(center)
        place = self.dbstate.db.get_place_from_gramps_id(mark[9])
        hdle = place.get_handle()
        bookm = Gtk.MenuItem(label=_("Bookmark this place"))
        bookm.show()
        bookm.connect("activate", self.add_bookmark_from_popup, hdle)
        itemoption.append(bookm)
        menu.popup(None, None, None,
                   None, event.button, event.time)
        return 1

    def add_specific_menu(self, menu, event, lat, lon):
        """
        Add specific entry to the navigation menu.
        """
        add_item = Gtk.MenuItem()
        add_item.show()
        menu.append(add_item)
        add_item = Gtk.MenuItem(label=_("Show all places"))
        add_item.connect("activate", self.show_all_places, event, lat, lon)
        add_item.show()
        menu.append(add_item)
        add_item = Gtk.MenuItem(label=_("Centering on Place"))
        add_item.show()
        menu.append(add_item)
        self.itemoption = Gtk.Menu()
        itemoption = self.itemoption
        itemoption.show()
        add_item.set_submenu(itemoption)
        oldplace = ""
        for mark in self.sort:
            if mark[0] != oldplace:
                oldplace = mark[0]
                modify = Gtk.MenuItem(label=mark[0])
                modify.show()
                modify.connect("activate", self.goto_place,
                               float(mark[3]), float(mark[4]))
                itemoption.append(modify)

    def goto_place(self, obj, lat, lon):
        """
        Center the map on latitude, longitude.
        """
        self.set_center(None, None, lat, lon)

    def get_default_gramplets(self):
        """
        Define the default gramplets for the sidebar and bottombar.
        """
        return (("Place Filter",),
                ())

    def specific_options(self, configdialog):
        """
        Add specific entry to the preference menu.
        Must be done in the associated view.
        """
        self.setup_colors()
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)
        names = [tup[0] for tup in PlaceType.DATAMAP.values() if tup[DM_NAME]]
        names.sort()
        row = col = 1
        for name in names:
            cfg = 'geography.color.' + ''.join(  # make a safe config name
                char for char in name.lower() if char.isalnum())
            configdialog.add_color(grid, name, row, cfg, col=col)
            row += 1
            if row > (len(names) + 1) / 2:
                row = 1
                col = 4
        scrolled_win = Gtk.ScrolledWindow()
        scrolled_win.add(grid)
        return _('The places marker color'), scrolled_win

    def setup_colors(self):
        """
        setup the marker colors from config options
        if not registered, register it.
        """
        self.place_color = {}
        names = [(typ, tup[DM_NAME]) for typ, tup in PlaceType.DATAMAP.items()
                 if tup[DM_NAME]]
        names.sort(key=lambda tup: tup[1])
        for typ, name in names:
            col_nam = 'geography.color.' + ''.join(  # make a safe config name
                char for char in name.lower() if char.isalnum())
            try:
                color = self._config.get(col_nam)
            except AttributeError:
                color = '#008b00'
                self._config.register(col_nam, color)
            if typ not in self.place_color:
                self.place_color[typ] = color.lower()
