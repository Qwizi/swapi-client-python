from .base import APIModel

class AccountUser(APIModel):
    """
    Model Account User (użytkownik konta).
    """

    endpoint = "/api/account_users"


class AccountUserAttribute(APIModel):
    """
    Model Account User Attribute (atrybut użytkownika konta).
    """

    endpoint = "/api/account_user_attributes"


class AccountUserHistory(APIModel):
    """
    Model Account User History (historia użytkownika konta).
    """

    endpoint = "/api/account_user_histories"


