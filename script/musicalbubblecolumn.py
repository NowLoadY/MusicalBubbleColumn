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
import os.path as os_path
import pygame.midi
from PyQt5.QtWidgets import QApplication
import sys
from PyQt5 import QtCore
from MBC_UI_widgets import *
import MBC_Core
import time


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
    
    midi_thread = threading.Thread(target=process_midi)
    midi_thread.start()

    last_time = time.time()
    fps = 0
    
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
        current_time = time.time()
        fps = int(1 / (current_time - last_time))
        print(f"FPS: {fps}")
        last_time = current_time

    midi_thread.join()
    pygame.mixer.music.stop()

if __name__ == "__main__":
    pygame.init()
    pygame.midi.init()
    app = QApplication(sys.argv)  # 在主线程中创建 QApplication 实例
    visualizer = MBC_Core.PatternVisualizer3D(orientation="up", pos_type="Fibonacci")  # Fibonacci
    loading_msg_manager = LoadingMessageManager()
    loading_msg_manager.initialize(app)
    loading_msg_manager.show()
    loading_manager = loading_msg_manager.get_loading_manager()
    loading_manager.smooth_transition(0, 50, duration=0.5)
    MBC_Core.init_njit_func(visualizer, bytes(15), [1] * 120, 0)  # 初始化
    loading_manager.smooth_transition(50, 100, duration=0.5)
    QApplication.processEvents()  # 确保界面更新
    
    dialog_manager = FileDialogManager(visualizer)
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