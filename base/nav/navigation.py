import json
from pathlib import Path

import wx
import wx.lib.agw.customtreectrl as CT


class AccordionNavigation(wx.Panel):
    """Navigation panel using CustomTreeCtrl for accordion-like behavior"""

    def __init__(self, parent, on_navigation_clicked=None):
        super().__init__(parent)
        self.on_navigation_clicked = on_navigation_clicked
        self.action_items = {}
        self._ignore_selection = False
        self.setup_ui()
        self.load_menu()

    def setup_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        title_panel = wx.Panel(self)
        title_sizer = wx.BoxSizer(wx.VERTICAL)

        title_label = wx.StaticText(title_panel, label="Registry")
        title_font = title_label.GetFont()
        title_font.PointSize = 16
        title_font = title_font.Bold()
        title_label.SetFont(title_font)
        title_sizer.Add(title_label, 0, wx.LEFT | wx.TOP, 16)

        subtitle_label = wx.StaticText(title_panel, label="Navigation Menu")
        subtitle_font = subtitle_label.GetFont()
        subtitle_font.PointSize = 9
        subtitle_label.SetFont(subtitle_font)
        title_sizer.Add(subtitle_label, 0, wx.LEFT | wx.BOTTOM, 16)

        title_panel.SetSizer(title_sizer)
        sizer.Add(title_panel, 0, wx.EXPAND)

        line = wx.StaticLine(self)
        sizer.Add(line, 0, wx.EXPAND)

        self.tree = CT.CustomTreeCtrl(
            self,
            agwStyle=(
                wx.TR_DEFAULT_STYLE
                | wx.TR_HIDE_ROOT
                | wx.TR_NO_LINES
                | CT.TR_AUTO_CHECK_CHILD
                | CT.TR_HAS_VARIABLE_ROW_HEIGHT
            ),
        )
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_item_selected)
        sizer.Add(self.tree, 1, wx.EXPAND)

        self.SetSizer(sizer)
        self.SetMinSize(wx.Size(260, -1))
        self.SetMaxSize(wx.Size(320, -1))

    def load_menu(self):
        """Load menu configuration from JSON file"""
        config_path = Path(__file__).parent / "menu.json"

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            root = self.tree.AddRoot("Root")

            def add_menu_items(parent, items, level=0):
                for item_config in items:
                    title = item_config["title"]
                    action = item_config.get("action")
                    submenu = item_config.get("submenu")

                    item = self.tree.AppendItem(parent, title, data=action)

                    font = self.tree.GetItemFont(item)
                    if level == 0:
                        font.PointSize = 10
                        font = font.Bold()
                    else:
                        font.PointSize = 9
                    self.tree.SetItemFont(item, font)

                    if action:
                        self.action_items[action] = item

                    if submenu:
                        add_menu_items(item, submenu, level + 1)

            add_menu_items(root, config["menu_items"])

            # Expand all categories
            self.tree.ExpandAll()

        except FileNotFoundError:
            print(f"Menu configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            print(f"Error parsing menu configuration: {e}")

    def on_item_selected(self, event):
        """Handle tree item selection (single-click)"""
        if self._ignore_selection:
            self._ignore_selection = False
            return
        item = event.GetItem()
        if item and self.tree.GetItemData(item):
            action = self.tree.GetItemData(item)
            print(f"Navigation clicked: {action}")
            if self.on_navigation_clicked:
                self.on_navigation_clicked(action)

    def select_action(self, action):
        """Programmatically select a navigation action without firing callbacks"""
        item = self.action_items.get(action)
        if not item:
            return
        self._ignore_selection = True
        self.tree.SelectItem(item)
        self.tree.EnsureVisible(item)
