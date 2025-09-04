"""
Musical Bubble Column!
"""
import matplotlib
matplotlib.use('Qt5Agg')
import pygame
import os.path as os_path
import pygame.midi
from PyQt5.QtWidgets import QApplication
import sys
from PyQt5 import QtCore
from MBC_UI_widgets import *
import MBC_app_widgets
import MBC_Core


if __name__ == "__main__":
    pygame.init()
    pygame.midi.init()

    # Print available MIDI devices
    print("\nAvailable MIDI devices:")
    for i in range(pygame.midi.get_count()):
        device_info = pygame.midi.get_device_info(i)
        name, is_input, is_output, opened = device_info[1].decode(), device_info[2], device_info[3], device_info[4]
        device_type = "Input" if is_input else "Output"
        print(f"Device ID: {i}, Name: {name}, Type: {device_type}, Is Open: {opened}")
    print()  # Empty line for better readability

    app = QApplication(sys.argv)  # 在主线程中创建 QApplication 实例
    visualizer = MBC_Core.PatternVisualizer3D(orientation="up", pos_type="Fibonacci", visualize_piano=True)# Fibonacci circle arc
    loading_msg_manager = LoadingMessageManager()
    loading_msg_manager.initialize(app)
    loading_msg_manager.show()
    loading_manager = loading_msg_manager.get_loading_manager()
    loading_manager.smooth_transition(0, 50, duration=0.5)
    MBC_Core.init_njit_func(visualizer)  # 初始化
    loading_manager.smooth_transition(50, 100, duration=0.5)
    QApplication.processEvents()  # 确保界面更新
    
    dialog_manager = FileDialogManager(visualizer)
    visualizer.working = True  # 初始化工作状态
    
    # 创建定时器显示文件对话框
    dialog_timer = QtCore.QTimer()
    dialog_timer.setSingleShot(True)
    dialog_timer.timeout.connect(dialog_manager.show_dialog)
    dialog_timer.start(100)  # 100ms后显示对话框
    
    # 在主线程中运行可视化
    while True:  
        if dialog_manager.should_switch_music:
            dialog_manager.should_switch_music = False
            visualizer.working = True
            dialog_manager.close_dialog()
        
        if os_path.exists(dialog_manager.current_midi_path) and visualizer.working:
            while not loading_manager.fully_complete:
                QApplication.processEvents()
            # Create and use MidiVisualizer instance
            midi_visualizer = MBC_app_widgets.MidiVisualizer(visualizer)
            midi_visualizer.visualize(dialog_manager.current_midi_path)
            dialog_manager.show_dialog()
        
        if not visualizer.working and dialog_manager.user_cancelled:
            break
        
        QApplication.processEvents()
