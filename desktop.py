"""
Desktop entry point for Image Vault, replacing the Electron shell
(electron/main.js + preload.js) with a pure-Python pywebview window.

Unlike Electron, this runs in the same process/runtime as the Flask
backend, so there's no subprocess to spawn or SIGTERM/SIGKILL on exit:
Flask runs in a daemon thread that simply dies with the process when the
window closes.
"""
import argparse
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request

import webview

import app as backend


def wait_for_flask(host: str, port: int, max_attempts: int = 30, interval_s: float = 0.2) -> bool:
    """Poll /api/version until Flask responds, mirroring electron/main.js's waitForFlask."""
    url = f'http://{host}:{port}/api/version'
    for _ in range(max_attempts):
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(interval_s)
    return False


class Api:
    """Exposed to the frontend as window.pywebview.api.*, replacing preload.js's electronAPI bridge."""

    def __init__(self):
        self.window = None

    def open_file_dialog(self):
        """Replaces getFileAbsolutePath(): a native file picker that returns real absolute paths."""
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        return list(result) if result else []

    def show_item_in_folder(self, filepath):
        """Reveal filepath in Finder/Explorer/file manager."""
        try:
            system = platform.system()
            if system == 'Darwin':
                subprocess.run(['open', '-R', filepath], check=True)
            elif system == 'Windows':
                # explorer.exe returns a non-zero exit code even on success - don't check=True.
                subprocess.run(['explorer', '/select,', filepath])
            else:
                # No native Linux equivalent of "reveal and select" - open the containing folder.
                subprocess.run(['xdg-open', os.path.dirname(filepath)], check=True)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def open_file(self, filepath):
        """Open filepath in its OS default application."""
        try:
            system = platform.system()
            if system == 'Darwin':
                subprocess.run(['open', filepath], check=True)
            elif system == 'Windows':
                os.startfile(filepath)
            else:
                subprocess.run(['xdg-open', filepath], check=True)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(description='Image Vault desktop app')
    parser.add_argument('--port', type=int, help='Port to run the backend on')
    parser.add_argument('--host', type=str, help='Host to bind the backend to')
    args = parser.parse_args()

    backend.initialize_app()
    port = args.port or backend.config['port']
    host = args.host or backend.config['host']

    flask_thread = threading.Thread(
        target=lambda: backend.app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True),
        daemon=True,
    )
    flask_thread.start()

    if not wait_for_flask(host, port):
        print(f'Could not connect to the backend at http://{host}:{port} after 6 seconds.', file=sys.stderr)
        sys.exit(1)

    api = Api()
    window = webview.create_window(
        'Image Vault',
        f'http://{host}:{port}',
        width=1400,
        height=900,
        js_api=api,
    )
    api.window = window

    debug = bool(os.environ.get('DEBUG_DEVTOOLS') or os.environ.get('NODE_ENV') == 'development')
    webview.start(debug=debug)


if __name__ == '__main__':
    main()
