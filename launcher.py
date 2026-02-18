from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"


class AppLauncher:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.root = tk.Tk()
        self.root.title("HairInfo Salon Manager 실행기")
        self.root.geometry("440x210")
        self.root.resizable(False, False)

        self.status = tk.StringVar(value="중지됨")

        frame = tk.Frame(self.root, padx=20, pady=18)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="HairInfo Salon Manager", font=("Arial", 16, "bold")).pack(anchor="w")
        tk.Label(frame, textvariable=self.status, fg="#3366ff", font=("Arial", 11)).pack(anchor="w", pady=(6, 14))

        tk.Button(frame, text="서버 시작", command=self.start_server, width=20).pack(pady=4)
        tk.Button(frame, text="브라우저 열기", command=self.open_browser, width=20).pack(pady=4)
        tk.Button(frame, text="서버 중지", command=self.stop_server, width=20).pack(pady=4)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _server_command(self) -> list[str]:
        # Why: 동일한 python 인터프리터를 강제해 가상환경 불일치를 줄입니다.
        return [sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)]

    def start_server(self) -> None:
        if self.process and self.process.poll() is None:
            self.status.set("이미 실행 중")
            return

        env = os.environ.copy()
        project_root = str(Path(__file__).resolve().parent)
        env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")

        try:
            self.process = subprocess.Popen(
                self._server_command(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=project_root,
                env=env,
                text=True,
            )
        except OSError as exc:
            messagebox.showerror("실행 실패", f"서버를 시작하지 못했습니다.\n{exc}")
            return

        self.status.set("서버 시작 중...")
        threading.Thread(target=self._wait_until_ready, daemon=True).start()

    def _wait_until_ready(self) -> None:
        # Why: 브라우저 오픈 타이밍 오류를 줄여 첫 실행 실패 경험을 방지합니다.
        import urllib.request

        for _ in range(30):
            if not self.process or self.process.poll() is not None:
                self.status.set("비정상 종료")
                return
            try:
                with urllib.request.urlopen(f"{BASE_URL}/health", timeout=0.5):
                    self.status.set(f"실행 중 ({BASE_URL})")
                    return
            except Exception:
                time.sleep(0.3)

        self.status.set("시작 지연 (로그 확인 필요)")

    def open_browser(self) -> None:
        webbrowser.open(BASE_URL)

    def stop_server(self) -> None:
        if not self.process or self.process.poll() is not None:
            self.status.set("중지됨")
            return

        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.status.set("중지됨")

    def on_close(self) -> None:
        self.stop_server()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    AppLauncher().run()
