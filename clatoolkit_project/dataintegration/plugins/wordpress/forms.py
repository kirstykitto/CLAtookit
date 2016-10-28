from django import forms


class ConnectForm(forms.Form):
    wp_root = forms.URLField(label="WordPress Root URL", widget=forms.TextInput(attrs={'class': 'form-control'}))
    client_key = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    client_secret = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    unit_id = forms.CharField(widget=forms.HiddenInput())
