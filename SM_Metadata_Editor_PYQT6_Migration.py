import sys
import os
import subprocess
import pygame
import traceback
from collections import defaultdict
import asyncio
from shazamio import Shazam
import nest_asyncio
from PIL import Image, ImageQt
import requests
from io import BytesIO
import webbrowser
import csv
from io import StringIO
from PyQt6.QtCore import QByteArray
from base64 import b64decode

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QScrollArea, QFrame, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QStyle, QFileDialog, QMessageBox,
    QDialog, QToolButton, QMenu, QGridLayout, QSpacerItem, QSizePolicy,
    QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor, QAction  # Add QAction here

# Constants
SUPPORTED_EXTENSIONS = {'.sm', '.ssc'}
SUPPORTED_AUDIO = {'.ogg', '.mp3', '.wav'}
METADATA_FIELDS = ['TITLE', 'SUBTITLE', 'ARTIST', 'GENRE', 'MUSIC']
SUPPORTED_ENCODINGS = ['utf-8-sig', 'utf-8', 'shift-jis', 'latin1', 'cp1252']
COLUMN_WIDTHS = {
    'checkbox': 30,
    'actions': 130,
    'type': 75,
    'parent_dir': 160,
    'title': 250,
    'subtitle': 250,
    'artist': 250,
    'genre': 250,
    'status': 30,
    'commit': 80,
    'id': 0
}
SHAZAM_BUTTON_NORMAL = {
    "text": "Shazam Mode: OFF",
    "style": "QPushButton { background-color: #4a90e2; }"
}
SHAZAM_BUTTON_ACTIVE = {
    "text": "SHAZAM ON!",
    "style": "QPushButton { background-color: lightgreen; }"
}

class MetadataUtil:
    @staticmethod
    def read_file_with_encoding(filepath):
        for encoding in SUPPORTED_ENCODINGS:
            try:
                with open(filepath, 'r', encoding=encoding) as file:
                    return file.readlines(), encoding
            except UnicodeDecodeError:
                continue
        return None, None
        
    @staticmethod
    def read_metadata(filepath):
        content, encoding = MetadataUtil.read_file_with_encoding(filepath)
        if not content:
            return {}
            
        metadata = {}
        credits = set()
        
        for line in content:
            if line.startswith('#') and ':' in line:
                key, value = line.strip().split(':', 1)
                key = key[1:]
                value = value.rstrip(';')
                
                if key == 'CREDIT':
                    credits.add(value)
                else:
                    metadata[key] = value
        
        metadata['CREDITS'] = credits
        return metadata
        
    @staticmethod
    def write_metadata(filepath, metadata):
        content, encoding = MetadataUtil.read_file_with_encoding(filepath)
        if not content:
            return False
            
        for i, line in enumerate(content):
            for key, value in metadata.items():
                if line.startswith(f'#{key}:'):
                    content[i] = f'#{key}:{value};\n'
                    
        try:
            with open(filepath, 'w', encoding=encoding) as file:
                file.writelines(content)
            return True
        except Exception:
            return False
            
class MetadataEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StepMania Metadata Editor")
        self.setFixedSize(1600, 800)
        
        # Initialize all attributes first
        self.current_playing = None
        self.selected_entries = []
        self.file_entries = []
        self.selected_directories = set()
        self.bulk_edit_enabled = False
        self.shazam_mode = False
        self.audio_enabled = False
        self.temp_widgets = []
        self.search_credits_button = None
        self.search_frame = None
        self.table = None
        self.clear_button = None
        self.bulk_edit_btn = None
        self.shazam_btn = None
        self.commit_all_button = None
        self.search_box = None
        
        # Initialize pygame for audio
        try:
            pygame.mixer.init()
            self.audio_enabled = True
        except Exception as e:
            print(f"Warning: Audio disabled - {str(e)}")
            self.audio_enabled = False

        # Initialize sort tracking
        self.sort_reverse = {
            'pack': False,
            'title': False,
            'subtitle': False,
            'artist': False,
            'genre': False
        }
        
        # Setup UI components
        self.setup_ui()
        
        # Setup bulk edit controls after main UI
        self.setup_bulk_edit_controls()
        
        # Initialize Shazam-related attributes safely
        try:
            nest_asyncio.apply()
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.shazam = Shazam()
        except Exception as e:
            print(f"Warning: Shazam initialization failed - {str(e)}")
            self.loop = None
            self.shazam = None
        
        # Add at the start of __init__
        self.entry_counter = 1  # Start at 1 for more human-readable IDs

        # Embedded icon data (you'll need to convert your icon to base64 first)
        icon_data = b64decode("AAABAAkAEBAAAAEAIABoBAAAlgAAABgYAAABACAAiAkAAP4EAAAgIAAAAQAgAKgQAACGDgAAMDAAAAEAIACoJQAALh8AAEBAAAABACAAKEIAANZEAABISAAAAQAgAIhUAAD+hgAAYGAAAAEAIAColAAAhtsAAICAAAABACAAKAgBAC5wAQAAAAAAAQAgAFrDAABWeAIAKAAAABAAAAAgAAAAAQAgAAAAAAAABAAAEwsAABMLAAAAAAAAAAAAAAQEBQAAAAAAVkh3AAADAA9cSIR2gl7F61dDfo0AAAACAAAAAAAAAAAAAAAAAAAAAAEBAQAEBAQAAgICAAEBAQAgKBwA////ADgySy90Va2mk1/q9Zxc//9/VcXeJSIwLzQsRwAHBwkAPDIrAAsMDQD/46IAAAAACwAAAAMAAAAABjYAAWNOj1uFWs/btIn6/9e+///Bmf//p3fz/19JipMAAAAEAAAAAHFYRQAAAAAJc1dBVppxULBMPC46ZVA+ANzp2wyof/K2m1z+/9G0////////9e///+bU//+Rbs7nKiM+Ov///wBLPDAzpnZQouSYW/P1oV7/kmlIlAAAAAMAAMcAyq//YaVv/vbfy///8ej//+LQ//+uev//m2L3/2VLkqqHY0F805dn4PrQr///yZ3//7V4/8mMW90vKCIw7+v/AP///wy+m/6m1r3//7uQ/v/l1f//uIz+/59l//S0j87A8KVm9P+oYf//0q7///n0///17f/ws4L9f1s+i8Sv/gDIr/4A3M3+M7CC/92bXP//tIX+/r6b/cu8nPxa/fLzJP+6gsH/tXr//9/F///06v//8uf//7Bw/8KGVuYhHhsAT1VRAAUAPwCwluh5oXPy5LSN/YLSwvseXQL/APWqeQD/0a1b/86o9v/Npf//1LH//9q8//+safTys4CwVkU3AAAAAAReRTFEuYZeuaqBacMoMigaeW2QAP///wD/8+kA////D//Ai7L/pVv//7uE+v7Kob79yqFV//nxDz4yKSubcU+P3Kh/6/6qaP/pmlr8clQ8eQAAAAEAAAAALSk8AP///wC7nYtp5Kh70/zElmf85dIV/pM9APvp2gDSl2jR9qZm///kzf//x5r//9Ks/8aYdOI2KB030J/4AB0eJB9cRYl8hl3O3HlascUCEBMYf3JtAP///wD9/PwA/8aXqP+0eP3/8+r///Tq///Usf/4qWj/mW1Lsk49d2+HZsPPu5vx/qRo//+ecej8UEFvb////wAAAAAAAAAAAP/s3SL/x5nA/9m7///p2P//06///69u8uCukreccOnpoWX//9zF///WvP//2cH//31butIXFh0jJSAzAAAAAAD/uH8A/93CQf+0eeT/sXP5/smeuf3QrVD///8UvZj/lsKd/v/m1f///v3//8qo//+WYu36Y1KKVpB0ygAAAAAA////AP///wL/17da/sujYfvl0xL+qGIA3831AOHW/ia8l/7Ru5D+/86w/vy5kf7UuJP9ebmq4xXVvv8AAAAAAP/69gD///8A/wAAAP1tAAD85dIA////AP///wAcAP0AyKz+a6x+/uO3kf2M1cX8Kf///wColNwAuZn/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKAAAABgAAAAwAAAAAQAgAAAAAAAACQAAEwsAABMLAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAcHCQAAAAAA2L7/AAQJACZTRXOcf2K39EM4XKIAAAALAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABkZHgAAAAAHLio7T29WoMKWZOr6n2L//3lYtegUFRhGMy9CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUFBwAAAAAA8NT/AAQJACJQQ3CLhmDL6ptg+/+aWv//m1v//5hi8P9NP22pAAAADgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAECAwAAAAABAAAADgAAAAMAAAAAAAAAAAAAAAAAAAAFLys9Tm9WocOVY+r8tof//82t//+3iv7/pWz+/55f//9+Wb/vHBsjUllRdgAAAAAAAAAAAAQEAwAAAAAAc19PAAAAABNQQTRoalRDrRoXFDYqJCAAAAAAAHRkoQB/dKEyjGfQ3pxi+/+cXf//3MX////////8+v//8Of//9vE//+yi/X/VEJ4tgAAABQAAAAAAAAAAB8cGQAAAAAGKiUhRIpoTbDbmGL15p9m/11IOI8AAAAEAAAAAMay/QDb0P1CrH3/7Zpa/v+hZv7/6t3////////9/P//8Ob///r3///UuP//hF3J9CQhLl9oXYwA////AAUJDChrUj6Mwolb5vekYf//pVv//6Zf/6R3U9kAAwcqDw4NAPv6/wD///8PyK7+np9l/v+pc/7/9e7///bw///8+f//za3+/616/v+lbP7/m2L4/1xIhMEAAAAtTD4yZah6Vs/rr3/9/8qe//+3fv//qWX//6Ra/96YX/xJOi91////AP///wDXy/4A7+z/MrSL/tW2iP7//fv//82t///k0v//8en//6ly/v+ZWf7/nFz//4xl1PKCZlbE25hi9P6mXv//zqb///7+///59f//69r//9Wz//2zd/+QakvFAAAAHv///wD///8A////AtXD/my8lf724tD//657/v+2h/7/+/j//86w//+bXP7/pG/+87ye+qn3wJbO/6Zd//+jWv//q2f//8eb///x5v/////////////Imf/Qj1v0Myskav///wD+/v8A9/b/AP///xXEpv6to2r+/5tc/v+dX/7/xaH//8Gd/v2whv3Iy7f7Xvv//xP/3sJu/69v+P+kXP//uH7//+DG///69v///v7///bv//+zdv/3o2D/f19GyAAAAAD///8A////AL2l/gDp4v8/sof/4Jtc//+dYf7/qXr94cCk/IPn5Poj////APbw8gD+//8c/8OUwf/Ajf//9/H///Tr///Wtv//9e3//+HJ//+lXf//pl3/z5Zo7gAAAAAAAAAAb21sAGJlYgD///8Et6fjhKJ58O63lPun2c37Pf//+QbPwvgA///9AP///wD7AAAA/9/GYP/FlvT/0Kr//7J0//+7hf//+vf//8WW//+oYv/+uYHW98qmdgAAAAAAAAAALykkAAAAAAoyKiROn3pdu6OCcdpCQ0JETzl3APb59QD///8A////AP///wD/+vYA////Ff/InLT/pV3//6JY//+yc///1LH//r6L4f3Loov76twu////BQkJCQAAAAACERITMHVZQpfKjl3r+6Zi/+2gYf9lTTqoAAAAEAAAAAAAAAAAAAAAAHx8fAD///8A5YU4AP/q1VH/tnrt/6df//6yder9xpqb/OPPOvv//wf607MA/f//AAAAABtWRDdysH9Y1/C3if//wY3//6Rb//+lW//Gilr0LiYgZgAAAAAAAAAAAAAAAAAAAAACAwEA////AFBXUi3Bn4jC4q+Guv3fyEj7//8L+byLAPz+/wD///8A////AKN8XLTfmmL4/6hh///iyf//59T//6lk//+/i//8x5z/kGxQ0gAAASwRDw4AAAAAAJOBxQAAAAAWMy5FZWxTncaOadL0UkdxoQAAAAt3dnMA////AP///wD///8AAAAAAP7Fl9b/p1///6pl///u4P//6dj//97D///69v//38X/5Z9n/ldDNJcAAAAKAAAADiomN1VlUY+5j2bY9p1h/P+eXv//e1i67RgYHk1DPVgAAAAAAAAAAAAAAAAAAAAAAP/p117/uIDm/7J1///38f////////Xt///Kn///qWT//6Zd/7qEWOwrJip7W0mCp4dfzvDBn/r/2L3//6Bj/v+ka///qX3z/1JCc7EAAAARAAAAAAAAAAAAAAAAAAAAAP///wj/2r1//7yH+f/o1v//+vb///bv///fxv//tHf//6Ze//ezeeekirvUmmX2/5tb//+5jf//+fX//8Kb/v/Vu///4s7//4RgxfIgHipaj4C/AAAAAAAAAAAAAAAAAP/38gD///8Y/8+orf+wcP//t33//8md///bvv//xJby/cKSrf/jxkncy/9yp3P/9qFm/v+sd/7/3sr///Ps///28f//y6r//5pg9/9ZRoC9AAAAFwUFBgAAAAAAAAAAAP///wD+2bsA//TsNf/CkNP/pV3//6xp9/6/jbz82bxZ+///Eve5jAD///8VwaL+rsWi/v/x6P//8+v////////49P//rnv+/5xe//+QbdTbMDI3KDc1RAAAAAAAAAAAAP///wD///8A////Af/m0lv/y6G8/dSzafv59xn3AAAA+/LsAP///wC9pP4A6OD/P7qU/uC3iv7/zKz//+DM///Tt///p3T+9rWP/b7JtfpWoKqjBayqvgAAAAAAAAAAAP///wD///8A////AP///wb///8V/v//Avvs4AD///8A/f39AP///wD///8A////BdK9/nyjbf75mlz+/6Zy/vS4lP27zrr8Yfb6/Bn///8BjZSWADIvVgAAAAAAAAAAAAAAAAD///8A//79AP/+/QD//PoA/v79AP38+wD///8AAAAAAP///wD7+v8A8O3/APr7/yHEp/7BtpD+0c66/G31+PwcAAAAAOjk+wD///8A/f39AP///wAAAAAAAAAAAMAH/wAAA4AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAMAAAADAAAAAQAAAAEAAAABAAAAAQAAAAMAgIADACgAAAAgAAAAQAAAAAEAIAAAAAAAABAAABMLAAATCwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYICgdGUEZtunllqPYzLkOyAAAAGQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAERDVAAAAAAYKSc1cW9andWaauz8omj//3RaqO4MDQ1eAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFCAoHPU1DaKqKZ8zyn2b8/5xc//+bXP//mWjt/0I4WbwAAAAdAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABGRVYAAAAAGCknNXJvWp3XmWnt/pxd//+aWv7/m1v+/5tc/v+eYf//e1609BISFWsAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAAAAQAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQgKBz1NQ2mqimfM859l/f+xf///w5z+/7B+/v+hZf7/mlv+/5pZ//+bZ/L/Sj5lxgAAACUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgNS4oeD01LqQDAwMyCwoKAAAAAAAAAAAAAAAAAP///wA3M0dKcFuf1Zpq7f6dX///nmH+/+PR////////+PP//+jZ///RtP//uYz+/6hv//+BYb/3GRgfeAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAABwZGAAAAAAPFxYUVXRbR7rRl2j2y5Vq/TIqI4kAAAAGAAAAAAAAAADa2twA9P/FBaqS45egafz/nFz//5pb/v+nb/7/8ur////////////////////////9+///6tz//6yA9/9QQnHQAAAALgAAAAAAAAAAAAAAAAAAAAAAAAAFAAEEOFREN5q0hmDp9Kdp//+mXf/7qGX/e19I0QAAACsAAAEAAAAAAP///wD///8I1sX/iqZy/vyaW/7/mlr+/7KC/v/69//////////////28P//6dz///n1///17///sn///4ZhyvofHiiFAAAABwAAAAAAAAAAAAAAIDUtJniVcVPV5Z9n/f+oYP//pFv//6Rb//+nXv/EjWH3IB0acgAAAAIAAAAA////AMvC/QD6/P8zwqT+zJ5i/v+ZWf7/wZr+///////7+P///fv///bx//+3iv7/r3z+/7GA/v+dXv7/nmb6/1pJftkAAAA3AAAADhgXFVZ0W0e70JZo9v25gv//uoH//6to//+kW///o1j//6NZ//SlZv9mUD6/AAAAHAAAAAD///8A////AP///wTm3/5osIT+75pa/v/Qs////////97J///eyf///////93I//+dX/7/mVn+/5tc/v+dXv//jWXU+yYjMaFSQzWZtYZg6fWmZ///sXD//+/i///7+P//7uD//9q8///Dk///sHH//6lh/7GCXPAPDw9Zkn5vAP///wD+//8A/v//AP///xjRvf6kpG7+/t3H////////yKX//698/v/17////Pr//72T/v+aWv7/m1z+/5tb/v+hb/v8noaY1eWja/n/qGH//6Ra//+raP//4sv///r2//////////////78///07P//xpj/6qBl/1BANKkAAAATAAAAAP///wD///8AjHH8APb1/z68mv7Xw5/+/+XU//+vfP7/mlr+/86w////////49L//55h/v+dYP7/qXn98L+l/aH339WQ/7N1+P+jWv//pFv//6Ra//+oYv//vIX//+fT///////////////////Qqv//p2D/m3RU5AADBU8AAAAAAAAAAP///wD///8A////COHW/netf/70n2L+/5tc/v+aW/7/pW3+/93H///PsP//pXH++7eU/MTVyPph/v/7Fv///i//yqHK/6dg//+jWv//pVz//7h+///fxP//+vf/////////////+fT//7h+//+kWv/dm2b8PjMqqAAAAAAAAAAA////AP///wD5+v8A////H8y0/rKgaP7/m1v+/5tc/v+aW/7/o2v+/7KJ/d7JtfuC8PH6KP///wTx8voA////Bf7n1XL/tHn1/6lk///TsP//9/H////////z6v//7N3////////m0v//qGL//6Ra//2oY/+Sb1PoAAAAAAAAAAAAAAAA////AP///wD///8B8e//TLmU/+CcXv//nWH+/6l6/e/Apfuk4dv6Qf//+wuomewA///+AP///wD++fUA////JP/MpMD/vYf///v4///69f//2rz//7V7///gx////////8ui//+jWP//pFr//6tm/9+rgtMAAAAAAAAAAAAAAAAAAAAAAAAAAG9xbwDy/eMNvbLfjKWA7vG0k/jF1sr7Xv//+hb///8B/P76AP///wD///8A////AP///wD///8D/uvbZf++ifH/xZf//7qD//+kXP//r27///Xu///38P//snX//6Zg//61e+/9zKSp+OHORAAAAAAAAAAAAAAAAAAAAAAkIR4AAAAAEBgWFVeGbVi6n4V44UtKTHOerIYHrKyzAP///wD+/v4A////AAAAAAD///8A////AP/9/AD///8c/9Kvs/+oYv//o1j//6Na//+raP//3MH//9Kv//60ePX9x5y4++PPW/v//xj///8CAAAAAAAAAAAAAAEAAAAABgADBTpWRTidtodh6vanaP/ypmn/ZU89ywAAAC8AAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH+7+NY/7uF6/+kW///pFr//6Vd//+xdPn9xZjF/N3Fafv9/x////8D+fXxAP///wAAAAAAAAAAAAAAACI2Lih7mHNV1+ehaf3/qGD//6Rb//+nXf/Nk2T7LiYhlAAAAA0AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQkJAA6OjoAP///xX/2Lim/65r//+ubPz9wI/R/Nm9ePv39Cj+//8F9+vhAP///wD///8A////AAAAABIaGBZYeF5JvtKWZvf+u4X//9e1//+ydP//o1r//6Na//+nYf+Ub1HoAwUGVQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADNxvYAAAAAGH54dILHoYXg37udlP317jL9//8I9NfAAP7//wD///8A////AP///wAAAAAAZ1NDkLeHYen2p2j//6Zc///VtP///////8me//+hVv//rWz//8GP/+usef9WRDW/AAAAJAAAAAAAAAAAAAAAAAAAAAArKjUAAAAAEQ8QEFJJP2SwgmW+7IJque4mJjB8AAAABYyOjwD///8A////AP///wAAAAAAAAAAAAAAAADzvZLg/6lj//+kWv//pl///+TP///+/f//w5P//8OT///s3f///////9Ks/8CKXvghHRmDAAAACAAAAAAODxEAAAAACwYJBkQ/NlaieV6v6Ztq8P+eYP//nmf6/1ZGeNUAAAAyAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/iypz/tHf3/6NZ//+saf//8OP///37///s3P///fv///z6///gxv//s3X//Khk/4RkS98AAAFGAAAABwABADc2MEeSclui4aWA6f6ncP//m1v//5tc/v+cXP//iWPP+yMhLowAAAAJAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////K//WtLX/qmf//7V5///59P/////////////t3///wI7//6Ze//+jWf//pVz/4p5n/kc5LbQnJDaFaVWU15No4Pyqdv//7N///9/L//+hZf7/nF3+/7F///+vgfz/XkyG3QAAAD4JCgoAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8B//jzRf/Hmtj/uH////Ts//////////////Lo///bvv//vYn//6Rb//+kWv//rmv/vZyL2JFx1e+fZf3/nFz//6Bk/v/i0P///////8Ga/v+tef7/9e///97I//+Radn9Kyc5mgAAAA0AAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8H/+3ebf+9iO7/tnz//8qf///dwf//7uH///v4///jzf//q2j//rd+6v3OqJ737O5tuZT/3ptd/v+aW/7/mFf+/7OD/v/49P//7OH//9W6////////y6n//55j/v9mUZLkAAMASCMkKgAAAAAAAAAAAAAAAAAAAAAA//7+AP///wD///8V/+DHmP+wcfv/olf//6Rb//+qZv//uYL//sOU8f3Koa/75tRR+///E////w7bzf6HqHX++aZu/v/Gov7/vJL+/+DM/////////fv///fy//+ue/7/m1v//5Nn4f82MEmhAAAADAAAAAAAAAAAAAAAAAAAAAD///8A////AP7v4wD///8t/9Kvv/+qZv//pl7//7Fz9v3FmLz838hf+///Gv///wL6+fgA8vH/AP///ynEqP7AvZX+//n2///9/P//+/n/////////////4s///55h/v+aW/7/o279/39urKEAAAAMAgIDAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH/9e1P/82l2P7Fl8v83MNu+/v8Iv///wP58uwA////AP39/QD///8A////Auvl/1m3kf7os4P+/8im///dyP//7uT///bw//+/l/7/nmT+/66C/ejEqv2h0MnvLv///wBbW1sAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wn/+vZA/vv4Lf3//wb359oA////AP///wD///8A////AP///wD///8A////EdbF/pWkb/78mVn+/5xd/v+kav7/sID+/7GH/ufEqv2i4tv8TP///BT///8BkaBnAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD//v4A////AP/q2gD96tsA/v//AP///wD///8A////AAAAAAAAAAAA////AP///wDf2v4A+/3/MsKk/sueY/7/oGb+/q2B/eXDqfyg4tv8S////RT///8B+fr8AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8F5t7/cL+i/uTDqf2y4tv8VP///Bb///8B+fr8AP///wD+/v4A////AAAAAAAAAAAAAAAAAAAAAAAAAAAA8AB//+AAf4OAAD4BAAA8AQAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAwAAAAMAAAADgAAAAwAAAAAABAAAAA4AAAAGAAAAAAAEAAAAHAAAADwAAAA8AAAAHAAAABwAAAAcAAAAHAAAAB4AAAAeAAAAHwBgAB+B8AB8oAAAAMAAAAGAAAAABACAAAAAAAAAkAAATCwAAEwsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAsDQ4Qh1JMatxhWn/0GxohxQAA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dfv/rm3//6Zd//+jWv/+rW3/f2VR7AAAAGsAAAAGAAAAAAAAAAAAAAAA////AP7+/gD///4M2tH+hKt9//2bW/7/m1z+/5tc/v+bXP7/m1z+/9i/////////////////////////////////////////////////////////v5f//6Ft+v9WS3TrAAAAcAAAAAkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAAAApBwgId1RGO8i9kW71+q9z//+oYf//pFv//6Rb//+kW///qGD/zZlv/CEeG7EAAAAhAAAAAAAAAAAAAAAA////AP///wD///8H9/f/XMOo/tyfZf7/m1z+/5tc/v+bW/7/n2P+/+bW////////////////////////+/j//93I///n1///+PP////+///07f//sH/+/51f//+RcdH9Hx4nvwAAAC8AAAAAAAAAAAAAAAAEAwIBAAAAGAAAAFk2LiivnXxh6+2rdf7/q2b//6Rb//+kW///pFv//6Rb//+kW///pFv/+a1w/2hVReMAAABYAAAAAwAAAAAAAAAA////AP///wD///8A////IOfh/pOxif72nF3+/5tc/v+aW/7/p3D+//Hp//////////////7+/////////////9Gz//+iZ/7/sH/+/8Kb/v+0hf7/nF7+/5tb/v+jbv3/XlKA7wABAHsAAAALAAAAAAAAAAwAAAA/GxkXlXdhT9zZoXX7/69u//+rZ///pV7//6NY//+jWf//pFr//6Rb//+kW///pFv//6pj/7mMafoTEhGeAAAAFgAAAAAAAAAAAAAAAP///wD///8A////A////0HSwv7BpXH+/5tc/v+aWv7/s4P+//r2////////+PP//9/L///9/P////////bw//+ygf7/mFj+/5lZ/v+aWv7/m1z+/5tc/v+eYP//lnPb/iclMscAAAA7AAAAKAcHCHZWSDzIvpJu9fmucv//qmT//86n///s3f//4cn//8yi//+4fv//qmX//6Na//+jWP//o1r//6Vb//Grcv9RRDjXAAAARQQDAwEAAAAAAAAAAP///wD///8A////AP///w/08/9tvqD+5Z5i/v+ZWf7/wJn+//7+////////7eL//7B+/v/q3f/////////////dyP//n2L+/5tb/v+bXP7/m1z+/5tc/v+bW/7/o2z//2lZj/ACBAOdNi8prJx7Yevuq3b+/6tm//+jWf//s3b///fw///////////////////48///6tj//9Wz//+/i///rmz//6Rb//+sZv+ifmD1BwcIiQAAAA0AAAAAAAAAAAAAAAD///8A////AP///AD///8n4tr+nq2C/vmaW/7/z7H/////////////4M3//51e/v++lf7/+/n////////7+P//vZP+/5pa/v+bXP7/m1z+/5tc/v+bXP7/nmD//5p73vJ1ZmDP26R4+P+ubP//pl3//6Rb//+jWv//r27//+7g///////////////////////////////////8+f//8eX//8qf//+mXv/lpXL/OzIryQAAADMAAAAAAAAAAAAAAAD///8A////AP///wD///8F/v//S825/suhav7/za7/////////////zq///5pa/v+fY/7/3sn/////////////6Nn//6Rq/v+aW/7/m1z+/5tc/v+cX/7/p3b+/r2o98HyzrLD/69t//+jWv//pFv//6Rb//+kW///pFv//7Z7///TsP//59T///bu///+/f///////////////////////+vb//+pZP//rWr/im1W7wAAAXMAAAAJAAAAAAAAAAAAAAAA////AP///wD///8A////E/Dt/nq4lv7sq3f+/9rD///dyP//q3b+/5pb/v+aWv7/soH+//bw/////////Pr//7iL/v+ZWf7/m13+/6Jr/v+yjf3pyrr6nO3v/E//7t+S/7qD9/+kW///pFv//6Rb//+kW///pFv//6NZ//+iWP//rGj//9Gr///69v///////////////////////93C//+lXf//p1//1Z1w/SgjH7gAAAAsAAAAAAAAAAAAAAAAAAAAAP///wD///8A//7/Af///y/d0v6qqXr+/J1f/v+dYP7/mlv+/5tc/v+bXP7/nF3+/8ys///7+f//8ej//657/v+dYv7/rID99sKr+7rg3Phi///7JP///wz///9H/9W0zP+raP//pFr//6Rb//+kW///o1r//6Vc//+5f///38X///n1/////////////////////////fv//8KR//+jWf//pFv//K1v/3RdS+YAAABuAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wj7/P9WyLD+1aBo/v+bW/7/m1z+/5tc/v+bXP7/m1v+/59j/v+2h/7/sH/+/6d1/v66m/zU1sz5fff5+TT///4P////Av///wD///8W/vDlgv++ivL/pVz//6Rb//+kWv//sHH//9Wy///27////////////////////fz/////////////7+P//61s//+jWv//pFv//6lh/8WUbfocGRa3AAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8Z6+f+hrWQ/vGcXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+haf7/sYv96Mu7+pzs7PhI///8F////wT///wA////AP///wD///8C////Pf7Zu8L/rWv//6Na///Bj///7+L///////////////////r2///dwv//6Nb/////////////2Lj//6Rb//+kW///pFv//6Rb//Wrcf9nVEXkAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8C////ONfJ/rendf7+m1z+/5tc/v+bXP7/n2X+/6yB/fXCrPu54dz5Yf//+iT///8I////AP///wD///8A////AP///wD///8A////Ef7z6nn/wY/v/6ll///p1//////////////9+///5dH//72J//+wcP//7+P////////7+P//vYj//6NZ//+kW///pFv//6Na//+ubP/DnoDcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////APb29gD///8A////C/n5/2LEqf/eoGf//51g//+ndv79up3809bN+Xz3+vkz////D////wH///8A////AP///wD///8AAAAAAP///wD///8A////Af///zb+3cK6/7Fy///Yuf//+vb//+zd///Gmf//qWT//6FW///Ckv///fv////////r2v//qmb//6Na//+kW///pl///7Fy/v3FmNrkyLJpAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkJCQAdnh1ANHTzSTDvtmXrZLt77GR9urKuvec7e35R////Bf///8E///8AP///wD///8A////AP///wAAAAAAAAAAAP///wD///8A////AP///w7+9/Bu/8WX6f+raP//tnz//61q//+jWf//pFr//6Ra///Yuf/////////////RrP//o1n//6Vd//+ubv/+wZDm+9i8ofrw6VD///8YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAAIQMEBWhdUkm0kYJ821dUW7Fwcm9B+vzyCQAAAAD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///gD///8t/uLKrf+xc/7/olj//6Na//+kW///pFv//6Na///Lov//+vf///Dk//+1ev//q2j//r2J7fzUtK767eNe/P//Jv///wr///8BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEA4LAAAAABMAAABOKSQgpI5xWuXlqHf997N8/3lhTesAAAB/AAAAEBQUFAAAAAAAMjIyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8K/vn1Y//JnuP/p2D//6Rb//+kW///pFv//6Ra//+nYf//uoL//7iA//66g/P80K27+uncafv+/yz///8N////Af///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJAAAANRMSEYhqV0fVzptz+f6vb///pl7//6de/+Ckc/46MSrUAAAASwICAgMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD+//8A////J/7l0aT/tHj8/6Rb//+kW///pFv//6Rb//+oY//+tnv4/cukx/vl1Hb7/P00////EP///wL///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAwAAACIBAwRrSD00v7GJafH2rnT//6lj//+kW///pFv//6Rb//+saP+qg2T4Dg0NpwAAACMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP7+/gD///8A////B//8+Vn/zaXc/6hi//+kWv//p2H//7R4+/3Jn9L74c2D+/n4PP7//xT///8D/v//AP///wD///8A////AAAAAAAAAAAAAAAAABQRDgAAAAATAAAATysmIqaOcVrm5qh2/f+xcP//q2f//6Ra//+kW///pFv//6Rb//+lXP/2rXL/Z1NE6QAAAHEAAAALAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA9PT0AdHV2APn//yH24c+d/7uE+/+zdv39xZjb+93FkPr28kb9//8Z////Bfz+/wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAACQAAADUTEhGJbFhJ1tCdc/n+rm7//69u///iyv//7Nz//72I//+jWv//pFv//6Rb//+jWv//qF//1J1x/SslIMgAAAA+AwMCAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASERYAAAAAEAEDAERRUVGVqpWF2ryhi7vc1M5X////Hv///wft8/kA////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAABAQFWEk+NLyyimry9q50//+pYv//olj//8CO///+/f///////9y///+kW///pFv//6NZ//+pY///rm7//69u/5d2XPUHBweaAAAAGwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAA4CgsMhkQ+Wc+Ebrfyj3nG8zQzRMQLDQpGOjo6Aq6urgD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAArpF5t+iqePz/rGj//6Vc//+kW///o1n//9Cq/////////////9Sy//+iWP//pl7//72H///kzv//8+r//8+o//Gsdf9WRzviAAAAYwEAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAALwUGBXk4NEnFe2er8qF28f+hZ///pG3//3Vio/cICAiXAAAAFgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9a00/+ubP//o1r//6Rb//+kW///pVz//97D/////////v3//8SU//+zdf//2rz///n0/////////////+fU//+taf/GlW38HxsYvgAAADQFBAQBAAAAAAAAAAAAAAAAAAAABQAAACUAAgBrLyw8u3FhnO2ed+n+omr//5xd//+bW/7/nF3//5907v87Nk7bAAAAUAICAgMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//Lnkf/Ele7/pl///6Rb//+kWv//qWT//+rZ////////+/j//97D///y5///////////////////7N7//7+L//+kW//+rm7/h2tV8gECA4wAAAAUAAAAAAAAAAMAAAAeAAAAXSUjLq9nWYzomXbg/aNt//+cXf//m1v+/5tc/v+bXP7/m1z+/6Fn//99ZrD5DQ0PogAAABwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////OP/o1qj/uYD6/6Rc//+jWf//sXP///Xt//////////////////////////////Pp///PqP//rWv//6Na//+kW///pl3/6Kh0/0Y6MdoAAABWAAAAGgAAAFIbGyKjW1B74ZV11/undP7/yab//9nA//+wfv7/mlv+/5tc/v+bXP7/mlr+/5pa//+gcvP/RT5b4QAAAFsAAAEEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////B////0z/27/I/7Bw//+iWP//u4X///v4///////////////////8+f//277//7J0//+iV///o1n//6Rb//+kW///pFv//6tm/7eLaPkUEhC2EhIXk1JKbdmOcsr5pHL7/51g//+rdv7/9vD////////l1f//omf+/5pb/v+bXf7/s4P+/8Sf//+tef//hWq9+xMTF64AAAAjAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///xD/+vZt/86n4f+oYv//wI3///79///////////////////8+f//5dH//9Cr//++iv//qWT//6Ra//+kW///pFv//6Rb//qyeP+GdGzThXK66KR1+P+gZP//m1z+/5pb/v+iZ/7/5NL////////+/f//xqH+/5lZ/v+sd/7/8un////////UuP//onH4/09GaecAAABnAAAABgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8g//Hlj//Bj/L/rmz//9e3///w5P//+vb////////////////////////9+///1bP//6Rc//+kWv//p2H//7N3/P7LoNHn2eKjso3/85xd//+bXP7/m1z+/5tc/v+aWv7/t4r+//n1////////7+X//6dw/v/Gov7////////////Lqf7/nmH//4xvyvwZGR+3AAAAKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8C////OP/l0bH/tnv8/6Vd//+sav//uYD//8qf///dwv//7d////n0////////3sP//6dh//+xcv79xJbe+9zDk/v18Ef9//9WzLj+y6Js/v+bW/7/m1z+/5pb/v+ZWf7/nF3+/9a8/////////////9W7///j0v////////fy//+vff7/mlr+/6Nw+/9XTHbrAAAAcQAAAAkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////CP/+/lT/2LnP/65t//+jWv//o1n//6JY//+lXP//q2j//7d+///ElP//uoP//sCO5/vYu6D68epS/P//H////wf///8U8O3/ermW/uydYP7/m1z+/6hx/v+zhP7/p2/+/657/v/w5v////////z5///8+////////+HP//+eYf7/m1v+/55h//+RcdP9IB8pvwAAAC4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///xP/+PN1/8uh5v+oY///pFv//6Rb//+kWv//pFv//6to//67hu3807Ku+u3iXvz//yX///8K////AP///wD//f8B////L9zR/qypef78pWz+/+ja///7+f//8un//+DN///t4v////////////////////7//8Sg/v+aWv7/m1z+/5tb/v+jbv3/ZlmK5gEDAFBVV2cAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////APD//wD///8l/+7hl/+/i/X/pV3//6Rb//+qZv/+uoPz/NCtu/rp3Gn8//8s////Df///wH///8A////AP///wD///8A////CPv8/1fGrv7Wqnj+/+nb////////////////////////////////////////8+z//6p1/v+aWv7/m1v+/5td/v+lcf//oI3XxRgcGS6WmLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8D////Pf/jzLn/uoP+/7iA+P3Npsb75dR1+/z9NP///xD///8C////AP///wD///8A////AP///wD///8A////AP///xns6P+GtY/+8al0/v/Amf7/1rz//+nb///28f///v3/////////////2sP//5xe/v+cXf7/omv+/7CH/fHFr/y61M/xSYiOeATc3d8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Cv/8+ln/6tmw/ujWiPv5+Dz+//8U////A/7//wD///8A////AP///wD///8AAAAAAAAAAAD///8A////AP///wH///8318n+tqZ0/v6ZWf7/m1z+/6Fm/v+tef7/vpX+/9O2///Xvv//rnz+/6Fp/v+wiP3xxa/8uuLc+2/8//wz////Dv///wH///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///w3///8n////Gf///wX8/v8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8L+Pj/YcOo/t6fZf7/m1v+/5tb/v+aWv7/mVn+/5td/v+ia/7/r4f98Maw/Lvh2/tv/f/8M////xH///8D///9AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////H+fh/pKxiP72m13+/5tb/v+cXv7/omv+/7CJ/e/GsPy54t37bf3//DP///8R////A////gD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////A////0DTwv7Bp3b+/6Nt/v+wif3uxrH8t+Ld+2z9//wy////Ef///wL///4A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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fv47My3eAAAAZwAAAAsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8Ao6OjAP///wJ1doo6p5Lh3qd2//+dYP//m1z+/5tc/v+bXP7/m1z+/5pb/v+jaP7/697////////////////////////////////////////////////////////9/P//9O3//9e+//+jaf//p3r6/1VOcPEAAACeAAAAJgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAABQAAABFAgIDjj83MM+oiG3z87OB/v+ua///pV3//6Rb//+kW///snT/i3Fd9AECA6QAAAAmAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAA////AP39/QD///4N29n5YbST/vSdYP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/rHj+//Xv///////////////////////////////////////////////////////////////////+/v//w5z+/59k//+Ues/8HRwj1wAAAGAAAAALAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAACwAAADIAAAB2IR4bu4dvXOnirIH8/7J0//+nYP//pFv//6Rb//+kW///pFv//6pj/9eke/0pJCDUAAAAVgAAAAcAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////EPT1/mfDrP7ioWr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mVn+/7mN/v/8+v///////////////////////////////////fz//////////////////////////////////8mo/v+aW/7/p3n8/2BWfvQBAQCnAAAAKwAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAQEGAAAAIQAAAF0PDg6nYFFG3smee/j9tXv//6pl//+kXP//pFv//6Rb//+kW///pFv//6Rb//+lXP/8s3j/c19P8AAAAJMAAAAcAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wb///9C5N7+qrKM/vmdYP7/m1z+/5tc/v+bXP7/m1z+/5la/v/Ipv7//////////////////////////////////////9/M///Qsv//59f///fx///+/v////////Ho//+wfv7/mlr+/6Bl//+afdn9JCMt3AAAAGkAAAAOAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAVAAAARgABAo5AODHOq4lv8/OzgP7/rmz//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6xn/8WZdvsaFxbJAAAARgAAAAQAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////F/3+/2jQwP7RpnX+/5td/v+bXP7/m1z+/5tc/v+bXf7/17/////////////////////////////////////////t4f//qXL+/6Bl/v+xgP7/xqL+/8+w/v+0hf7/nF3+/5tc/v+bXf7/p3b+/2hcivYDAwKxAAAAMwAAAAIAAAAAAAAAAQAAAAsAAAAyAAAAdyMfHLyEbVvp462C/P+xcv//pV3//6JY//+iWP//o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXf/1snz/W01B6gAAAIIAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wP///8w8fD+jr6h/uygZv7/m1z+/5tc/v+bW/7/oGT+/+bW///////////////////x6P//+fX//////////////////9K0//+bXf7/mVn+/5pZ/v+aW/7/mlr+/5tc/v+bXP7/m1z+/59j//+ef+L+LSw54gAAAHMAAAARAQEABgAAACEAAABdDw4Np2NTR9/Jnnv5/LV7//+pY///r3D//82k///PqP//vor//65t//+lXf//olj//6NZ//+kWv//pFv//6Rb//+kW///pFv//69s/6+LbvkODQy7AAAAOAAAAAIAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////C////07f1/61roX+/Jxf/v+bXP7/mlv+/6hx/v/x6P/////////////+/f//yab//9rD///////////////////28P//s4P+/5pa/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/pnP//3NlmvcFBga2AAAARAAAAEYAAQKOPzcwz6uKb/P0tID+/65r//+lXP//qWX//+LL//////////////v3///w4///3sP//8ic//+1ef//qGL//6NZ//+iWP//o1r//6Rb//+nX//sr37+Rjw04wAAAG8AAAANAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP7+/wD///8c+/v/ccu4/tmkcP7/m1z+/5pa/v+ygv7/+PX/////////////+vf//7WF/v+xgP7/9O7//////////////////93H//+fYv7/m1v+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/55h//+hf+j+NTNE4QAAAJ4kIR23hm9c6uKsgfz/snP//6dg//+kW///o1n//7h+///59f/////////////////////////////9/P//9ez//+XQ///Qq///u4X//6to//+jWv//pFr//7Fx/5d6YvYEBAWrAAAAKwAAAAEAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////BP///zbt6v6YuZr+8Z5k/v+ZWf7/wJn///79//////////////Lq//+pc/7/m1z+/86v///+/v/////////////69///vZT+/5pa/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/qHb//3htn+VYTUPMzaKA9fy1e///qmX//6Rc//+kW///pFv//6NZ//+ydP//8+n///////////////////////////////////////////////////n1///t3v//yZ///6Ze//+oYv/eqHz9MCol2QAAAF0AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8O////VtrP/r+rf/79mlv+/8ek///////////////////m1v//oGX+/5pa/v+ncP7/6t7//////////////////+ja//+ka/7/mlv+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nF/+/6t+/v+votq4576b1P+zdP//pV3//6Rb//+kW///pFv//6Rb//+kW///pVz//8WX///r2///+fT////+//////////////////////////////////////////////bv//+1ev//o1n//rN3/39oVvIAAACaAAAAHwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A/v7/Af///yL4+P96xrD+4KFq/v+2iP7/+PP/////////////z7H+/5tc/v+bXP7/mlv+/8GZ/v/7+P/////////////+/f//xqL+/5pb/v+bXP7/m1z+/5tc/v+cXf7/oWj+/66F/vvCr/rD6Of1ff/bvc7/sHH//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kWv//q2j//7uE///Opv//4sn///fw///////////////////////////////////48v//tnv//6NZ//+rZv/Nnnj8HhsYzgAAAEwAAAAGAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8G////Pujk/qK1kf72n2T+/7+W/v/gzP//07f+/6dv/v+aW/7/m1z+/5tb/v+gZP7/38v//////////////////97J//+dX/7/m1z+/5tc/v+eY/7/qXr+/7qf/ODSyfmU7+/3Sf///0b+8eeX/8OS9P+nYP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Na//+hVv//pl///8OT///w4///////////////////////////////////6Nb//6pl//+kWv//pV3/+bN7/2ZVSO0AAACJAAAAGwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///xP///9g1cj+yKl5/v+aW/7/nWD+/5xd/v+aW/7/m1z+/5tc/v+bXP7/mlr+/7OD/v/07f/////////////Rs///m1z+/5xf/v+kcf7/tJL98Mq7+a/m5vdi/v/7Mf///xT///8U////XP7cwcr/snT//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+lXf//uYD//9/E///59f///////////////////////////////////////86n//+jWf//pFv//6Rb//+tav+7k3P7ExEQwQAAAEcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD//v8C////KPX0/oTCqf7noWn+/5tb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+cXf7/u5D+/9zG///Stv//p2/+/6Bo/v+uhf76wq37yd3Z+Hj5+/k9///+HP///wj///8A////Af///yz+9e2M/8ea7/+oYv//pFv//6Rb//+kW///o1r//6Ra//+xcv//1bL///Xt//////////////////////////////////////////////bw//+2e///o1n//6Rb//+kW///pl7/8rF9/1JFO+YAAACGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wj///9G5N7+q7KL/vmdYP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pa/v+dX/7/n2T+/6h5/v+7n/zf08n5k/Hy+Ev///0l////Df///wH///8A////AP///wD///8M////Uv7gyMD/tHj//6Rc//+kW///o1r//6tn///Jnf//7+H///7+////////////////////////+vb///n1///////////////////jzP//p2H//6Rb//+kW///pFv//6Rb//+wbv+mhGr3CQkJwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////F/3+/2jQv/7RpnT+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+dYP7/pHD+/7SS/e/Ku/qv5+b3X///+i////8T////A////wD///8A////AP///wD///8A///+Af///yX+9/GE/8qf6/+pZP//o1r//69u///jzP///Pr////////////////////////9/P//6NT//8ea///u4P/////////////+/f//yZ3//6NZ//+kW///pFv//6Rb//+kW///p2D/5at9/UM5Mt8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP7+/wP///8v8e/+j72g/u2fZv7/m1z+/5tc/v+bXP7/m1z+/5xd/v+haf7/r4b9+cKt+8jd2Pd3+fv5Pf///hv///8H////AP///wD///8A////AP///wD///8A////AP///wD///8K////Tf7jzrr/tnz+/6Na///Kn//////////////////////////+///v4f//yp///6pl//+7hf//+vf/////////////8+n//7Jz//+jWf//pFv//6Rb//+kW///pFv//6Rb//61e/+ki3fcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////C////0/f1/62roX+/Jxf/v+bXP7/m1z+/55k/v+pe/7/u6H83dTL+JHx8vhM///9Jf///w3///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAP///wD///8A//7+AP///yH++fR9/82l5/+pZP//zKL///////////////////Tr///Tr///sHD//6NZ//+jWf//1bT//////////////////97C//+lXf//pFv//6Rb//+kW///pFv//6Ze//+tbP/9w5TxxayYgQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADu7u4A////AP///wD///8c+/z/csy6/tqndf//n2P//6Vy/v+1lP3uy735rOfn91////sv////E////wT///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8I////R/7o1bH/uYD8/65t///bv///7d7//9q9//+2e///pFv//6NZ//+jWv//rGr//+7g//////////////z6///Dkf//o1n//6Rb//+kW///pV3//6tp//66hPv8zqnT+OHPfuzo5SYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB+fn4AlZWVBsfHxT3Ew9SctaLs6rOW9/a/rPTO29f0dvr8+Tv///4b////B////wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A/urZAP///xz++/lz/9Kt3/+raP//pV7//6pm//+lXf//o1n//6Rb//+kW///o1n//7iA///59f/////////////v4v//rWz//6NZ//+kXP//qmb//7d+/v3Lotz64MuX+fXxVfz//yr///8OAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAADAAAADQAAQJzQT05qnpycc9fXWjHY2RnfbGyrjH7+/oN////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8F////Pv7r3Kb/vYf6/6Vd//+jWv//pFv//6Rb//+kW///pFv//6NZ//+ydf//8ef/////////////06///6Vc//+oY///tXn//cec5fvdxaP58uxe/P//Mv///xb///8F////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEBAQABAAAGAAAAIwAAAF8QDw+pZVVJ38yhfvjvuIv9kXlj8AcHB7UCAgNFAAAAB3FxcQA9PT0A4eHhAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///xb+/fxq/tW02P+tbP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFz//72J///bv///z6n//65t//+ydP/+xJbs+9m+r/nv52f7/v84////Gv///wf///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAMAAAAWAAAASQIDA5JCOTLQroxw8/W0gP//rmv//6pl/++xgP9QRDrsAAAAlQAAACQAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8E////OP7u4p7/v433/6Zf//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWf//p2D//69v//7Aj/L71re6+evhcvv9/j3///8e////Cf///wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAwAAAA0AAAAeScjH7+Kcl7r5K2B/f+ycv//p1///6Rb//+kW///rmv/w5l2+x0aF9cAAABlAAAADwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///xP+/v5j/ti60v+vb///pFv//6Rb//+kW///pFv//6Rb//+mXv//rm3//r6K9/zTscb66Np8+vv7Q/7//yL///8L////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQEABwAAACQAAABgEA8PqWZWSeDOoX35/rV6//+qZP//pFv//6Rb//+kW///pFv//6Vd//20ef+Da1j1AQICtAAAADsAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8D////Mv7x5pb/wpL0/6Zg//+kW///pFv//6Vd//+saf//u4X6/M+r0Prl1If6+fdL/v//J////w7///8C////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAAFgAAAEoDBASUQzoz0a6McPP1tH///6xn//+kWv//pFr//6Rb//+kW///pFv//6Rb//+kW///qWP/5ax//j82L+cAAACIAAAAHQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE5OTgD+/v4A9PT0AP///xD///9c/tzAy/+xc///pV3//6pn//+4gP39zKTa+uHNk/n281P9//8r////Ev///wP///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEBAAAMAAAANQAAAHspJCHAjXRg7OWugf3/sXH//61r//+9iP//t37//6Zf//+kW///pFv//6Rb//+kW///pFv//6Rb//+wb/+0jnH6ExEQzwAAAFgAAAALAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFhYWAB0dHQExcfJNN7UzJf6yJ/z/7yH//vHneT53cWg+fPuW/z//zH///8V////Bf///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEBAQYAAAAiAAAAYREQD6toWErhz6F9+v60ev//qWP//6Zf///Yuf///Pn///jy///KoP//pFv//6Rb//+kW///pFv//6Rb//+kW///pl3/+bR8/25bTPIAAACoAAAAMQAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAENAAAAMgABAG0zNDWgiH13z6OQgM2poZuA4OLkO////xn///8G////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA4AQICi0Q7M9KxjnL09rSA//+tav//pV3//6NZ//+wcP//9Or/////////////6tr//6pl//+kWv//pFv//6Rb//+jWf//pFv//6Rc//+qZP/apn39MCol4gAAAHwAAAAXAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAoAAAAqAAAAZgoLDKtEP1fehne09JSCyfNLSGDdBwgHkCYmJilaWVkCtbW1AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOzUwgZJ4ZOHnr4L9/7Fy//+mX///pFv//6Rb//+jWP//vIb///v4/////////////+jW//+pY///pFr//6Na//+kXP//tnv//9i4///dwv//vYj//7Jy/6ODafkLCwrGAAAATgAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABwAAACMAAABbBQYFoDY0Rdd/b6z1p4Ly/6Zy//+nc///ln7Q/RwcI9cAAABgAAAACwEBAQAAAAAAAwMDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOfGq7z+uoT//6lj//+kW///pFv//6Rb//+kW///o1n//8qg///////////////////avf//pFv//6Na//+vb///0q3///Tr//////////////Dk//+yc//0sn3/Xk9D7wAAAJ0AAAApAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFAAAAHAAAAFECAwGWLCs40HRnm/Gkg+r+p3P//51h//+bXP7/m13+/6h5/f9gV3/0AAEAqAAAACwAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/4svD/7iA/v+lXf//pFv//6Rb//+kW///pFv//6Rb///Xt////////////////v//yZ3//6hi///Hmv//7d3///7+///////////////////17f//s3b//6xn/86fevwjHxzcAAAAbwAAABIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAXAAAARgAAAIskIy3IaV+L7p+C4f2od///n2P//5tc/v+bXP7/m1z+/5tc/v+gZf//m33b/SUjLt0AAABqAAAADgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//r3hv/UsuD/r27//6Rb//+kW///pFv//6Rb//+nYP//5M7/////////////+/j//9Ks///iy////Pn////////////////////////27///zab//6Zf//+kXP//s3b/kXZg9wUFBb0AAABDAAAABgAAAAAAAAAAAAAAAgAAABIAAAA8AAAAfxoaIMBdVXrqmX/X+6d4/v+fY///m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m13+/6d2//9pXo32AgMCsQAAADMAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///0T/8+qc/8ic8f+pZf//pFv//6Rb//+jWv//rWz///Dk//////////////79///7+P////////////////////////r2///ew///uH7//6Vd//+kW///pFv//6hh/+2wf/5NQTjrAAAAkQAAACIAAAADAAAADgAAADUAAAB0EREUtlFLaeSUfMz6qHz7/6p1//+4iv//rHj+/5xd/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+fY///n37j/i0rOeIAAAB1AAAAEgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8Q////VP/q2bf/vYj7/6Zf//+kW///o1n//7d+///58////////////////////////////////////fv//+fS//+/i///pl///6NZ//+kW///pFv//6Rb//+kW///rmz/wJd1+xkXFdQAAABkAAAAMAAAAGcNDQ+uRUBY34p2vPipgPj/o2r//6Nq/v/gzP///Pr///Lr//+6jv7/mlr+/5tc/v+bXP7/m1z+/5pa/v+aW/7/mlr+/6Zy//90Zp34BgcHugAAADsAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA///+AP///xv//v5u/97D0f+0eP//pVz//6JY///Ckf///fv/////////////////////////////8eb//8id//+pY///oVb//6Na//+kW///pFv//6Rb//+kW///pFv//6Vd//y0ev99ZlXzAAAAtgYHB5s8OUzVgnGv9qeB8v+lb///nV///5pa/v+wfv7/+PT/////////////6Nn//6Rq/v+aW/7/m1z+/5tc/v+xgP7/0bX//8il//+mbv//on7r/jYzRecAAAB/AAAAFgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///4C////Lf/59Yj/0a3l/61s//+iWP//yqD///////////////////////////////////Pq///avP//x5r//7d9//+qZv//pFr//6Rb//+kW///pFv//6Rb//+kW///qmT/5LCF/EtEQcx2bJzgpoTt/qZy//+dYf//m1z+/5tc/v+aW/7/pGr+/+XV//////////////79///Jpv7/m1v+/5pa/v+qdP7/7uT/////////////yKX//6Ru//99bKr5CwsNwgAAAEMAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wj///9C//Lno//Fl/T/p2H//7iA///y6P////////////////////////////////////////7+///48///6Nb//7iA//+jWf//pFv//6Rb//+kW///pl///7Fy//7LoerIvMqpspL89p9k//+bXP7/m1z+/5tc/v+bXP7/m1z+/5pa/v+6jv7/+fX/////////////8ej//6t2/v+YWP7/xaH+/////////////////8mn//+cXf//pn/y/0E8U+sAAACIAAAAGQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Ef///1r/59O+/7uE/P+mX///tHn//82m///gx///7+P///r1/////v/////////////////////////////dwf//pVz//6Rb//+mXv//rm3//r6L9/zSscP669198vH+jb+k/uufZv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bW/7/nmH+/9nB///////////////////Uuf//n2P+/+DN//////////////fy//+wfv7/mlr+/6Rt//+Fcbf6Dg8RyAAAAEsAAAAGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///gH///8f//79dP/bvtb/snX//6Na//+jWf//pV3//6xp//+5gf//y6H//93D///t3///+PP///7+////////1bL//6Vd//+saf//u4b6/M+r0Prl1If6+fhJ/v//LP///1Te1v61roT+/Jxf/v+bXP7/m1z+/5tc/v+aW/7/mlv+/5pa/v+uev7/8ur/////////////9vH//8ai/v/07f/////////////iz///n2L+/5tb/v+cX///p372/0hDXu0AAACSAAAAHwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A///+A////zL/+PKO/86n6v+saf//pFv//6Rb//+jWv//o1j//6JY//+lXP//rGn//7h////Inf//yZ7//7J0//+4f/39y6Ta+uHOkfr29FL9//8r////Ef///wP///8c+vv/csq2/tqkcP7/m1z+/5tc/v+bXP7/omj+/6Rq/v+dX/7/mlr+/8mn///9/P/////////////48////v3////////+/v//xJ/+/5pa/v+bXP7/m1z+/6Nq//+MdsH7FBQZzwAAAFMAAAAHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8K////SP/v46n/w5P2/6hi//+kW///pFv//6Rb//+kW///pFv//6Na//+jWv//p2H//7R5//3IneL73cag+fPuWvz//y////8V////Bf///wD///8A////BP///zfs6f6ZuJj+855j/v+aW/7/uY3+/+nc///t4v//3sj//8il/v+9k/7/7uL/////////////////////////////8+z//6p2/v+aWv7/m1z+/5tc/v+cXv7/qHz5/1RNbu8AAACKAAAAEwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///xT///9g/+TPxP+5gP7/pV7//6Rb//+kW///pFv//6Rb//+oYv//s3b//sWY6vvawKn58Olk/P//Nv///xj///8G////AP///wD///8A////AP///wD///8P////WNnO/sCrfv7+nmH+/+HN////////////////////////+fX///v4/////////////////////////////93H//+dYP7/m1z+/5tc/v+bXP7/m1v+/6Jp//+Yg8/4ISIokwAAABUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///4B////I//9+3r/2Lnb/7Fy//+kW///pFv//6dg//+xcv/+wpLw+9e6tvnt4277/v86////HP///wj///8B////AP///wD///8A////AP///wD///8A/v7/Af///yL4+f97xa/+4aJs/v/Nrf//+/n///////////////////////////////////////////////////37//++lv7/mlr+/5tc/v+bXP7/m1z+/51g/v+mdP//s5/v2kRFUE0AAAAJAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///gT///82//bvlf/MpO7/rm3//69v//6/jfX81LPC+endd/r8/UH///8h////Cv///wH///8A////AP///wD///8AAAAAAAAAAAD///8A////AP///wD///8G////Punk/qK1kf72oWj+/7eJ/v/OsP//4tD///Lq///8+f/////////////////////////////v5f//pm7+/5pa/v+bXP7/nWD+/6Rv/v+xi/73xLD8ytPO82GrrqkNAAAAAVRUVAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////C////07/7+Ox/9a17P7Vtc/659eD+vn5SP7//yT///8N////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///xL///9f1cf+yKh5/v+aWv7/mlr+/55i/v+pc/7/uY3+/8ys///gzf//8Of///r3///59v//yqn+/5tc/v+dYP7/pHD+/7GM/vfEsPzK3df7iPb4+07///4i////B1xcWQD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP/9/QD///8V////VP/8+X3+/fxZ/v//Kv///xD///8D////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD+/v8B////KPX1/4TBqP7noWn+/5tc/v+bXP7/mlv+/5pa/v+aWv7/nV/+/6Zu/v+0hP7/soH+/6Bl/v+kb/7/sYz+98Sw/Mvd1/qH9/n7Tv///iz///8T////BP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///wz///8Z////Ef///wT///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wj///9F5N3+rLKL/vmdYP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aW/7/m17+/6Nu/v+yjf72xbH8y93X+4f3+ftP///+K////xL///8E////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Fv3+/2jQwP7RpnT+/5td/v+bXP7/m1z+/5tc/v+dYP7/pHD+/7KN/fbFsfzJ39n7hPj5+0////4r////Ev///wT///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP/+/wL///8v8fD+jr2g/u2fZv7/m1z+/51g/v+kcP7/so3+9sWx/Mjf2fqE+Pn7Tv///ir///8S////BP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////C////03g2f63tJH+/Kl6/v+zjv71xbL8xt/Z+4T4+ftM///+Kf///xH///8D////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP7+/wD///8e+/z/dt/a/8rSx/7Q4Nr9kPj5+1L///4v////E////wT///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/+AAD///////wAAH//////8AAAf//////gAAA//////4AAAD//////AAAAH//4B/4AAAAf/+AH+AAAAA//wAPwAAAAD/8AA/AAAAAH/AAB4AAAAAf4AAHgAAAAA+AAAOAAAAADwAAA4AAAAAEAAADgAAAAAAAAAGAAAAAAAAAAYAAAAAAAAAAwAAAAAAAAADAAAAAAAAAAOAA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R9OJeLf0q4P5/6Jq//+cXv7/m1z+/5tc/v+aW/7/y6v///////////////////v5///w5///3cj//8ai//+xf/7/omf+/5pb/v+ZWP7/mlr+/5tb/v+bXP7/pW///4t4vfsTExbXAAAAaQAAABIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAAEwAAAD4AAACBHBoYwHlmVunarYr86ruW/nRkWPMBAQGsAAAANAAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWFhYAAAAABQAAADsZGh6hY1yB5aKG4vyodv//nmL+/5tc/v+bXP7/m1z+/5tb/v+hZf7/59f///////////////////////////////////79///28P//59j//9K1//+7kP7/qHH+/51g/v+ZWf7/nF///6mB9/9RS2nxAAAAqwAAADYAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAsAAAAtAAAAaQkJCKxXS0HewJp79/q4gv//rmz//7Fw/86jgPwiHhvYAAAAZQAAAA4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAL6+vgAAAAAAAAAACEJCUGWRg8Dkq4P5/6Jq//+cXv7/m1z+/5tc/v+bXP7/m1z+/5pa/v+pcv7/8ur////////////////////////////////////////////////////////6+P//7uP//9vD///Bmv//omf+/6Nr//+Tfcr8Ghof3AAAAHIAAAAVAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGAAAAHgAAAFQAAQGYNC4p0J6Ca/HvtYb+/7Jy//+nYP//pFv//6Ze//m1f/9oWErwAAAAngAAACkAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8C0NXJELSr4oyviP7/nmL//5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5lZ/v+2h/7/+vf////////////////////////////////////////////////////////////////////////8+///0bT//51g/v+pfvr/W1N28wAAALMAAAA9AAAABgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAABQAAAA/AAAAgB0bGMB7aFjp2qqE+/+2e///qmT//6Rc//+kW///pFv//6Rb//+wbv+7lHb6FBMRzgAAAFYAAAAKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8E///9LNHI/aurf/7/m13+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5lZ/v/En/7//v7/////////////////////////////////////////////////////////////////////////////8+z//6p0/v+haP//mIDT/CAgKOAAAAB8AAAAGQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAALAAAALgAAAGsJCQmtVEk/3cKcfPf6uIL//61r//+lXv//pFv//6Rb//+kW///pFv//6Rb//+nYP/xs4L+UUY86gAAAI8AAAAfAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8C////MOro/pO6nP7zn2b+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pb/v/TuP////////////////////////////////////////79///7+f//////////////////////////////////8Ob//6dw/v+bXf7/qXz9/2VchfUCAwK7AAAAQwAAAAcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABgAAAB4AAABTAAEBmDcwK9Gegmzx7rWG/v+ycv//p2D//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///snP/pIVs+AoKCcIAAABHAAAABgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////GP///2TYzv7FrIH+/pxf/v+bXP7/m1z+/5tc/v+bXP7/m1v+/59i/v/i0P////////////////////////////////////////n2///Or///0LH//+bX///28P///v3////////9/P//0rX//51f/v+bXP7/oWf//56C3f0oJzLkAAAAhAAAAB0AAAABAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAUAAAAQAAAAIEdGhi/fGhY6dyrhPv/tnv//6pk//+lXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///qWP/5q+C/jw1LuQAAAB+AAAAFwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Bf///zP29v6Ixa/+5aNv/v+bXf7/m1z+/5tc/v+bXP7/mlv+/6Zt/v/u4//////////////////////////////////////////////awv//nmH+/6Fm/v+xgP7/x6P+/9W7///Ho/7/o2r+/5tb/v+bXP7/nF3+/6l6/v9tYpD3BAUEwwAAAEwAAAAJAAAAAAAAAAAAAAABAAAACwAAAC4AAABrCgoKrlVJP97Bm3z3+7iD//+saP//o1r//6JX//+jWf//pFr//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pVz//7R4/410YPYDAwO1AAAAOgAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///w////9R5uL+q7aT/veeY/7/m1z+/5tc/v+bXP7/mlr+/7B//v/38v//////////////////+PT///n1///////////////////69v//vJH+/5lZ/v+ZWf7/mln+/5tc/v+aW/7/mlv+/5tc/v+bXP7/m1z+/6Bl//+ig+X+MTA+6AAAAI4AAAAhAAAAAgAAAAYAAAAeAAAAUwABAZg4MSzRn4Ns8e60hv7/snL//6Zf//+xc///w5P//7+L//+wcf//pl///6JY//+iWP//o1r//6Rb//+kW///pFv//6Rb//+kW///pFv//6tm/9emf/0pJCHcAAAAbgAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wH///8g/v//b9PG/s6qfP7/nF7+/5tc/v+bXP7/mVn+/76V/v/8+///////////////////2sP//9S5/////v//////////////////59j//6Vr/v+aW/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+od///eWuh+AgICcgAAABTAAAAHAAAAD8AAACBHBoXwHxoWOndrIX7/7Z7//+qZP//pFr//7R5///s3P///fv///v4///x5v//4cn//8yk//+5gP//q2f//6Rb//+iWP//o1n//6Rb//+kW///pFv//6Vd//y1ff91YlPyAAAApgAAAC0AAAACAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8G////OvPy/pDBqP7qomv+/5tc/v+bXP7/mlr+/8ur////////////////////////yKT//6t3/v/v5v///////////////////fz//8ek/v+aWv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+fY///pIPq/jg1R+kAAACaAAAAcgsKCqtWSkDewpt8+Pu4g///rWr//6Vd//+kW///pFv//9e3//////////////////////////////79///38P//6db//9Sy//+/jP//r27//6Vd//+iV///o1n//6Rb//+ua//Fm3r7GRcV0gAAAFwAAAALAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Ev///1ji2/61so3++55i/v+bXP7/nF/+/9rE///////////////////7+P//uY3//5pZ/v/Ipf///Pr//////////////////+7k//+rdf7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/qHX//4F0rPYNDhDJOjMtx6GFbvDvtYb+/7Jy//+nYP//pFv//6Rb//+kW///pV3//9/F///////////////////////////////////////////////////69///7+P//93C///Hm///rmz//6NZ//+nX//1tIH/WkxC7QAAAJYAAAAjAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///yb8/f93z7/+1qd3/v+bXf7/oWX+/+fY///////////////////07P//rHf+/5lZ/v+kaf7/49L////////////////////////Uuf7/nF7+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/omr//6SM4+5pYWG63bKN8v+2e///qWT//6Rc//+kW///pFv//6Rb//+kW///o1n//8WX///69v/////////////////////////////////////////////////////////////+/P//5tP//7Bw//+jWv//sXH/r41x+Q4NDMcAAABNAAAABwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wj///9B7+3+mb2h/u+gZ/7/oWX+/+ja///////////////////o2f//omj+/5pb/v+aWv7/uo7+//fz///////////////////28f//tIX+/5pa/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+eY/7/q3/+/7ys88Tlzbyq/76I//+mX///pFv//6Rb//+kW///pFv//6Rb//+kW///pFr//6dg///Elf//4Mf///Hn///7+P///////////////////////////////////////////////////fv//8KR//+iWP//qGH/7LGD/kQ7NOcAAACEAAAAGgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8W////X93U/r2vhv79nWD+/86u/v/9/P////////7+///Or/7/nF3+/5tc/v+bW/7/n2H+/9e+////////////////////////28T//55h/v+bXP7/m1z+/5tc/v+bXP7/nWD+/6Nv/v+yjf34xLT6wOPj9nH98uac/8aY9P+oY///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Ra//+jWf//p2D//7Fz///CkP//1bL//+/h/////v//////////////////////////////////+vf//72I//+iWP//pFz//7R2/5Z6ZPcEBAS7AAAAPwAAAAYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8D////LPn5/4DJtv7fpHH+/6Jn/v/HpP7/38v+/82u/v+ka/7/m1v+/5tc/v+bXP7/mlr+/657/v/x6P//////////////////7eL//6Vs/v+aW/7/m1z+/5xe/v+gaP7/rIL+/r6n/NvVzviP8PH3Sv///jj///9s/t3DzP+0d///pVz//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1r//6JX//+mXv//wI3//+ra////////////////////////////////////////7d7//61r//+jWv//pFv//6pl/96qgf0xKybgAAAAdQAAABYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////C////0nr6P6iuZr+9J9l/v+aWv7/nWD+/5tc/v+aW/7/m1z+/5tc/v+bXP7/m1z+/5tc/v/Jpv///fv/////////////4s///6Bk/v+bXP7/nmP+/6h4/v+4mvzszcH5qejo9mH+//s1////Gv///w3///86/vTslP/InPH/qWX//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWf//pV3//7mA///ew///+fT/////////////////////////////////////////////1LH//6Rb//+kW///pFv//6Vd//61e/+Ba1n0AAABrQAAADoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///xv///9n2M3+xqyB/v6cX/7/m1v+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pb/v+iZ/7/0LL//+zg///k0///s4L+/5xf/v+jb/7/so79+Ma0+sPf3fd1+fv5QP///iP///8M////Av///wD///8W////YP7iy8P/t33//6Vd//+kW///pFv//6Rb//+kW///o1r//6Rb//+yc///1bL///Xs///////////////////////////////////////////////////59P//u4T//6NY//+kW///pFv//6Rb//+saP/Qon78Ih8c1wAAAHEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wT///8z9vf+h8Wv/uSjbv7/m13+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aW/7/nF7+/6Vr/v+iZ/7/n2b+/6yC/v6+p/zb1s74jfP090z///0r////Ev///wT///8A////AP///wD///8E////M/738Yr/zKPr/6tn//+kW///pFv//6Rb//+jWf//q2f//8qe///u3////v7//////////////////////////////vz////+///////////////////o1f//qmX//6Ra//+kW///pFv//6Rb//+mXv/6tn//a1pM7wAAAKoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8O////UObh/qu1k/74nmP+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/55i/v+nd/7/uJr97M3B+ajp6fZe/v/7NP///xn///8H////AP///wD///8A////AP///wD///8A////Ev///1j+5NC8/7mA/v+lXv//pFv//6Rb//+8h///5c////z5//////////////////////////////38///n0///38b///79///////////////////PqP//o1n//6Rb//+kW///pFv//6Rb//+kW///r23/vJV2+RUTEtMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////IP7//2/Txv7PqXv+/5xe/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+dYP7/pG/+/7KO/ffGtPrC39z3dPn7+D////4i////DP///wH///8A////AP///wD///8AAAAAAP///wD///8A////A////y7++fSE/8+o5/+saf//o1r//7Fy///v4v//////////////////////////////////7+P//8yi//+ubP//3cL///////////////////bv//+2fP//o1n//6Rb//+kW///pFv//6Rb//+kW///p2D/8LSD/mJVSuAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Bv///zry8v6Rwaj+66Jr/v+bXP7/m1z+/5tc/v+bXP7/nF7+/6Fp/v+tg/79v6j72dbP+I3y9PdN///9K////xL///8D////AP///wD///8A////AAAAAAAAAAAAAAAAAP///wD///8A////AP///w////9T/ufVtf+7hf3/pFz//8OS///9+/////////////////////////Xs///Usv//sXL//6JY//+wcf//8+n//////////////////+PM//+nYf//pFv//6Rb//+kW///pFv//6Rb//+kW///pl///r2J/7Gah8EAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A/v7+AP///xL///9Y4tz+tLKN/vqdYf7/m1z+/5td/v+eZP7/qHn+/7ic/OvOw/mm6ur2Xv7/+zX///8Z////B////wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wL///8p/vv3fv/SruL/rGr//7h+///27//////////////59P//3cH//7d+//+kW///o1n//6NZ///Hmv///fz//////////////v3//8md//+jWf//pFv//6Rb//+kW///pFv//6Vd//+raP//uYL/+s6r0ralmE8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADU1NQA/Pz8AP///wL///8m+/z+eM/A/dmrff//oGf+/6Vx/v+zkP32xrb6wODe93P5+/k////+If///wz///8C////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8N////Tf7r3Kz/v4v6/6dh///Elf//4cr//97D//+/i///pl///6NY//+kW///pFv//6Zf///hyv//////////////////8uj//7Jz//+jWf//pFv//6Rb//+lXf//qmX//7Z8//3Inuj63MOq9u3lV/n6+xwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAwMAAAAAACXl5cNxMTCSMTD0Z64qevotZr3+Lyp9N/Ry/GP8/T3S////Sr///8S////A////wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////I/79+3T+17fa/7Bw//+jWf//pl7//6Vd//+jWP//pFr//6Rb//+kW///o1r//61r///w4///////////////////3cL//6Vd//+kW///pFz//6hj//+0eP/+xZjv+9m9tvjt5HD6/P5C/v//I////wwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAABIAAAA8AQIDdjc0MqZuaWnJYmBsymJjaZKdnptK5ublHP///wb///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Cf///0X+7+Oi/8KR9/+nYf//pFr//6Rb//+kW///pFv//6Rb//+kW///pFr//6pl///m0//////////////79///wI7//6NZ//+nYf//sXP//sKS9PvWt8L56t56+vv7SP7//yn///8R////BP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAALAAAAKwAAAGcJCQmrUkc+3L2ZffXmto77mYFs8A0MC8MFBQZiDw8PFAAAAAF6enoAAAAAAP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///x7+/v1t/tq90/+ydP//pFz//6Rb//+kW///pFv//6Rb//+kW///pFv//6Na//+5gv//4cr//+va///Lof//qWX//69v//6/jfj80rHM+ebYhfn5+E7+//8u////Ff///wX///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABgAAAB4AAABSAAAAljIsJ8+cgGrw7rSH/v+zdP//rmv/9beG/19RRfEAAACwAAAAPwAAAAcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wf///8//vHnm//FlvT/qGP//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWf//p2D//6to//+sav//vIf7/M+r1vnj0pD59/VU/f//Mv///xj///8H////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAATAAAAPQAAAIAaGBa/dWNU6NmqhPv/t3z//6pl//+kXP//pFv//65s/86ifvwkIB3jAAAAhwAAACEAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8a/v//Zv7dw8z/tHf//6Vc//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXv//q2j//7mB/v3Mpd/64Muc+fTwW/z//zf///8c////CP///wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAACwAAACwAAABoCQkJq1VJP92/mXv3+beD//+ua///pV3//6Rb//+kW///pFv//6Vd//+2e/+SeGP3BgYGygAAAFoAAAAPAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8F////Ov707JP/yJzx/6lk//+kW///pFv//6Rb//+kW///pV3//6pm//+3fv/9yZ/m+t3Fp/nx62T8/v87////IP///wv///8B////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYAAAAfAAAAUwAAAZYzLSjPnIFq8O60hv7/snP//6dg//+kW///pFv//6Rb//+kW///pFv//6Rb//+pZP/tsoT+TEE57gAAAKUAAAA2AAAABgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD9/PwA////Fv///2D+4MnF/7Z7//+lXP//pFv//6Vc//+pZP//tXn//saa7fvZv7P47uZt+/3+QP///yT///8N////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAAEwAAAD4AAACBGxkXwHdkVejZqoT7/7Z7//+oYf//o1n//6NZ//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//sXD/v5h4+xoXFd0AAAB6AAAAGwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHx8fADp6ekA////BP///zT89O6O/sui7/+saf//qGP//7J1//7DlPP71rm++evgd/r7/Eb+//8o////Ef///wP///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAsAAAAsAAAAaQoJCa1WSkHev5l79/m3g///rWr//6tn///ElP//yZ7//7N2//+kWv//pFv//6Rb//+kW///pFv//6Rb//+kW///pl///Ld//39pWPUBAgLAAAAATwAAAAsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA3NzcAAAAAAo6Ojh28vb1m4826x/7FmP3+w5T599CwzPfm2IL6+flM/v//LP///xT///8F/v7+AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFAAAAHAAAAFIAAACXNS8q0J+CbPHutIb+/7Jz//+nYP//pFv//9Cr///9+////v7//+3f//+0d///o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6tn/+Oug/07My3qAAAAmQAAAC0AAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAMAAAALAAAAGINDg2TUlBRt4+Cd9WXiX23paOia+Pl5zb///8X////Bv///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAuAAAAdxkXFb96Zlfp3KuF+/+2e///qmT//6Rc//+jWv//qmb//+zc///////////////////Op///o1n//6Rb//+kW///pFv//6Ra//+jWf//o1n//6Na//+zdP+ujHH6EA8O1wAAAG8AAAAWAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAACgAAACUAAABaAAAAmiIiK9BpYYnuloXJ9oF2q+4jIyzMCgoKeTExMSFiYmICu7u7AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQDw5tWk1DzcKbfPf7uIP//61q//+lXf//pFv//6Rb//+jWf//tHf///bv///////////////////Npf//o1n//6Rb//+kW///o1n//6lj///Dkv//1bL//8SV//+rZ//5toH/bFtN8wAAALgAAABGAAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAcAAAAfAAAAUAAAAJAYGB3IXVZ565yE1/ysgf3/pnL//6+F//9vZZL3AwQDwQAAAEwAAAAJBgYGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADCqpej8ryR+/+ycv//p2D//6Rb//+kW///pFv//6Rb//+jWP//wY7///z6//////////////z5///Ajf//o1j//6NZ//+mXv//u4T//+HI///79/////////z6///Mo///rGj/2aiB/TAqJeYAAACPAAAAJgAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFAAAAGgAAAEgAAACGEREVwFBLZ+eUf8r6rIP7/6Ns//+cX/7/m1z+/6Bl//+jhOb+MC496AAAAI4AAAAiAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/38bG/7qB//+lXf//pFv//6Rb//+kW///pFv//6Rb//+jWf//zqb///////////////////Xt//+ydP//o1n//7N2///Xtv//9u/////////////////////////kzv//qGL//7V4/56BafgJCAjPAAAAYwAAABIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABUAAAA+AAAAfA0OD7lFQVjii3q8+KuF9/+lcP//nWD+/5tc/v+bXP7/m1z+/5td/v+odv//eWuh+QgICckAAABUAAAACwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/8+qe/8yi7/+saf//pFv//6Rb//+kW///pFv//6Rb//+kW///2r3//////////////////+nW//+xcv//zKL///Dj//////////////////////////////38///PqP//pFv//6hi//K1g/5ZTEHwAAAArgAAAD0AAAAHAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAQAAAANQAAAHEGBwewOjdJ3YJ0rvaph/H+p3T//55i//+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+fY///poTt/jo3SesAAACXAAAAJwAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///9n/+vbuf/Ajvv/qGL//6Rb//+kW///pFv//6Ra//+oYv//59T//////////////////+/i///n1P///fv/////////////////////////////8eX//8yj//+qZv//pFr//6Rb//+vbf/NoX78Ih8b4QAAAIQAAAAgAAAAAgAAAAAAAAACAAAADQAAAC4AAABmAQIBpS4tOtd3a57zpobq/qd1//+eYv//mlr+/5tb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/p3T//4BwrfoLDA3PAAAAXQAAAA4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8s//7+d//gx9H/t37//6Ze//+kW///pFv//6NZ//+wcf//8+n///////////////////////////////////////////////////bv///Wtf//snP//6Ra//+kWv//pFv//6Rb//+lXv//tnz/jXRg9wUFBcgAAABYAAAADwAAAAoAAAAnAAAAXQAAAJwiIivQa2GN76OH5P2qev//pGz//7+X/v/Qsf//uIv+/51f/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nmL//6iD8v5EQFfuAAAAoQAAAC0AAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8I////Ov769o7/1LHl/7Bw//+lXP//pFv//6NZ//+7g///+vb////////////////////////////////////////69v//38X//7h///+kW///o1n//6Rb//+kW///pFv//6Rb//+kW///qmT/67KE/kk+Nu0AAACiAAAAQwAAAE8AAACTHBwjy19Xe+ychNf8q3///6Fo//+bXP7/xJ/+//z6////////+PP//72T/v+aWv7/m1z+/5tc/v+bXP7/mlv+/5pa/v+cXf7/mlr+/6Vv//+LeLz7EhIV1gAAAGcAAAARAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////D////0//8uin/8id9P+rZ///pFv//6JY///Gl////v3///////////////////////////////7//+rZ///Ajv//pl7//6JX//+jWv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFz//7Fx/7uVd/oWFBLYAAAAnRQUGLZVT23nloHN+quC+/+jbP//nF7+/5tc/v+cXv7/28T//////////////////+nb//+lbP7/mlv+/5tc/v+bW/7/oWX+/8Wh///awv//x6T//6Jp//+ogff/Tkhl8QAAAKoAAAA1AAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////Af///xv///9m/ujWv/++ivz/p2H//6JY///PqP///////////////////////////////////v7//+3f///Usv//wpL//7N3//+pZP//o1r//6Rb//+kW///pFv//6Rb//+kW///pFv//6Zf//u5g/+AbVzkNzZGx5OCxPKrhfj/pG///51g/v+bXP7/m1z+/5tc/v+bW/7/wpz///v5//////////////79///Kqf7/m1z+/5tc/v+bXP7/yqj+//38/////////fz//8Kb//+iav//kXzI/BgYHdsAAABxAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wP///8s//79fP/dwtb/tXr//6Rb///Ajv//+fX//////////////////////////////////////////////fz///bu///n1f//wpL//6Rc//+kW///pFv//6Rb//+kW///pV3//6pl//+/i//gw6u9rJ/fya2A//+dYf//m1z+/5tc/v+bXP7/m1z+/5tc/v+aW/7/oWX+/+DN///////////////////y6f//rXn+/5lZ/v+kav7/7N///////////////////8il//+bXf7/qoD7/1pTdfMAAACyAAAAOgAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8I////P//485T/0azp/65t//+mX///wpL//+HJ///x5f//+vf/////////////////////////////////////////////8uj//7J0//+jWf//pFv//6Rc//+oY///s3f//sWX8PvZvrT58+2D0cb/zKl7/v+bXf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlr+/7aH/v/28f//////////////////1rz//5tc/v+2if7/+vj/////////////9vH//7B+/v+aWv7/o2r//5iA0/wdHSTfAAAAeAAAABcAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8A////Ev///1X/8OWs/8aY9v+pZf//o1n//6Zf//+tbP//u4T//8yj///exP//7uH///n0///+/v//////////////////+fT//7d9//+jWf//p2H//7Fz//7CkvX81bbE+endefr7+0f///9U7+3+mb2g/vCgaP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/51e/v/Ttv//////////////////+PP//7aI/v/RtP//////////////////4s///59j/v+bW/7/nF7+/6p9/f9iWYH1AAEAuAAAAEEAAAAHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///x////9r/+bSxP+8hv3/p2D//6Rb//+jWv//olj//6JY//+lXP//rGr//7mB///KoP//3MD//+3e///z6v//17b//6tn//+ubv/+v4z5/NKxzPnn2Ib6+fhO/v//Lf///xX///8b////X9zT/r6uhf79nWD+/5tc/v+bXP7/m1z+/5pa/v+ZWf7/mlr+/5lZ/v+qdP7/7uP//////////////////+fY///v5f/////////////+/f//xJ///5pa/v+bXP7/m1z+/6Fo//+dgtv9JCMt4wAAAIIAAAAcAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wT///8w//z7gv/avdv/tHf//6Vd//+kW///pFv//6Rb//+kW///o1r//6NY//+jWf//pV3//6xp//+ydP//r2///7yG/P3Pqtj549GQ+fb1VP3//zP///8Z////Bv///wD///8D////Lfn5/4DJtf7fpXL+/5td/v+bXP7/nF7+/7B//v++lf7/s4P+/6Vt/v+cXv7/w53///v4///////////////////////////////////z6///qnX+/5pa/v+bXP7/m1z+/5xe/v+pe/7/bGKP9wQEBL8AAABEAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8K////RP/38Zn/z6js/61s//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//6tn//+4gP/9zKTg+uDKnvnz7138//82////HP///wn///8B////AP///wD///8A////C////0nq5/6juJj+9Z9l/v+aWv7/u5D+//Xu///+/f//+fX//+3i///bw///zKv///Ho///////////////////////////////////cx///nV/+/5tc/v+bXP7/m1z+/5tc/v+gZf//ooTk/jAvPd8AAABpAAAACgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////FP///1r+7uCy/8OT+P+pZP//pFv//6Rb//+kW///pFv//6Vd//+qZv//t33//cme6PrcxKj58etk/P7/Pf///yH///8L////Af///wD///8A////AP///wD///8A////Af///xv///9o18z+x6yA/v+cXv7/1rv//////////////////////////////v3///79//////////////////////////////37///AmP7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXf7/q37//352oeEDBANjAAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///yL///9w/+PNyv+6gv7/pl///6Rb//+lXP//qWP//7R4//7Gme772b+0+e7lb/v9/0D///8k////Dv///wL///8A////AP///wD///8A////AP///wD///8A////AP///wT///8z9vb/iMWv/uaibP7/vpX+//bx/////////////////////////////////////////////////////////////+/l//+nb/7/mlv+/5tc/v+bXP7/m1z+/5xe/v+gaP7/so7//6Gay6IAAQAqAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wX///80//z5h//XuOD/s3b//6ll//+ydP/+w5Pz/Na4wPnq33b6+/xH/v//Kf///xD///8D////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAD///8A////AP///wD///8O////UOfi/qu1kv74n2X+/7F//v/Lqv//38v///Dm///69////////////////////////////////////////9W7//+bXP7/m1z+/5tc/v+cXv7/oWj+/6t+/v+6nv3szMH6p83O4DN5eW8GAAAAAB0dHQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8M////Sf/17qL/1rbu/8qf9/3Vtcr56NqC+vn5TP7//yz///8U////Bf7+/gD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8B////IP7//2/Txf7PqXv+/5pc/v+ZWf7/nV/+/6dv/v+2if7/yaj+/93I///u4///+fb////+////////9vD//7SF/v+aWv7/nF7+/6Fo/v+rf/7/up796s/C+7Lo5vpz+/37P////xn///8E29vbAP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Fv///1n/+fWX//Tslf37+lj+//8x////F////wb///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Bv///znz8v6Qwaj+66Fr/v+bXP7/m1z+/5pb/v+aWv7/mlr+/5xe/v+ka/7/soL+/8Wh///Or///ton+/51g/v+gaP7/q37+/7qe/erPwvuy6Of6cf3//Ef///8r////Ev///wT///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///xX///80////NP///xz///8I////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///xL///9X4tv+tLKM/vudYf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aW/7/mVn+/5lZ/v+bXP7/n2b+/6t//v+7n/3qzsL7sujn+nH9//xH////Kv///xL///8E/f39AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wD///8C////Av///wH///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wL///8m/P3/d86+/tendv7/nF3+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nF7+/6Fp/v+rf/7/u6D96dDE+7Dp6Ppy/f/8Rv///yr///8S////BP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8I////Qe/t/pm8oP7woGj+/5tc/v+bXP7/m1z+/5xf/v+haf7/q4D+/7ug/ejPw/uw6ej6b/7//EX///8q////Ev///wT7+/sA////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Fv///1/d1P69r4f+/Z1h/v+cX/7/oWn+/6uA/v+7oP3p0MP7r+ro+m79//xG////Kf///xH///8E////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////A////yz6+v+Azr/+4LCK/v+vh/7+vKH959DE+63q6Ppv/v/8RP///yj///8R////BP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wz///9L8vL/odvV/9PZ0f686un8eP7//En///8u////FP///wT///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD//wAAf/////8AAAD//gAAP/////8AAAD/+AAAP/////8AAAD/8AAAH/////8AAAD/wAAAH/////8AAAD/gAAAD/////8AAAD+AAAAD///wD8AAAD4AAAAB///AB8AAADwAAAAB//+AB8AAADgAAAAA//4AB8AAADAAAAAAf/gAA8AAADAAAAAAf+AAA8AAADAAAAAAP8AAAcAAADAAAAAAPwAAAcAAADAAAAAAHAAAAMAAADAAAAAAGAAAAMAAADAAAAAAAAAAAEAAADAAAAAAAAAAAEAAADAAAAAAAAAAAAAAADAAAAAAAAAAAAAAADAAAAAAAAAAAAAAADgAAAAAAAAAAAAAADwAAAAAAAAAAAAAADwAAAAAAAAAAAAAAD4AAAAAAAAAAAAAAD8AAAAAAAAAAAAAAD8AAAAAAAAAAAAAAD+AAAAAAAAAAAAAAD/AAAAAAAAAAAAAAD/AAAAAAAAAAAAAAD/gAAAAAAAAAAAAAD/wAAABAAAAAAAAAD/wAAAHAAAAAAAAAD/4AAAPgAAAAAAAAD/8AAA/gAAAAAAAAD/wAAB/wAAAAAAAAD/gAAH/wAAAAAAAAD+AAAf/4AAAAAAAAD4AAAf/4AAAAAAAADgAAAP/8AAAAMAAADAAAAP/8AAAAcAAAAAAAAH/+AAAB8AAAAAAAAD/8AAAH8AAAAAAAAD/4AAAf8AAAAAAAAB/gAAB/8AAAAAAAAB+AAAH/8AAAAAAAAA8AAAP/8AAAAAAAAAQAAAH/8AAAAAAAAAAAAAH/8AAAAAAAAAAAAAD/8AAAAAAAAAAAAAD/8AAAAAAAAAAAAAD/8AAAAAAAAAAAAAB/8AAAAAAAAAAAAAB/8AAAAAAAAAAAAAA/8AAAAAAAAAAAAAAf8AAAAAAAAAAAAAAf8AAAAAAAAAAAAAAf8AAACAAAAAAAAAAP8AAADAAAAAAAAAAP8AAADgAAAAAAAAAP8AAADwAAAAAAAAAP8AAADwAAAAAAAAAP8AAAD4AAAcAAAAAf8AAAD8AAB8AAAAAf8AAAD+AAH+AAAAAf8AAAD+AAf/AAAAA/8AAAD/AA//AAAAB/8AAAD/gD//gAAAH/8AAAD/////wAAAf/8AAAD/////4AAB//8AAAD/////4AAH//8AAAAoAAAAYAAAAMAAAAABACAAAAAAAACQAAATCwAAEwsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAAAAVAAAAOgAAAHMBAgGwHB0i2yorMusTFBboAAAA0AAAAI0AAAA7AAAADQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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//////////////v5///y6v//4tD//86v//+5jP//p2/+/51g/v+YWP7/mVj+/5pa/v+bW/7/m1z+/5tc/v+dYP7/qnv//5CAv/sWFhrmAAAAowAAAEEAAAAMAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAwAAAAkAAAAUAAAAIgDAwS6PTYx3qKIdPPvvZb+/8OT//HFof5oXFLyAAAAxQAAAGIAAAAXAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEBAQAAAAAAAAAADAAAAD4AAQCOJiYuzXZumO+rkez9q37//6Bo/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/xqH///79//////////////////////////////////////////////79///38v//69///9jB///Dnf7/sH7+/6Fm/v+bXP7/mVn+/5la/v+bXP7/oWj//66M9v5WUm70AQEB0AAAAHQAAAAhAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAIAAAAGwAAAEAAAAB1AAAAqiIfHdKBbl/t3bGO+/+9iP//sHD//6tn//+5f/+8m4D6GBYV4QAAAJEAAAAwAAAABgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAX19fAAAAAAAAAAABAAAAGAwNDmVTUmfHm4vN9rCL/P+lcf//nmL+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/1br////////////////////////////////////////////////////////////////////////7+f//8ur//+HO///MrP//t4j+/6Zu/v+bXP7/nF7+/6l4//+aiM78Hh4l6QAAAKoAAABHAAAADgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABQAAABIAAAAyAAAAZAAAAJoNDQzHWk5F5cWihvj7v47//7R2//+pZP//pV3//6Rc//+saf/wuY3+VktC8AAAALwAAABWAAAAEgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8CBAUBFnh3lIiyn+32rID//6Bn/v+cX/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tb/v+fY/7/49H////////////////////////////////////////////////////////////////////////////////////////9+///9vD//+bX///En///nF7+/59l/v+vi/r/YFt79QIDAtQAAAB7AAAAJQAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAMAAAAJAAAAFEAAACIBQUFujs0L92iiXTz77yS/v+4f///q2j//6Ze//+kW///pFv//6Rb//+nX///uX//p4p0+Q0MDNoAAACEAAAAKAAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wH///8LyMvSIb618LGwiv7/n2T+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pa/v+pcf7/7+X////////////////////////////////////////////////////////////////////////////////////////////////////////38f//t4r+/5la/v+ndf//norU/CUlLesAAACxAAAATQAAABEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAACAAAABsAAABAAAAAdQAAAKojIB3TgW9g7d2xjvz+vIf//69v//+nYf//pFz//6Rb//+kW///pFv//6Rb//+lXP//rmz/5bSM/UE5M+wAAACxAAAASgAAAA4AAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wH///8X9ff6Q8vB/cisgv7/nWD+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5lZ/v+zg/7/9/L/////////////////////////////////////////////////////////////////////////////////////////////////////////////3cf//51f/v+eZP7/roj8/2pjifYFBQXYAAAAgwAAACoAAAAGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAQAAAASAAAAMwAAAGQAAACaDAsLx1xQR+XGo4b4+r6O//+0dv//qWT//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///qGH//rqF/5F6aPcHBwfTAAAAdgAAACAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wH///8Z/v/+U9zY/rS2lf78oGj+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5lZ/v/Bmv7//fz/////////////////////////////////////////////////////////////////////////////////////////////////////////////4M3//59k/v+bXf7/pnL//6KM3f0tLDftAAAAtwAAAFQAAAATAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAADAAAACUAAABRAAAAiQQEBLs8NTDdpIp18++7kf7/uX///6to//+mX///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pVz//7Fx/9esifwuKSXoAAAApQAAAD4AAAAKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8P////SPb2/ovLu/7iqn3+/51h/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pa/v/Qsf////////////////////////////////////////////////////////v6///w5///+PP///79///////////////////////////////////+/v//za3//5pb/v+bXP7/nmP+/66G/v91bZj4CAgJ3AAAAIkAAAAuAAAABwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAgAAAAbAAAAQAAAAHUAAACrJCAe1IJvYO7csI77/7yH//+wb///p2H//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6lk//q7if95Z1n0AQICywAAAGkAAAAZAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8F////Kv///2ro5f6vvKH+9qNu/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlv+/59i/v/eyv////////////////////////////////////////////////////////n1///Ho/7/uo7+/9Gz/v/l1f//9O3///37///////////////////q3f//r3z+/5pb/v+bXP7/nF3+/6Rv//+njuX9NTRC7wAAAL0AAABbAAAAFgAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAFAAAAEwAAADMAAABjAAAAmQ4NDMZfU0nmxaGF+Pq+jv//tHb//6lk//+lXf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Vd//+0d//HooP7Hxwa5AAAAJgAAAA0AAAABwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////D////0P9/v6B1s3+z7CK/v+fZf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlr+/6Vs/v/p2//////////////////////////////////////////////////////////////i0P//o2j+/5pZ/v+jav7/s4L+/8im/v/cxf7/5dT//9nA//+ygv7/nF3+/5tc/v+bXP7/m1z+/55i/v+tg///e3Gh+AoKC98AAACTAAAANAAAAAkAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAwAAAAmAAAAUgAAAIkDAwO6OjMu3aSKdfPyvZL+/7l///+raP//pV3//6Na//+kWv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+rZ//0uoz+YVRJ8gAAAMEAAABcAAAAFAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////A////x3///9b8vL+m8az/uqoeP7/nWD+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mVr+/699/v/z7P/////////////////////////////+/v/////////////////////////////8+v//xqL+/5pa/v+ZWv7/mFj+/5pa/v+eYf7/o2n+/59i/v+aWv7/m1z+/5tc/v+bXP7/m1z+/5xd/v+jbf//qY7q/j89TvEAAADEAAAAYgAAABkAAAACAAAAAAAAAAEAAAAHAAAAGgAAAEEAAAB3AAAArCMgHdSBbmDu3bGO/P+9h///r27//6Zf//+jW///p2H//6dh//+kWv//olf//6JX//+jWf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+mXv//t3z/spN6+hIREN4AAACLAAAAKwAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wj///8y////cuXh/ra5m/75omv+/5xd/v+bXP7/m1z+/5tc/v+bXP7/mVn+/7uQ/v/69v////////////////////////z6///k0v//9vD/////////////////////////////7eH//6x3/v+ZWv7/m1z+/5tc/v+aW/7/mlr+/5pb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+dYf7/rID//4h7s/oRERTiAAAAmQAAADgAAAAKAAAABQAAABIAAAAxAAAAYwAAAJsQDw7IYFRK58Shhfj5vY3//7R2//+pZP//pFz//6lk///Mov//4sv//+PN///Wtf//w5L//7J0//+oYf//o1n//6JX//+jWf//pFr//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//rWr/67eN/ktCOu4AAAC3AAAATwAAAA8AAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8S////Sfv8/ofSx/7WroX+/59k/v+bXP7/m1z+/5tc/v+bXP7/mlv+/8qn/v/+/f////////////////////////Xv//+3iv7/2L/////+/////////////////////////v7//9O4/v+dYP7/mlv+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/omr//62O8v5JRlzyAAAAxwAAAGcAAAAkAAAAJwAAAFEAAACIAwMDuj02Md6mi3X08LuR/v+5f///rGn//6Ze//+kW///pl7//9Cs///7+P///////////////v//+vb///Dk///gx///zaX//7qC//+sav//pVz//6JY//+jWP//pFr//6Rb//+kW///pFv//6Rb//+kW///p2D//7qC/56Eb/gKCgnXAAAAfAAAACIAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8D////If///2Dw7/6hwq3+7qZ1/v+cX/7/m1z+/5tc/v+bXP7/nF7+/9a9/////////////////////////////+7j//+ncP7/s4T+//Pr//////////////////////////////Tu//+0hf7/mVn+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nWD+/6t8//+Nfrr6ExMW4wAAAJ4AAABfAAAAdAAAAKohHhvTgG5e7eG0kPz/vYf//69u//+nYP//pVz//6Rb//+jWf//tHn///Pq/////////////////////////////////////////fv///Xt///n0///1LL//8CO//+wcP//pl///6JX//+iV///o1n//6Rb//+kW///pVz//7Bv/9+wi/02MCvqAAAAqgAAAEMAAAALAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Cv///zf///9339r+v7aV/vyhaf7/m13+/5tc/v+bW/7/oWb+/+PS/////////////////////////////+LP//+gZP7/nV/+/9Cz///9+//////////////////////////////cxf//oGT+/5pb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m13+/6Fp//+tjvT+Uk9n8AAAAMcAAACjEQ8Pv19TSeXFoob4+r6O//+0dv//qWT//6Vd//+kW///pFv//6Rb//+iWP//wY////v4/////////////////////////////////////////////////////////v3///jy///t3///3MH//8md//+2e///qGP//6JY//+jWf//pFv//6hi//28h/+Cbl/1AgIDzgAAAG4AAAAcAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///xX///9P+fn+js7B/t2sgf7/nmL+/5tc/v+aWv7/qHL+/+7k/////////////////////////////9K2//+cXv7/mln+/6t1/v/o2v/////////////////////////////59P//v5b+/5pa/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/51g/v+sf///lYnD9xkaHs9BOzXLq5B77u+6kP3/uH7//6xo//+mXv//pFv//6Rb//+kW///pFv//6Rb//+jWP//uoP///fw//////////////////////////////////////////////////////////////////////////////z6///y6f//5dD//8SW//+nYP//o1n//6Vd//+zdP/Opob7IyAd5gAAAJ0AAAA4AAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wX///8n////Z+zr/qe/p/7ypXL+/5xe/v+aWv7/sYD+//fy/////////////////////////Pv//8Od//+aWv7/m1z+/5pb/v/Bmv//+fX/////////////////////////////6Nn//6dv/v+ZWf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5xe/v+od///qZbi6ldUWqXVtJbk/8GO//+vbv//p2H//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWv//qWP//9zA///+/f////////////////////////////////////////////////////////////////////////////////////////fx///Inf//o1n//6Rb//+qZf/3u4v/bF1R8wAAAMUAAABgAAAAFQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8M////Pf7//3zb0/7Hs5D+/aBn/v+ZWv7/soH+//jz////////////////////////9/L//7WF/v+aWv7/m1z+/5pa/v+iaP7/3sn//////////////////////////////fv//8qo/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nF7+/6Fo/v+xi/7/uq7uwdLDuo/9yp/3/69v//+lXf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//69w///Usf//6tn///fx///9/P/////////////////////////////////////////////////////////////////////////////hyf//p2H//6Na//+mXv//tnr/vZuA+hYUE+AAAACPAAAALgAAAAYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8C////Gf///1X39/6Tyrr+46p8/v+cX/7/p3D+/+zh////////////////////////6t3//6dv/v+aW/7/m1z+/5tc/v+aWv7/toj+//Pr/////////////////////////////+7j//+sd/7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+eY/7/pXL+/7KO/v/DtPvY2dnxgfrw55f/0avx/7Bx//+lXf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+lXf//rm3//76K///Qqv//48z///Lm///69v///v3////////////////////////////////////////////////////////hyf//p2D//6Ra//+kXP//rGn/8LmN/lFHP+8AAAC6AAAAVAAAABEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Bv///yz///9s6OX+sLug/vejbv7/nF7+/8Kc/v/07P/////////////48///xqP+/5xe/v+bXP7/m1z+/5tc/v+bW/7/nmD+/9G0///9/f////////////////////////38///Jp/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/nWD+/6Js/v+tg/7/u6L978zC+bPg4PJj+vr6VP7+/YD+48zK/72H//+oY///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kWv//o1n//6JY//+kW///qGP//7N2///Mo///9Ov////////////////////////////////////////////////////+///Srf//pFr//6Rb//+kW///pmD//7mA/6SIcvgLCgraAAAAgwAAACYAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///w////9D/P3/gtbM/tCwiv7/n2T+/5xe/v+2iP7/07f+/9i//v+9lP7/n2P+/5tb/v+bXP7/m1z+/5tc/v+bXP7/mln+/6t2/v/r3v/////////////////////////////Uuf7/m13+/5tc/v+bXP7/m1z+/5xf/v+gZ/7/qXr+/7aY/fnGuPrM3Nn2gvP09k/+/vw1////M////17+9u+Z/9Cq7v+wcf//pV3//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Na//+iWP//qGH//8CM///iyv//+vb///////////////////////////////////////////////////fw//+6gf//o1n//6Rb//+kW///pFz//65t/+W0jf1AODLsAAAAsQAAAEkAAAAPAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wP///8d////W/Pz/prGtP7pqHj+/51g/v+ZWP7/m13+/5xe/v+aWv7/mlv+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tb/v/Env//+fb///////////////////38///Jpf//m1v+/5tc/v+cXf7/nmP+/6Vy/v+yjf7+wa773tTP95rs7fVe/P37P////iv///8V////Dv///zX+//90/uXRxP+/jP7/qWT//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kWv//o1n//6Ze//+7gv//3cH///fx/////////////////////////////////////////////////////////////+TP//+pZP//o1r//6Rb//+kW///pFv//6dh//+7hf+Se2j3BgYG1AAAAHcAAAAjAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8I////Mf///3Hk4P63uJv++qJs/v+cXf7/mlv+/5pb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pa/v+jaP7/2L////r4//////////7//+fX//+rdv7/mlv+/51g/v+ibP7/rYP+/7yk/e7NxPmz5OT0bPn6+Ef///0y////HP///wr///8C////Af///xf///9T/vjzk//Tsen/snT//6Ve//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+kW///tHf//9Sx///z6f////7//////////////////////////////////////////////////////////////v3//8yi//+jWf//pFv//6Rb//+kW///pFv//6Vc//+xcf/ZrYr8Lyom6QAAAKUAAABFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////Ef///0n7/P6H08f+1a6F/v+eY/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/pGr+/8Ga/v/UuP//zq7//6hx/v+bXf7/oGf+/6l6/v+3mP76x7j6ytza9X/09vdP/v78Of///yP///8P////BP///wD///8A////AP///wb///8w////b/7p2br/wpH8/6pm//+kW///pFv//6Rb//+kW///pFv//6Rb//+kWv//o1r//65r///Knv//7d7///38////////////////////////////////////////////////////////////////////////8+r//7Z7//+jWf//pFv//6Rb//+kW///pFv//6Rb//+pY//8vIn/fGpb9AEBAsoAAAByAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////A////yH///9g8O/+oMKt/u6mdP7/nF/+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlr+/5pa/v+cXv7/m13+/51g/v+lcv7/so7+/sGu/ODUz/eY7e71Wv39+j7///8q////FP///wb///8B////AP///wD///8A////AP///wH///8T////TP7694v+1rbj/7R3//+mXv//pFv//6Rb//+kW///pFv//6NZ//+oYv//wY3//+XO///69v/////////////////////////////////////////////+/f///v3/////////////////////////////38b//6dg//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXf//tHb/y6WF+x8cGuMAAAChAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wr///83////d9/Z/sC1lf78oWn+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+dYP7/omz+/62D/v+8o/3vzcP4seXl9Gr6+/hG///+Mf///xr///8J////Av///wD///8A////AP///wD///8A////AP///wD///8F////Kv///2n+69y0/8SV+/+rZ///pFz//6Rb//+kW///pFv//7d9///avP//9u7//////////////////////////////////////////////////+/j///cwP//+fP////////////////////////8+v//x5n//6JY//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///qmb/97yN/2FUSfAAAADGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wH///8V////T/n6/o3OwP7drID+/55i/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nF/+/6Bn/v+pe/7/t5j9+Me5+snc2fWA9PX2Tv3+/Dj///8i////Dv///wP///8A////AP///wD///8A////AAAAAAAAAAAA////AP///wD///8A////EP///0j++/iH/tm63/+2ev//pl///6Rb//+jWf//tnz//+3f///+/v/////////////////////////////////////////////27///2br//7R3///Kn////Pr////////////////////////x5f//sXP//6NZ//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pl7//7d8/7OTevgUExLWAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8E////J////2fs6v6pv6b+86Rx/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5xe/v+fZP7/pnP+/7KO/v7Brvze1M/2lu3u9Vv8/fo////+Kf///xT///8G////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////BP///yf///9m/u7hrv/Gmfn/rGn//6Rc//+kW///1LH/////////////////////////////////////////////+vb//+HI//+8hv//pl///6Ze///iy//////////////////////////////avf//pl///6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFz//65t/+y9lvxhV0/TAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////DP///z3+/v992tP+yLOP/v6gZ/7/m13+/5tc/v+bXP7/m1z+/5tc/v+bXf7/nWH+/6Nt/v+uhf7/vKT87M7E+LDl5fVr+fr4Rv///jH///8b////Cv///wL///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///w7///9E/vz6g/7bv9r/t37//6Zf//+pZP//5c////////////////////////////////////z6///o1P//xJT//6lk//+iWP//olj//7V6///07P////////////////////////v3///Ajv//o1j//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pl7//7Bw//nJoviXh3umAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///xn///9W9/f+k8q6/uOqfP7/nWH+/5tc/v+bXP7/m1z+/5xf/v+gaP7/qXv+/7ea/fjHuvrH3dv1fvT29k/+/vw4////Iv///w7///8D////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wP///8j////Yv7w5an/yp72/61r//+lXf//2Ln////////////////////////+/f//7uH//8yk//+ta///o1n//6Na//+kW///o1n//8ui///+/f///////////////////////+zd//+ubf//o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Vd//+pZP//snP//8SU//LRtb9rY106AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wb///8s////bOjm/rC8of73pG/+/5xf/v+cXv7/n2T+/6Z0/v+zj/79wrD73NXQ95bt7vVZ/P36Pv///yr///8U////Bv///wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8M////QP79/H7+38bS/7qD//+mXv//tHf//+jV///79////Pr///Pq///Vsv//sXP//6Na//+jWf//pFv//6Rb//+kWv//qWX//+XR//////////////////////////7//9Sx//+lXP//pFv//6Rb//+kW///pFv//6Rb//+lXf//qGP//7Bx//+9if/9zafr+d3GqvHm3VDl5eUWAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGRkZACZmZkA7OzsAP///wD+/v4O/Pz7RPb3+YbVzfrTtpb+/6d2/v+mdf7/r4f+/72l/OzOxfit5ub0afn6+Ub+/v4x////Gv///wn///8C////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8C////H////13+8+ug/82l8v+vbv//pFv//69v///Bkf//xpj//7Z7//+lXP//o1j//6Rb//+kW///pFv//6Rb//+iWP//tnz///bv////////////////////////+PL//7uE//+jWP//pFv//6Rb//+kW///pFz//6dh//+ubf//u4T//sui8Prbwrv36+F6+Pj4Tfz9/i3///8UAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEhISAAAAAAFOTk4Hn5+fJby8u2DBwcmgv7jm4bun9/i8qPj2wrfw0tTS6oTy9PRN/v78N////yL///8O////A////wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Cf///zn+/v54/uPNyv+9iP//qGP//6JY//+hV///olf//6JY//+kWv//pFv//6Rb//+kW///pFv//6Rb//+iWP//wpH///v4////////////////////////59X//6lm//+jWv//pFv//6Rc//+mYP//rWv//7iA//7InfX72b3G+OndhPj491X8/v8/////Kv///xP///8GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAA0AAAAnAQEBTwoLC3koKCiaVlVZuGRjcspvb325f4CDha+vrVPi4uEu/Pz8FP///wb///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Av///xr///9X/vbwmP/Qq+3/sXH//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+iWf//u4T///fw///////////////////9/P//zKT//6Rb//+kW///pl///6to//+2fP/+xpj4/Na40fjm2I349vRb/f7/Qv///y7///8Y////CP///wL///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAJAAAAHAAAAEMAAAB5AAAAriUhHtGJd2jowKOJ8Y9+a+klIh/PBQUFmyEhIVNFRUUcY2NjBP///wDf398A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wf///8z/v//cv7m08L/v4z+/6lk//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kWv//qGL//9e3///59f///v7///38///jzP//rm7//6Vd//+qZv//tHj//sOT+/zTstr449OY9/PxYPv9/kX///8x////G////wr///8C////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABQAAABQAAAA0AAAAZgAAAJ0SERDJZFdM6Mmkh/n7wJH//76H//7Hmv+MeGj3BgYG2wAAAJAAAAA4AAAACwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8W////Uv7485L+07Dp/7J0//+lXv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//6ll///Bj///06///8eb//+raP//qGP//7J0///Aj/790a3i+eHOovfx7Gj7/P1J////Nf///x7///8M////A////wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAANAAAAKAAAAFUAAACMBQUFvEA5M9+rjnj0872S/v+4ff//q2j//6hi//+xcv/ot4/+SUA58QAAAMkAAABvAAAAIgAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8G////L////27+6Ne8/8KQ/P+qZv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+iWP//pFv//6Zf//+vcP//vor//c6p6PreyK/37uhv+vv8TP7//zj///8i////Dv///wT///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAACQAAAB0AAABEAAAAewAAAK8lIR7VhnJi7uK0kPz/vYb//65t//+nYP//pFz//6Rb//+nYP//uH//uZh++hYVE+gAAACtAAAATgAAABMAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////E////03++faM/ta15P+0d///pl7//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Vc//+nYv//r27//7yG//7MpO/628O69+zkdvn6+k/9//87////Jf///xH///8F////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAUAAAAUAAAANQAAAGcAAACeExIRymVYTejJpIf5+76N//+zdP//qWP//6Vd//+kW///pFv//6Rb//+kXP//q2f/+r6N/3poWfYDAwPZAAAAiQAAADEAAAAJAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Bf///yv///9q/uvctf/ElPv/q2f//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//p2D//61r//+5gf/+yZ70+9m+w/jq34H5+PhU/f//Pv///yn///8U////Bv///wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAADgAAACgAAABVAAAAjAYGBrxDPDXfrpF69fO9kf7/uH3//6tn//+mXv//pFv//6Rb//+kW///pFv//6Rb//+kW///pV7//7Jz/9+yjf07NC7uAAAAwgAAAGUAAAAdAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///xH///9J/vv4iP7Yut//tXr//6Zf//+kW///pFv//6Rb//+kW///pFz//6Zf//+saf//t33//saa9/vXuc3459mL+Pb1Wf3+/0H///8t////F////wf///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAkAAAAeAAAARgAAAHsAAACuJiIf1Yh0ZO/itI/8/7yF//+ubf//pmD//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6hi//+7g/+ojHX5Dw4N5AAAAKMAAABFAAAAEAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wT///8n////Zv7u4a7/xpn5/6xp//+kXP//pFv//6Rc//+mXv//q2f//7V5//7Elfr81LTX+OTUlff08V/7/f9E////MP///xr///8J////Av///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAFAAAAFAAAADYAAABpAAAAoBMSEctkV0zoyaWH+fy+jf//s3T//6hh//+kW///pFr//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rc//+tav/zu47+ZFZL9AAAANQAAAB/AAAAKwAAAAcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADHx8cA+vr6AP///wD///8O////RP37+oP+277b/7d+//+nYf//pV7//6ll//+zdv//wZD9/NGv3/niz5/38u5m+/z+R////zP///8d////DP///wL///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAA4AAAApAAAAVgAAAI4HBwe+Rj434KyQefXxu5D+/7h9//+rZ///pV3//6pm//+sav//pl7//6NZ//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+mX///tXf/06qK/CwoJO0AAAC6AAAAWwAAABkAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEhISAKioqADX19cE6OjoJuvs7Wjx5Nmz/syk+f+1ev//s3f//7+M/vzPqub538mr9+/pbvr7/Ev+//83////If///w7///8D////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAIAAAAHQAAAEUAAAB7AAAAsCklItaNeGfw47WQ/P+8hf//r23//6dg//+lXf//x5n//+jV///s3P//277//7R4//+jWf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///qWP//72H/5iAbPgJCQngAAAAmQAAADwAAAANAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAQAAAAOKioqKGZnZ1aYl5WP3MWy2vjMqPn4zKr06s+5werg2Xr3+PlQ/f//Ov///yT///8Q////BP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABIAAAA0AAAAaAAAAJ8TEhHLaFpP6c2nifn8voz//7J0//+oY///pV3//6NZ//+3fv//9Oz//////////////////+XQ//+sav//o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//69t/+25j/5SRz/xAAAAzQAAAHUAAAAmAAAABgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAADAAAACIAAABJAAAAegAAAJ4YGRuwSklKwHJqY8t4cGizenp5erS1tk7p6eks/v7+E////wb///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGwAAAEsAAACKBAQEvkQ8NuCwk3z1872R/v+3fP//q2f//6Ve//+kW///pFv//6NY///PqP////7///////////////////r3///Aj///o1j//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+iWP//o1n//6Zf//+3fP/CnoL7HhsZ6gAAALMAAABUAAAAFQAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAoAAAAdAAAAQQAAAHMAAACmDQ0PzkdFWemHf6/1lIjC9Gxoi+kXGBzNBQUFlCMjI0hQUFAVgoKCApKSkgD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASQAAAJMmIh/RjHdm7+W3kfz/u4T//65s//+mYP//pFz//6Rb//+kW///pFv//6Vd///exP////////////////////////z6///Elf//o1n//6Rb//+kW///pFv//6Rb//+jWv//o1r//6to//+0eP//rm7//6Vd//+pZf/8vYv/hnFh9gQEBN0AAACRAAAANwAAAAsAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAIAAAAGQAAADoAAABrAAAAngYHB8g6OUnlh3uw96+U8P6wiP//roT//7Wa+P9mYYD1AQIB0wAAAH0AAAAoAAAABgAAAAACAgIASEhIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIyAea3RmWsjRq4z4/r+N//+yc///qGP//6Vd//+kW///pFv//6Rb//+kW///o1r//6to///q2v////////////////////////jz//+7hP//o1n//6Rb//+kW///pFr//6NZ//+pY///wpH//+XR///17f//7+H//9Ku//+pY///sHD/57aP/UU8NvAAAADIAAAAbQAAACEAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABgAAABYAAAA1AAAAYgAAAJYDBATCLi054XlwnfSsk+z+r4X//6Ru//+eY/7/nmL+/6h2//+ijtz9KCgy7AAAALUAAABRAAAAEgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAz7qpjPjLp/n/uH7//6tm//+lXv//pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//7V5///17P////////////////////////Dl//+wcf//o1n//6Rb//+jWf//pl///7qB///ewv//+PL///////////////////z6///InP//pl7//7l//7iXffoXFRPnAAAAqgAAAEsAAAASAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAUAAAASAAAALgAAAFsAAACPAQEBvCQjLN1tZo3yp5Hi/bGJ//+lcf//nmL+/5xd/v+bXP7/m1z+/59j/v+vh/7/cmmT9wUFBdsAAACHAAAALAAAAAYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/eTQtP/GmP//q2j//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//7+L///69v///////////////////////+XQ//+oY///o1j//6Rb//+zdf//1LD///Pp///////////////////////////////////fxv//p2D//6tn//m9jf90Y1b1AAAB2AAAAIcAAAAwAAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAEAAAADwAAACgAAABTAAAAhwAAALYdHiTZYVx876CN1/uxjf3/p3X//59k/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5xd/v+lcP//po7k/TIxPu4AAAC7AAAAWAAAABQAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/vLpn//SrvD/snT//6Zf//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//8uh///+/f///////////////////////9Wz//+jWP//rWr//8qf///s3f///fz////////////////////////////////////////Usv//pFz//6Ve//+zdP/br4z8NC4p7gAAAMEAAABkAAAAHQAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAwAAAAjAAAASwAAAH4AAACvFhYa1FdUbuyZiMv6sY/6/6l5//+gZv7/nF7+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+eYv7/roT//3txofgICQneAAAAjwAAADEAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////e/7s3b7/xpn7/61r//+lXf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//9e3/////////////////////////Pr//8ib//++if//5M7///v3/////////////////////////////////////////v7//+nX//+1ef//pFr//6Rb//+oYv//u4T/p4p0+Q4ODeQAAACiAAAARAAAAA8AAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAKAAAAHQAAAEIAAAB1AAAAqA4PEc9KR1zpkYO/+LCR9v6rfP//oWn+/51f/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+cXf7/pG7//6qP6/46OEjwAAAAwQAAAGAAAAAYAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////Vf79/Iz/4cnW/76J//+qZf//pFz//6Rb//+kW///pFv//6Rb//+kWv//p2H//+TP/////////////////////////Pr//+nX///17f/////////////////////////////////////////////06v//07D//7Fz//+kW///pFv//6Rb//+lXP//rWr/9byP/mNVSvMAAADTAAAAfgAAACoAAAAHAAAAAAAAAAAAAAACAAAACAAAABoAAAA8AAAAbAAAAJ8ICAnJPjxN5od8sfeukvH+rID//6Bo//+bXf7/mlr+/5pb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nWH+/62B//+Cd6v5DA0O4QAAAJcAAAA3AAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////Jf///2D++fWe/9i45/+3fP//p2H//6Rb//+kW///pFv//6Rb//+jWf//r3D///Dl////////////////////////////////////////////////////////////////////////+fT//9zA//+3ff//pV3//6NZ//+kW///pFv//6Rb//+kW///pl///7V4/9CoiPwpJSHsAAAAuQAAAFoAAAAXAAAABAAAAAYAAAAWAAAANwAAAGUAAACYAwQDwy8uO+F9dKP0rZTu/q6E//+jbf//oGX+/7aI/v/FoP//t4n+/6Bl/v+aW/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m13+/6Jr//+sj/D+RkRY8QAAAMcAAABnAAAAGwAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////Cf///zH///9x/vLpsP/NpvT/sXL//6Ze//+kW///pFv//6Rb//+jWf//uoL///jz//////////////////////////////////////////////////////////////v4///kzv//v4r//6Zf//+iWf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6lk//69iP+Wfmv4CAgH4AAAAJcAAAA8AAAAGgAAAC4AAABdAAAAkgIDAr4nJjDeb2iP8qiS5P2wiP//pXD//55i/v+fYv7/z7H///n1///+/f//+fX//9a8/v+iZv7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tb/v+aWv7/mlv+/51g/v+rff//jX+7+hMTFuQAAACfAAAAPQAAAAsAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////Af///w7///9B////gP/p18b/xJX9/6xp//+lXP//pFv//6Rb//+jWP//xZb///37///////////////////////////////////////////////////9/P//7Nz//8ib//+qZv//olj//6Na//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Vd//+vbv/suI/+UEU98QAAAMwAAAB7AAAAWQAAAIIAAAC3ISEo2mVggfCgjdj7sYz9/6d0//+fZP7/nF7+/5pa/v+vfP7/9O3///////////////////z5///Enf7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlr+/51g/v+ka/7/n2P+/5pb/v+haP//ro71/lBMZfMAAADNAAAAbwAAAB8AAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wL///8Y////U//9+5D/38ba/7yG//+pZP//pFz//6Rb//+jWf//0av///////////////////////////////////////////////////Xt///Pqf//rm3//6FW//+iWP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+nYP//uH3/wJ2B+hsYFuUAAAC2AAAAoxcXHMpaVnPsnIvP+7CO+/+peP//oGb+/5xe/v+bXP7/m1z+/5lZ/v+5jf7/+vf////////////////////////r3v//qXL+/5pa/v+bXP7/m1z+/5tc/v+bW/7/rXn+/9i////q3f//4s///8CZ//+cXv7/qnr//5SExvsYGR3nAAAApgAAAEQAAAANAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8F////Jf///2X+9/Ki/9Wz6/+1ev//p2D//6Rb//+kXP//277///////////////////////////////////////////////////Xu///avf//x5r//7Z8//+raP//pV3//6NZ//+jWf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//q2b/+7+O/4h1Ze8JCQnHSklc0JiLyPWxkfn/qnv//6Bo/v+cX/7/m1z+/5tc/v+bXP7/m1z+/5pb/v+pcv7/6Nr////////////////////////+/f//z7D+/5xd/v+bW/7/m1z+/5pb/v+mbv7/5tX///////////////////Tt//+wfv7/n2T+/6+M+f9aVXP1AAEA0gAAAHcAAAAjAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Cv///zX///91/vDktf/Loff/r2///6Ve//+kW///1rX//////////////////////////////////////////////////////////////v3///fx///s3P//28D//8id//+ubv//o1r//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//qGL//7yF/+O/oeVkYXCisaHq8a+G//+hav7/nWD+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/wJf///n1////////////////////////8+z//7KB/v+ZWv7/m1z+/5pa/v/CnP7//fz///////////////////37///Bmv//mlv+/6h2//+cidL8ISEp6gAAAK0AAABJAAAADwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///xH///9G////hP7n1Mr/wpH9/6to//+jWv//t33//+zd//////////////////////////////////////////////////////////////////////////////38///l0P//r3D//6NZ//+kW///pFv//6Rb//+kW///pFz//6Zf//+raP//tnv//8uh+/bcxLPMyOyauJz++6Jr/v+bXf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aW/7/oWX+/93I/////////////////////////////9rD//+fYv7/mlr+/51g/v/cx/7///////////////////////Xv//+wfv7/mlr+/59l/v+wi/3/Zl+D9gIDAtUAAAB9AAAAJgAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wL///8b////V/77+ZT/3MHf/7qD//+oY///o1r//7F0///PqP//48z///Hn///69v/////////////////////////////////////////////////////////////+/v//zqf//6NZ//+kW///pFv//6Rb//+lXv//qmb//7N3///Ckv380rHa+OPSlfr383Ts7P6gwa3+8qVz/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mln+/7WF/v/z7P////////////////////////j0//+7j/7/mFj+/6p1/v/y6v///////////////////////+LQ//+gZP7/mlv+/5xe/v+nc///oYvb/SUlLuwAAACzAAAATwAAABEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8G////Kf///2n+9u+m/9Ov7v+0d///pl///6Na//+jWf//p2H//69v//+9iP//zqb//+DH///v4v//+fT///79////////////////////////////////////////1bP//6Ra//+kW///pV3//6lk//+ydP//wI3+/dCs5PrgzKX38exl+/z9SP///1b+//9/29P+xrOP/v2gZ/7/m13+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1v+/51e/v/Psf///fz////////////////////////l1P//o2j+/8Ga/v/9+////////////////////v3//8ai/v+aW/7/m1z+/5tc/v+eY/7/r4j+/25mj/cEBATZAAAAhAAAACoAAAAGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////C////zn///94/u7iuv/Jnvj/rm7//6Vd//+kW///pFv//6NZ//+iWP//olf//6Vd//+ubP//u4X//82k///ew///7d7///fx///+/f/////////////48///wY///6Ra//+oYv//sHD//72J//3Op+r63sex9+7ncfr7/Ez+//84////JP///yX///9X9vb+k8m4/uSpe/7/nWH+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pa/v+pc/7/693////////////////////////8+///x6T+/93H////////////////////////8un//614/v+aWv7/m1z+/5tc/v+cXv7/pXH//6aO4v0uLTntAAAAuQAAAFYAAAAUAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///xP///9K//79iP7kz9D/wI3//6tn//+kXP//pFv//6Rb//+kW///pFv//6Rb//+jWf//olf//6NY//+mXv//rm3//7qC///KoP//277//9/G///Ckf//qmX//65s//+7g//+y6Lx+tvCuffs43j5+vpS/f7/PP///yb///8R////Bf///wf///8s////bOfk/rG7n/74o23+/5xe/v+bXP7/m1z+/5tc/v+bW/7/mVr+/5lZ/v+ZWf7/mlr+/5pb/v+aWv7/w53///r3////////////////////////9e////j1////////////////////////28X//51f/v+bXP7/m1z+/5tc/v+bXP7/nmP+/66F/v92bZn4BgcH3QAAAIwAAAAwAAAABwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wP///8e////XP7795j/2r3i/7mA//+oYv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1r//6NZ//+jWf//pl7//6hi//+raP//uH///sid9vzYvMj36NyB+Pj3U/3+/z////8q////Ff///wb///8B////AP///wD///8P////RP3+/4PWzP7Qr4n+/59l/v+bXP7/m1z+/5pb/v+gZf7/uo/+/8im/v/Bmf7/sH7+/6Nq/v+cXf7/oWT+/9zH/////v/////////////////////////////////////////////8+v//v5f+/5lZ/v+bXP7/m1z+/5tc/v+bXP7/nF3+/6Ru//+pj+j+OThH7wAAAL0AAABXAAAAEQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8H////Lf///2z+9e2q/9Cr8f+ydf//pl///6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rc//+mX///q2j//7Z8//7GmPn81rfR+ObXj/j29Fr8/v9B////Lf///xf///8I////Af///wD///8A////AP///wD///8D////Hv///1zz8/6bxbH+66d3/v+dYP7/m1v+/59i/v/Rtf//+vf////////9/P//9e///+jZ///Wu///wJj+/8ai///38v/////////////////////////////////////////////u5P//qHL+/5pa/v+bXP7/m1z+/5tc/v+bXP7/m1z+/55h/v+tgv//gneq+QwND9gAAAB5AAAAGwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////DP///zz///98/uzdv//Hmfv/rWz//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV7//6pm//+0eP//w5P9/NOy2fjk05b49PFh/P3+Rv///zH///8a////Cv///wL///8A////AP///wD///8A////AP///wD///8A////CP///zL///9z497+ubiZ/vqia/7/mlv+/697/v/17v///////////////////////////////////Pr///bw///9+//////////////////////////////////////////////Yv///nV/+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+jbP//rpTv/khHWd8AAACAAAAAHQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///xX///9O//79i//iy9T/vor//6pl//+kXP//pFv//6Rb//+kW///pFv//6Vd//+pZP//snX//8GP/v3RruH54c2j9/LtZPv9/kf///81////H////wz///8D////AP///wD///8A////AAAAAAAAAAAAAAAAAP///wD///8A////Af///xL///9K+/z/iNLG/tethP7/nWD+/7B+/v/28P////////////////////////////////////////////////////////////////////////////////////////r3//+6j/7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+gZv7/tpb//4iGqc8BAgFgAAAAFQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wT///8h////YP769pv/2Lnm/7d9//+nYf//pFv//6Rb//+lXf//qGP//7Bx//++iv/9zqno+d/Jrffv6W/6+/xM/v//N////yH///8O////BP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wT///8i////YfDv/qHCrP7wpXP+/6Fm/v/WvP///Pr//////////////////////////////////////////////////////////////////////////////////+rd//+ka/7/mlv+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nF/+/6Bn/v+qfP7/vqn99JCQsX4AAAAmAAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8I////L////3D+8+mv/86n9P+xc///p2D//6hi//+vb///vIb//syk7/vcw7n37OR0+fr7UP7//zv///8l////EP///wT///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8J////N////3fg2v6/tZT+/KBn/v+gZf7/u5D+/9W7///o2f//9O7///z7/////////////////////////////////////////////////////////////8+x//+aW/7/m1z+/5tc/v+bXP7/m13+/5xf/v+gaP7/qHf+/7OQ/v7Cr/3kz8v2jLq8xSJsbGgHBwcHAUJCQgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Dv///0H///+A/+rax//Kn/3/uYD//7yG//7KoPP72r/C9+rff/n5+VL9/v8+////Kf///xT///8G////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////Ff///0/6+v6MzsD+3qyA/v+dYf7/mVj+/5pa/v+hZf7/rnv//8CY///Uuf//5db///Ts///8+v//////////////////////////////////9/L//7OE/v+ZWf7/m1z+/5td/v+dX/7/oGj+/6h4/v+0kf7+wq7949TM+qzp6fhs+fr4PP///hz///8H////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Av///xj///9S//37kv/r2tP/3MDt/t7F0vvr3on59/ZZ/P7/Qf///yz///8W////B////wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////BP///yb///9m7Ov+qL+m/vOlcf7/nF7+/5tc/v+aW/7/mVn+/5lZ/v+cXf7/omf+/615/v+9lP7/0LP//+PS///y6f//+/j///38///59v//0LP//55h/v+bXP7/nF/+/6Bo/v+oeP7/s5H+/cKu/ePUzfqo7Oz5cPz9+1L///48////I////w3///8C+vr6AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wX///8i////Wf///4b/+/mR//37b/7//0j///8w////Gv///wn///8C////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wv///88////e9vT/sezj/7+oGf+/5td/v+bXP7/m1z+/5tc/v+bXP7/mlv+/5pZ/v+ZWP7/mVn+/55i/v+qdP7/uo3+/8Kc//+2iP7/n2L+/5xf/v+gZ/7/qHj+/7OR/v7Cr/zi1M36qevr+W/9/vtP///+Pv///yj///8T////Bv///wH///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8H////Hv///zz///9H////N////x7///8L////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wL///8Y////Vff3/pPKuf7kqnz+/51h/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pb/v+aWf7/mVj+/5lZ/v+aXP7/oGf+/6h5/v+0kf7+wq795NTN+qnr7Phw/P37Uf///j3///8n////E////wb///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///wf///8K////B////wP///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8F////K////2zo5f6wvKD+96Nu/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/nWD+/6Bo/v+oef7/tJP+/cOw/eHVzvup7Ov5cP3++0////49////J////xP///8G////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Cv///zf///948vP/ruPi/8fj4f6x8PH9eP7//FL///4/////Kv///xT///8G////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA///+AAAf///////////8AAAP///////////wAAAP///////////gAAAH//////////+AAAAH//////////8AAAAD//////////4AAAAB//////////gAAAAB//////////AAAAAB/////gP//8AAAAAA/////AH//4AAAAAA////8AD//gAAAAAAf///wAD//AAAAAAAP///AAB/+AAAAAAAP//+AAB/8AAAAAAAH//4AAA/4AAAAAAAH//gAAA/4AAAAAAAD/+AAAAf4AAAAAAAB/4AAAAf4AAAAAAAB/wAAAAP4AAAAAAAB/AAAAAP4AAAAAAAA+AAAAAH4AAAAAAAA4AAAAAH4AAAAAAAAQAAAAAH4AAAAAAAAAAAAAAD4AAAAAAAAAAAAAAD4AAAAAAAAAAAAAAB8AAAAAAAAAAAAAAB+AAAAAAAAAAAAAAA+AAAAAAAAAAAAAAA/AAAAAAAAAAAAAAA/AAAAAAAAAAAAAAA/gAAAAAAAAAAAAAA/wAAAAAAAAAAAAAA/4AAAAAAAAAAAAAA/4AAAAAAAAAAAAAA/8AAAAAAAAAAAAAA/8AAAAAAAAAAAAAA/+AAAAAAAAAAAAAA//AAAAAAAAAAAAAA//AAAAAAAAAAAAAA//gAAAAAAAAAAAAA//gAAAAAYAAAAAAA//wAAAAB4AAAAAAA//4AAAAD8AAAAAAA//4AAAAP+AAAAAAA//8AAAA/+AAAAAAA//8AAAB/+AAAAAAA//wAAAH//AAAAAAA//gAAAf//gAAAAAA/+AAAA///gAAAAAA/8AAAD///wAAAAAA/wAAAB///wAAAAAD/AAAAA///4AAAAAP+AAAAAf//4AAAAA/4AAAAAf//8AAAAD/gAAAAAP//+AAAAP/AAAAAAP//+AAAAf/AAAAAAH//4AAAB//AAAAAAD//wAAAH//AAAAAAD//AAAAf//AAAAAAB/8AAAB///AAAAAAB/wAAAD///AAAAAAA/AAAAD///AAAAAAAcAAAAB///AAAAAAAYAAAAB///AAAAAAAAAAAAA///AAAAAAAAAAAAAf//AAAAAAAAAAAAAf//AAAAAAAAAAAAAP//AAAAAAAAAAAAAP//AAAAAAAAAAAAAP//AAAAAAAAAAAAAH//AAAAAAAAAAAAAD//AAAAAAAAAAAAAD//AAAAAAAAAAAAAB//gAAAAAAAAAAAAB//wAAAAAAAAAAAAA//4AAAAAAAAAAAAA//4AAAAAAAAAAAAA//8AAAAAAAAAAAAA//+AAAAAAAAAAAAA///AAAAAAAAAAAAA///AAAAAcAAAAAAA///gAAAA8AAAAAAA///wAAAD+AAAAAAA///4AAAP/AAAAAAB///8AAA//gAAAAAB///8AAD//gAAAAAB///+AAH//wAAAAAD////AAf//wAAAAAP////AB///4AAAAA//////////8AAAAD//////////8AAAAP//////////+AAAAf//////////+AAAD////////////AAAP////KAAAAIAAAAAAAQAAAQAgAAAAAAAAAAEAEwsAABMLAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABQAAABEAAAApAAAATgAAAH4AAACtBwgJ0BUWGeQRERTpAwMD4wAAANAAAACiAAAAYgAAACsAAAANAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAkAAAAZAAAANgAAAF8AAACNAAAAtyAgJ9lcW3Dvd3WT9nNyjvZHSFfyDw8R6gAAAM8AAACRAAAASwAAABoAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAACAAAABwAAABIAAAApAAAASwAAAHYAAAChAAAAwyMgHt18bmLxwKmW+qSRgvhOR0HyEhEQ4gAAAKsAAABeAAAAIQAAAAYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAHAAAAHAAAAEIAAAB1AAAApAkJCsg/P03iiYGw9LSb9P6vhv//pHD+/59k/v+cX/7/m13+/5tc/v+bXP7/m1z+/5tc/v+aWv7/n2T+/9rD/////////////////////////////////////////fz///j0///u4///38r//82u//+5jf7/q3X//51g/v+ZWf7/l1b+/5hX/v+aWf7/m1v+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nWH+/6d2//+wl/H+VVJq9AICAuEAAACrAAAAWgAAACAAAAAHAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABQAAAA0AAAAfAAAAPQAAAGYAAACSAAAAuBMRENRcUkrpuZyG9/fHof7+xZj//cui/9e6o/w7NjHuAAAAzQAAAIQAAAA3AAAADgAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQAAABkAAABEAAAAfgICArIeHyTVaGWC7aWW2vuzkv3/qXn+/6Fp/v+dYf7/m13+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5lZ/v+wf///8ej////////////////////////////////////////////////////////+/v///Pr///Pr///m1///177//8Of/v+yg///o2n+/55f/v+YV/7/mFf+/5lZ/v+aW/7/m1z+/5tc/v+cXv7/oGj+/6+H/v+YjMb7Hx8l7QAAAM4AAACGAAAAPAAAABEAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAwAAAAoAAAAZAAAAMwAAAFgAAACEAAAArQoJCcw8NjHioIp39Oq9mv3/wI///7V6//+wcf//tnv/+sWb/4h3afYICAfhAAAAqQAAAFYAAAAbAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAALAAAAMQAAAHALCw2vPT1L24yDs/SxmfL+r4b//6Vx/v+fZP7/nF7+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlr+/8GZ/v/7+P/////////////////////////////////////////////////////////////////////////////+/f//9/L//+7k///fy///za3//7mO//+pc/7/oWb+/5la/v+YWP7/mVn+/5pb/v+dYf7/pnP//7GW9f5kYH72BQYG4wAAALAAAABhAAAAIwAAAAgAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAcAAAASAAAAKQAAAEsAAAB1AAAAnwAAAMEjIB7bfm5h7taxk/v8w5X//7h+//+ubf//qGP//6Zf//+qZv//u4T/zaqO+y8qJ+wAAADHAAAAegAAADAAAAALAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAABEAAABEISEnkm1rh9mrm+H6tJL+/6l5//+haf7/nWH+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tb/v+aW/7/zKz///38///////////////////////////////////////////////////////////////////////////////////////////////////8+v//9O3//+XV///Uuf//wZj+/7B9/v+iZ/7/mVn+/5tc/v+gZv7/r4T//6CR0/woKDHuAAAA0QAAAIwAAABAAAAAEwAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAQAAAANAAAAIAAAAD8AAABoAAAAlAAAALkQDw7UWE5G6MCiifj5xZv//72G//+xcf//qWX//6Ze//+kXP//pFv//6Zf//+xcf/2wZb+c2RY9AQEBN0AAACgAAAATAAAABcAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wH///8CAAAADiMkKkqQjrK/uKX0+6+I/v+kcP7/n2T+/5xf/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlv+/51g/v/bxP////////////////////////////////////////////////////////////////////////////////////////////////////////////////////7///z6///28f//6tz//9a9//+1hv//mVn+/5xf/v+lcf7/tJb6/2llhvYGBgflAAAAtgAAAGYAAAAmAAAACQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAMAAAAJAAAAFwAAADIAAABZAAAAhAAAAK0HBwbMOjQv4p2HdvPqvpv9/8CO//+0eP//q2j//6dg//+lXP//pFv//6Rb//+kW///pVz//6pm//+9h/+9noX6HhsZ6gAAAMAAAABvAAAAKQAAAAkAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////Av///wmVlY4MlZazVryw8+WxjP//omz+/51g/v+bXf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/pm7+/+nb/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////fz//+rc//+rdv7/l1f+/59l/v+tgf//o5LX/DAwOu8AAADVAAAAkwAAAEQAAAAVAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAHAAAAEgAAACgAAABKAAAAdQAAAKACAgLDJiMg3IJxZO/WsZP7+8OV//+5f///rmz//6hi//+lXf//pFv//6Rb//+kW///pFv//6Rb//+kW///p2D//7N2/+y8lf5eU0ryAQEB2AAAAJUAAABEAAAAEwAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8D////FPX28SLOzfR7v6r9+al5/v+dYf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5hX/v+vfP7/8Of//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v3//9O3//+bXP7/m13+/6Rv//+yk/r/dG+T9wkKC+cAAAC7AAAAawAAACoAAAALAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAFAAAADgAAACAAAAA/AAAAZwAAAJIAAAC3FBMS01xRSei/oYj39MGY/v+9hv//sXL//6ll//+mX///pFz//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXf//rGn//r+M/6mPe/kXFRPnAAAAtwAAAGQAAAAkAAAABwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wT///8d/v/8PN3d+47ArP76qHn+/51h/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mFf+/7uQ/v/49P//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////8Ob//6p2/v+YWf7/n2T+/6t///+nld/9NzdE8AAAANkAAACYAAAASgAAABgAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAACQAAABkAAAA0AAAAWgAAAIYAAACtAQICyzo0L+KjjHn07sGc/f/Bjv//tHf//6to//+nYP//pVz//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+oYf//tXr/5bmW/UpCPPAAAADSAAAAigAAADwAAAAQAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////BP///x7///5L7e79icq+/uiviP7/oGj+/5xe/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tb/v+aW/7/yKb+//79///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////u5f//rnz+/5lZ/v+cX/7/o23+/7KQ/P99dqD4Dg4Q6QAAAL8AAABxAAAALgAAAAsAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAABgAAABIAAAApAAAATAAAAHcAAAChAQEBwyQhHtyAcGPv1bCT+v3Dlf//uH7//61s//+oYv//pV3//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Vd//+ubP/7wJD/lYBv9wsLCuMAAACuAAAAWwAAAB4AAAAGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8C////GP///0j9/f5439v+vryi/vundv7/nmL+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlr+/5xe/v/Wu//////////////////////////////////////////////////////////////////////////////9/f///v3//////////////////////////////////////////////////////////////////+TS//+iaP7/mVr+/5td/v+eY/7/qnv//62Y6f1DQlPyAAAA2wAAAJwAAABOAAAAGgAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABAAAAA0AAAAfAAAAPQAAAGcAAACUAAAAuRQTEtVcUknpvqCJ+PXCmf7/vYf//7Fx//+pZf//pV7//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFz//6lj//+5f//XsJD8NzEt7QAAAMsAAACAAAAANAAAAAwAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wH///8N////Nf///2n29v6X0Mb+3rKO/v+ibP7/nF/+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/omj+/+PR/////////////////////////////////////////////////////////////////////////////+/n///aw///6Nr///Xv///7+f////7////////////////////////////////////////8+v//za3//5xe/v+aW/7/m1z+/5xe/v+ia/7/s47//4d+rfkUFBjqAAAAwwAAAHcAAAAxAAAADQAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAwAAAAoAAAAZAAAAMwAAAFgAAACDAAAArQgHB8xAOjTioYp49Om9mf3+v47//7R4//+saP//p2D//6Vc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pl7//69v//nBlP9+bWD1BwcG3wAAAKUAAABSAAAAGQAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wX///8d////T////33q6f6ww7D+8qp+/v+fZf7/m13+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5lZ/v+seP7/7uP/////////////////////////////////////////////////////////////////////////////7eH//7aH/v+pc/7/vpT+/8+x/v/k0///8ej///v4/////v///////////////////fz//+PR//+tev7/mlv+/5tc/v+bXP7/m13+/55i/v+pef//r5js/klIW/MAAADdAAAAowAAAFMAAAAcAAAABwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAcAAAASAAAAKQAAAEwAAAB2AAAAoAAAAMIiHx3bg3Jk79eylPv+xJX//7h+//+ubP//qGL//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXP//qmX//7yE/8imi/smIiDrAAAAxAAAAHUAAAAsAAAACgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///wv///8u////Y/39/orb1f7MuJr+/aVz/v+dYf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mFj+/7WH/v/07f/////////////////////////////////////////////////////////////////////////////9/P//177+/6Fl/v+XVf7/nmD+/6Zv/v+1h/7/yKX+/93I/v/p2/7/8ej//+3i///Xvv//sH7+/5xe/v+bXP7/m1z+/5tc/v+bXP7/nF7+/6Fq/v+xjP7/jIK0+hQUGOsAAADJAAAAfgAAADUAAAAPAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAQAAAAOAAAAIQAAAEAAAABoAAAAlAAAALkQDw7TWU5G6MOkjPj5xJr+/72G//+wcf//qWX//6Zf//+lXP//pFz//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+mX///snP/8b6V/mhbUfMDAwPbAAAAmgAAAEgAAAAVAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////A////xX///9B////c/P0/p/Mv/7nsIn+/6Fq/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/wpz+//r3///////////////////////////////////////////////////////////////////////////////////28f//vpT+/5lY/v+ZWf7/mVn+/5dW/v+cXP7/oWf+/6x3/v+0hP7/sYD+/6Jo/v+aW/7/m1v+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nmH+/6h2//+vl+7+UU9l9AECAeEAAACqAAAAWQAAAB8AAAAHAAAAAQAAAAAAAAAAAAAAAAAAAAMAAAAJAAAAGAAAADMAAABaAAAAhgAAAK4FBQXNQDk0456Id/TpvZr9/8GO//+0d///q2j//6Zf//+iWP//oVX//6FU//+gVf//olj//6Ra//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Vc//+rZ///von/tJeB+hoXFukAAAC8AAAAagAAACYAAAAIAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////B////yP///9V/v//gubk/rfAqv72qnz+/59k/v+bXf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlv+/51f/v/Psv///v3///////////////////////////////////79///69////v3////////////////////////////////////////j0P//p27+/5pa/v+bXP7/m1v+/5pa/v+ZWf7/mFj+/5lY/v+ZWf7/mVr+/5pb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+cXv7/oWj+/7CJ//+VicL7ICEn7QAAAM0AAACDAAAAOQAAABEAAAACAAAAAAAAAAIAAAAGAAAAEgAAACgAAABLAAAAdwAAAKIDAwLEKCQh3H9vYu/WsZP7/MOV//+4fv//rmz//6hi//+kW///o1n//61s//+1ev//tnz//69u//+oYv//olf//6FV//+iV///o1j//6Na//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6dg//+0eP/pu5X+U0pC8QAAANUAAACQAAAAPwAAABEAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8C////Dv///zP///9n+/z+j9jR/tG2l/79pHD+/51g/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/oWT+/93G////////////////////////////////////////9Oz//9e+///z6v////////////////////////////////////////r2///Ipf7/nF7+/5pb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+dYf7/pnT//7OY9/9gXXn1BAUF4wAAAK0AAABdAAAAIgAAAAgAAAAFAAAADQAAAB8AAAA+AAAAZwAAAJMAAAC5ExIR1V9UTOnBo4r49cKY/v+9hv//sXL//6ll//+mXv//pFv//6Ve///Ckv//5ND//+/i///v4///6tj//9m5///InP//t33//6xq//+kWv//olf//6FW//+iWP//o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//61q//3Ajv+giHX4EA8O5QAAALIAAABfAAAAIAAAAAYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8E////F////0b///938fH+pMm6/uquhv7/oWn+/5xe/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pa/v+ocf7/6dr////////////////////////////////////////m1v//rXn+/9a9///8+////////////////////////////////////////+zg//+wfv7/mVn+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5xd/v+gZ/7/r4X//56Qz/smJi7uAAAAzwAAAIcAAAA9AAAAGQAAABsAAAAzAAAAWQAAAIUAAACtBQUFzEI7NeOhiXbz676Z/f/Bjv//tHf//6to//+nYP//pVz//6Rb//+kXP//wZD///Hn/////////////////////////fv///n1///x5f//4cn//9Gs///Ajv//snT//6hh//+kXP//olf//6NY//+jWv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///qGL//7d8/+C2lf1COzXvAAAAzgAAAIQAAAA3AAAADQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8I////Jv///1r+//+E4+D+vr2l/vqoeP7/nmP+/5td/v+bXP7/m1z+/5tc/v+bXP7/mVr+/7GB/v/x6P///////////////////////////////////////9zG//+fY/7/tYj+/+/l/////////////////////////////////////////fz//9O2/v+fYv7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/51g/v+lcv7/s5b4/2ZigPYDAwPjAAAAsAAAAGUAAAA9AAAATAAAAHUAAACgAAAAwyAdG9uAcGLv27WX+//Flv//uH7//65s//+oYv//pV3//6Rb//+kW///o1j//69v///o1f///////////////////////////////////////////////v///Pr///Ts///o1v//2Lf//8aY//+1ev//qmb//6Rb//+hVf//olf//6NZ//+kWv//pFv//6Rb//+kW///pFv//6Rb//+mXf//rm3/+8GT/4x4afYIBwfgAAAAqAAAAFUAAAAaAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wL///8P////N////2v5+v6T08r+2bSR/v+jbv7/nGD+/5tc/v+bXP7/m1z+/5tc/v+ZWf7/upD///bx///////////////////////////////////+/f//0LL//5tc/v+fY/7/0LP+//v5////////////////////////////////////////8ej//7aH/v+aWf7/m1v+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m13+/59m/v+ug///n5DS/CkpMu0AAADPAAAAlAAAAHcAAACQAAAAthMRENRdUknpwKKJ+PjEmv7/vYb//7Bw//+pZP//pl7//6Rc//+kW///pFv//6Rb//+jWP//wY////n1///////////////////////////////////////////////////////////////////9+///9u7//+7h///ew///zKT//7uF//+vb///pVz//6JW//+hVv//olf//6Ra//+kW///pFv//6Rc//+pZP//uoL/zqqN+y0oJewAAADHAAAAeQAAAC8AAAALAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wT///8b////S////3rt7f6rxrT+8KyC/v+gZ/7/nF3+/5tc/v+bXP7/m1v+/5td/v/Hpf///Pr///////////////////////////////////n2///Cmv//mln+/5lZ/v+vfP7/6Nr////////////////////////////////////////+/f//2sP//6Jn/v+aWv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nWD+/6Vx//+zlfn/b2uL9QgJCt0AAAC4AAAAqQcHBsJAOjXgoYp49Ou/m/3/wI7//7R3//+raP//pmD//6Vc//+kW///pFv//6Rb//+kW///pFv//6NY///Jnv///Pn///////////////////////////////////////////////////////////////////////////////////39///59f//8+r//+TQ///Vs///wpD//7N3//+mX///olf//6JY//+jWv//pFv//6Zf//+xcf/2wZb+b2BV9AICAtwAAACeAAAASwAAABYAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///wr///8q////Xv3+/onf2v7Gu6D++qd2/v+eYv7/m13+/5tc/v+aW/7/nmH+/9S8///+/f//////////////////////////////////9Oz//7OE//+aWv7/mlr+/51e/v/Env//9vD////////////////////////////////////////28f//wJj+/5pb/v+aW/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/n2X+/6+F//+om9v7MjM94gICAsQuKifJiHdp59axk/r8w5X//7h+//+ubP//qGL//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//8OT///48/////////////////////////////////////////////////////////////////////////////////////////////////////7///38///27///69z//93C///Aj///pl///6NY//+kW///pVz//6pm//+9iP+8noX6GxkX6QAAAMAAAABuAAAAKAAAAAgAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///xL///88////cPb3/pnQxv7fso7+/6Js/v+cX/7/m1z+/5pb/v+hZv7/4tH////////////////////////////////////////q3v//qHL+/5pa/v+bXP7/mlr+/6Vs/v/cxv///f3////////////////////////////////////////m1v7/qnT+/5lY/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+dYf7/qnv//7Sf8ftcW3PQMzArtMWrlun4x6D9/7yH//+wcf//qWX//6Ze//+kXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWP//sHH//+fU//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////Hn///Npf//p2D//6NZ//+kW///p2D//7N2/+29lv5cUknyAAAA2AAAAJMAAABBAAAAEgAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Bv///x7///9Q////fuvq/q7DsP7zq3/+/59l/v+bXf7/mlv+/6Zu/v/q3f///////////////////////////////////////97I//+hZv7/mlr+/5tc/v+bW/7/mln+/7eK/v/w5v////////////////////////////////////////z6///Mq/7/nF7+/5pa/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m13+/55k/v+rf///tqHz8XNwj5Cum4ek/Myj+v+5gf//q2j//6dg//+lXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Ra//+kWv//wpL//+7h///+/f////7///////////////////////////////////////////////////////////////////////////////////////////////////////////////////Lo//+6g///olf//6Rb//+lXf//rGn//r+M/6ySffkUEhHmAAAAtgAAAGIAAAAhAAAABwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////C////y7///9j/Pz+jNvV/su4m/79pXP+/51h/v+aWv7/o2r+/+jZ///////////////////////////////////+/f//0LH//51f/v+aW/7/m1z+/5tc/v+aWv7/oGT+/9K1///6+P///////////////////////////////////////+3h//+wfv7/mln+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5xe/v+fZP7/pXL+/7WU/v/AtfXUvr3Mb/XXvsX/xpf//69v//+mXv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+mX///vIb//9m6///o1v//9e7///z6/////v//////////////////////////////////////////////////////////////////////////////////////////////////+vX//8ea//+jWP//pFv//6Rb//+nYf//tnv/47iW/UhAOfAAAADQAAAAhwAAADkAAAAPAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8C////FP///0H///9z9PX+nc3A/uSwif7/oWr+/5td/v+eYv7/2cH////+//////////////////////////////jz//++lf7/mlv+/5tc/v+bXP7/m1z+/5tc/v+aWv7/r33+/+jZ/////////////////////////////////////////fz//9O3//+fYv7/mlv+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5te/v+dYv7/omr+/6l6/v+1lP7/xLf85tHR74/w8PB3/ejUxf/Kn/3/sXL//6Zf//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6NY//+jWf//p2D//7Jz///Bj///0q7//+LK///w5P//+fP///79///////////////////////////////////////////////////////////////////////////////////69v//xpn//6JY//+kW///pFv//6Vd//+ubP/8wZH/k35u9wgIB+MAAACsAAAAWQAAAB0AAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8H////Iv///1X///+A5eP+uL+o/vepe/7/n2T+/5lZ/v+9k/7/8Of/////////////////////////////5NP//6lz/v+aW/7/m1z+/5tc/v+bXP7/m1z+/5tb/v+dX/7/xaH///jz////////////////////////////////////////8OX//7OC/v+aWv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+dYP7/oGf+/6Zz/v+viP7/vKP++Mi++svV1fJ77/DyV/39/Xj99u+g/te27P+5gf//qWX//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Ra//+jWf//olj//6Na//+lXf//rmz//7h////Jm///2Lf//+nX///7+P////////////////////////////////////////////////////////////////////////Xt//+8hv//oVb//6Rb//+kW///pFz//6lk//+5gP/Vr5D8MCsn7QAAAMoAAAB/AAAAMwAAAAwAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8N////Mv///2f6+/6Q1s7+1baW/v6kcP7/m17+/55h/v+/l/7/7OD///r3///+/f//+vj//+fZ//+5jf7/nF7+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pZ/v+mbf7/38v///7+///////////////////////////////////69///x6T+/5td/v+bW/7/m1z+/5tc/v+bXP7/m1z+/5td/v+cXv7/n2T+/6Rv/v+sgf7/t5r+/cW2+97U0Pae5ufyYvb39UH9/f1G////Zv7+/oT+6NfD/8ea/f+wcf//pl///6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1r//6NZ//+iV///oFT//6JX//+wcf//1bL///jz////////////////////////////////////////////////////////////////////////5tL//65t//+jWP//pFv//6Rb//+kW///pl7//7Bw//jBlP99bF/1AwMD3wAAAKUAAABRAAAAGQAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wT///8Y////Rv///3jw8P6lybn+666F/v+haP7/mlv+/5xd/v+vff7/yKT+/9K1/v/Jp/7/rXr+/5xd/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1v+/5pa/v+7kP7/8ur///////////////////////////////////z6///Kqf7/mlv+/5tb/v+bXP7/m1z+/5tc/v+cXv7/nmL+/6Jr/v+pev7/tJL+/8Cs/O3Ox/i34eHzdfT09VD8/PtB/v7+MP///yr///9E////bv738pn+2Lnn/7uE//+qZv//pVz//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//6NZ//+qZv//wpD//+DI///17f///v3///////////////////////////////////////////////////////////////////z6///Pqf//pFv//6Ra//+kW///pFv//6Rb//+kXP//qmX//7yF/8alivslIiDrAAAAxQAAAHYAAAAsAAAACwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///wj///8m////Wv7//4Xj4f69vaX++ah4/v+eZP7/m1v+/5hW/v+aWv7/nF7+/5tb/v+ZWP7/mlv+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mVn+/6Fl/v/Tt///+/j/////////////////////////////+PP//8GZ//+aWv7/m1z+/5tc/v+bXf7/nWD+/6Bn/v+mdP7/sIn+/7yk/fbKwPnK2tr0iu7v9Fr7+/pG/v79Of///yj///8V////Dv///yL///9T/v7+fv7q277/yZ/7/7Fz//+nYP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1r//6JY//+oYf//vYf//9u+///07P////7/////////////////////////////////////////////////////////////////////////////8uj//7mB//+iWP//pFv//6Rb//+kW///pFv//6Rb//+mX///snP/88CW/mldUvMBAQHbAAAAnAAAAEgAAAAXAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///xD///84////bPn6/pTUyv7YtJH+/6Nu/v+dYP7/m1z+/5pb/v+aWv7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlr+/698/v/n2P///v7////////////////////////n1///rHf+/5pa/v+bXP7/nF7+/59k/v+kb/7/rYL+/7ib/vzFtvve1ND2nujp8mT4+PdL/f38P////y7///8b////Df///wT///8C////Dv///zb///9q/vj0lv7bv+L/vYj//6tn//+lXf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFr//6NZ//+mX///tXn//9Sv///x5P///fv////////////////////////////////////////////////////////////////////////////////////////gyP//qmX//6Na//+kW///pFv//6Rb//+kW///pFv//6Vc//+rZ///vor/tZiB+RoYFukAAAC9AAAAawAAACkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////BP///xv///9L////eu3t/qrFtP7wrYL+/6Bn/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bW/7/m13+/7qP///l1f//+PP///v5///8+v//6dv//7mN//+cXv7/m13+/51i/v+iav7/qXr+/7SS/v/Brv3tz8n4tOHi9HT19vVP/f37Qv7+/jT///8h////EP///wb///8B////AP///wD///8F////Hf///0////97/u7htf/Npfj/s3b//6dh//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+kWv//sHD//8yi///q2P///Pj//////////////////////////////////////////////////////////////////////////////////////////////Pn//8uf//+iWP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6dg//+0d//svJf+VUtD8QAAANcAAACQAAAARAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8B////Cv///yr///9e/v7+h9/b/sW7oP76p3X+/55i/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aW/7/m1z+/6p2/v/Al///zKv//8qn//+pcv7/mVj+/5xf/v+gZ/7/pnT+/7CJ/v+8o/74yb/6zNvZ9ILv8PNY+/v6R/7+/jn///8n////Ff///wn///8D////Af///wD///8A////AP///wH///8M////Mv///2b++/mN/t/F2v+/jP//rGn//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Ra//+kWv//rGj//8KQ///iyv//+fP////////////////////////////////////////////////////////////////////////////////////////////////////////v4///tnz//6NY//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//6xq///Ajv+mjXn4EhAP5gAAALMAAABmAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8C////Ev///zz///9v9/f+mNDE/uCyjv7/omz+/5xf/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aW/7/mFj+/5pa/v+cXf7/mlr+/5pa/v+eY/7/pG/+/6yB/v+4m/7/xbf84dTR9p3p6/Jg+fr3Sf7+/T3///8t////Gv///wz///8E////Af///wD///8A////AP///wD///8A////AP///wP///8Z////Sv///3b98OWt/8+o9v+0eP//qGH//6Rb//+kW///pFv//6Rb//+kW///pFv//6Ra//+jWf//p1///7qC///bvP//9Or///79/////////////////////////////////////////////////////////////////////////////////////////////////////////////9u///+nYf//pFr//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///qGL//7d8/+S5lv1DOzbvAAAAzgAAAIwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8G////Hv///1D///9+6uj+sMKu/vSrfv7/n2X+/5xd/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+dYv7/omv+/6l6/v+0kv7/wK387c/I+LLi4vNx9fb1T/z8+0H+/v4y////IP///xD///8G////Af///wD///8A////AP///wD///8AAAAAAP///wD///8A////AP///wr///8t////YP78+or+4MjW/8CO//+ta///pV3//6Rb//+kW///pFv//6Rb//+jWv//pV3//7N2///Qqf//7t////36///////////////////////////////////////////////////////////////////17f//7+L///38///////////////////////////////////69f//xZf//6JX//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXf//rm3//sOU/415afYIBwfgAAAArQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8L////Lv///2P8/P6M29X+zLia/v6lcv7/nWH+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+dYP7/oGf+/6Z0/v+wif7/vKT++cq/+svb2fOE8PHyVvv7+kb+/v45////Jv///xT///8I////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAA////AP///wD///8A////A////xb///9F////c/7x56v/0Kv0/7Z7//+oYv//pFz//6Rb//+kW///pFr//6df///Fl///6NT///r1///////////////////////////////////////////////////////////////////7+P//48z//8GP///Zu////v3//////////////////////////////////+3e//+yc///olj//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rc//+pY///uoH/0q2P/CwoJOoAAADGAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wP///8U////Qv///3P09P6dzL/+5a+J/v+hav7/nF7+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+cX/7/n2T+/6Rw/v+tgv7/uJv+/MW2+9vV0faa6OnyY/j490r8/Pw9/v7+LP///xr///8M////BP///wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Cf///yr///9e/vz7iP7jzNL/w5L+/65s//+mXv//pFv//6Rb//+jWv//v4z///Lo/////v/////////////////////////////////////////////////////////////8+f//69v//8uh//+ta///r2///+rZ///////////////////////////////////+/f//2br//6Ve//+jWv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Zf//+wcf/2wZb+c2RZ8AMDA88AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wb///8i////Vv///4Dm5P65v6j+96l6/v+fZP7/m13+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+cXv7/nmL+/6Jr/v+pe/7/tJL+/8Gu/OzPyPiy4uLycfX29lH8/PtC/v7+Mv///x////8P////Bf///wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8C////FP///0P///9y/fPrpf/TsPD/t3z//6hj//+kXP//o1r//6hi///cwf///////////////////////////////////////////////////////////////v//8eX//9Kt//+zdv//pV3//6BU///CkP//+vb///////////////////////////////////fw///BkP//o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFz//6tn///AjP/Dp5D0KCUjyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///w3///8z////Z/r7/pHWzv7VtZb+/qRw/v+dYP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/nWD+/6Bo/v+ndv7/sIr+/7yl/fTKwPrJ29r0he/w81f7+/pG/v7+OP///yf///8U////CP///wL///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8I////J////1v+/fyE/uXRy//Elf7/rm7//6Ze//+jWf//snT//+3e///////////////////////////////////////////////////+/v//9ez//9q8//+6gv//pV7//6JY//+jWf//pFz//9i6///+/v//////////////////////////////////6Nb//61r//+jWf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//qmb//72H/+/MsPduZF2yAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////BP///xj///9G////ePHx/qXJuv7srob+/6Fo/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/nF/+/59k/v+kcP7/rYP+/7ic/vvGuPvb1dL1m+nq82P4+fhL/v79Pf///yz///8a////DP///wT///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wL///8S////P////3D+9e+g/9Wz7v+4f///qWT//6NZ//+3ff//8uj/////////////////////////////////////////////+fX//+HJ//+/iv//qWT//6JY//+jWf//pFv//6NZ//+vcf//7uH///////////////////////////////////37///Trv//pFr//6Ra//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//pV3//6hj//+wcv//xpf/4cOszlBJRGgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////CP///yb///9a/v/+hePg/r29pf74qHj+/55j/v+bXf7/m1z+/5tc/v+bXP7/nF7+/55i/v+ibP7/qXz+/7ST/v7Br/zqz8r3r+Lj83D19fZQ/Pz8Qv7+/jL///8g////D////wb///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wb///8k////WP7+/oL+6NXG/8eZ/f+wcf//pV3//6lj///hyf//////////////////////////////////+vf//+jV///Hmv//rGn//6JY//+jWf//pFv//6Rb//+kW///olj//8KT///69v//////////////////////////////////9ez//7yG//+jWP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//pV3//6hi//+ta///tXr//8OT//3XuO7Yw7J1BQcJHQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8C////D////zj///9s+fr+lNPL/tmzkf7/o27+/51g/v+bXf7/nF3+/51g/v+gaP7/p3b+/7GL/v+9pf30ysH5yNvb9IXw8fNW+/v6Rv7+/jj///8m////Ff///wn///8C////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Av///xH///88////bf748pv+2Lno/7qE//+qZv//olb//72I///u4f///fz//////////////fz//+/h///Opv//sHD//6NZ//+iWP//o1r//6Rb//+kW///pFv//6Ra//+nYf//3MH////+///////////////////////////////////kzf//q2f//6Na//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//6dh//+raf//s3f//7+M//7Mpfb62r/L8+PVfufh3DHh4uIQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AAAAAAD///8E////Gv///0v+/v577Oz8rca2/vGvh/7/o27+/59m/v+gaP7/pXH+/62D/v+5nf76xrn72NbT9Znp6/Ni+fn4Sv39/Tz+/v4s////Gf///wv///8D////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Bv///yH///9U/v7/fv7r273/yp/6/7J0//+mX///pFv//7yH///Wtv//5dD//+PM///TsP//tnv//6Rb//+iV///o1r//6Rb//+kW///pFv//6Rb//+kW///olj//7J1///x5f//////////////////////////////////+/j//8uh//+jWf//pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//6Zg//+rZ///snT//72I//7Kofn72LvW9+TVnPTv62P39/hA+/z8J/7+/hQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA1NTUAampqAPn5+QHw8PAK8vLyLPLy8mLu7++Q2Nb1zcKv/fuyj///rIL+/66G//+2l/7/wa/868/J96/j5PJu9vb1Tvz8+0L+/v4y////H////w////8G////Af///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8B////Dv///zb///9p/vn1lP7bwOL/vYj//6to//+jWv//olf//6Ve//+rZ///q2f//6Rb//+iV///o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+iV///wZD///nz///////////////////////////////////y5///tXr//6JY//+kW///pFv//6Rb//+kW///pFz//6Zf//+qZv//sXH//7uE///InPz81rfg+OLQpfXv6W34+fpS/P39Rf7+/zL///8c////DAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAICAgAAAAAAAAAAAi8vLwh2dnYcoqKiQ7OzsnK6u8ChwL/f18C08vK+rPn5wbL39MS97tTNzOOR5ubpWvr6+EX+/v43////Jv///xT///8I////Av///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8E////HP///07+//96/u7htv/NpPj/s3b//6dh//+kW///o1n//6JX//+iWP//o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ///Lof//+/n//////////////////////////////////9/F//+nYv//o1n//6Rb//+kW///pFz//6Ze//+pZP//r2///7mB///Gmf791LPl+eHNr/bt5nX4+PhV/P3+SP7+/jr///8o////Fv///wn///8DAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAUAAAAPAAAAIQAAAD0JCQlaGRkZeCwsLJBOTlKqbGt5w39+k8qJiZm5j4+UjqqqqWfS0tJI8PDwLvz8/Br///8L////BP///wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8L////Mv///2b++/iO/t/F2/+/i///rGn//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///oln//8SU///58//////////////////////////////69v//xpn//6Rb//+kW///pFv//6Ve//+oY///rm3//7d9///ElP/90a7t+t7Iu/br4n339vZY/P39Sv///z3///8r////Gf///wv///8E////Af///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAMAAAAKAAAAGgAAADYAAABdAAAAiQAAAKwHBwbCS0Q+1Id6beBSS0HYNjMxzggIB7AZGRiJQkJCX3JycjednZ0XycnJB////wHCwsIA////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wP///8Z////Sv///3b+8OWt/8+p9f+0eP//qGL//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWv//r27//+TP/////v///////////////////////+XQ//+ubf//o1r//6Vd//+oYv//rWv//7Z7///CkP/+z6vy+tzFwvbp34T29fRc+/z9S/7//z////8u////HP///w3///8E////Af///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAIAAAAHAAAAFAAAACsAAABOAAAAeAAAAKMCAwPFKSUi3YJxZO/cuJv7+cuj/+a+mv23oYv4IR4c5AAAAMIAAACFBgYGRA0NDRkLCwsGBQUFAf///wBnZ2cA////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///wr///8t////Yf78+or+4MnW/8CP//+ta///pV7//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Ra//+jWv//u4b//+TO///17f//+vf///n0///iyv//t33//6Rb//+nYP//rGn//7R3//+/jP/+zab1+9rAz/fm2ZD18/Fi+vv8Tv7+/kL///8x////Hv///w////8G////Af///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAFAAAADwAAACIAAABCAAAAawAAAJYAAAC7FxUU1mdaUevGpo35+cSa//++if//t33//72H//vJov+Dc2X2CAgH5wAAAL8AAAB0AAAAMwAAABAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////A////xb///9G////c/7y6Kr/0azz/7Z7//+oY///pFz//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Na//+iWf//rGv//76K///Lof//wI3//6dg//+kW///q2f//7N1//++if/+y6L5+9i81ffl15b18e9k+fr7UP7+/kP///8z////If///xH///8G////Af///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAADAAAACgAAABoAAAA2AAAAXAAAAIgAAACwCQgIzUE5NOOoj3z078Cb/f/Ajf//s3b//6to//+oY///rGn//7uD/9+3lv1FPjjxAAAA3gAAAKUAAABZAAAAIgAAAAkAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Cf///yr///9e/vz7h/7jzdH/w5P+/65t//+lXv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Na//+iV///olf//6NZ//+jWf//qWX//7Fz//+7hf/+yZ76/Ne43vji0aX17+pt+fn6Uf39/kb///83////JP///xP///8I////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAACAAAABQAAAAsAAAAUAAAAHwAAAClAQECxiklIt2GdGbw37iY/P/ElP//t3z//61r//+nYf//pV3//6Rc//+mXv//rWz//sCP/7CVgPkWFBPsAAAAzwAAAIoAAABCAAAAFgAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8C////FP///0L///9y/vTso//Use//t37//6hk//+kXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rc//+lXv//qWT//7Bw//+6gv//xpr+/dS05fjhz6r17uhw+Pj5VPz9/kj///85////J////xX///8J////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAABQAAAA8AAAAjAAAAQQAAAGsAAACXAAAAvBcVFNZiVkzqxKSL+PjEmf7/vIT//7Bw//+pZP//pV7//6Rc//+kW///pFv//6Rc//+nYv//tHf/88CY/nBiVvQCAgPlAAAAuAAAAG4AAAAuAAAADQAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8H////Jv///1v+/fyE/ubSyv/Flv3/rm7//6Ze//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rc//+lXv//qWT//65u//+4fv//xZX+/dKw6vrfybn26+J79/f3Vvz8/Er+/v49////Kv///xj///8L////A////wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAwAAAAoAAAAaAAAANgAAAF0AAACJAAAAsAoJCc9JQTvlqZB89e/Am/7/wIz//7N2//+rZ///p1///6Rc//+kW///pFv//6Rb//+kW///pFv//6Vd//+rZ///vIX/2LKT/DgyLfAAAADbAAAAnwAAAFMAAAAeAAAACAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wL///8S////Pv///2/+9u+e/ta17P+4gP//qWT//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXf//qGL//61s//+2fP//wpL//tGs8frdxsD26uGC9/b2Wvz9/kv///8+////LP///xv///8M////BP///wH///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAgAAAAgAAAAVAAAAKwAAAE8AAAB6AAAApAMDA8UtKSXdi3hp8N+3l/z/w5T//7d8//+ta///qGH//6Vd//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Zf//+vbv//w5P/oIl2+BEQD+oAAADJAAAAggAAADsAAAATAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wb///8k////V/7+/YD+59bE/8aZ/f+vcP//pl///6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXf//qGH//6xq//+0eP//wI7//s6n8/rbwcr359qN9vTyX/v7/E3+/v5B////MP///x3///8O////Bf///wH///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAUAAAAPAAAAIwAAAEMAAABsAAAAlwAAALsWFBPWZVpQ6samjPn6xZn//7uD//+vcP//qWT//6Ve//+kXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFz//6hi//+2ev/vv5n+XlNK8wABAeMAAACyAAAAZQAAACkAAAAMAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///xD///87////bP338pr+2Lno/7qD//+qZv//pVz//6Rb//+kW///pFv//6Rb//+lXP//p2D//6to//+zdv//vor//syj+fvZvtP35tiV9fLvY/r7/E/+/v5D////Mv///yD///8Q////Bv///wH///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAMAAAALAAAAHAAAADgAAABfAAAAiwAAALEKCgnORj445KqRffXuv5r9/8CL//+zdf//q2f//6Zg//+kXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//6to//++iP/GpYv7JiIf7gAAANYAAACWAAAATAAAABwAAAAGAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Bv///yH///9T/v//fv7q2r7/yZ38/7Fy//+mX///pFv//6Rb//+lXP//p2D//6tn//+yc///vIb//sqf+fzXudr449Oh9e/ravn5+lH9/f5F////Nv///yP///8S////B////wL///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAHAAAAEwAAACwAAABRAAAAfAAAAKYCAwPHKyck3oZ1Z/Ddtpf7/8OU//+3fP//rWv//6dg//+kW///pFr//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///p2D//7Fy//rClv+MeWn3CQkI6QAAAMMAAAB6AAAANwAAABAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////Dv///zf+//9p/Pfyl/7avOb/vIb//6tn//+lXv//pl///6ll//+wcf//uoP//8eb/fzVteP44s+o9e7pcPj4+VT9/f5H////OP///yb///8V////Cf///wL///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAFAAAAEAAAACMAAABDAAAAbQAAAJkAAAC9GhgW12pdU+vGpoz598KY/v+7hP//sHD//6hj//+jWv//o1r//6Vc//+jWf//olf//6NZ//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//qWT//7h+/+i8mP1RR0DyAAAA4AAAAKoAAABeAAAAJQAAAAoAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAc3NzAP///wDu7u4F8PDwH/Ly8lTw8PCE9eTXwv7Npfv/t33//65u//+wcf//uID//8WX/f3TsOj538q19evjeff39lf8/f1J////O////yn///8X////Cv///wP///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAADAAAACgAAABoAAAA3AAAAXgAAAIoAAACyCwoK0EtEPeatlH/278Ca/v/AjP//s3b//6tn//+mX///pFr//7R4///Lov//1rb//8+o//+7hf//p2D//6NZ//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+mXv//rWv//8CN/72fh/oeGxntAAAA0QAAAI4AAABFAAAAFwAAAAUAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAR0dHQZvb28WqqqqP8HBwXHQzcqi89fB6P/Mo///wpL//8aZ//vPrPH12sO/8ujfgfb19Vr7/P1L/v7/Pv///yz///8a////DP///wT///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAABwAAABQAAAAsAAAAUAAAAHwAAACmAQEBxi8qJ9+Nemvx37eX/P7Ckv//tnv//61r//+oYf//pV3//6NZ//+0eP//6NX///v4///+/f///Pr///Pp///Opf//p2D//6Na//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+nYf//snT/+MKY/3xsX/UGBQXmAAAAvQAAAHIAAAAwAAAADwAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAUAAAAOAAAAHgICAjgMDAxSKSkpbFhYWI6poJbB1r+r5O7NsvLjybTdzMC2o8/Ny23r6+xR+/v7Qf///zD///8d////Dv///wX///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwAAAAwAAAAgAAAAQQAAAGwAAACYAAAAvRYUE9dqXVTry6qP+frDmP//u4P//69w//+pZP//pV7//6Rc//+kW///pV7//9a1///+/f////////////////////////Xt///Ajv//o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rd//+qZv//uoL/2rOT/Do1L/AAAADdAAAAowAAAFcAAAAhAAAACQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAQAAAALAAAAGgAAADUAAABZAAAAggAAAKQAAAC2DxASuycnKr49PDzBV1JMvk9NSqBgYGF7lJWVXMbGxj7o6Ogi/f39EP///wb///8B////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAALAAAAFgAAACIAAAAsQgICM9KQjvlsJaC9vDAmv3/v4v//7J0//+qZ///pmD//6Rc//+kW///pFv//6JY//+vbv//7N3//////////////////////////////v7//9zA//+nYf//o1r//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Zf//+ubf/+wZD/qI97+RQSEewAAADNAAAAiAAAAEEAAAAWAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAQAAAAKAAAAGAAAADAAAABSAAAAfAAAAKQAAADEEhIV20xLXuyGgan1kYq89XdymO06OkfdAgIDwQYGBpMbGxtaSEhILW5ubhCZmZkD////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC0AAABfAAAAmQAAAMMlIh/djXpr8eK6mfz+wpL//7d7//+sa///p2H//6Vd//+kW///pFv//6Rb//+kW///oVb//7mB///27v//////////////////////////////////5dH//6tn//+jWv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Ra//+iWP//olj//6FW//+iV///o1n//6hi//+1eP/xwJn+alxS9AABAeUAAAC3AAAAbAAAAC0AAAANAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAMAAAAJAAAAFQAAACsAAABNAAAAdAAAAJwAAAC/CQkK10A/T+qKgrD4sp/u/reZ/f+1lP//t575/56XyvwsLDXsAAAAzQAAAIsAAABBAwMDFgEBAQQAAAAAUFBQAP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASwAAAIoWFBPEaVxS6M+tkvn8xZn//7uC//+vb///qGP//6Ve//+kXP//pFv//6Rb//+kW///pFv//6Rb//+iWP//xpn///z5///////////////////////////////////exf//qGP//6Na//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWf//pl7//7d8///Lof//zaX//7+N//+ubP//pFv//6pn//+9hv/VsJL8NC4q7wAAANoAAACdAAAAUwAAAB0AAAAHAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAIAAAAEwAAACgAAABGAAAAbgAAAJgAAAC6BAQF1DMzQOeAeqT2sZ3s/bWS//+rfv//pXL+/6Rv/v+qfP//uJz8/3dzlvcICArnAAAAuwAAAGwAAAArAAAACwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQDw5aWFBJrLadiOv1xZ/+/8CL//+ydP//qmb//6Zf//+kXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFr//6Ra///Tsf///v3//////////////////////////////v7//9Sy//+mXv//pFr//6Rb//+kW///pFv//6Rb//+jWf//pFv//7Fw///Opv//7d////v4///9/P//9/H//+TP//+2e///o1n//69w///Flf+bhHP4Dw4N6gAAAMgAAACAAAAAOgAAABIAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAGAAAAEAAAACQAAABBAAAAZwAAAJAAAAC0AwMD0CYmL+RxbI/zq5ri/beX//+sf///pG7+/59k/v+cX/7/nF/+/6Bm/v+sgP//qpnj/Tg3RfEAAADZAAAAmAAAAEoAAAAYAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKydkWfu0Lfq/8md//+2e///rGr//6dh//+lXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWv//qWP//+HK///////////////////////////////////7+P//xpn//6NZ//+kW///pFv//6Rb//+kWv//pFr//6xq///Gl///59P///v3/////////////////////////////+HJ//+pZP//p2H//7Z6/+29mP5eU0rzAAAA4gAAALEAAABkAAAAKAAAAAsAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAFAAAADgAAACAAAAA8AAAAYgAAAIsAAACxAQEAzSAgJ+FlYYDxppfa/LeZ/f+ug///pHD+/59l/v+dX/7/m13+/5tc/v+bXP7/nF/+/6Nt/v+zkf7/gnun+QwMDukAAADAAAAAcwAAAC4AAAAMAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA9uLSg//Usvb/uYH//6pm//+lXf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+vbv//69v///////////////////////////////////bv//+6gv//o1n//6Rb//+kWv//o1n//6lj//++iP//3sP///fw////////////////////////////////////////+PL//76J//+kWv//rGn//7+K/8Wli/snIyDuAAAA1QAAAJQAAABKAAAAGgAAAAYAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAEAAAADAAAABsAAAA2AAAAWwAAAIQAAACqAAEAyRgYHd5YVW7um47K+rec+v+vh///pnT+/6Bn/v+dYP7/m13+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nmP+/6p7//+umer+QT9Q8gAAANsAAACfAAAATwAAABkAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD97eCn/9a19/+5gf//qWX//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//7Z8///z6f//////////////////////////////////7Nz//69u//+iWP//o1j//6Ze//+2fP//1rP///Pn///+/v/////////////////////////////////////////////59P//wI7//6Na//+nYP//sXL/+sKW/4p3aPYHBgboAAAAwgAAAHgAAAA2AAAAEQAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAADAAAACgAAABkAAAAxAAAAVAAAAH4AAACmAAAAxRUWGdxPTWLtlIm/+bWd9v6yjP//p3b+/6Bo/v+dYf7/nF3+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+cXv7/omv+/7OO//+KgbL6ERIU6gAAAMUAAAB4AAAAMQAAAA0AAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP77+IX+5dDT/8aY//+wcf//p2D//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+iWP//wI7///n0///////////////////////////////////gxf//p2D//6NY//+wcP//zaT//+va///8+f////////////////////////////////////////////////////////Dj//+0eP//o1n//6Vc//+pZP//uH//5LmX/UlBOvIAAADfAAAAqQAAAF4AAAAlAAAACQAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAADAAAACAAAABUAAAAsAAAATgAAAHYAAACeAAAAwA4OEdhEQ1PqioKy97Gb7v6zj///qXn//6Jq/v+eYv7/nF7+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+eYv7/qHj//6+Y7v5LSV3yAAAA3gAAAKQAAABTAAAAHAAAAAYAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////d/759KD/27/o/76K//+ta///pl7//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6JX///Mov///fr//////////////////////////////fz//8+n//+oYv//xJT//+XP///59P/////////////////////////////////////////////////////////////48///zqf//6dg//+kWv//pFv//6Ve//+ta///wI3/upyF+h0aGO0AAADRAAAAjwAAAEYAAAAYAAAABQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAACAAAABwAAABIAAAAnAAAARwAAAHAAAACaAAAAvAcHCNU4OEbogXql9a+b6v20kv//qnz//6Js/v+eY/7/nF7+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5xe/v+haf7/sYv//5GHvPoXFxzsAAAAyQAAAH4AAAA2AAAADwAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///9f////hf7x5rn/0q71/7h///+qZv//pV3//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kWv//pV3//9i5///////////////////////////////////7+P//17b//9i4///17f///v3////////////////////////////////////////////////////////9+///69v//8id//+qZ///pFr//6Rb//+kW///pFv//6dh//+zdf/5xJn/empd9QQEBOYAAAC8AAAAcgAAADAAAAAOAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAACAAAABwAAABEAAAAjAAAAQQAAAGgAAACRAAAAtgQEBNErKzXkdXCV9KmY4Py1lf3/rID//6Nu/v+eZP7/nF/+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/51h/v+odv//sZjx/lNQaPQAAADgAAAAqQAAAFoAAAAgAAAABwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///zf///9o/v79kf7p2Mz/y6D8/7N3//+oYv//pFz//6Rb//+kW///pFv//6Rb//+kW///pFv//6NZ//+pZP//5ND///////////////////////////////////7+///59P///fr/////////////////////////////////////////////////////////////8uf//9Kt//+yc///pVz//6Na//+kW///pFv//6Rb//+kW///pV3//6pm//+7gv/dtZX9PDYx8AAAAN0AAACjAAAAVgAAACAAAAAIAAAAAQAAAAAAAAABAAAABQAAAA8AAAAhAAAAPQAAAGIAAACLAAAAsQAAAMwiIinibGeI8qeY3Py1l/z/rYP//6Rw/v+dYv7/m1z+/5xd/v+ZWP7/mVn+/5tb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m13+/6Fo/v+wiP//l4vF+x4eJO0AAADNAAAAhQAAADsAAAARAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////F////0H///91/vz5m//iy9z/w5P+/69v//+nYP//pFv//6Rb//+kW///pFv//6Rb//+kW///o1n//7J1///w5f//////////////////////////////////////////////////////////////////////////////////////////////////9/D//9q9//+4fv//pV7//6NZ//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pl///65t//7BkP+njnr4FBMR6wAAAMwAAACFAAAAPgAAABQAAAAFAAAABQAAAA0AAAAdAAAAOQAAAF0AAACFAAAAqwAAAMkWFxveWldw7qCT0fq3nPz/r4b//6Vy/v+gZv7/nF/+/6x4/v/Lqv//0LH//8Oc//+pc/7/nF3+/5tb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nWH+/6Z0/v+zl/f/Yl979QIDAuMAAACwAAAAYAAAACMAAAAIAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8H////H////1D///9//vjzqP/Zu+v/vYf//6xq//+lXv//pFv//6Rb//+kW///pFv//6Rb//+jWP//vIb///fx////////////////////////////////////////////////////////////////////////////////////////+vX//+PL//++iv//pl///6JY//+jWv//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//qGL//7V4//LBmf5sXlT0AgIC5QAAALUAAABpAAAALAAAABQAAAAZAAAAMgAAAFYAAACAAAAApwAAAMYSExbcTkxh7ZeMw/m3nvn/sYr//6d0/v+gZ/7/nWD+/5xe/v/AmP7/8Of///7+///+/v///Pr//+jZ//+1iP7/m1r+/5tb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+cXf7/oGf+/6+E//+fkNH8JiYu7gAAANIAAACMAAAAPwAAABIAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wH///8K////Kv///17///+J/vDku//Qqvj/t33//6pl//+lXf//pFv//6Rb//+kW///pFv//6Ra///Im////Pn//////////////////////////////////////////////////////////////////////////////Pn//+nX///Im///q2f//6JX//+jWf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+lXf//q2j//7yG/9CskPwuKSXvAAAA1wAAAJkAAABVAAAAOAAAAEwAAAB1AAAAoAAAAMIRERTZRURV6oqBsfeynPD+s4///6h4/v+hav7/nWH+/5xd/v+aWv7/qXP+/+ve/////////////////////////////+TT//+ocP7/mln+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlv+/5lZ/v+ZWf7/mFj+/5lZ/v+cYP7/pXH+/7SW+v9rZof2BgYG5QAAALYAAABmAAAAJgAAAAoAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wL///8Q////Nv///2r+/v2S/ufV0P/Jnf3/snX//6di//+kXP//pFv//6Rb//+kW///pFr//9Ku///+/f///////////////////////////////////////////////////////////////////vz//+/j///Rq///sXH//6NZ//+jWP//pFr//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+mX///sHD//cOV/5eCcfcKCQnpAAAAxgAAAIsAAAB0AAAAkAAAALgHCAjVPT1L6YN8qPavm+r9tJL//6p8//+ia/7/nmL+/5xe/v+bXP7/m1z+/5lZ/v+8kv7/+fX//////////////////////////////Pr//8mn/v+cXf7/mlv+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5lZ/v+eYP7/r37+/7iM/v+wfv7/oWf+/5pb/v+eZP7/rYH//6OT2PwtLTfvAAAA1gAAAJIAAABEAAAAFQAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wT///8X////RP///3f++vef/9/G4f/BkP//rm7//6Zf//+kW///pFv//6Ra//+mX///3sP///////////////////////////////////////////////////////////////////jy///Wtf//tHn//6Na//+hVv//o1r//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rc//+pZP//t3z/6r2Y/VNJQfAAAADbAAAAtQAAAKcFBQbBMDA74Hp0m/SrmeT9tJT+/6t+//+jbv7/n2T+/5xf/v+bXP7/m1z+/5tc/v+bXP7/mlr+/8Gb///69///////////////////////////////////7eH//657/v+ZWv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bW/7/qXP+/9W6///x5///9vD///Ho///fy///sH7//5pa/v+kb/7/tJT8/3Nuk/cKCgznAAAAuwAAAGwAAAAqAAAACwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wf///8h////U////4L+9e+u/9e37/+7hf//q2j//6Ve//+kW///o1n//6to///o1f//////////////////////////////////////////////////////////////////9/H//93B///Gmf//t37//6to//+kW///o1j//6JX//+jWf//pFr//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Ve//+sav//wI3/xaaO+SUhH+EAAADFICEmxHNvj+esnOH7tpf9/62B//+kb/7/n2X+/5xf/v+bXf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+aWv7/r3z+/+vf///////////////////////////////////+/f//1Lj+/59i/v+aWv7/m1z+/5tc/v+bXP7/m1v+/6Np/v/cxf///v3////////////////////////eyf//n2P+/55i/v+sfv//qJXg/TY1QvEAAADZAAAAmAAAAEkAAAAYAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///wv///8t////Yv7+/ov+7uG//86n+f+2e///qWT//6Vc//+jWf//rGj//+fT//////////////////////////////////////////////////////////////////////////////v4///27///6tn//9y////Kn///uoP//69v//+lXf//o1r//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFz//6hi//+2e//8zKf/j35w1yYnLq6alcLlu6X8/6+G//+lcv7/oGb+/51g/v+bXf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tb/v+cXf7/xqL///jz///////////////////////////////////07f//uY3+/5pa/v+bXP7/m1z+/5tc/v+aW/7/vpT+//r2//////////////////////////////Xu//+zhP7/mlv+/6Nt/v+0kf7/gHik+A8PEukAAAC/AAAAcgAAAC4AAAALAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///xH///86////bv79/ZT/5tLT/8eZ/v+xc///p2H//6Nb//+mX///2br///////////////////////////////////////////////////////////////////////////////////////////////////37///27///6tr//8+q//+ubf//o1j//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rc//+mX///q2j//7iA///Rq//Jsp2jkI+0kL2r/PithP//oWn+/51g/v+bXf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pZ/v+mbf7/4Mz///7+///////////////////////////////////gy/7/o2r+/5lZ/v+bXP7/mlv+/55i/v/aw/7/////////////////////////////////8Oj//7B+//+ZWf7/nmP+/6p7//+vmev+QkBR8gAAANsAAACdAAAATgAAABgAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Bf///xr///9I////ef769qH/3cLk/8CN//+ubf//pl///6NY//+0eP//5M////z6/////////////////////////////////////////////////////////////////////////////////////////////////////////Pr//9q9//+pZP//o1n//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rc//+mX///qWX//7Bx//+6g///y6H+/NzC2+zj2H/Rzvisu6P+/Kd3/v+dYf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1v+/5ta/v+6j/7/8+z///////////////////////////////////r2///Bmv7/mlv+/5tb/v+ZWf7/qnX+/+3i///////////////////////////////////gzP//omb+/5pa/v+cXv7/omv+/7OP//+Jf7D5EREU6QAAAMQAAAB3AAAAMAAAAA0AAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8B////CP///yP///9W////hP7z67P/1bPy/7qC//+rZ///pV3//6NZ//+ubv//zqf//+XQ///x5v//+/j////+////////////////////////////////////////////////////////////////////////////////////////9/L//7+N//+iWP//pFv//6Rb//+kW///pFv//6Rc//+lXv//qGP//65u//+4f///xZb//dKw6/nfyrD27ed6+/v6eufn/a7Dsf72q3/+/59k/v+bXf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mlr+/6Bk/v/VvP///fz//////////////////////////////////+fY//+ocf7/mVn+/5hZ/v/Amf7/+/j//////////////////////////////Pr//8ik/v+aWv7/m1z+/5tc/v+eYv7/qXj//7Ga8P5GRFfzAAAA3gAAAKIAAABSAAAAGwAAAAYAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////Df///y////9l/v7+jv7s3sT/zaT6/7V5//+pY///pFz//6NZ//+kW///qWX//7R4///BkP//06///+PL///v4///+PL///78///////////////////////////////////////////////////////////////////9+v//zaX//6NZ//+kW///pFv//6Rc//+lXv//qGP//61s//+2fP//wpL//tCs8frdxr/16d979fX0Vfz9/Vf///9z+/z+j9fR/tG2l/7+pHD+/51g/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/mVn+/7B+/v/r3////////////////////////////////////Pr//8yr/v+dX/7/nF3+/9jB///////////////////////////////////x6f//r33+/5pa/v+bXP7/m1z+/5xe/v+haf7/sov//46EuPoUFRjrAAAAyAAAAHwAAAAzAAAADgAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8D////E////z7///9y/v38l//kz9f/xZb+/7Bx//+nYf//pFz//6Ra//+jWv//olj//6FW//+jWv//p2D//7Fy//+/jP//0Kv//+DH///v4v//+PL///37//////////////////////////////////////////////v4///Flv//o1n//6Rb//+lXf//p2H//6xq//+1ef//wI7//s6n9fvbwcv36NuK9vX0W/v8/Uz+//9A////PP///1X///958PD+o8i4/uythP7/oGj+/5xe/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bW/7/nFz+/8il///59v//////////////////////////////////8Ob//7B+/v+ocv7/7+X//////////////////////////////////93H//+fYv7/mlv+/5tc/v+bXP7/m1z+/51h/v+ndv//sprz/lJQZ/MAAADgAAAApwAAAFYAAAAeAAAABwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8F////HP///0z///98/vn1pP/bv+f/vov//61r//+mXv//pFv//6Rb//+kW///pFv//6Rb//+jWf//olf//6FW//+iV///p2H//7Bx//+/jP//zaX//97D///r3P//9u7///z5////////////////////////6tr//7J0//+jW///p2D//6to//+zdv//vov//syk9/vavtH35tiU9vLwY/r7/E7+/v5C////Mv///yD///8X////K////1r///+D4t/+vryj/vqoeP7/nmL+/5td/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+ZWf7/p2/+/+PQ/////v///////////////////////////////v//07f+/8Oe///7+P/////////////////////////////69///wJj//5pb/v+bXP7/m1z+/5tc/v+bXP7/nF7+/6Fo/v+wif//l4vE+xsbIe0AAADMAAAAggAAADoAAAAQAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wH///8J////Jv///1r///+G/vLot//Sr/X/uYD//6pm//+lXf//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWf//olf//6JX//+jWf//qGL//7By//+8hv//zKP//9zB///p2f//7+P//9zA//+3ff//p1///6pm//+xcv//vIb//8qg/PzXutr45NSb9fHtafn6+1L9/v5F////Nf///yL///8S////Bv///wP///8Q////N////2z4+P6W0cf+3bOQ/v+jbf7/nF/+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pb/v+ZWv7/mVn+/5pb/v+bW/7/m1z+/5tb/v+aWv7/vZT///Xu///////////////////////////////////17///7+X///7+/////////////////////////////+3i//+pcv7/mlr+/5tc/v+bXP7/m1z+/5tc/v+bXP7/nWH+/6Z0//+ymPX+WVZw9AAAAOIAAACtAAAAXQAAACIAAAAHAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wH///8O////Mv///2f+/v6Q/urayf/Lovz/tHf//6hi//+kXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+jWv//o1n//6NY//+jWv//p1///65s//+xcf//qGH//6hi//+wcP//uoP//8eb/v3VteP44s+m9O7pa/j5+VP9/f5H////OP///yb///8U////CP///wL///8A////AP///wT///8b////TP///3vt7f6qxbP+8KyB/v+fZv7/nF3+/5tc/v+bXP7/m1z+/5tc/v+aW/7/nmH+/6Zu/v+mb/7/oWX+/5xd/v+ZWv7/mlr+/5lZ/v+hZf7/1rz///38////////////////////////////////////////////////////////////////////////1rz//51f/v+aW/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXf7/oGf+/6+G//+dj838JCQs7gAAAM8AAACHAAAAOwAAAA8AAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wT///8V////Qf///3X+/Pqa/+LM2v/ElP7/r2///6dg//+kXP//pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pVz//6dh//+ubv//uH///8WW/v3TsOv638q29ezldvf3+FT8/P1I////Ov///yj///8X////Cv///wP///8A////AP///wD///8A////Af///wr///8r////YP3+/one2f7GuZ7+/aZ0/v+dYv7/m13+/5tc/v+bXP7/m1z+/658/v/Vu///6t3//+rd///hzf//z7D//72T/v+tev7/omf+/5ta/v+tef//6dz///////////////////////////////////////////////////////////////////n1//+7kf7/mFj+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+dYP7/pXL+/7SX+f9oZIP1AwMD4wAAAK0AAABXAAAAGQAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////Af///wb///8e////T////37++POn/9q86v+9iP//rGr//6Ze//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kXP//pV7//6hj//+tbf//t33//8OU//3Rre763se99urhgPf29Vr8/f5K/v7/PP///yv///8Y////C////wP///8B////AP///wD///8A////AP///wD///8A////Av///xL///8+////cPf3/pjOwv7isYv+/6Jr/v+cX/7/m1z+/5pa/v+rdv7/5tf////////////////////////+/f//+vf//+/k///hzf//z7D+/7qP/v/Xvf///Pr/////////////////////////////////////////////////////////////6dv//6dx/v+ZWf7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5xd/v+fZf7/roP//6OU2PwsKzXrAAAAwwAAAG0AAAAhAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///wr///8p////Xf///4f+8OW7/9Gs9/+3fv//qmX//6Vc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//6dh//+sav//tXn//8GP//7OqfX728LF9ujdh/f19F77/PxO/v7+Qf///y7///8b////Df///wT///8B////AP///wD///8A////AP///wAAAAAA////AP///wD///8A////Bv///x////9R////f+nn/rLBrP72qn3+/59l/v+bXf7/mln+/8ek///8+//////////////////////////////////////////////9/P//9vD///bx///+/f/////////////////////////////////////////////////////////+///Tt///nF7+/5tb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5xf/v+kcP7/tZj7/3Juj/IJCQrHAAAAcwAAACMAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Av///w////81////av7+/ZL/6NbO/8me/f+zdv//qGL//6Rc//+kW///pFv//6Rb//+kW///pFv//6Rb//+kW///pV3//6dh//+raf//tHf//7+L//7Npff82r/R9ubZjfX08l77/P1O/v//Q////zL///8f////D////wX///8B////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////C////y////9k/f3+jNrT/s23mv7+pXL+/51h/v+bXP7/07f///7+////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////9/H//7iL/v+aW/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m13+/6Bn/v+xi///sKjf9zM1PrcAAABlAAAAHgAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////BP///xf///9E////d/77+J3/4Mfg/8KR//+vbv//pmD//6Rc//+kW///pFv//6Rb//+kW///pFz//6Zg//+rZ///snT//72I//7Kofn82LvY+OTUnPbx7mb5+vtP/v7+RP///zT///8i////Ev///wf///8C////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8D////Ff///0L///909PT+nsu+/uevif7/oWr+/5pa/v/Dnv//+/n////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////k1P//o2n+/5tb/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+cX/7/omv+/7OP//+9te7wQEJNiAAAAEIAAAAUAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////B////yD///9S////gf738Kv/2Lnu/7uG//+saf//pV3//6Rb//+kW///pVz//6Zf//+qZf//sXH//7uE///Inf781rjf+OPSo/Xv6275+vpT/f7+Rv///zb///8k////E////wf///8C////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8H////If///1X///+B5uT+t7+p/vipe/7/nWH+/6Zu/v/aw////Pr//////////////////////////////////////////////////////////////////////////////////////////////////////////////fz//8uq/v+aW/7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+cX/7/n2X+/6Nu/v+tg/7/v6r+/bi246wnKC46AAAAHAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8B////C////yz///9h////if7v4r7/z6n3/7Z7//+pZf//pV3//6Ze//+pZP//r2///7mB///GmP7+1LLq+eDMrvXt53H4+PhW/f39Sf///zr///8n////Ff///wn///8C////AP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8N////M////2n7/P6P18/+1LaV/v6kb/7/m17+/6Jn/v+/l/7/2sP//+zg///38v///Pr////////////////////////////////////////////////////////////////////////////////////////z6///sH7+/5lZ/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+dX/7/n2X+/6Rv/v+rfv7/tJP+/8Gu/vPNyPm0wsTZPnd3dQ9BQUAGAgICAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8C////EP///zn///9t/v38lf/n1NP/yZ3//7V6//+ubf//sHD//7h////Elf/90q/s+t/Jufbr5Hr29/dW/P3+Sf///zz///8r////Gf///wv///8D////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wP///8X////Rv///3fz8/6hyLn+7K6F/v+haP7/mlz+/5lX/v+aW/7/pWz+/7SE///Ho///2cL//+na///17////Pr//////////////////////////////////////////////////////////////////9/K//+fZP7/mlv+/5tc/v+bXP7/m1z+/5td/v+cX/7/n2X+/6Rv/v+rf/7/tZT+/8Cs/fPOxPvI3t33h+7v80r39/Yp////FP///wX///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8E////Gv///0f///95/vn2pf/hyuf/zaP//8OS///Gmf/+0a3y+93Fwfbp3oX29fRc+/z8TP7+/j////8t////G////w3///8F////Af///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wj///8m////Wf///oTi3v6/vaT++6h4/v+eY/7/m13+/5pb/v+ZWf7/mFf+/5pa/v+eYP7/p3H+/7WH/v/Fof7/177//+na///07f///Pr////////////////////////////////////////7+P//wZr+/5la/v+bXP7/m1z+/5td/v+dYP7/n2X+/6Rv/v+rf/7/tZT+/8Cs/fLOxfvG4N34jfLz+GX8/PtN/v7+O////yP///8Q////BP///wD+/v4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8I////I////1X///+F//jys//p2N3/4cnq/uPO0vvu44/59/Zf+/z9Tv7+/kH///8w////Hf///w7///8F////Af///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////Af///w////82////a/r6/pPTyv7atJH+/6Nt/v+cX/7/m1z+/5tc/v+bXP7/m1z+/5pb/v+aWv7/mVn+/5pa/v+dYP7/pGr+/7GA/v/Cm///1Ln//+bX///y6v//+/j///79///+/f//+fX//9O4//+hZv7/mlv+/5td/v+cX/7/n2X+/6Rv/v+rf/7/tZT+/8Gt/fPOxfvE4eD3ifX2+GL9/vtT///+R////zb///8i////EP///wX///8B////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wH///8M////LP///1v///+C//38l//695j//Pp6/v//WP///0X///8z////If///xH///8G////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////BP///xr///9K////eu7t/qnFtP7wrIH+/59m/v+cXv7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tb/v+aWv7/mFj+/5hW/v+bXP7/oWb+/698/v+/lv//y6v//8ur//+6j/7/n2P+/5pc/v+dX/7/n2X+/6Rv/v+rf/7/tZT+/8Cs/fDOxfvG4N74ivP092L9/ftS/v7+R////zf///8l////FP///wj///8D////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wL///8P////K////07///9j////Y////1L///86////JP///xL///8H////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8B////Cf///yn///9f/v//h9/b/sW6n/79pnX+/55h/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5pb/v+ZWf7/mVj+/5hY/v+ZWf7/mVr+/5lY/v+cXf7/n2X+/6Rv/v+rf/7/tJT+/8Cs/vTOxvvE4N/4jPP092P+/vxR///+Rv///zf///8k////E////wj///8C////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wP///8L////Gv///yf///8q////Iv///xT///8J////Av///wD///8A////AP///wD///8A////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8C////Ef///zz///9v9/j+l8/E/uCyjf7/omv+/5xf/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+cYP7/n2b+/6Rw/v+rgP7/tZX+/8Cs/vHOxfzJ4N74iPT1+GL9/ftS/v7+R////zb///8k////E////wj///8C////AP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP///wD///8A////AP///wH///8C////BP///wX///8D////Av///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8F////Hf///1D///996un+scOu/vWrfv7/n2X+/5xd/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5tc/v+bXP7/m1z+/5td/v+dX/7/n2X+/6Rw/v+sgP7/tZX+/8Gu/fHPx/vC4eD5jPX1+GH9/vxS///+Rv///zf///8k////E////wj///8C////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD///8A////AP///wD///8E////Gv///0j///95/Pz/nfDy/7Xr7f+07vD/l/r6/Wz///5V///+SP///zj///8l////FP///wj///8C////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/////AAAAf////////////////wAAAH////////////////wAAAA////////////////4AAAAP///////////////4AAAAD///////////////8AAAAAf//////////////8AAAAAD//////////////+AAAAAA//////////////+AAAAAAH/////////////+AAAAAAB//////////////AAAAAAAP/////////////AAAAAAAB///////gf////gAAAAAAAf//////gB////gAAAAAAAD//////gAP///wAAAAAAAA//////wAD///wAAAAAAAAH/////wAAf//4AAAAAAAAB/////wAAD//8AAAAAAAAAf////wAAA//+AAAAAAAAAD////4AAAP//AAAAAAAAAAf///4AAAB//wAAAAAAAAAH///8AAAAf/4AAAAAAAAAA///8AAAAD/+AAAAAAAAAAP//+AAAAA//gAAAAAAAAAB//8AAAAAP/4AAAAAAAAAAf/+AAAAAB/+AAAAAAAAAAD/+AAAAAAP/gAAAAAAAAAA//AAAAAAD/4AAAAAAAAAAH/AAAAAAA/+AAAAAAAAAAB/gAAAAAAH/gAAAAAAAAAAPAAAAAAAB/4AAAAAAAAAABgAAAAAAAP+AAAAAAAAAAAQAAAAAAAD/gAAAAAAAAAAAAAAAAAAA/4AAAAAAAAAAAAAAAAAAAH/AAAAAAAAAAAAAAAAAAAA/wAAAAAAAAAAAAAAAAAAAP/AAAAAAAAAAAAAAAAAAAD/wAAAAAAAAAAAAAAAAAAAf+AAAAAAAAAAAAAAAAAAAH/gAAAAAAAAAAAAAAAAAAB/8AAAAAAAAAAAAAAAAAAAP/AAAAAAAAAAAAAAAAAAAD/4AAAAAAAAAAAAAAAAAAA//AAAAAAAAAAAAAAAAAAAP/wAAAAAAAAAAAAAAAAAAD/+AAAAAAAAAAAAAAAAAAA//wAAAAAAAAAAAAAAAAAAP/8AAAAAAAAAAAAAAAAAAD//gAAAAAAAAAAAAAAAAAA//4AAAAAAAAAAAAAAAAAAP//AAAAAAAAAAAAAAAAAAD//wAAAAAAAAAAAAAAAAAA//+AAAAAAAAAAAAAAAAAAP//wAAAAAAAEAAAAAAAAAD//+AAAAAAAHAAAAAAAAAA///wAAAAAAH4AAAAAAAAAP//8AAAAAAH/AAAAAAAAAD///gAAAAAH/wAAAAAAAAA///4AAAAAD/+AAAAAAAAAP///AAAAAD//gAAAAAAAAD///4AAAAB//8AAAAAAAAA///+AAAAB///AAAAAAAAAP///gAAAA///wAAAAAAAAD///gAAAB////AAAAAAAAA///wAAAA////wAAAAAAAAP//gAAAA////+AAAAAAAAD//4AAAAf////gAAAAAAAA//4AAAAH////4AAAAAAAA//4AAAAB/////AAAAAAAA//4AAAAAP////wAAAAAAA//8AAAAAB////+AAAAAAA//8AAAAAAf////wAAAAAA//+AAAAAAD////8AAAAAAf/+AAAAAAAf////gAAAAAf/8AAAAAAAD////4AAAAAf/+AAAAAAAA/////AAAAAf//AAAAAAAAH////AAAAAf//wAAAAAAAA////gAAAAf//8AAAAAAAAP///gAAAAf///AAAAAAAAB///wAAAAP///wAAAAAAAAf//gAAAAf///8AAAAAAAAD//wAAAAP////AAAAAAAAA//wAAAAD////wAAAAAAAAH/wAAAAAf///8AAAAAAAAA/wAAAAAH////AAAAAAAAAP4AAAAAA////wAAAAAAAABwAAAAAAP///8AAAAAAAAAYAAAAAAB////AAAAAAAAAAAAAAAAAP///wAAAAAAAAAAAAAAAAD///8AAAAAAAAAAAAAAAAAf///AAAAAAAAAAAAAAAAAH///wAAAAAAAAAAAAAAAAA///8AAAAAAAAAAAAAAAAAP///AAAAAAAAAAAAAAAAAB///wAAAAAAAAAAAAAAAAAP//8AAAAAAAAAAAAAAAAAD///AAAAAAAAAAAAAAAAAA///4AAAAAAAAAAAAAAAAAH///AAAAAAAAAAAAAAAAAB///wAAAAAAAAAAAAAAAAAP///AAAAAAAAAAAAAAAAAB///wAAAAAAAAAAAAAAAAAf//+AAAAAAAAAAAAAAAAAH///gAAAAAAAAAAAAAAAAA///8AAAAAAAAAAAAAAAAAP///gAAAAAAAAAAAAAAAAD///8AAAAAAAAAAAAAAAAA////AAAAAAAIAAAAAAAAAP///4AAAAAAfAAAAAAAAAD////AAAAAAPwAAAAAAAAA////4AAAAAP+AAAAAAAAAf///+AAAAAH/wAAAAAAAAH////wAAAAP/8AAAAAAAAB////+AAAAH//gAAAAAAAAf////wAAAP//4AAAAAAAAP////+AAAH///AAAAAAAAD/////gAAH///4AAAAAAAB/////8AAD///+AAAAAAAA//////gAH////wAAAAAAB//////8AP////+AAAAAAD//////////////gAAAAAB//////////////8AAAAAD///////////////gAAAAB///////////////4AAAAD////////////////AAAAB////////////////4AAAD////////////////+AAAB//////4lQTkcNChoKAAAADUlIRFIAAAEAAAABAAgGAAAAXHKoZgAAAAFvck5UAc+id5oAAIAASURBVHja7P1XkyVZlh6KfXu79qNP6MxInaWru1pNT0/PYHpmMMAlacA1u+Q1Gh9ofMQfAI1vNCsY32gwvoCkwS7Ja5cGAheY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")
        icon = QIcon()
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(icon_data))
        icon.addPixmap(pixmap)
        self.setWindowIcon(icon)

    def setup_ui(self):
        """Setup the main UI components"""
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        
        # Create toolbar
        toolbar = QHBoxLayout()
        
        # Left side buttons
        left_buttons = QHBoxLayout()
        
        # Add directory picker
        self.pick_dir_btn = QPushButton("Pick Directory")
        self.pick_dir_btn.clicked.connect(self.pick_directory)
        left_buttons.addWidget(self.pick_dir_btn)
        
        # Add bulk edit toggle with consistent name
        self.bulk_edit_btn = QPushButton("Bulk Edit: OFF")
        self.bulk_edit_btn.clicked.connect(self.toggle_bulk_edit)
        left_buttons.addWidget(self.bulk_edit_btn)
        
        # Add search by credits button
        self.search_credits_button = QPushButton("Search by Credits")
        self.search_credits_button.clicked.connect(self.show_credit_search)
        left_buttons.addWidget(self.search_credits_button)
        
        toolbar.addLayout(left_buttons)
        
        # Add search box with clear directories button in the middle
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self.apply_search_filter)
        search_layout.addWidget(self.search_box)
        
        # Modify clear button to be a clear directories button
        self.clear_button = QPushButton("Clear All Directories")
        self.clear_button.clicked.connect(self.clear_directories)
        self.clear_button.hide()  # Initially hidden until directories are loaded
        search_layout.addWidget(self.clear_button)
        
        toolbar.addLayout(search_layout)
        
        # Add stretch to push right-side buttons to the right
        toolbar.addStretch()
        
        # Right side buttons
        right_buttons = QHBoxLayout()
        
        # Add commit all button on the right
        self.commit_all_button = QPushButton("No Changes")
        self.commit_all_button.setEnabled(False)
        self.commit_all_button.clicked.connect(self.commit_all_changes)
        right_buttons.addWidget(self.commit_all_button)
        
        # Add Shazam toggle on the right
        self.shazam_btn = QPushButton(SHAZAM_BUTTON_NORMAL["text"])
        self.shazam_btn.setStyleSheet(SHAZAM_BUTTON_NORMAL["style"])
        self.shazam_btn.clicked.connect(self.toggle_shazam_mode)
        right_buttons.addWidget(self.shazam_btn)
        
        toolbar.addLayout(right_buttons)
        
        self.main_layout.addLayout(toolbar)
        
        # Initialize table widget before setup
        self.table = QTableWidget()
        
        # Setup table
        self.setup_table()
        self.main_layout.addWidget(self.table)
        
        # Create GitHub and help buttons frame
        github_frame = QFrame()
        github_layout = QHBoxLayout(github_frame)
        github_layout.setContentsMargins(0, 0, 0, 0)
        
        help_button = QPushButton("❓ Help")
        help_button.clicked.connect(self.show_help_dialog)
        github_layout.addWidget(help_button)
        
        github_button = QPushButton("\u25D3 GitHub")
        github_button.clicked.connect(
            lambda: webbrowser.open("https://github.com/therzog92/SM_Metadata_Editor")
        )
        github_layout.addWidget(github_button)
        
        # Add settings button next to help button
        settings_btn = QPushButton("⚙️")
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self.show_settings_dialog)
        github_layout.addWidget(settings_btn)
        
        self.main_layout.addWidget(github_frame, alignment=Qt.AlignmentFlag.AlignRight)
        
        # Add display count indicator below toolbar
        self.display_count_frame = QFrame()
        count_layout = QHBoxLayout(self.display_count_frame)
        count_layout.setContentsMargins(4, 0, 4, 0)
        
        self.display_count_label = QLabel()
        self.display_count_label.setStyleSheet("color: #666;")  # Subtle gray color
        count_layout.addWidget(self.display_count_label)
        count_layout.addStretch()
        
        self.main_layout.addWidget(self.display_count_frame)
        self.display_count_frame.hide()  # Hidden by default
        
        # Set application-wide stylesheet for modern scrollbars
        self.setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;            /* Reduced from 14px */
                margin: 0px 0px 0px 0px;
                border-radius: 5px;     /* Reduced from 7px */
            }

            QScrollBar::handle:vertical {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a90e2, stop:0.5 #357abd, stop:1 #2c5a8c);
                min-height: 30px;
                border-radius: 5px;     /* Reduced from 7px */
            }

            QScrollBar::handle:vertical:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5da1e9, stop:0.5 #4a90e2, stop:1 #357abd);
            }

            QScrollBar::add-line:vertical {
                height: 0px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }

            QScrollBar::sub-line:vertical {
                height: 0px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }

            QScrollBar:horizontal {
                border: none;
                background: #f0f0f0;
                height: 10px;           /* Reduced from 14px */
                margin: 0px 0px 0px 0px;
                border-radius: 5px;     /* Reduced from 7px */
            }

            QScrollBar::handle:horizontal {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90e2, stop:0.5 #357abd, stop:1 #2c5a8c);
                min-width: 30px;
                border-radius: 5px;     /* Reduced from 7px */
            }

            QScrollBar::handle:horizontal:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5da1e9, stop:0.5 #4a90e2, stop:1 #357abd);
            }

            QScrollBar::add-line:horizontal {
                width: 0px;
                subcontrol-position: right;
                subcontrol-origin: margin;
            }

            QScrollBar::sub-line:horizontal {
                width: 0px;
                subcontrol-position: left;
                subcontrol-origin: margin;
            }
        """)

    def setup_bulk_edit_controls(self):
        """Set up bulk edit controls"""
        self.bulk_edit_controls = QFrame()
        bulk_layout = QHBoxLayout(self.bulk_edit_controls)
        
        # Create bulk edit fields
        self.bulk_fields = {}
        for field in ['subtitle', 'artist', 'genre']:
            label = QLabel(field.capitalize())
            edit = QLineEdit()
            bulk_layout.addWidget(label)
            bulk_layout.addWidget(edit)
            self.bulk_fields[field] = edit
        
        apply_button = QPushButton("Apply to Selected")
        apply_button.clicked.connect(self.apply_bulk_edit)
        bulk_layout.addWidget(apply_button)
        
        # Add to main layout and hide initially
        self.main_layout.addWidget(self.bulk_edit_controls)
        self.bulk_edit_controls.hide()
        
    def setup_table(self):
        """Set up the main table widget"""
        self.table = QTableWidget()
        self.table.setColumnCount(11)  # Add one more column for ID
        
        # Define column indices
        self.COL_CHECKBOX = 0
        self.COL_ACTIONS = 1
        self.COL_TYPE = 2
        self.COL_PACK = 3
        self.COL_TITLE = 4
        self.COL_SUBTITLE = 5
        self.COL_ARTIST = 6
        self.COL_GENRE = 7
        self.COL_STATUS = 8
        self.COL_COMMIT = 9
        self.COL_ID = 10
        
        # Set headers
        headers = ['', 'Actions', 'Type', 'Pack', 'Title', 'Subtitle', 'Artist', 'Genre', 'Status', 'Commit', 'ID']
        self.table.setHorizontalHeaderLabels(headers)
        
        # Set edit triggers for single-click editing
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.CurrentChanged |
            QTableWidget.EditTrigger.DoubleClicked |
            QTableWidget.EditTrigger.EditKeyPressed |
            QTableWidget.EditTrigger.AnyKeyPressed
        )
        
        # Set selection behavior
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        
        # Set lighter selection color
        self.table.setStyleSheet("""
            QTableWidget {
                selection-background-color: rgba(53, 122, 189, 0.3);
            }
        """)
        
        # Set column widths and make actions column fixed
        for col, width in enumerate(COLUMN_WIDTHS.values()):
            self.table.setColumnWidth(col, width)
            if col == 1:  # Actions column
                self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            # Make non-editable columns read-only
            if col not in [4, 5, 6, 7]:  # Not Title, Subtitle, Artist, or Genre
                self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        
        # Connect signals
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_table)
        
    def create_file_entry_with_type(self, filepaths, file_type, parent_dir, title, subtitle, artist, genre, music_file):
        """Create a file entry with specified type in the table"""
        try:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Create unique ID and increment counter
            entry_id = str(self.entry_counter)
            self.entry_counter += 1
            
            # Add empty checkbox column item and make it non-editable
            checkbox_item = QTableWidgetItem("")
            checkbox_item.setFlags(checkbox_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self.COL_CHECKBOX, checkbox_item)
            
            # Store entry data with ID
            entry_data = {
                'id': entry_id,
                'filepaths': filepaths,
                'original_values': {
                    'title': title,
                    'subtitle': subtitle,
                    'artist': artist,
                    'genre': genre
                }
            }
            self.file_entries.append(entry_data)
            
            # Add ID to table
            id_item = QTableWidgetItem(entry_id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self.COL_ID, id_item)
            
            # Create action buttons with ID reference
            action_widget = self.create_action_buttons(row, filepaths, music_file, entry_id)
            self.table.setCellWidget(row, self.COL_ACTIONS, action_widget)
            
            # Set file type and parent directory (read-only)
            type_item = QTableWidgetItem(file_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, type_item)
            
            pack_item = QTableWidgetItem(parent_dir)
            pack_item.setFlags(pack_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, pack_item)

            # Create editable metadata fields
            metadata_fields = {
                4: ('title', title),
                5: ('subtitle', subtitle),
                6: ('artist', artist),
                7: ('genre', genre)
            }

            for col, (field, value) in metadata_fields.items():
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

            # Add empty status and commit columns (read-only)
            status_item = QTableWidgetItem("")
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 8, status_item)
            
            commit_item = QTableWidgetItem("")
            commit_item.setFlags(commit_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 9, commit_item)

            return entry_data

        except Exception as e:
            print(f"Error in create_file_entry_with_type: {str(e)}")
            traceback.print_exc()
            return None

    def on_entry_change(self, row, filepath, field):
        """Handle changes to table entries"""
        try:
            # Map field names to column indices
            col_map = {
                'title': 4,
                'artist': 6,
                'genre': 7,
                'subtitle': 5
            }
            
            # Get column index for the field
            col_index = col_map.get(field)
            if col_index is None:
                print(f"Warning: Invalid field name: {field}")
                return
            
            # Get the item from the table
            item = self.table.item(row, col_index)
            if not item:
                print(f"Warning: No item found at row {row}, column {col_index}")
                return
            
            # Update status column
            status_item = QTableWidgetItem("⚠")
            status_item.setToolTip("Unsaved changes")
            self.table.setItem(row, 8, status_item)  # Status column
            
        except Exception as e:
            print(f"Error in on_entry_change: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_commit_all_button(self):
        """Update the commit all button state"""
        try:
            # Count rows with unsaved changes by checking both item and widget status
            uncommitted = 0
            for row in range(self.table.rowCount()):
                status_widget = self.table.cellWidget(row, 8)
                status_item = self.table.item(row, 8)
                
                has_warning = False
                if status_widget and isinstance(status_widget, QWidget):
                    label = status_widget.findChild(QLabel)
                    if label and label.text() == "⚠":
                        has_warning = True
                elif status_item and status_item.text() == "⚠":
                    has_warning = True
                    
                if has_warning:
                    uncommitted += 1
            
            if uncommitted > 0:
                self.commit_all_button.setText(f"Commit Changes ({uncommitted})")
                self.commit_all_button.setEnabled(True)
            else:
                self.commit_all_button.setText("No Changes")
                self.commit_all_button.setEnabled(False)
                
        except Exception as e:
            print(f"Error updating commit button: {str(e)}")
            import traceback
            traceback.print_exc()

    def commit_changes(self, row, filepaths):
        """Commit changes for a specific row"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
                
            # Find the entry in backend data using ID
            entry_id = id_item.text()
            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry:
                return
            
            # Get current values from table
            metadata = {
                'TITLE': self.table.item(row, self.COL_TITLE).text() if self.table.item(row, self.COL_TITLE) else '',
                'SUBTITLE': self.table.item(row, self.COL_SUBTITLE).text() if self.table.item(row, self.COL_SUBTITLE) else '',
                'ARTIST': self.table.item(row, self.COL_ARTIST).text() if self.table.item(row, self.COL_ARTIST) else '',
                'GENRE': self.table.item(row, self.COL_GENRE).text() if self.table.item(row, self.COL_GENRE) else ''
            }
            
            # Write changes to the actual files
            success = True
            for filepath in entry['filepaths']:  # Use filepaths from entry
                if not MetadataUtil.write_metadata(filepath, metadata):
                    success = False
                    break
            
            if success:
                # Update original values in backend data
                entry['original_values'].update({
                    'title': metadata['TITLE'],
                    'subtitle': metadata['SUBTITLE'],
                    'artist': metadata['ARTIST'],
                    'genre': metadata['GENRE']
                })
                
                # Update status columns
                self.table.removeCellWidget(row, self.COL_STATUS)
                self.table.setItem(row, self.COL_STATUS, QTableWidgetItem(""))
                self.table.removeCellWidget(row, self.COL_COMMIT)
                self.table.setItem(row, self.COL_COMMIT, QTableWidgetItem(""))
                
                # Update commit all button
                self.update_commit_all_button()
            
        except Exception as e:
            print(f"Error in commit_changes: {str(e)}")
            traceback.print_exc()

    def commit_all_changes(self):
        """Commit all pending changes"""
        try:
            # Find all rows with uncommitted changes
            for row in range(self.table.rowCount()):
                status_widget = self.table.cellWidget(row, 8)
                status_item = self.table.item(row, 8)
                
                has_warning = False
                if status_widget and isinstance(status_widget, QWidget):
                    label = status_widget.findChild(QLabel)
                    if label and label.text() == "⚠":
                        has_warning = True
                elif status_item and status_item.text() == "⚠":
                    has_warning = True
                
                if has_warning:
                    entry = next((e for e in self.file_entries if e['row'] == row), None)
                    if entry:
                        self.commit_changes(row, entry['filepaths'])
        except Exception as e:
            print(f"Error in commit_all_changes: {str(e)}")
            traceback.print_exc()

    async def do_shazam_analysis(self, file_path, row):
        """Perform Shazam analysis"""
        if self.shazam_mode and row != -1:
            print("Starting Shazam analysis...")
            try:
                result = await self.analyze_single_file(file_path)
                if result and 'track' in result:
                    track = result['track']
                    shazam_data = {
                        'title': track.get('title', ''),
                        'artist': track.get('subtitle', ''),
                        'genre': track.get('genres', {}).get('primary', ''),
                        'images': {'coverart': track['share']['image']} if 'share' in track and 'image' in track['share'] else {}
                    }
                    self.show_shazam_results(row, shazam_data)
                else:
                    print("No Shazam results found")
            except Exception as e:
                print(f"Shazam analysis error: {str(e)}")
                import traceback
                traceback.print_exc()

    def play_audio(self, music_path, play_btn, entry_id):
        """Play audio file with fallback logic"""
        try:
            # Handle current playing button
            try:
                if self.current_playing:
                    pygame.mixer.music.stop()
                    self.current_playing.setText("▶")
                    if self.current_playing == play_btn:
                        self.current_playing = None
                        return
            except RuntimeError:
                self.current_playing = None
            except Exception as e:
                print(f"Error handling current playing button: {str(e)}")
                self.current_playing = None

            directory = os.path.dirname(music_path)
            base_filename = os.path.basename(music_path)
            found_playable = False
            actual_path = None

            # Priority 1: Exact filepath
            if os.path.exists(music_path):
                try:
                    pygame.mixer.music.load(music_path)
                    found_playable = True
                    actual_path = music_path
                    print(f"Using exact file: {music_path}")
                except Exception as e:
                    print(f"Failed to load exact file: {str(e)}")

            # Priority 2: Using filename as mask
            if not found_playable and base_filename:
                mask_term = os.path.splitext(base_filename)[0]
                for file in os.listdir(directory):
                    if mask_term in file and file.lower().endswith(tuple(SUPPORTED_AUDIO)):
                        try:
                            test_path = os.path.join(directory, file)
                            pygame.mixer.music.load(test_path)
                            found_playable = True
                            actual_path = test_path
                            print(f"Using masked file: {test_path}")
                            break
                        except Exception as e:
                            print(f"Failed to load masked file {file}: {str(e)}")

            # Priority 3: Any supported audio file (smallest one)
            if not found_playable:
                audio_files = []
                for file in os.listdir(directory):
                    if file.lower().endswith(tuple(SUPPORTED_AUDIO)):
                        file_path = os.path.join(directory, file)
                        try:
                            size = os.path.getsize(file_path)
                            audio_files.append((size, file_path))
                        except Exception as e:
                            print(f"Failed to get size for {file}: {str(e)}")

                if audio_files:
                    # Sort by size, then by path (for same-size files)
                    audio_files.sort(key=lambda x: (x[0], x[1]))
                    try:
                        pygame.mixer.music.load(audio_files[0][1])
                        found_playable = True
                        actual_path = audio_files[0][1]
                        print(f"Using smallest audio file: {actual_path} ({audio_files[0][0]} bytes)")
                    except Exception as e:
                        print(f"Failed to load smallest audio file: {str(e)}")

            if found_playable and actual_path:
                pygame.mixer.music.play()
                play_btn.setText("⏹")
                play_btn.setEnabled(True)
                self.current_playing = play_btn
                
                # If Shazam mode is active, analyze the file
                if self.shazam_mode:
                    current_row = self.find_row_by_id(entry_id)
                    if current_row != -1:
                        self.run_shazam_analysis(actual_path, current_row)
            else:
                print(f"No playable audio found in {directory}")
                play_btn.setText("\U0001F507")  # Unicode for speaker with cancellation slash
                play_btn.setEnabled(False)
                play_btn.setToolTip("No audio file found")

        except Exception as e:
            print(f"Error in play_audio: {str(e)}")
            traceback.print_exc()

    def run_shazam_analysis(self, audio_path, row):
        """Run Shazam analysis on an audio file"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                print("Debug: No ID item found for row", row)
                return
                
            entry_id = id_item.text()
            print(f"Debug: Running Shazam analysis for ID {entry_id} at row {row}")
            
            # Find current row for this ID (in case table was sorted)
            current_row = self.find_row_by_id(entry_id)
            if current_row == -1:
                print(f"Debug: Could not find row for ID {entry_id}")
                return
            
            print(f"Debug: Current row for ID {entry_id} is {current_row}")
            
            # Run Shazam analysis
            try:
                result = self.loop.run_until_complete(self.shazam.recognize(audio_path))
                print(f"Debug: Shazam result: {result}")
                
                if result and 'track' in result:
                    track = result['track']
                    shazam_data = {
                        'title': track.get('title', ''),
                        'artist': track.get('subtitle', ''),
                        'genre': track.get('genres', {}).get('primary', ''),
                        'images': {'coverart': track['share']['image']} if 'share' in track and 'image' in track['share'] else {}
                    }
                    print(f"Debug: Processed Shazam data: {shazam_data}")
                    self.show_shazam_results(current_row, shazam_data)  # Use current_row here
                else:
                    print("Debug: No Shazam results found")
                
            except Exception as e:
                print(f"Debug: Error in Shazam analysis: {str(e)}")
                traceback.print_exc()
                
        except Exception as e:
            print(f"Error in run_shazam_analysis: {str(e)}")
            traceback.print_exc()

    def open_file_location(self, directory):
        try:
            if os.name == 'nt':  # Windows
                os.startfile(directory)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.run(['open', directory])
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Error opening directory {directory}: {str(e)}"
            )

    async def analyze_single_file(self, file_path):
        """Analyze a single file with Shazam"""
        try:
            shazam = Shazam()
            return await shazam.recognize(file_path)  # Updated from recognize_song
        except Exception as e:
            print(f"Error in Shazam analysis: {str(e)}")
            traceback.print_exc()
            return None
    
    def pick_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            try:
                # Find all SM/SSC files and their parent packs
                packs = set()
                sm_files_found = False
                
                for root, _, files in os.walk(directory):
                    for file in files:
                        if file.endswith(tuple(SUPPORTED_EXTENSIONS)):
                            sm_files_found = True
                            # Get the song directory and its parent (pack directory)
                            song_dir = os.path.dirname(os.path.join(root, file))
                            pack_dir = os.path.dirname(song_dir)
                            pack_name = os.path.basename(pack_dir)
                            
                            # Add to packs regardless of directory level
                            if pack_name:
                                packs.add((pack_name, pack_dir))
                
                if packs:
                    # Show pack selector dialog
                    dialog = PackSelectorDialog(self, {name for name, _ in packs})
                    dialog.setModal(True)
                    
                    result = dialog.exec()
                    
                    if result == QDialog.DialogCode.Accepted:
                        selected_packs = dialog.selected_packs
                        self.load_selected_packs(
                            directory,
                            {path for name, path in packs if name in selected_packs}
                        )
                elif sm_files_found:
                    # If no packs found but SM files exist, treat selected directory as a pack
                    self.load_selected_packs(os.path.dirname(directory), {directory})
                else:
                    QMessageBox.information(
                        self,
                        "No Songs Found",
                        "No StepMania files (.sm/.ssc) were found in the selected directory."
                    )
                    
            except Exception as e:
                print(f"Error in pick_directory: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.warning(
                    self,
                    "Error",
                    f"An error occurred while loading directory: {str(e)}"
                )

    def load_selected_packs(self, base_directory, selected_pack_paths):
        """Load selected packs with proper error handling"""
        progress = None
        try:
            # Get unique pack names of existing directories
            existing_pack_names = {os.path.basename(dir_path) for dir_path in self.selected_directories}
            
            # Filter out packs that are already loaded (by pack name)
            new_pack_paths = {
                path for path in selected_pack_paths 
                if os.path.basename(path) not in existing_pack_names
            }
            
            if not new_pack_paths:
                QMessageBox.information(
                    self,
                    "Already Loaded",
                    "All selected packs are already loaded."
                )
                return
                
            # Get current table row count
            existing_rows = self.table.rowCount()
            
            # Create progress dialog with better styling
            progress = QMessageBox(self)
            progress.setWindowTitle("Loading")
            if existing_rows > 0:
                progress.setText(f"Reloading {existing_rows} existing songs, loading new songs...")
            else:
                progress.setText("Loading selected packs...")
            progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress.setStyleSheet("""
                QMessageBox {
                    min-width: 300px;
                    min-height: 100px;
                }
            """)
            progress.show()
            QApplication.processEvents()
            
            # Add the new pack paths to existing ones
            self.selected_directories.update(new_pack_paths)
            
            # Clear existing table but preserve file_entries
            old_entries = self.file_entries.copy()
            self.table.setRowCount(0)
            self.file_entries.clear()
            
            # Track loaded songs
            loaded_songs = 0
            
            # Modify load_files_from_all_directories to update progress
            def update_progress():
                nonlocal loaded_songs
                loaded_songs += 1
                if existing_rows > 0:
                    progress.setText(f"Reloading {existing_rows} existing songs... ({loaded_songs} new songs processed)")
                else:
                    progress.setText(f"Loading songs... ({loaded_songs} songs processed)")
                QApplication.processEvents()
            
            # Pass the progress callback to load_files_from_all_directories
            self.load_files_from_all_directories(update_progress)
            
        except Exception as e:
            print(f"Error loading packs: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(
                self,
                "Load Error",
                f"An error occurred while loading packs: {str(e)}"
            )
        finally:
            # Ensure progress dialog is properly cleaned up
            if progress:
                try:
                    progress.close()
                    progress.deleteLater()
                    QApplication.processEvents()
                except Exception as e:
                    print(f"Error cleaning up progress dialog: {str(e)}")

    def load_files_from_all_directories(self, progress_callback=None):
        """Load all StepMania files from selected directories"""
        try:
            self.table.setSortingEnabled(False)
            
            # Process existing table in chunks
            if self.table.rowCount() > 0:
                chunk_size = 100
                for i in range(0, self.table.rowCount(), chunk_size):
                    end = min(i + chunk_size, self.table.rowCount())
                    for j in range(i, end):
                        self.table.removeRow(i)
                    QApplication.processEvents()
            
            self.table.setRowCount(0)
            self.file_entries.clear()
            
            # Show UI elements
            for widget in [self.clear_button, self.bulk_edit_btn, 
                          self.search_credits_button, self.search_frame]:
                if widget and hasattr(widget, 'show'):
                    widget.show()
            
            # Process files by directory
            files_by_dir = defaultdict(list)
            
            # Find all SM/SSC files in selected directories
            for pack_dir in self.selected_directories:
                for song_dir in next(os.walk(pack_dir))[1]:
                    full_song_dir = os.path.join(pack_dir, song_dir)
                    
                    # Get all files in directory
                    dir_files = os.listdir(full_song_dir)
                    
                    # Group files by base name (case insensitive)
                    grouped_files = {}
                    for file in dir_files:
                        if file.lower().endswith(tuple(SUPPORTED_EXTENSIONS)):
                            base_name = os.path.splitext(file)[0].lower()
                            if base_name not in grouped_files:
                                grouped_files[base_name] = {'sm': None, 'ssc': None}
                            
                            full_path = os.path.join(full_song_dir, file)
                            if file.lower().endswith('.sm'):
                                grouped_files[base_name]['sm'] = full_path
                            elif file.lower().endswith('.ssc'):
                                grouped_files[base_name]['ssc'] = full_path
                    
                    # Process each group of files
                    for base_name, files in grouped_files.items():
                        sm_path = files['sm']
                        ssc_path = files['ssc']
                        
                        if ssc_path:  # SSC exists
                            ssc_metadata = MetadataUtil.read_metadata(ssc_path)
                            if sm_path:  # Both exist
                                files_by_dir[full_song_dir].append({
                                    'primary_file': ssc_path,
                                    'secondary_file': sm_path,
                                    'metadata': ssc_metadata,
                                    'type': 'sm+ssc'
                                })
                            else:  # SSC only
                                files_by_dir[full_song_dir].append({
                                    'primary_file': ssc_path,
                                    'metadata': ssc_metadata,
                                    'type': 'ssc'
                                })
                        elif sm_path:  # SM only
                            sm_metadata = MetadataUtil.read_metadata(sm_path)
                            files_by_dir[full_song_dir].append({
                                'primary_file': sm_path,
                                'metadata': sm_metadata,
                                'type': 'sm'
                            })
                            
            # Add files to table in chunks
            chunk_size = 50
            for directory, files in files_by_dir.items():
                for i in range(0, len(files), chunk_size):
                    chunk = files[i:i + chunk_size]
                    for file_info in chunk:
                        try:
                            metadata = file_info['metadata']
                            filepaths = [file_info['primary_file']]
                            if 'secondary_file' in file_info:
                                filepaths.append(file_info['secondary_file'])
                            
                            self.create_file_entry_with_type(
                                filepaths=filepaths,
                                file_type=file_info['type'],
                                parent_dir=os.path.basename(os.path.dirname(directory)),
                                title=metadata.get('TITLE', '').strip(),
                                subtitle=metadata.get('SUBTITLE', '').strip(),
                                artist=metadata.get('ARTIST', '').strip(),
                                genre=metadata.get('GENRE', '').strip(),
                                music_file=metadata.get('MUSIC', '')
                            )
                            
                            if progress_callback:
                                progress_callback()
                        except Exception as e:
                            print(f"Error creating file entry: {e}")
                            continue
                    QApplication.processEvents()
            
            self.table.setSortingEnabled(True)
            total_count = len(self.file_entries)
            self.update_display_count(total_count, total_count)
            
        except Exception as e:
            print(f"Error loading files: {e}")
            traceback.print_exc()

    def apply_search_filter(self):
        """Apply search filter to table entries"""
        search_text = self.search_box.text().lower()
        shown_count = 0
        total_count = len(self.file_entries)
        
        # If search is empty, show all rows and update count
        if not search_text:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            self.update_display_count(total_count, total_count)
            return
        
        # For each row in the table
        for row in range(self.table.rowCount()):
            # Get searchable text from table items
            searchable_fields = []
            
            # Parent directory (Pack) - column 3
            pack_item = self.table.item(row, 3)
            if pack_item:
                searchable_fields.append(pack_item.text())
                
            # Title - column 4
            title_item = self.table.item(row, 4)
            if title_item:
                searchable_fields.append(title_item.text())
                
            # Subtitle - column 5
            subtitle_item = self.table.item(row, 5)
            if subtitle_item:
                searchable_fields.append(subtitle_item.text())
                
            # Artist - column 6
            artist_item = self.table.item(row, 6)
            if artist_item:
                searchable_fields.append(artist_item.text())
                
            # Genre - column 7
            genre_item = self.table.item(row, 7)
            if genre_item:
                searchable_fields.append(genre_item.text())
            
            # Combine all fields and search
            searchable_text = ' '.join(searchable_fields).lower()
            hide_row = search_text not in searchable_text
            
            self.table.setRowHidden(row, hide_row)
            if not hide_row:
                shown_count += 1
        
        # Update display count after filtering
        self.update_display_count(shown_count, total_count)

    def get_column_index(self, field):
        """Helper method to get column index for a field"""
        column_map = {
            'title': 4,
            'subtitle': 5,
            'artist': 6,
            'genre': 7
        }
        return column_map.get(field, 0)
    
    def toggle_bulk_edit(self):
        """Toggle bulk edit mode"""
        self.bulk_edit_enabled = not self.bulk_edit_enabled
        
        if self.bulk_edit_enabled:
            self.bulk_edit_btn.setText("Exit Bulk Edit")
            self.bulk_edit_controls.show()
            # Disable direct editing of cells during bulk edit
            self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        else:
            self.bulk_edit_btn.setText("Bulk Edit: OFF")
            self.bulk_edit_controls.hide()
            # Re-enable direct editing
            self.table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
            self.table.clearSelection()

    def apply_bulk_edit(self):
        """Apply bulk edits to selected rows"""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        
        if not selected_rows:
            return
        
        # Get values from bulk edit fields
        new_values = {
            'subtitle': self.bulk_fields['subtitle'].text(),
            'artist': self.bulk_fields['artist'].text(),
            'genre': self.bulk_fields['genre'].text()
        }
        
        # Apply to each selected row
        for row in selected_rows:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                continue
            
            # Find the entry in backend data using ID
            entry_id = id_item.text()
            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
            
            if entry:
                for field, value in new_values.items():
                    if value:  # Only update if value is not empty
                        col_index = self.get_column_index(field)
                        item = QTableWidgetItem(value)
                        self.table.setItem(row, col_index, item)
                        self.on_entry_change(row, entry['filepaths'], field)

    def toggle_shazam_mode(self):
        """Toggle Shazam mode on/off"""
        self.shazam_mode = not self.shazam_mode
        
        if self.shazam_mode:
            # Show information popup
            msg = QMessageBox(self)
            msg.setWindowTitle("Shazam Mode Activated!")
            msg.setText(f"🎵 Shazam Mode is now active! Here's how it works:")
            msg.setInformativeText("""
                1. Press ▶ on any song to analyze with Shazam
                                   
                2. Results will appear as follows:
                   • Matching fields will turn green
                   • Different values will show as blue suggestion buttons
                   • A "Compare Artwork" button (camera icon)
                     will appear if new jacket artwork is found

                3. To use suggestions:
                   • Left-click to accept a new value
                   • Right-click to keep the original value
                    Click "Compare Artwork" to compare and 
                     choose between current and new jacket artwork

                Remember: No changes are permanent until you click 'Commit'! :)
                """)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.setIcon(QMessageBox.Icon.NoIcon)
            msg.setStyleSheet("""
                QMessageBox {
                    min-width: 300px;
                    min-height: 100px;
                }
            """)
            
            # Force the size
            msg.show()
            msg.setFixedSize(msg.sizeHint())
            msg.exec()
            
            self.shazam_btn.setText(SHAZAM_BUTTON_ACTIVE["text"])
            self.shazam_btn.setStyleSheet("""
                QPushButton {
                    background-color: lightgreen;
                    color: black;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12pt;
                    font-weight: bold;
                    min-width: 150px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #90EE90;
                }
            """)
        else:
            self.shazam_btn.setText(SHAZAM_BUTTON_NORMAL["text"])
            self.shazam_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a90e2;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12pt;
                    font-weight: bold;
                    min-width: 150px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #357abd;
                }
            """)

    def show_shazam_results(self, row, shazam_data):
        """Display Shazam results for a row"""
        if not self.shazam_mode:
            return
        
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
            
            # Find the entry using ID instead of row
            entry_id = id_item.text()
            entry_data = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry_data:
                return

            # Initialize metadata dictionary if it doesn't exist
            if 'metadata' not in entry_data:
                entry_data['metadata'] = {}

            # Store widgets temporarily to prevent deletion
            self.temp_widgets = []
            
            # Column mapping
            col_map = {
                'title': 4,
                'artist': 6,
                'genre': 7
            }
            
            print(f"Processing Shazam data: {shazam_data}")
            
            # Create suggestion buttons for each field
            for field in ['title', 'artist', 'genre']:
                if field in shazam_data and shazam_data[field]:
                    try:
                        col_index = col_map[field]
                        current_item = self.table.item(row, col_index)
                        current_value = current_item.text() if current_item else ''
                        
                        # Escape special characters in the Shazam value
                        new_value = str(shazam_data[field])
                        escaped_new_value = (new_value
                            .replace('#', r'\#')
                            .replace(':', r'\:')
                            .replace(';', r'\;')
                            .strip()
                        )
                        
                        if current_value.lower() == escaped_new_value.lower():
                            # Values match - show green confirmation but keep field editable
                            item = QTableWidgetItem(current_value)
                            item.setBackground(QColor("#f0fff0"))  # Light green background
                            self.table.setItem(row, col_index, item)
                            entry_data['metadata'][field] = current_value  # Store current value
                        else:
                            # Create container widget
                            container = QWidget()
                            layout = QVBoxLayout(container)
                            layout.setContentsMargins(4, 4, 4, 4)
                            layout.setSpacing(4)

                            # Create suggestion button
                            suggest_btn = QPushButton()
                            
                            # Add right-click functionality
                            suggest_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                            suggest_btn.customContextMenuRequested.connect(
                                lambda pos, r=row, f=field, v=current_value:
                                self.reject_shazam_value(r, f, v)
                            )

                            # Keep all the existing styling and setup exactly as is
                            suggest_btn.setStyleSheet("""
                                QPushButton {
                                    background-color: #4a90e2;
                                    color: white;
                                    border: none;
                                    border-radius: 4px;
                                    padding: 8px;
                                    text-align: left;
                                    min-height: 50px;
                                }
                                QPushButton:hover {
                                    background-color: #357abd;
                                }
                            """)

                            # Create layout for button content
                            btn_layout = QVBoxLayout(suggest_btn)
                            btn_layout.setContentsMargins(4, 4, 4, 4)
                            btn_layout.setSpacing(2)
                            
                            # Add current and new value labels
                            current_label = QLabel(f"Current: {current_value}")
                            current_label.setStyleSheet("color: #ccc; font-size: 9pt;")
                            new_label = QLabel(f"New: {escaped_new_value}")
                            new_label.setStyleSheet("color: white; font-size: 10pt; font-weight: bold;")
                            
                            btn_layout.addWidget(current_label)
                            btn_layout.addWidget(new_label)

                            suggest_btn.clicked.connect(
                                lambda checked, r=row, f=field, v=escaped_new_value:
                                self.apply_shazam_value(r, f, v)
                            )
                            
                            layout.addWidget(suggest_btn)
                            self.table.setCellWidget(row, col_index, container)
                            self.temp_widgets.append(container)
                            
                            # Set row height to accommodate the taller button
                            self.table.setRowHeight(row, 70)

                    except Exception as e:
                        print(f"Error processing field {field}: {str(e)}")
                        traceback.print_exc()
                        continue

            # Add artwork button if available
            if 'images' in shazam_data and 'coverart' in shazam_data['images']:
                # Check if actions widget exists
                actions_widget = self.table.cellWidget(row, 1)
                if actions_widget:
                    actions_layout = actions_widget.layout()
                    
                    # Check if artwork button already exists
                    artwork_btn_exists = False
                    for i in range(actions_layout.count()):
                        widget = actions_layout.itemAt(i).widget()
                        if isinstance(widget, QPushButton) and widget.text() == "📸":
                            artwork_btn_exists = True
                            break
                    
                    # Only create new button if it doesn't exist
                    if not artwork_btn_exists:
                        artwork_btn = QPushButton("📸")
                        artwork_btn.setToolTip("Compare Artwork")
                        artwork_btn.setMinimumWidth(30)
                        artwork_btn.clicked.connect(
                            lambda: self.compare_artwork(
                                row,
                                shazam_data['images']['coverart'],
                                os.path.dirname(entry_data['filepaths'][0])
                            )
                            )
                        artwork_btn.setStyleSheet("""
                            QPushButton {
                                background-color: #4a90e2;
                                color: white;
                                border: none;
                                border-radius: 4px;
                                padding: 4px 8px;
                            }
                            QPushButton:hover {
                                background-color: #357abd;
                            }
                        """)
                        
                        # Add to actions cell before the stretch
                        actions_layout.insertWidget(3, artwork_btn)
                        
        except Exception as e:
            print(f"Error in show_shazam_results: {str(e)}")
            traceback.print_exc()

    def apply_shazam_value(self, row, field, value):
        """Apply a Shazam suggestion to a field"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
            
            # Find the entry using ID instead of row
            entry_id = id_item.text()
            entry_data = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry_data:
                print(f"Warning: Could not find entry data for ID {entry_id}")
                return
            
            # Find the current row for this ID (in case table was sorted)
            current_row = self.find_row_by_id(entry_id)
            if current_row == -1:
                return
            
            # Use current_row instead of row parameter from here on
            row = current_row

            # Value is already escaped when passed from show_shazam_results
            escaped_value = str(value).strip()

            # Map field names to column indices
            col_map = {
                'title': 4,
                'artist': 6,
                'genre': 7
            }
            
            col_index = col_map.get(field)
            if col_index is None:
                print(f"Warning: Invalid field name: {field}")
                return

            # Get current value
            current_item = self.table.item(row, col_index)
            current_value = current_item.text() if current_item else ""

            # Only mark as changed if the value is different
            if current_value != escaped_value:
                # Create new editable table item with the escaped value
                new_item = QTableWidgetItem(escaped_value)
                new_item.setForeground(QColor("#FF8C00"))  # Dark orange
                new_item.setFlags(new_item.flags() | Qt.ItemFlag.ItemIsEditable)
                
                # Remove the button container and set the new editable item
                self.table.removeCellWidget(row, col_index)
                self.table.setItem(row, col_index, new_item)
                
                # Update metadata
                if 'metadata' not in entry_data:
                    entry_data['metadata'] = {}
                entry_data['metadata'][field] = escaped_value
                
                # Update commit button and status
                self.update_row_status(row, entry_data['filepaths'])
                
                # Update the commit all button
                self.update_commit_all_button()
            
            # Check for remaining suggestions and update row height
            self.check_remaining_suggestions(row, col_index)
            
        except Exception as e:
            print(f"Error applying Shazam value: {str(e)}")
            traceback.print_exc()

    def collect_credits(self):
        """Collect all unique credits from loaded files"""
        all_credits = set()  # Back to using a simple set
        has_no_credits = False
        
        for entry in self.file_entries:
            entry_has_credits = False
            for filepath in entry['filepaths']:
                metadata = MetadataUtil.read_metadata(filepath)
                if 'CREDITS' in metadata:
                    valid_credits = {credit.lower() for credit in metadata['CREDITS'] 
                                   if credit and not credit.isspace()}
                    if valid_credits:
                        entry_has_credits = True
                        all_credits.update(valid_credits)
            
            if not entry_has_credits:
                has_no_credits = True
        
        if has_no_credits:
            all_credits.add('no credits! :(')
        
        return sorted(all_credits)  # Simple sort since everything is already lowercase

    def show_credit_search(self):
        credits = self.collect_credits()
        dialog = CreditSelectorDialog(self, sorted(credits))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_credit_filter(dialog.selected_credits)

    def apply_credit_filter(self, selected_credits):
        if not selected_credits:
            # Show all entries
            for entry in self.file_entries:
                self.table.setRowHidden(entry['row'], False)
            self.statusBar().showMessage("Ready")
            return

        shown_count = 0
        total_count = len(self.file_entries)
        
        for entry in self.file_entries:
            show_entry = False
            entry_has_credits = False
            entry_credits = set()
            
            # Collect credits from all files in the entry
            for filepath in entry['filepaths']:
                metadata = MetadataUtil.read_metadata(filepath)
                if metadata.get('CREDITS'):
                    valid_credits = {credit.lower() for credit in metadata['CREDITS'] 
                                   if credit and not credit.isspace()}
                    if valid_credits:
                        entry_has_credits = True
                        entry_credits.update(valid_credits)
        
            # Check if we should show this entry
            if not entry_has_credits and 'no credits! :(' in selected_credits:
                # Show entries with no credits when "no credits! :(" is selected
                show_entry = True
                shown_count += 1
            elif entry_credits and (entry_credits & selected_credits):
                # Show entries that have any of the selected credits
                show_entry = True
                shown_count += 1
            
            self.table.setRowHidden(entry['row'], not show_entry)
        
        # Update display count
        self.update_display_count(shown_count, total_count)
        
        # Update status bar
        self.statusBar().showMessage("Credit filter applied")

    def clear_directories(self):
        """Clear all loaded directories and reset the table"""
        reply = QMessageBox.question(
            self,
            "Clear All Directories",
            "Are you sure you want to clear all loaded directories?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.selected_directories.clear()
            self.table.setRowCount(0)
            self.file_entries.clear()
            
            # Hide buttons that should only show when files are loaded
            # Only hide widgets that exist
            if hasattr(self, 'clear_button') and self.clear_button:
                self.clear_button.hide()
            if hasattr(self, 'bulk_edit_btn') and self.bulk_edit_btn:
                self.bulk_edit_btn.hide()
            if hasattr(self, 'search_credits_button') and self.search_credits_button:
                self.search_credits_button.hide()
            if hasattr(self, 'commit_all_button') and self.commit_all_button:
                self.commit_all_button.hide()
            
            # Reset status bar and display count
            self.statusBar().showMessage("Ready")
            self.update_display_count(0, 0)

    def sort_table(self, column):
        """Sort table by clicked column header"""
        try:
            # Only handle sortable columns
            if column not in [3, 4, 5, 6, 7]:  # pack, title, subtitle, artist, genre
                return
                
            # Store current sort order
            field_map = {3: 'pack', 4: 'title', 5: 'subtitle', 6: 'artist', 7: 'genre'}
            field = field_map[column]
            self.sort_reverse[field] = not self.sort_reverse[field]
            
            # Sort using Qt's built-in functionality
            self.table.sortItems(column, Qt.SortOrder.AscendingOrder if not self.sort_reverse[field] 
                                       else Qt.SortOrder.DescendingOrder)
            
            # Update file_entries row references
            for entry in self.file_entries:
                for row in range(self.table.rowCount()):
                    if self.table.item(row, 3) and entry['original_values'].get('pack') == self.table.item(row, 3).text():
                        entry['row'] = row
                        break
                        
        except Exception as e:
            print(f"Sort error: {str(e)}")
            traceback.print_exc()

    def show_help_dialog(self):
        """Show the help dialog with usage instructions"""
        dialog = HelpDialog(self)
        dialog.exec()

    def show_artwork_preview(self, row, artwork_url):
        """Show artwork preview dialog with option to save"""
        try:
            # Download image
            response = requests.get(artwork_url)
            image = Image.open(BytesIO(response.content))
            
            # Create preview dialog
            preview = QDialog(self)
            preview.setWindowTitle("Album Artwork Preview")
            layout = QVBoxLayout(preview)
            
            # Convert PIL image to QPixmap
            qim = ImageQt.ImageQt(image)
            pixmap = QPixmap.fromImage(qim)
            
            # Scale pixmap if too large
            max_size = 400
            if pixmap.width() > max_size or pixmap.height() > max_size:
                pixmap = pixmap.scaled(max_size, max_size, 
                                     Qt.AspectRatioMode.KeepAspectRatio, 
                                     Qt.TransformationMode.SmoothTransformation)
            
            # Add image to dialog
            label = QLabel()
            label.setPixmap(pixmap)
            layout.addWidget(label)
            
            # Add buttons
            button_frame = QFrame()
            button_layout = QHBoxLayout(button_frame)
            
            save_btn = QPushButton("Save Artwork")
            save_btn.clicked.connect(lambda: self.save_artwork(row, image))
            button_layout.addWidget(save_btn)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(preview.accept)
            button_layout.addWidget(close_btn)
            
            layout.addWidget(button_frame)
            preview.exec()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load artwork: {str(e)}")
            
    def save_artwork(self, row, image):
        """Save artwork to song directory and update JACKET metadata"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                print("Error: No ID found for row", row)
                return False
                
            # Find the entry using ID instead of row
            entry_id = id_item.text()
            entry_data = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry_data:
                print(f"Error: Could not find entry data for ID {entry_id}")
                return False
            
            # Get the directory from the first filepath
            directory = os.path.dirname(entry_data['filepaths'][0])
            if not directory or not os.path.exists(directory):
                print(f"Error: Invalid directory for ID {entry_id}")
                return False
            
            # Save with default name if no JACKET field exists
            jacket_filename = 'SM_MDE_Jacket.png'
            output_path = os.path.join(directory, jacket_filename)
            image.save(output_path)
            
            # Update metadata in all associated files
            for filepath in entry_data['filepaths']:
                content, encoding = MetadataUtil.read_file_with_encoding(filepath)
                if not content:
                    continue
                
                jacket_line_exists = False
                
                # Check if JACKET field exists
                for i, line in enumerate(content):
                    if line.startswith('#JACKET:'):
                        content[i] = f'#JACKET:{jacket_filename};\n'
                        jacket_line_exists = True
                        break
                
                # If JACKET doesn't exist, add it after TITLE
                if not jacket_line_exists:
                    for i, line in enumerate(content):
                        if line.startswith('#TITLE:'):
                            content.insert(i + 1, f'#JACKET:{jacket_filename};\n')
                            break
                
                # Write back to file
                with open(filepath, 'w', encoding=encoding) as file:
                    file.writelines(content)
            
            print(f"Successfully saved artwork to {output_path}")
            QMessageBox.information(self, "Success", "Artwork Updated")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save artwork: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            QMessageBox.warning(self, "Error", error_msg)
            return False

    def create_action_buttons(self, row, filepaths, music_file='', entry_id=None):
        """Create action buttons for a table row"""
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(2, 2, 2, 2)
        action_layout.setSpacing(5)
        
        # Open folder button
        folder_btn = QToolButton()
        folder_btn.setText("...")
        folder_btn.setMinimumWidth(30)
        folder_btn.clicked.connect(
            lambda: self.open_file_location(os.path.dirname(filepaths[0]))
        )
        action_layout.addWidget(folder_btn)
        
        # Play button
        play_btn = QToolButton()
        play_btn.setText("▶")
        play_btn.setMinimumWidth(30)
        if music_file:
            # Create the full music path
            music_path = os.path.join(os.path.dirname(filepaths[0]), music_file)
            
            # Simple lambda without default arguments
            play_btn.clicked.connect(
                lambda checked, mp=music_path, pb=play_btn, eid=entry_id: 
                self.play_audio(mp, pb, eid)
            )
        else:
            play_btn.setEnabled(False)
            play_btn.setToolTip("No audio file found")
        action_layout.addWidget(play_btn)
        
        # Edit button
        edit_btn = QToolButton()
        edit_btn.setText("✎")
        edit_btn.setMinimumWidth(30)
        edit_btn.clicked.connect(lambda: self.edit_metadata(filepaths))  # Changed to edit_metadata
        action_layout.addWidget(edit_btn)
        
        return action_widget

    def cleanup_audio(self):
        """Clean up audio resources"""
        if self.current_playing:
            try:
                pygame.mixer.music.stop()
                self.current_playing.setText("▶")
                self.current_playing = None
            except Exception as e:
                print(f"Error cleaning up audio: {str(e)}")

    def closeEvent(self, event):
        """Handle application closure"""
        try:
            # Stop any playing music
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            
            # Restore original stdout/stderr if console was used
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            
            # Accept the close event
            event.accept()
            
        except Exception as e:
            print(f"Error during closure: {str(e)}")
            event.accept()  # Close anyway even if there's an error

    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            if pygame.get_init():
                pygame.quit()
        except:
            pass

    def check_remaining_suggestions(self, row, current_col):
        """Check if there are any remaining suggestion buttons in the row"""
        has_suggestions = False
        for col in [4, 6, 7]:  # title, artist, genre columns
            if col != current_col:
                widget = self.table.cellWidget(row, col)
                if widget and isinstance(widget, QWidget):
                    has_suggestions = True
                    break
        
        if not has_suggestions:
            self.table.setRowHeight(row, self.table.verticalHeader().defaultSectionSize())

    def compare_artwork(self, row, shazam_url, song_directory):
        """Compare local artwork with Shazam artwork"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
                
            # Find the entry using ID
            entry_id = id_item.text()
            entry_data = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry_data:
                return

            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Compare Artwork")
            dialog.setMinimumWidth(500)
            layout = QVBoxLayout(dialog)
            
            # Create image comparison layout
            images_layout = QHBoxLayout()
            layout.addLayout(images_layout)
            
            # Left side (Current)
            left_frame = QFrame()
            left_layout = QVBoxLayout(left_frame)
            left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Get JACKET value from metadata
            metadata = MetadataUtil.read_metadata(entry_data['filepaths'][0])
            jacket_ref = metadata.get('JACKET', '').strip()
            local_image = None
            current_jacket_ref = None

            if jacket_ref:
                # Try to find any file containing the jacket name (without extension)
                search_term = os.path.splitext(jacket_ref)[0].lower()
                for file in os.listdir(song_directory):
                    if search_term in file.lower() and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        try:
                            local_image = Image.open(os.path.join(song_directory, file))
                            current_jacket_ref = file
                            break
                        except Exception as e:
                            print(f"Failed to load file containing {search_term}: {str(e)}")

            # If no image found from JACKET reference, look for any file with "jacket" in the name
            if not local_image:
                for file in os.listdir(song_directory):
                    if 'jacket' in file.lower() and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        try:
                            local_image = Image.open(os.path.join(song_directory, file))
                            current_jacket_ref = file
                            break
                        except Exception as e:
                            print(f"Failed to load jacket file: {str(e)}")
            
            # Display current artwork if found
            if local_image:
                local_label = QLabel()
                local_pixmap = ImageQt.toqpixmap(local_image.resize((200, 200)))
                local_label.setPixmap(local_pixmap)
                left_layout.addWidget(local_label)
                left_layout.addWidget(QLabel(f"Current: {current_jacket_ref}"))
                left_layout.addWidget(QLabel(f"Size: {local_image.size[0]}x{local_image.size[1]}"))
            else:
                left_layout.addWidget(QLabel("No matching jacket artwork found"))
                if jacket_ref:
                    left_layout.addWidget(QLabel(f"(Looking for: {jacket_ref})"))
            
            images_layout.addWidget(left_frame)
            
            # Right side (Shazam)
            right_frame = QFrame()
            right_layout = QVBoxLayout(right_frame)
            right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Download and display Shazam artwork
            try:
                response = requests.get(shazam_url)
                shazam_image = Image.open(BytesIO(response.content))
                
                shazam_label = QLabel()
                shazam_pixmap = ImageQt.toqpixmap(shazam_image.resize((200, 200)))
                shazam_label.setPixmap(shazam_pixmap)
                right_layout.addWidget(shazam_label)
                right_layout.addWidget(QLabel("Shazam Artwork"))
                right_layout.addWidget(QLabel(f"Size: {shazam_image.size[0]}x{shazam_image.size[1]}"))
                
                images_layout.addWidget(right_frame)
                
                # Add buttons
                button_layout = QHBoxLayout()
                layout.addLayout(button_layout)
                
                keep_btn = QPushButton("Keep Current")
                keep_btn.clicked.connect(dialog.reject)
                button_layout.addWidget(keep_btn)
                
                update_btn = QPushButton("Update Artwork")
                update_btn.clicked.connect(lambda: self.handle_artwork_update(dialog, row, shazam_image))
                button_layout.addWidget(update_btn)
                
                dialog.exec()
                
            except Exception as e:
                error_msg = f"Error downloading Shazam artwork: {str(e)}"
                print(error_msg)
                traceback.print_exc()
                QMessageBox.warning(self, "Error", error_msg)
                
        except Exception as e:
            error_msg = f"Error comparing artwork: {str(e)}"
            print(error_msg)
            traceback.print_exc()

    def handle_artwork_update(self, dialog, row, image):
        """Handle artwork update and dialog closing"""
        if self.save_artwork(row, image):
            dialog.accept()  # Close the dialog only if save was successful

    def check_playback(self):
        """Check if playback has ended and reset button state"""
        if self.current_playing and not pygame.mixer.music.get_busy():
            self.current_playing.setText("▶")
            self.current_playing = None

    def edit_metadata(self, filepaths):
        """Open the metadata editor dialog"""
        try:
            dialog = MetadataEditorDialog(self, filepaths)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Refresh the display after changes
                self.refresh_table()
        except Exception as e:
            print(f"Error opening metadata editor: {str(e)}")
            traceback.print_exc()

    def update_row_status(self, row, filepaths):
        """Update the status and commit columns for a row"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
                
            # Find the entry in backend data using ID
            entry_id = id_item.text()
            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry:
                return

            # Check if any values have changed
            has_changes = False
            for col, field in [
                (self.COL_TITLE, 'title'),
                (self.COL_SUBTITLE, 'subtitle'),
                (self.COL_ARTIST, 'artist'),
                (self.COL_GENRE, 'genre')
            ]:
                item = self.table.item(row, col)
                if item and item.text() != entry['original_values'][field]:
                    has_changes = True
                    break

            # Update status column
            if has_changes:
                status_label = QLabel("⚠")
                status_label.setStyleSheet("color: #FF8C00;")  # Dark orange
                status_label.setToolTip("Unsaved changes")
                
                status_container = QWidget()
                status_layout = QHBoxLayout(status_container)
                status_layout.setContentsMargins(0, 0, 0, 0)
                status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                status_layout.addWidget(status_label)
                
                self.table.setCellWidget(row, 8, status_container)

                # Create commit button
                commit_container = QWidget()
                commit_layout = QHBoxLayout(commit_container)
                commit_layout.setContentsMargins(2, 2, 2, 2)
                
                commit_btn = QPushButton("Commit")
                commit_btn.clicked.connect(lambda: self.commit_changes(row, filepaths))
                commit_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4a90e2;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 8px;
                        min-width: 60px;
                    }
                    QPushButton:hover {
                        background-color: #357abd;
                    }
                """)
                commit_layout.addWidget(commit_btn)
                self.table.setCellWidget(row, 9, commit_container)
            else:
                # Clear status and commit columns if no changes
                self.table.removeCellWidget(row, 8)
                self.table.removeCellWidget(row, 9)
                self.table.setItem(row, 8, QTableWidgetItem(""))
                self.table.setItem(row, 9, QTableWidgetItem(""))

            # Update commit all button
            self.update_commit_all_button()

        except Exception as e:
            print(f"Error updating row status: {str(e)}")
            traceback.print_exc()

    def clear_search(self):
        """Clear the search box and reset display"""
        self.search_box.clear()
        self.clear_button.setVisible(False)
        
        # Show all rows
        total_count = len(self.file_entries)
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)
            
        # Update display count to show all entries
        self.update_display_count(total_count, total_count)

    def on_cell_changed(self, row, col):
        """Handle cell value changes"""
        try:
            # Only process editable columns
            if col not in [self.COL_TITLE, self.COL_SUBTITLE, self.COL_ARTIST, self.COL_GENRE]:
                return
                
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
                
            # Find the entry in backend data using ID
            entry_id = id_item.text()
            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry:
                return
                
            # Map column to field name
            col_to_field = {
                self.COL_TITLE: 'title',
                self.COL_SUBTITLE: 'subtitle',
                self.COL_ARTIST: 'artist',
                self.COL_GENRE: 'genre'
            }
            
            field = col_to_field.get(col)
            if not field:
                return
                
            # Get the new value
            item = self.table.item(row, col)
            if not item:
                return
                
            # Check if value has changed from original
            if item.text() != entry['original_values'][field]:
                # Update status and commit columns
                self.update_row_status(row, entry['filepaths'])
                
        except Exception as e:
            print(f"Error in on_cell_changed: {str(e)}")
            traceback.print_exc()

    def update_display_count(self, shown_count, total_count):
        """Update the display count indicator"""
        # Get unique pack names by taking the basename of each directory
        unique_packs = {os.path.basename(directory) for directory in self.selected_directories}
        pack_count = len(unique_packs)
        
        self.display_count_label.setText(
            f"Displaying {shown_count} of {total_count} songs from {pack_count} packs"
        )
        # Always show the frame, even when counts are equal
        self.display_count_frame.show()

    def reject_shazam_value(self, row, field, original_value):
        """Reject a Shazam suggestion and restore the original value"""
        try:
            col_map = {
                'title': 4,
                'artist': 6,
                'genre': 7
            }
            
            col_index = col_map.get(field)
            if col_index is None:
                return

            # Create new item with original value
            item = QTableWidgetItem(original_value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            
            # Remove suggestion and restore original value
            self.table.removeCellWidget(row, col_index)
            self.table.setItem(row, col_index, item)
            
            # Reset row height if no more suggestions
            has_suggestions = False
            for col in [4, 6, 7]:  # title, artist, genre columns
                if isinstance(self.table.cellWidget(row, col), QWidget):
                    has_suggestions = True
                    break
            if not has_suggestions:
                self.table.setRowHeight(row, self.table.verticalHeader().defaultSectionSize())
            
        except Exception as e:
            print(f"Error rejecting Shazam value: {str(e)}")
            traceback.print_exc()

    def show_settings_dialog(self):
        """Show the settings dialog"""
        dialog = SettingsDialog(self)
        dialog.exec()

    def export_to_csv(self):
        """Export visible table data to CSV"""
        try:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save CSV File",
                "",
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if file_name:
                with open(file_name, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    
                    # Write headers including all possible metadata fields
                    headers = [
                        'Type',
                        'Pack',
                        'Title',
                        'Subtitle',
                        'Artist',
                        'Genre',
                        'Credits',
                        'Music File',
                        'Banner',
                        'Background',
                        'CDTitle',
                        'Sample Start',
                        'Sample Length',
                        'Display BPM',
                        'Selectable'
                    ]
                    writer.writerow(headers)
                    
                    # Write visible rows
                    for row in range(self.table.rowCount()):
                        if not self.table.isRowHidden(row):
                            # Get the ID from the current row
                            id_item = self.table.item(row, self.COL_ID)
                            if not id_item:
                                continue
                            
                            # Find the entry using ID
                            entry_id = id_item.text()
                            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
                            
                            if entry:
                                # Get file type from table
                                type_item = self.table.item(row, 2)
                                file_type = type_item.text() if type_item else ''
                                
                                # Read metadata from primary file
                                metadata = MetadataUtil.read_metadata(entry['filepaths'][0])
                                
                                # Format credits properly - remove empty credits and handle single credit case
                                credits = {credit for credit in metadata.get('CREDITS', set()) 
                                         if credit and not credit.isspace()}
                                credits_str = '; '.join(sorted(credits)) if len(credits) > 1 else next(iter(credits), '')
                                
                                row_data = [
                                    file_type,
                                    os.path.basename(os.path.dirname(os.path.dirname(entry['filepaths'][0]))),
                                    metadata.get('TITLE', '').strip(),
                                    metadata.get('SUBTITLE', '').strip(),
                                    metadata.get('ARTIST', '').strip(),
                                    metadata.get('GENRE', '').strip(),
                                    credits_str,
                                    metadata.get('MUSIC', '').strip(),
                                    metadata.get('BANNER', '').strip(),
                                    metadata.get('BACKGROUND', '').strip(),
                                    metadata.get('CDTITLE', '').strip(),
                                    metadata.get('SAMPLESTART', '').strip(),
                                    metadata.get('SAMPLELENGTH', '').strip(),
                                    metadata.get('DISPLAYBPM', '').strip(),
                                    metadata.get('SELECTABLE', '').strip()
                                ]
                                writer.writerow(row_data)
                
                QMessageBox.information(self, "Success", "Data exported successfully!")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to export data: {str(e)}")
            traceback.print_exc()

    def find_row_by_id(self, entry_id):
        """Find the current row number for a given entry ID"""
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, self.COL_ID)
            if id_item and id_item.text() == entry_id:
                return row
        print(f"Debug: Could not find row for ID {entry_id}")
        return -1

    def verify_row_id_mapping(self):
        """Debug helper to print current row-ID mappings"""
        print("\nCurrent Row-ID Mappings:")
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, self.COL_ID)
            if id_item:
                print(f"Row {row}: ID {id_item.text()}")

class PackSelectorDialog(QDialog):
    def __init__(self, parent, directories):
        super().__init__(parent)
        self.setWindowTitle("Select Packs")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        # Convert directories to list and store as instance variable
        self.directories = sorted(list(directories), key=str.lower)
        self.selected_packs = set()
        self.buttons = {}
        self.is_accepting = False
        
        # Create the UI after initializing variables
        self.setup_ui()
        
    def setup_ui(self):
        try:
            layout = QVBoxLayout(self)
            
            # Warning label
            warning_text = ("Warning: Selecting all packs may cause performance issues.\n"
                          "Consider working with a handful of packs at a time for better responsiveness.")
            warning_label = QLabel(warning_text)
            warning_label.setStyleSheet("color: blue; font-weight: bold;")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)
            
            # Create scroll area
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_widget = QWidget()
            scroll_layout = QGridLayout(scroll_widget)
            scroll_layout.setSpacing(4)
            

            button_width = 240 
            
            # Create pack buttons with proper reference handling
            row = col = 0
            for pack in self.directories:
                btn = QPushButton(str(pack))  # Ensure string conversion
                btn.setCheckable(True)
                btn.setFixedWidth(button_width)
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                
                # Set the stylesheet for the button
                btn.setStyleSheet("""
                    QPushButton:checked {
                        background-color: lightgreen;
                    }
                """)
                
                # Store button reference and connect with lambda
                self.buttons[pack] = btn
                btn.clicked.connect(lambda checked, p=pack: self.toggle_pack(p))
                
                btn.setToolTip(str(pack))
                scroll_layout.addWidget(btn, row, col)
                
                col += 1
                if col >= 3:
                    col = 0
                    row += 1
            
            # Add stretch to push buttons to top
            scroll_layout.setRowStretch(row + 1, 1)
            scroll_layout.setColumnStretch(3, 1)
            
            scroll_area.setWidget(scroll_widget)
            layout.addWidget(scroll_area)
            
            # Button frame
            button_frame = QFrame()
            button_layout = QHBoxLayout(button_frame)
            
            select_all_btn = QPushButton("Select All")
            select_all_btn.clicked.connect(self.select_all_packs)
            button_layout.addWidget(select_all_btn)
            
            deselect_all_btn = QPushButton("Deselect All")
            deselect_all_btn.clicked.connect(self.deselect_all_packs)
            button_layout.addWidget(deselect_all_btn)
            
            button_layout.addStretch()
            
            ok_button = QPushButton("Let's Go!")
            ok_button.clicked.connect(self.accept)
            button_layout.addWidget(ok_button)
            
            cancel_button = QPushButton("Cancel")
            cancel_button.clicked.connect(self.reject)
            button_layout.addWidget(cancel_button)
            
            layout.addWidget(button_frame)
            
        except Exception as e:
            print(f"Error in setup_ui: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def toggle_pack(self, pack):
        """Toggle pack selection state with error handling"""
        try:
            if pack in self.selected_packs:
                self.selected_packs.remove(pack)
                if pack in self.buttons:
                    self.buttons[pack].setChecked(False)
            else:
                self.selected_packs.add(pack)
                if pack in self.buttons:
                    self.buttons[pack].setChecked(True)
        except Exception as e:
            print(f"Error toggling pack {pack}: {str(e)}")
            traceback.print_exc()

    def select_all_packs(self):
        """Select all packs with error handling"""
        try:
            self.selected_packs = set(self.directories)
            for btn in self.buttons.values():
                btn.setChecked(True)
        except Exception as e:
            print(f"Error selecting all packs: {str(e)}")
            traceback.print_exc()

    def deselect_all_packs(self):
        """Deselect all packs with error handling"""
        try:
            self.selected_packs.clear()
            for btn in self.buttons.values():
                btn.setChecked(False)
        except Exception as e:
            print(f"Error deselecting all packs: {str(e)}")
            traceback.print_exc()

    def accept(self):
        """Override accept with proper cleanup"""
        if self.is_accepting:
            return
            
        try:
            self.is_accepting = True
            
            if not self.selected_packs:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select at least one pack to continue."
                )
                self.is_accepting = False
                return
            
            # Safely disconnect signals
            for btn in self.buttons.values():
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                    
            self.buttons.clear()
            super().accept()
            
        except Exception as e:
            print(f"Error in accept: {str(e)}")
            traceback.print_exc()
        finally:
            self.is_accepting = False

    def reject(self):
        """Override reject with proper cleanup"""
        try:
            # Safely disconnect signals
            for btn in self.buttons.values():
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                    
            self.buttons.clear()
            super().reject()
            
        except Exception as e:
            print(f"Error in reject: {str(e)}")
            traceback.print_exc()

class CreditSelectorDialog(QDialog):
    def __init__(self, parent, credits):
        super().__init__(parent)
        self.setWindowTitle("Select Credits")
        self.setMinimumSize(800, 600)
        
        self.credits = credits
        self.selected_credits = set()
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info label
        info_text = ("Select credits to filter songs by their creators.\n"
                    "You can select multiple credits to see all songs by those creators.")
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #666; font-weight: bold;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Button frame for Select All/Deselect All
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        select_all = QPushButton("Select All")
        select_all.clicked.connect(self.select_all_credits)
        button_layout.addWidget(select_all)
        
        deselect_all = QPushButton("Deselect All")
        deselect_all.clicked.connect(self.deselect_all_credits)
        button_layout.addWidget(deselect_all)
        
        button_layout.addStretch()
        layout.addWidget(button_frame)
        
        # Create scroll area for credit buttons
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        scroll_layout.setSpacing(4)
        
        # Create credit buttons in a grid
        row = 0
        col = 0
        for credit in sorted(self.credits, key=str.lower):
            btn = QPushButton(credit)
            btn.setCheckable(True)
            btn.setFixedWidth(240)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            
            # Set the stylesheet for the button
            btn.setStyleSheet("""
                QPushButton:checked {
                    background-color: lightgreen;
                }
            """)
            
            btn.clicked.connect(lambda checked, c=credit: self.toggle_credit(c))
            btn.setToolTip(credit)
            scroll_layout.addWidget(btn, row, col)
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        # Add stretch to push buttons to top
        scroll_layout.setRowStretch(row + 1, 1)
        scroll_layout.setColumnStretch(3, 1)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Dialog buttons
        dialog_buttons = QFrame()
        dialog_layout = QHBoxLayout(dialog_buttons)
        dialog_layout.addStretch()
        
        ok_button = QPushButton("Filter by Credits")
        ok_button.clicked.connect(self.accept)
        dialog_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        dialog_layout.addWidget(cancel_button)
        
        layout.addWidget(dialog_buttons)
        
    def select_all_credits(self):
        self.selected_credits = set(self.credits)
        for button in self.findChildren(QPushButton):
            if button.text() in self.credits:
                button.setChecked(True)
                
    def deselect_all_credits(self):
        self.selected_credits.clear()
        for button in self.findChildren(QPushButton):
            if button.text() in self.credits:
                button.setChecked(False)

    def toggle_credit(self, credit):
        if credit in self.selected_credits:
            self.selected_credits.remove(credit)
        else:
            self.selected_credits.add(credit)
            
class ArtworkPreviewDialog(QDialog):
    def __init__(self, parent, current_img_path, new_artwork_url, filepaths):
        super().__init__(parent)
        self.setWindowTitle("Album Artwork Preview")
        self.setFixedSize(800, 600)
        
        self.current_img_path = current_img_path
        self.new_artwork_url = new_artwork_url
        self.filepaths = filepaths
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create image preview area
        preview_frame = QFrame()
        preview_layout = QHBoxLayout(preview_frame)
        
        # Current artwork
        current_frame = QFrame()
        current_layout = QVBoxLayout(current_frame)
        current_label = QLabel("Current Artwork")
        current_layout.addWidget(current_label)
        
        self.current_image_label = QLabel()
        if os.path.exists(self.current_img_path):
            pixmap = QPixmap(self.current_img_path)
            pixmap = pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio)
            self.current_image_label.setPixmap(pixmap)
            current_layout.addWidget(QLabel(f"Dimensions: {pixmap.width()}x{pixmap.height()}"))
        else:
            self.current_image_label.setText("No current artwork")
        current_layout.addWidget(self.current_image_label)
        
        preview_layout.addWidget(current_frame)
        
        # New artwork
        new_frame = QFrame()
        new_layout = QVBoxLayout(new_frame)
        new_label = QLabel("New Artwork")
        new_layout.addWidget(new_label)
        
        self.new_image_label = QLabel()
        try:
            response = requests.get(self.new_artwork_url)
            image = Image.open(BytesIO(response.content))
            qimage = ImageQt.ImageQt(image)
            pixmap = QPixmap.fromImage(qimage)
            pixmap = pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio)
            self.new_image_label.setPixmap(pixmap)
            new_layout.addWidget(QLabel(f"Dimensions: {pixmap.width()}x{pixmap.height()}"))
            self.new_image = image
        except Exception as e:
            self.new_image_label.setText(f"Failed to load new artwork: {str(e)}")
            self.new_image = None
        new_layout.addWidget(self.new_image_label)
        
        preview_layout.addWidget(new_frame)
        layout.addWidget(preview_frame)
        
        # Buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        keep_button = QPushButton("Keep Current")
        keep_button.clicked.connect(self.reject)
        button_layout.addWidget(keep_button)
        
        update_button = QPushButton("Update Artwork")
        update_button.clicked.connect(self.update_artwork)
        button_layout.addWidget(update_button)
        
        layout.addWidget(button_frame)
        
    def update_artwork(self):
        if not self.new_image:
            return
        
        try:
            # Save new artwork
            self.new_image.save(self.current_img_path)
            
            # Update metadata in files
            for filepath in self.filepaths:
                content, encoding = MetadataUtil.read_file_with_encoding(filepath)
                if not content:
                    continue
                
                jacket_name = os.path.basename(self.current_img_path)
                jacket_line_exists = False
                
                for i, line in enumerate(content):
                    if line.startswith('#JACKET:'):
                        content[i] = f'#JACKET:{jacket_name};\n'
                        jacket_line_exists = True
                        break
                
                if not jacket_line_exists:
                    # Find #TITLE: line and add JACKET after it
                    for i, line in enumerate(content):
                        if line.startswith('#TITLE:'):
                            content.insert(i + 1, f'#JACKET:{jacket_name};\n')
                            break
                
                with open(filepath, 'w', encoding=encoding) as file:
                    file.writelines(content)
            
            QMessageBox.information(self, "Success", "Artwork updated successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update artwork: {str(e)}")
            
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("StepMania Metadata Editor Help")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Help content sections
        sections = {
            "Basic Features": [
                "• Add Directory: Select folders containing StepMania song files (.sm, .ssc)",
                "• Clear All: Remove all loaded songs from the editor",
                "• Bulk Edit: Select multiple songs to edit their metadata simultaneously",
                "• Sort columns by clicking on column headers"
            ],
            "Actions Column": [
                "• ... (three dots): Open song folder in file explorer",
                "   ▶ (play): Preview song audio (if available)",
                "✎ (pencil): Open full metadata editor for advanced fields"
            ],
            "Metadata Editing": [
                "• Edit Title, Subtitle, Artist, and Genre directly in the main view",
                "• Successfully saved changes appear in light green commited button",
                "• Click 'Commit?' to save changes (appears when modifications are made)",
                "• Use 'Commit All' to save all pending changes at once"
            ],
            "Shazam Integration": [
                "• Toggle Shazam Mode to identify songs automatically",
                "• Play a song while Shazam is active to get metadata suggestions",
                "• Click on suggested values to apply them",
                "• Preview and update album artwork when available"
            ],
            "Bulk Editing": [
                "• Enable Bulk Edit mode to show checkboxes",
                "• Select multiple songs using checkboxes",
                "• Enter new values in the bulk edit fields",
                "• Click 'Apply to Selected' to update all chosen songs"
            ],
            "Tips": [
                "• The editor supports multiple file encodings (UTF-8, Shift-JIS, etc.)",
                "• Combined view for songs with both .sm and .ssc files",
                "• Mouse wheel scrolling supported in all views",
                "• Internet connection required for Shazam features"
            ],
            "File Handling": [
                "• SSC files take precedence over SM files with the same name",
                "• When both SM and SSC exist, SSC metadata is used but both files are updated",
                "• Files are matched by name (case-insensitive)",
                "• The Type column shows 'sm+ssc' when both file types exist"
            ]
        }
        
        for section, items in sections.items():
            # Section header
            header = QLabel(section)
            header.setStyleSheet("font-weight: bold; font-size: 12pt;")
            scroll_layout.addWidget(header)
            
            # Section content
            content = QLabel("\n".join(items))
            content.setWordWrap(True)
            content.setContentsMargins(20, 0, 0, 0)
            scroll_layout.addWidget(content)
            
            # Add spacing between sections
            scroll_layout.addSpacing(10)
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

class MetadataEditorDialog(QDialog):
    def __init__(self, parent, filepaths):
        super().__init__(parent)
        self.setWindowTitle("Full Metadata Editor")
        self.setMinimumSize(600, 800)
        
        self.filepaths = filepaths
        self.entries = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        
        # Read metadata from first file
        metadata = MetadataUtil.read_metadata(self.filepaths[0])
        
        # Create entry fields for each metadata item
        row = 0
        for key, value in metadata.items():
            if key != 'CREDITS':  # Skip credits set
                label = QLabel(key)
                scroll_layout.addWidget(label, row, 0)
                
                line_edit = QLineEdit(value)
                scroll_layout.addWidget(line_edit, row, 1)
                self.entries[key] = {'widget': line_edit, 'original': value}
                
                row += 1
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Button frame
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        commit_button = QPushButton("Commit Changes")
        commit_button.clicked.connect(self.commit_changes)
        button_layout.addWidget(commit_button)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addWidget(button_frame)
        
    def commit_changes(self):
        changes = {}
        for key, entry in self.entries.items():
            new_value = entry['widget'].text()
            if new_value != entry['original']:
                changes[key] = new_value
        
        if changes:
            success = True
            for filepath in self.filepaths:
                if not MetadataUtil.write_metadata(filepath, changes):
                    success = False
                    break
            
            if success:
                QMessageBox.information(self, "Success", "Changes saved successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to save changes to one or more files.")
        else:
            self.reject()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Settings")
        self.setMinimumWidth(300)
        # Move console_window to the parent (MetadataEditor)
        if not hasattr(self.parent, 'console_window'):
            self.parent.console_window = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Export section
        export_frame = QFrame()
        export_layout = QHBoxLayout(export_frame)
        
        export_btn = QPushButton("Export to CSV")
        export_btn.setToolTip("Export visible table data to CSV file")
        export_btn.clicked.connect(self.parent.export_to_csv)
        export_layout.addWidget(export_btn)
        
        layout.addWidget(export_frame)
        
        # Console section
        console_btn = QPushButton("Open Console")
        console_btn.clicked.connect(self.show_console)
        layout.addWidget(console_btn)
        
        # Add a stretch to push everything up
        layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
    def show_console(self):
        if not self.parent.console_window:
            self.parent.console_window = ConsoleWindow(self.parent)  # Parent is main window
            # Redirect stdout to our console window
            sys.stdout = self.parent.console_window
            sys.stderr = self.parent.console_window
        self.parent.console_window.show()

class ConsoleWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Console Output")
        self.setMinimumSize(600, 400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create text display
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: Consolas, monospace;
                padding: 8px;
            }
        """)
        layout.addWidget(self.console_output)
        
        # Add clear and close buttons
        button_layout = QHBoxLayout()
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.console_output.clear)
        button_layout.addWidget(clear_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.hide)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def write(self, text):
        self.console_output.append(text.rstrip())
        
    def flush(self):
        pass

def main():
    # Enable high DPI scaling
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Set default font
    font = app.font()
    font.setPointSize(9)
    app.setFont(font)
    
    # Create and show main window
    window = MetadataEditor()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()