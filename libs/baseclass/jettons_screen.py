#####################
## SECTION IMPORTS ##
##############################################################################
from kivy import platform
from kivy.animation import Animation
from kivy.app import App
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.screenmanager import Screen

from kivymd.toast import toast

try:
    from kivymd.uix.picker import MDDatePicker
except ModuleNotFoundError:
    from kivymd.uix.pickers import MDDatePicker

from psycopg2.errors import (InvalidDatetimeFormat, OperationalError,
                             UniqueViolation)

# !SECTION
##############################################################################


##########################
## SECTION JettonScreen ##
##############################################################################
class JettonScreen(Screen):
    ## ANCHOR Properties
    invalid_data = ListProperty([])
    recycle_opacity = NumericProperty(0)

    ## ANCHOR Properties
    def on_enter(self, *args):
        self.invalid_data = []

    ## ANCHOR toast
    def toast(self, text='', duration=1.5):
        "display toast for a second"
        if platform == 'android':
            toast(text=text, gravity=80, length_long=duration)
        else:
            toast(text=text, duration=duration)

    ## ANCHOR adjust_logo_on_focus
    def adjust_logo_on_focus(self, focus, logo, bot_space_holder):
        if focus:
            Animation(height=0, duration=.2).start(logo)
            Animation(height=dp(180), duration=.2).start(bot_space_holder)
        else:
            Animation(height=dp(180), duration=.2).start(logo)
            Animation(height=0, duration=.2).start(bot_space_holder)

    ## ANCHOR on_save
    def on_save(self, instance, value, date_range):
        """
        Save button pressed on datepicker. Action: Set text of 
        date text input field as the selected date
        """
        self.ids.date_field.text = str(value)

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

    ## ANCHOR submit
    def submit(self, text, date):
        """Save information specified by user on the system"""
        app = App.get_running_app()
        self.invalid_data = []

        # DOCS: Make pg-bar visible, display spinner, and a message that
        # data processing started
        app.pg_bar_col = 1, 1, 1, .2
        app.pg_bar_text_val = "Pointage des jettons amorcer."
        app.spinner_state = True

        # DOCS: hide the progress bar, spinner, and pg-bar-label if there
        # is no input from user
        if text == '':
            app.pg_bar_val = 0
            app.pg_bar_col = (1, 1, 1, 0)
            app.pg_bar_text_val = ''
            app.spinner_state = False
            toast("Auccune information saisie")
            return

        # DOCS: split data entered by user and return list to iterate over
        else:
            data_points = app.orm.data_preprocessing(text=text)

        # DOCS: hide the progress bar, spinner, and pg-bar-label if there 
        # are no valid data
        if not data_points:
            app.pg_bar_val = 0
            app.pg_bar_col = (1, 1, 1, 0)
            app.pg_bar_text_val = ''
            app.spinner_state = False
            toast("Toute les donnees saisie sont invalide")
            return

        # Retrieve delivery entered by user
        if app.orm.is_date(date):
            delivery_date = self.ids.date_field.text
        # Determine delivery date based on the most recurring date
        else:
            delivery_date = app.orm.delivery_date

        # Handle cases where there is no delivery date
        if not delivery_date:
            app.pg_bar_val = 0
            app.pg_bar_col = (1, 1, 1, 0)
            app.pg_bar_text_val = ''
            app.spinner_state = False
            toast("Veuillez specifier une date de livraison valide")
            return

        # TODO add validation if date is greater than today

        # Clear text input and date fields
        self.ids.txt_input.text = ''
        self.ids.date_field.text = ''

        # Iterate over data to set delivery status to true
        total_count = len(data_points)
        count = 1
        msg = ""
        for data in data_points:
            # RETRIVE THE ORDER ID IF IT WAS NOT SPECIFIED
            if 'order_id' not in data.keys():
                order_id = app.orm.retrieve_order_id(
                    created_at=data['created_at'],
                    card_number=data['card_number'],
                    command=data['command']
                )
                # failed to retrieve order id
                if not order_id:
                    msg = (
                        f"{count}/{total_count} [b][{data['created_at']}" +
                        f" {data['card_number']} {data['command']}][/b] Ne " +
                        "correspondent à aucune commande dans le systeme"
                        )
                    self.invalid_data.append(
                        {
                            "viewclass": "OneLineListItem",
                            "text": msg
                        }
                    )
                    count += 1
                    continue
            else:
                order_id = data['order_id']

            # RETRIEVE DATE OF ORDER IF IT WAS NOT SPECIFIED
            if 'created_at' not in data.keys():
                created_at = app.orm.retrieve_created_at(
                    order_id=data['order_id']
                )
                # failed to retrieve order date
                if not created_at:
                    msg = (f"{count}/{total_count} [b]#{order_id}[/b] " + 
                            "Le numéro de jetton spécifié est incorrect")
                    self.invalid_data.append(
                        {
                            "viewclass": "OneLineListItem",
                            "text": msg
                        }
                    )
                    count += 1
                    continue
            else:
                created_at = data['created_at']

            try:
                # create delivery object in operations
                app.orm.execute_query(
                    querry_string=app.orm.qs_1(),
                    parm={
                        'order_id': order_id,
                        'delivery_date': delivery_date,
                        'created_at': created_at,
                        'delivered_by_id': app.session_info['user_id']
                    }
                )
                # update deliver status in sales
                app.orm.execute_query(
                    querry_string=app.orm.qs_2(),
                    parm={'order_id':order_id}
                )
                msg = (
                    f"{count}/{total_count} - Jetton [b]#{order_id}[/b] " +
                     "pointer avec succes"
                    )
            # Order has already been delivered
            except UniqueViolation:
                msg = (
                    f"{count}/{total_count} - [color=ff0000]Jetton " +
                    f"[b]#{order_id}[/b] a déjà été pointer[/color]"
                    )
                self.invalid_data.append(
                        {
                            "viewclass": "OneLineListItem",
                            "text": msg
                        }
                    )
                app.orm.conn.rollback()
            # Invalid date format - CASTING issue
            except InvalidDatetimeFormat:
                msg = (
                    f"{count}/{total_count} - Le Jetton #{order_id} a " +
                    f"retourne une date de command incorrecte --{created_at}--"
                    )
                data['pos'] = count
                data['description'] = msg
                app.orm.invalid_data.insert(0, data)
                self.invalid_data.append(
                        {
                            "viewclass": "OneLineListItem",
                            "text": msg
                        }
                    )
                app.orm.conn.rollback()
            # No active internet connection
            except OperationalError:
                msg = "Aucune connexion Internet active détectée"
                self.invalid_data.append(
                        {
                            "viewclass": "OneLineListItem",
                            "text": msg
                        }
                    )
                app.orm.conn.rollback()
            # General exception
            except Exception as e:
                self.invalid_data.append(
                        {
                            "viewclass": "OneLineListItem",
                            "text": f"{count}/{total_count} - {e}"
                        }
                    )
                app.orm.conn.rollback()

            count += 1
            app.pg_bar_val = int((count/total_count)*100)
            app.pg_bar_text_val = msg

        msg = "Sauvegarde des donnees en cours...."
        app.pg_bar_text_val = msg
        app.orm.conn.commit()
        app.pg_bar_val = 0
        app.pg_bar_col = (1, 1, 1, 0)
        app.pg_bar_text_val = ''
        app.spinner_state = False
# !SECTION
##############################################################################
