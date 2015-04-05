
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

    def text(self):
        return self.label.text()

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
    id = 0

    def __init__(self, parent=None):
        QtCore.QObject.__init__(self, parent)

        self.id = Task.id
        self.label = EditableQLabel("Task", parent)
        self.time = KlickableQLabel("", parent)
        self.button = QtGui.QPushButton("Start", parent)
        self.button.setCheckable(True)
        self.tray = QtGui.QAction("Task", parent)
        self.tray.setCheckable(True)
        self.start_time = 0
        self.value = 0
        self.active = False

        self.time.double_click.connect(self.correct_time)
        self.label.changed.connect(self.tray.setText)

        Task.id += 1

    def stop(self, stop_time=None):
        if stop_time is None:
            stop_time = time.time()
        self.value += stop_time - self.start_time
        self.button.setChecked(False)
        self.tray.setChecked(False)
        self.button.setText("Continue")
        self.active = False

    def start(self):
        self.start_time = time.time()
        self.button.setChecked(True)
        self.tray.setChecked(True)
        self.button.setText("Stop")
        self.active = True

    def correct_time(self):
        value, ok = QtGui.QInputDialog.getInt(None, "Correct Time", "Add/substract time in minutes to '%s'" % self.label.text())
        if ok:
            self.value += value*60
            self.update()

    def update(self):
        value = self.get_value()
        self.time.setText("%d:%02d" % (value/3600, (value/60) % 60))

    def get_value(self):
        if self.active:
            value = self.value + time.time() - self.start_time
        else:
            value = self.value
        return value


class Mainwindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)

        self.ui = uic.loadUi(os.path.join(ROOT, 'main.ui'), self)
        self.ui.show()

        self.exit = False
        self.inactive_icon = QtGui.QIcon(os.path.join(ROOT, 'icon.png'))
        self.active_icon = QtGui.QIcon(os.path.join(ROOT, 'icon_green.png'))

        self.sys_tray_icon = QtGui.QSystemTrayIcon(self)
        self.sys_tray_icon.setIcon(self.inactive_icon)
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

        self.tasks = {}

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update)
        self.update_timer.start(1000)

        self.add()

    def update(self):
        sum = 0
        for task in self.tasks.values():
            task.update()
            sum += task.get_value()

        self.status.setText("total: %d:%02d" % (sum/3600, (sum/60) % 60))

	active_task = None
        for t in self.tasks.values():
            if t.active:
                active_task = t
                break

        if active_task:
            self.sys_tray_icon.setIcon(self.active_icon)

            if actmon.get_idle_time() >= 15*60*1000:
                inactive_start_time = time.time() - 15*60
                value = QtGui.QMessageBox.question(self, "No Activity", "No activity since %s. Stop '%s'?" %
                    (time.strftime("%H:%M", time.localtime(inactive_start_time)), active_task.label.text()), "Yes", "No")
                if value == 0:
                    active_task.stop(inactive_start_time)
        else:
            self.sys_tray_icon.setIcon(self.inactive_icon)

    def add(self):
        row = self.ui.main.layout().rowCount()

        task = Task(self)
        id = task.id

        task.button.clicked.connect(lambda: self.toggle_state(id))
        task.tray.triggered.connect(lambda: self.toggle_state(id))
        self.tasks[id] = task

        self.ui.main.layout().addWidget(task.label, row, 0)
        self.ui.main.layout().addWidget(task.time, row, 1)
        self.ui.main.layout().addWidget(task.button, row, 2)
        self.sys_tray_menu.addAction(task.tray)

        self.update()

    def toggle_state(self, id):
        task = self.tasks[id]

        if task.active:
            task.stop()
        else:
            for t in self.tasks.values():
                if t.active:
                    t.stop()
            task.start()

        self.update()

    def exit_action(self):
        self.exit = True
        self.close()

    def closeEvent(self, ev):
        if self.exit is False:
            ev.ignore()
            self.hide()

    def tray_action(self, reason):
        if reason == QtGui.QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.setGeometry(self.geometry())
                self.show()


def main():
    app = QtGui.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(os.path.join(ROOT, 'icon.png')))
    Mainwindow()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
