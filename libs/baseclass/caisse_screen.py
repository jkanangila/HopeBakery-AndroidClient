#####################
## SECTION IMPORTS ##
##############################################################################
import datetime
from threading import Thread

from kivy.app import App
from kivy.properties import (BooleanProperty, ColorProperty, ObjectProperty,
                             StringProperty, ListProperty)
from kivy.uix.screenmanager import Screen
from kivymd.theming import ThemableBehavior
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from libs.baseclass.add_order_page import MyContent

# !SECTION
##############################################################################


############################
## SECTION ListingItemRow ##
##############################################################################
class ListingItemRow(ThemableBehavior, MDBoxLayout):
    # ANCHOR Properties
    no = StringProperty()
    name = StringProperty()
    debit = StringProperty()
    commande = StringProperty()
    nbr = StringProperty()
    bg_col = ColorProperty()
    confirm_button = StringProperty("cart-check")
    remove_button = StringProperty("cart-remove")
    # keys(local_id, remote_id)
    data = ObjectProperty() 
    delivery_disabled = BooleanProperty(False)
    is_delivered = BooleanProperty(False)
    confirm_button_disabled = BooleanProperty(False)
    date = StringProperty()

    # ANCHOR clean_currency
    @staticmethod
    def clean_currency(_str):
        try:
            _str = _str.replace(' ', '')
            _str = _str.replace('CDF', '')
            _str = _str.replace('FC', '')
            _str = _str.replace('[color=FF0000]', '')
            _str = _str.replace('[/color]', '')
            _str = _str.replace(',', '')
            return float(_str)
        except ValueError:
            return 0

    # ANCHOR delete_row
    def delete_row(self, instance):
        app = App.get_running_app()

        # Delete order from local db
        app.orm.execute_query(
            querry_string=f"DELETE FROM sales_order WHERE id = {instance.data['local_id']}", 
            cursor="local")
        app.orm.local_conn.commit()

        # Update totals displayed in GUI
        cmd = self.clean_currency(self.commande)
        db = self.clean_currency(self.debit)
        if self.no not in ('144', '146') and cmd != 0:
            cr = cmd - db
        else:
            cr = 0

        change_sign = lambda x: x * (-1)

        self.parent.parent.parent.parent.parent.update_totals(
            commande=change_sign(cmd), 
            debit=change_sign(db), 
            credit=change_sign(cr)
        )

        # Delete object in GUI
        row_data = {
            'viewclass': 'ListingItemRow', 
            'no': instance.no, 
            'name': instance.name, 
            'debit': instance.debit, 
            'commande': instance.commande, 
            'is_delivered': instance.is_delivered, 
            'bg_col': instance.bg_col, 
            'data': instance.data, 
            'date': instance.date
        }

        index = self.parent.parent.parent.parent.parent.order_book.\
            index(row_data)
        self.parent.parent.parent.parent.parent.order_book.pop(index)
        self.parent.remove_widget(instance)

    # ANCHOR confirmer_commande
    def confirmer_commande(self, instance):

        # Disable delivery checkbox if order was 
        # marked as delivered during creation
        if self.is_delivered:
            instance.ids.deliver_updated.disabled = True

        app = App.get_running_app()

        # Querry orders from local database which 
        # corresponds to specified id 
        id = instance.data['local_id']
        kwargs = app.orm.execute_query(
            querry_string=f"SELECT * FROM sales_order WHERE id = {id}",
            verbose=True, 
            cursor="local")[0]

        # udpate cursor
        kwargs['cursor'] = 'remote'

        # delete unnecessary entries
        del kwargs['saved_to_remote']
        del kwargs['carte_no']

        # add data to upload queue
        app.upload_queue.put(kwargs)

        # start worker thread if it's not running already
        if not app.worker_thread:
            app.worker_thread = Thread(
                target=self.save_to_remote, args=(instance,)
            )
            app.worker_thread.setDaemon = True
            app.worker_thread.start()

    # ANCHOR save_to_remote
    def save_to_remote(self, instance):

        app = App.get_running_app()

        queue_length = app.upload_queue.qsize()
        # Display message on pg-bar
        msg = "Enregistrement des donn\u00e9es amorc\u00e9..."
        app.pg_bar_col = 1, 1, 1, .2
        app.pg_bar_text_val = msg
        app.spinner_state = True
        app.pg_bar_val = 0

        # iterate over upload queue
        while not app.upload_queue.empty():
            # get key word arguments from queue
            kwargs = app.upload_queue.get()

            # Update progress bar
            progress_percentage = round(
                1 - app.upload_queue.qsize()/queue_length, 1
            )*100
            app.pg_bar_val = progress_percentage

            # if there are 10 or more kwargs, save order to remote
            if len(kwargs.keys()) >= 10:
                local_id = kwargs['id']

                msg = ("Enregistrement de la commande de " +
                      f"{kwargs['client_name']} de CDF " + 
                      f"{kwargs['command']:,.2f}...")

                app.pg_bar_text_val = msg

                del kwargs['client_name']
                del kwargs['id']

                remote_id = app.orm.place_order(
                    **kwargs
                    )
                instance.data['remote_id'] = remote_id

                # update status of data as saved to remote repo
                app.orm.local_cur.execute(
                    f"""UPDATE sales_order SET saved_to_remote = 1 
                        WHERE id = {local_id}"""
                )
                app.orm.local_conn.commit()

            elif len(kwargs.keys()) == 4:
                # create delivery object in operations
                app.orm.execute_query(
                    querry_string=app.orm.qs_1(),
                    parm=kwargs
                )
                # update deliver status in sales
                del kwargs['delivery_date']
                del kwargs['created_at']
                del kwargs['delivered_by_id']
                app.orm.execute_query(
                    querry_string=app.orm.qs_2(),
                    parm=kwargs
                )
                app.conn.commit()
            app.upload_queue.task_done()

        msg = "Enregistrement finis avec succe\u00e8s"
        app.pg_bar_text_val = msg

        # Hide progress bar elements
        app.pg_bar_col = 1, 1, 1, 0
        app.pg_bar_text_val = ""
        app.spinner_state = False
        app.pg_bar_val = 0

        # set worker thread to None
        app.worker_thread = None

    # ANCHOR update_delivery
    def update_delivery(self, instance):
        pass
        # app = App.get_running_app()
        # # Disable delivery checkbox if confirmation button is disabled
        # if self.is_delivered and instance.ids.confirm_button.disabled:
        #     instance.ids.deliver_updated.disabled = True
        #     # update status in remote and local (ORDER CONFIRMED)
        #     # UPDATE LOCAL
        #     app.orm.execute_query(
        #         querry_string=f"""
        #             UPDATE sales_order 
        #             SET is_delivery = true 
        #             WHERE id = {instance.data['local_id']}""",
        #         cursor='local'
        #     )
        #     app.orm.local_conn.commit()
        #     # UPDATE REMOTE
        #     try:
        #         today = f"{datetime.date.today():%Y-%m-%d}"
        #         app.upload_queue.put({
        #                     'order_id': instance.data['remote_id'],
        #                     'delivery_date': today,
        #                     'created_at': today,
        #                     'delivered_by_id': app.session_info['id']
        #                 })
        #     except KeyError:
        #         # TODO THINK OF SOMETHING: order still in delivery queue 
        #         # inside worked thread
        #         pass

        # else:
        #     self.is_delivered = True
        #     # UPDATE LOCAL
        #     app.orm.execute_query(
        #         querry_string=f"""UPDATE sales_order 
        #                               SET is_delivery = true 
        #                               WHERE id = {instance.data['local_id']}""",
        #         cursor='local'
        #     )
        #     app.orm.local_conn.commit()
# !SECTION
##############################################################################


##########################
## SECTION CaisseScreen ##
##############################################################################
class CaisseScreen(Screen):
    dialog = None
    is_super_user = BooleanProperty(False)
    listing_instantiated = BooleanProperty(False)
    operator_name = StringProperty()
    sales_site = StringProperty()
    order_book = ListProperty()
    header_row_added = BooleanProperty(False)

    # ANCHOR on_enter
    def on_enter(self):
        app = App.get_running_app()

        self.operator_name = app.session_info['user']
        self.sales_site = app.session_info['sales_site']

        # Add header row
        if not self.header_row_added:
            self.order_book.append(
                        {
                            'viewclass': 'ListingItemRow',
                            'no': "[color=FFFFFF]CARTE[/color]",
                            'name': "[color=FFFFFF]CLIENT[/color]",
                            'debit': "",
                            'commande': "[color=FFFFFF]COMMANDE[/color]",
                            'bg_col': app.custom_focus_color,
                            '_bold': True,
                            'delivery_disabled': True,
                            'confirm_button_disabled': True
                        }
                    )
            self.header_row_added = True

        if not self.listing_instantiated:
            # ADD ORDERS FROM LOCAL DB TO LISTING
            day_orders = app.orm.execute_query(
                querry_string=f"""
                    SELECT * FROM sales_order 
                    WHERE date = {datetime.date.today():'%Y-%m-%d'}
                    AND site_de_vente_id = {
                        app.session_info['sales_site_id']
                    }""",
                verbose=True, cursor='local')

            for order in day_orders:
                name, commande, cmd = self.generate_strings(
                deb=order['debit'], crd=order['credit'], cmd=order['command'],
                _name=order['client_name'],description = order['description'])

                self.order_book.append(
                    {
                        'viewclass': 'ListingItemRow',
                        'no': str(order['carte_no']),
                        'name': name,
                        'debit': f"{order['debit']:,.0f} FC",
                        'commande': commande,
                        'is_delivered': order['is_delivery'],
                        'bg_col': [1,1,1,0],
                        'data': {"local_id": order['id']},
                        'date': f"{datetime.datetime.now()}"
                    }
                )

                self.update_totals(
                    commande=order['command'], 
                    debit=order['debit'], 
                    credit=order['credit'])

                self.listing_instantiated = True

    # ANCHOR dismiss_dialog
    def dismiss_dialog(self, *args):
        if self.dialog:
            self.dialog.dismiss()

    # ANCHOR placer_une_comande
    def placer_une_comande(self):

        self.dialog = MDDialog(
            title="Ajouter une commande",
            type="custom",
            size_hint=[0.9, None],
            content_cls=MyContent(),
            auto_dismiss=False,
            buttons=[
                MDFlatButton(
                    text="ANNULER",
                    on_release=lambda x: self.dismiss_dialog()
                ),
                MDRaisedButton(
                    text="CONFIRMER",
                    on_release=lambda x: self.post_to_order_book(
                        self.dialog.content_cls
                        )
                ),
            ],
        )
        self.dialog.open()

    # ANCHOR clean_currency
    @staticmethod
    def clean_currency(_str):
        try:
            _str = _str.replace(' ', '')
            _str = _str.replace('CDF', '')
            _str = _str.replace(',', '')
            return float(_str)
        except ValueError:
            return 0

    # ANCHOR data_validation
    def data_validation(
            self, card_number, commande, debit, 
            credit, description, date, nom_du_client
            ):
        ## validate card number ##
        ##########################
        if not card_number:
            toast("Le numero du client ne peut pas \u00eatre vide")
            return False

        ## validate client's name ##
        ##########################
        if (nom_du_client == "Nom du client" or 
            nom_du_client == "[color=ff0000]Numero non assign\u00e9[/color]"):
            toast("Veuillez specficiez un client valide")
            return False

        ## validate commande ##
        #######################
        if not commande and not debit and not credit:
            toast("Commande, debit, et credit ne peuvent pas tous " +
                   "\u00eatre vide")
            return False

        if commande and not debit and not credit:
            toast("Le montant de debbit et credit ne peuvent pas tous " +
                   "\u00eatre vide")
            return False

        ## Check description ##
        #######################
        if not description:
            toast("Veuiller specifier une description pour la commande!")
            return False

        ## check VSC Sales order can only be placed by vsc-sales agent ##
        #################################################################
        if (description.lower() == "vente sans commission" and 
            card_number not in ('144', '146')):
            toast("Ce vendeur ne peut pas passer une vente sans commission")
            return False

        if (card_number in ('144', '146') and 
            description.lower() != "vente sans commission"):
            toast("VSC client ne peut pas effectuer l'op\u00e9ration " + 
                   "s\u00e9lectionner")
            return False

        ## validate sales value by type ##
        ##################################
        if description.lower() == "normal" and not commande:
            toast("Vous devez entr\u00e9 le montant de la commande")
            return False

        if description.lower() == "vente sans commission" and commande:
            toast("Le montant de vente sans commission sont calculez "+
                  "automatiquement.\nVeuillez supprimer le montant de "+
                  "la commande")
            return False

        if description.lower() == "vente sans commission" and credit:
            toast("Vous ne pouvez pas passer une vente sans commission " +
                  "\u00e0 credit")
            return False

        if description.lower() == "vente sans commission" and not debit:
            toast("Veuillez entr\u00e9 le montant de la vente")
            return False

        if (description.lower() == "credit payment" and commande or 
                description.lower() == "credit payment" and credit):
            toast("Le champ de COMMANDE et/ou CREDIT dovient \u00eatre " + 
                 "vide pour le paiment de cr\u00e9dit")
            return False

        if description.lower() == "credit payment" and not debit:
            toast("Le champ de DEBIT est obligatoire pour le paiment de " +
                  "cr\u00e9dit")
            return False

        ## validate value of order ##
        #############################
        if description.lower() == "normal" and debit > commande:
            toast("Le montant en esp\u00e8ce (DEBIT) ne peut \u00eatre " +
                  "sup\u00e9rieur \u00e0 la valeur de la commande")
            return False

        if credit > commande:
            toast("La valeur du cr\u00e9dit ne peut pas \u00eatre " +
                  "sup\u00e9rieur \u00e0 celle de la commande")
            return False

        if credit and credit + debit > commande:
            toast("Le total DEBIT + CREDIT ne peut pas \u00eatre " + 
                   "sup\u00e9rieur \u00e0 la valeur de la commande")
            return False

        if description.lower() == "normal" and credit and debit:
            if debit + credit < commande:
                if credit and credit + debit > commande:
                    toast("Le total DEBIT + CREDIT ne peut pas \u00eatre " + 
                           "inf\u00e9rieur \u00e0 la valeur de la commande")
                    return False

        ## validate date ##
        ###################
        date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        today = datetime.datetime.now().date()

        if not self.is_super_user and date < today:
            toast("Vous ne pouvez pas passer une commande \u00e0 " +
                  "une date ant\u00e9rieure")
            return False

        if date > today:
            toast("Vous ne pouvez pas passer une commande" + 
                   " \u00e0 une date ult\u00e9rieure")
            return False

        return True

    # ANCHOR update_totals
    def update_totals(self, commande, debit, credit):
        "Update total values on infobox"
        # UPDATE TOTAL COMMANDE
        total_commande = self.clean_currency(
            self.ids.total_commande._text.split(':')[1]
        )
        total_commande += commande
        total_commande = f"Commande: CDF {total_commande:,.2f}"
        self.ids.total_commande._text = total_commande

        # UPDATE TOTAL DEBIT
        total_debit = self.clean_currency(
            self.ids.total_debit._text.split(':')[1]
        )
        total_debit += debit
        total_debit = f"Esp\u00e8ces: CDF {total_debit:,.2f}"
        self.ids.total_debit._text = total_debit

        # UPDATE TOTAL CREDIT
        total_credit = self.clean_currency(
            self.ids.total_credit._text.split(':')[1]
        )
        total_credit += credit
        total_credit = f"Cr\u00e9dit: CDF {total_credit:,.2f}"
        self.ids.total_credit._text = total_credit

    # ANCHOR generate_strings
    @staticmethod
    def generate_strings(deb, crd, cmd, _name, description):
        "Prepare data to be displayed on listing"
        app = App.get_running_app()
        commande = ""
        cmd = cmd
        # Credit donner
        if crd > 0:
            name = f"{_name} [color=FF0000] ({f'{crd:,.0f}'})[/color]"
            commande = f"[color=FF0000]{cmd:,.0f} FC[/color]"
        # Pas de credit
        else:
            name = f"{_name}"
            # Vente sans commission
            if int(description) == 2:
                commande = f"{deb*(1+1/3):,.0f} FC"
                cmd = deb*(1+1/3)
            else:
                commande = f"{cmd:,.0f} FC"

        return name, commande, cmd

    # ANCHOR post_to_order_book
    def post_to_order_book(self, instance):
        app = App.get_running_app()
        _name = instance.ids.nom_du_client.text
        cmd = self.clean_currency(instance.ids.commande_amount.text)
        deb = self.clean_currency(instance.ids.debit_amount.text)

        validatation = self.data_validation(
            card_number = instance.ids.no_carte.text,
            commande = cmd,
            debit = deb,
            credit = self.clean_currency(instance.ids.credit_amount.text),
            description = instance.ids.description.text,
            date = instance.ids.commande_date.text,
            nom_du_client = instance.ids.nom_du_client.text
        )
        if not validatation:
            return

        # calculer la valeur du credit
        if instance.ids.credit_amount.text:
            crd = self.clean_currency(instance.ids.credit_amount.text)
            if crd < cmd:
                deb = cmd - crd
        elif not instance.ids.credit_amount.text and cmd and deb and deb > 0:
            crd = cmd - deb
        else:
            crd = 0

        # Place data in a form to be displayed on listing
        name, commande, cmd = self.generate_strings(
            deb=deb, crd=crd, cmd=cmd, _name=_name,
            description = app.orm.sales_type[
                instance.ids.description.text]
        )

        # Update total values
        self.update_totals(
            **{
                'commande': float(cmd),
                'debit': float(deb),
                'credit': float(crd) if crd > 0 else float(0)
            }
        )

        # Save to local database
        kwargs = {
                'carte_no': instance.ids.no_carte.text,
                'client_name': _name,
                'vendeur_id': app.session_info['sales_agents']\
                                [int(instance.ids.no_carte.text)]['id'],
                'site_de_vente_id': app.session_info['sales_site_id'],
                'date': 'DATE()',
                'command': float(cmd),
                'debit': float(deb),
                'credit': float(crd) if crd > 0 else float(0),
                'description': app.orm.sales_type[
                                    instance.ids.description.text
                                    ],
                'operateur_id': app.session_info['user_id'],
                'is_delivery': instance.ids.delivery_status.active,
                'cursor':'local'
            }
        local_id = app.orm.place_order(**kwargs)

        self.order_book.append(
            {
                'viewclass': 'ListingItemRow',
                'no': instance.ids.no_carte.text,
                'name': name,
                'debit': f"{deb:,.0f} FC",
                'commande': commande,
                'is_delivered': instance.ids.delivery_status.active,
                'bg_col': [1,1,1,0],
                'data': {"local_id": local_id},
                'date': f"{datetime.datetime.now()}"
            }
        )

        if not self.listing_instantiated:
            self.listing_instantiated = True

        if self.dialog:
            self.dialog.dismiss()
# !SECTION
##############################################################################
