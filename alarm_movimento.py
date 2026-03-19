import argparse
import datetime as dt
import threading
import time
from pathlib import Path

import cv2
import numpy as np

try:
    import winsound
except ImportError:
    winsound = None


class AlarmPlayer:
    def __init__(self, beep_hz: int = 1800, beep_ms: int = 300, pause_ms: int = 200) -> None:
        self.beep_hz = beep_hz
        self.beep_ms = beep_ms
        self.pause_ms = pause_ms
        self._stop_event = threading.Event()
        self._thread = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def _play_loop(self) -> None:
        while not self._stop_event.is_set():
            if winsound is not None:
                winsound.Beep(self.beep_hz, self.beep_ms)
            else:
                print("\a", end="", flush=True)
                time.sleep(self.beep_ms / 1000)

            time.sleep(self.pause_ms / 1000)


class MotionAlarmSystem:
    def __init__(
        self,
        camera_index: int,
        min_area: int,
        cooldown_sec: float,
        confirm_frames: int,
    ) -> None:
        self.camera_index = camera_index
        self.min_area = min_area
        self.cooldown_sec = cooldown_sec
        self.confirm_frames = confirm_frames

        self.capture = cv2.VideoCapture(self.camera_index)
        self.bg_subtractor = self._new_bg_subtractor()
        self.alarm_player = AlarmPlayer()

        self.armed = True
        self.alarm_active = False
        self.motion_frames = 0
        self.last_trigger_time = 0.0

        self.capture_dir = Path("captures")
        self.capture_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _new_bg_subtractor() -> cv2.BackgroundSubtractor:
        return cv2.createBackgroundSubtractorMOG2(history=600, varThreshold=25, detectShadows=True)

    def _save_capture(self, frame: np.ndarray) -> str:
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.capture_dir / f"movimento_{timestamp}.jpg"
        cv2.imwrite(str(file_path), frame)
        return str(file_path)

    def _process_frame(self, frame: np.ndarray):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fg_mask = self.bg_subtractor.apply(gray)

        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
        clean = cv2.dilate(clean, kernel, iterations=2)

        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            motion_boxes.append((x, y, w, h, int(area)))

        return clean, motion_boxes

    def _draw_hud(self, frame: np.ndarray, boxes, triggered: bool) -> None:
        for x, y, w, h, area in boxes:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 220, 255), 2)
            cv2.putText(
                frame,
                f"Area: {area}",
                (x, max(y - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 220, 255),
                1,
                cv2.LINE_AA,
            )

        armed_text = "ARMADO" if self.armed else "DESARMADO"
        armed_color = (0, 220, 0) if self.armed else (0, 0, 220)

        cv2.putText(frame, f"Status: {armed_text}", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, armed_color, 2)
        cv2.putText(
            frame,
            f"Frames com movimento: {self.motion_frames}/{self.confirm_frames}",
            (12, 52),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (240, 240, 240),
            2,
        )

        if triggered:
            cv2.putText(
                frame,
                "ALARME DISPARADO",
                (12, 84),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (20, 20, 255),
                2,
            )

        cv2.putText(
            frame,
            "Teclas: [A] Armar/Desarmar  [R] Recalibrar  [Q] Sair",
            (12, frame.shape[0] - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (235, 235, 235),
            1,
        )

    def _handle_alarm_logic(self, frame: np.ndarray, has_motion: bool) -> bool:
        now = time.time()

        if self.armed and has_motion:
            self.motion_frames += 1
        else:
            self.motion_frames = 0

        trigger_condition = (
            self.armed
            and self.motion_frames >= self.confirm_frames
            and (now - self.last_trigger_time) >= self.cooldown_sec
        )

        if trigger_condition:
            self.last_trigger_time = now
            self.alarm_active = True
            self.alarm_player.start()
            saved_path = self._save_capture(frame)
            print(f"[ALERTA] Movimento detectado. Evidencia salva em: {saved_path}")
            return True

        # Para manter o exemplo simples, o alarme continua ativo ate desarmar.
        return self.alarm_active

    def run(self) -> None:
        if not self.capture.isOpened():
            raise RuntimeError(
                f"Nao foi possivel acessar a camera {self.camera_index}. Verifique permissao/dispositivo."
            )

        print("Sistema iniciado. Pressione A para armar/desarmar, R para recalibrar, Q para sair.")

        try:
            while True:
                ok, frame = self.capture.read()
                if not ok:
                    print("Falha ao capturar frame da camera.")
                    break

                mask, motion_boxes = self._process_frame(frame)
                has_motion = len(motion_boxes) > 0
                triggered = self._handle_alarm_logic(frame, has_motion)

                if not self.armed:
                    self.alarm_active = False
                    self.alarm_player.stop()

                self._draw_hud(frame, motion_boxes, triggered)

                cv2.imshow("Alarme por Movimento - Camera", frame)
                cv2.imshow("Mascara de Movimento", mask)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("a"):
                    self.armed = not self.armed
                    self.motion_frames = 0
                    if not self.armed:
                        self.alarm_active = False
                        self.alarm_player.stop()
                if key == ord("r"):
                    self.bg_subtractor = self._new_bg_subtractor()
                    self.motion_frames = 0
                    print("Modelo de fundo reiniciado.")

        finally:
            self.alarm_player.stop()
            self.capture.release()
            cv2.destroyAllWindows()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sistema de alarme por movimento sem IA.")
    parser.add_argument("--camera", type=int, default=0, help="Indice da camera (padrao: 0)")
    parser.add_argument(
        "--min-area",
        type=int,
        default=1500,
        help="Area minima para considerar movimento (padrao: 1500)",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=5.0,
        help="Intervalo minimo entre disparos, em segundos (padrao: 5)",
    )
    parser.add_argument(
        "--frames-confirmacao",
        type=int,
        default=6,
        help="Quantidade de frames consecutivos com movimento para disparar (padrao: 6)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    system = MotionAlarmSystem(
        camera_index=args.camera,
        min_area=args.min_area,
        cooldown_sec=args.cooldown,
        confirm_frames=args.frames_confirmacao,
    )
    system.run()


if __name__ == "__main__":
    main()
