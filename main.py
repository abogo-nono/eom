import os
import sys
from PySide6.QtWidgets import QMainWindow, QApplication, QFileDialog, QTableWidgetItem, QMessageBox
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import QFileInfo, QFile, QTextStream, Qt, QRect
import Extractor

from app_ui import Ui_MainWindow

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super(MainWindow, self).__init__()
        
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.setWindowFlags(Qt.FramelessWindowHint)
        
        
        self.draggable = True
        self.old_pos = None
        self.ui.header_widget.mousePressEvent = self.mouse_press_event
        self.ui.header_widget.mouseMoveEvent = self.mouse_move_event
        
        self.anim_duration = 300
        self.update_maximize_button_icon()
        
        self.ui.minimize_btn.clicked.connect(self.showMinimized)
        self.ui.maximize_btn.clicked.connect(self.toggle_maximized)
        self.ui.close_btn.clicked.connect(self.close)
        
        self.setWindowTitle("Eye On Metadata")
        self.setMinimumSize(850, 600)

        self.ui.stackedWidget.setCurrentIndex(0)
        self.ui.menu_home_btn.setChecked(True)

        self.ui.about_btn.clicked.connect(self.on_about_btn_clicked)

        self.ui.menu_home_btn.clicked.connect(self.on_menu_home_btn_toggled)
        self.ui.menu_extract_btn.clicked.connect(self.on_menu_extract_btn_toggled)
        self.ui.menu_remove_btn.clicked.connect(self.on_menu_remove_btn_toggled)
        self.ui.menu_docs_btn.clicked.connect(self.on_menu_docs_btn_toggled)
        self.ui.menu_report_btn.clicked.connect(self.on_menu_report_btn_toggled)

        self.ui.extract_browse_btn.clicked.connect(self.on_extract_browse_btn_clicked)
        self.ui.extract_btn.clicked.connect(self.on_extract_btn_clicked)
        self.ui.export_btn.clicked.connect(self.on_export_btn_clicked)

        self.ui.remove_browse_btn.clicked.connect(self.on_remove_browse_btn_clicked)
        self.ui.remove_btn.clicked.connect(self.on_remove_btn_clicked)
        self.ui.export_and_remove_btn.clicked.connect(self.on_export_and_remove_btn_clicked)


    def mouse_press_event(self, event):
        if event.button() == Qt.LeftButton and self.draggable:
            self.old_pos = event.globalPosition().toPoint()


    def mouse_move_event(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()


    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

        self.update_maximize_button_icon()


    def update_maximize_button_icon(self):
        if self.isMaximized():
            self.ui.maximize_btn.setIcon(QIcon(':/outline/icons/outline/minimize-2.svg'))
        else:
            self.ui.maximize_btn.setIcon(QIcon(':/outline/icons/outline/maximize-2.svg'))


    def on_about_btn_clicked(self):
        # QMessageBox.aboutQt(self, 'About E.O.M')
        QMessageBox.about(self, 'About E.O.M', """
<p><a name="intro-section" /><span style=" font-size:x-large; font-weight:600;">W</span><span
                style=" font-size:x-large; font-weight:600;">hat is EOM?</span></p>
        <p>Eye On Metadata (E.O.M) is an open-source desktop application that displays, exports and removes metadata
            from a media (images, videos, audio, pdf, ...). EOM is cross-platform so it can work on Windows, Linux, and
            MacOS as well. EOM is developed in February 2024 by <a href="https://github.com/abogo-nono">Abogo Lincoln</a> a software engineer and cybersecurity student</p>
        """)


    def on_extract_browse_btn_clicked(self):
        if self.ui.extraction_type.currentIndex() == 0:
            # get the file absolute path of the file
            image_path = QFileDialog.getOpenFileName(filter="*.jpg")[0]

            # set the file path in the input
            self.ui.extract_file_path.setText(image_path)

            # extracted_data = Extractor.single_image_extractor(image_path)
            # print(extracted_data)
            
        else:
            # get the absolute path of the directory
            dir_path = QFileDialog.getExistingDirectory()
            
            # set the path in the input box
            self.ui.extract_file_path.setText(dir_path)

            # list of images to extract
            # images = self.list_to_dict(os.listdir(dir_path))

            # extracted_data = Extractor.multi_image_extractor(dir_path, images)
            # print(extracted_data)

    def on_extract_btn_clicked(self):
        # get file or file path
        path = self.ui.extract_file_path.text().strip()

        # initialize the array
        self.ui.extracted_table_data.setRowCount(0)

        # define the extraction type
        extraction_type = self.ui.extraction_type.currentIndex()

        # check if there is a selected image
        if not path:
            QMessageBox.warning(self, 'Data Extract Error', 'Select a file / directory first, before extract data contained in image(s)!')
            return
        
        # check the type of extraction
        if extraction_type == 0:
            # Reinitialize the array
            self.ui.extracted_table_data.setRowCount(0)

            # get the image data
            extracted_data = Extractor.single_image_extractor(path)

            # check if we have some data in the  image data dict before
            if extracted_data:
                # print data contained in the image
                for property, value in extracted_data.items():
                    new_row = self.ui.extracted_table_data.rowCount()
                    self.ui.extracted_table_data.insertRow(new_row)
                    self.ui.extracted_table_data.setItem(new_row, 0, QTableWidgetItem(property))
                    self.ui.extracted_table_data.setItem(new_row, 1, QTableWidgetItem(str(value)))
            else:
                QMessageBox.warning(self, 'Data Extract Error', 'The file doesn\'t contain any metadata!')
                return None

        else:
            # get list of file in the selected directory
            images = self.list_to_dict(os.listdir(path))
            
            extracted_data = Extractor.multi_image_extractor(path, images)

            # print data of each if image is there is any
            for image, data in extracted_data.items():
                new_row = self.ui.extracted_table_data.rowCount()
                self.ui.extracted_table_data.insertRow(new_row)

                self.ui.extracted_table_data.setItem(new_row, 0, QTableWidgetItem('Image Name'))
                self.ui.extracted_table_data.setItem(new_row, 1, QTableWidgetItem(image))

                if data:
                    for property, value in data.items():
                        new_row = self.ui.extracted_table_data.rowCount()
                        self.ui.extracted_table_data.insertRow(new_row)

                        self.ui.extracted_table_data.setItem(new_row, 0, QTableWidgetItem(property))
                        self.ui.extracted_table_data.setItem(new_row, 1, QTableWidgetItem(str(value)))

        # resize the table column
        self.ui.extracted_table_data.resizeColumnsToContents()

    def on_export_btn_clicked(self):

        # check if the path is not empty
        if not self.ui.extract_file_path.text():
            QMessageBox.warning(self, 'Empty file path', 'Select a file first, before export his data')
            return

        # extract data from file(s)
        self.on_extract_btn_clicked()

        # check if there is any data in the array
        if not self.ui.extracted_table_data.rowCount():
            QMessageBox.warning(self, 'Data Exported Error', 'Error: image(s) doesn\'t contain metadata!')
            return

        # set the name and the path of the output file
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Extracted Data At", "", "Text Files (*.txt)")
        # print(file_path)

        # write data in the output file
        if file_path:
            try:
                with open(file_path, 'w') as file:
                    for i in range(self.ui.extracted_table_data.rowCount()):
                        line = self.ui.extracted_table_data.item(i, 0).text() + ": "
                        line += self.ui.extracted_table_data.item(i, 1).text() + '\n'
                        file.write(line)
                
                QMessageBox.information(self, 'Data Exported Successfully', 'Data save at: ' + file_path)
            except:
                QMessageBox.warning(self, 'Data Exported Error', 'Error while saving the file!')
        else:
            QMessageBox.warning(self, 'Data Exported Error', 'You must enter a valid filename to stored data')

    def on_remove_browse_btn_clicked(self):
        if self.ui.remove_type.currentIndex() == 0:
            # get the file absolute path of the file
            image_path = QFileDialog.getOpenFileName(filter="*.jpg")[0]

            # set the file path in the input
            self.ui.remove_file_path.setText(image_path)

        else:
            # get the absolute path of the directory
            dir_path = QFileDialog.getExistingDirectory()
            
            # set the path in the input box
            self.ui.remove_file_path.setText(dir_path)

    def on_remove_btn_clicked(self):
        path = self.ui.remove_file_path.text().strip()

        # initialize the array
        self.ui.removed_table_data.setRowCount(0)

        # define the remove type
        remove_type = self.ui.remove_type.currentIndex()

        if not path:
            QMessageBox.warning(self, 'Data Remove Error', 'Select a file first, before remove his data!')
            return None
        
        if remove_type == 0:
            if Extractor.remove_image_metadata(path):
                new_row = self.ui.removed_table_data.rowCount()
                self.ui.removed_table_data.insertRow(new_row)
                self.ui.removed_table_data.setItem(new_row, 0, QTableWidgetItem(path))
                self.ui.removed_table_data.setItem(new_row, 1, QTableWidgetItem('Done'))
            else:
                new_row = self.ui.removed_table_data.rowCount()
                self.ui.removed_table_data.insertRow(new_row)
                self.ui.removed_table_data.setItem(new_row, 0, QTableWidgetItem(path))
                self.ui.removed_table_data.setItem(new_row, 1, QTableWidgetItem('Error'))
        else:
            images = self.list_to_dict(os.listdir(path))

            # print(images) ;return
            new_images = Extractor.multi_remove_image_metadata(path, images)
            print(new_images)
            for image, status in new_images.items():
                print(image, status)
                new_row = self.ui.removed_table_data.rowCount()
                self.ui.removed_table_data.insertRow(new_row)
                self.ui.removed_table_data.setItem(new_row, 0, QTableWidgetItem(image))
                if status:
                    self.ui.removed_table_data.setItem(new_row, 1, QTableWidgetItem('Done!'))
                else:
                    self.ui.removed_table_data.setItem(new_row, 1, QTableWidgetItem('Error!'))


        self.ui.removed_table_data.resizeColumnsToContents()

    def on_export_and_remove_btn_clicked(self): 
        path = self.ui.remove_file_path.text().strip()
        
        if path:
            self.ui.extract_file_path.setText(path)
            self.on_export_btn_clicked()
            self.on_remove_btn_clicked()
        else:
            QMessageBox.warning(self, 'Data Exported Error', 'Error: select image or directory path to extract data and export')

    def on_menu_home_btn_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(0)


    def on_menu_extract_btn_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(1)


    def on_menu_remove_btn_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(2)


    def on_menu_docs_btn_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(3)


    def on_menu_report_btn_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(4)


    def list_to_dict(self, items: list) -> dict:
        images = {}

        if not items:
            return images
        
        for i in range(len(items)):
            images[items[i]] = items[i]
        
        # for i in range(len(items)):
        #     new_items.append(i)
        #     new_items.append(items[i])
        
        # for i in range(0, len(new_items), 2):
        #     images[new_items[i]] = new_items[i + 1]

        return images



if __name__ == '__main__':
    app = QApplication(sys.argv)


    style_file = QFile("style.qss")
    style_file.open(QFile.ReadOnly | QFile.Text)
    style_stream = QTextStream(style_file)
    app.setStyleSheet(style_stream.readAll())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
        

