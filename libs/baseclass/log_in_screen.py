import ssl
import urllib
from http import cookiejar
# from threading import Thread, local
from urllib.error import HTTPError

from bs4 import BeautifulSoup
from kivy.app import App
# from kivy.metrics import dp
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivymd.toast import toast
from kivymd.uix.chip import MDChip
# from kivymd.uix.dialog import MDDialog
# from kivymd.uix.spinner import MDSpinner
from kivymd.uix.textfield import MDTextField
import os
import json

ssl._create_default_https_context = ssl._create_unverified_context

class PasswordField(MDTextField):
    pass


class UserChip(MDChip):
    pass


class ErrorBox(BoxLayout):
    pass


class LogInScreen(Screen):
    dialog = None
    response = 403
    password = StringProperty()
    login_details = ObjectProperty()

    # def __init__(self, **kw):
    #     super().__init__(**kw)
        # if os.path.isfile(f"{os.environ['BOULANGERIE_ROOT']}/.logs.json"):
        #     with open(
        #         f"{os.environ['BOULANGERIE_ROOT']}/.logs.json", 'r'
        #     ) as f:
        #         self.login_details = json.load(f)
        # else:
        #     _dict = {}
        #     with open(
        #         f"{os.environ['BOULANGERIE_ROOT']}/.logs.json", 'w'
        #     ) as f:
        #         json.dump(_dict, f)

    # def on_enter(self, *args):
    #     self.ids.pwsd.text = ""

    def authenticate_user(self, username, password):
        BASE_URL = "https://be.kanangila.com/authentication/login/"

        cj = cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        urllib.request.install_opener(opener)

        url = urllib.request.urlopen(BASE_URL)
        html = url.read()

        soup = BeautifulSoup(html, features="html.parser")
        csrf_input = soup.find(attrs = dict(name = 'csrfmiddlewaretoken'))
        csrf_token = csrf_input['value']

        params = urllib.parse.urlencode(dict(username=username, password=password, csrfmiddlewaretoken = csrf_token)).encode("utf-8")

        try:
            url = urllib.request.urlopen(BASE_URL, params)
            url = str(url.read())

            if "Welcome" in url:
                return 200
            else:
                return 403
        except HTTPError:
            return 403

    def update_session_info(self, instance):
        app = App.get_running_app()

        if instance.selected_chip_color == app.custom_focus_color:
            app.session_info = {"user": instance.text}

    def dismiss_dialog(self):
        if self.dialog:
            self.dialog.dismiss()

    def _retrieve_session_info(self):
        """update session_info on main app. The keys are: 
            ['user','user_id', 'is_superuser', 
            'sales_site_id', 'sales_site']"""

        app = App.get_running_app()

        if not self.password:
            toast("Veuillez saisir votre mot de passe")
            return

        if not app.session_info['user']:
            toast("Selectionez votre nom")
            return
        else: 
            app.session_info = app.orm.retrieve_session_info(
                user=app.session_info['user']
            )[0]

        def login_user():
            # self.dialog = MDDialog(
            #     title="Veuillez patienter!",
            #     type="custom",
            #     content_cls=MDSpinner(
            #         size_hint=(None, None),
            #         size=(dp(45), dp(45)),
            #         pos_hint={"center_x": .5, "center_y": .5},
            #         active=True,
            #         color=app.custom_normal_color
            #     ),
            #     auto_dismiss=False
            # )
            # self.dialog.open()

            local_user = app.orm.execute_query(
                querry_string=(
                    "SELECT user FROM users" +
                    f" WHERE password='{self.password}'" +
                    f" AND user='{app.session_info['username']}'"
                    ),
                verbose=True,
                cursor="local"
                )

            if local_user:
                self.response = 200
            else:
                self.response =  self.authenticate_user(
                    username=app.session_info['username'],
                    password=self.password
                )

                if self.response == 200:
                    # self.login_details[app.session_info['username']] = self.password
                    # with open(f"{os.environ['BOULANGERIE_ROOT']}/.logs.json", 'w') as f:
                    #     json.dump(self.login_details, f)

                    qs = f"""
                        INSERT INTO users(
                                        user, 
                                        password
                                            ) 
                        VALUES (
                                '{app.session_info['username']}', 
                                '{self.password}'
                                )
                """
                    app.orm.execute_query(querry_string=qs, cursor="local", commit=True)

            # try:
            #     if self.login_details[app.session_info['username']] == self.password:
            #         self.response = 200
            #     else:
            #         self.response = 403
            # except KeyError:
            #     # Authenticate user remote
            #     self.response =  self.authenticate_user(
            #         username=app.session_info['username'],
            #         password=self.password
            #     )

            #     if self.response == 200:
            #         self.login_details[app.session_info['username']] = self.password
            #         with open(f"{os.environ['BOULANGERIE_ROOT']}/.logs.json", 'w') as f:
            #             json.dump(self.login_details, f)

            #         qs = f"""
            #             INSERT INTO users(
            #                             user, 
            #                             password
            #                                 ) 
            #             VALUES (
            #                     '{app.session_info['username']}', 
            #                     '{self.password}'
            #                     )
            #     """
            #         app.orm.execute_query(querry_string=qs, cursor="local", commit=True)

            app.session_info['sales_agents'] = app.orm.\
                retrieve_sales_agents(app.session_info['sales_site_id']
            )
            app.session_info['archived_sales_agents'] = app.orm.\
                retrieve_archived_agents(app.session_info['sales_site_id']
                )

            # self.dismiss_dialog()

        # Thread(target=login_user, daemon=True).start()

        login_user()

        if self.response == 200:
            self.parent.current = "home screen"
        else:
            toast("Le mot de passe saisit est incorrecte")
