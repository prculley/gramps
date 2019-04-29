#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017       Nick Hall
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

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from ..managedwindow import ManagedWindow
from ..glade import Glade
from ..listmodel import ListModel, NOSORT, INTEGER
from ..autocomp import StandardCustomSelector
from ..selectors.selectplace import SelectPlace
from gramps.gen.lib import PlaceType, PlaceHierType, PlaceAbbrevType
from gramps.gen.lib.placetype import DM_NAME
from gramps.gen.errors import HandleError
from gramps.gen.display.place import displayer as _pd
from gramps.gen.display.place import PlaceFormat, PlaceRule
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


#-------------------------------------------------------------------------
#
# EditPlaceFormat
#
#-------------------------------------------------------------------------
class EditPlaceFormat(ManagedWindow):
    def __init__(self, uistate, dbstate, track, callback):
        self.title = _('Place Format Editor')
        self.dbstate = dbstate
        if not dbstate.is_open():
            return
        ManagedWindow.__init__(self, uistate, track, EditPlaceFormat)
        self.callback = callback
        self.top = Glade()
        self.set_window(self.top.toplevel, None, self.title, None)
        self.setup_configs('interface.editplaceformat', 750, 400)
        self.top.get_object('add').connect('clicked', self.__add)
        self.top.get_object('remove').connect('clicked', self.__remove)
        self.top.get_object('name').connect('changed', self.__name_changed)
        self.top.get_object('add_btn').connect('clicked', self.__add_rule)
        self.top.get_object('rem_btn').connect('clicked', self.__remove_rule)
        self.top.get_object('up_btn').connect('clicked', self.__up_rule)
        self.top.get_object('down_btn').connect('clicked', self.__down_rule)
        self.window.connect('response', self.__close)
        self.model = None
        self.rule_model = None
        self.formats = _pd.get_formats()
        self.rules = None
        self.current_format = None
        self.current_rule = None
        self.hier = None
        self.__populate_format_list()
        self.show()

    def build_menu_names(self, obj):
        return (self.title, self.title)

    def __populate_format_list(self):
        flist = self.top.get_object('format_list')
        self.model = ListModel(flist,
                               [(_('Format'), -1, 100)],
                               select_func=self.__format_changed)
        for fmt in self.formats:
            self.model.add([fmt.name])
        self.model.select_row(0)

    def __format_changed(self, _selection):
        """ The format changed, update gui for the new format """
        if self.current_format is not None:
            fmt = self.formats[self.current_format]
            self.__save_format(fmt)
        row = self.model.get_selected_row()
        if row != -1:
            fmt = self.formats[row]
            self.__load_format(fmt)
            self.current_format = row
            self.rules = fmt.rules
        for obj in ('remove', 'name', 'hier_cb', 'language', 'reverse',
                    'add_btn', 'rem_btn', 'up_btn', 'down_btn'):
            self.top.get_object(obj).set_sensitive(row != 0)
        self.__update_rules()

    def __update_rules(self):
        if self.rule_model:
            self.rule_model.clear()
        else:
            self.rule_model = ListModel(
                self.top.get_object('rule_view'),
                [(_('Where'), NOSORT, 150),
                 (_('Type'), NOSORT, 150),
                 (_('Display'), NOSORT, 150),
                 ('', NOSORT, 150, INTEGER)],
                event_func=self.__edit_rule)
        bad_rule = []
        for indx, rule in enumerate(self.rules):
            where = rule.where
            try:
                if where:
                    p_name = self.dbstate.db.get_place_from_handle(
                        where).get_name().get_value()
                else:
                    p_name = _('All')
            except HandleError:
                # deals with missing handles due to changed db or removed item
                p_name = _("Unknown")
            r_type = rule.type
            try:
                if r_type == PlaceRule.T_GRP:
                    rt_name = _("%s Group") % PlaceType.GROUPMAP[rule.value][0]
                elif r_type == PlaceRule.T_TYP:
                    rt_name = PlaceType.DATAMAP[rule.value][DM_NAME]
                else:
                    rt_name = _("Street Format")
            except KeyError:
                # deals with missing groups or types due to changed db or
                # removed item
                bad_rule.append(rule)
                continue
            r_abb = int(rule.abb)
            if rule.vis >= PlaceRule.V_ALL and r_abb != PlaceRule.A_NONE:
                if r_abb == PlaceRule.A_FIRST:
                    abbr = _("First")
                else:
                    abbr = str(rule.abb)
                vis = _("{r_vis}, Abbrev: {abbr}").format(
                    r_vis=PlaceRule.VIS_MAP[rule.vis], abbr=abbr)
            else:
                vis = PlaceRule.VIS_MAP[rule.vis]
            self.rule_model.add((p_name, rt_name, vis, indx))
        for rule in bad_rule:
            self.rules.remove(rule)

    def __name_changed(self, entry):
        dummy_store, iter_ = self.model.get_selected()
        self.model.set(iter_, [entry.get_text()])

    def __load_format(self, fmt):
        self.top.get_object('name').set_text(fmt.name)
        self.top.get_object('language').set_text(fmt.language)
        self.top.get_object('reverse').set_active(fmt.reverse)
        hier = self.top.get_object('hier_cb')
        custom_hier_types = sorted(self.dbstate.db.get_placehier_types(),
                                   key=lambda s: s.lower())
        mapping = PlaceHierType.get_map(PlaceHierType)
        self.hier = StandardCustomSelector(
            mapping, hier, custom_key=PlaceHierType.CUSTOM,
            additional=custom_hier_types, )
        if fmt.hier:
            self.hier.set_values((int(fmt.hier), str(fmt.hier)))

    def __save_format(self, fmt):
        fmt.name = self.top.get_object('name').get_text()
        fmt.hier = PlaceHierType(self.hier.get_values())
        fmt.language = self.top.get_object('language').get_text()
        fmt.reverse = self.top.get_object('reverse').get_active()

    def __add(self, _button):
        name = _('New')
        self.formats.append(
            PlaceFormat(name, PlaceHierType(PlaceHierType.ADMIN),
                        '', False, []))
        self.model.add([name])
        self.model.select_row(len(self.formats) - 1)

    def __remove(self, _button):
        dummy_store, iter_ = self.model.get_selected()
        if iter_:
            self.current_format = None
            del self.formats[self.model.get_selected_row()]
            self.model.remove(iter_)
        if self.model.get_selected_row() == -1:
            self.model.select_row(len(self.formats) - 1)

    def __close(self, *_obj):
        """ Save or abandon work """
        fmt = self.formats[self.current_format]
        self.__save_format(fmt)
        self.dbstate.db.save_place_formats(_pd.get_formats())
        self.callback()
        self.close()

    def __add_rule(self, _button):
        """ Add a new rule """
        rule = PlaceRule(None, PlaceRule.T_GRP, PlaceType.G_COUNTRY,
                         PlaceRule.V_SMALL, PlaceAbbrevType(PlaceRule.A_NONE))
        self.rules.append(rule)
        EditPlaceRule(self.uistate, self.dbstate, self.track, rule,
                      self.edit_rule_callback)

    def __edit_rule(self, _obj):
        """ edit the selected rule """
        row = self.rule_model.get_selected_row()
        EditPlaceRule(self.uistate, self.dbstate, self.track, self.rules[row],
                      self.edit_rule_callback)

    def edit_rule_callback(self):
        """ update the ui with rule data """
        self.__update_rules()

    def __remove_rule(self, _button):
        """ Remove a rule """
        dummy_store, iter_ = self.rule_model.get_selected()
        if iter_:
            del self.rules[self.rule_model.get_selected_row()]
            self.rule_model.remove(iter_)
        if self.rule_model.get_selected_row() == -1:
            self.rule_model.select_row(len(self.formats) - 1)

    def __up_rule(self, _button):
        """ Move a rule up in the list """
        row = self.rule_model.get_selected_row()
        if row < 1:
            return
        self.rule_model.move_up(row)
        self.rules.insert(row, self.rules.pop(row))

    def __down_rule(self, _button):
        """ Move a rule down in list """
        row = self.rule_model.get_selected_row()
        if row >= len(self.rules) - 1 or row == -1:
            return
        self.rule_model.move_down(row)
        self.rules.insert(row + 1, self.rules.pop(row))


#-------------------------------------------------------------------------
#
# EditPlaceRule
#
#-------------------------------------------------------------------------
class EditPlaceRule(ManagedWindow):
    """ Editor for Place Rules """
    def __init__(self, uistate, dbstate, track, rule, callback):
        self.dbstate = dbstate
        self.title = _('Place Format Rule Editor')
        ManagedWindow.__init__(self, uistate, track, EditPlaceRule, modal=True)
        self.callback = callback
        self.top = Glade(toplevel='rule_dlg', also_load=['image1'])
        self.set_window(self.top.toplevel, None, self.title, None)
        self.setup_configs('interface.editplacerule', 500, 400)
        self.top.get_object('all_btn').connect('clicked', self.__all_btn)
        self.top.get_object('place_btn').connect('clicked', self.__place_btn)
        self.window.connect('response', self.__done)
        self.where_cb = self.top.get_object('where_cb')
        self.where = None
        self.type_combo = None
        self.vis_cb = self.top.get_object('vis_cb')
        self.rule = rule
        # set 'where' label
        try:
            if rule.where:
                p_name = self.dbstate.db.get_place_from_handle(
                    rule.where).get_name().get_value()
            else:
                p_name = _('All Places')
        except HandleError:
            p_name = _("Unknown")
        self.top.get_object('where_lbl').set_text(p_name)
        # set up what combo
        what_cb = self.top.get_object('what_cb')
        what_cb.connect('changed', self.__what_changed)
        what_cb.set_active_id(str(rule.type))
        # set up type and vis combo
        self.__what_changed(what_cb, use_val=True)
        # set up abb combo
        abb = self.top.get_object('abbrev_cb')
        custom = sorted(self.dbstate.db.get_placeabbr_types(),
                        key=lambda s: s.lower())
        mapping = PlaceAbbrevType.get_map(PlaceAbbrevType).copy()
        mapping[-2] = _("None")
        mapping[-3] = _("First")
        self.abb_combo = StandardCustomSelector(
            mapping, cbe=abb, custom_key=PlaceAbbrevType.CUSTOM,
            additional=custom)
        self.abb_combo.set_values((int(rule.abb), str(rule.abb)))
        self.show()

    def build_menu_names(self, obj):
        return (self.title, self.title)

    def __all_btn(self, _obj):
        """ 'Where/All' button clicked, set rule for all places
        """
        self.where = None
        self.top.get_object('where_lbl').set_text(_('All Places'))

    def __place_btn(self, _obj):
        """ Select the place for this rule """
        sel = SelectPlace(self.dbstate, self.uistate, self.track)
        place = sel.run()
        if place:
            self.where = place.handle
            name = place.get_name().get_value()
            self.top.get_object('where_lbl').set_text(name)

    def __what_changed(self, _obj, use_val=False):
        """ Change type combo and vis combo based on what combo setting
        """
        r_type = _obj.get_active_id()
        if not r_type:
            return
        r_type = int(r_type)
        def_vis = PlaceRule.V_NONE
        type_cb = self.top.get_object('type_cbe')
        vis_lst = (PlaceRule.V_NONE, PlaceRule.V_ALL,
                   PlaceRule.V_SMALL, PlaceRule.V_LARGE)
        if r_type == PlaceRule.T_ST_NUM:
            self.top.get_object('type_lbl').set_text('')
            type_cb.get_child().set_text('')
            type_cb.set_sensitive(False)
            self.top.get_object('abbrev_cb').get_child().set_text('')
            self.top.get_object('abbrev_cb').set_sensitive(False)
            vis_lst = (PlaceRule.V_NONE, PlaceRule.V_STNUM, PlaceRule.V_NUMST)
            def_vis = PlaceRule.V_NUMST
        elif r_type == PlaceRule.T_GRP:
            self.top.get_object('type_lbl').set_text(_('Group:'))
            type_cb.set_sensitive(True)
            self.top.get_object('abbrev_cb').set_sensitive(True)
            mapping = {key: tup[0] for key, tup in PlaceType.GROUPMAP.items()}
            self.type_combo = StandardCustomSelector(
                mapping, type_cb, custom_key=PlaceType.CUSTOM)
            value = self.rule.value if use_val else PlaceType.G_PLACE
            self.type_combo.set_values((
                self.rule.value, PlaceType.GROUPMAP.get(
                    self.rule.value, PlaceType.GROUPMAP[value])[0]))
        elif r_type == PlaceRule.T_TYP:
            self.top.get_object('type_lbl').set_text(_('Type:'))
            type_cb.set_sensitive(True)
            self.top.get_object('abbrev_cb').set_sensitive(True)
            mapping = {key: tup[DM_NAME] for
                       key, tup in PlaceType.DATAMAP.items()}
            self.type_combo = StandardCustomSelector(
                mapping, type_cb, custom_key=PlaceType.CUSTOM,
                menu=PlaceType.get_menu())
            value = self.rule.value if use_val else PlaceType.UNKNOWN
            self.type_combo.set_values((
                self.rule.value, PlaceType.DATAMAP.get(
                    self.rule.value, PlaceType.DATAMAP[value])[DM_NAME]))
        self.vis_cb.remove_all()
        for vis in vis_lst:
            self.vis_cb.append(str(vis), PlaceRule.VIS_MAP[vis])
        if not self.vis_cb.set_active_id(str(self.rule.vis)):
            self.vis_cb.set_active_id(str(def_vis))

    def __done(self, _obj, response):
        """ Dialog is closing """
        if response == Gtk.ResponseType.OK:
            # need to save rule
            abb = self.abb_combo.get_values()
            self.rule.abb = (
                PlaceAbbrevType(-2) if (
                    abb[0] == PlaceAbbrevType.CUSTOM) else
                PlaceAbbrevType(abb))
            self.rule.where = self.where
            self.rule.type = int(self.top.get_object('what_cb').
                                 get_active_id())
            if self.rule.type != PlaceRule.T_ST_NUM:
                value = self.type_combo.get_values()
                if value[0]:  # if not CUSTOM, use value
                    self.rule.value = value[0]
                else:       # CUSTOM, pick default values instead
                    if self.rule.type == PlaceRule.T_GRP:
                        self.rule.value = PlaceType.G_PLACE
                    else:
                        self.rule.value = PlaceType.UNKNOWN
            else:
                self.rule.abb = PlaceAbbrevType(-2)
            self.rule.vis = int(self.vis_cb.get_active_id())
        self.callback()
        self.close()
