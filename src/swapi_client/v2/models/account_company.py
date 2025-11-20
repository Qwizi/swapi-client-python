from .base import APIModel


class AccountCompany(APIModel):
    """
    Model Account Company (firma konta).
    """

    endpoint = "/api/account_companies"


class AccountCompanyAttribute(APIModel):
    """
    Model Account Company Attribute (atrybut firmy konta).
    """

    endpoint = "/api/account_company_attributes"


class AccountCompanyHistory(APIModel):
    """
    Model Account Company History (historia firmy konta).
    """

    endpoint = "/api/account_company_histories"