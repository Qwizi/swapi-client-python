from .base import APIModel

class User(APIModel):
    """
    Model User (użytkownik).
    """

    endpoint = "/api/user_users"

class UserAbsence(APIModel):
    """
    Model User Absence (nieobecność użytkownika).
    """

    endpoint = "/api/user_user_absences"


class UserAbsenceLimit(APIModel):
    """
    Model User Absence Limit (limit nieobecności użytkownika).
    """

    endpoint = "/api/user_user_absence_limits"


class UserAttribute(APIModel):
    """
    Model User Attribute (atrybut użytkownika).
    """

    endpoint = "/api/user_user_attributes"


class UserHistory(APIModel):
    """
    Model User History (historia użytkownika).
    """

    endpoint = "/api/user_user_histories"




class UserProfile(APIModel):
    """
    Model User Profile (profil użytkownika).
    """

    endpoint = "/api/user_profiles"