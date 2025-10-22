from django.urls import reverse
from django.utils.http import urlencode


def build_url(url_name: str, *args, **kwargs):
    '''
    Returns reversed_url?kwarg1=val1,kwarg2=val2

    Parameters
    ----------

    url_name : str
        URL name.
    args : *
        Args for reverse(url_name, args=args)
    kwargs : **
        Get parameters.
    '''
    url = reverse(url_name, args=args)
    params = urlencode(kwargs)
    return f'{url}?{params}'