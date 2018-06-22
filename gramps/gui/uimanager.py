#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015      Nick Hall
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
A replacement UIManager and ActionGroup.
"""

import xml.etree.ElementTree as ET
from gi.repository import GLib, Gio, Gtk
import copy

ACTION_NAME = 0  # tuple index for action name
ACTION_CB = 1    # tuple index for action callback
ACTION_ST = 2    # tuple index for action state


class ActionGroup():
    """ This class represents a group of actions that con be manipulated
    together.
    """
    def __init__(self, name, actionlist=[]):
        """
        @param name: the action group name, used to match to the 'groups'
                     attribute in the ui xml.
        @type name: string
        @type actionlist: list
        @param actionlist: the list of actions to add
            The list contains tuples with the following contents:
            string: Action Name
            method: signal callback function
            state: initial state for stateful actions.
                'True' or 'False': the action is interpreted as a checkbox.
                'None': non stateful action (optional)
                'string': the action is interpreted as a Radio button
                '0': the int '0' the action is non stateful but is an
                     accelerator (the name is also the accelerator value)
        """
        self.name = name
        self.actionlist = actionlist

    def add_actions(self, actionlist):
        """  Add a list of actions to the current list
        @type actionlist: list
        @param actionlist: the list of actions to add
        """
        self.actionlist.extend(actionlist)

class UIManager():
    """
    This is Gramps UIManager, it is designed to replace the deprecated Gtk
    UIManager.  The replacement is not exact, but performs similar
    functions, in some case with the same method names and parameters.
    It is designed to be a singleton, responsible only for Gramps main
    window menus and toolbar.
    """

    def __init__(self, app, initial_xml):
        """
        @param app: Gramps Gtk.Application reference
        @type app: Gtk.Application
        @param initial_xml: Initial (primary) XML string for Gramps menus and
            toolbar
        @type changexml: string

        The xml is basically Gtk Builder xml, in particular the various menu
        and toolbar elements.  It is possible to add other elements as well.
        The xml this supports has been extended in two ways;
        1) there is an added "groups=" attribute to elements.  This
           attribute associates the element with one or more named ActionGroups
           for making the element visible or not.  If 'groups' is missing, the
           element will be shown as long as enclosing elements are shown.  The
           element will be shown if the group is present and considered visible
           by the uimanager.  If more than one group is needed, they should be
           separated by a space.
        2) there is an added <placeholder> tag supported; this is used to mark
           a place where merged UI XML can be inserted.  During the update_menu
           processing, elements enclosed in this tag pair are promoted to the
           level of the placeholder tag, and the placeholder tag is removed.

        Note that any elements can be merged (replaced) by the
        add_ui_from_string method, not just placeholders.  This works by
        matching the "id=" attribute on the element, and replacing the
        original element with the one from the add method.
        """
        self.app = app
        self.et_xml = ET.fromstring(initial_xml)
        self.builder = None
        self.toolbar = None
        self.action_groups = []
        self.show_groups = ['RW', 'RO']

    def update_menu(self, init=False):
        """ This updates the menus and toolbar when there is a change in the
        ui; any addition or removal or set_visible operation needs to call
        this.
        @param init: When True, this is first call and we set the builder
                     toolbar and menu to the application.
                     When False, we update the menus and toolbar
        @type init: bool
        """

        def iterator(parents):
            """ This recursively goes through the ET xml and deals with the
            'groups' attribute and <placeholder> tags, which are not valid for
            builder.
            Groups processing removes elements that are not shown, as well as
            the 'groups' attribute itself.
            <placeholder> tags are removed and their enclosed elements are
            promoted to the level of the placeholder.

            @param parents: the current element to recursively process
            @type parents: ET element
            """
            indx = 0
            while indx < len(parents):
                child = parents[indx]
                if len(child) >= 1:
                    iterator(child)
                # print(child.attrib)
                groups = child.get('groups')
                if not groups:
                    indx += 1
                    continue
                del child.attrib['groups']
                for group in groups.split(' '):
                    if group in self.show_groups:
                        indx += 1
                        break
                    else:
                        print('del', child.tag, child.attrib, parents.tag, parents.attrib)
                        del parents[indx]
                        break
            # The following looks for 'placeholder' elements and if found,
            # promotes any children to the same level as the placeholder.
            # this allows the user to insert elements without using a section.
            indx = 0
            while indx < len(parents):
                if parents[indx].tag == "placeholder":
                    subtree = parents[indx]
                    print('placholder del', parents[indx].tag, parents[indx].attrib, parents.tag, parents.attrib)
                    del parents[indx]
                    for child in subtree:
                        parents.insert(indx, child)
                        indx += 1
                else:
                    indx += 1

        if self.builder:
            toolbar = self.builder.get_object("ToolBar")  # previous toolbar
        # need to copy the tree so we can preserve original for later edits.
        editable = copy.deepcopy(self.et_xml)
        iterator(editable)  # clean up tree to builder specifications
        xml_str = ET.tostring(editable, encoding="unicode")
        print(xml_str)
        self.builder = Gtk.Builder.new_from_string(xml_str, -1)
        if init:
            self.app.menubar = self.builder.get_object("menubar")
            self.app.set_menubar(self.app.menubar)
            return
        # the following is the only way I have found to update the menus
        self.app.menubar.remove_all()
        menu_list = [('m1', "_Family Trees"),
                     ('m2', "_Add"),
                     ('m3', "_Edit"),
                     ('m4', "_View"),
                     ('m5', "_Go"),
                     ('m6', "_Bookmarks"),
                     ('m7', "_Reports"),
                     ('m8', "_Tools"),
                     ('m9', "_Windows"),
                     ('m10', "_Help"),
                     ]
        for item_id, label in menu_list:
            menuitem = self.builder.get_object(item_id)
            if menuitem:
                self.app.menubar.append_submenu(label, menuitem)
        # the following updates the toolbar from the new builder
        #toolbar = self.app.window.grid.get_child_at(0, 0)
        toolbar_parent = toolbar.get_parent()
        toolbar_parent.remove(toolbar)
        toolbar = self.builder.get_object("ToolBar")  # new toolbar
        toolbar_parent.pack_start(toolbar, False, True, 0)
        toolbar.show_all()

    def add_ui_from_string(self, changexml):
        """ This performs a merge operation on the xml elements that have
        matching 'id's between the current ui xml and change xml strings.
        The 'change' is a list of xml strings used to replace
        matching elements in the current xml.

        There MUST one and only one matching id in the orig xml.
        @param changexml: list of xml fragments to merge into main
        @type changexml: list
        @return: changexml
        """
        for xml in changexml:
            update = ET.fromstring(xml)
            el_id = update.attrib['id']
            parent = self.et_xml.find(".//*[@id='%s'].." % el_id)
            for indx in range(len(parent)):
                if parent[indx].get('id') == el_id:
                    del parent[indx]
                    parent.insert(indx, update)
        results = ET.tostring(self.et_xml, encoding="unicode")
        print(results)
        return changexml

    def remove_ui(self, change_xml):
        """ This removes the 'change_xml' from the current ui xml.  It works on
        any element with matching 'id', the actual element remains but any
        children are removed.
        The 'change' is a list of xml strings originally used to replace
        matching elements in the current ui xml.
        @param changexml: list of xml fragments to remove from main
        @type changexml: list
        """
        for xml in change_xml:
            update = ET.fromstring(xml)
            el_id = update.attrib['id']
            element = self.et_xml.find(".//*[@id='%s']" % el_id)
            for dummy in range(len(element)):
                del element[0]
        results = ET.tostring(self.et_xml, encoding="unicode")
        print(results)
        return results

    def get_widget(self, obj):
        """ Get the object from the builder.
        @param obj: the widget to get
        @type obj: string
        @return: the object
        """
        return self.builder.get_object(obj)

    def insert_action_group(self, group, pos):
        """
        This inserts (actually overwrites any matching actions) the action
        group's actions to the app.

        @param group: the action group
        @type group: ActionGroup
        @param pos: the position of the action group (not used)
        @type pos: int
        """
        for item in group.actionlist:
            if len(item) == 2 or item[ACTION_ST] is None:
                action = Gio.SimpleAction.new(item[ACTION_NAME], None)
                action.connect("activate", item[ACTION_CB])
            elif isinstance(item[ACTION_ST], str):
                action = Gio.SimpleAction.new_stateful(
                    item[ACTION_NAME], GLib.VariantType.new("s"),
                    GLib.Variant("s", item[ACTION_ST]))
                action.connect("change-state", item[ACTION_CB])
            elif isinstance(item[ACTION_ST], bool):
                action = Gio.SimpleAction.new_stateful(
                    item[ACTION_NAME], None,
                    GLib.Variant.new_boolean(item[ACTION_ST]))
                action.connect("change-state", item[ACTION_CB])
            elif isinstance(item[ACTION_ST], int):
                action = Gio.SimpleAction.new(item[ACTION_NAME], None)
                action.connect("activate", item[ACTION_CB])
                self.app.set_accels_for_action('win.' + item[ACTION_NAME],
                                               [item[ACTION_NAME]])
            self.app.window.add_action(action)
        self.action_groups.append(group)

    def remove_action_group(self, group):
        """ This removes the ActionGroup from the UIManager

        @param group: the action group
        @type group: ActionGroup
        """
        for item in group.actionlist:
            self.app.window.remove_action(item[ACTION_NAME])
        self.action_groups.remove(group)

    def get_action_groups(self):
        """ This returns a list of action Groups installed into the UIManager.
        @return: list of groups
        """
        return self.action_groups

    def set_actions_sensitive(self, group, value):
        """ This sets an ActionGroup enabled or disabled.  A disabled action
        will be greyed out in the UI.

        @param group: the action group
        @type group: ActionGroup
        @param value: the state of the group
        @type value: bool
        """
        for item in group.actionlist:
            action = self.app.window.lookup_action(item[ACTION_NAME])
            if action:
                action.set_enabled(value)

    def get_actions_sensitive(self, group):
        """ This sets an ActionGroup enabled or disabled.  A disabled action
        will be greyed out in the UI.

        @param group: the action group
        @type group: ActionGroup
        @return: the state of the group
        """
        item = group.actionlist[0]
        action = self.app.window.lookup_action(item[ACTION_NAME])
        return action.get_enabled()

    def set_actions_visible(self, group, value):
        """ This sets an ActionGroup visible and enabled or invisible and
        disabled.

        @param group: the action group
        @type group: ActionGroup
        @param value: the state of the group
        @type value: bool
        """
        self.set_actions_sensitive(group, value)
        if value:
            if group.name not in self.show_groups:
                self.show_groups.append(group.name)
        else:
            if group.name in self.show_groups:
                self.show_groups.remove(group.name)

    def get_action(self, actionname):
        """ Return a single action from the group.
        @param actionname: the action name
        @type actionname: string
        @return: Gio.Action
        """
        return self.app.window.lookup_action(actionname)
