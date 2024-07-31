# -*- coding: utf-8 -*-
import sys
import os
import re
import asyncio
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QComboBox,
    QHBoxLayout,
    QSlider,
    QFileDialog,  # 新增：导入QFileDialog用于文件选择
)
from PyQt5.QtCore import pyqtSlot, QThread, pyqtSignal, Qt, QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import edge_tts
import subprocess
from PyQt5.QtGui import QFont
import lameenc
from PyQt5.QtCore import QTimer

# 获取用户的桌面路径
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
# 生成完整的文件路径
OUTPUT_FILE = os.path.join(desktop_path, "output.mp3")

DEFAULT_VOICE = {
    "云扬": "zh-CN-YunyangNeural",
    "晓晓": "zh-CN-XiaoxiaoNeural",
    "晓伊": "zh-CN-XiaoyiNeural",
    "云健": "zh-CN-YunjianNeural",
    "云希": "zh-CN-YunxiNeural",
    "云夏": "zh-CN-YunxiaNeural",
}

MAX_SEGMENT_LENGTH = 1000  # 设置每个文本段的最大长度


async def process_segment(segment, voice):
    if re.match(r"\{pause=\d+\}", segment):
        return b""  # 或者根据需要返回空字节，或者删除这个分支
    else:
        communicate = edge_tts.Communicate(segment, voice)
        segment_audio = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                segment_audio += chunk["data"]
        return segment_audio


async def run_tts(text, voice, finished_callback):
    # 将文本分段，每段不超过 MAX_SEGMENT_LENGTH 字符
    segments = [text[i : i + MAX_SEGMENT_LENGTH] for i in range(0, len(text), MAX_SEGMENT_LENGTH)]
    combined_audio = b""
    try:
        for segment in segments:
            if segment.strip():  # 处理非空段落
                segment_audio = await process_segment(segment, voice)
                combined_audio += segment_audio
        with open(OUTPUT_FILE, "wb") as f:
            f.write(combined_audio)
    except Exception as e:
        finished_callback(f"出现意外错误：{e}")
        return
    finished_callback("语音生成完毕！")


def start_background_task(loop, text, voice, finished_callback):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_tts(text, voice, finished_callback))


class TTSWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, text, voice):
        super().__init__()
        self.text = text
        self.voice = voice

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_tts(self.text, self.voice, self.finished.emit))


class TTSApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("文字转语音工具")
        self.setGeometry(300, 300, 1000, 800)
        self.last_pause_insertion_position = -1  # 初始化属性
        self.animation_index = 0  # 初始化动画索引
        self.player = QMediaPlayer()  # 创建音频播放器
        self.setupUI()

    def setupUI(self):
        # 正确创建 QVBoxLayout 实例
        self.layout = QVBoxLayout(self)

        # 设置整体字体
        font = QFont("Arial", 14)
        self.setFont(font)
        self.player.error.connect(self.handle_error)

        # 创建界面元素
        # self.layout = QVBoxLayout(self)
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("请输入文字...")
        self.layout.addWidget(self.text_input)

        self.voice_dropdown = QComboBox()
        # self.voice_dropdown.addItems(DEFAULT_VOICE)
        self.voice_dropdown.addItems(list(DEFAULT_VOICE.keys()))
        self.layout.addWidget(self.voice_dropdown)

        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)

        # 设置按钮样式
        button_style = """
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                font-size: 16px;
                margin: 4px 2px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """
        # 上传按钮
        self.load_button = QPushButton("上传TXT文件", self)  # 新增：按钮用于加载txt文件
        self.load_button.setStyleSheet(button_style)
        self.load_button.clicked.connect(self.load_text_file)  # 新增：连接按钮点击事件到加载函数
        self.button_layout.addWidget(self.load_button)  # 新增：将按钮添加到布局中

        # 生成按钮
        self.generate_button = QPushButton("生成")
        self.generate_button.setStyleSheet(button_style)
        self.generate_button.clicked.connect(self.start_tts)
        self.button_layout.addWidget(self.generate_button)

        # 试听按钮
        self.play_button = QPushButton("试听")
        self.play_button.setStyleSheet(button_style)
        self.play_button.clicked.connect(self.toggleAudioPlay)
        self.button_layout.addWidget(self.play_button)

        # 打开文件位置按钮
        self.open_file_button = QPushButton("打开文件位置")
        self.open_file_button.setStyleSheet(button_style)
        self.open_file_button.clicked.connect(self.open_file_location)
        self.button_layout.addWidget(self.open_file_button)

        # 创建状态标签并添加到布局中
        self.status_label = QLabel("")
        self.layout.addWidget(self.status_label)

        # 初始化进度条并连接到相应的槽函数
        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderPressed.connect(self.slider_pressed)
        self.slider.sliderReleased.connect(self.slider_released)
        self.layout.addWidget(self.slider)

        self.userIsInteracting = False  # 添加一个标志来跟踪用户交互
        self.slider.sliderPressed.connect(lambda: setattr(self, "userIsInteracting", True))
        self.slider.sliderReleased.connect(lambda: setattr(self, "userIsInteracting", False))

        # 创建音频时间标签
        self.start_time_label = QLabel("00:00")
        self.end_time_label = QLabel("00:00")

        # 创建包含时间标签和进度条的水平布局
        self.progress_layout = QHBoxLayout()
        self.progress_layout.addWidget(self.start_time_label)
        self.progress_layout.addWidget(self.slider)
        self.progress_layout.addWidget(self.end_time_label)

        # 将进度条布局添加到垂直布局中
        self.layout.addLayout(self.progress_layout)

        # 初始化定时器
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_status_animation)

        # 连接播放器信号
        self.player.durationChanged.connect(self.duration_changed)
        self.player.positionChanged.connect(self.position_changed)

        self.player.stateChanged.connect(self.handle_play_state_change)

    def handle_error(self):
        self.status_label.setText("播放器错误:" + self.player.errorString())

    def set_position(self, position):
        # 当用户正在拖动滑块时，不要更新播放器的位置
        if not self.userIsInteracting:
            # print(f"设置播放位置: {position}")  # 调试信息
            self.player.setPosition(position)

    def slider_pressed(self):
        self.userIsInteracting = True

    def slider_released(self):
        self.userIsInteracting = False
        # 当用户释放滑块时，根据滑块的位置更新播放位置
        self.set_position(self.slider.value())

    @pyqtSlot(QMediaPlayer.State)
    def handle_play_state_change(self, state):
        if state == QMediaPlayer.PlayingState:
            # 播放中，将试听按钮文本设置为"停止"，禁用其他按钮
            self.play_button.setText("停止")
            self.enableButtons(False)
        else:
            # 非播放状态，将试听按钮文本设置为"试听"，启用其他按钮
            self.play_button.setText("试听")
            self.enableButtons(True)

    @pyqtSlot()
    def playAudio(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_button.setText("试听")
            self.play_button.setProperty("playing", False)
            self.play_button.setStyleSheet(self.play_button_style)
            # 启用其他按钮
            self.enableButtons(True)
        else:
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(OUTPUT_FILE))))
        self.player.play()
        self.play_button.setText("停止")
        self.play_button.setProperty("playing", True)
        self.play_button.setStyleSheet(self.play_button_style)
        # 禁用其他按钮
        self.enableButtons(False)

    @pyqtSlot()
    def toggleAudioPlay(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.stop()  # 停止播放
        else:
            if self.player.mediaStatus() in [QMediaPlayer.NoMedia, QMediaPlayer.LoadedMedia]:
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(OUTPUT_FILE))))
            self.player.play()  # 开始播放

    def enableButtons(self, enable):
        # 启用或禁用其他按钮
        self.generate_button.setEnabled(enable)
        self.open_file_button.setEnabled(enable)

    def position_changed(self, position):
        # 更新当前播放时间
        self.start_time_label.setText(self.format_time(position))
        if not self.userIsInteracting:
            self.slider.blockSignals(True)  # 阻止信号发送，以避免循环调用
            self.slider.setValue(position)
            self.slider.blockSignals(False)  # 重新启用信号

    def duration_changed(self, duration):
        # 更新进度条范围和结束时间
        self.slider.setRange(0, duration)
        self.end_time_label.setText(self.format_time(duration))

    def format_time(self, milliseconds):
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02d}:{seconds:02d}"

    def set_position(self, position):
        # 检查是否是用户交互导致的位置改变
        if not self.userIsInteracting:
            # 直接设置播放器位置并播放
            self.player.setPosition(position)
            if self.player.state() != QMediaPlayer.PlayingState:
                self.player.play()

    def slider_pressed(self):
        self.userIsInteracting = True

    def slider_released(self):
        self.userIsInteracting = False
        self.set_position(self.slider.value())

    def styleDropdown(self, dropdown):
        dropdown.setStyleSheet(
            """
            QComboBox {
                height: 40px;  /* Increase the height */
                border: 1px solid gray;
                border-radius: 5px;
                padding: 1px 18px 1px 3px;  /* Adjust padding for text alignment */
                min-width: 6em;
            }

            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 40px;   /* Match height for a square button */
                border-left-width: 1px;
                border-left-color: darkgray;
                border-left-style: solid; /* just a single line */
                border-top-right-radius: 3px; /* same radius as the QComboBox */
                border-bottom-right-radius: 3px;
            }

            QComboBox::down-arrow {
                image: url(/path/to/your/icon.png);  /* Path to your down-arrow icon */
            }

            QComboBox QAbstractItemView {
                border: 2px solid darkgray;
                selection-background-color: lightgray;
            }
        """
        )

    def load_text_file(self):  # 新增：加载txt文件内容到变量中并展示在输入框内
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Text File",
            os.path.expanduser("~/Desktop"),
            "Text Files (*.txt);;All Files (*)",
            options=options,
        )
        if file_path:
            with open(file_path, "r", encoding="utf-8") as file:
                self.loaded_text = file.read()  # 新增：将文件内容保存到实例变量中
                self.text_input.clear()  # 新增：清除输入框
                self.text_input.setPlainText(self.loaded_text)  # 新增：将文件内容展示在输入框内

    @pyqtSlot()
    def start_tts(self):
        if self.text_input.toPlainText().strip() != "":
            self.loaded_text = None  # 清除 loaded_text 内容

        text = (
            self.loaded_text
            if hasattr(self, "loaded_text") and self.loaded_text
            else self.text_input.toPlainText()
        )  # 修改：使用加载的文本（如果有）或文本编辑框中的文本
        selected_voice_name = self.voice_dropdown.currentText()
        voice_id = DEFAULT_VOICE.get(selected_voice_name)  # 获取语音 ID，如果找不到则使用默认值

        if text.strip() == "":
            self.status_label.setText("请输入一些文本！")
            return

        # 在生成新的语音文件之前，卸载并尝试删除旧文件
        self.unload_and_remove_old_audio()

        # 禁用所有按钮
        self.generate_button.setDisabled(True)
        self.open_file_button.setDisabled(True)
        self.play_button.setDisabled(True)

        # 开始动画
        self.animation_index = 0
        self.animation_timer.start(500)

        self.tts_thread = TTSWorker(text, voice_id)
        self.tts_thread.finished.connect(self.tts_finished)
        self.tts_thread.start()

    def unload_and_remove_old_audio(self):
        # 停止播放器并卸载当前媒体
        self.player.stop()
        self.player.setMedia(QMediaContent())

        # 尝试删除旧的音频文件
        try:
            if os.path.exists(OUTPUT_FILE):
                os.remove(OUTPUT_FILE)
                # print("旧音频文件已删除")
        except Exception as e:
            print(f"删除旧音频文件时出错: {e}")

    def update_status_animation(self):
        animation_states = ["生成中", "生成中.", "生成中..", "生成中..."]
        self.status_label.setText(animation_states[self.animation_index])
        self.animation_index = (self.animation_index + 1) % len(animation_states)

    @pyqtSlot(str)
    def tts_finished(self, message):
        # 停止动画
        self.animation_timer.stop()

        # 启用所有按钮
        self.generate_button.setDisabled(False)
        self.open_file_button.setDisabled(False)
        self.play_button.setDisabled(False)
        self.status_label.setText("语音文件生成完毕")
        # 设置播放器的媒体源为新生成的音频文件
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(OUTPUT_FILE))))
        self.player.durationChanged.emit(self.player.duration())  # 触发 durationChanged 信号以更新时间

    @pyqtSlot()
    def open_file_location(self):
        file_path = os.path.abspath(OUTPUT_FILE)
        folder_path = os.path.dirname(file_path)
        self.status_label.setText(folder_path)
        try:
            if sys.platform.startswith("darwin"):  # macOS
                subprocess.run(["open", folder_path], check=True)
            elif sys.platform.startswith("win32"):  # Windows
                os.startfile(folder_path)
            else:
                # 可以为其他操作系统添加更多选项，或显示不支持的消息
                self.status_label.setText("此操作系统不支持打开文件位置。")
        except Exception as e:
            self.status_label.setText("无法打开文件位置：" + str(e))


# 主函数
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = TTSApp()
    ex.show()
    sys.exit(app.exec_())
