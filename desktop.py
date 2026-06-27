"""
Desktop entry point for Image Vault, replacing the Electron shell
(electron/main.js + preload.js) with a pure-Python pywebview window.

Unlike Electron, this runs in the same process/runtime as the Flask
backend, so there's no subprocess to spawn or SIGTERM/SIGKILL on exit:
Flask runs in a daemon thread that simply dies with the process when the
window closes.
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request

import webview

import app as backend


# Maps each upload drop zone (by CSS selector) to the logical zone name that the
# frontend's window.handleDroppedPaths() dispatches on.
_DROP_ZONES = {
    '#imageDropZone': 'image',
    '#audioDropZone': 'audio',
    '#pdfDropZone': 'pdf',
    '#folderDropZone': 'folder',
}


def _make_drop_handler(window, zone):
    """Build a Python drop handler that forwards resolved file paths to the page.

    pywebview only exposes a dropped file's real filesystem path
    (``pywebviewFullPath``) to a Python-side drop listener — the page's own JS
    ``drop`` event sees a sandboxed File with no path (same as a browser). So we
    pull the paths here and hand them back to the normal add-by-path flow.
    """
    def _handler(event):
        try:
            data_transfer = (event or {}).get('dataTransfer') or {}
            files = data_transfer.get('files') or []
            paths = [f.get('pywebviewFullPath') for f in files]
            paths = [p for p in paths if p]
            if not paths:
                return
            window.evaluate_js(
                'window.handleDroppedPaths && window.handleDroppedPaths('
                f'{json.dumps(zone)}, {json.dumps(paths)})'
            )
        except Exception as exc:
            print(f'Drop handler error for {zone}: {exc}', file=sys.stderr)

    return _handler


def register_drop_zones(window):
    """Register a native file-drop handler on each upload zone, once per window."""
    from webview.dom import DOMEventHandler

    for selector, zone in _DROP_ZONES.items():
        element = window.dom.get_element(selector)
        if element is not None:
            element.on('drop', DOMEventHandler(_make_drop_handler(window, zone), prevent_default=True))


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

    # Wire native drag-and-drop once the DOM (and pywebview bridge) is ready.
    # loaded can fire again on in-app reloads, so register only the first time.
    _drops_registered = {'done': False}

    def _on_loaded(*_):
        if _drops_registered['done']:
            return
        _drops_registered['done'] = True
        register_drop_zones(window)

    window.events.loaded += _on_loaded

    debug = bool(os.environ.get('DEBUG_DEVTOOLS') or os.environ.get('NODE_ENV') == 'development')
    webview.start(debug=debug)


if __name__ == '__main__':
    main()
