
from swapi_client.v2.models.base import APIModel


class Product(APIModel):
    """
    Model Product (produkt).
    """

    endpoint = "/api/products"


class ProductAttribute(APIModel):
    """
    Model Product Attribute (atrybut produktu).
    """

    endpoint = "/api/product_attributes"


class ProductCategory(APIModel):
    """
    Model Product Category (kategoria produktu).
    """

    endpoint = "/api/product_categories"



class ProductTemplate(APIModel):
    """
    Model Product Template (szablon produktu).
    """

    endpoint = "/api/product_templates"


class ProductToProductCategory(APIModel):
    """
    Model Product to Product Category (produkt do kategorii produktu).
    """

    endpoint = "/api/product_to_product_categories"


class ServicedProduct(APIModel):
    """
    Model Serviced Product (produkt serwisowany).
    """

    endpoint = "/api/serviced_products"


class ServicedProductAttribute(APIModel):
    """
    Model Serviced Product Attribute (atrybut produktu serwisowanego).
    """

    endpoint = "/api/serviced_product_attributes"