import base64
import hashlib
import io
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional
from filelock import FileLock
import pystray
import webview
import webview.menu as wm
from PIL import Image, ImageDraw, ImageGrab


@dataclass
class AppState:
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
        lock_file = "app.lock"
        lock = FileLock(lock_file + ".lock")
        try:
            lock.acquire(timeout=0)  # Fail immediately if the lock is held
        except:
            sys.exit(0)  # Exit if another instance is running

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

            if new_hash != self.state.image_data_hash:
                window.show()
                self.state.image_data = new_image_data
                self.state.image_data_hash = new_hash
                window.load_html(self.generate_html_content())

    def setup_initial_window(self):
        """Set up the initial application window"""
        self.state.image_data = self.get_image_from_clipboard() or self.state.system_tray_icon
        self.state.image_data_hash = hashlib.md5(self.state.image_data).hexdigest()

        menu_items = [
            wm.MenuAction("About", lambda: webview.create_window(
                "About Google Lens Desktop",
                html="""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>About Google Lens Desktop</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                            margin: 0;
                            padding: 20px;
                            background-color: #f8f9fa;
                            color: #333;
                        }
                        .container {
                            max-width: 600px;
                            margin: 0 auto;
                            background-color: white;
                            padding: 24px;
                            border-radius: 8px;
                            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                        }
                        h2 {
                            color: #1a73e8;
                            margin-top: 0;
                            margin-bottom: 16px;
                        }
                        .warning {
                            background-color: #fef3f2;
                            border-left: 4px solid #dc3545;
                            padding: 12px 16px;
                            margin: 16px 0;
                            border-radius: 4px;
                        }
                        .info {
                            background-color: #f0f7ff;
                            border-left: 4px solid #1a73e8;
                            padding: 12px 16px;
                            margin: 16px 0;
                            border-radius: 4px;
                        }
                        p {
                            line-height: 1.5;
                            margin: 8px 0;
                        }
                        .footer {
                            margin-top: 20px;
                            font-size: 0.9em;
                            color: #666;
                            text-align: center;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>About Google Lens Desktop</h2>

                        <div class="warning">
                            <p><strong>Important Notice:</strong> This is an unofficial desktop application and is not affiliated with or published by Google.</p>
                            <p>For security reasons, please do not sign in to any Google accounts through this application.</p>
                        </div>

                        <div class="info">
                            <p><strong>How to use:</strong></p>
                            <p>1. Copy any image to your clipboard</p>
                            <p>2. The app will automatically detect and submit it to Google Lens</p>
                            <p>3. View your results directly in the application window</p>
                        </div>

                        <div class="footer">
                            <p>Version 1.0.0</p>
                            <p>This is a desktop wrapper for Google Lens web service</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                width=500,
                height=450,
                easy_drag=True,
                resizable=False
            ))
        ]

        window = webview.create_window(
            "Google Lens",
            html=self.generate_html_content(),
            height=720,
            width=1280
        )

        def on_closing():
            if self.state.running:
                print("going to hide")
                for each_window in webview.windows:
                    threading.Thread(target=window.hide, daemon=True).start()
                return False
            else:
                return True

        window.events.closing += on_closing

        self.setup_tray()

        webview.start(self.monitor_clipboard, window, menu=menu_items, private_mode=False)

    def setup_tray(self):
        def on_quit():
            self.state.running = False
            for each_window in webview.windows:
                each_window.destroy()
            icon.stop()

        icon = pystray.Icon(
            'google_lens',
            icon=self.state.system_icon,
            title="Google Lens",
            menu=pystray.Menu(pystray.MenuItem('Quit', on_quit))
        )
        signal.signal(signal.SIGTERM, lambda *args: on_quit())

        icon.run_detached()


if __name__ == "__main__":
    app = GoogleLensApp()
