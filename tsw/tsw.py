
import sys
from PyQt4 import QtGui, QtCore, uic
import time
import os
import actmon

ROOT = os.path.abspath(os.path.dirname(__file__))


class EditableQLabel(QtGui.QStackedWidget):
    changed = QtCore.pyqtSignal(str)

    def __init__(self, text, parent=None):
        QtGui.QStackedWidget.__init__(self, parent)

        self.label = QtGui.QLabel(text, self)
        self.edit = QtGui.QLineEdit()

        self.insertWidget(0, self.label)
        self.insertWidget(1, self.edit)
        self.setCurrentIndex(0)

        p = self.sizePolicy()
        p.setVerticalPolicy(QtGui.QSizePolicy.Fixed)
        self.setSizePolicy(p)

        self.edit.editingFinished.connect(self.edit_finish)

    def mouseDoubleClickEvent(self, ev):
        self.edit.setText(self.label.text())
        self.setCurrentIndex(1)
        self.edit.setFocus()

    def edit_finish(self):
        text = self.edit.text()
        self.label.setText(text)
        self.setCurrentIndex(0)
        self.changed.emit(text)

    def sizeHint(self):
        return self.label.sizeHint()


class KlickableQLabel(QtGui.QLabel):
    double_click = QtCore.pyqtSignal()

    def __init__(self, text, parent=None):
        QtGui.QLabel.__init__(self, text, parent)

    def mouseDoubleClickEvent(self, ev):
        self.double_click.emit()


class Task(QtCore.QObject):
    def __init__(self, parent=None):
        QtCore.QObject.__init__(self, parent)

        self.value = 0
        self.start_time = 0

        self.name_label = EditableQLabel("Task")
        self.time_label = KlickableQLabel("")
        self.action_button = QtGui.QPushButton("Start")
        self.action_button.setCheckable(True)
        self.tray_menue = QtGui.QAction("Task", self)
        self.tray_menue.setCheckable(True)

        self.action_button.toggled.connect(self.button_toggeld)
        self.time_label.double_click.connect(self.time_double_clicked)
        self.name_label.changed.connect(self.tray_menue.setText)
        self.tray_menue.toggled.connect(self.button_toggeld)

        self.update()

    def button_toggeld(self, value):
        if value:
            self.ui_start()
            self.start()
        else:
            self.stop()
            self.ui_stop()

    def ui_start(self):
        self.action_button.setText("Stop")
        self.action_button.setChecked(True)
        self.tray_menue.setChecked(True)

    def ui_stop(self):
        self.action_button.setChecked(False)
        self.tray_menue.setChecked(False)
        if self.value == 0:
            self.action_button.setText("Start")
        else:
            self.action_button.setText("Continue")

    def time_double_clicked(self):
        value, ok = QtGui.QInputDialog.getInt(None, "Add time in minutes", "Minutes")
        if ok:
            self.value += value*60
            self.update()

    def start(self):
        self.start_time = time.time()

    def stop(self, stop_time=None):
        if self.is_active():
            if stop_time is None:
                stop_time = time.time()
            interval = stop_time - self.start_time
            self.value += interval

    def update(self):
        value = self.get_value()
        self.time_label.setText("%d:%02d:%02d" % (value/3600, (value/60) % 60, value % 60))

    def is_active(self):
        return self.action_button.isChecked()

    def get_value(self):
        if self.is_active():
            interval = time.time() - self.start_time
        else:
            interval = 0

        return self.value + interval

    def revert(self, revert_time):
        self.stop(revert_time)
        self.ui_stop()


class Mainwindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)

        self.ui = uic.loadUi(os.path.join(ROOT, 'main.ui'), self)
        self.ui.show()

        self.exit = False

        self.sys_tray_icon = QtGui.QSystemTrayIcon(self)
        self.sys_tray_icon.setIcon(QtGui.QIcon(os.path.join(ROOT, 'icon.png')))
        self.sys_tray_icon.setVisible(True)
        self.sys_tray_icon.activated.connect(self.tray_action)
        self.sys_tray_menu = QtGui.QMenu(self)
        exit_action = self.sys_tray_menu.addAction("Exit")
        exit_action.triggered.connect(self.exit_action)
        self.sys_tray_menu.addSeparator()
        self.sys_tray_icon.setContextMenu(self.sys_tray_menu)

        self.ui.add_button.released.connect(self.add)

        self.status = QtGui.QLabel('')
        self.status.setAlignment(QtCore.Qt.AlignRight)
        self.statusbar.addWidget(self.status, 1)

        self.tasks = []

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update)
        self.update_timer.start(1000)

        self.add()

    def update(self):
        sum = 0
        for t in self.tasks:
            t.update()
            sum += t.get_value()

        self.status.setText("total: %d:%02d" % (sum/3600, (sum/60) % 60))

        if actmon.get_idle_time() >= 15*60*1000:
            active = False
            for t in self.tasks:
                if t.is_active():
                    active = True
                    break

            if active:
                inactive_start_time = time.time() - 15*60
                value = QtGui.QMessageBox.question(self, "No Activity", "No activity since %s. Stop clocks?" % time.strftime("%H:%M", time.localtime(inactive_start_time)), "Yes", "No")
                if value == 0:
                    for t in self.tasks:
                        if t.is_active():
                            t.revert(inactive_start_time)

    def add(self):
        task = Task(self)
        self.tasks.append(task)

        row = self.ui.main.layout().rowCount()
        self.ui.main.layout().addWidget(task.name_label, row, 0)
        self.ui.main.layout().addWidget(task.time_label, row, 1)
        self.ui.main.layout().addWidget(task.action_button, row, 2)
        self.sys_tray_menu.addAction(task.tray_menue)

    def exit_action(self):
        self.exit = True
        self.close()

    def closeEvent(self, ev):
        if self.exit is False:
            ev.ignore()
            self.hide()

    def tray_action(self, reason):
        #print(reason)
        #if reason == QtGui.QSystemTrayIcon.DoubleClick:
        self.show()


def main():
    app = QtGui.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(os.path.join(ROOT, 'icon.png')))
    Mainwindow()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
