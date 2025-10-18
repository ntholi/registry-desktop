import json
from pathlib import Path

import wx
import wx.lib.agw.customtreectrl as CT


class AccordionNavigation(wx.Panel):
    """Navigation panel using CustomTreeCtrl for accordion-like behavior"""

    def __init__(self, parent, on_navigation_clicked=None):
        super().__init__(parent)
        self.on_navigation_clicked = on_navigation_clicked
        self.setup_ui()
        self.load_menu()

    def setup_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Title section
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

        # Separator
        line = wx.StaticLine(self)
        sizer.Add(line, 0, wx.EXPAND)

        # Tree control for accordion
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
        self.tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.on_item_activated)
        sizer.Add(self.tree, 1, wx.EXPAND)

        self.SetSizer(sizer)
        self.SetMinSize((260, -1))
        self.SetMaxSize((320, -1))

    def load_menu(self):
        """Load menu configuration from JSON file"""
        config_path = Path(__file__).parent / "menu.json"

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            root = self.tree.AddRoot("Root")

            for item_config in config["menu_items"]:
                # Add category as parent
                parent_item = self.tree.AppendItem(
                    root,
                    f"{item_config['title']}\n{item_config['description']}",
                )
                parent_font = self.tree.GetItemFont(parent_item)
                parent_font.PointSize = 10
                parent_font = parent_font.Bold()
                self.tree.SetItemFont(parent_item, parent_font)

                # Add submenu items
                for submenu in item_config["submenu"]:
                    child_item = self.tree.AppendItem(
                        parent_item, submenu["title"], data=submenu["action"]
                    )
                    child_font = self.tree.GetItemFont(child_item)
                    child_font.PointSize = 9
                    self.tree.SetItemFont(child_item, child_font)

            # Expand all categories
            self.tree.ExpandAll()

        except FileNotFoundError:
            print(f"Menu configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            print(f"Error parsing menu configuration: {e}")

    def on_item_activated(self, event):
        """Handle tree item activation (double-click or enter)"""
        item = event.GetItem()
        if item and self.tree.GetItemData(item):
            action = self.tree.GetItemData(item)
            print(f"Navigation clicked: {action}")
            if self.on_navigation_clicked:
                self.on_navigation_clicked(action)
