class SWAPIError(RuntimeError):
    """
    Ogólny błąd SWAPI — wszystko co nie jest konkretną kategorią,
    np. złe dane, błędna struktura JSON lub nieobsłużona sytuacja.
    """
    pass


class SWAPIAuthError(SWAPIError):
    """
    Błąd autoryzacji:
    - login zwrócił 400/401/403
    - response z loginu nie ma pola token
    """
    pass

class SWAPINotFoundError(SWAPIError):
    """
    Błąd 404 — obiekt nie istnieje po stronie SW API.
    """
    pass


class SWAPISchemaError(SWAPIError):
    """
    Nieprawidłowa struktura odpowiedzi JSON, np.
    API zwraca pola inne niż oczekiwane.

    Ten wyjątek jest przydatny przy walidacji dynamicznych modeli.
    """
    pass


class SWAPIValidationError(SWAPIError):
    """
    Zwrotka API informująca o błędach walidacji,
    np. POST/PUT z nieprawidłowym payloadem.

    Gdy API zwraca:
    {
      \"errors\": [
         {\"field\": \"name\", \"message\": \"required\"}
      ]
    }
    """
    pass


class SWAPIPermissionDenied(SWAPIError):
    """
    Błąd autoryzacji — brak uprawnień do wykonania danej akcji.
    Najczęściej API odpowiada statusem 403.
    """
    pass


class SWAPIConnectionError(SWAPIError):
    """
    Błąd połączenia (timeout, brak internetu, problemy sieciowe).
    """
    pass