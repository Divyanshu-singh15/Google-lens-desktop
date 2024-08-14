import os
import signal
import string
import time
import random
import requests
import io
from PIL import ImageGrab, Image, ImageDraw
import webview
import webview.menu as wm
import pystray
import win32event
import win32api
from bs4 import BeautifulSoup
from winerror import ERROR_ALREADY_EXISTS
import sys

#to help in creating single instance

mutex = win32event.CreateMutex(None, False, 'GoogleLens')
last_error = win32api.GetLastError()

if last_error == ERROR_ALREADY_EXISTS:
    sys.exit(0)
#-------------------------------------------------------------

#To create systemtray icon
system_tray_icon = None
sysicon = None
def systemtrayicon():
    global system_tray_icon, sysicon
    buffer = io.BytesIO()
    im = Image.new('RGB', (400, 400), (256, 256, 256))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((10, 10, 390, 390), outline="black",width=35, radius=100)
    draw.rectangle((200, 200, 400, 400), fill="white")
    draw.ellipse((125, 125, 275, 275), fill=(0,0,0))
    draw.ellipse((275, 275, 325, 325), fill=(0,0,0))
    sysicon = im
    im.save(buffer, format="PNG")
    system_tray_icon = buffer.getvalue()


startTime = time.time()
systemtrayicon()


#some helpinng functions
def generate_random_string(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))



#---------------
def getting_image():
    global image_data
    img = ImageGrab.grabclipboard()
    img_bytes = io.BytesIO()
    try:
        img.save(img_bytes, format='PNG')
        image_data = img_bytes.getvalue()
    except:
        image_data = system_tray_icon    #if no image in clipboard, this image is used
    finally:
        return image_data

def search_on_google_lens():
    global image_data
    # Prepare a fake URL



    fake_url = f"https://{generate_random_string(12)}.com/images/{generate_random_string(12)}"

    # Set user-agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4725.0 Safari/537.36',
    }

    # Send the image to Google Lens
    try:

        response = requests.post(f"https://lens.google.com/v3/upload?s=4&re=df&stcs={generate_random_string(13)}",
                                 data={'image_url': fake_url, 'sbisrc': 'Chromium 98.0.4725.0 Windows'},
                                 files={'encoded_image': ('image.png', image_data, 'image/png')},
                                 headers=headers)
    except:
        return ""

    if response.status_code == 200:
        html_content = response.text
        search_start = html_content.index('Abrf')
        part_after_search = html_content[search_start:]

        start = part_after_search.index('Abrf')
        end = part_after_search.index('\\', start)

        part_url = part_after_search[start:end]
        return part_url

    return ""



windowstatus = True    #Certainly True when gui is open / may be True when gui is close

carryon = True     #This is used to stop while loops when quiting the app
def custom_logic(loc_window):        #Main thread is blocked and a new thread is created to handle backend
    global prv_img, image_data, windowstatus

    while carryon:                  #This code checks in background if something is copied to clipboard when gui is open
        time.sleep(1)
        try:
            new_clip = ImageGrab.grabclipboard()
        except:
            continue
        if not windowstatus:
                windowstatus = True
                return
        elif new_clip is None or prv_img == new_clip:
            pass
        else:
            prv_img = new_clip
            image_data = getting_image()
            url = "https://lens.google.com/search?ep=subb&re=df&s=4&p=" + search_on_google_lens()
            loc_window.load_url(url)


#window 'about' button
def about():
    webview.create_window("About", html="<h4>This desktop version is not<br/>directly published by google.<br/>"
                                        "Do not sign in.</h4>", width=400, height=200, easy_drag=True)

menuItems = [
    wm.MenuAction("About", about),
]



def newwindowprocess(url, loc_custom_logic):
    global windowstatus
    newwindow = webview.create_window("Google lens", url=url, height=720, width=1280)
    webview.start(loc_custom_logic, newwindow, menu=menuItems)    #Main thread is blocked and the new thread is created                   #This line executes on the main thread after the gui windows are closed
    windowstatus = False      #The following lines execute on the main thread after the gui windows are closed


prv_img = ImageGrab.grabclipboard()
image_data = getting_image()
URL = "https://lens.google.com/search?ep=subb&re=df&s=4&p=" + search_on_google_lens()




window = webview.create_window("Google lens", url=URL, height=720, width=1280)

webview.start(custom_logic, window, menu=menuItems, private_mode=False)   #Main thread is blocked and the new thread is created
#The following lines execute on the main thread after the gui windows are closed
windowstatus = False



def on_quit():
    global windowstatus, carryon
    for loc_window in webview.windows:
        loc_window.destroy()
    windowstatus = False
    carryon = False
    icon.stop()


#systemtray icon

icon = pystray.Icon('google lens', icon=sysicon, title="Google lens",menu=pystray.Menu(
    pystray.MenuItem('Quit', on_quit),
))

icon.run_detached()

#-------------------------------------------------------------

signal.signal(signal.SIGTERM, on_quit)   #This closes the app if running when the system shuts down




while carryon:
    while carryon:             #This code checks in background if something is copied to clipboard when gui is closed
        try:
            new_clip = ImageGrab.grabclipboard()
        except:
            time.sleep(2)
            continue
        else:
            if new_clip is None or prv_img == new_clip:
                time.sleep(1)
            else:
                break
    if not carryon:
        break
    getting_image()
    url = "https://lens.google.com/search?ep=subb&re=df&s=4&p=" + search_on_google_lens()
    newwindowprocess(url, custom_logic)
