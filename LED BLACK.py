import sys #https://github.com/dedKRV/Color-Music-on-Python-and-Arduino-WS2812B-ESP32
import json
import numpy as np
import sounddevice as sd
from scipy.fftpack import fft
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSlider,
                             QLabel, QHBoxLayout, QCheckBox, QPushButton,
                             QGroupBox, QRadioButton, QColorDialog, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPalette, QFont
import serial
import time
import os

os.environ["QT_FATAL_CRASHES"] = "1"

SAMPLE_RATE = 44100
FFT_SIZE = 1024
MIN_LEVEL = 0.01


class AudioThread(QThread):
    data_updated = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.running = False

    def run(self):
        self.running = True
        try:
            with sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype='float32',
                    callback=self.audio_callback
            ) as stream:
                while self.running:
                    sd.sleep(100)
        except Exception as e:
            print(f"AUDIO ERROR: {str(e)}")

    def audio_callback(self, indata, frames, time, status):
        if self.running and not status:
            fft_data = np.abs(fft(indata[:, 0] * np.hamming(len(indata)), n=FFT_SIZE))
            self.data_updated.emit(fft_data)

    def stop(self):
        self.running = False


class LEDControl(QWidget):
    def __init__(self):
        super().__init__()
        self.ser = None
        self.audio_thread = AudioThread()
        self.default_config = {
            'mode': 0,
            'base_color': (50, 0, 100),  # Фиолетовый по умолчанию
            'low_color': (255, 0, 100),  # Розово-фиолетовый
            'high_color': (100, 0, 255),  # Сине-фиолетовый
            'low_cutoff': 60,
            'high_cutoff': 80,
            'threshold': 0.1
        }
        self.config = self.default_config.copy()

        self.init_ui()
        self.connect_serial()
        self.load_config()
        self.apply_dark_theme()

    def apply_dark_theme(self):
        # Применяем темную тему с фиолетовыми акцентами
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(30, 30, 40))
        dark_palette.setColor(QPalette.WindowText, QColor(220, 220, 255))
        dark_palette.setColor(QPalette.Base, QColor(40, 40, 50))
        dark_palette.setColor(QPalette.AlternateBase, QColor(50, 50, 60))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(100, 50, 150))
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, QColor(220, 220, 255))
        dark_palette.setColor(QPalette.Button, QColor(60, 40, 80))
        dark_palette.setColor(QPalette.ButtonText, QColor(220, 220, 255))
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Highlight, QColor(120, 50, 180))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)

        self.setPalette(dark_palette)

        # Устанавливаем стиль для групп
        group_style = """
        QGroupBox {
            font-weight: bold;
            border: 2px solid #6A0DAD;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 10px;
            background-color: #2A2A3A;
            color: #DCDCF0;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #B19CD9;
        }
        """

        self.setStyleSheet(f"""
            QWidget {{
                background-color: #1E1E2E;
                color: #DCDCF0;
                font-family: 'Segoe UI';
            }}
            QPushButton {{
                background-color: #4A2C7A;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #6A3C9A;
            }}
            QPushButton:pressed {{
                background-color: #8A5CBA;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid #4A2C7A;
                height: 8px;
                background: #2A2A3A;
                margin: 2px 0;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: #8A2BE2;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }}
            QSlider::sub-page:horizontal {{
                background: #6A0DAD;
                border-radius: 4px;
            }}
            QCheckBox {{
                spacing: 5px;
                color: #DCDCF0;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid #6A0DAD;
                border-radius: 3px;
                background: #2A2A3A;
            }}
            QCheckBox::indicator:checked {{
                background: #8A2BE2;
            }}
            QRadioButton {{
                spacing: 5px;
                color: #DCDCF0;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid #6A0DAD;
                border-radius: 9px;
                background: #2A2A3A;
            }}
            QRadioButton::indicator:checked {{
                background: #8A2BE2;
                border: 2px solid #8A2BE2;
            }}
            {group_style}
        """)

    def init_ui(self):
        self.setWindowTitle('LED Music Controller - Dark Theme')
        self.setGeometry(300, 300, 700, 600)

        # Режимы работы
        self.mode_group = QGroupBox("Режимы работы")
        self.mode1 = QRadioButton("Фоновый режим")
        self.mode2 = QRadioButton("Один диапазон")
        self.mode3 = QRadioButton("Два диапазона")
        self.mode1.setChecked(True)

        layout_modes = QHBoxLayout()
        layout_modes.addWidget(self.mode1)
        layout_modes.addWidget(self.mode2)
        layout_modes.addWidget(self.mode3)
        self.mode_group.setLayout(layout_modes)

        # Цветовые кнопки
        self.base_color_btn = QPushButton('Фоновый цвет')
        self.low_color_btn = QPushButton('Низкие частоты')
        self.high_color_btn = QPushButton('Высокие частоты')

        # Настройка цветов
        self.base_color_btn.clicked.connect(lambda: self.choose_color('base'))
        self.low_color_btn.clicked.connect(lambda: self.choose_color('low'))
        self.high_color_btn.clicked.connect(lambda: self.choose_color('high'))

        # Частотные диапазоны
        self.low_cutoff = self.create_slider(40, 60, 'Низкие частоты (Гц):', 60)
        self.high_cutoff = self.create_slider(60, 80, 'Высокие частоты (Гц):', 70)
        self.threshold = self.create_slider(1, 100, 'Порог срабатывания (%):', 10)

        # Управление
        self.audio_toggle = QCheckBox('Включить аудио реакцию')
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(50)
        self.color_preview.setStyleSheet("border: 2px solid #6A0DAD; border-radius: 5px;")
        self.update_preview()

        # Компоновка
        layout = QVBoxLayout()
        layout.addWidget(self.mode_group)
        layout.addWidget(self.create_color_group())
        layout.addWidget(self.create_freq_group())
        layout.addWidget(self.audio_toggle)
        layout.addWidget(self.color_preview)
        layout.addStretch()

        self.setLayout(layout)

        self.audio_thread.data_updated.connect(self.process_audio)
        self.audio_toggle.stateChanged.connect(self.toggle_audio)
        self.mode1.toggled.connect(lambda: self.set_mode(0))
        self.mode2.toggled.connect(lambda: self.set_mode(1))
        self.mode3.toggled.connect(lambda: self.set_mode(2))

        # Инициализация цветов кнопок
        self.update_color_buttons()

    def create_color_group(self):
        group = QGroupBox("Настройки цвета")
        layout = QVBoxLayout()
        layout.addWidget(self.base_color_btn)
        layout.addWidget(self.low_color_btn)
        layout.addWidget(self.high_color_btn)
        group.setLayout(layout)
        return group

    def create_freq_group(self):
        group = QGroupBox("Настройки частот")
        layout = QVBoxLayout()
        layout.addWidget(self.low_cutoff)
        layout.addWidget(self.high_cutoff)
        layout.addWidget(self.threshold)
        group.setLayout(layout)
        return group

    def create_slider(self, min_val, max_val, label, init_val):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        label_widget = QLabel(label)
        label_widget.setMinimumWidth(200)
        label_widget.setStyleSheet("color: #DCDCF0;")

        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(init_val)
        slider.valueChanged.connect(self.update_config)

        value_label = QLabel(str(init_val))
        value_label.setMinimumWidth(30)
        value_label.setStyleSheet("color: #B19CD9; font-weight: bold;")
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        slider.valueChanged.connect(lambda val: value_label.setText(str(val)))

        layout.addWidget(label_widget)
        layout.addWidget(slider)
        layout.addWidget(value_label)

        container.slider = slider
        container.value_label = value_label
        return container

    def connect_serial(self):
        try:
            self.ser = serial.Serial('COM3', 115200, timeout=2)
            time.sleep(2)
            print("Serial connection established")
        except Exception as e:
            print(f"SERIAL ERROR: {str(e)}")

    def set_mode(self, mode):
        self.config['mode'] = mode
        self.send_full_update()

    def update_color_buttons(self):
        base_r, base_g, base_b = self.config['base_color']
        low_r, low_g, low_b = self.config['low_color']
        high_r, high_g, high_b = self.config['high_color']

        self.base_color_btn.setStyleSheet(
            f"background-color: rgb({base_r}, {base_g}, {base_b}); color: white;")
        self.low_color_btn.setStyleSheet(
            f"background-color: rgb({low_r}, {low_g}, {low_b}); color: white;")
        self.high_color_btn.setStyleSheet(
            f"background-color: rgb({high_r}, {high_g}, {high_b}); color: white;")

        self.update_preview()

    def update_preview(self):
        base_r, base_g, base_b = self.config['base_color']
        self.color_preview.setStyleSheet(
            f"background-color: rgb({base_r}, {base_g}, {base_b}); "
            f"border: 2px solid #6A0DAD; border-radius: 5px;"
        )

    def choose_color(self, color_type):
        color = QColorDialog.getColor()
        if color.isValid():
            rgb = (color.red(), color.green(), color.blue())
            if color_type == 'base':
                self.config['base_color'] = rgb
            elif color_type == 'low':
                self.config['low_color'] = rgb
            elif color_type == 'high':
                self.config['high_color'] = rgb
            self.update_color_buttons()
            self.send_full_update()

    def update_config(self):
        self.config['low_cutoff'] = self.low_cutoff.slider.value()
        self.config['high_cutoff'] = self.high_cutoff.slider.value()
        self.config['threshold'] = self.threshold.slider.value() / 100
        self.send_full_update()

    def process_audio(self, fft_data):
        try:
            freqs = np.fft.fftfreq(FFT_SIZE, 1 / SAMPLE_RATE)

            low_level = 0.0
            high_level = 0.0

            if self.config['mode'] > 0:
                # Низкие частоты
                low_mask = (freqs > 20) & (freqs < self.config['low_cutoff'])
                low_level = np.mean(fft_data[low_mask]) / 100

                # Высокие частоты (только для режима 2)
                if self.config['mode'] == 2:
                    high_mask = (freqs > self.config['high_cutoff']) & (freqs < 100)
                    high_level = np.mean(fft_data[high_mask]) / 100

            self.send_to_leds(low_level, high_level)

        except Exception as e:
            print(f"AUDIO PROCESS ERROR: {str(e)}")

    def send_to_leds(self, low_level, high_level):
        if self.ser and self.ser.is_open:
            try:
                # Принудительная отправка фонового цвета при отсутствии сигнала
                if low_level < MIN_LEVEL and high_level < MIN_LEVEL:
                    command = f"B{self.config['base_color'][0]},{self.config['base_color'][1]},{self.config['base_color'][2]}\n"
                else:
                    command = (
                        f"M{self.config['mode']};"
                        f"B{self.config['base_color'][0]},{self.config['base_color'][1]},{self.config['base_color'][2]};"
                        f"L{self.config['low_color'][0]},{self.config['low_color'][1]},{self.config['low_color'][2]},{low_level};"
                        f"H{self.config['high_color'][0]},{self.config['high_color'][1]},{self.config['high_color'][2]},{high_level};"
                        f"T{self.config['threshold']}\n"
                    )
                self.ser.write(command.encode())
            except Exception as e:
                print(f"SERIAL WRITE ERROR: {str(e)}")

    def send_full_update(self):
        self.send_to_leds(0, 0)  # Принудительное обновление всех параметров

    def toggle_audio(self, state):
        if state == Qt.Checked:
            self.audio_thread.start()
        else:
            self.audio_thread.stop()
            self.send_full_update()

    def load_config(self):
        try:
            with open('config.json', 'r') as f:
                loaded_config = json.load(f)
                self.config.update(loaded_config)

            # Применяем настройки интерфейса
            self.low_cutoff.slider.setValue(self.config['low_cutoff'])
            self.high_cutoff.slider.setValue(self.config['high_cutoff'])
            self.threshold.slider.setValue(int(self.config['threshold'] * 100))
            self.update_color_buttons()

            # Устанавливаем режим
            if self.config['mode'] == 0:
                self.mode1.setChecked(True)
            elif self.config['mode'] == 1:
                self.mode2.setChecked(True)
            elif self.config['mode'] == 2:
                self.mode3.setChecked(True)

        except FileNotFoundError:
            print("Config file not found, using default settings")
        except Exception as e:
            print(f"CONFIG LOAD ERROR: {str(e)}")

    def save_config(self):
        try:
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"CONFIG SAVE ERROR: {str(e)}")

    def closeEvent(self, event):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.audio_thread.stop()
        self.save_config()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Используем Fusion стиль для лучшего отображения темной темы

    # Устанавливаем иконку приложения
    app.setApplicationName("LED Music Controller")

    window = LEDControl()
    window.show()

    sys.exit(app.exec_())
