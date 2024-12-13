from PyQt5.QtWidgets import QProgressDialog, QGraphicsDropShadowEffect, QProgressBar, QGraphicsBlurEffect
from PyQt5.QtGui import QColor, QPainter
from PyQt5 import QtCore
from PyQt5 import QtGui
import os.path as os_path
import time
base_path = os_path.dirname(os_path.abspath(__file__))
PATH_TO_ICON = os_path.join(base_path, "icon.png")


class RoundedProgressDialog(QProgressDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setValue(0)  # 设置初始进度值为 0
        self.setBar(ShadowProgressBar())  # 使用自定义的进度条

        # 添加窗口阴影效果
        self._add_shadow_effect()

    def _add_shadow_effect(self):
        """
        为整个对话框窗口添加阴影效果。
        """
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(10)  # 增加模糊半径以获得柔和阴影
        shadow_effect.setColor(QColor(0, 0, 0, 80))  # 使用透明的黑色阴影
        shadow_effect.setOffset(5, 5)  # 设置阴影的偏移量
        self.setGraphicsEffect(shadow_effect)

    def paintEvent(self, event):
        """
        自定义窗口绘制事件，用于绘制圆角背景和图标。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 启用抗锯齿

        # 绘制圆角背景
        self._draw_rounded_background(painter)

        # 绘制图标带阴影
        self._draw_icon_with_shadow(painter)

    def _draw_rounded_background(self, painter):
        """
        绘制圆角背景。
        """
        background_rect = QtCore.QRectF(self.rect()).adjusted(10, 10, -10, -10)  # 考虑阴影边距
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))  # 设置背景颜色为白色
        painter.setPen(QtCore.Qt.NoPen)  # 不绘制边框
        painter.drawRoundedRect(background_rect, 30, 30)  # 绘制圆角矩形

    def _draw_icon_with_shadow(self, painter):
        """
        绘制带圆角和模糊阴影效果的图标。
        """
        # 加载图标
        icon_pixmap = QtGui.QPixmap(PATH_TO_ICON)

        # 计算缩放后的图标大小
        icon_size = min(self.height(), self.width()) // 3
        scaled_icon = icon_pixmap.scaled(icon_size, icon_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        icon_x = self.width() // 5  # 图标 x 坐标
        icon_y = 20  # 图标 y 坐标
        shadow_offset = 3
        corner_radius = 3  # 阴影圆角半径
        shadow_color = QtGui.QColor(0, 0, 0, 60)  # 半透明黑色阴影

        # 创建阴影的圆角矩形路径
        shadow_path = QtGui.QPainterPath()
        shadow_path.addRoundedRect(icon_x + shadow_offset, icon_y + shadow_offset,
                                scaled_icon.width(), scaled_icon.height(),
                                corner_radius, corner_radius)

        # 启用模糊效果
        shadow_blur_effect = QGraphicsBlurEffect()
        shadow_blur_effect.setBlurRadius(10)

        # 绘制模糊阴影
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(shadow_color))
        painter.drawPath(shadow_path)
        painter.restore()

        # 绘制图标
        painter.drawPixmap(icon_x, icon_y, scaled_icon)

    def setSmoothValue(self, value, callback=None):
        """
        平滑过渡到目标值，并在结束后执行回调。
        :param value: 目标进度值
        :param callback: 动画结束后的回调函数
        """
        animation = QtCore.QPropertyAnimation(self, b"value")  # 绑定到进度条的值属性
        animation.setDuration(1000)  # 动画持续时间（毫秒）
        animation.setStartValue(self.value())
        animation.setEndValue(value)
        animation.finished.connect(lambda: callback() if callback else None)
        animation.start()


class ShadowProgressBar(QProgressBar):
    def __init__(self):
        super().__init__()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        # 绘制背景
        painter.setBrush(QColor(102, 204, 255))  # 背景颜色
        painter.setPen(QtCore.Qt.NoPen)
        rect = rect.adjusted(10, 0, -10, 0)
        painter.drawRoundedRect(rect, 10, 10)  # 圆角背景

        # 绘制进度条和阴影（计算出进度条的填充区域）
        chunk_rect = rect.adjusted(0, 0, int(-rect.width() * (1 - self.value() / self.maximum())), 0)
        # 先绘制阴影
        shadow_rect = chunk_rect.adjusted(1, 0, 3, 0)  # 设置阴影位置
        painter.setBrush(QColor(0, 0, 0, 30))  # 半透明黑色阴影
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, 10, 10)  # 圆角阴影
        # 然后绘制进度条
        painter.setBrush(QColor(0, 120, 215))  # 进度条颜色
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(chunk_rect, 10, 10)  # 圆角进度条

        painter.end()

class LoadingManager():
    def __init__(self, loading_msg):
        super().__init__()
        self.loading_msg = loading_msg
        self.fully_complete = False

    def set_complete(self):
        self.fully_complete = True
        self.loading_msg.close()

    def smooth_transition(self, start_value, end_value, duration=1):
        step_count = int(duration * 30)  # Smooth steps per second (30fps)
        step_size = (end_value - start_value) / step_count
        
        for i in range(step_count):
            current_value = max(min(start_value + step_size * (i + 1), 100), 0)
            self.loading_msg.setValue(int(current_value))
            time.sleep(duration / step_count)  # Sleep to control transition speed
        if self.loading_msg.value()<0:
            self.set_complete()