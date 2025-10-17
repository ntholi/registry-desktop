import json
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class AccordionItem(QWidget):
    """A single accordion item with expandable submenu"""

    item_clicked = Signal(str)  # Emits the action name when submenu item is clicked

    def __init__(self, title, description, submenu_items, parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.submenu_items = submenu_items
        self.is_expanded = False

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Header container
        self.header_btn = QPushButton()
        self.header_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.header_btn.clicked.connect(self.toggle_expand)
        self.header_btn.setFlat(True)
        self.header_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

        # Header widget
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(4)

        # Title
        title_label = QLabel(self.title)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        # Description
        desc_label = QLabel(self.description)
        desc_label.setWordWrap(True)
        desc_font = QFont()
        desc_font.setPointSize(8)
        desc_label.setFont(desc_font)
        header_layout.addWidget(desc_label)

        # Set header widget as button's layout
        btn_layout = QVBoxLayout(self.header_btn)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(header_widget)

        layout.addWidget(self.header_btn)

        # Submenu container
        self.submenu_container = QWidget()
        self.submenu_layout = QVBoxLayout(self.submenu_container)
        self.submenu_layout.setContentsMargins(0, 0, 0, 0)
        self.submenu_layout.setSpacing(2)

        # Add submenu items
        for item in self.submenu_items:
            submenu_btn = QPushButton(item["title"])
            submenu_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            submenu_btn.clicked.connect(
                lambda checked=False, action=item["action"]: self.on_submenu_clicked(
                    action
                )
            )

            # Style submenu button
            submenu_font = QFont()
            submenu_font.setPointSize(9)
            submenu_btn.setFont(submenu_font)
            submenu_btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            submenu_btn.setMinimumHeight(32)

            self.submenu_layout.addWidget(submenu_btn)

        self.submenu_container.setMaximumHeight(0)
        self.submenu_container.setVisible(False)
        layout.addWidget(self.submenu_container)

    def toggle_expand(self):
        """Toggle the expansion state of the accordion item"""
        self.is_expanded = not self.is_expanded

        if self.is_expanded:
            self.submenu_container.setVisible(True)
            target_height = self.submenu_container.sizeHint().height()

            # Animate expansion
            self.animation = QPropertyAnimation(
                self.submenu_container, b"maximumHeight"
            )
            self.animation.setDuration(200)
            self.animation.setStartValue(0)
            self.animation.setEndValue(target_height)
            self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.animation.start()
        else:
            # Animate collapse
            self.animation = QPropertyAnimation(
                self.submenu_container, b"maximumHeight"
            )
            self.animation.setDuration(200)
            self.animation.setStartValue(self.submenu_container.height())
            self.animation.setEndValue(0)
            self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.animation.finished.connect(
                lambda: self.submenu_container.setVisible(False)
            )
            self.animation.start()

    def on_submenu_clicked(self, action):
        """Handle submenu item click"""
        self.item_clicked.emit(action)


class AccordionNavigation(QWidget):
    """Main accordion navigation widget"""

    navigation_clicked = Signal(
        str
    )  # Emits action name when any navigation item is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_menu()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(16, 20, 16, 16)
        title_layout.setSpacing(2)

        title_label = QLabel("Registry")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)

        subtitle_label = QLabel("Navigation Menu")
        subtitle_font = QFont()
        subtitle_font.setPointSize(9)
        subtitle_label.setFont(subtitle_font)
        title_layout.addWidget(subtitle_label)

        layout.addWidget(title_widget)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setLineWidth(1)
        layout.addWidget(separator)

        # Scroll area for accordion items
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container for accordion items
        self.accordion_container = QWidget()
        self.accordion_layout = QVBoxLayout(self.accordion_container)
        self.accordion_layout.setContentsMargins(0, 0, 0, 0)
        self.accordion_layout.setSpacing(2)
        self.accordion_layout.addStretch()

        scroll_area.setWidget(self.accordion_container)
        layout.addWidget(scroll_area)

        # Set width
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)

    def load_menu(self):
        """Load menu configuration from JSON file"""
        config_path = Path(__file__).parent / "menu.json"

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            # Remove stretch before adding items
            if self.accordion_layout.count() > 0:
                self.accordion_layout.takeAt(self.accordion_layout.count() - 1)

            # Create accordion items
            for item_config in config["menu_items"]:
                accordion_item = AccordionItem(
                    title=item_config["title"],
                    description=item_config["description"],
                    submenu_items=item_config["submenu"],
                )
                accordion_item.item_clicked.connect(self.on_navigation_clicked)
                self.accordion_layout.addWidget(accordion_item)

                # Add separator between items
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                self.accordion_layout.addWidget(separator)

            # Add stretch at the end
            self.accordion_layout.addStretch()

        except FileNotFoundError:
            print(f"Menu configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            print(f"Error parsing menu configuration: {e}")

    def on_navigation_clicked(self, action):
        """Handle navigation item click"""
        print(f"Navigation clicked: {action}")
        self.navigation_clicked.emit(action)
