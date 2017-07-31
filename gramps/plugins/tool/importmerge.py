# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012       Doug Blank <doug.blank@gmail.com>
#               2017       Paul Culley <paulr2787@gmail.com>
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

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
ngettext = glocale.translation.ngettext
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.plug.docgen import (FontStyle, ParagraphStyle, GraphicsStyle,
                             FONT_SERIF, PARA_ALIGN_RIGHT,
                             PARA_ALIGN_LEFT, PARA_ALIGN_CENTER,
                             TableStyle, TableCellStyle, FONT_SANS_SERIF)
from gramps.gen.plug.menu import (BooleanOption, DestinationOption, StringOption)
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.merge.diff import diff_dbs, to_struct
from gramps.gen.db.utils import import_as_dict
from gramps.gen.simple import SimpleAccess

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------

WIKI_PAGE = 'https://gramps-project.org/wiki/index.php?title=Import_Merge_Tool'
TITLE = _("Import and merge a Gramps XML")
#------------------------------------------------------------------------
#
# Local Functions
#
#------------------------------------------------------------------------
def todate(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

#------------------------------------------------------------------------
#
# ImportMerge
#
#------------------------------------------------------------------------
class ImportMerge(Tool, ManagedWindow):
    """
    Create the ImportMerge Gui.
    """
    def __init__(self, dbstate, user, options, name, callback=None):
        uistate = user.uistate
        self._user = user

        tool.Tool.__init__(self, dbstate, options, name)
        ManagedWindow.__init__(self, uistate, [], self.__class__)
        self.db = dbstate.db
        self.uistate = uistate
        menu = options.menu
        self.top = Glade(toplevel="filechooserdialog1",
                         also_load=["filefilter1"])
        window = self.top.toplevel
        self.set_window(window, None, TITLE)
        self.show()
        response = self.window.run()
        if respone == Gtk.RESPONSE_CANCEL:
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

        self.diff_liststore = self.top.get_object("diffs_liststore")
        self.imp_textbuf = self.top.get_object("import_textbuffer")
        self.tree_textbuf = self.top.get_object("tree_textbuffer")
        self.diff_view = self.top.get_object("Diffs_treeview")
        self.diff_sel = self.diff_view.get_selection()
        self.fam_sel.connect('changed', self.on_fam_row_changed)

        self.diffs_liststore = self.top.get_object("diffs_liststore")
        self.show()
        if not self.find_diffs():
            return
        


    def find_diffs(self):
        """ Load import file, and search for diffs. """
        self.database2 = import_as_dict(self.filename, self._user)
        if self.database2 is None:
            ErrorDialog(_("Import Failure"), parent=self.window)
            return False
        self.sa = [SimpleAccess(self.database), SimpleAccess(self.database2)]
        diffs, added, missing = diff_dbs(self.database, self.database2, self._user)
            last_object = None
            if diffs:
                self._user.begin_progress(_('Family Tree Differences'),
                                          _('Processing...'), len(diffs))
                for diff in diffs:
                    self._user.step_progress()
                    obj_type, item1, item2 = diff
                    if hasattr(item1, "gramps_id"):
                        self.start_list(self.doc, "%s: %s" % (obj_type, item1.gramps_id),
                                        "Database", "File")
                    else:
                        self.start_list(self.doc, "%s: %s" % (obj_type, item1.get_name()),
                                        "Database", "File")
                    self.report_diff(obj_type, to_struct(item1), to_struct(item2), self.doc)
            if missing:
                for pair in missing:
                    obj_type, item = pair
                    self.doc.write_text("Missing %s: %s" % (obj_type, self.sa[0].describe(item)))
            if added:
                for pair in added:
                    obj_type, item = pair
                    self.doc.write_text("Added %s: %s " % (obj_type, self.sa[1].describe(item)))
        self._user.end_progress()

    def start_list(self, doc, text, heading1, heading2):
        doc.start_row()
        doc.start_cell('DIFF-TableCell')
        doc.start_paragraph('DIFF-TableHeading')
        doc.write_text(text)
        doc.end_paragraph()
        doc.end_cell()
        if heading1:
            doc.start_cell('DIFF-TableCell')
            doc.start_paragraph('DIFF-TableHeading')
            doc.write_text(heading1)
            doc.end_paragraph()
            doc.end_cell()
        if heading2:
            doc.start_cell('DIFF-TableCell')
            doc.start_paragraph('DIFF-TableHeading')
            doc.write_text(heading2)
            doc.end_paragraph()
            doc.end_cell()
        doc.end_row()

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

    def report_details(self, doc, path, diff1, diff2):
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
        doc.start_row()
        doc.start_cell('DIFF-TableCell')
        doc.start_paragraph('DIFF-TableHeading')
        doc.write_text(self.format_struct_path(path))
        doc.end_paragraph()
        doc.end_cell()
        doc.start_cell('DIFF-TableCell')
        doc.start_paragraph('DIFF-Text')
        doc.write_text(desc1)
        doc.end_paragraph()
        doc.end_cell()
        doc.start_cell('DIFF-TableCell')
        doc.start_paragraph('DIFF-Text')
        doc.write_text(desc2)
        doc.end_paragraph()
        doc.end_cell()
        doc.end_row()

    def report_diff(self, path, struct1, struct2, doc):
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
                self.report_diff(path + ("[%d]" % pos), value1, value2, doc)
        elif isinstance(struct1, dict) or isinstance(struct2, dict):
            keys = struct1.keys() if isinstance(struct1, dict) else struct2.keys()
            for key in keys:
                value1 = struct1[key] if struct1 is not None else None
                value2 = struct2[key] if struct2 is not None else None
                if key == "dict": # a raw dict, not a struct
                    self.report_details(path, value1, value2, doc)
                else:
                    self.report_diff(path + "." + key, value1, value2, doc)
        else:
            self.report_details(doc, path, struct1, struct2)

#------------------------------------------------------------------------
#
# DifferencesOptions
#
#------------------------------------------------------------------------
class DifferencesOptions(MenuReportOptions):
    """ Options for the Differences Report """

    def add_menu_options(self, menu):
        """ Add the options for the text differences report """
        category_name = _("Report Options")
        filename = DestinationOption(_("Family Tree file"), "data.gramps")
        filename.set_help(_("Select a .gpkg or .gramps file"))
        menu.add_option(category_name, "filename", filename)

        show_diff = BooleanOption(_("Show items that are different"), True)
        show_diff.set_help(_("Include items that are different"))
        menu.add_option(category_name, "show_diff", show_diff)

        show_missing = BooleanOption(_("Show items missing from file"), True)
        show_missing.set_help(_("Include items not in file but in database"))
        menu.add_option(category_name, "show_missing", show_missing)

        show_added = BooleanOption(_("Show items added in file"), True)
        show_added.set_help(_("Include items in file but not in database"))
        menu.add_option(category_name, "show_added", show_added)

    def make_my_style(self, default_style, name, description,
                      size=9, font=FONT_SERIF, justified ="left",
                      color=None, align=PARA_ALIGN_CENTER,
                      shadow = None, italic=0, bold=0, borders=0, indent=None):
        """ Create paragraph and graphic styles of the same name """
        # Paragraph:
        f = FontStyle()
        f.set_size(size)
        f.set_type_face(font)
        f.set_italic(italic)
        f.set_bold(bold)
        p = ParagraphStyle()
        p.set_font(f)
        p.set_alignment(align)
        p.set_description(description)
        p.set_top_border(borders)
        p.set_left_border(borders)
        p.set_bottom_border(borders)
        p.set_right_border(borders)
        if indent:
            p.set(first_indent=indent)
        if justified == "left":
            p.set_alignment(PARA_ALIGN_LEFT)
        elif justified == "right":
            p.set_alignment(PARA_ALIGN_RIGHT)
        elif justified == "center":
            p.set_alignment(PARA_ALIGN_CENTER)
        default_style.add_paragraph_style(name, p)
        # Graphics:
        g = GraphicsStyle()
        g.set_paragraph_style(name)
        if shadow:
            g.set_shadow(*shadow)
        if color is not None:
            g.set_fill_color(color)
        if not borders:
            g.set_line_width(0)
        default_style.add_draw_style(name, g)

    def make_default_style(self, default_style):
        """ Add the styles used in this report """
        self.make_my_style(default_style, "DIFF-Text",
                           _('Text'), 12, justified="left")
        self.make_my_style(default_style, "DIFF-Title",
                           _('Text'), 16, justified="left",
                           bold=1)
        self.make_my_style(default_style, "DIFF-Heading",
                           _('Text'), 14, justified="left",
                           bold=1, italic=1)
        self.make_my_style(default_style, "DIFF-TableHeading",
                           _('Text'), 12, justified="left",
                           bold=1)

        #Table Styles
        cell = TableCellStyle()
        cell.set_borders(1)
        default_style.add_cell_style('DIFF-TableCell', cell)

        cell = TableCellStyle()
        default_style.add_cell_style('DIFF-TableCellNoBorder', cell)

        table = TableStyle()
        table.set_width(100)
        table.set_columns(3)
        table.set_column_width(0, 50)
        table.set_column_width(1, 25)
        table.set_column_width(2, 25)
        default_style.add_table_style('DIFF-Table3',table)

        table = TableStyle()
        table.set_width(100)
        table.set_columns(2)
        table.set_column_width(0, 15)
        table.set_column_width(1, 85)
        default_style.add_table_style('DIFF-Table2',table)

