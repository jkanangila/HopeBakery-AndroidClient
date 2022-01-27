#####################
## SECTION Imports ##
##############################################################################
import webbrowser
from functools import partial
from threading import Thread

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.screenmanager import Screen

from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineListItem

try:
    from kivymd.uix.picker import MDDatePicker
except ModuleNotFoundError:
    from kivymd.uix.pickers import MDDatePicker
# !SECTION
##############################################################################


############################
## SECTION ClientListItem ##
##############################################################################
class ClientListItem(OneLineListItem):
    vendeur_id = StringProperty()
# !SECTION
##############################################################################


############################
## SECTION CustomerScreen ##
##############################################################################
class CustomerScreen(Screen):
    # ANCHOR Properties
    sales_agent_list_set = BooleanProperty(False)
    sort_order = StringProperty("Clients Actif")
    data = ListProperty()
    dialog = None

    # ANCHOR on_enter
    def on_enter(self):
        self.set_customers_list()
        self.sales_agent_list_set = True

    ## ANCHOR on_save
    def on_save(self, instance, value, date_range):
        """
        Save button pressed on datepicker. Action: Set text of 
        date text input field as the selected date
        """
        self.ids.search_field.text = str(value)

    ## ANCHOR on_cancel
    def on_cancel(self, instance, value):
        "Cancel button pressed on date picker"
        pass

    ## ANCHOR show_date_picker
    def show_date_picker(self):
        "Display date picker when calendar icon is pressed on jetton screen"
        app = App.get_running_app()
        date_dialog = MDDatePicker(
            primary_color=app.custom_normal_color,
            selector_color=app.custom_normal_color,
            text_current_color=app.custom_normal_color,
            text_button_color=app.custom_normal_color,
            input_field_text_color=app.custom_normal_color
        )
        date_dialog.bind(on_save=self.on_save, on_cancel=self.on_cancel)
        date_dialog.open()

    # ANCHOR add_customer
    def add_customer(self, name, id=""):
            self.data.append(
                {
                "viewclass": "ClientListItem",
                "text": name,
                "vendeur_id":id,
                "on_release":partial(self.open_url, id)
                }
            )

    # ANCHOR set_customers_list
    def set_customers_list(self, text="", search=False, date=None):
        # active is related to chip and indicate wich list to use
        app = App.get_running_app()

        # Generate sales agents list
        if self.sort_order == "Clients Actif":
            sales_agents = app.session_info['sales_agents']

        elif self.sort_order == "Clients Déclassé":
            sales_agents = app.session_info['archived_sales_agents']

        elif self.sort_order == 'Numéro vide':
            sales_agents = [
                num for num in range(
                1, max(list(app.session_info['sales_agents'].keys())) + 1
            ) if num not in app.session_info['sales_agents'].keys()
            ]

        def add_customer(name, id=""):
            self.data.append(
                {
                "viewclass": "ClientListItem",
                "text": name,
                "vendeur_id":id,
                "on_release":partial(self.open_url, id)
                }
            )

        self.data = []
        if self.sort_order in ("Clients Actif", "Clients Déclassé"):
            for key in sales_agents.keys():
                if search:
                    if (text == str(key) or 
                        text in sales_agents[key]['first_name'].lower() or
                        text in sales_agents[key]['last_name'].lower()):

                        if self.sort_order == "Clients Actif":
                            self.add_customer(
                                (f"{key}. {sales_agents[key]['first_name']}" +
                                 f" {sales_agents[key]['last_name']}")
                            )

                        else:
                            self.add_customer(
                                name=(
                                    f"{sales_agents[key]['first_name']} " +
                                    f"{sales_agents[key]['last_name']}"
                                    ),
                                id=str(key),
                            )

                else:
                    if self.sort_order == "Clients Actif":
                        self.add_customer(
                                f"{key}. {sales_agents[key]['first_name']} {sales_agents[key]['last_name']}"
                            )
                    else:
                        self.add_customer(
                            name=f"{sales_agents[key]['first_name']} {sales_agents[key]['last_name']}",
                            id=str(key),
                        )

        elif self.sort_order == "Numéro vide":
            for num in sales_agents:
                if search:
                    if text in str(num):
                        self.add_customer(str(num))
                else:
                    self.add_customer(str(num))

    # ANCHOR set_inactif_agents
    def set_inactif_agents(self, date):
        app = App.get_running_app()
        if date:
            sales_agents = app.orm.retrieve_inactive_agents(
                    date, app.session_info['sales_site_id']
                )

            self.data = []
            for agent in sales_agents:
                self.add_customer(
                    f"{agent['carte']}. {agent['vendeur'].title()}"
                )

    # ANCHOR dismiss_dialog
    def dismiss_dialog(self, *args):
        if self.dialog:
            self.dialog.dismiss()

    # ANCHOR open_dialog
    def open_dialog(self, date):
        # TODO pop up: 
        self.dialog = MDDialog(
        text=("Vous \u00eates sur le point de d\u00e9class\u00e9 " +
              "les clients sp\u00e9cifier. Voulez-vous continuer?"),
        buttons=[
            MDFlatButton(
                text="NON",
                on_release=lambda x: self.dismiss_dialog()
                ), 
            MDRaisedButton(
                text="OUI",
                on_release=lambda x: self.archive_sales_agents(date)
                    ),
            ]
        )
        self.dialog.open()

    # ANCHOR archive_sales_agents
    def archive_sales_agents(self, date):
        app = App.get_running_app()

        def worker_function():
            app.spinner_state = True
            app.orm.archive_inactive_agents(
                date=date, 
                sales_site_id=app.session_info['sales_site_id']
            )
            app.spinner_state = False
            app.pg_bar_text_val = "Operation r\u00e8ussi"
            Clock.schedule_once(self.clear_toolbar, 5)

        Thread(target=worker_function, daemon=True).start()
        self.dismiss_dialog()

    # ANCHOR clear_toolbar
    def clear_toolbar(self, args):
        app = App.get_running_app()

        app.pg_bar_val = 0
        app.pg_bar_col = (1, 1, 1, 0)
        app.pg_bar_text_val = ""
        app.spinner_state = False

    # ANCHOR open_url
    def open_url(self, id):
        if id:
            webbrowser.open(
                f"https://be.kanangila.com/backend/hr/salesagent/{id}/change/"
                )
# !SECTION
##############################################################################
