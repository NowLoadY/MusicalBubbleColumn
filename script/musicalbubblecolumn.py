"""
Musical Bubble Column!
"""
import matplotlib
matplotlib.use('Qt5Agg')
import numpy as np
from mido import MidiFile
import pygame
import threading
from collections import deque
from PyQt5 import QtGui
import os.path as os_path
import pygame.midi
from PyQt5.QtWidgets import QApplication, QFileDialog
import sys
from PyQt5 import QtCore
from MBC_UI_widgets import *
import MBC_Core
import time
base_path = os_path.dirname(os_path.abspath(__file__))
PATH_TO_ICON = os_path.join(base_path, "icon.png")
DEFAULT_MIDI_PATH = os_path.join(base_path, "Blade_Runner_2049_Main_Theme.mid")


def action_midi_visualization(visualizer, midi_path):
    temp_midi_path = "temp_midi_file.mid"  # 定义临时MIDI文件路径

    midi = MidiFile(midi_path)
    for track in midi.tracks:
        for msg in track:
            if msg.type == 'program_change':
                msg.program = 0  # 将音色更改为钢琴音色
    midi.save(temp_midi_path)

    pygame.mixer.init()
    pygame.mixer.music.load(temp_midi_path)
    pygame.mixer.music.play()
    min_note, max_note = 127, 0
    total_volumes = deque(maxlen=480)
    for track in midi.tracks:
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                min_note, max_note = min(min_note, msg.note), max(max_note, msg.note)

    def map_note_to_range(note):
        note_array = np.clip((note - min_note) / (max_note - min_note) * 120, 0, 119)
        return int(note_array)
    
    num_keys = 120
    volumes = [0] * num_keys
    average_volume = 0
    key_activation = np.zeros(num_keys, dtype=int)
    midi_iterator = iter(midi.play())
    new_pattern = bytes(15)
    zero_pattern_interval = 2
    update_count = 0
    process_midi_thread_bool=True
    
    def process_midi():
        nonlocal new_pattern, update_count, volumes, process_midi_thread_bool
        for msg in midi_iterator:
            if msg.type in ['note_on']:
                mapped_note = map_note_to_range(msg.note)
                if 0 <= mapped_note < num_keys:
                    key_activation[mapped_note] = 1 if (msg.type == 'note_on' and msg.velocity > 0) else 0
                    volumes[mapped_note] = msg.velocity if msg.type == 'note_on' else 0
                    total_volumes.append(msg.velocity)

                new_pattern = np.packbits(key_activation).tobytes()
                update_count = 0
            
            if not pygame.mixer.music.get_busy() or not process_midi_thread_bool:
                break
    
    #visualizer._initialize_data()
    midi_thread = threading.Thread(target=process_midi)
    midi_thread.start()

    #last_time = time.time()
    #fps = 0
    
    while True:
        visualizer.working = True
        if total_volumes:
            average_volume = sum(total_volumes) / len(total_volumes)
        if update_count % zero_pattern_interval == 0:
            new_pattern = bytes(15)
            one_volumes = [1] * 120
            visualizer.update_pattern(new_pattern, one_volumes, average_volume)
        else:
            visualizer.update_pattern(new_pattern, volumes, average_volume)
        update_count += 1
        
        if not pygame.mixer.music.get_busy() and np.sum(visualizer.pattern_data) == 0:
            visualizer.working = False
            break  # 如果 MIDI 播放完且数据已清空，则退出
        visualizer.update_view_angle()
        if not visualizer.working:
            process_midi_thread_bool=False
            break

        # 计算FPS
        #current_time = time.time()
        #fps = int(1 / (current_time - last_time))
        #print(f"FPS: {fps}")
        #last_time = current_time

    midi_thread.join()
    pygame.mixer.music.stop()

def choose_midi_file(app):
    # 设置全局样式表
    app.setStyleSheet("""
        QFileDialog {
            background-color: #ffffff;
            color: #000000;
            border-radius: 15px;
        }
        QPushButton {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #000000;
            padding: 5px;
            border-radius: 10px;
        }
        QPushButton:hover {
            background-color: #f0f0f0;
        }
        QLineEdit {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #000000;
            border-radius: 10px;
        }
        QLabel {
            color: #000000;
        }
    """)
# 
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog  # 使用非原生对话框
    options |= QFileDialog.HideNameFilterDetails  # 隐藏文件类型过滤器的详细信息
    dialog = QFileDialog(None, "选择MIDI文件", "", "MIDI files (*.mid *.midi);;All files (*.*)", options=options)
    dialog.setFileMode(QFileDialog.ExistingFile)  # 只允许选择现有文件
    dialog.setViewMode(QFileDialog.List)
    dialog.resize(1200, 1200)  # 设置默认窗口大小
    dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)  # 设置窗口置顶
    if dialog.exec_() == QFileDialog.Accepted:
        midi_file_path = dialog.selectedFiles()[0]
    else:
        midi_file_path = None
    return midi_file_path


class FileDialogManager:
    def __init__(self):
        self.current_midi_path = DEFAULT_MIDI_PATH
        self.file_dialog = None
        self.visualizer = visualizer
        self.should_switch_music = False
        self.user_cancelled = False
    
    def create_file_dialog(self):
        self.file_dialog = QFileDialog(None, "选择MIDI文件", "", "MIDI files (*.mid *.midi);;All files (*.*)")
        self.file_dialog.setFileMode(QFileDialog.ExistingFile)
        self.file_dialog.setViewMode(QFileDialog.List)
        self.file_dialog.resize(800, 800)  # 调整对话框大小
        self.file_dialog.setWindowFlags(self.file_dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        
        # 设置对话框位置在屏幕左侧
        screen = QApplication.primaryScreen().geometry()
        dialog_x = screen.x() + 50  # 距离左边界50像素
        dialog_y = (screen.height() - self.file_dialog.height()) // 2  # 垂直居中
        self.file_dialog.move(dialog_x, dialog_y)
        
        def on_file_selected(result):
            if result == QFileDialog.Accepted and self.file_dialog.selectedFiles():
                new_path = self.file_dialog.selectedFiles()[0]
                if new_path:
                    self.current_midi_path = new_path
                    self.should_switch_music = True
                    self.visualizer.working = False
                    self.file_dialog.close()  # 选择文件后自动关闭对话框
            else:
                self.user_cancelled = True
                if not self.visualizer.working:  # 只有在可视化已经停止时才结束程序
                    self.should_switch_music = False
        
        self.file_dialog.finished.connect(on_file_selected)
        self.user_cancelled = False  # 重置取消标志
        return self.file_dialog
    
    def show_dialog(self):
        if self.file_dialog is None or not self.file_dialog.isVisible():
            self.create_file_dialog().show()
    
    def close_dialog(self):
        if self.file_dialog and self.file_dialog.isVisible():
            self.file_dialog.close()


if __name__ == "__main__":
    pygame.init()
    pygame.midi.init()
    app = QApplication(sys.argv)  # 在主线程中创建 QApplication 实例
    visualizer = MBC_Core.PatternVisualizer3D(visualize_piano=True, orientation="up", pos_type="Fibonacci")  # Fibonacci
    loading_msg = RoundedProgressDialog("Musical Bubble Column!\n正在预编译...", None, 0, 0)  # 使用自定义的带圆角的进度对话框
    loading_msg.setWindowTitle("Musical Bubble Column!")
    loading_msg.setCancelButton(None)  # 不显示取消按钮
    loading_msg.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)  # 设置无边框和置顶
    loading_msg.setAttribute(QtCore.Qt.WA_TranslucentBackground)  # 允许背景透明
    loading_msg.setMinimumSize(600, 150)  # 设置最小大小

    loading_msg.setWindowIcon(QtGui.QIcon(PATH_TO_ICON))  # 使用相对路径设置图标
    loading_msg.show()  # 显示提示框
    
    screen_geometry = app.primaryScreen().geometry()
    loading_msg.move(
        screen_geometry.x() + (screen_geometry.width() - loading_msg.width()) // 2,
        (screen_geometry.y() + screen_geometry.height()) // 8
    )
    QApplication.processEvents()
    loading_manager = LoadingManager(loading_msg)
    loading_manager.smooth_transition(0, 50, duration=0.5)
    MBC_Core.init_njit_func(visualizer, bytes(15), [1] * 120, 0)  # 初始化
    loading_manager.smooth_transition(50, 100, duration=0.5)
    QApplication.processEvents()  # 确保界面更新
    
    dialog_manager = FileDialogManager()
    visualizer.working = True  # 初始化工作状态
    
    # 创建定时器来显示文件对话框
    dialog_timer = QtCore.QTimer()
    dialog_timer.setSingleShot(True)
    dialog_timer.timeout.connect(dialog_manager.show_dialog)
    dialog_timer.start(100)  # 100ms后显示对话框
    
    # 在主线程中运行可视化
    while True:
        if dialog_manager.should_switch_music:
            # 重置标志
            dialog_manager.should_switch_music = False
            # 重新启动可视化
            visualizer.working = True
            # 确保文件选择对话框已关闭
            dialog_manager.close_dialog()
        
        if os_path.exists(dialog_manager.current_midi_path) and visualizer.working:
            # 等待加载完成
            while not loading_manager.fully_complete:
                QApplication.processEvents()
            # 在主线程中执行可视化
            action_midi_visualization(visualizer, dialog_manager.current_midi_path)
            # 可视化结束后（音乐播放完或用户关闭窗口），显示文件选择对话框
            dialog_manager.show_dialog()
        
        # 只有在可视化停止且用户取消文件选择时才退出程序
        if not visualizer.working and dialog_manager.user_cancelled:
            break
        
        QApplication.processEvents()
