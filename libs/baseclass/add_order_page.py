from kivy.uix.boxlayout import BoxLayout
from kivy.app import App


class MyContent(BoxLayout):

    def display_customer_name(self, no_carte, instance):
        app = App.get_running_app()
        try:
            usr = app.session_info['sales_agents'][int(no_carte)]
            instance.text = f"{usr['first_name']} {usr['last_name']}".title()
        except Exception as e:
            instance.text = "[color=ff0000]Numero non assign\u00e9[/color]"


    def validate_text_on_unfocus(self, instance):
        if not instance.focus:
            if instance.text.isalnum():
                instance.text = f"CDF {float(instance.text):,.2f}"
                instance.readonly = True
