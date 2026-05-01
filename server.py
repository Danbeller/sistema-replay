# =============================================================================
# SISTEMA DE REPLAY EM BUFFER — replay_system.py
# =============================================================================
# INSTALAÇÃO:
#   pip install opencv-python numpy mss Pillow
#
# USO:
#   python server.py
#
# MODO PADRÃO: captura de tela (mss)
# Para usar a webcam, altere CAPTURE_MODE = "webcam" na seção de configurações
# =============================================================================


import cv2 # pyright: ignore[reportMissingImports]
import numpy as np
import mss # pyright: ignore[reportMissingImports]
import threading
import time
import collections
import re
import ctypes
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from PIL import Image, ImageTk
import os
from urllib.parse import quote, unquote

try:
    import serial  # pyright: ignore[reportMissingImports]
    from serial.tools import list_ports  # pyright: ignore[reportMissingImports]
except Exception:
    serial = None
    list_ports = None

# =============================================================================
# CONFIGURAÃ‡Ã•ES GLOBAIS
# =============================================================================
CAPTURE_MODE   = "webcam"   # "screen" ou "webcam"
TARGET_FPS     = 120          # FPS alvo (reduzido para tela â€” 30 Ã© pesado para screen capture)
REPLAY_SECONDS = 180         # 3 minutos
BUFFER_MAXLEN  = TARGET_FPS * REPLAY_SECONDS
JPEG_QUALITY   = 70          # Qualidade da compressÃ£o JPEG (0-100). Menor = menos RAM
PREVIEW_W      = 400         # Largura do preview na UI
PREVIEW_H      = 225         # Altura do preview na UI
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
SAVED_DIR      = os.path.join(BASE_DIR, "arquivos_salvos")
CONFIG_FILE    = os.path.join(BASE_DIR, "config.json")
SERIAL_ENABLED = True
SERIAL_PORT    = "AUTO"
SERIAL_BAUDRATE = 115200
SERIAL_TRIGGER_MESSAGE = "REPLAY"
SERIAL_DEBOUNCE_MS = 1200
CAM1_DEVICE_INDEX = 0
CAM2_ENABLED = True
CAM2_SOURCE_URL = ""
CAM2_QR_URL = "http://yoosee.co/?D=0-7154973099-8034"
CAM2_RTSP_HINT = "rtsp://IP_DA_CAMERA:554/user=SEU_EMAIL&password=SUA_SENHA&channel=1&stream=0.sdp"
CAM2_FALLBACK_PASSWORDS = ("123", "123456", "888888")
CAM2_WINDOW_FALLBACK_ENABLED = True
CAM2_WINDOW_TITLE_HINT = "Yoosee"
CAM2_WINDOW_CROP_ENABLED = True
CAM2_WINDOW_SEARCH_LEFT = 0.20
CAM2_WINDOW_SEARCH_TOP = 0.14
CAM2_WINDOW_SEARCH_RIGHT = 0.98
CAM2_WINDOW_SEARCH_BOTTOM = 0.86
CAM2_WINDOW_TILE_INSET_X = 0.02
CAM2_WINDOW_TILE_INSET_Y = 0.04
CAM2_VLC_RELAY_PORT = 8092


def _load_config():
    """Carrega configuraÃ§Ãµes salvas do config.json, se existir."""
    global TARGET_FPS, REPLAY_SECONDS, BUFFER_MAXLEN, JPEG_QUALITY, CAPTURE_MODE
    global SERIAL_ENABLED, SERIAL_PORT, SERIAL_BAUDRATE, SERIAL_TRIGGER_MESSAGE, SERIAL_DEBOUNCE_MS
    global CAM1_DEVICE_INDEX, CAM2_ENABLED, CAM2_SOURCE_URL, CAM2_QR_URL, CAM2_RTSP_HINT
    global CAM2_WINDOW_FALLBACK_ENABLED, CAM2_WINDOW_TITLE_HINT
    global CAM2_WINDOW_CROP_ENABLED, CAM2_WINDOW_SEARCH_LEFT, CAM2_WINDOW_SEARCH_TOP
    global CAM2_WINDOW_SEARCH_RIGHT, CAM2_WINDOW_SEARCH_BOTTOM
    global CAM2_WINDOW_TILE_INSET_X, CAM2_WINDOW_TILE_INSET_Y
    import json
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        fps = int(cfg.get("TARGET_FPS", TARGET_FPS))
        replay_seconds = int(cfg.get("REPLAY_SECONDS", REPLAY_SECONDS))
        jpeg_quality = int(cfg.get("JPEG_QUALITY", JPEG_QUALITY))
        mode = str(cfg.get("CAPTURE_MODE", CAPTURE_MODE)).strip().lower()
        serial_enabled = bool(cfg.get("SERIAL_ENABLED", SERIAL_ENABLED))
        serial_port = str(cfg.get("SERIAL_PORT", SERIAL_PORT)).strip()
        serial_baudrate = int(cfg.get("SERIAL_BAUDRATE", SERIAL_BAUDRATE))
        serial_trigger = str(cfg.get("SERIAL_TRIGGER_MESSAGE", SERIAL_TRIGGER_MESSAGE)).strip()
        serial_debounce = int(cfg.get("SERIAL_DEBOUNCE_MS", SERIAL_DEBOUNCE_MS))
        cam1_device_index = int(cfg.get("CAM1_DEVICE_INDEX", CAM1_DEVICE_INDEX))
        cam2_enabled = bool(cfg.get("CAM2_ENABLED", CAM2_ENABLED))
        cam2_source_url = str(cfg.get("CAM2_SOURCE_URL", CAM2_SOURCE_URL)).strip()
        cam2_qr_url = str(cfg.get("CAM2_QR_URL", CAM2_QR_URL)).strip()
        cam2_rtsp_hint = str(cfg.get("CAM2_RTSP_HINT", CAM2_RTSP_HINT)).strip()
        cam2_window_fallback_enabled = bool(cfg.get("CAM2_WINDOW_FALLBACK_ENABLED", CAM2_WINDOW_FALLBACK_ENABLED))
        cam2_window_title_hint = str(cfg.get("CAM2_WINDOW_TITLE_HINT", CAM2_WINDOW_TITLE_HINT)).strip()
        cam2_window_crop_enabled = bool(cfg.get("CAM2_WINDOW_CROP_ENABLED", CAM2_WINDOW_CROP_ENABLED))
        cam2_window_search_left = float(cfg.get("CAM2_WINDOW_SEARCH_LEFT", CAM2_WINDOW_SEARCH_LEFT))
        cam2_window_search_top = float(cfg.get("CAM2_WINDOW_SEARCH_TOP", CAM2_WINDOW_SEARCH_TOP))
        cam2_window_search_right = float(cfg.get("CAM2_WINDOW_SEARCH_RIGHT", CAM2_WINDOW_SEARCH_RIGHT))
        cam2_window_search_bottom = float(cfg.get("CAM2_WINDOW_SEARCH_BOTTOM", CAM2_WINDOW_SEARCH_BOTTOM))
        cam2_window_tile_inset_x = float(cfg.get("CAM2_WINDOW_TILE_INSET_X", CAM2_WINDOW_TILE_INSET_X))
        cam2_window_tile_inset_y = float(cfg.get("CAM2_WINDOW_TILE_INSET_Y", CAM2_WINDOW_TILE_INSET_Y))

        # Sanitiza limites para evitar valores quebrando a captura.
        TARGET_FPS = max(1, min(fps, 240))
        REPLAY_SECONDS = max(30, min(replay_seconds, 3600))
        JPEG_QUALITY = max(30, min(jpeg_quality, 100))
        CAPTURE_MODE = mode if mode in ("screen", "webcam") else "webcam"
        SERIAL_ENABLED = serial_enabled
        SERIAL_PORT = serial_port or "AUTO"
        SERIAL_BAUDRATE = max(300, min(serial_baudrate, 2000000))
        SERIAL_TRIGGER_MESSAGE = serial_trigger or "REPLAY"
        SERIAL_DEBOUNCE_MS = max(100, min(serial_debounce, 10000))
        CAM1_DEVICE_INDEX = max(0, min(cam1_device_index, 10))
        CAM2_ENABLED = cam2_enabled
        CAM2_SOURCE_URL = cam2_source_url
        CAM2_QR_URL = cam2_qr_url or CAM2_QR_URL
        CAM2_RTSP_HINT = cam2_rtsp_hint or CAM2_RTSP_HINT
        CAM2_WINDOW_FALLBACK_ENABLED = cam2_window_fallback_enabled
        CAM2_WINDOW_TITLE_HINT = cam2_window_title_hint or CAM2_WINDOW_TITLE_HINT
        CAM2_WINDOW_CROP_ENABLED = cam2_window_crop_enabled
        CAM2_WINDOW_SEARCH_LEFT = max(0.0, min(cam2_window_search_left, 0.95))
        CAM2_WINDOW_SEARCH_TOP = max(0.0, min(cam2_window_search_top, 0.95))
        CAM2_WINDOW_SEARCH_RIGHT = max(CAM2_WINDOW_SEARCH_LEFT + 0.02, min(cam2_window_search_right, 1.0))
        CAM2_WINDOW_SEARCH_BOTTOM = max(CAM2_WINDOW_SEARCH_TOP + 0.02, min(cam2_window_search_bottom, 1.0))
        CAM2_WINDOW_TILE_INSET_X = max(0.0, min(cam2_window_tile_inset_x, 0.2))
        CAM2_WINDOW_TILE_INSET_Y = max(0.0, min(cam2_window_tile_inset_y, 0.2))
        BUFFER_MAXLEN  = TARGET_FPS * REPLAY_SECONDS
    except Exception:
        pass  # sem config salvo, usa os padrÃµes acima

_load_config()


def _apply_env_overrides():
    """Permite sobrescrever configs por variáveis de ambiente sem editar arquivos."""
    global SERIAL_ENABLED, SERIAL_PORT

    serial_enabled_env = os.environ.get("REPLAY_SERIAL_ENABLED", "").strip().lower()
    if serial_enabled_env in {"0", "false", "nao", "não", "off"}:
        SERIAL_ENABLED = False
    elif serial_enabled_env in {"1", "true", "sim", "on"}:
        SERIAL_ENABLED = True

    serial_port_env = os.environ.get("REPLAY_SERIAL_PORT", "").strip()
    if serial_port_env:
        SERIAL_PORT = serial_port_env


_apply_env_overrides()


def _save_config():
    """Persiste as configuraÃ§Ãµes atuais no config.json."""
    import json
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "TARGET_FPS":     TARGET_FPS,
                "REPLAY_SECONDS": REPLAY_SECONDS,
                "JPEG_QUALITY":   JPEG_QUALITY,
                "CAPTURE_MODE":   CAPTURE_MODE,
                "SERIAL_ENABLED": SERIAL_ENABLED,
                "SERIAL_PORT": SERIAL_PORT,
                "SERIAL_BAUDRATE": SERIAL_BAUDRATE,
                "SERIAL_TRIGGER_MESSAGE": SERIAL_TRIGGER_MESSAGE,
                "SERIAL_DEBOUNCE_MS": SERIAL_DEBOUNCE_MS,
                "CAM1_DEVICE_INDEX": CAM1_DEVICE_INDEX,
                "CAM2_ENABLED": CAM2_ENABLED,
                "CAM2_SOURCE_URL": CAM2_SOURCE_URL,
                "CAM2_QR_URL": CAM2_QR_URL,
                "CAM2_RTSP_HINT": CAM2_RTSP_HINT,
                "CAM2_WINDOW_FALLBACK_ENABLED": CAM2_WINDOW_FALLBACK_ENABLED,
                "CAM2_WINDOW_TITLE_HINT": CAM2_WINDOW_TITLE_HINT,
                "CAM2_WINDOW_CROP_ENABLED": CAM2_WINDOW_CROP_ENABLED,
                "CAM2_WINDOW_SEARCH_LEFT": CAM2_WINDOW_SEARCH_LEFT,
                "CAM2_WINDOW_SEARCH_TOP": CAM2_WINDOW_SEARCH_TOP,
                "CAM2_WINDOW_SEARCH_RIGHT": CAM2_WINDOW_SEARCH_RIGHT,
                "CAM2_WINDOW_SEARCH_BOTTOM": CAM2_WINDOW_SEARCH_BOTTOM,
                "CAM2_WINDOW_TILE_INSET_X": CAM2_WINDOW_TILE_INSET_X,
                "CAM2_WINDOW_TILE_INSET_Y": CAM2_WINDOW_TILE_INSET_Y,
            }, f, indent=2)
    except Exception:
        pass


# =============================================================================
# CLASSE: FrameCapture
# Gerencia a thread de captura contÃ­nua e o buffer circular
# =============================================================================
class FrameCapture:
    def __init__(self, mode: str = "screen", source=None, label: str = "CAM-1"):
        self.mode    = mode
        self.source  = 0 if source is None else source
        self.label   = label
        self.running = False
        self.thread  = None
        self.lock    = threading.Lock()
        self.status_text = "Aguardando..."
        self.last_error = ""

        # Buffer circular: cada item Ã© (timestamp_float, bytes_jpeg)
        self.buffer: collections.deque = collections.deque(maxlen=BUFFER_MAXLEN)

        # Frame mais recente para exibir no preview (numpy array BGR)
        self.latest_frame: np.ndarray | None = None
        self.actual_fps: float = 0.0

        # EstatÃ­sticas
        self._fps_counter = 0
        self._fps_timer   = time.time()
        self._vlc_relay_proc = None

    # ------------------------------------------------------------------
    def start(self):
        """Inicia a thread de captura em background."""
        if self.running:
            return
        self.last_error = ""
        self.status_text = "Conectando..."
        self.running = True
        self.thread  = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    # ------------------------------------------------------------------
    def stop(self):
        """Sinaliza parada e aguarda a thread encerrar."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
        self._stop_vlc_relay()
        self.status_text = "Parada"

    # ------------------------------------------------------------------
    def _capture_loop(self):
        """Loop principal de captura â€” roda em thread separada."""
        try:
            if self.mode == "webcam":
                self._capture_webcam()
            else:
                self._capture_screen()
        except Exception as err:
            self.last_error = str(err)
            self.status_text = f"Erro: {err}"
            self.running = False

    # ------------------------------------------------------------------
    def _capture_webcam(self):
        """Captura frames da webcam via OpenCV."""
        capture_source = self.source
        if isinstance(capture_source, str):
            capture_source = capture_source.strip()
            if not capture_source:
                raise RuntimeError(f"Fonte da {self.label} nÃ£o configurada.")
            if capture_source.isdigit():
                capture_source = int(capture_source)

        def _open_with_backend(source, backend=None, ffmpeg_options=None):
            previous_options = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
            try:
                if ffmpeg_options is None:
                    os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
                else:
                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = ffmpeg_options

                if backend is None:
                    cap = cv2.VideoCapture(source)
                else:
                    cap = cv2.VideoCapture(source, backend)
                if cap.isOpened():
                    return cap
                cap.release()
                return None
            finally:
                if previous_options is None:
                    os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
                else:
                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous_options

        def _is_exact_rtsp_source(source: str) -> bool:
            normalized = source.strip().lower()
            return normalized.startswith("rtsp://") and (
                "@" in normalized or "/user=" in normalized
            )

        def _build_rtsp_candidates(source: str):
            candidates = [source]

            def _encode_rtsp_value(value: str) -> str:
                return quote(value, safe="")

            def _can_use_auth_style(username: str, password: str) -> bool:
                blocked_chars = set("@:/?&#")
                return not any(ch in blocked_chars for ch in username) and not any(ch in blocked_chars for ch in password)

            auth_match = re.match(r"^rtsp://([^:]+):([^@]+)@([^/:]+)(?::(\d+))?/(.+)$", source, re.IGNORECASE)
            if auth_match:
                username, password, host, port, _path = auth_match.groups()
                username = unquote(username)
                password = unquote(password)
                port = port or "554"
                user_candidates = [username]

                password_candidates = [password]
                for fallback_password in CAM2_FALLBACK_PASSWORDS:
                    if fallback_password not in password_candidates:
                        password_candidates.append(fallback_password)

                for candidate_user in user_candidates:
                    for candidate_password in password_candidates:
                        encoded_user = _encode_rtsp_value(candidate_user)
                        encoded_password = _encode_rtsp_value(candidate_password)
                        if _can_use_auth_style(candidate_user, candidate_password):
                            candidates.extend([
                                f"rtsp://{candidate_user}:{candidate_password}@{host}:{port}/onvif1",
                                f"rtsp://{candidate_user}:{candidate_password}@{host}:{port}/onvif2",
                                f"rtsp://{candidate_user}:{candidate_password}@{host}:{port}/11",
                                f"rtsp://{candidate_user}:{candidate_password}@{host}:{port}/12",
                            ])
                        candidates.extend([
                            f"rtsp://{host}:{port}/user={encoded_user}&password={encoded_password}&channel=1&stream=0.sdp",
                            f"rtsp://{host}:{port}/user={encoded_user}&password={encoded_password}&channel=1&stream=1.sdp",
                        ])

            query_match = re.match(
                r"^rtsp://([^/:]+)(?::(\d+))?/user=([^&]+)&password=([^&]+)&channel=(\d+)&stream=(\d+)\.sdp$",
                source,
                re.IGNORECASE,
            )
            if query_match:
                host, port, username, password, channel, _stream = query_match.groups()
                username = unquote(username)
                password = unquote(password)
                port = port or "554"
                user_candidates = [username]

                password_candidates = [password]
                for fallback_password in CAM2_FALLBACK_PASSWORDS:
                    if fallback_password not in password_candidates:
                        password_candidates.append(fallback_password)

                for candidate_user in user_candidates:
                    for candidate_password in password_candidates:
                        encoded_user = _encode_rtsp_value(candidate_user)
                        encoded_password = _encode_rtsp_value(candidate_password)
                        candidates.extend([
                            f"rtsp://{host}:{port}/user={encoded_user}&password={encoded_password}&channel={channel}&stream=0.sdp",
                            f"rtsp://{host}:{port}/user={encoded_user}&password={encoded_password}&channel={channel}&stream=1.sdp",
                        ])
                        if _can_use_auth_style(candidate_user, candidate_password):
                            candidates.extend([
                                f"rtsp://{candidate_user}:{candidate_password}@{host}:{port}/onvif1",
                                f"rtsp://{candidate_user}:{candidate_password}@{host}:{port}/onvif2",
                                f"rtsp://{candidate_user}:{candidate_password}@{host}:{port}/11",
                                f"rtsp://{candidate_user}:{candidate_password}@{host}:{port}/12",
                            ])

            unique_candidates = []
            for item in candidates:
                if item not in unique_candidates:
                    unique_candidates.append(item)
            return unique_candidates

        if (
            isinstance(capture_source, str)
            and self.label.upper().startswith("CAM-2")
            and capture_source.lower().startswith("rtsp://")
        ):
            if self._capture_rtsp_with_vlc_relay(capture_source):
                return

        attempts = []
        open_attempts = []
        if isinstance(capture_source, str):
            normalized_source = capture_source.lower()
            if normalized_source.startswith("rtsp://"):
                rtsp_sources = (
                    [capture_source]
                    if self.label.upper().startswith("CAM-2") and _is_exact_rtsp_source(capture_source)
                    else _build_rtsp_candidates(capture_source)
                )
                for candidate_source in rtsp_sources:
                    open_attempts.extend([
                        (f"FFMPEG/UDP {candidate_source}", candidate_source, cv2.CAP_FFMPEG, "rtsp_transport;udp"),
                        (f"FFMPEG/TCP {candidate_source}", candidate_source, cv2.CAP_FFMPEG, "rtsp_transport;tcp"),
                    ])
            elif normalized_source.startswith("http://") or normalized_source.startswith("https://"):
                open_attempts = [
                    (f"AUTO {capture_source}", capture_source, cv2.CAP_ANY, None),
                    (f"FFMPEG {capture_source}", capture_source, cv2.CAP_FFMPEG, None),
                ]

        if not open_attempts:
            open_attempts = [("AUTO", capture_source, cv2.CAP_ANY, None)]

        cap = None
        for attempt_name, attempt_source, backend, ffmpeg_options in open_attempts:
            attempts.append(attempt_name)
            cap = _open_with_backend(attempt_source, backend=backend, ffmpeg_options=ffmpeg_options)
            if cap is not None:
                self.source = attempt_source
                break

        if cap is None:
            if (
                self.label.upper().startswith("CAM-2")
                and CAM2_WINDOW_FALLBACK_ENABLED
            ):
                self.status_text = "RTSP falhou, usando janela Yoosee"
                self._capture_named_window(CAM2_WINDOW_TITLE_HINT)
                return
            raise RuntimeError(
                f"{self.label} nÃ£o abriu. Verifique a URL/IP/login da cÃ¢mera. Tentativas: {', '.join(attempts)}"
            )

        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        interval = 1.0 / TARGET_FPS
        self.status_text = "Online"

        try:
            while self.running:
                t0 = time.time()
                ret, frame = cap.read()
                if not ret:
                    self.status_text = "Sem frames"
                    time.sleep(0.1)
                    continue
                self.status_text = "Online"
                self._push_frame(frame)
                elapsed = time.time() - t0
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            cap.release()

    # ------------------------------------------------------------------
    def _find_vlc_path(self):
        """Localiza o VLC instalado no sistema."""
        candidates = [
            shutil.which("vlc"),
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    # ------------------------------------------------------------------
    def _stop_vlc_relay(self):
        """Encerra o processo de relay do VLC, se existir."""
        if self._vlc_relay_proc is None:
            return
        try:
            self._vlc_relay_proc.terminate()
            self._vlc_relay_proc.wait(timeout=5)
        except Exception:
            try:
                self._vlc_relay_proc.kill()
            except Exception:
                pass
        finally:
            self._vlc_relay_proc = None

    # ------------------------------------------------------------------
    def _capture_rtsp_with_vlc_relay(self, source: str) -> bool:
        """Usa o VLC para abrir o RTSP e expor um TS HTTP local compatível com OpenCV."""
        vlc_path = self._find_vlc_path()
        if not vlc_path:
            return False

        relay_url = f"http://127.0.0.1:{CAM2_VLC_RELAY_PORT}/cam2.ts"
        self._stop_vlc_relay()

        cmd = [
            vlc_path,
            "-I", "dummy",
            source,
            "--network-caching=1000",
            "--rtsp-tcp",
            "--sout",
            f"#std{{access=http,mux=ts,dst=:{CAM2_VLC_RELAY_PORT}/cam2.ts}}",
            "--no-sout-audio",
            "--sout-keep",
        ]

        try:
            self._vlc_relay_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            self._vlc_relay_proc = None
            return False

        time.sleep(6.0)
        cap = cv2.VideoCapture(relay_url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            self._stop_vlc_relay()
            return False

        interval = 1.0 / TARGET_FPS
        self.status_text = "Online via VLC relay"

        try:
            while self.running:
                t0 = time.time()
                ret, frame = cap.read()
                if not ret:
                    self.status_text = "Sem frames via VLC relay"
                    time.sleep(0.1)
                    continue
                self.status_text = "Online via VLC relay"
                self._push_frame(frame)
                elapsed = time.time() - t0
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            cap.release()
            self._stop_vlc_relay()

        return True

    # ------------------------------------------------------------------
    def _find_window_rect(self, title_hint: str):
        """Localiza uma janela visível pelo título e retorna sua área."""
        user32 = ctypes.windll.user32
        rect = ctypes.wintypes.RECT()
        title_hint = (title_hint or "").strip().lower()
        if not title_hint:
            return None

        found_rect = None

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def _enum_proc(hwnd, _lparam):
            nonlocal found_rect
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if title_hint not in title.lower():
                return True

            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True

            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width < 50 or height < 50:
                return True

            found_rect = {
                "left": rect.left,
                "top": rect.top,
                "width": width,
                "height": height,
            }
            return False

        user32.EnumWindows(_enum_proc, 0)
        return found_rect

    # ------------------------------------------------------------------
    def _capture_named_window(self, title_hint: str):
        """Captura continuamente uma janela específica usando mss."""
        interval = 1.0 / TARGET_FPS

        with mss.mss() as sct:
            while self.running:
                t0 = time.time()
                monitor = self._find_window_rect(title_hint)
                if not monitor:
                    self.status_text = f"Janela '{title_hint}' nÃ£o encontrada"
                    time.sleep(0.4)
                    continue

                try:
                    img = sct.grab(monitor)
                    frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                except Exception:
                    self.status_text = f"Falha ao capturar janela '{title_hint}'"
                    time.sleep(0.2)
                    continue

                if CAM2_WINDOW_CROP_ENABLED:
                    cropped_frame = self._crop_yoosee_video_area(frame)
                    if cropped_frame is not None and cropped_frame.size > 0:
                        frame = cropped_frame

                self.status_text = f"Online via janela {title_hint}"
                self._push_frame(frame)

                elapsed = time.time() - t0
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    # ------------------------------------------------------------------
    def _capture_screen(self):
        """Captura a tela principal via mss."""
        interval = 1.0 / TARGET_FPS

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # monitor principal

            while self.running:
                t0 = time.time()

                img = sct.grab(monitor)
                # mss retorna BGRA â€” converter para BGR (OpenCV padrÃ£o)
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
                self._push_frame(frame)

                elapsed = time.time() - t0
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    # ------------------------------------------------------------------
    def _push_frame(self, frame: np.ndarray):
        """Comprime e insere um frame no buffer circular."""
        ts = time.time()

        # Comprimir para JPEG em memÃ³ria â€” reduz uso de RAM drasticamente
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        success, encoded = cv2.imencode(".jpg", frame, encode_params)
        if not success:
            return

        with self.lock:
            self.buffer.append((ts, encoded.tobytes()))
            self.latest_frame = frame  # frame bruto para preview

        # Calcular FPS real a cada segundo
        self._fps_counter += 1
        now = time.time()
        if now - self._fps_timer >= 1.0:
            self.actual_fps  = self._fps_counter / (now - self._fps_timer)
            self._fps_counter = 0
            self._fps_timer   = now

    # ------------------------------------------------------------------
    def get_snapshot(self) -> list:
        """Retorna uma cÃ³pia do buffer no instante atual (thread-safe)."""
        with self.lock:
            return list(self.buffer)

    # ------------------------------------------------------------------
    @property
    def buffer_duration(self) -> float:
        """DuraÃ§Ã£o em segundos do conteÃºdo atual no buffer."""
        with self.lock:
            if len(self.buffer) < 2:
                return 0.0
            return self.buffer[-1][0] - self.buffer[0][0]

    # ------------------------------------------------------------------
    def resize_buffer(self, new_maxlen: int):
        """Redimensiona o buffer circular preservando os frames existentes (thread-safe)."""
        with self.lock:
            self.buffer = collections.deque(self.buffer, maxlen=new_maxlen)


# =============================================================================
# CLASSE: ReplayExporter
# Exporta o buffer para um arquivo .mp4 de forma assÃ­ncrona
# =============================================================================
class ReplayExporter:
    def __init__(self, on_progress=None, on_done=None, on_error=None):
        """
        Callbacks:
          on_progress(pct: float)  â€” 0.0 a 1.0
          on_done(filepath: str, thumb_path: str | None)
          on_error(msg: str)
        """
        self.on_progress = on_progress or (lambda p: None)
        self.on_done     = on_done     or (lambda f: None)
        self.on_error    = on_error    or (lambda e: None)
        self.exporting   = False

    # ------------------------------------------------------------------
    def export_async(self, snapshot: list, replay_label: str = "replay"):
        """Inicia a exportaÃ§Ã£o em uma thread separada."""
        if self.exporting:
            self.on_error("ExportaÃ§Ã£o jÃ¡ em andamento. Aguarde.")
            return
        t = threading.Thread(target=self._export, args=(snapshot, replay_label), daemon=True)
        t.start()

    # ------------------------------------------------------------------
    def _export(self, snapshot: list, replay_label: str = "replay"):
        """LÃ³gica de exportaÃ§Ã£o â€” roda em thread separada."""
        self.exporting = True
        try:
            if not snapshot:
                self.on_error("Buffer vazio â€” grave por pelo menos 10 segundos.")
                return

            now_ts = time.time()
            cutoff  = now_ts - REPLAY_SECONDS

            # Filtrar apenas os frames dentro da janela de 3 minutos
            frames_in_window = [(ts, data) for ts, data in snapshot if ts >= cutoff]

            if len(frames_in_window) < 2:
                self.on_error("Buffer vazio â€” grave por pelo menos 10 segundos.")
                return

            # Calcular FPS real baseado nos timestamps
            duration   = frames_in_window[-1][0] - frames_in_window[0][0]
            real_fps   = len(frames_in_window) / max(duration, 0.001)
            real_fps   = max(1.0, min(real_fps, 60.0))  # Limitar entre 1 e 60

            # Decodificar o primeiro frame para descobrir Resolução
            first_encoded = np.frombuffer(frames_in_window[0][1], dtype=np.uint8)
            first_frame   = cv2.imdecode(first_encoded, cv2.IMREAD_COLOR)
            if first_frame is None:
                self.on_error("Erro ao decodificar frames do buffer.")
                return

            h, w = first_frame.shape[:2]

            # Nome do arquivo com timestamp
            os.makedirs(SAVED_DIR, exist_ok=True)
            ts_str    = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath  = os.path.join(SAVED_DIR, f"{replay_label}_{ts_str}.mp4")

            # Criar VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(filepath, fourcc, real_fps, (w, h))

            if not writer.isOpened():
                self.on_error(f"NÃ£o foi possÃ­vel criar o arquivo: {filepath}")
                return

            total = len(frames_in_window)
            thumb_frame = None
            mid_index   = total // 2

            for i, (ts, data) in enumerate(frames_in_window):
                encoded_arr = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(encoded_arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    # Redimensionar se necessÃ¡rio (tamanho pode variar em screen capture)
                    if frame.shape[:2] != (h, w):
                        frame = cv2.resize(frame, (w, h))
                    writer.write(frame)
                    if i == mid_index:
                        thumb_frame = frame.copy()

                # Reportar progresso
                self.on_progress((i + 1) / total)

            writer.release()

            # Salvar thumbnail ao lado do .mp4
            thumb_path = filepath.replace(".mp4", "_thumb.jpg")
            if thumb_frame is not None:
                thumb_small = cv2.resize(thumb_frame, (160, 90))
                cv2.imwrite(thumb_path, thumb_small, [cv2.IMWRITE_JPEG_QUALITY, 85])
            else:
                thumb_path = None

            self.on_done(filepath, thumb_path)

        except Exception as e:
            self.on_error(f"Erro inesperado durante exportaÃ§Ã£o: {e}")
        finally:
            self.exporting = False


# =============================================================================
# CLASSE: SerialReplayTrigger
# Escuta a porta serial do Arduino e dispara o replay ao receber o comando
# =============================================================================
class SerialReplayTrigger:
    def __init__(self, on_trigger=None, on_status=None, on_error=None):
        self.on_trigger = on_trigger or (lambda: None)
        self.on_status = on_status or (lambda msg: None)
        self.on_error = on_error or (lambda msg: None)
        self.running = False
        self.thread = None
        self.connection = None
        self.connected_port = None
        self._last_trigger_at = 0.0

    # ------------------------------------------------------------------
    def start(self):
        """Inicia a escuta serial em background."""
        if self.running or not SERIAL_ENABLED:
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    # ------------------------------------------------------------------
    def stop(self):
        """Encerra a escuta serial e fecha a porta, se aberta."""
        self.running = False
        self._close_connection()
        if self.thread:
            self.thread.join(timeout=3)

    # ------------------------------------------------------------------
    def _close_connection(self):
        """Fecha a conexão serial atual sem lançar erro."""
        conn = self.connection
        self.connection = None
        self.connected_port = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _match_arduino_port(self):
        """Tenta localizar automaticamente uma porta que pareça ser um Arduino."""
        if list_ports is None:
            return None

        preferred_terms = (
            "arduino",
            "uno",
            "ch340",
            "wch",
            "usb serial",
            "serial usb",
        )

        ports = list(list_ports.comports())
        for port in ports:
            text = " ".join([
                getattr(port, "device", "") or "",
                getattr(port, "description", "") or "",
                getattr(port, "manufacturer", "") or "",
                getattr(port, "hwid", "") or "",
            ]).lower()
            if any(term in text for term in preferred_terms):
                return port.device

        if len(ports) == 1:
            return ports[0].device
        return None

    # ------------------------------------------------------------------
    def _resolve_port_name(self):
        """Resolve a porta configurada manualmente ou por autodetecção."""
        configured_port = (SERIAL_PORT or "AUTO").strip()
        if configured_port.upper() != "AUTO":
            return configured_port
        return self._match_arduino_port()

    # ------------------------------------------------------------------
    def _listen_loop(self):
        """Mantém conexão com o Arduino e reage aos comandos vindos da serial."""
        while self.running:
            if self.connection is None:
                port_name = self._resolve_port_name()
                if not port_name:
                    self.on_status("Aguardando Arduino")
                    time.sleep(2.0)
                    continue

                if serial is None:
                    self.on_error("pyserial não está instalado. O replay via Arduino foi desativado.")
                    self.on_status("PySerial ausente")
                    self.running = False
                    return

                try:
                    self.connection = serial.Serial(port_name, SERIAL_BAUDRATE, timeout=0.2)
                    self.connected_port = port_name
                    time.sleep(2.0)  # Arduino Uno reinicia ao abrir a serial
                    self.connection.reset_input_buffer()
                    self.on_status(f"Arduino conectado em {port_name}")
                except Exception as err:
                    self._close_connection()
                    self.on_status("Falha ao conectar Arduino")
                    self.on_error(f"Não foi possível abrir {port_name}: {err}")
                    time.sleep(2.0)
                    continue

            try:
                raw = self.connection.readline()
                if not raw:
                    continue

                message = raw.decode("utf-8", errors="ignore").strip()
                if not message:
                    continue

                message_upper = message.upper()
                tokens = set(re.findall(r"[A-Z0-9_]+", message_upper))

                normalized_command = None
                if (
                    "D3" in tokens
                    or "REPLAY_CAM2" in tokens
                    or "CAM2" in tokens
                    or "WIFI" in tokens
                    or "PIN3" in tokens
                    or "BTN3" in tokens
                    or "BOTAO3" in tokens
                    or "BOTAO_D3" in tokens
                    or tokens == {"3"}
                ):
                    normalized_command = "D3"
                elif (
                    "D2" in tokens
                    or "REPLAY_CAM1" in tokens
                    or "CAM1" in tokens
                    or "USB" in tokens
                    or "PIN2" in tokens
                    or "BTN2" in tokens
                    or "BOTAO2" in tokens
                    or "BOTAO_D2" in tokens
                    or tokens == {"2"}
                ):
                    normalized_command = "D2"
                elif message_upper == SERIAL_TRIGGER_MESSAGE.upper():
                    normalized_command = SERIAL_TRIGGER_MESSAGE.upper()

                if normalized_command is None:
                    continue

                now = time.time()
                if (now - self._last_trigger_at) * 1000 < SERIAL_DEBOUNCE_MS:
                    continue

                self._last_trigger_at = now
                self.on_trigger(normalized_command)
            except Exception as err:
                current_port = self.connected_port
                self._close_connection()
                self.on_status("Arduino desconectado")
                self.on_error(f"Conexão serial perdida em {current_port}: {err}")
                time.sleep(1.0)


# =============================================================================
# CLASSE: ReplayApp
# Interface grÃ¡fica principal (tkinter)
# =============================================================================
class ReplayApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Sistema de Replay em Buffer")
        self.root.resizable(True, True)
        self.root.configure(bg="#060912")

        # Centralizar e definir tamanho compacto
        self.root.update_idletasks()
        win_w, win_h = 1120, 760
        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()
        x = (scr_w - win_w) // 2
        y = (scr_h - win_h) // 2
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # Inicializar captura e exportador
        self.capture  = FrameCapture(mode=CAPTURE_MODE, source=CAM1_DEVICE_INDEX, label="CAM-1 USB")
        self.capture_cam1 = self.capture
        self.capture_cam2 = None
        self.capture_errors: list[str] = []
        cam2_source = (CAM2_SOURCE_URL or "").strip()
        if CAM2_ENABLED:
            if cam2_source and "IP_DA_CAMERA" not in cam2_source.upper() and "SUA_SENHA" not in cam2_source.upper():
                self.capture_cam2 = FrameCapture(mode="webcam", source=cam2_source, label="CAM-2 WIFI")
            else:
                self.capture_errors.append(
                    "CAM-2 Wi-Fi nÃ£o iniciada: configure CAM2_SOURCE_URL com o RTSP da sua Yoosee."
                )
        self.captures = [self.capture_cam1] + ([self.capture_cam2] if self.capture_cam2 is not None else [])
        self.exporter = ReplayExporter(
            on_progress = self._on_export_progress,
            on_done     = self._on_export_done,
            on_error    = self._on_export_error,
        )
        self.serial_status_text = "Arduino: inicializando..."
        self.serial_trigger = SerialReplayTrigger(
            on_trigger=self._on_serial_trigger,
            on_status=self._set_serial_status,
            on_error=self._on_serial_error,
        )
        self._reported_capture_errors = set()
        self._saved_cards_count = 0
        self._saved_cards = []
        self._saved_paths = set()

        self._build_ui()
        self._load_saved_replays()
        self._start_capture()
        self._start_serial_listener()

        # Atualizar preview a cada 100ms
        self.root.after(100, self._update_preview)

        # Encerrar threads ao fechar a janela
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    def _build_ui(self):
        """ConstrÃ³i todos os widgets da interface."""
        PAD = 18
        BG_ROOT = "#060912"
        BG_PANEL = "#111a2b"
        BG_PANEL_SOFT = "#1a2841"
        BG_INNER = "#0c1424"
        ACCENT = "#f5be68"
        ACCENT_SOFT = "#59d0ff"
        TXT_PRIMARY = "#f4f7ff"
        TXT_MUTED = "#96a9cb"

        # Configurar grid da root: tÃ­tulo fixo | centro expande | bottom fixo
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        # --- TÃ­tulo ---
        title_frame = tk.Frame(self.root, bg=BG_ROOT)
        title_frame.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD - 2, 2))

        tk.Label(
            title_frame, text="REPLAY CONTROL CENTER  |  INFO TECH ARACATUBA",
            font=("Bahnschrift SemiBold", 17),
            fg=ACCENT, bg=BG_ROOT
        ).pack(side="left")

        self.fps_label = tk.Label(
            title_frame, text="FPS: --",
            font=("Segoe UI Semibold", 10),
            fg=TXT_MUTED, bg=BG_ROOT
        )
        self.fps_label.pack(side="right")

        self.settings_btn = tk.Button(
            title_frame,
            text="CONFIGURACOES",
            font=("Segoe UI Semibold", 10),
            fg=ACCENT, bg=BG_ROOT,
            activeforeground="#ffffff", activebackground="#253457",
            relief="flat", bd=0,
            cursor="hand2",
            command=self._open_settings
        )
        self.settings_btn.pack(side="right", padx=(0, 8))
        self.settings_btn.bind("<Enter>", lambda e: self.settings_btn.config(fg="#ffffff"))
        self.settings_btn.bind("<Leave>", lambda e: self.settings_btn.config(fg=ACCENT))

        # --- Container central: preview (50%) e thumbnails (50%) ---
        center = tk.Frame(self.root, bg=BG_ROOT)
        center.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=(8, 6))
        center.grid_rowconfigure(0, weight=3)
        center.grid_rowconfigure(1, weight=2)
        center.grid_columnconfigure(0, weight=1)

        # --- Ãrea superior: preview (esquerda) + mÃ©tricas (direita) ---
        top_split = tk.Frame(center, bg=BG_ROOT)
        top_split.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        top_split.grid_rowconfigure(0, weight=1)
        top_split.grid_columnconfigure(0, weight=6)
        top_split.grid_columnconfigure(1, weight=2)

        # --- Preview das cÃ¢meras (lado esquerdo) ---
        preview_outer = tk.Frame(
            top_split,
            bg=BG_PANEL,
            bd=0,
            highlightthickness=2,
            highlightbackground="#243455",
            highlightcolor=ACCENT
        )
        preview_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        preview_outer.grid_rowconfigure(0, weight=1)
        preview_outer.grid_columnconfigure(0, weight=1)
        preview_outer.grid_propagate(False)

        preview_outer.grid_rowconfigure(0, weight=0)
        preview_outer.grid_rowconfigure(1, weight=1)

        tk.Label(
            preview_outer,
            text="PREVIEW DAS CAMERAS",
            font=("Segoe UI Semibold", 10),
            fg=TXT_PRIMARY,
            bg=BG_PANEL_SOFT,
            anchor="center",
            padx=8,
            pady=6
        ).grid(row=0, column=0, sticky="ew")

        preview_grid = tk.Frame(preview_outer, bg=BG_INNER)
        preview_grid.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        preview_grid.grid_rowconfigure(0, weight=1)
        preview_grid.grid_columnconfigure(0, weight=1, uniform="preview_cols")
        preview_grid.grid_columnconfigure(1, weight=1, uniform="preview_cols")

        cam1_preview_frame = tk.Frame(
            preview_grid,
            bg=BG_INNER,
            highlightthickness=1,
            highlightbackground="#243455"
        )
        cam1_preview_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        cam1_preview_frame.grid_rowconfigure(1, weight=1)
        cam1_preview_frame.grid_columnconfigure(0, weight=1)

        tk.Label(
            cam1_preview_frame,
            text="CAM-1 USB",
            font=("Segoe UI Semibold", 10),
            fg=ACCENT,
            bg=BG_INNER
        ).grid(row=0, column=0, sticky="ew", pady=(6, 2))

        self.preview_cam1_label = tk.Label(
            cam1_preview_frame,
            bg="#060912",
            text="Iniciando CAM-1 USB...",
            font=("Segoe UI", 11),
            fg=TXT_MUTED,
            anchor="center",
            justify="center"
        )
        self.preview_cam1_label.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        self.save_cam1_btn = tk.Button(
            cam1_preview_frame,
            text="SALVAR CAM-1",
            font=("Segoe UI Semibold", 10),
            fg="#1a1306",
            bg=ACCENT,
            activebackground="#e4ab56",
            activeforeground="#1a1306",
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            cursor="hand2",
            command=lambda: self._trigger_replay_save(source="painel", camera_key="cam1")
        )
        self.save_cam1_btn.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))

        cam2_preview_frame = tk.Frame(
            preview_grid,
            bg=BG_INNER,
            highlightthickness=1,
            highlightbackground="#243455"
        )
        cam2_preview_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        cam2_preview_frame.grid_rowconfigure(1, weight=1)
        cam2_preview_frame.grid_columnconfigure(0, weight=1)

        tk.Label(
            cam2_preview_frame,
            text="CAM-2 WIFI",
            font=("Segoe UI Semibold", 10),
            fg=ACCENT_SOFT,
            bg=BG_INNER
        ).grid(row=0, column=0, sticky="ew", pady=(6, 2))

        self.preview_cam2_label = tk.Label(
            cam2_preview_frame,
            bg="#060912",
            text="Aguardando CAM-2 Wi-Fi...",
            font=("Segoe UI", 11),
            fg=TXT_MUTED,
            anchor="center",
            justify="center"
        )
        self.preview_cam2_label.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        self.save_cam2_btn = tk.Button(
            cam2_preview_frame,
            text="SALVAR CAM-2",
            font=("Segoe UI Semibold", 10),
            fg="#06131a",
            bg=ACCENT_SOFT,
            activebackground="#46bfe8",
            activeforeground="#06131a",
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            cursor="hand2",
            command=lambda: self._trigger_replay_save(source="painel", camera_key="cam2")
        )
        self.save_cam2_btn.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))

        # --- Painel de mÃ©tricas em tempo real (lado direito) ---
        metrics_outer = tk.Frame(
            top_split,
            bg=BG_PANEL,
            bd=0,
            highlightthickness=2,
            highlightbackground="#243455",
            highlightcolor=ACCENT
        )
        metrics_outer.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        metrics_outer.grid_rowconfigure(1, weight=1)
        metrics_outer.grid_columnconfigure(0, weight=1)

        tk.Label(
            metrics_outer,
            text="PAINEL DE TELEMETRIA",
            font=("Segoe UI Semibold", 10),
            fg=TXT_PRIMARY,
            bg=BG_PANEL_SOFT,
            anchor="center",
            padx=8,
            pady=6
        ).grid(row=0, column=0, sticky="ew")

        metrics_body = tk.Frame(metrics_outer, bg=BG_INNER)
        metrics_body.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        metrics_body.grid_columnconfigure(0, weight=1)

        def _metric_row(parent, title):
            row = tk.Frame(parent, bg=BG_INNER)
            row.pack(fill="x", pady=4)
            tk.Label(
                row,
                text=title,
                font=("Segoe UI Semibold", 8),
                fg=TXT_MUTED,
                bg=BG_INNER,
                anchor="w"
            ).pack(side="left")
            value = tk.Label(
                row,
                text="--",
                font=("Bahnschrift SemiBold", 10),
                fg=TXT_PRIMARY,
                bg=BG_INNER,
                anchor="e"
            )
            value.pack(side="right")
            return value

        self.metric_mode_value = _metric_row(metrics_body, "Modo")
        self.metric_fps_value = _metric_row(metrics_body, "FPS Atual")
        self.metric_frames_value = _metric_row(metrics_body, "Frames Buffer")
        self.metric_res_value = _metric_row(metrics_body, "Resolução")
        self.metric_buffer_value = _metric_row(metrics_body, "Buffer")
        self.metric_arduino_value = _metric_row(metrics_body, "Arduino")

        # --- Ãrea de thumbnails dos replays salvos ---
        thumb_outer = tk.Frame(
            center,
            bg=BG_PANEL,
            bd=0,
            highlightthickness=2,
            highlightbackground="#243455",
            highlightcolor=ACCENT
        )
        thumb_outer.grid(row=1, column=0, sticky="nsew")
        thumb_outer.grid_rowconfigure(1, weight=1)
        thumb_outer.grid_columnconfigure(0, weight=1)
        thumb_outer.grid_propagate(False)

        tk.Label(
            thumb_outer,
            text="BIBLIOTECA DE REPLAYS",
            font=("Segoe UI Semibold", 10),
            fg=TXT_PRIMARY, bg=BG_PANEL_SOFT,
            anchor="center", padx=8, pady=6
        ).grid(row=0, column=0, sticky="ew")

        # Canvas + scrollbar vertical para as miniaturas
        thumb_scroll_frame = tk.Frame(thumb_outer, bg=BG_INNER)
        thumb_scroll_frame.grid(row=1, column=0, sticky="nsew")
        thumb_scroll_frame.grid_rowconfigure(0, weight=1)
        thumb_scroll_frame.grid_columnconfigure(0, weight=1)
        thumb_scroll_frame.grid_columnconfigure(1, weight=0)

        self.thumb_canvas = tk.Canvas(
            thumb_scroll_frame,
            bg=BG_INNER,
            highlightthickness=2,
            highlightbackground="#243455",
            highlightcolor=ACCENT
        )
        self.thumb_scrollbar = tk.Scrollbar(
            thumb_scroll_frame,
            orient="vertical",
            command=self.thumb_canvas.yview
        )
        self.thumb_canvas.configure(yscrollcommand=self.thumb_scrollbar.set)

        self.thumb_scrollbar.grid(row=0, column=1, sticky="ns")
        self.thumb_canvas.grid(row=0, column=0, sticky="nsew")

        # Frame interno onde os widgets de thumbnail sÃ£o inseridos
        self.thumb_inner = tk.Frame(self.thumb_canvas, bg=BG_INNER)
        self.thumb_inner.grid_columnconfigure(0, weight=1)
        self.thumb_inner.grid_columnconfigure(1, weight=1)
        self._thumb_canvas_window = self.thumb_canvas.create_window(
            (0, 0), window=self.thumb_inner, anchor="nw"
        )

        def _on_thumb_inner_configure(event):
            self.thumb_canvas.configure(
                scrollregion=self.thumb_canvas.bbox("all")
            )
        self.thumb_inner.bind("<Configure>", _on_thumb_inner_configure)

        def _on_thumb_canvas_configure(event):
            self.thumb_canvas.itemconfigure(self._thumb_canvas_window, width=event.width)
        self.thumb_canvas.bind("<Configure>", _on_thumb_canvas_configure)

        def _on_thumb_mousewheel(event):
            self.thumb_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.thumb_canvas.bind("<MouseWheel>", _on_thumb_mousewheel)
        self.thumb_inner.bind("<MouseWheel>", _on_thumb_mousewheel)

        # Placeholder quando nÃ£o hÃ¡ replays ainda
        self._thumb_placeholder = tk.Label(
            self.thumb_inner,
            text="SEM REPLAYS AINDA\nOs videos exportados aparecerao aqui automaticamente.",
            font=("Segoe UI Semibold", 10),
            fg=TXT_MUTED, bg=BG_INNER,
            pady=44, padx=20
        )
        self._thumb_placeholder.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # --- Bottom frame ---
        bottom_frame = tk.Frame(self.root, bg=BG_ROOT)
        bottom_frame.grid(row=2, column=0, sticky="ew")

        # --- Status do buffer ---
        status_frame = tk.Frame(
            bottom_frame,
            bg=BG_PANEL_SOFT,
            bd=0,
            highlightthickness=2,
            highlightbackground="#243455"
        )
        status_frame.pack(fill="x", padx=PAD, pady=(0, 8))

        self.status_label = tk.Label(
            status_frame,
            text="Aguardando...",
            font=("Segoe UI", 10),
            fg=TXT_PRIMARY, bg=BG_PANEL_SOFT,
            anchor="w", padx=10, pady=6
        )
        self.status_label.pack(fill="x")

        # --- Barra de progresso (oculta por padrÃ£o) ---
        self.progress_var = tk.DoubleVar(value=0)
        # Estilo da barra
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "neo.Horizontal.TProgressbar",
            troughcolor=BG_PANEL,
            background=ACCENT_SOFT,
            bordercolor="#243455",
            lightcolor=ACCENT_SOFT,
            darkcolor="#3ab8e8"
        )
        self.progress_frame = tk.Frame(bottom_frame, bg=BG_ROOT)
        self.progress_frame.pack(padx=PAD, pady=(0, 4))

        self.progress_bar_widget = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=1.0,
            mode="determinate",
            length=PREVIEW_W,
            style="neo.Horizontal.TProgressbar"
        )
        # A barra fica oculta atÃ© a exportaÃ§Ã£o comeÃ§ar
        self.progress_bar_widget.pack()
        self.progress_frame.pack_forget()

        self.progress_status = tk.Label(
            bottom_frame, text="",
            font=("Segoe UI Semibold", 9),
            fg=ACCENT_SOFT, bg=BG_ROOT
        )

        # --- NotificaÃ§Ã£o inline (substitui messagebox) ---
        self.notify_label = tk.Label(
            bottom_frame, text="",
            font=("Segoe UI Semibold", 9),
            fg=TXT_PRIMARY, bg=BG_ROOT,
            wraplength=680, justify="center"
        )
        self.notify_label.pack(pady=(0, 4))

        # --- RodapÃ© ---
        mode_text = "TELA" if CAPTURE_MODE == "screen" else "WEBCAM"
        mins = REPLAY_SECONDS // 60
        secs = REPLAY_SECONDS % 60
        self.footer_label = tk.Label(
            bottom_frame,
            text=f"Info Tech Araçatuba. Modo: {mode_text}  |  Buffer max: {mins}min {secs:02d}s  |  FPS alvo: {TARGET_FPS}",
            font=("Segoe UI", 9),
            fg=TXT_MUTED, bg=BG_ROOT
        )
        self.footer_label.pack(pady=(0, 4))

    # ------------------------------------------------------------------
    def _start_capture(self):
        """Inicia a captura e trata erros de inicializaÃ§Ã£o."""
        for capture in self.captures:
            try:
                capture.start()
            except RuntimeError as e:
                self._show_notify(f"âœ– Erro de captura: {e}", color="#e94560")

        for msg in self.capture_errors:
            self._show_notify(msg, color="#f5be68", duration_ms=8000)

    # ------------------------------------------------------------------
    def _start_serial_listener(self):
        """Inicia a escuta do Arduino, se a integração serial estiver habilitada."""
        if not SERIAL_ENABLED:
            self._set_serial_status("Arduino desativado")
            return

        if serial is None:
            self._set_serial_status("PySerial ausente")
            self._show_notify(
                "Integração com Arduino indisponível: instale a dependência pyserial.",
                color="#e94560"
            )
            return

        self.serial_trigger.start()

    # ------------------------------------------------------------------
    def _set_serial_status(self, status: str):
        """Atualiza o status visível da integração com Arduino."""
        self.serial_status_text = status

    # ------------------------------------------------------------------
    def _on_serial_error(self, msg: str):
        """Mostra erros da integração serial na interface principal."""
        self.root.after(0, lambda: self._show_notify(f"Arduino: {msg}", color="#e94560"))

    # ------------------------------------------------------------------
    def _on_serial_trigger(self, command: str):
        """Dispara o salvamento do replay a partir do comando vindo do Arduino."""
        self.root.after(0, lambda cmd=command: self._handle_serial_trigger(cmd))

    # ------------------------------------------------------------------
    def _handle_serial_trigger(self, command: str):
        """Converte o comando serial recebido no replay da cÃ¢mera correta."""
        camera_key = "cam2" if command in {"REPLAY_CAM2", "D3"} else "cam1"
        self._trigger_replay_save(source="arduino", camera_key=camera_key)

    # ------------------------------------------------------------------
    def _get_capture_for_camera(self, camera_key: str):
        """Retorna a instÃ¢ncia de captura da cÃ¢mera solicitada."""
        if camera_key == "cam2":
            return self.capture_cam2
        return self.capture_cam1

    # ------------------------------------------------------------------
    def _render_capture_preview(self, capture, target_label: tk.Label, fallback_text: str):
        """Renderiza o preview de uma cÃ¢mera em um widget de preview."""
        if capture is None:
            target_label.configure(image="", text=fallback_text)
            target_label.image = None
            return "--", "--", "--", "--"

        frame = None
        frame_res_text = "--"
        with capture.lock:
            if capture.latest_frame is not None:
                frame = capture.latest_frame.copy()

        if frame is not None:
            fh, fw = frame.shape[:2]
            frame_res_text = f"{fw}x{fh}"
            lw = target_label.winfo_width()
            lh = target_label.winfo_height()
            max_w = (PREVIEW_W // 2) if lw <= 1 else max(1, lw)
            max_h = PREVIEW_H if lh <= 1 else max(1, lh)
            # Cover: escala pelo maior fator para preencher todo o espaço sem bordas pretas
            scale = max(max_w / fw, max_h / fh)
            scaled_w = max(1, int(fw * scale))
            scaled_h = max(1, int(fh * scale))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((scaled_w, scaled_h), Image.LANCZOS)
            # Crop centralizado para o tamanho exato do label
            x0 = (scaled_w - max_w) // 2
            y0 = (scaled_h - max_h) // 2
            img = img.crop((x0, y0, x0 + max_w, y0 + max_h))
            photo = ImageTk.PhotoImage(img)
            target_label.configure(image=photo, text="")
            target_label.image = photo
        else:
            status_message = capture.status_text or fallback_text
            if capture.last_error:
                status_message = f"{capture.label}\n{capture.last_error}"
            target_label.configure(image="", text=status_message)
            target_label.image = None

        duration = capture.buffer_duration
        mins = int(duration) // 60
        secs = int(duration) % 60
        n_frames = len(capture.buffer)
        fps_real = capture.actual_fps
        return frame_res_text, f"{fps_real:.1f}", f"{n_frames:,}", f"{mins:02d}:{secs:02d}"

    # ------------------------------------------------------------------
    def _update_preview(self):
        """Atualiza o preview e os labels de status â€” chamado a cada 100ms."""
        cam1_res, cam1_fps, cam1_frames, cam1_buffer = self._render_capture_preview(
            self.capture_cam1,
            self.preview_cam1_label,
            "CAM-1 USB\nAguardando imagem..."
        )
        cam2_res, cam2_fps, cam2_frames, cam2_buffer = self._render_capture_preview(
            self.capture_cam2,
            self.preview_cam2_label,
            "CAM-2 WIFI\nConfigure a fonte Wi-Fi"
        )

        for capture in self.captures:
            if capture.last_error and capture.label not in self._reported_capture_errors:
                self._reported_capture_errors.add(capture.label)
                self._show_notify(f"{capture.label}: {capture.last_error}", color="#e94560", duration_ms=8000)

        self.fps_label.config(text=f"FPS C1: {cam1_fps}  |  FPS C2: {cam2_fps}")
        self.status_label.config(
            text=f"CAM-1 Buffer: {cam1_buffer}  |  CAM-2 Buffer: {cam2_buffer}  |  Arduino: {self.serial_status_text}"
        )
        self.metric_mode_value.config(text="USB + WIFI")
        self.metric_fps_value.config(text=f"C1 {cam1_fps} | C2 {cam2_fps}")
        self.metric_frames_value.config(text=f"C1 {cam1_frames} | C2 {cam2_frames}")
        self.metric_res_value.config(text=f"C1 {cam1_res} | C2 {cam2_res}")
        self.metric_buffer_value.config(text=f"C1 {cam1_buffer} | C2 {cam2_buffer}")
        self.metric_arduino_value.config(text=self.serial_status_text)

        # Agendar prÃ³xima atualizaÃ§Ã£o
        self.root.after(100, self._update_preview)

    # ------------------------------------------------------------------
    def _on_save_clicked(self):
        """Callback do botÃ£o Salvar Replay."""
        self._trigger_replay_save(source="painel", camera_key="cam1")

    # ------------------------------------------------------------------
    def _trigger_replay_save(self, source: str = "painel", camera_key: str = "cam1"):
        """Executa o mesmo fluxo de salvamento para UI e Arduino."""
        if self.exporter.exporting:
            if source == "arduino":
                self._show_notify("Arduino acionado, mas já existe uma exportação em andamento.", color="#f5be68")
            return

        capture = self._get_capture_for_camera(camera_key)
        if capture is None:
            if camera_key == "cam2":
                self._show_notify(
                    "CAM-2 Wi-Fi ainda nÃ£o estÃ¡ pronta. Configure CAM2_SOURCE_URL no config.json.",
                    color="#e94560"
                )
            else:
                self._show_notify("CAM-1 USB nÃ£o estÃ¡ disponÃ­vel.", color="#e94560")
            return

        replay_label = "replay_cam2" if camera_key == "cam2" else "replay_cam1"
        camera_text = "CAM-2 Wi-Fi" if camera_key == "cam2" else "CAM-1 USB"

        self.save_cam1_btn.config(state="disabled")
        self.save_cam2_btn.config(state="disabled")

        # Mostrar barra de progresso
        self.progress_var.set(0)
        self.progress_frame.pack(padx=12, pady=(0, 4))
        if source == "arduino":
            self.progress_status.config(text=f"Exportando replay acionado pelo Arduino ({camera_text})...")
            self._show_notify(f"Botão do Arduino acionou o replay da {camera_text}.", color="#59d0ff")
        else:
            self.progress_status.config(text=f"Exportando replay da {camera_text}...")
        self.progress_status.pack()

        # Tirar snapshot do buffer e iniciar exportaÃ§Ã£o assÃ­ncrona
        snapshot = capture.get_snapshot()
        self.exporter.export_async(snapshot, replay_label=replay_label)

    # ------------------------------------------------------------------
    def _on_export_progress(self, pct: float):
        """Atualiza a barra de progresso (chamado da thread de exportaÃ§Ã£o)."""
        self.root.after(0, lambda: self.progress_var.set(pct))
        self.root.after(0, lambda: self.progress_status.config(
            text=f"Exportando... {int(pct*100)}%"
        ))

    # ------------------------------------------------------------------
    def _on_export_done(self, filepath: str, thumb_path):
        """Chamado quando a exportaÃ§Ã£o termina com sucesso."""
        def _ui():
            self._reset_save_button()
            self.progress_frame.pack_forget()
            self.progress_status.pack_forget()
            nome = os.path.basename(filepath)
            self._show_notify(f"Replay salvo: {nome}", color="#00d26a")
            self._add_thumbnail(filepath, thumb_path)
        self.root.after(0, _ui)

    # ------------------------------------------------------------------
    def _load_saved_replays(self):
        """Carrega no painel os replays jÃ¡ existentes na pasta de saÃ­da."""
        os.makedirs(SAVED_DIR, exist_ok=True)
        replay_files = [
            os.path.join(SAVED_DIR, name)
            for name in os.listdir(SAVED_DIR)
            if name.lower().endswith(".mp4")
        ]
        replay_files.sort(key=os.path.getmtime, reverse=False)

        for filepath in replay_files:
            thumb_path = os.path.splitext(filepath)[0] + "_thumb.jpg"
            self._add_thumbnail(filepath, thumb_path if os.path.exists(thumb_path) else None)

    # ------------------------------------------------------------------
    def _add_thumbnail(self, filepath: str, thumb_path):
        """Cria e insere uma miniatura clicÃ¡vel na Ã¡rea de replays salvos."""
        filepath = os.path.abspath(filepath)
        if not os.path.exists(filepath) or filepath in self._saved_paths:
            return
        self._saved_paths.add(filepath)

        # Remover placeholder na primeira miniatura
        if self._thumb_placeholder.winfo_ismapped():
            self._thumb_placeholder.grid_remove()

        # Carregar imagem da thumbnail
        if thumb_path and os.path.exists(thumb_path):
            img_bgr = cv2.imread(thumb_path)
            if img_bgr is not None:
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb).resize((160, 90), Image.LANCZOS)
            else:
                pil_img = Image.new("RGB", (160, 90), color=(20, 20, 40))
        else:
            pil_img = Image.new("RGB", (160, 90), color=(20, 20, 40))

        photo = ImageTk.PhotoImage(pil_img)

        # Container do card
        card = tk.Frame(
            self.thumb_inner,
            bg="#111a2b",
            bd=0,
            highlightthickness=2,
            highlightbackground="#243455",
            highlightcolor="#f5be68",
            cursor="hand2"
        )
        card.configure(width=186, height=185)
        card.grid_propagate(False)
        self._saved_cards.insert(0, card)
        for idx, c in enumerate(self._saved_cards):
            c.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="n")
        self._saved_cards_count = len(self._saved_cards)

        # Imagem clicÃ¡vel
        img_label = tk.Label(card, image=photo, bg="#111a2b", cursor="hand2")
        img_label.image = photo  # manter referÃªncia
        img_label.pack(padx=6, pady=(7, 2))

        # Nome do arquivo (truncado)
        nome = os.path.basename(filepath)
        nome_curto = nome[:20] + "..." if len(nome) > 21 else nome
        nome_label = tk.Label(
            card, text=nome_curto,
            font=("Segoe UI Semibold", 9),
            fg="#f4f7ff", bg="#111a2b"
        )
        nome_label.pack(pady=(0, 1))

        data_salvamento = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%d/%m/%Y %H:%M")
        data_label = tk.Label(
            card,
            text=data_salvamento,
            font=("Segoe UI", 8),
            fg="#96a9cb", bg="#111a2b"
        )
        data_label.pack(pady=(0, 2))

        tipo_label = tk.Label(
            card,
            text="MP4",
            font=("Segoe UI Semibold", 8),
            fg="#1a1306", bg="#f5be68",
            padx=6, pady=1
        )
        tipo_label.pack(pady=(0, 3))

        # BotÃµes de aÃ§Ã£o â€” sem propagar o clique para _open_video do card
        actions_frame = tk.Frame(card, bg="#111a2b")
        actions_frame.pack(pady=(0, 6), fill="x", padx=6)

        wa_btn = tk.Button(
            actions_frame,
            text="📲 WhatsApp",  # Corrigido para UTF-8
            font=("Segoe UI Semibold", 9),
            fg="#ffffff", bg="#25D366",
            activeforeground="#ffffff", activebackground="#1ebe5d",
            relief="flat", bd=0,
            padx=8, pady=5,
            cursor="hand2"
        )  # Botão WhatsApp — sem propagar o clique para _open_video do card
        wa_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        delete_btn = tk.Button(
            actions_frame,
            text="🗑 Excluir",
            font=("Segoe UI Semibold", 9),
            fg="#ffffff", bg="#e94560",
            activeforeground="#ffffff", activebackground="#cf3550",
            relief="flat", bd=0,
            padx=8, pady=5,
            cursor="hand2"
        )
        delete_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        def _wa_press(e):
            wa_btn.config(relief="sunken")
            return "break"

        def _wa_release(e, fp=filepath):
            wa_btn.config(relief="flat")
            self._send_whatsapp(fp)
            return "break"

        wa_btn.bind("<Button-1>",        _wa_press)
        wa_btn.bind("<ButtonRelease-1>", _wa_release)
        wa_btn.bind("<Enter>",  lambda e: wa_btn.config(bg="#1ebe5d"))
        wa_btn.bind("<Leave>",  lambda e: wa_btn.config(bg="#25D366"))

        def _delete_press(e):
            delete_btn.config(relief="sunken")
            return "break"

        def _delete_release(e, fp=filepath, tp=thumb_path, card_widget=card):
            delete_btn.config(relief="flat")
            self._delete_replay(fp, tp, card_widget)
            return "break"

        delete_btn.bind("<Button-1>", _delete_press)
        delete_btn.bind("<ButtonRelease-1>", _delete_release)
        delete_btn.bind("<Enter>", lambda e: delete_btn.config(bg="#cf3550"))
        delete_btn.bind("<Leave>", lambda e: delete_btn.config(bg="#e94560"))

        # Ãcone play sobreposto via bind de hover
        def _on_enter(e):
            card.config(bg="#1d2a42")
            img_label.config(bg="#1d2a42")
            nome_label.config(bg="#1d2a42")
            data_label.config(bg="#1d2a42")

        def _on_leave(e):
            card.config(bg="#111a2b")
            img_label.config(bg="#111a2b")
            nome_label.config(bg="#111a2b")
            data_label.config(bg="#111a2b")

        def _open_video(e):
            threading.Thread(
                target=self._play_video_window,
                args=(filepath,),
                daemon=True
            ).start()

        for widget in (card, img_label, nome_label, data_label, tipo_label):
            widget.bind("<Enter>",  _on_enter)
            widget.bind("<Leave>",  _on_leave)
            widget.bind("<Button-1>", _open_video)

        # Atualizar scrollregion
        self.thumb_canvas.update_idletasks()
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))

    # ------------------------------------------------------------------
    def _on_export_error(self, msg: str):
        """Chamado quando ocorre um erro na exportaÃ§Ã£o."""
        def _ui():
            self._reset_save_button()
            self.progress_frame.pack_forget()
            self.progress_status.pack_forget()
            self._show_notify(f"Erro: {msg}", color="#e94560")
        self.root.after(0, _ui)

    # ------------------------------------------------------------------
    def _reset_save_button(self):
        """Restaura o botÃ£o ao estado normal."""
        self.save_cam1_btn.config(state="normal")
        self.save_cam2_btn.config(state="normal")

    # ------------------------------------------------------------------
    def _show_notify(self, msg: str, color: str = "#e94560", duration_ms: int = 5000):
        """Exibe uma notificaÃ§Ã£o inline no painel, some automaticamente."""
        self.notify_label.config(text=msg, fg=color)
        self.root.after(duration_ms, lambda: self.notify_label.config(text=""))

    # ------------------------------------------------------------------
    def _delete_replay(self, filepath: str, thumb_path, card_widget: tk.Widget):
        """Exclui um replay salvo diretamente pelo painel."""
        nome = os.path.basename(filepath)
        confirm = messagebox.askyesno(
            "Excluir Replay",
            f"Deseja excluir o replay '{nome}'?"
        )
        if not confirm:
            return

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)
        except Exception as err:
            self._show_notify(f"Erro ao excluir replay: {err}", color="#e94560")
            return

        self._saved_paths.discard(os.path.abspath(filepath))
        self._saved_cards = [c for c in self._saved_cards if c is not card_widget]
        card_widget.destroy()

        if not any(child.winfo_exists() and child is not self._thumb_placeholder for child in self.thumb_inner.winfo_children()):
            self._thumb_placeholder.grid()

        self.thumb_canvas.update_idletasks()
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))
        self._show_notify(f"Replay excluído: {nome}", color="#00d26a")

    # ------------------------------------------------------------------
    def _open_settings(self):
        """Abre a janela modal de configuracoes do sistema."""
        global REPLAY_SECONDS, TARGET_FPS, JPEG_QUALITY, CAPTURE_MODE, BUFFER_MAXLEN

        settings_win = tk.Toplevel(self.root)
        settings_win.title("Configuracoes")
        settings_win.configure(bg="#060912")
        settings_win.resizable(False, False)
        settings_win.grab_set()

        sw, sh = 460, 420
        px = self.root.winfo_x() + (self.root.winfo_width() - sw) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - sh) // 2
        settings_win.geometry(f"{sw}x{sh}+{px}+{py}")

        BG = "#060912"
        BG_P = "#111a2b"
        BG_IN = "#0c1424"
        ACCENT = "#f5be68"
        TXT = "#f4f7ff"
        TXT_M = "#96a9cb"

        tk.Label(
            settings_win,
            text="PAINEL DE CONFIGURACOES",
            font=("Bahnschrift SemiBold", 14),
            fg=ACCENT, bg=BG
        ).pack(pady=(18, 10))

        body = tk.Frame(
            settings_win,
            bg=BG_P,
            padx=18,
            pady=14,
            highlightthickness=2,
            highlightbackground="#243455"
        )
        body.pack(fill="x", padx=18)

        def _row(parent, label_text):
            f = tk.Frame(parent, bg=BG_P)
            f.pack(fill="x", pady=8)
            tk.Label(
                f,
                text=label_text,
                font=("Segoe UI Semibold", 10),
                fg=TXT_M, bg=BG_P, width=22, anchor="w"
            ).pack(side="left")
            return f

        r1 = _row(body, "Tempo de Replay (s):")
        replay_var = tk.IntVar(value=REPLAY_SECONDS)
        tk.Spinbox(
            r1, from_=30, to=600, increment=30,
            textvariable=replay_var, width=6,
            font=("Segoe UI Semibold", 10),
            fg=TXT, bg=BG_IN, insertbackground=ACCENT,
            buttonbackground="#2b3d62", relief="flat"
        ).pack(side="left")
        tk.Label(r1, text="seg", font=("Segoe UI", 9), fg=TXT_M, bg=BG_P).pack(side="left", padx=4)

        r2 = _row(body, "FPS Alvo:")
        fps_var = tk.IntVar(value=TARGET_FPS)
        tk.Spinbox(
            r2, values=(15, 24, 30, 60, 120),
            textvariable=fps_var, width=6,
            font=("Segoe UI Semibold", 10),
            fg=TXT, bg=BG_IN, insertbackground=ACCENT,
            buttonbackground="#2b3d62", relief="flat"
        ).pack(side="left")

        r3 = _row(body, "Qualidade JPEG (0-100):")
        quality_var = tk.IntVar(value=JPEG_QUALITY)
        tk.Spinbox(
            r3, from_=30, to=100, increment=5,
            textvariable=quality_var, width=6,
            font=("Segoe UI Semibold", 10),
            fg=TXT, bg=BG_IN, insertbackground=ACCENT,
            buttonbackground="#2b3d62", relief="flat"
        ).pack(side="left")

        r4 = _row(body, "Modo de Captura:")
        mode_var = tk.StringVar(value=CAPTURE_MODE)
        for mode_val, mode_lbl in (("webcam", "Webcam"), ("screen", "Tela")):
            tk.Radiobutton(
                r4, text=mode_lbl,
                variable=mode_var, value=mode_val,
                font=("Segoe UI", 9),
                fg=TXT, bg=BG_P,
                selectcolor="#2b3d62",
                activebackground=BG_P, activeforeground=ACCENT
            ).pack(side="left", padx=6)

        fb_label = tk.Label(
            settings_win, text="",
            font=("Segoe UI Semibold", 9),
            fg="#00d26a", bg=BG
        )
        fb_label.pack(pady=(12, 0))

        def _apply():
            global REPLAY_SECONDS, TARGET_FPS, JPEG_QUALITY, CAPTURE_MODE, BUFFER_MAXLEN
            try:
                new_replay  = int(replay_var.get())
                new_fps     = int(fps_var.get())
                new_quality = int(quality_var.get())
                new_mode    = mode_var.get().strip().lower()
            except (ValueError, tk.TclError):
                fb_label.config(text="Valores invalidos.", fg="#e94560")
                return

            if new_mode not in ("webcam", "screen"):
                fb_label.config(text="Modo de captura invalido.", fg="#e94560")
                return
            if not (30 <= new_replay <= 3600):
                fb_label.config(text="Tempo deve ficar entre 30s e 3600s.", fg="#e94560")
                return
            if not (1 <= new_fps <= 240):
                fb_label.config(text="FPS deve ficar entre 1 e 240.", fg="#e94560")
                return
            if not (30 <= new_quality <= 100):
                fb_label.config(text="Qualidade JPEG deve ficar entre 30 e 100.", fg="#e94560")
                return

            mode_changed = (new_mode != CAPTURE_MODE)
            fps_changed = (new_fps != TARGET_FPS)

            REPLAY_SECONDS = new_replay
            TARGET_FPS     = new_fps
            JPEG_QUALITY   = new_quality
            CAPTURE_MODE   = new_mode
            BUFFER_MAXLEN  = TARGET_FPS * REPLAY_SECONDS

            # Redimensionar buffer circular com novo tamanho
            for capture in self.captures:
                capture.resize_buffer(BUFFER_MAXLEN)

            # Reiniciar captura quando modo ou FPS mudar, para aplicar imediatamente.
            if mode_changed or fps_changed:
                self.capture_cam1.stop()
                self.capture_cam1.mode    = CAPTURE_MODE
                self.capture_cam1.running = False
                self.capture_cam1.start()

                if fps_changed and self.capture_cam2 is not None:
                    self.capture_cam2.stop()
                    self.capture_cam2.running = False
                    self.capture_cam2.start()

            # Atualizar rodapÃ© da janela principal
            ft = "TELA" if CAPTURE_MODE == "screen" else "WEBCAM"
            mins = REPLAY_SECONDS // 60
            secs = REPLAY_SECONDS %  60
            self.footer_label.config(
                text=(
                    f"Modo: {ft}  |  "
                    f"Buffer max: {mins}min {secs:02d}s  |  "
                    f"FPS alvo: {TARGET_FPS}"
                )
            )

            fb_label.config(text="Configuracoes aplicadas!", fg="#00d26a")
            _save_config()
            settings_win.after(1400, settings_win.destroy)

        apply_btn = tk.Button(
            settings_win,
            text="APLICAR CONFIGURACOES",
            font=("Bahnschrift SemiBold", 11),
            fg="#1a1306", bg=ACCENT,
            activebackground="#e4ab56", activeforeground="#1a1306",
            relief="flat", bd=0,
            padx=22, pady=10,
            cursor="hand2",
            command=_apply
        )
        apply_btn.pack(pady=(10, 20))
        apply_btn.bind("<Enter>", lambda e: apply_btn.config(bg="#e4ab56"))
        apply_btn.bind("<Leave>", lambda e: apply_btn.config(bg=ACCENT))

    # ------------------------------------------------------------------
    def _send_whatsapp(self, filepath: str):
        """Abre WhatsApp Web direcionado ao numero informado e copia o caminho do arquivo."""
        import webbrowser

        dialog = tk.Toplevel(self.root)
        dialog.title("Enviar via WhatsApp")
        dialog.configure(bg="#060912")
        dialog.resizable(False, False)
        dialog.grab_set()

        sw, sh = 430, 330
        px = self.root.winfo_x() + (self.root.winfo_width()  - sw) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - sh) // 2
        dialog.geometry(f"{sw}x{sh}+{px}+{py}")

        BG      = "#060912"
        BG_P    = "#111a2b"
        ACCENT  = "#f5be68"
        TXT     = "#f4f7ff"
        TXT_M   = "#96a9cb"
        WA_GRN  = "#25D366"
        WA_DARK = "#1ebe5d"

        content = tk.Frame(
            dialog,
            bg=BG_P,
            highlightthickness=2,
            highlightbackground="#243455",
            padx=14,
            pady=12
        )
        content.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            content,
            text="ENVIAR VIA WHATSAPP",
            font=("Bahnschrift SemiBold", 13),
            fg=WA_GRN, bg=BG_P
        ).pack(pady=(4, 6))

        tk.Label(
            content,
            text="Numero com DDI + DDD (ex: 5518999998888):",
            font=("Segoe UI", 9),
            fg=TXT_M, bg=BG_P
        ).pack()

        phone_var = tk.StringVar()
        phone_entry = tk.Entry(
            content,
            textvariable=phone_var,
            width=26,
            font=("Segoe UI Semibold", 13),
            fg=TXT, bg="#0c1424",
            insertbackground=ACCENT,
            relief="flat",
            justify="center"
        )
        phone_entry.pack(pady=8, ipady=4)
        phone_entry.focus_set()

        # Arquivo selecionado
        nome = os.path.basename(filepath)
        nome_curto = nome[:36] + "..." if len(nome) > 37 else nome
        tk.Label(
            content,
            text=f"Arquivo: {nome_curto}",
            font=("Segoe UI", 8),
            fg=TXT_M, bg=BG_P
        ).pack(pady=(0, 2))

        info_label = tk.Label(
            content, text="",
            font=("Segoe UI Semibold", 8),
            fg=WA_GRN, bg=BG_P,
            wraplength=360, justify="center"
        )
        info_label.pack(pady=(2, 0))

        def _copy_path():
            dialog.clipboard_clear()
            dialog.clipboard_append(filepath)
            dialog.update()
            self._show_notify("Caminho do arquivo copiado!", color="#25D366")

        def _open_wa():
            raw = phone_var.get().strip()
            phone = "".join(c for c in raw if c.isdigit())
            if len(phone) < 10:
                info_label.config(
                    text="Numero invalido. Use formato: 5518999998888",
                    fg="#e94560"
                )
                return
            import subprocess, platform
            url = f"https://wa.me/{phone}"
            webbrowser.open(url)
            # Abrir Explorer com o arquivo jÃ¡ selecionado (Windows) ou gerenciador de arquivos
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{filepath}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", filepath])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(filepath)])
            info_label.config(
                text=(
                    "WhatsApp e pasta abertos!\n"
                    "Arraste o video da pasta para o WhatsApp e envie."
                ),
                fg=WA_GRN
            )

        btn_frame = tk.Frame(content, bg=BG_P)
        btn_frame.pack(pady=(8, 16))

        copy_btn = tk.Button(
            btn_frame,
            text="Copiar Caminho",
            font=("Segoe UI Semibold", 9),
            fg="#1a1306", bg=ACCENT,
            activebackground="#e4ab56", activeforeground="#1a1306",
            relief="flat", bd=0,
            padx=10, pady=8,
            cursor="hand2",
            command=_copy_path
        )
        copy_btn.pack(side="left", padx=6)
        copy_btn.bind("<Enter>", lambda e: copy_btn.config(bg="#e4ab56"))
        copy_btn.bind("<Leave>", lambda e: copy_btn.config(bg=ACCENT))

        send_btn = tk.Button(
            btn_frame,
            text="Abrir WhatsApp Web",
            font=("Segoe UI Semibold", 9),
            fg="#ffffff", bg=WA_GRN,
            activebackground=WA_DARK, activeforeground="#ffffff",
            relief="flat", bd=0,
            padx=10, pady=8,
            cursor="hand2",
            command=_open_wa
        )
        send_btn.pack(side="left", padx=6)
        send_btn.bind("<Enter>", lambda e: send_btn.config(bg=WA_DARK))
        send_btn.bind("<Leave>", lambda e: send_btn.config(bg=WA_GRN))

        # Permitir disparar com Enter
        phone_entry.bind("<Return>", lambda e: _open_wa())

    # ------------------------------------------------------------------
    def _play_video_window(self, filepath: str):
        """Reproduz um vídeo salvo em janela OpenCV padronizada (960x540)."""
        PLAYBACK_W = 960
        PLAYBACK_H = 540
        win_name = os.path.basename(filepath)
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            self.root.after(0, lambda: self._show_notify(
                "Não foi possível abrir o vídeo.", color="#e94560"
            ))
            return
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        delay = max(1, int(1000 / fps))
        cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_name, PLAYBACK_W, PLAYBACK_H)
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                cv2.imshow(win_name, frame)
                key = cv2.waitKey(delay) & 0xFF
                if key == 27 or cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            cap.release()
            cv2.destroyWindow(win_name)

    # ------------------------------------------------------------------
    def _on_close(self):
        """Para as threads e fecha a janela corretamente."""
        self.serial_trigger.stop()
        for capture in self.captures:
            capture.stop()
        self.root.destroy()


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================
def main():
    root = tk.Tk()
    app  = ReplayApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
