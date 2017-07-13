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
NAME = 2
DIFF_I = 3
TAG = 4
ACTION = 5
S_MISS = _("Missing")
S_ADD = _("Added")
S_DIFFERS = _("Different")
A_MERGE_L = _("Merge Left")
A_MERGE_R = _("Merge Right")
A_REPLACE = _("Replace")
A_IGNORE = _("Ignore")
A_ADD = _("Add")
A_DEL = _("Delete")

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
        self.top = Glade(toplevel="main",
                         also_load=["import_label", "tree_label",
                                    "result_label", "diffs_liststore"])
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
        self.imp_label = self.top.get_object("imp_label")
        self.tree_label = self.top.get_object("tree_label")
        self.res_label = self.top.get_object("res_label")
        self.diff_view = self.top.get_object("Diffs_treeview")
        self.diff_sel = self.diff_view.get_selection()
        self.diff_sel.connect('changed', self.on_diff_row_changed)
        self.db1_hndls = {}
        self.db2_hndls = {}
        self.res_mode = False
        self.show()
        if not self.find_diffs():
            self.close()
            return

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
                name = self.sa[0].describe(item1)
                diff_data = (status, obj_type, name, diff_i, "tag", "")
                self.diff_list.append(row=diff_data)
        if self.missing:
            status = S_MISS
            for item_i in range(len(self.missing)):
                obj_type, item = self.missing[item_i]
                self.db1_hndls[item.handle] = (obj_type, item_i)
                name = self.sa[0].describe(item)
                diff_data = (status, obj_type, name, item_i, "tag", "")
                self.diff_list.append(row=diff_data)
        if self.added:
            status = S_ADD
            for item_i in range(len(self.added)):
                obj_type, item = self.added[item_i]
                self.db2_hndls[item.handle] = (obj_type, item_i)
                name = self.sa[1].describe(item)
                diff_data = (status, obj_type, name, item_i, "tag", "")
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

    def report_details(self, path, diff1, diff2):
        if isinstance(diff1, bool):
            desc1 = repr(diff1)
        else:
            desc1 = str(diff1) if diff1 is not None else ""
        if isinstance(diff2, bool):
            desc2 = repr(diff2)
        else:
            desc2 = str(diff2) if diff2 is not None else ""
        if path.endswith(".change"):
            diff1 = todate(diff1)
            diff2 = todate(diff2)
            desc1 = diff1
            desc2 = diff2
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
        path = self.format_struct_path(path)
        if self.res_mode:
            if desc1 and not desc2:
                self.text2 += path + "<s>" + desc1 + "</s>\n"
            else:
                self.text2 += path + "<b>" + desc2 + "</b>\n"
        else:
            desc1 = path + "\n" + desc1 + "\n"
            desc2 = path + "\n" + desc2 + "\n"
            self.text1 += desc1
            self.text2 += desc2

    def report_diff(self, path, struct1, struct2):
        """
        Compare two struct objects and report differences.
        """
        if struct1 == struct2:
            return
        elif (isinstance(struct1, (list, tuple)) or
              isinstance(struct2, (list, tuple))):
            if (isinstance(struct1, tuple) or
                isinstance(struct2, tuple)):
                pass
            len1 = len(struct1) if isinstance(struct1, (list, tuple)) else 0
            len2 = len(struct2) if isinstance(struct2, (list, tuple)) else 0
            for pos in range(max(len1, len2)):
                value1 = struct1[pos] if pos < len1 else None
                value2 = struct2[pos] if pos < len2 else None
                self.report_diff(path + ("[%d]" % pos), value1, value2)
        elif isinstance(struct1, dict) or isinstance(struct2, dict):
            keys = struct1.keys() if isinstance(struct1, dict) else struct2.keys()
            for key in keys:
                value1 = struct1[key] if struct1 is not None else None
                value2 = struct2[key] if struct2 is not None else None
                if key == "dict":  # a raw dict, not a struct
                    self.report_details(path, value1, value2)
                else:
                    self.report_diff(path + "." + key, value1, value2)
        else:
            self.report_details(path, struct1, struct2)

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
        self.res_mode = False
        if status == S_DIFFERS:
            diff = self.diffs[self.diff_list[self.diff_iter][DIFF_I]]
            obj_type, item1, item2 = diff
            self.item1_hndls = {i[1]: i[0] for i in
                                item1.get_referenced_handles_recursively()}
            self.item2_hndls = {i[1]: i[0] for i in
                                item2.get_referenced_handles_recursively()}
            self.text1 = self.text2 = ""
            self.report_diff(obj_type, to_struct(item1), to_struct(item2))
            self.tree_label.set_markup(self.text1)
            self.imp_label.set_markup(self.text2)
        elif status == S_ADD:
            diff = self.added[self.diff_list[self.diff_iter][DIFF_I]]
            obj_type, item = diff
            name = self.sa[1].describe(item)
            self.imp_label.set_markup(obj_type + ": " + name)
            self.tree_label.set_markup("")
        else:  # status == S_MISS:
            diff = self.missing[self.diff_list[self.diff_iter][DIFF_I]]
            obj_type, item = diff
            name = self.sa[0].describe(item)
            self.tree_label.set_markup(obj_type + ": " + name)
            self.imp_label.set_markup("")

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
        action = self.diff_list.get_value(self.diff_iter, ACTION)
        diff_i = self.diff_list.get_value(self.diff_iter, DIFF_I)
        status = self.diff_list.get_value(self.diff_iter, STATUS)
        res = ""
        if action == A_ADD or action == A_REPLACE:
            if status == S_DIFFERS:
                obj_type, dummy, item = self.diffs[diff_i]
            else:
                obj_type, item = self.added[diff_i]
            res = obj_type + ": " + self.sa[1].describe(item)
        elif action == A_IGNORE:
            if status == S_DIFFERS:
                obj_type, item, dummy = self.diffs[diff_i]
            elif status == S_ADD:
                obj_type, item = self.added[diff_i]
            else:
                obj_type, item = self.missing[diff_i]
            res = obj_type + ": " + self.sa[0].describe(item)
        elif action == A_DEL:
            obj_type, item = self.missing[diff_i]
            res = "<s>" + obj_type + ": " + self.sa[0].describe(item) + "</s>"
        elif action == A_MERGE_L:
            obj_type, item1, item2 = self.diffs[diff_i]
            self.text1 = self.text2 = ""
            item_r = deepcopy(item1)
            item_m = deepcopy(item2)
            item_m.gramps_id = None
            item_r.merge(item_m)
            self.report_diff(obj_type, to_struct(item1), to_struct(item_r))
            res = self.text2
        elif action == A_MERGE_R:
            obj_type, item1, item2 = self.diffs[diff_i]
            self.text1 = self.text2 = ""
            item_r = deepcopy(item2)
            item_m = deepcopy(item1)
            item_m.gramps_id = None
            item_r.merge(item_m)
            self.report_diff(obj_type, to_struct(item1), to_struct(item_r))
            res = self.text2

        self.res_label.set_markup(res)

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
            return "%s [%s]" % (self.name(obj), self.gid(obj))
        elif isinstance(obj, Event):
            return "%s [%s] %s" % (
                self.event_type(obj), self.gid(obj),
                get_participant_from_event(self.dbase, obj.handle))
        elif isinstance(obj, Family):
            return "%s/%s [%s]" % (self.name(self.mother(obj)),
                                   self.name(self.father(obj)),
                                   self.gid(obj))
        elif isinstance(obj, Media):
            return "%s [%s]" % (obj.desc, self.gid(obj))
        elif isinstance(obj, Source):
            return "%s [%s]" % (self.title(obj), self.gid(obj))
        elif isinstance(obj, Citation):
            return "[%s] %s" % (self.gid(obj), obj.page)
        elif isinstance(obj, Place):
            place_title = place_displayer.display(self.dbase, obj)
            return "%s [%s]" % (place_title, self.gid(obj))
        elif isinstance(obj, Repository):
            return "%s [%s] %s" % (obj.type, self.gid(obj), obj.name)
        elif isinstance(obj, Note):
            return "%s [%s] %s" % (obj.type, self.gid(obj), obj.get())
        elif isinstance(obj, Tag):
            return "[%s]" % (obj.name)
        else:
            return "Error: incorrect object class in describe: '%s'" % type(obj)
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
