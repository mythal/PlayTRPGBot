from django import forms


class Password(forms.Form):
    password = forms.CharField(label='Password', widget=forms.PasswordInput)


class Search(forms.Form):
    search = forms.CharField(label='Search')
