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
import copy
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
from gramps.gui.plug import tool
from gramps.gui.display import display_url
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.dialog import ErrorDialog
from gramps.gen.db.utils import import_as_dict
from gramps.gen.simple import SimpleAccess
from gramps.gui.glade import Glade

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
                         also_load=["import_textbuffer", "tree_textbuffer",
                                    "diffs_liststore"])
        window = self.top.toplevel
        self.set_window(window, None, TITLE)
        self.setup_configs('interface.importmergetool', 750, 520)
        self.top.connect_signals({
            "on_close"              : self.close,
            "on_help_clicked"       : self.on_help_clicked,
            "on_delete_event"       : self.close,
            "on_merge_clicked"     : self.on_merge,
            "on_add_clicked"       : self.on_add,
            "on_ignore_clicked" : self.on_ignore,
            "on_tag_clicked"     : self.on_tag})

        self.diff_list = self.top.get_object("diffs_liststore")
        self.imp_textbuf = self.top.get_object("import_textbuffer")
        self.tree_textbuf = self.top.get_object("tree_textbuffer")
        self.diff_view = self.top.get_object("Diffs_treeview")
        self.diff_sel = self.diff_view.get_selection()
        self.diff_sel.connect('changed', self.on_diff_row_changed)
        self.db1_hndls = {}
        self.db2_hndls = {}

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
        self.sa = [SimpleAccess(self.db), SimpleAccess(self.db2)]
        self.diffs, self.added, self.missing = diff_dbs(
            self.db, self.db2, self._user)
        last_object = None
        if self.diffs:
            status = "Different"
            # self._user.begin_progress(_('Family Tree Differences'),
            #                           _('Processing...'), len(self.diffs))
            for diff_i in range(len(self.diffs)):
                # self._user.step_progress()
                obj_type, item1, item2 = self.diffs[diff_i]
                name = self.sa[0].describe(item1)
                diff_data = (status, obj_type, name, diff_i, "tag", "")
                self.diff_list.append(row=diff_data)
        if self.missing:
            status = "Missing"
            for item_i in range(len(self.missing)):
                obj_type, item = self.missing[item_i]
                self.db1_hndls[item.handle] = (obj_type, item_i)
                name = self.sa[0].describe(item)
                diff_data = (status, obj_type, name, item_i, "tag", "")
                self.diff_list.append(row=diff_data)
        if self.added:
            status = "Added"
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
                part, index = re.match("(.*)\[(\d*)\]", part).groups()
                retval += "%s #%s" % (part.replace("_", " "), int(index) + 1)
            else:
                retval += part
        return retval

    def report_details(self, path, diff1, diff2):
        if isinstance(diff1, bool):
            desc1 = repr(diff1)
        else:
            desc1 = str(diff1) if diff1 else ""
        if isinstance(diff2, bool):
            desc2 = repr(diff2)
        else:
            desc2 = str(diff2) if diff2 else ""
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
        if status == "Different":
            diff = self.diffs[self.diff_list[self.diff_iter][DIFF_I]]
            obj_type, item1, item2 = diff
            self.item1_hndls = {i[1]: i[0] for i in
                                item1.get_referenced_handles_recursively()}
            self.item2_hndls = {i[1]: i[0] for i in
                                item2.get_referenced_handles_recursively()}
            self.text1 = self.text2 = ""
            self.report_diff(obj_type, to_struct(item1), to_struct(item2))
            self.tree_textbuf.set_text(*str_byte(self.text1))
            self.imp_textbuf.set_text(*str_byte(self.text2))
        elif status == "Added":
            diff = self.added[self.diff_list[self.diff_iter][DIFF_I]]
            obj_type, item = diff
            name = self.sa[1].describe(item)
            self.imp_textbuf.set_text(*str_byte(obj_type + ": " + name))
            self.tree_textbuf.set_text(*str_byte(""))
        else:  # status == "Missing":
            diff = self.missing[self.diff_list[self.diff_iter][DIFF_I]]
            obj_type, item = diff
            name = self.sa[0].describe(item)
            self.tree_textbuf.set_text(*str_byte(obj_type + ": " + name))
            self.imp_textbuf.set_text(*str_byte(""))

    def on_merge(self, dummy):
        pass

    def on_add(self, dummy):
        pass

    def on_ignore(self, dummy):
        pass

    def on_tag(self, dummy):
        pass

    def on_help_clicked(self, dummy):
        """ Button: Display the relevant portion of GRAMPS manual"""
        display_url(WIKI_PAGE)

    def build_menu_names(self, obj):
        return (TITLE, TITLE)


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
