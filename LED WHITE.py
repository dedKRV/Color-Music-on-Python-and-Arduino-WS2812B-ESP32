import sys #https://github.com/dedKRV/Color-Music-on-Python-and-Arduino-WS2812B-ESP32
import json
import numpy as np
import sounddevice as sd
from scipy.fftpack import fft
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSlider,
                             QLabel, QHBoxLayout, QCheckBox, QPushButton,
                             QGroupBox, QRadioButton, QColorDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
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
            'base_color': (0, 0, 0),
            'low_color': (255, 0, 0),
            'high_color': (0, 0, 255),
            'low_cutoff': 60,
            'high_cutoff': 80,
            'threshold': 0.1
        }
        self.config = self.default_config.copy()

        self.init_ui()
        self.connect_serial()
        self.load_config()

    def init_ui(self):
        self.setWindowTitle('LED Music Controller')
        self.setGeometry(300, 300, 600, 500)

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
        self.high_cutoff = self.create_slider(60, 80, 'Высокие частоты (Гц):', 60)
        self.threshold = self.create_slider(1, 100, 'Порог срабатывания (%):', 1)

        # Управление
        self.audio_toggle = QCheckBox('Включить аудио реакцию')
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(50)

        # Компоновка
        layout = QVBoxLayout()
        layout.addWidget(self.mode_group)
        layout.addWidget(self.create_color_group())
        layout.addWidget(self.create_freq_group())
        layout.addWidget(self.audio_toggle)
        layout.addWidget(self.color_preview)

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
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(init_val)
        slider.valueChanged.connect(self.update_config)
        layout.addWidget(QLabel(label))
        layout.addWidget(slider)
        container.slider = slider
        return container

    def connect_serial(self):
        try:
            self.ser = serial.Serial('COM3', 115200, timeout=2)
            time.sleep(2)
        except Exception as e:
            print(f"SERIAL ERROR: {str(e)}")

    def set_mode(self, mode):
        self.config['mode'] = mode
        self.send_full_update()

    def update_color_buttons(self):
        self.base_color_btn.setStyleSheet(
            f"background-color: rgb{self.config['base_color']};")
        self.low_color_btn.setStyleSheet(
            f"background-color: rgb{self.config['low_color']};")
        self.high_color_btn.setStyleSheet(
            f"background-color: rgb{self.config['high_color']};")

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
                # Обновляем конфиг с сохранением значений по умолчанию
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
            pass
        except Exception as e:
            print(f"CONFIG LOAD ERROR: {str(e)}")

    def save_config(self):
        with open('config.json', 'w') as f:
            json.dump(self.config, f)

    def closeEvent(self, event):
        if self.ser:
            self.ser.close()
        self.audio_thread.stop()
        self.save_config()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LEDControl()
    window.show()

    sys.exit(app.exec_())
