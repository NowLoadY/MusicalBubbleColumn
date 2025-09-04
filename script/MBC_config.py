import os.path as os_path
base_path = os_path.dirname(os_path.abspath(__file__))
PATH_TO_ICON = os_path.join(base_path, "rounded_icon.png")
DEFAULT_MIDI_PATH = os_path.join(base_path, "City_Of_Stars.mid")
WAV_FILE_PATH = os_path.join(base_path, "City_Of_Stars_vocal.wav")
# 主题颜色
fig_themes_rgba = [
    (0., 0., 60/255, 1.),           # 深蓝
    (0., 0., 0., 1.),               # 黑色
    (1., 1., 1., 1.),               # 白色
    (47/255, 0., 80/255, 1.),       # 深紫
    (0., 0., 60/255, 1.),           # 深蓝
]
data_themes_rgb = [
    (229/255, 248/255, 1.),         # 亮蓝
    (1., 1., 1.),                   # 白色
    (0., 0., 0.),                   # 黑色
    (255/255, 192/255, 203/255),    # 粉色
    (255/255, 192/255, 203/255),    # 粉色
]
data_height_3d = 400
