from django import forms


class Password(forms.Form):
    password = forms.CharField(label='密码', widget=forms.PasswordInput)
