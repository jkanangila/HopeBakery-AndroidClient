#####################
## SECTION IMPORTS ##
###########################################################################
import os
import sys
from logging import error
from pathlib import Path
from queue import Queue
from threading import Thread
from time import sleep
from kivy import app

from kivy.base import EventLoop
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import (BooleanProperty, ColorProperty, DictProperty,
                             ListProperty, NumericProperty, ObjectProperty,
                             StringProperty)
from kivy.utils import get_color_from_hex as gch
from kivymd.app import MDApp
from kivymd.uix.chip import MDChooseChip
from psycopg2.errors import OperationalError

from libs.baseclass.log_in_screen import ErrorBox, PasswordField, UserChip
from libs.modules.orm import MyORM
# !SECTION
###########################################################################


###################################
## SECTION ENVIRONMENT VARIABLES ##
###########################################################################
if getattr(sys, "frozen", False):
    os.environ["BOULANGERIE_ROOT"] = sys._MEIPASS
else:
    os.environ["BOULANGERIE_ROOT"] = str(Path(__file__).parent)

KV_DIR = f"{os.environ['BOULANGERIE_ROOT']}/libs/kv"

for kv_file in os.listdir(KV_DIR):
    with open(os.path.join(KV_DIR, kv_file), encoding="utf-8") as kv:
        Builder.load_string(kv.read())
# !SECTION
###########################################################################


#########################
## SECTION ROOT LAYOUT ##
###########################################################################
KV = """
#:import FadeTransition kivy.uix.screenmanager.FadeTransition
#:import LogInScreen libs.baseclass.log_in_screen.LogInScreen


ScreenManager:
    id: screen_manager_0
    transition: FadeTransition()

    LoadingScreen:
        name: "loading screen"

    LogInScreen:
        name: "login screen"

    BakeryHomeScreen:
        name: "home screen"
"""
# !SECTION
###########################################################################


#################################
## SECTION MAIN APP DEFINITION ##
###########################################################################
class BoulangerieApp(MDApp):
    ## SECTION APP PROPERTIES
    ## ANCHOR Appearance
    custom_normal_color = ColorProperty(gch("#B25026"))
    custom_focus_color = ColorProperty(gch("#2A1C10"))
    _heading_font_size = sp(12)
    text_color_2 = ColorProperty((1,1,1,1))

    ## ANCHOR Session
    orm = ObjectProperty()
    session_info = DictProperty()
    active_users = ListProperty()
    upload_queue = Queue(maxsize=0)
    worker_thread = None

    ## ANCHOR ToolbarProperties
    pg_bar_val = NumericProperty(0)
    pg_bar_col = ColorProperty((1, 1, 1, 0))
    pg_bar_text_val = StringProperty()
    spinner_state = BooleanProperty(False)

    check_connection = None
    login_box_added = None
    error_box_added = None
    login_disabled = BooleanProperty(True)

    cycle = NumericProperty()
    # !SECTION 

    ## ANCHOR __init__
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session_info['sales_agents'] = {}
        self.session_info['archived_sales_agents'] = {}
        self.session_info['user'] = ""

    ## ANCHOR build
    def build(self):
        return Builder.load_string(KV)

    ## ANCHOR add_login_widget
    def add_login_widget(self, *args):

        try:
            if self.check_connection:
                # Cancel the event check if there's an active internet con
                self.check_connection.cancel()
                self.check_connection = None
                # Call the function reset connection to create orm 
                self.reset_conn()

            # Querry list of active users from remote database
            self.active_users = self.orm.retrieve_staff_users()

            # Create chips containing user names
            choose_chip = MDChooseChip(spacing=dp(15))
            for user in self.active_users:
                choose_chip.add_widget(
                    UserChip(
                        text=user,
                        # icon=f"alpha-{user.lower()[0]}-circle-outline"
                        icon=""
                    )
                )

            # Clear login box layout in case it already had children
            self.root.get_screen(
                        "login screen"
                        ).ids._login_boxlayout.clear_widgets()

            # Add chips to login screen
            self.root.get_screen(
                        "login screen"
                        ).ids._login_boxlayout.add_widget(
                            choose_chip
                        )

            # Add password field
            self.root.get_screen(
                        "login screen"
                        ).ids._login_boxlayout.add_widget(
                            PasswordField()
                        )

            # Set login disabled to false in case of an exception
            self.login_disabled = False

            # Cancel clock event that adds widgets to login screen
            if self.login_box_added:
                self.login_box_added.cancel()
                self.login_box_added = None

        except:
            if not self.error_box_added:
                self.error_box_added = True

                self.login_disabled = True

                self.root.get_screen(
                        "login screen"
                        ).ids._login_boxlayout.clear_widgets()

                self.root.get_screen(
                            "login screen"
                            ).ids._login_boxlayout.add_widget(
                                ErrorBox()
                            )

    ## ANCHOR load_assets
    def load_assets(self, args):
        # TODO run this on a thread
        self.reset_conn()
        self.login_box_added = Clock.create_trigger(self.add_login_widget,
                                                    2, True)
        self.login_box_added()
        self.root.current = "login screen"
        if self.orm:
            Thread(target=self.orm.email_undelivered_orders(),
                   daemon=True).start()

    ## ANCHOR on_start
    def on_start(self):
        Clock.schedule_once(self.load_assets)
        EventLoop.window.bind(on_keyboard=self.back_key_action)

    ## ANCHOR back_key_action
    def back_key_action(self, window, key, *largs):
        # if escape key (back key on phones) is pressed
        if key == 27:
            return True

    ## ANCHOR reset_conn
    def reset_conn(self):
        
        try:
            msg = "Initialization de la connection avec le serveur..."
            self.pg_bar_text_val = msg
            self.spinner_state = True
            self.pg_bar_col = 1, 1, 1, .2
            self.pg_bar_val = 50

            self.orm = MyORM()

            self.pg_bar_text_val = "Connection avec serveur etablie"
            self.pg_bar_val = 100
            sleep(2)

            self.pg_bar_text_val = ""
            self.spinner_state = False
            self.pg_bar_col = 1, 1, 1, 0
            self.pg_bar_val = 0

            # Cancel the event attempting to connect to DB
            if self.check_connection:
                self.check_connection.cancel()
                self.check_connection = None

                self.pg_bar_text_val = ""

        except OperationalError:
            # Schedule DB conn check
            msg = ("[color=ff0000][b]Vous n'êtes pas connecté à Internet. " + 
                "Les données seront sauvegardées une fois la connexion " + 
                "rétablie [/b][/color]")
            self.pg_bar_text_val = msg

            # TODO display a different message if on the login screen

            if not self.check_connection:
                self.check_connection = Clock.schedule_interval(self.no_internet_message, 5)

    ## ANCHOR no_internet_message
    def no_internet_message(self, args):
        "Reset the connection if there is no active internet connection"
        if self.check_connection:
            self.reset_conn()
        else:
            self.check_connection = None

    ## ANCHOR refresh_session_info
    def refresh_session_info(self):
        self.reset_conn()

        if self.session_info['sales_site_id']:

            self.spinner_state = True

            self.session_info['sales_agents'] = self.orm.\
                retrieve_sales_agents(self.session_info['sales_site_id']
            )
            self.session_info['archived_sales_agents'] = self.orm.\
                retrieve_archived_agents(self.session_info['sales_site_id']
            )

            self.spinner_state = False
# !SECTION
###########################################################################


############################
## ANCHOR FONT DEFINITION ##
###########################################################################
LabelBase.register(
    name="Raleway",
    fn_bold="assets/fonts/Raleway-Heavy.ttf",
    fn_regular="assets/fonts/Raleway-Bold.ttf",
    fn_italic="assets/fonts/Raleway-ExtraLight.ttf")
###########################################################################


#########################
## ANCHOR RUN MAIN APP ##
###########################################################################
BoulangerieApp().run()
###########################################################################
