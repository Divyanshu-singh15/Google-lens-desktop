import base64
import hashlib
import io
import signal
import sys
import time
from dataclasses import dataclass
from typing import Optional

import pystray
import webview
import webview.menu as wm
import win32api
import win32event
from PIL import Image, ImageDraw, ImageGrab
from winerror import ERROR_ALREADY_EXISTS


@dataclass
class AppState:
    window_active: bool = True
    running: bool = True
    image_data: Optional[bytes] = None
    image_data_hash: Optional[str] = None
    system_tray_icon: Optional[bytes] = None
    system_icon: Optional[Image.Image] = None


class GoogleLensApp:
    def __init__(self):
        self.state = AppState()
        self.ensure_single_instance()
        self.create_system_tray_icon()
        self.setup_initial_window()

    def ensure_single_instance(self):
        mutex = win32event.CreateMutex(None, False, 'GoogleLens')
        if win32api.GetLastError() == ERROR_ALREADY_EXISTS:
            sys.exit(0)

    def create_system_tray_icon(self):
        """Create and initialize system tray icon"""
        buffer = io.BytesIO()
        im = Image.new('RGB', (400, 400), (256, 256, 256))
        draw = ImageDraw.Draw(im)

        # Draw icon elements
        draw.rounded_rectangle((10, 10, 390, 390), outline="black", width=35, radius=100)
        draw.rectangle((200, 200, 400, 400), fill="white")
        draw.ellipse((125, 125, 275, 275), fill=(0, 0, 0))
        draw.ellipse((275, 275, 325, 325), fill=(0, 0, 0))

        self.state.system_icon = im
        im.save(buffer, format="PNG")
        self.state.system_tray_icon = buffer.getvalue()

    @staticmethod
    def get_image_from_clipboard() -> Optional[bytes]:
        """Get image data from clipboard"""
        img = ImageGrab.grabclipboard()
        if not img:
            return None

        try:
            img_bytes = io.BytesIO()
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.thumbnail((1000, 1000))
            img.save(img_bytes, format='JPEG', quality=85)
            return img_bytes.getvalue()
        except Exception as e:
            print(f"Error processing clipboard image: {e}")
            return None

    def generate_html_content(self) -> str:
        """Generate HTML content for Google Lens submission"""
        base64_data = base64.b64encode(self.state.image_data).decode('utf-8')
        img = Image.open(io.BytesIO(self.state.image_data))
        width, height = img.size

        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Submitting to Google Lens</title>
            <style>
                .loader-container {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    background-color: #f5f5f5;
                }}
                .loader {{
                    border: 5px solid #f3f3f3;
                    border-radius: 50%;
                    border-top: 5px solid #3498db;
                    width: 50px;
                    height: 50px;
                    animation: spin 1s linear infinite;
                }}
                .loading-text {{
                    margin-left: 20px;
                    font-family: Arial, sans-serif;
                    font-size: 18px;
                    color: #333;
                }}
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
                #submission-form {{
                    display: none;
                }}
            </style>
        </head>
        <body>
            <div class="loader-container">
                <div class="loader"></div>
                <div class="loading-text">Submitting to Google Lens...</div>
            </div>

            <form id="submission-form">
                <script>
                    (function() {{
                        const base64_data = '{base64_data}';
                        const byteArray = new Uint8Array([...atob(base64_data)].map(c => c.charCodeAt(0)));
                        const blob = new Blob([byteArray], {{type: 'image/jpeg'}});

                        const form = document.createElement("form");
                        form.action = "https://lens.google.com/v3/upload?ep=ccm&s=&st=" + Date.now();
                        form.method = "POST";
                        form.enctype = "multipart/form-data";

                        const fileInput = document.createElement("input");
                        fileInput.type = "file";
                        fileInput.name = "encoded_image";

                        const dimensionsInput = document.createElement("input");
                        dimensionsInput.type = "text";
                        dimensionsInput.name = "processed_image_dimensions";
                        dimensionsInput.value = "{width},{height}";

                        const dataTransfer = new DataTransfer();
                        dataTransfer.items.add(new File([blob], "image.jpg", {{ type: "image/jpeg" }}));
                        fileInput.files = dataTransfer.files;

                        form.append(fileInput, dimensionsInput);
                        document.body.appendChild(form);
                        form.submit();
                    }})();
                </script>
            </form>
        </body>
        </html>
        '''

    def monitor_clipboard(self, window):
        """Monitor clipboard for changes"""
        while self.state.running:
            time.sleep(1)
            new_image_data = self.get_image_from_clipboard()
            if not new_image_data:
                continue

            new_hash = hashlib.md5(new_image_data).hexdigest()
            if not self.state.window_active:
                self.state.window_active = True
                return

            if new_hash != self.state.image_data_hash:
                self.state.image_data = new_image_data
                self.state.image_data_hash = new_hash
                window.load_html(self.generate_html_content())

    def setup_initial_window(self):
        """Set up the initial application window"""
        self.state.image_data = self.get_image_from_clipboard() or self.state.system_tray_icon
        self.state.image_data_hash = hashlib.md5(self.state.image_data).hexdigest()

        menu_items = [
            wm.MenuAction("About", lambda: webview.create_window(
                "About",
                html="<h4>This desktop version is not directly published by Google.<br>Do not sign in.</h4>",
                width=400,
                height=200,
                easy_drag=True
            ))
        ]

        window = webview.create_window(
            "Google Lens",
            html=self.generate_html_content(),
            height=720,
            width=1280
        )

        webview.start(self.monitor_clipboard, window, menu=menu_items, private_mode=False)
        self.state.window_active = False

    def run(self):
        """Run the application"""

        def on_quit():
            self.state.running = False
            self.state.window_active = False
            for window in webview.windows:
                window.destroy()
            icon.stop()

        icon = pystray.Icon(
            'google_lens',
            icon=self.state.system_icon,
            title="Google Lens",
            menu=pystray.Menu(pystray.MenuItem('Quit', on_quit))
        )

        icon.run_detached()
        signal.signal(signal.SIGTERM, lambda *args: on_quit())

        while self.state.running:
            self.main_loop()

    def main_loop(self):
        """Main application loop"""
        while self.state.running:
            new_image_data = self.get_image_from_clipboard()
            if not new_image_data:
                time.sleep(1)
                continue

            new_hash = hashlib.md5(new_image_data).hexdigest()
            if new_hash != self.state.image_data_hash:
                self.state.image_data = new_image_data
                self.state.image_data_hash = new_hash
                break
            time.sleep(1)

        if self.state.running:
            html_content = self.generate_html_content()
            window = webview.create_window("Google Lens", html=html_content, height=720, width=1280)
            webview.start(self.monitor_clipboard, window)


if __name__ == "__main__":
    app = GoogleLensApp()
    app.run()
