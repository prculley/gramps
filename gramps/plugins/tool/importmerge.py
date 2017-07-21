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
from gramps.gen.merge.diff import diff_items, to_struct
from gramps.gen.dbstate import DbState
from gramps.gen.utils.db import get_participant_from_event
from gramps.gen.db import CLASS_TO_KEY_MAP
from gramps.gui.plug import tool
from gramps.gui.display import display_url
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.dialog import ErrorDialog
from gramps.gui.utils import ProgressMeter
from gramps.gui.editors import EditObject
from gramps.gen.db.utils import import_as_dict
from gramps.gen.simple import SimpleAccess
from gramps.gui.glade import Glade
from gramps.gen.lib import (Person, Family, Event, Source, Place, Citation,
                            Media, Repository, Note, Tag)
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
A_NONE = 0
A_DEL = 1      # _("Delete original")
A_IGNORE = 2   # _("Ignore")
A_KEEP = 3     # _("Keep original")
A_ADD = 4      # _("Add Import")
A_MERGE_L = 5  # _("Merge into original")
A_MERGE_R = 6  # _("Merge into import")
A_REPLACE = 7  # _("Replace with import")
A_LST = ['',
         _("Delete original"),
         _("Ignore"),
         _("Keep original"),
         _("Add Import"),
         _("Merge into original"),
         _("Merge into import"),
         _("Replace with import")]
SPN_MONO = "<span font_family='monospace'>"
SPN_ = "</span>"


#------------------------------------------------------------------------
#
# Local Functions
#
#------------------------------------------------------------------------
def todate(tim):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tim))


#------------------------------------------------------------------------
#
# ImportMerge
#
#------------------------------------------------------------------------
class ImportMerge(tool.Tool, ManagedWindow):
    '''
    Create the ImportMerge Gui and run it.
    '''
    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate
        self._user = user

        tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, uistate, [], self.__class__)
        self.db1 = dbstate.db
        self.uistate = uistate
        # some diagnostic data saved to print at end
        self.classes = set()  # set of classes encountered
        self.nokey = set()  # list of missing keys
        self.notitle = set()  # list of objects/keys with no title
        self.item1_hndls = {}  # handles found in current difference of db
        self.item2_hndls = {}  # handles found in current difference of import

#         # start with a file name dialog
#         self.top = Glade(toplevel="filechooserdialog1",
#                          also_load=["filefilter1"])
#         window = self.top.toplevel
#         self.set_window(window, None, TITLE)
#         self.setup_configs('interface.importmergetoolfileopen', 750, 520)
#         self.show()
#         response = self.window.run()
#         self.filename = self.window.get_filename()
#         window.destroy()
#         if response == Gtk.ResponseType.CANCEL:
#             self.close()
#             return
        self.filename = r"d:\users\prc\documents\Gramps\data\tests\imp_sample.gramps"

        # bring up the main screen and fill it
        self.top = Glade(toplevel="main",
                         also_load=["res_treeview", "res_liststore",
                                    "diffs_liststore"])
        window = self.top.toplevel
        self.set_window(window, None, TITLE)
        self.setup_configs('interface.importmergetool', 760, 560)
        self.top.connect_signals({
            "on_merge_l_clicked"    : (self.on_btn, A_MERGE_L),
            "on_merge_r_clicked"    : (self.on_btn, A_MERGE_R),
            "on_ignore_clicked"     : (self.on_btn, A_IGNORE),
            "on_add_clicked"        : (self.on_btn, A_ADD),
            "on_replace_clicked"    : (self.on_btn, A_REPLACE),
            "on_help_clicked"       : self.on_help_clicked,
            "on_edit_clicked"       : self.on_edit,
            "on_tag_clicked"        : self.on_tag,
            "on_delete_event"       : self.close,
            "on_close"              : self.close})

        self.merge_l_btn = self.top.get_object("merge_l_btn")
        self.merge_r_btn = self.top.get_object("merge_r_btn")
        self.edit_btn = self.top.get_object("edit_btn")
        self.add_btn = self.top.get_object("add_btn")
        self.ignore_btn = self.top.get_object("ignore_btn")
        self.replace_btn = self.top.get_object("replace_btn")
        self.parent_fam_btn = self.top.get_object("parent_fam_btn")
        self.fam_btn = self.top.get_object("fam_btn")
        self.diff_list = self.top.get_object("diffs_liststore")
        self.res_list = self.top.get_object("res_liststore")
        self.res_view = self.top.get_object("res_treeview")
        self.diff_view = self.top.get_object("Diffs_treeview")
        self.diff_sel = self.diff_view.get_selection()
        self.diff_iter = None
        self.diff_sel.connect('changed', self.on_diff_row_changed)
        self.db1_hndls = {}  # dict with (iter, diff_i) tuples, handle as key
        self.db2_hndls = {}  # dict with (iter, diff_i) tuples, handle as key
        self.my_families = True      # wether to automark my families
        self.parent_families = True  # wether to automark parent families
        self.res_mode = False
        self.show()
        if not self.find_diffs():
            self.close()
            return

    def close(self, *args):
        print(self.classes, '\n', self.notitle, '\n', self.nokey, '\n')
        ManagedWindow.close(self, *args)

    def progress_step(self, percent):
        ''' a hack to allow import XML callback progress to work '''
        self._progress._ProgressMeter__pbar_index = percent - 1.0
        self._progress.step()

    def find_diffs(self):
        ''' Load import file, and search for diffs. '''
        self._progress = ProgressMeter(_('Import and Merge tool'),
                                       _('Importing data...'),
                                       parent=self.window)
        # importxml uses the user.callback(percentage) for progress
        # not compatible with usual user progress. So bypass step()
        self._user.callback_function = \
            self.progress_step
        self.db2 = import_as_dict(self.filename, self._user)
        if self.db2 is None:
            self._progress.close()
            ErrorDialog(_("Import Failure"), parent=self.window)
            return False
        self.sa = [MySa(self.db1), MySa(self.db2)]
        self._user.parent = self.window  # so progress is right
        self.diffs, self.added, self.missing = diff_dbs(
            self.db1, self.db2, self._progress)
        self._progress.set_pass(_('Processing...'),
                                len(self.diffs) + len(self.added) +
                                len(self.missing))
        if self.diffs:
            status = S_DIFFERS
            for diff_i in range(len(self.diffs)):
                self._progress.step()
                obj_type, hndl1, dummy = self.diffs[diff_i]
                item1 = self.db1.get_from_name_and_handle(obj_type, hndl1)
                gid, name = self.sa[0].describe(item1)
                diff_data = (status, obj_type, gid, name, diff_i, "tag", "")
                self.diff_list.append(row=diff_data)
        if self.missing:
            status = S_MISS
            for item_i in range(len(self.missing)):
                self._progress.step()
                obj_type, hndl = self.missing[item_i]
                item = self.db1.get_from_name_and_handle(obj_type, hndl)
                gid, name = self.sa[0].describe(item)
                diff_data = (status, obj_type, gid, name, item_i, "tag", "")
                d_list_iter = self.diff_list.append(row=diff_data)
                self.db1_hndls[item.handle] = (d_list_iter, item_i)
        if self.added:
            status = S_ADD
            for item_i in range(len(self.added)):
                self._progress.step()
                obj_type, hndl = self.added[item_i]
                item = self.db2.get_from_name_and_handle(obj_type, hndl)
                gid, name = self.sa[1].describe(item)
                diff_data = (status, obj_type, gid, name, item_i, "tag", "")
                d_list_iter = self.diff_list.append(row=diff_data)
                self.db2_hndls[hndl] = (d_list_iter, item_i)
        if len(self.diff_list) != 0:
            spath = Gtk.TreePath.new_first()
            self.diff_sel.select_path(spath)
        self._progress.close()
        return True

    def format_struct_path(self, path):
        ''' clean up path text for better readability '''
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
        ''' report out the detailed difference for two items '''
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
            hndl_func = self.db1.get_table_metadata(obj_type)["handle_func"]
            text = _("your tree ")
            desc1 = text + obj_type + ": " + hndl_func(desc1).gramps_id
        else:
            obj_type = self.item2_hndls.get(desc2)

        if self.item2_hndls.get(desc2):
            if self.db2_hndls.get(desc2):
                text = _("imported ")
            else:
                text = _("your tree ")
            hndl_func = self.db2.get_table_metadata(obj_type)["handle_func"]
            desc2 = text + obj_type + ": " + hndl_func(desc2).gramps_id
        if self.item2_hndls.get(desc3):
            if self.db2_hndls.get(desc3):
                text = _("imported ")
            else:
                text = _("your tree ")
            hndl_func = self.db2.get_table_metadata(obj_type)["handle_func"]
            desc3 = text + obj_type + ": " + hndl_func(desc3).gramps_id
        elif self.item1_hndls.get(desc3):
            if self.db2_hndls.get(desc3):
                text = _("imported ")
            else:
                text = _("your tree ")
            hndl_func = self.db1.get_table_metadata(obj_type)["handle_func"]
            desc3 = text + obj_type + ": " + hndl_func(desc3).gramps_id
        path = self.format_struct_path(path)
        text = SPN_MONO + _("Current") + "  >> " + SPN_ + desc1 + "\n"
        text += SPN_MONO + _("Imported") + " >> " + SPN_ + desc2
        if self.res_mode:
            text += "\n" + SPN_MONO + _("Result") + "   >> " + SPN_ + desc3
        self.res_list.append((path, text))

    def report_diff(self, path, item1, item2, item3=None):
        '''
        Compare two struct objects and report differences.
        '''
        if to_struct(item1) == to_struct(item2):
            return   # _eq_ doesn't work on Gramps objects for this purpose
        if item1 is None and item2 is None:
            return
        elif (isinstance(item1, (list, tuple)) or
              isinstance(item2, (list, tuple))):
            #assert not (isinstance(item1, tuple) or
            # if (isinstance(item1, tuple) or isinstance(item2, tuple)):
            #     pass  # yes there are tuples
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
            if schema.get('title') is None:
                self.notitle.add(class_name)
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
                        self.nokey.add(class_name + ':' + key)
                        continue
                    if schema['properties'][key_].get('title') is None:
                        self.notitle.add(class_name + ':' + key_)
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
                        self.nokey.add(class_name + ' cl:' + key)
                        continue
                    if schema['properties'][key_].get('title') is None:
                        self.notitle.add(class_name + ' cl:' + key_)
                    key_ = schema['properties'][key_].get('title', key_)
                    self.report_diff(path + "." + key_, val1, val2, val3)
        else:
            self.report_details(path, item1, item2, item3)

    def mark_refs(self, obj, mark, status, old_mark):
        ''' Mark other additions (or missing) that are referenced by the
        current primary object.  This is a recursive operation, if a new
        object is found, we also mark it and go on down.  We avoid potental
        loops in the object references by not marking an object already marked.

        item: index into either the added or missing lists
        mark: index into A_LST action strings
        status: str used to figure out which list we are marking
        old_mark: Previous mark of main item, used to decide if we should
                override priority
        '''
        # don't automark families unless user wants.  So get family handles we
        # DON't want to automark
        not_list = []
        if obj.__class__.__name__ == 'Person':
            if not self.parent_families:
                not_list = obj.parent_family_list[:]
            if not self.my_families:
                not_list.extend(obj.family_list)

        for dummy, handle in obj.get_referenced_handles_recursively():
            # see if a member of the additions or missing group
            if status == S_ADD:
                d_list_iter, item_i = self.db2_hndls.get(handle, (None, None))
            else:
                d_list_iter, item_i = self.db1_hndls.get(handle, (None, None))
            if item_i is None:
                continue  # not in the list of differences
            if handle in not_list:
                continue  # family handle we don't want to mark.
            c_mark = self.diff_list[d_list_iter][ACTION]
            if c_mark.startswith('*'):  # automarked entries get lower priority
                cur_mark = A_LST.index(c_mark.replace('*', '')) - 10
            else:
                cur_mark = A_LST.index(c_mark)
            if cur_mark == mark or cur_mark + 10 == mark:
                continue  # already marked (prevents infinite recursion)
            # if the previous mark is same as this, user changed mind, allow
            # if new mark is higher priority, allow.  if never marked, allow
            if cur_mark == old_mark - 10 or mark - 10 > cur_mark \
                    or cur_mark == 0:
                self.diff_list[d_list_iter][ACTION] = '*' + A_LST[mark]
                if status == S_ADD:
                    item = self.db2.get_from_name_and_handle(
                        *self.added[item_i])
                else:
                    item = self.db1.get_from_name_and_handle(
                        *self.missing[item_i])
                self.mark_refs(item, mark, status, old_mark)

    def do_commits(self):
        ''' need to make sure that we don't reuse GIDs on add/merge.  When
        deleting something from current db, make sure nothing else holds
        reference first.  Need to adds/dels first, and then check on merges
        that references still exist.
        '''
        pass

    def on_diff_row_changed(self, *obj):
        ''' Signal: update lower panes when the diff pane row changes '''
        if not obj:
            return
        self.diff_iter = obj[0].get_selected()[1]
        if not self.diff_iter:
            return
        status = self.diff_list[self.diff_iter][STATUS]
        self.fix_btns(status)
        self.show_results()

    def fix_btns(self, status):
        ''' Update the buttons '''
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
        ''' update the lower pane '''
        status = self.diff_list[self.diff_iter][STATUS]
        action = A_LST.index(self.diff_list[self.diff_iter][ACTION])
        diff_i = self.diff_list[self.diff_iter][DIFF_I]
        self.res_mode = action != 0
        self.res_list.clear()
        if status == S_DIFFERS:
            obj_type, hndl1, hndl2 = self.diffs[diff_i]
            item1 = self.db1.get_from_name_and_handle(obj_type, hndl1)
            item2 = self.db2.get_from_name_and_handle(obj_type, hndl2)
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
            obj_type, hndl = self.added[diff_i]
            item = self.db2.get_from_name_and_handle(obj_type, hndl)
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
            item = self.db1.get_from_name_and_handle(obj_type, hndl)
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

    def on_edit(self, dummy):
        ''' deal with button press '''
        if not self.diff_iter:
            return
        item_i = self.diff_list[self.diff_iter][DIFF_I]
        status = self.diff_list[self.diff_iter][STATUS]
        if status == S_ADD:
            obj_type, hndl = self.added[item_i]
        else:  # mis be different list
            obj_type, dummy, hndl = self.diffs[item_i]
        dbstate = DbState()
        dbstate.db = self.db2
        self.connect_everything()
        EditObject(dbstate, self.uistate, self.track, obj_type, prop='handle',
                   value=hndl)

    def edit_callback(self, *args):
        ''' This gets called by db signals during the edit operation
        args = (obj_type, operation, list_of_handles)
        if handle is in self.added group, or self.differs group, and operation
        is an update, just refresh lower pane
        if operation is add, handle is not, then we need to add it added;
        means user added something new. So should redo auto mark
        Should never get a delete operation'''
        pass
        # self.db2.disconnect_all()

    def on_btn(self, dummy, action):
        ''' deal with general action button press '''
        self.parent_families = self.parent_fam_btn.get_active()
        self.my_families = self.fam_btn.get_active()
        if not self.diff_iter:
            return
        old_act = A_LST.index(self.diff_list[self.diff_iter][ACTION])
        self.diff_list.set_value(self.diff_iter, ACTION, A_LST[action])
        diff_i = self.diff_list[self.diff_iter][DIFF_I]
        status = self.diff_list[self.diff_iter][STATUS]
        # do markup of referenced items
        if status == S_DIFFERS:
            obj_type, hndl1, hndl2 = self.diffs[diff_i]
            item1 = self.db1.get_from_name_and_handle(obj_type, hndl1)
            item2 = self.db2.get_from_name_and_handle(obj_type, hndl2)
            self.mark_refs(item2, x_act(action)[0], S_ADD, x_act(old_act)[0])
            self.mark_refs(item1, x_act(action)[1], S_MISS, x_act(old_act)[1])
        elif status == S_MISS:
            item = self.db1.get_from_name_and_handle(*self.missing[diff_i])
            if action == A_ADD:  # really A_DEL dual mode button.
                self.mark_refs(item, A_DEL, S_MISS, old_act)
            else:  # action == A_IGNORE:
                self.mark_refs(item, A_IGNORE, S_MISS, old_act)
        else:  # status == S_ADD
            item = self.db2.get_from_name_and_handle(*self.added[diff_i])
            if action == A_ADD:
                self.mark_refs(item, A_ADD, status, old_act)
            else:  # A_IGNORE
                self.mark_refs(item, A_IGNORE, status, old_act)
        self.show_results()

    def on_tag(self, dummy):
        ''' deal with button press '''
        pass

    def on_help_clicked(self, dummy):
        ''' Button: Display the relevant portion of GRAMPS manual'''
        display_url(WIKI_PAGE)

    def build_menu_names(self, obj):
        ''' So ManagedWindow is happy '''
        return (TITLE, TITLE)


    def connect_everything(self):
        ''' Make connections to all db signals of import db '''
        for sname in CLASS_TO_KEY_MAP.keys():
            for etype in ['add', 'delete', 'update']:
                sig_name = sname.lower() + '-' + etype
                sig_func = sname.lower() + '_' + etype
                my_func = make_function(sig_name)
                my_func.__name__ = sig_func
                my_func.__doc__ = sig_func
                setattr(ImportMerge, sig_func, my_func)
                self.db2.connect(sig_name, getattr(self, sig_func))


def make_function(sig_name):
    """ This is here to support the dynamic function creation.  This creates
    the signal function (a method, to be precise).
    """
    def myfunc(self, *args):
        obj_type, action = sig_name.split('-')
        self.edit_callback(obj_type, action, args)

    return myfunc


def x_act(action):
    if action == A_NONE:
        return (A_NONE, A_NONE)
    elif action == A_REPLACE:
        return (A_ADD, A_DEL)
    elif action == A_IGNORE:
        return (A_IGNORE, A_IGNORE)
    else:  # merge
        return (A_ADD, A_KEEP)


def diff_dbs(db1, db2, progress):
    """
    1. new objects => mark for insert
    2. deleted objects, no change locally after delete date => mark
       for deletion
    3. deleted objects, change locally => mark for user confirm for
       deletion
    4. updated objects => do a diff on differences, mark origin
       values as new data
    """
    missing_from_old = []
    missing_from_new = []
    diffs = []
    progress.set_pass(_('Searching...'), db1.get_total() + db2.get_total())
    for item in ['Person', 'Family', 'Source', 'Citation', 'Event', 'Media',
                 'Place', 'Repository', 'Note', 'Tag']:

        handles_func1 = db1.get_table_metadata(item)["handles_func"]
        handles_func2 = db2.get_table_metadata(item)["handles_func"]
        handle_func1 = db1.get_table_metadata(item)["handle_func"]
        handle_func2 = db2.get_table_metadata(item)["handle_func"]

        handles1 = sorted([handle for handle in handles_func1()])
        handles2 = sorted([handle for handle in handles_func2()])
        p1 = 0
        p2 = 0
        while p1 < len(handles1) and p2 < len(handles2):
            if handles1[p1] == handles2[p2]:  # in both
                item1 = handle_func1(handles1[p1])
                item2 = handle_func2(handles2[p2])
                diff = diff_items(item, to_struct(item1), to_struct(item2))
                if diff:
                    diffs += [(item, handles1[p1], handles2[p2])]
                # else same!
                progress.step()
                progress.step()
                p1 += 1
                p2 += 1
            elif handles1[p1] < handles2[p2]:  # p1 is mssing in p2
                missing_from_new += [(item, handles1[p1])]
                progress.step()
                p1 += 1
            elif handles1[p1] > handles2[p2]:  # p2 is mssing in p1
                missing_from_old += [(item, handles2[p2])]
                progress.step()
                p2 += 1
        while p1 < len(handles1):
            missing_from_new += [(item, handles1[p1])]
            progress.step()
            p1 += 1
        while p2 < len(handles2):
            missing_from_old += [(item, handles2[p2])]
            progress.step()
            p2 += 1
    return diffs, missing_from_old, missing_from_new


#------------------------------------------------------------------------
#
# MySa extended SimpleAccess for more info
#
#------------------------------------------------------------------------
class MySa(SimpleAccess):
    ''' Extended SimpleAccess '''

    def __init__(self, dbase):
        SimpleAccess.__init__(self, dbase)

    def describe(self, obj, prop=None, value=None):
        '''
        Given a object, return a string describing the object.
        '''
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
    ''' Options for the ImportMerge '''

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        # Options specific for this report
        self.options_dict = {}
        self.options_help = {}
