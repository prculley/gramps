# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017       Paul Culley <paulr2787@gmail.com>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# $Id: $
#

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
from copy import deepcopy
import datetime
import time
import re
#-------------------------------------------------------------------------
#
# GNOME libraries
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
ngettext = glocale.translation.ngettext
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.merge.diff import diff_dbs, to_struct
from gramps.gen.utils.db import get_participant_from_event
from gramps.gui.plug import tool
from gramps.gui.display import display_url
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.dialog import ErrorDialog
from gramps.gen.db.utils import import_as_dict
from gramps.gen.simple import SimpleAccess
from gramps.gui.glade import Glade
from gramps.gen.lib import (Person, Family, Event, Source, Place, Citation,
                            Media, Repository, Note, Date, Tag)
from gramps.gen.display.place import displayer as place_displayer

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------

WIKI_PAGE = 'https://gramps-project.org/wiki/index.php?title=Import_Merge_Tool'
TITLE = _("Import and merge a Gramps XML")
STATUS = 0
OBJ_TYP = 1
GID = 2
NAME = 3
DIFF_I = 4
TAG = 5
ACTION = 6
S_MISS = _("Missing")
S_ADD = _("Added")
S_DIFFERS = _("Different")
A_MERGE_L = _("Merge Left")
A_MERGE_R = _("Merge Right")
A_REPLACE = _("Replace")
A_IGNORE = _("Ignore")
A_ADD = _("Add")
A_DEL = _("Delete")
SPN_MONO = "<span font_family='monospace'>"
SPN_ = "</span>"

#------------------------------------------------------------------------
#
# Local Functions
#
#------------------------------------------------------------------------
def todate(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

def str_byte(string):
    return (string, len(string.encode("utf8")))
#------------------------------------------------------------------------
#
# ImportMerge
#
#------------------------------------------------------------------------
class ImportMerge(tool.Tool, ManagedWindow):
    """
    Create the ImportMerge Gui.
    """
    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate
        self._user = user

        tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, uistate, [], self.__class__)
        self.db = dbstate.db
        self.uistate = uistate
        # menu = options.menu
        self.top = Glade(toplevel="filechooserdialog1",
                         also_load=["filefilter1"])
        window = self.top.toplevel
        self.set_window(window, None, TITLE)
        self.setup_configs('interface.importmergetoolfileopen', 750, 520)
        self.show()
        response = self.window.run()
        if response == Gtk.ResponseType.CANCEL:
            return
        self.filename = self.window.get_filename()
        window.destroy()
        #self.filename = r"d:\users\prc\documents\Gramps\data\tests\imp_sample.gramps"
        self.top = Glade(toplevel="main",
                         also_load=["res_treeview", "res_liststore",
                                    "diffs_liststore"])
        window = self.top.toplevel
        self.set_window(window, None, TITLE)
        self.setup_configs('interface.importmergetool', 760, 560)
        self.top.connect_signals({
            "on_merge_l_clicked"    : self.on_merge_l,
            "on_edit_clicked"       : self.on_edit,
            "on_merge_r_clicked"    : self.on_merge_r,
            "on_ignore_clicked"     : self.on_ignore,
            "on_add_clicked"        : self.on_add,
            "on_replace_clicked"    : self.on_replace,
            "on_help_clicked"       : self.on_help_clicked,
            "on_tag_clicked"        : self.on_tag,
            "on_delete_event"       : self.close,
            "on_close"              : self.close})

        self.merge_l_btn = self.top.get_object("merge_l_btn")
        self.merge_r_btn = self.top.get_object("merge_r_btn")
        self.edit_btn = self.top.get_object("edit_btn")
        self.add_btn = self.top.get_object("add_btn")
        self.ignore_btn = self.top.get_object("ignore_btn")
        self.replace_btn = self.top.get_object("replace_btn")
        self.diff_list = self.top.get_object("diffs_liststore")
        self.res_list = self.top.get_object("res_liststore")
        self.res_view = self.top.get_object("res_treeview")
        self.diff_view = self.top.get_object("Diffs_treeview")
        self.diff_sel = self.diff_view.get_selection()
        self.diff_sel.connect('changed', self.on_diff_row_changed)
        self.db1_hndls = {}
        self.db2_hndls = {}
        self.res_mode = False
        self.classes = set()
        self.show()
        if not self.find_diffs():
            self.close()
            return

    def close(self, *args):
        print(self.classes)
        ManagedWindow.close(self, *args)

    def find_diffs(self):
        """ Load import file, and search for diffs. """
        self.db2 = import_as_dict(self.filename, self._user)
        if self.db2 is None:
            ErrorDialog(_("Import Failure"), parent=self.window)
            return False
        self.sa = [MySa(self.db), MySa(self.db2)]
        self.diffs, self.added, self.missing = diff_dbs(
            self.db, self.db2, self._user)
        last_object = None
        if self.diffs:
            status = S_DIFFERS
            # self._user.begin_progress(_('Family Tree Differences'),
            #                           _('Processing...'), len(self.diffs))
            for diff_i in range(len(self.diffs)):
                # self._user.step_progress()
                obj_type, item1, item2 = self.diffs[diff_i]
                gid, name = self.sa[0].describe(item1)
                diff_data = (status, obj_type, gid, name, diff_i, "tag", "")
                self.diff_list.append(row=diff_data)
        if self.missing:
            status = S_MISS
            for item_i in range(len(self.missing)):
                obj_type, item = self.missing[item_i]
                self.db1_hndls[item.handle] = (obj_type, item_i)
                gid, name = self.sa[0].describe(item)
                diff_data = (status, obj_type, gid, name, item_i, "tag", "")
                self.diff_list.append(row=diff_data)
        if self.added:
            status = S_ADD
            for item_i in range(len(self.added)):
                obj_type, item = self.added[item_i]
                self.db2_hndls[item.handle] = (obj_type, item_i)
                gid, name = self.sa[1].describe(item)
                diff_data = (status, obj_type, gid, name, item_i, "tag", "")
                self.diff_list.append(row=diff_data)
        if len(self.diff_list) != 0:
            spath = Gtk.TreePath.new_first()
            self.diff_sel.select_path(spath)
        # self._user.end_progress()
        return True

    def format_struct_path(self, path):
        retval = ""
        parts = path.split(".")
        for part in parts:
            if retval:
                retval += ", "
            if "[" in part and "]" in part:
                part, index = re.match(r"(.*)\[(\d*)\]", part).groups()
                retval += "%s #%s" % (part.replace("_", " "), int(index) + 1)
            else:
                retval += part
        return retval

    def report_details(self, path, diff1, diff2, diff3):
        if isinstance(diff1, bool):
            desc1 = repr(diff1)
        else:
            desc1 = str(diff1) if diff1 is not None else ""
        if isinstance(diff2, bool):
            desc2 = repr(diff2)
        else:
            desc2 = str(diff2) if diff2 is not None else ""
        if isinstance(diff3, bool):
            desc3 = repr(diff3)
        else:
            desc3 = str(diff3) if diff3 is not None else ""
        if path.endswith(_("Last changed")):
            diff1 = todate(diff1)
            diff2 = todate(diff2)
            diff3 = todate(diff3)
            desc1 = diff1
            desc2 = diff2
            desc3 = diff3
        if diff1 == diff2:
            return
        obj_type = self.item1_hndls.get(desc1)
        if obj_type:
            hndl_func = self.db.get_table_metadata(obj_type)["handle_func"]
            desc1 = obj_type + ": " + hndl_func(desc1).gramps_id
        obj_type = self.item2_hndls.get(desc2)
        if obj_type:
            if self.db2_hndls.get(desc2):
                text = _("imported ")
            else:
                text = _("your tree ")
            hndl_func = self.db2.get_table_metadata(obj_type)["handle_func"]
            desc2 = text + obj_type + ": " + hndl_func(desc2).gramps_id
        obj_type = self.item2_hndls.get(desc3)
        if obj_type:
            if self.db2_hndls.get(desc3):
                text = _("imported ")
            else:
                text = _("your tree ")
            hndl_func = self.db2.get_table_metadata(obj_type)["handle_func"]
            desc3 = text + obj_type + ": " + hndl_func(desc3).gramps_id
        path = self.format_struct_path(path)
        text = SPN_MONO + _("Current") + "  >> " + SPN_ + desc1 + "\n"
        text += SPN_MONO + _("Imported") + " >> " + SPN_ + desc2
        if self.res_mode:
            text += "\n" + SPN_MONO + _("Result") + "   >> " + SPN_ + desc3
        self.res_list.append((path, text))

    def report_diff(self, path, item1, item2, item3=None):
        """
        Compare two struct objects and report differences.
        """
        #if to_struct(item1) == to_struct(item2):
            #return   # _eq_ doesn't work on Gramps objects for this purpose
        if item1 is None and item2 is None:
            return
        elif (isinstance(item1, (list, tuple)) or
              isinstance(item2, (list, tuple))):
            #assert not (isinstance(item1, tuple) or
            if (isinstance(item1, tuple) or
                        isinstance(item2, tuple)):
                pass  # yes there are tuples
            len1 = len(item1) if isinstance(item1, (list, tuple)) else 0
            len2 = len(item2) if isinstance(item2, (list, tuple)) else 0
            len3 = 0
            if item3 and isinstance(item3, (list, tuple)):
                len3 = len(item3)
            for pos in range(max(len1, len2, len3)):
                val1 = item1[pos] if pos < len1 else None
                val2 = item2[pos] if pos < len2 else None
                val3 = item3[pos] if pos < len3 else None
                self.report_diff(path + ("[%d]" % pos), val1, val2, val3)
        elif hasattr(item1, '__dict__') or hasattr(item2, '__dict__'):
            # dealing with Gramps object.  Note: we assume that Gramps class
            # objects attached to an another object are always the same type
            # test if we have added/deleted and only list the class info
            val1 = val2 = val3 = None
            if item1 is None:
                class_name = item2.__class__.__name__
                schema = item2.get_schema()
                val2 = schema.get('title', class_name)
            else:
                class_name = item1.__class__.__name__
                schema = item1.get_schema()
            self.classes.add(class_name)
            if item2 is None:
                val1 = schema.get('title', class_name)
            if item1 is None or item2 is None:
                val3 = schema.get('title', class_name) \
                    if item3 is not None else None
                self.report_details(path, val1, val2, val3)
                return
            assert item1.__class__.__name__ == item2.__class__.__name__
            item = item1 if item2 is None else item2
            keys = list(item.__dict__.keys())
            for key in keys:
                val1 = item1.__dict__[key] if item1 is not None else None
                val2 = item2.__dict__[key] if item2 is not None else None
                val3 = item3.__dict__[key] if item3 is not None else None
                if key == "dict":  # a raw dict, not a struct
                    self.report_details(path, val1, val2, val3)
                elif not key.startswith('_'):
                    key_ = key.replace('_' + class_name + '__', '')
                    if schema['properties'].get(key_) is None:
                        print("**** obj: ", path, key)
                        continue
                    key_ = schema['properties'][key_].get('title', key_)
                    self.report_diff(path + "." + key_, val1, val2, val3)
            for key, value in item.__class__.__dict__.items():
                if not (isinstance(value, property) and key != 'year'):
                    continue
                val1 = getattr(item1, key) if item1 is not None else None
                val2 = getattr(item2, key) if item2 is not None else None
                val3 = getattr(item3, key) if item3 is not None else None
                if key == "dict":  # a raw dict, not a struct
                    self.report_details(path, val1, val2, val3)
                elif not key.startswith('_'):
                    key_ = key.replace('_' + class_name + '__', '')
                    if schema['properties'].get(key_) is None:
                        print("**** classprop: ", path, key)
                        continue
                    key_ = schema['properties'][key_].get('title', key_)
                    self.report_diff(path + "." + key_, val1, val2, val3)
        else:
            self.report_details(path, item1, item2, item3)

    def on_diff_row_changed(self, *obj):
        """ Signal: update lower panes when the diff pane row changes """
        if not obj:
            return
        self.diff_iter = obj[0].get_selected()[1]
        if not self.diff_iter:
            return
        status = self.diff_list[self.diff_iter][STATUS]
        self.fix_btns(status)
        self.show_results()

    def fix_btns(self, status):
        if status == S_DIFFERS:
            self.add_btn.set_sensitive(False)
            self.edit_btn.set_sensitive(True)
            self.merge_l_btn.set_sensitive(True)
            self.merge_r_btn.set_sensitive(True)
            self.replace_btn.set_sensitive(True)
        elif status == S_ADD:
            self.add_btn.set_label(_("Add"))
            self.add_btn.set_sensitive(True)
            self.edit_btn.set_sensitive(True)
            self.merge_l_btn.set_sensitive(False)
            self.merge_r_btn.set_sensitive(False)
            self.replace_btn.set_sensitive(False)
        else:
            self.add_btn.set_label(_("Delete"))
            self.add_btn.set_sensitive(True)
            self.edit_btn.set_sensitive(False)
            self.merge_l_btn.set_sensitive(False)
            self.merge_r_btn.set_sensitive(False)
            self.replace_btn.set_sensitive(False)

    def show_results(self):
        status = self.diff_list[self.diff_iter][STATUS]
        action = self.diff_list[self.diff_iter][ACTION]
        diff_i = self.diff_list[self.diff_iter][DIFF_I]
        self.res_mode = action != ""
        self.res_list.clear()
        if status == S_DIFFERS:
            obj_type, item1, item2 = self.diffs[diff_i]
            item3 = None
            self.item1_hndls = {i[1]: i[0] for i in
                                item1.get_referenced_handles_recursively()}
            self.item2_hndls = {i[1]: i[0] for i in
                                item2.get_referenced_handles_recursively()}
            if action == A_REPLACE:
                item3 = item2
            elif action == A_IGNORE:
                item3 = item1
            elif action == A_MERGE_L:
                item3 = deepcopy(item1)
                item_m = deepcopy(item2)
                item_m.gramps_id = None
                item3.merge(item_m)
            elif action == A_MERGE_R:
                item3 = deepcopy(item2)
                item_m = deepcopy(item1)
                item_m.gramps_id = None
                item3.merge(item_m)
            self.report_diff(obj_type, item1, item2, item3)
        elif status == S_ADD:
            obj_type, item = self.added[diff_i]
            desc1 = ""
            desc2 = '[%s] %s' % self.sa[1].describe(item)
            if action == A_ADD:
                desc3 = desc2
            else:  # action == A_IGNORE:
                desc3 = desc1
            text = SPN_MONO + _("Current") + "  >> " + SPN_ + desc1 + "\n"
            text += SPN_MONO + _("Imported") + " >> " + SPN_ + desc2
            if self.res_mode:
                text += "\n" + SPN_MONO + _("Result") + "   >> " + SPN_ + desc3
            self.res_list.append((_(obj_type), text))
        else:  # status == S_MISS:
            obj_type, item = self.missing[diff_i]
            desc1 = '[%s] %s' % self.sa[0].describe(item)
            desc2 = ""
            if action == A_IGNORE:
                desc3 = desc1
            else:  # action == A_DEL
                desc3 = "<s>" + desc1 + "</s>"
            text = SPN_MONO + _("Current") + "  >> " + SPN_ + desc1 + "\n"
            text += SPN_MONO + _("Imported") + " >> " + SPN_ + desc2
            if self.res_mode:
                text += "\n" + SPN_MONO + _("Result") + "   >> " + SPN_ + desc3
            self.res_list.append((_(obj_type), text))

    def on_merge_l(self, dummy):
        self.on_btn(A_MERGE_L)

    def on_merge_r(self, dummy):
        self.on_btn(A_MERGE_R)

    def on_edit(self, dummy):
        pass

    def on_add(self, dummy):
        self.on_btn(A_ADD)

    def on_ignore(self, dummy):
        self.on_btn(A_IGNORE)

    def on_replace(self, dummy):
        self.on_btn(A_REPLACE)

    def on_btn(self, action):
        if not self.diff_iter:
            return
        self.diff_list.set_value(self.diff_iter, ACTION, action)
        self.show_results()

    def on_tag(self, dummy):
        pass

    def on_help_clicked(self, dummy):
        """ Button: Display the relevant portion of GRAMPS manual"""
        display_url(WIKI_PAGE)

    def build_menu_names(self, obj):
        return (TITLE, TITLE)


#------------------------------------------------------------------------
#
# MySa extended SimpleAccess for more info
#
#------------------------------------------------------------------------
class MySa(SimpleAccess):
    """ Extended SimpleAccess """

    def __init__(self, dbase):
        SimpleAccess.__init__(self, dbase)

    def describe(self, obj, prop=None, value=None):
        """
        Given a object, return a string describing the object.
        """
        if prop and value:
            if self.dbase.get_table_metadata(obj):
                obj = self.dbase.get_table_metadata(obj)[prop + "_func"](value)
        if isinstance(obj, Person):
            return (self.gid(obj), self.name(obj))
        elif isinstance(obj, Event):
            return (self.gid(obj), "%s %s" % (
                self.event_type(obj),
                get_participant_from_event(self.dbase, obj.handle)))
        elif isinstance(obj, Family):
            return (self.gid(obj), "%s/%s" % (self.name(self.mother(obj)),
                                              self.name(self.father(obj))))
        elif isinstance(obj, Media):
            return (self.gid(obj), obj.desc)
        elif isinstance(obj, Source):
            return (self.gid(obj), self.title(obj))
        elif isinstance(obj, Citation):
            return (self.gid(obj), obj.page)
        elif isinstance(obj, Place):
            place_title = place_displayer.display(self.dbase, obj)
            return (self.gid(obj), place_title)
        elif isinstance(obj, Repository):
            return (self.gid(obj), "%s %s" % (obj.type, obj.name))
        elif isinstance(obj, Note):
            return (self.gid(obj), "%s %s" % (obj.type, obj.get()))
        elif isinstance(obj, Tag):
            return ("", obj.name)
        else:
            return ("", "Error: incorrect object class in describe: '%s'"
                    % type(obj))
#------------------------------------------------------------------------
#
# ImportMergeOptions
#
#------------------------------------------------------------------------
class ImportMergeOptions(tool.ToolOptions):
    """ Options for the ImportMerge """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        # Options specific for this report
        self.options_dict = {}
        self.options_help = {}
