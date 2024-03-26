# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'app.ui'
##
## Created by: Qt User Interface Compiler version 6.6.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QApplication, QComboBox,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
import resources_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(700, 600)
        MainWindow.setMinimumSize(QSize(700, 600))
        icon = QIcon()
        icon.addFile(u":/images/images/[removal.ai]_9835d176-5ccf-44cb-b4b5-648db9c37be2-istockphoto-844038932-612x612.png", QSize(), QIcon.Normal, QIcon.Off)
        MainWindow.setWindowIcon(icon)
        MainWindow.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_3 = QGridLayout(self.centralwidget)
        self.gridLayout_3.setSpacing(0)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.menu_widget = QWidget(self.centralwidget)
        self.menu_widget.setObjectName(u"menu_widget")
        self.verticalLayout_2 = QVBoxLayout(self.menu_widget)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(5, 0, 5, 10)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(-1, 5, -1, 5)
        self.logo_label = QLabel(self.menu_widget)
        self.logo_label.setObjectName(u"logo_label")
        self.logo_label.setMinimumSize(QSize(0, 50))
        self.logo_label.setMaximumSize(QSize(100, 80))
        self.logo_label.setCursor(QCursor(Qt.ArrowCursor))
        self.logo_label.setPixmap(QPixmap(u":/images/images/[removal.ai]_9835d176-5ccf-44cb-b4b5-648db9c37be2-istockphoto-844038932-612x612.png"))
        self.logo_label.setScaledContents(True)
        self.logo_label.setAlignment(Qt.AlignCenter)

        self.horizontalLayout.addWidget(self.logo_label)


        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.menu_home_btn = QPushButton(self.menu_widget)
        self.menu_home_btn.setObjectName(u"menu_home_btn")
        self.menu_home_btn.setCursor(QCursor(Qt.PointingHandCursor))
        icon1 = QIcon()
        icon1.addFile(u":/light/icons/light/home.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon1.addFile(u":/dark/icons/dark/home.svg", QSize(), QIcon.Normal, QIcon.On)
        self.menu_home_btn.setIcon(icon1)
        self.menu_home_btn.setIconSize(QSize(25, 25))
        self.menu_home_btn.setCheckable(True)
        self.menu_home_btn.setAutoExclusive(True)

        self.verticalLayout.addWidget(self.menu_home_btn)

        self.menu_extract_btn = QPushButton(self.menu_widget)
        self.menu_extract_btn.setObjectName(u"menu_extract_btn")
        self.menu_extract_btn.setCursor(QCursor(Qt.PointingHandCursor))
        icon2 = QIcon()
        icon2.addFile(u":/light/icons/light/search.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon2.addFile(u":/dark/icons/dark/search.svg", QSize(), QIcon.Normal, QIcon.On)
        self.menu_extract_btn.setIcon(icon2)
        self.menu_extract_btn.setIconSize(QSize(25, 25))
        self.menu_extract_btn.setCheckable(True)
        self.menu_extract_btn.setAutoExclusive(True)

        self.verticalLayout.addWidget(self.menu_extract_btn)

        self.menu_remove_btn = QPushButton(self.menu_widget)
        self.menu_remove_btn.setObjectName(u"menu_remove_btn")
        self.menu_remove_btn.setCursor(QCursor(Qt.PointingHandCursor))
        icon3 = QIcon()
        icon3.addFile(u":/light/icons/light/zap-off.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon3.addFile(u":/dark/icons/dark/zap-off.svg", QSize(), QIcon.Normal, QIcon.On)
        self.menu_remove_btn.setIcon(icon3)
        self.menu_remove_btn.setIconSize(QSize(25, 25))
        self.menu_remove_btn.setCheckable(True)
        self.menu_remove_btn.setAutoExclusive(True)

        self.verticalLayout.addWidget(self.menu_remove_btn)

        self.menu_docs_btn = QPushButton(self.menu_widget)
        self.menu_docs_btn.setObjectName(u"menu_docs_btn")
        self.menu_docs_btn.setCursor(QCursor(Qt.PointingHandCursor))
        icon4 = QIcon()
        icon4.addFile(u":/light/icons/light/help-circle.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon4.addFile(u":/dark/icons/dark/help-circle.svg", QSize(), QIcon.Normal, QIcon.On)
        self.menu_docs_btn.setIcon(icon4)
        self.menu_docs_btn.setIconSize(QSize(25, 25))
        self.menu_docs_btn.setCheckable(True)
        self.menu_docs_btn.setAutoExclusive(True)

        self.verticalLayout.addWidget(self.menu_docs_btn)

        self.menu_report_btn = QPushButton(self.menu_widget)
        self.menu_report_btn.setObjectName(u"menu_report_btn")
        self.menu_report_btn.setCursor(QCursor(Qt.PointingHandCursor))
        icon5 = QIcon()
        icon5.addFile(u":/light/icons/light/alert-triangle.svg", QSize(), QIcon.Normal, QIcon.Off)
        icon5.addFile(u":/dark/icons/dark/alert-triangle.svg", QSize(), QIcon.Normal, QIcon.On)
        self.menu_report_btn.setIcon(icon5)
        self.menu_report_btn.setIconSize(QSize(25, 25))
        self.menu_report_btn.setCheckable(True)
        self.menu_report_btn.setAutoExclusive(True)

        self.verticalLayout.addWidget(self.menu_report_btn)


        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.verticalSpacer = QSpacerItem(17, 247, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)


        self.gridLayout_3.addWidget(self.menu_widget, 0, 0, 1, 1)

        self.widget = QWidget(self.centralwidget)
        self.widget.setObjectName(u"widget")
        self.verticalLayout_3 = QVBoxLayout(self.widget)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.header_widget = QWidget(self.widget)
        self.header_widget.setObjectName(u"header_widget")
        self.header_widget.setMinimumSize(QSize(0, 40))
        self.horizontalLayout_6 = QHBoxLayout(self.header_widget)
        self.horizontalLayout_6.setSpacing(0)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setSpacing(0)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer)

        self.title_label = QLabel(self.header_widget)
        self.title_label.setObjectName(u"title_label")
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        self.title_label.setFont(font)

        self.horizontalLayout_5.addWidget(self.title_label)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_2)


        self.horizontalLayout_6.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, -1, 10, -1)
        self.minimize_btn = QPushButton(self.header_widget)
        self.minimize_btn.setObjectName(u"minimize_btn")
        self.minimize_btn.setCursor(QCursor(Qt.PointingHandCursor))
        icon6 = QIcon()
        icon6.addFile(u":/outline/icons/outline/minus.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.minimize_btn.setIcon(icon6)
        self.minimize_btn.setIconSize(QSize(15, 15))

        self.horizontalLayout_4.addWidget(self.minimize_btn)

        self.maximize_btn = QPushButton(self.header_widget)
        self.maximize_btn.setObjectName(u"maximize_btn")
        self.maximize_btn.setCursor(QCursor(Qt.PointingHandCursor))
        icon7 = QIcon()
        icon7.addFile(u":/outline/icons/outline/maximize-2.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.maximize_btn.setIcon(icon7)
        self.maximize_btn.setIconSize(QSize(15, 15))

        self.horizontalLayout_4.addWidget(self.maximize_btn)

        self.close_btn = QPushButton(self.header_widget)
        self.close_btn.setObjectName(u"close_btn")
        self.close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.close_btn.setAcceptDrops(False)
        icon8 = QIcon()
        icon8.addFile(u":/outline/icons/outline/x.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.close_btn.setIcon(icon8)
        self.close_btn.setIconSize(QSize(15, 15))

        self.horizontalLayout_4.addWidget(self.close_btn)


        self.horizontalLayout_6.addLayout(self.horizontalLayout_4)


        self.verticalLayout_3.addWidget(self.header_widget)

        self.stackedWidget = QStackedWidget(self.widget)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.home_page = QWidget()
        self.home_page.setObjectName(u"home_page")
        self.gridLayout = QGridLayout(self.home_page)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_8 = QVBoxLayout()
        self.verticalLayout_8.setSpacing(0)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.welcome_image = QLabel(self.home_page)
        self.welcome_image.setObjectName(u"welcome_image")
        self.welcome_image.setMinimumSize(QSize(0, 0))
        self.welcome_image.setMaximumSize(QSize(16777215, 400))
        self.welcome_image.setPixmap(QPixmap(u":/images/images/hero.jpg"))
        self.welcome_image.setScaledContents(True)
        self.welcome_image.setAlignment(Qt.AlignCenter)
        self.welcome_image.setWordWrap(False)

        self.verticalLayout_8.addWidget(self.welcome_image)

        self.welcome_text = QLabel(self.home_page)
        self.welcome_text.setObjectName(u"welcome_text")

        self.verticalLayout_8.addWidget(self.welcome_text)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setSpacing(0)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.gridLayout_5 = QGridLayout()
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.label_6 = QLabel(self.home_page)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setMaximumSize(QSize(100, 100))
        self.label_6.setPixmap(QPixmap(u":/images/images/types-of-metadata-3-1.jpg"))
        self.label_6.setScaledContents(True)

        self.gridLayout_5.addWidget(self.label_6, 0, 0, 1, 1)

        self.label_7 = QLabel(self.home_page)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout_5.addWidget(self.label_7, 1, 0, 1, 1)


        self.horizontalLayout_8.addLayout(self.gridLayout_5)

        self.gridLayout_6 = QGridLayout()
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.label_8 = QLabel(self.home_page)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setMaximumSize(QSize(100, 100))
        self.label_8.setPixmap(QPixmap(u":/images/images/myths-about-digital-forensics.jpg"))
        self.label_8.setScaledContents(True)

        self.gridLayout_6.addWidget(self.label_8, 0, 1, 1, 1)

        self.label_9 = QLabel(self.home_page)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_6.addWidget(self.label_9, 1, 1, 1, 1)

        self.openGLWidget = QOpenGLWidget(self.home_page)
        self.openGLWidget.setObjectName(u"openGLWidget")

        self.gridLayout_6.addWidget(self.openGLWidget, 0, 0, 1, 1)


        self.horizontalLayout_8.addLayout(self.gridLayout_6)

        self.verticalLayout_7 = QVBoxLayout()
        self.verticalLayout_7.setSpacing(0)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.label_12 = QLabel(self.home_page)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setMaximumSize(QSize(100, 100))
        self.label_12.setPixmap(QPixmap(u":/images/images/preview-lightbox-ALL-ABOUT-3.png"))
        self.label_12.setScaledContents(True)

        self.verticalLayout_7.addWidget(self.label_12)

        self.label_13 = QLabel(self.home_page)
        self.label_13.setObjectName(u"label_13")

        self.verticalLayout_7.addWidget(self.label_13)


        self.horizontalLayout_8.addLayout(self.verticalLayout_7)

        self.verticalLayout_6 = QVBoxLayout()
        self.verticalLayout_6.setSpacing(0)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.label_10 = QLabel(self.home_page)
        self.label_10.setObjectName(u"label_10")
        self.label_10.setMaximumSize(QSize(100, 100))
        self.label_10.setPixmap(QPixmap(u":/images/images/logo.jpg"))
        self.label_10.setScaledContents(True)

        self.verticalLayout_6.addWidget(self.label_10)

        self.label_11 = QLabel(self.home_page)
        self.label_11.setObjectName(u"label_11")

        self.verticalLayout_6.addWidget(self.label_11)


        self.horizontalLayout_8.addLayout(self.verticalLayout_6)


        self.verticalLayout_8.addLayout(self.horizontalLayout_8)

        self.intro_text = QLabel(self.home_page)
        self.intro_text.setObjectName(u"intro_text")

        self.verticalLayout_8.addWidget(self.intro_text)


        self.gridLayout.addLayout(self.verticalLayout_8, 0, 0, 1, 1)

        self.stackedWidget.addWidget(self.home_page)
        self.extract_page = QWidget()
        self.extract_page.setObjectName(u"extract_page")
        self.gridLayout_2 = QGridLayout(self.extract_page)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setSpacing(10)
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.horizontalLayout_9.setContentsMargins(-1, 20, -1, 20)
        self.extraction_type = QComboBox(self.extract_page)
        self.extraction_type.addItem("")
        self.extraction_type.addItem("")
        self.extraction_type.setObjectName(u"extraction_type")
        self.extraction_type.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_9.addWidget(self.extraction_type)

        self.extract_browse_btn = QPushButton(self.extract_page)
        self.extract_browse_btn.setObjectName(u"extract_browse_btn")
        self.extract_browse_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_9.addWidget(self.extract_browse_btn)

        self.extract_file_path = QLineEdit(self.extract_page)
        self.extract_file_path.setObjectName(u"extract_file_path")
        self.extract_file_path.setEnabled(True)
        self.extract_file_path.setReadOnly(True)

        self.horizontalLayout_9.addWidget(self.extract_file_path)

        self.extract_btn = QPushButton(self.extract_page)
        self.extract_btn.setObjectName(u"extract_btn")
        self.extract_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_9.addWidget(self.extract_btn)

        self.export_btn = QPushButton(self.extract_page)
        self.export_btn.setObjectName(u"export_btn")
        self.export_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_9.addWidget(self.export_btn)


        self.gridLayout_2.addLayout(self.horizontalLayout_9, 0, 0, 1, 1)

        self.extracted_table_data = QTableWidget(self.extract_page)
        if (self.extracted_table_data.columnCount() < 2):
            self.extracted_table_data.setColumnCount(2)
        font1 = QFont()
        font1.setPointSize(10)
        font1.setBold(False)
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setFont(font1);
        self.extracted_table_data.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        __qtablewidgetitem1.setFont(font1);
        self.extracted_table_data.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        self.extracted_table_data.setObjectName(u"extracted_table_data")
        self.extracted_table_data.setEditTriggers(QAbstractItemView.SelectedClicked)
        self.extracted_table_data.setRowCount(0)
        self.extracted_table_data.setColumnCount(2)
        self.extracted_table_data.horizontalHeader().setDefaultSectionSize(280)

        self.gridLayout_2.addWidget(self.extracted_table_data, 1, 0, 1, 1)

        self.stackedWidget.addWidget(self.extract_page)
        self.remove_page = QWidget()
        self.remove_page.setObjectName(u"remove_page")
        self.gridLayout_4 = QGridLayout(self.remove_page)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.horizontalLayout_10 = QHBoxLayout()
        self.horizontalLayout_10.setSpacing(10)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.horizontalLayout_10.setContentsMargins(-1, 20, -1, 20)
        self.remove_type = QComboBox(self.remove_page)
        self.remove_type.addItem("")
        self.remove_type.addItem("")
        self.remove_type.setObjectName(u"remove_type")
        self.remove_type.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_10.addWidget(self.remove_type)

        self.remove_browse_btn = QPushButton(self.remove_page)
        self.remove_browse_btn.setObjectName(u"remove_browse_btn")
        self.remove_browse_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_10.addWidget(self.remove_browse_btn)

        self.remove_file_path = QLineEdit(self.remove_page)
        self.remove_file_path.setObjectName(u"remove_file_path")
        self.remove_file_path.setReadOnly(True)

        self.horizontalLayout_10.addWidget(self.remove_file_path)

        self.remove_btn = QPushButton(self.remove_page)
        self.remove_btn.setObjectName(u"remove_btn")
        self.remove_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_10.addWidget(self.remove_btn)

        self.export_and_remove_btn = QPushButton(self.remove_page)
        self.export_and_remove_btn.setObjectName(u"export_and_remove_btn")
        self.export_and_remove_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.horizontalLayout_10.addWidget(self.export_and_remove_btn)


        self.gridLayout_4.addLayout(self.horizontalLayout_10, 0, 0, 1, 1)

        self.removed_table_data = QTableWidget(self.remove_page)
        if (self.removed_table_data.columnCount() < 2):
            self.removed_table_data.setColumnCount(2)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.removed_table_data.setHorizontalHeaderItem(0, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.removed_table_data.setHorizontalHeaderItem(1, __qtablewidgetitem3)
        self.removed_table_data.setObjectName(u"removed_table_data")
        self.removed_table_data.horizontalHeader().setDefaultSectionSize(250)

        self.gridLayout_4.addWidget(self.removed_table_data, 1, 0, 1, 1)

        self.stackedWidget.addWidget(self.remove_page)
        self.docs_page = QWidget()
        self.docs_page.setObjectName(u"docs_page")
        self.gridLayout_7 = QGridLayout(self.docs_page)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.docScrollArea = QScrollArea(self.docs_page)
        self.docScrollArea.setObjectName(u"docScrollArea")
        self.docScrollArea.setAutoFillBackground(False)
        self.docScrollArea.setStyleSheet(u"background: transparent;")
        self.docScrollArea.setFrameShape(QFrame.NoFrame)
        self.docScrollArea.setLineWidth(0)
        self.docScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.docScrollArea.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.docScrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 553, 828))
        self.scrollAreaWidgetContents.setStyleSheet(u"background: transparent;")
        self.gridLayout_8 = QGridLayout(self.scrollAreaWidgetContents)
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.label_4 = QLabel(self.scrollAreaWidgetContents)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setCursor(QCursor(Qt.IBeamCursor))
        self.label_4.setStyleSheet(u"color: #788596;")
        self.label_4.setFrameShadow(QFrame.Plain)
        self.label_4.setTextFormat(Qt.RichText)
        self.label_4.setScaledContents(True)
        self.label_4.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
        self.label_4.setWordWrap(True)
        self.label_4.setOpenExternalLinks(True)

        self.gridLayout_8.addWidget(self.label_4, 0, 0, 1, 1)

        self.docScrollArea.setWidget(self.scrollAreaWidgetContents)

        self.gridLayout_7.addWidget(self.docScrollArea, 0, 0, 1, 1)

        self.stackedWidget.addWidget(self.docs_page)
        self.report_page = QWidget()
        self.report_page.setObjectName(u"report_page")
        self.label_5 = QLabel(self.report_page)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setGeometry(QRect(150, 160, 49, 16))
        self.stackedWidget.addWidget(self.report_page)

        self.verticalLayout_3.addWidget(self.stackedWidget)

        self.footer_widget = QWidget(self.widget)
        self.footer_widget.setObjectName(u"footer_widget")
        self.horizontalLayout_7 = QHBoxLayout(self.footer_widget)
        self.horizontalLayout_7.setSpacing(0)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 5, 0, 5)
        self.footer_left_widget = QWidget(self.footer_widget)
        self.footer_left_widget.setObjectName(u"footer_left_widget")
        self.horizontalLayout_3 = QHBoxLayout(self.footer_left_widget)
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(10, 0, 0, 0)
        self.eom_version_label = QLabel(self.footer_left_widget)
        self.eom_version_label.setObjectName(u"eom_version_label")

        self.horizontalLayout_3.addWidget(self.eom_version_label, 0, Qt.AlignLeft|Qt.AlignVCenter)


        self.horizontalLayout_7.addWidget(self.footer_left_widget, 0, Qt.AlignLeft)

        self.footer_right_widget = QWidget(self.footer_widget)
        self.footer_right_widget.setObjectName(u"footer_right_widget")
        self.horizontalLayout_2 = QHBoxLayout(self.footer_right_widget)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 10, 0)
        self.about_btn = QPushButton(self.footer_right_widget)
        self.about_btn.setObjectName(u"about_btn")
        self.about_btn.setCursor(QCursor(Qt.PointingHandCursor))
        icon9 = QIcon()
        icon9.addFile(u":/light/icons/light/alert-circle.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.about_btn.setIcon(icon9)

        self.horizontalLayout_2.addWidget(self.about_btn)

        self.about_label = QLabel(self.footer_right_widget)
        self.about_label.setObjectName(u"about_label")

        self.horizontalLayout_2.addWidget(self.about_label)


        self.horizontalLayout_7.addWidget(self.footer_right_widget, 0, Qt.AlignRight|Qt.AlignVCenter)


        self.verticalLayout_3.addWidget(self.footer_widget)


        self.gridLayout_3.addWidget(self.widget, 0, 1, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        QWidget.setTabOrder(self.menu_home_btn, self.menu_remove_btn)
        QWidget.setTabOrder(self.menu_remove_btn, self.menu_extract_btn)
        QWidget.setTabOrder(self.menu_extract_btn, self.menu_report_btn)
        QWidget.setTabOrder(self.menu_report_btn, self.minimize_btn)
        QWidget.setTabOrder(self.minimize_btn, self.maximize_btn)
        QWidget.setTabOrder(self.maximize_btn, self.close_btn)
        QWidget.setTabOrder(self.close_btn, self.menu_docs_btn)
        QWidget.setTabOrder(self.menu_docs_btn, self.about_btn)

        self.retranslateUi(MainWindow)

        self.stackedWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Eye On Metedata", None))
        self.logo_label.setText("")
        self.menu_home_btn.setText(QCoreApplication.translate("MainWindow", u"Home", None))
#if QT_CONFIG(shortcut)
        self.menu_home_btn.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+H", None))
#endif // QT_CONFIG(shortcut)
        self.menu_extract_btn.setText(QCoreApplication.translate("MainWindow", u"Extract", None))
#if QT_CONFIG(shortcut)
        self.menu_extract_btn.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+E", None))
#endif // QT_CONFIG(shortcut)
        self.menu_remove_btn.setText(QCoreApplication.translate("MainWindow", u"Remove", None))
#if QT_CONFIG(shortcut)
        self.menu_remove_btn.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+R", None))
#endif // QT_CONFIG(shortcut)
        self.menu_docs_btn.setText(QCoreApplication.translate("MainWindow", u"Docs", None))
#if QT_CONFIG(shortcut)
        self.menu_docs_btn.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+D", None))
#endif // QT_CONFIG(shortcut)
        self.menu_report_btn.setText(QCoreApplication.translate("MainWindow", u"Report Bugs", None))
#if QT_CONFIG(shortcut)
        self.menu_report_btn.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+B", None))
#endif // QT_CONFIG(shortcut)
        self.title_label.setText(QCoreApplication.translate("MainWindow", u"Eyes On Metadata", None))
        self.minimize_btn.setText("")
        self.maximize_btn.setText("")
        self.close_btn.setText("")
#if QT_CONFIG(shortcut)
        self.close_btn.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Q", None))
#endif // QT_CONFIG(shortcut)
        self.welcome_image.setText("")
        self.welcome_text.setText(QCoreApplication.translate("MainWindow", u"welcome text + intro to features", None))
        self.label_6.setText("")
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"Title + description", None))
        self.label_8.setText("")
        self.label_9.setText(QCoreApplication.translate("MainWindow", u"Title + description", None))
        self.label_12.setText("")
        self.label_13.setText(QCoreApplication.translate("MainWindow", u"Title + description", None))
        self.label_10.setText("")
        self.label_11.setText(QCoreApplication.translate("MainWindow", u"Title + description", None))
        self.intro_text.setText(QCoreApplication.translate("MainWindow", u"others text for details", None))
        self.extraction_type.setItemText(0, QCoreApplication.translate("MainWindow", u"Single Extraction", None))
        self.extraction_type.setItemText(1, QCoreApplication.translate("MainWindow", u"Multiple Extraction", None))

        self.extract_browse_btn.setText(QCoreApplication.translate("MainWindow", u"Browse", None))
        self.extract_btn.setText(QCoreApplication.translate("MainWindow", u"Extract", None))
        self.export_btn.setText(QCoreApplication.translate("MainWindow", u"Export", None))
        ___qtablewidgetitem = self.extracted_table_data.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"Property", None));
        ___qtablewidgetitem1 = self.extracted_table_data.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"Value", None));
        self.remove_type.setItemText(0, QCoreApplication.translate("MainWindow", u"Single Remove", None))
        self.remove_type.setItemText(1, QCoreApplication.translate("MainWindow", u"Multiple Remove", None))

        self.remove_browse_btn.setText(QCoreApplication.translate("MainWindow", u"Browse", None))
        self.remove_btn.setText(QCoreApplication.translate("MainWindow", u"Remove", None))
        self.export_and_remove_btn.setText(QCoreApplication.translate("MainWindow", u"Export and Remove", None))
        ___qtablewidgetitem2 = self.removed_table_data.horizontalHeaderItem(0)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"File", None));
        ___qtablewidgetitem3 = self.removed_table_data.horizontalHeaderItem(1)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"Status", None));
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p align=\"center\"><img src=\":/images/images/istockphoto-844038932-612x612_resized.jpg\"/></p><p align=\"center\"><br/></p><p><a name=\"intro-section\"/><span style=\" font-size:x-large; font-weight:600; color:#33c6cb;\">W</span><span style=\" font-size:x-large; font-weight:600; color:#33c6cb;\">hat is EOM?</span></p><p>Eye On Metadata (E.O.M) is an open-source desktop application that displays, exports and removes metadata from a media (images, videos, audio, pdf, ...). EOM is cross-platform so it can work on Windows, Linux, and MacOS as well. </p><p><span style=\" font-size:x-large; font-weight:600; color:#33c6cb;\">How do you extract/display metadata from a media?</span></p><p>Follow these steps to display metadata from one or many file </p><ol style=\"margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; -qt-list-indent: 1;\"><li style=\" margin-top:12px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Click on extract </"
                        "li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Select the extraction type </li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Select the file or the directory </li><li style=\" margin-top:0px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Click on the extract button </li></ol><p><span style=\" font-size:x-large; font-weight:600; color:#33c6cb;\">How do you remove metadata from one or many files?</span></p><p>To remove one metadata from media, you must follow these steps </p><ol style=\"margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; -qt-list-indent: 1;\"><li style=\" margin-top:12px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Click on remove </li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-"
                        "indent:0; text-indent:0px;\">Select the remove type </li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Select the file or the directory </li><li style=\" margin-top:0px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Click on the remove button </li></ol><p><span style=\" font-size:x-large; font-weight:600; color:#33c6cb;\">How do you export metadata of file(s) to your local storage?</span></p><p>You can export metadata of one or many files into a file stored in your local disk </p><ol style=\"margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; -qt-list-indent: 1;\"><li style=\" margin-top:12px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Click on extract </li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Select the extract type </li><li style=\""
                        " margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Select a file or directory by clicking the browse button </li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Click on export </li><li style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Select the path and the name of the file which will contain the data </li><li style=\" margin-top:0px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Click on save </li></ol><p><span style=\" font-size:x-large; font-weight:600; color:#33c6cb;\">How do you report a bug, contribute, or suggest features?</span></p><ol style=\"margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; -qt-list-indent: 1;\"><li style=\" margin-top:12px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"
                        "\">Open this link <a href=\"https://github.com/abogo-nono/eom\"><span style=\" text-decoration: underline; color:#33c6cb;\">EOM repo</span></a></li><li style=\" margin-top:0px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">Follow the steps presented in the readme </li></ol></body></html>", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"report", None))
        self.eom_version_label.setText(QCoreApplication.translate("MainWindow", u"E.O.M v1.0.0 all rights are reserved", None))
        self.about_btn.setText("")
        self.about_label.setText(QCoreApplication.translate("MainWindow", u"about", None))
    # retranslateUi

