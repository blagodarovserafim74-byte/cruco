import importlib
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from typing import Optional

from config import AppConfig
from tracker import CodeTracker, ScanResult


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
DB_PATH = os.path.join(DATA_DIR, "tracker.db")
REPORT_PATH = os.path.join(DATA_DIR, "last_report.txt")


class TrackerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Cruco Code Tracker")
        self.config = AppConfig.load(CONFIG_PATH)
        self.geometry(f"{self.config.window_width}x{self.config.window_height}")
        self.resizable(True, True)

        self.tracker = CodeTracker(
            db_path=DB_PATH,
            max_hash_size_bytes=self.config.max_hash_file_size_mb * 1024 * 1024,
        )

        self.selected_root: Optional[str] = None
        self.monitoring = False
        self.after_id: Optional[str] = None

        self._apply_ui_scale(self.config.ui_scale)
        self._build_ui()

    def _apply_ui_scale(self, scale: float) -> None:
        self.tk.call("tk", "scaling", scale)
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=max(8, int(10 * scale)))
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(size=max(8, int(10 * scale)))

    def _build_ui(self) -> None:
        self.mode_frame = ttk.Frame(self, padding=12)
        self.mode_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(self.mode_frame, text="Выберите режим работы:").pack(
            side=tk.LEFT, padx=(0, 12)
        )

        self.scan_button = ttk.Button(
            self.mode_frame, text="Быстрое сканирование", command=self._run_scan_once
        )
        self.scan_button.pack(side=tk.LEFT, padx=6)

        self.monitor_button = ttk.Button(
            self.mode_frame, text="Наблюдение", command=self._toggle_monitor
        )
        self.monitor_button.pack(side=tk.LEFT, padx=6)

        self.settings_button = ttk.Button(
            self.mode_frame, text="Настройки", command=self._open_settings
        )
        self.settings_button.pack(side=tk.LEFT, padx=6)

        self.camera_button = ttk.Button(
            self.mode_frame, text="Камера", command=self._open_camera
        )
        self.camera_button.pack(side=tk.LEFT, padx=6)

        self.path_frame = ttk.Frame(self, padding=12)
        self.path_frame.pack(side=tk.TOP, fill=tk.X)

        self.path_label = ttk.Label(self.path_frame, text="Каталог: не выбран")
        self.path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            self.path_frame, text="Выбрать каталог", command=self._choose_directory
        ).pack(side=tk.RIGHT)

        self.log_frame = ttk.Frame(self, padding=12)
        self.log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(self.log_frame, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _choose_directory(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.selected_root = path
            self.path_label.configure(text=f"Каталог: {path}")
            self._log(f"Выбран каталог: {path}")

    def _run_scan_once(self) -> None:
        if not self._ensure_directory():
            return
        result = self.tracker.scan(self.selected_root)
        self._render_scan_result(result)
        self._write_report(result)

    def _toggle_monitor(self) -> None:
        if self.monitoring:
            self._stop_monitoring()
            return
        if not self._ensure_directory():
            return
        self.monitoring = True
        self.monitor_button.configure(text="Остановить")
        self._log("Мониторинг запущен.")
        self._schedule_next_scan()

    def _schedule_next_scan(self) -> None:
        if not self.monitoring:
            return
        result = self.tracker.scan(self.selected_root)
        self._render_scan_result(result)
        self._write_report(result)
        self.after_id = self.after(
            self.config.scan_interval_seconds * 1000, self._schedule_next_scan
        )

    def _stop_monitoring(self) -> None:
        self.monitoring = False
        self.monitor_button.configure(text="Наблюдение")
        if self.after_id:
            self.after_cancel(self.after_id)
        self._log("Мониторинг остановлен.")

    def _open_settings(self) -> None:
        SettingsWindow(self)

    def _open_camera(self) -> None:
        CameraWindow(self)

    def _ensure_directory(self) -> bool:
        if not self.selected_root:
            messagebox.showwarning("Каталог не выбран", "Выберите каталог для анализа.")
            return False
        return True

    def _render_scan_result(self, result: ScanResult) -> None:
        self._log(
            "\n".join(
                [
                    "Результаты сканирования:",
                    f"Добавлено: {len(result.added)}",
                    f"Удалено: {len(result.removed)}",
                    f"Изменено: {len(result.modified)}",
                    f"Перемещено: {len(result.moved)}",
                    f"Без изменений: {result.unchanged}",
                    f"Длительность: {result.scan_duration:.2f} сек.",
                ]
            )
        )

    def _write_report(self, result: ScanResult) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            handle.write("Отчет о сканировании\n")
            handle.write("====================\n")
            handle.write(f"Добавлено: {len(result.added)}\n")
            handle.write(f"Удалено: {len(result.removed)}\n")
            handle.write(f"Изменено: {len(result.modified)}\n")
            handle.write(f"Перемещено: {len(result.moved)}\n")
            handle.write(f"Без изменений: {result.unchanged}\n")
            handle.write(f"Длительность: {result.scan_duration:.2f} сек.\n")
        permissions = self.config.report_permissions_mode()
        self.tracker.apply_permissions(REPORT_PATH, permissions)
        self.tracker.apply_permissions(DB_PATH, permissions)

    def _log(self, message: str) -> None:
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent: TrackerApp) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Настройки")
        self.resizable(False, False)

        self.inputs = {}
        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        self._add_field(container, "Интервал сканирования (сек)", "scan_interval_seconds")
        self._add_field(container, "Макс. размер для хэша (МБ)", "max_hash_file_size_mb")
        self._add_field(container, "Масштаб интерфейса", "ui_scale")
        self._add_field(container, "Ширина окна", "window_width")
        self._add_field(container, "Высота окна", "window_height")
        self._add_field(container, "Права отчета (octal)", "report_permissions")

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(button_frame, text="Применить", command=self._apply).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(button_frame, text="Закрыть", command=self.destroy).pack(
            side=tk.RIGHT, padx=6
        )

    def _add_field(self, parent: ttk.Frame, label: str, key: str) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=4)
        ttk.Label(frame, text=label).pack(side=tk.LEFT)
        entry = ttk.Entry(frame)
        entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        entry.insert(0, getattr(self.parent.config, key))
        self.inputs[key] = entry

    def _apply(self) -> None:
        try:
            self.parent.config.scan_interval_seconds = int(
                self.inputs["scan_interval_seconds"].get()
            )
            self.parent.config.max_hash_file_size_mb = int(
                self.inputs["max_hash_file_size_mb"].get()
            )
            self.parent.config.ui_scale = float(self.inputs["ui_scale"].get())
            self.parent.config.window_width = int(self.inputs["window_width"].get())
            self.parent.config.window_height = int(self.inputs["window_height"].get())
            self.parent.config.report_permissions = self.inputs[
                "report_permissions"
            ].get()
        except ValueError:
            messagebox.showerror(
                "Ошибка", "Проверьте значения настроек."
            )
            return

        self.parent.config.save(CONFIG_PATH)
        self.parent.geometry(
            f"{self.parent.config.window_width}x{self.parent.config.window_height}"
        )
        self.parent._apply_ui_scale(self.parent.config.ui_scale)
        self.parent.tracker.max_hash_size_bytes = (
            self.parent.config.max_hash_file_size_mb * 1024 * 1024
        )
        messagebox.showinfo("Готово", "Настройки сохранены.")


class CameraWindow(tk.Toplevel):
    def __init__(self, parent: TrackerApp) -> None:
        super().__init__(parent)
        self.title("Камера")
        self.resizable(True, True)
        self.parent = parent
        self.capture = None
        self.aruco_detector = None
        self.aruco_dictionaries = []
        self.aruco_dictionary_names = []
        self.last_marker_ids: list[int] = []
        self.running = True
        self.after_id = None
        self.frame_label = ttk.Label(self)
        self.frame_label.pack(fill=tk.BOTH, expand=True)
        self.status_label = ttk.Label(self, text="ArUco: ожидание")
        self.status_label.pack(fill=tk.X)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_camera()

    def _setup_camera(self) -> None:
        if not self._load_camera_modules():
            self.destroy()
            return

        if not self.cv2 or not self.Image or not self.ImageTk:
            messagebox.showerror(
                "Камера недоступна",
                "Не удалось загрузить модули камеры. Проверьте зависимости.",
            )
            self.destroy()
            return
        self._setup_aruco()
        self.capture = self.cv2.VideoCapture(0)
        if not self.capture.isOpened():
            messagebox.showerror("Камера недоступна", "Не удалось открыть камеру.")
            self.destroy()
            return
        self._update_frame()

    def _update_frame(self) -> None:
        if not self.running or not self.capture:
            return
        ok, frame = self.capture.read()
        if ok:
            frame = self._detect_aruco(frame)
            frame = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
            image = self.Image.fromarray(frame)
            photo = self.ImageTk.PhotoImage(image=image)
            self.frame_label.configure(image=photo)
            self.frame_label.image = photo
        if self.running:
            self.after_id = self.after(30, self._update_frame)

    def _on_close(self) -> None:
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id)
        if self.capture:
            self.capture.release()
        self.destroy()

    def _load_camera_modules(self) -> bool:
        try:
            self.cv2 = importlib.import_module("cv2")
            self.Image = importlib.import_module("PIL.Image")
            self.ImageTk = importlib.import_module("PIL.ImageTk")
        except Exception:
            DependencyDialog(self)
            return False
        return True

    def _setup_aruco(self) -> None:
        try:
            aruco = self.cv2.aruco
        except AttributeError:
            messagebox.showwarning(
                "ArUco недоступен",
                "Ваша версия OpenCV не поддерживает ArUco. "
                "Установите opencv-contrib-python.",
            )
            self.aruco_detector = None
            return

        self.aruco_dictionary_names = [
            "DICT_4X4_50",
            "DICT_4X4_100",
            "DICT_5X5_100",
            "DICT_6X6_100",
        ]
        self.aruco_dictionaries = [
            aruco.getPredefinedDictionary(getattr(aruco, name))
            for name in self.aruco_dictionary_names
        ]
        parameters = aruco.DetectorParameters()
        self.aruco_detector = aruco.ArucoDetector(
            self.aruco_dictionaries[0], parameters
        )
        self.status_label.configure(text="ArUco: поиск маркеров")

    def _detect_aruco(self, frame):
        if not self.aruco_detector or not self.aruco_dictionaries:
            return frame
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        corners = ids = None
        found_dictionary = None
        for dictionary, name in zip(
            self.aruco_dictionaries, self.aruco_dictionary_names
        ):
            self.aruco_detector = self.cv2.aruco.ArucoDetector(
                dictionary, self.aruco_detector.getDetectorParameters()
            )
            corners, ids, _ = self.aruco_detector.detectMarkers(gray)
            if ids is not None and len(ids) > 0:
                found_dictionary = name
                break
        if ids is not None and len(ids) > 0:
            self.last_marker_ids = [int(value) for value in ids.flatten().tolist()]
            self.cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            self.status_label.configure(
                text=(
                    f"ArUco: найдено {len(self.last_marker_ids)} "
                    f"({found_dictionary}) | ids: {self.last_marker_ids}"
                )
            )
        else:
            self.last_marker_ids = []
            self.status_label.configure(text="ArUco: маркеры не найдены")
        return frame


class DependencyDialog(tk.Toplevel):
    def __init__(self, parent: tk.Toplevel) -> None:
        super().__init__(parent)
        self.title("Камера недоступна")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        message = (
            "Для камеры нужны зависимости: opencv-contrib-python и Pillow.\n"
            "Если установка не удается, закройте приложения, использующие Python,\n"
            "или запустите установку с правами администратора."
        )
        ttk.Label(frame, text=message, justify=tk.LEFT).pack(fill=tk.X)

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(button_frame, text="Установить", command=self._install).pack(
            side=tk.LEFT
        )
        ttk.Button(button_frame, text="Закрыть", command=self.destroy).pack(
            side=tk.RIGHT
        )

    def _install(self) -> None:
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "opencv-contrib-python",
            "Pillow",
        ]
        try:
            subprocess.check_call(command)
        except subprocess.CalledProcessError:
            messagebox.showerror(
                "Ошибка установки",
                "Не удалось установить зависимости. Попробуйте вручную:\n"
                "1) pip uninstall opencv-python opencv-contrib-python\n"
                "2) pip install opencv-contrib-python Pillow\n"
                "3) Удалите папки cv2/opencv_python* из .venv/Lib/site-packages\n"
                "4) Запустите терминал от администратора, если нужна запись в venv.",
            )
            return
        messagebox.showinfo(
            "Установка завершена",
            "Зависимости установлены. Откройте окно камеры снова.",
        )
        self.destroy()


if __name__ == "__main__":
    app = TrackerApp()
    app.mainloop()
