import requests
import logging
from typing import Dict, Any, Optional, List
from django.conf import settings

logger = logging.getLogger(__name__)


class SWQueryBuilder:
    """Helper class to build complex SW API query parameters"""
    
    def __init__(self):
        self.params = {}
    
    def with_relations(self, value: bool = True) -> 'SWQueryBuilder':
        """Set with_relations parameter"""
        self.params['setting[with_relations]'] = str(value).lower()
        return self
    
    def with_editable_settings_for_action(self, action: Optional[str] = None) -> 'SWQueryBuilder':
        """Set with_editable_settings_for_action parameter"""
        self.params['setting[with_editable_settings_for_action]'] = action or 'null'
        return self
    
    def with_cache(self, value: bool = False) -> 'SWQueryBuilder':
        """Set with_cache parameter (deprecated)"""
        self.params['setting[with_cache]'] = str(value).lower()
        return self
    
    def limit_to_my_settings(self, value: bool = True) -> 'SWQueryBuilder':
        """Set limit_to_my_settings parameter"""
        self.params['setting[limit_to_my_settings]'] = str(value).lower()
        return self
    
    def lang(self, language: str = 'pl') -> 'SWQueryBuilder':
        """Set language parameter"""
        self.params['setting[lang]'] = language
        return self
    
    def fields(self, field_list: List[str]) -> 'SWQueryBuilder':
        """Set fields to include in response"""
        self.params['fields'] = ','.join(field_list)
        return self
    
    def extra_fields(self, field_list: List[str]) -> 'SWQueryBuilder':
        """Set extra fields to include in response"""
        self.params['extra_fields'] = ','.join(field_list)
        return self
    
    def order(self, field: str, direction: str = 'asc') -> 'SWQueryBuilder':
        """Add ordering parameter"""
        self.params[f'order[{field}]'] = direction
        return self
    
    def page_limit(self, limit: int = 20) -> 'SWQueryBuilder':
        """Set page limit"""
        self.params['page[limit]'] = str(limit)
        return self
    
    def page_offset(self, offset: int) -> 'SWQueryBuilder':
        """Set page offset"""
        self.params['page[offset]'] = str(offset)
        return self
    
    def page_number(self, number: int = 1) -> 'SWQueryBuilder':
        """Set page number"""
        self.params['page[number]'] = str(number)
        return self
    
    def filter(self, field: str, value: Any = None, operator: str = 'eq') -> 'SWQueryBuilder':
        """Add filter parameter"""
        if operator in ['isNull', 'isNotNull']:
            self.params[f'filter[{field}][{operator}]'] = ''
        elif operator == 'eq':
            self.params[f'filter[{field}]'] = str(value)
        else:
            self.params[f'filter[{field}][{operator}]'] = str(value) if not isinstance(value, list) else ','.join(map(str, value))
        return self
    
    def filter_or(self, filters: Dict[str, Any], group_index: int = 0) -> 'SWQueryBuilder':
        """Add filterOr parameters"""
        for field, filter_config in filters.items():
            if isinstance(filter_config, dict):
                for operator, value in filter_config.items():
                    if operator in ['isNull', 'isNotNull']:
                        self.params[f'filterOr[{group_index}][{field}][{operator}]'] = ''
                    else:
                        filter_value = str(value) if not isinstance(value, list) else ','.join(map(str, value))
                        self.params[f'filterOr[{group_index}][{field}][{operator}]'] = filter_value
            else:
                self.params[f'filterOr[{group_index}][{field}]'] = str(filter_config)
        return self
    
    def filter_and(self, filters: Dict[str, Any], group_index: int = 0) -> 'SWQueryBuilder':
        """Add filterAnd parameters"""
        for field, filter_config in filters.items():
            if isinstance(filter_config, dict):
                for operator, value in filter_config.items():
                    if operator in ['isNull', 'isNotNull']:
                        self.params[f'filterAnd[{group_index}][{field}][{operator}]'] = ''
                    else:
                        filter_value = str(value) if not isinstance(value, list) else ','.join(map(str, value))
                        self.params[f'filterAnd[{group_index}][{field}][{operator}]'] = filter_value
            else:
                self.params[f'filterAnd[{group_index}][{field}]'] = str(filter_config)
        return self
    
    def build(self) -> Dict[str, str]:
        """Build and return the query parameters"""
        return self.params.copy()


class SWApiClient:
    def __init__(self, base_url: str = None, auth_token: str = None, login: str = None, password: str = None):
        """
        Initialize SW API Client
        
        Args:
            base_url: API base URL (defaults to settings.SW['API_URL'])
            auth_token: API authentication token (defaults to settings.SW['AUTH_TOKEN'])
            login: Login username (defaults to settings.SW['login'])
            password: Login password (defaults to settings.SW['password'])
        """
        self.base_url = base_url or settings.SW['API_URL']
        self.client_id = settings.SW['CLIENT_ID']
        self.auth_token = auth_token or settings.SW['AUTH_TOKEN']
        
        self.login = login or settings.SW['LOGIN']
        self.password = password or settings.SW['PASSWORD']
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'SW-Integrator/1.0'
        })
        
    def _get_url(self, endpoint: str) -> str:
        """Construct full URL for an endpoint"""
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise exceptions for errors"""
        try:
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError:
            logger.error(f"HTTP error {response.status_code}: {response.text}")
            raise
        except requests.exceptions.RequestException:
            logger.error("Request error occurred")
            raise
        except ValueError:
            logger.error("JSON decode error occurred")
            raise
    
    def authenticate(self) -> bool:
        """
        Authenticate with the SW API using login credentials
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            login_endpoint = settings.SW['ENDPOINTS']['LOGIN']
            print(login_endpoint)
            print(self.base_url)
            print(self.client_id)
            print(self.auth_token)
            print(self.login)
            print(self.password)
            url = self._get_url(login_endpoint)
            
            login_data = {
                'clientId': self.client_id,
                "authToken": self.auth_token,
                'login': self.login,
                'password': self.password
            }
            
            response = self.session.post(url, json=login_data)
            
            if response.status_code == 200:
                # If authentication returns a token, store it
                auth_data = response.json()
                if 'token' in auth_data:
                    self.session.headers.update({
                        'Authorization': f"Bearer {auth_data['token']}"
                    })
                elif 'access_token' in auth_data:
                    self.session.headers.update({
                        'Authorization': f"Bearer {auth_data['access_token']}"
                    })
                
                logger.info("Successfully authenticated with SW API")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Make GET request to SW API
        
        Args:
            endpoint: API endpoint
            params: Query parameters (will be merged with query_builder params)
            query_builder: SWQueryBuilder instance for complex queries
            
        Returns:
            Dict: API response data
        """
        url = self._get_url(endpoint)
        
        # Merge params from query_builder if provided
        final_params = params or {}
        if query_builder:
            final_params.update(query_builder.build())
        
        response = self.session.get(url, params=final_params)
        return self._handle_response(response)
    
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make POST request to SW API
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            
        Returns:
            Dict: API response data
        """
        url = self._get_url(endpoint)
        response = self.session.post(url, data=data, json=json_data)
        return self._handle_response(response)
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make PUT request to SW API
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            
        Returns:
            Dict: API response data
        """
        url = self._get_url(endpoint)
        response = self.session.put(url, data=data, json=json_data)
        return self._handle_response(response)
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """
        Make DELETE request to SW API
        
        Args:
            endpoint: API endpoint
            
        Returns:
            Dict: API response data
        """
        url = self._get_url(endpoint)
        response = self.session.delete(url)
        return self._handle_response(response)
    
    def close(self):
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


    # =============================================================================
    # ACCOUNT COMPANIES ENDPOINTS
    # =============================================================================
    
    def get_account_companies(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account companies from SW API
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Account companies data
        """
        return self.get('/api/account_companies', query_builder=query_builder)
    
    def get_account_company(self, company_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific account company by ID
        
        Args:
            company_id: Company ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Account company data
        """
        return self.get(f'/api/account_companies/{company_id}', query_builder=query_builder)
    
    def create_account_company(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new account company
        
        Args:
            data: Company data
            
        Returns:
            Dict: Created company data
        """
        return self.post('/api/account_companies', json_data=data)
    
    def update_account_company(self, company_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an account company
        
        Args:
            company_id: Company ID
            data: Updated company data
            
        Returns:
            Dict: Updated company data
        """
        return self.put(f'/api/account_companies/{company_id}', json_data=data)
    
    def patch_account_company(self, company_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update an account company
        
        Args:
            company_id: Company ID
            data: Partial company data
            
        Returns:
            Dict: Updated company data
        """
        return self.patch(f'/api/account_companies/{company_id}', json_data=data)
    
    def delete_account_company(self, company_id: int) -> Dict[str, Any]:
        """
        Delete an account company
        
        Args:
            company_id: Company ID
            
        Returns:
            Dict: Deletion result
        """
        return self.delete(f'/api/account_companies/{company_id}')
    
    def get_my_company(self) -> Dict[str, Any]:
        """
        Get the current user's company
        
        Returns:
            Dict: User's company data
        """
        return self.get('/api/account_companies/myCompany')
    
    def gus_update_company(self, company_id: int, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Update an account company with GUS data
        
        Args:
            company_id: Company ID
            data: GUS update data
            
        Returns:
            Dict: Updated company data
        """
        return self.patch(f'/api/account_companies/{company_id}/gusUpdate', json_data=data or {})
    
    # =============================================================================
    # ACCOUNT USERS ENDPOINTS  
    # =============================================================================
    
    def get_account_users(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account users from SW API
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Account users data
        """
        return self.get('/api/account_users', query_builder=query_builder)
    
    def get_account_user(self, user_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific account user by ID
        
        Args:
            user_id: User ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Account user data
        """
        return self.get(f'/api/account_users/{user_id}', query_builder=query_builder)
    
    def create_account_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new account user
        
        Args:
            data: User data
            
        Returns:
            Dict: Created user data
        """
        return self.post('/api/account_users', json_data=data)
    
    def update_account_user(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an account user
        
        Args:
            user_id: User ID
            data: Updated user data
            
        Returns:
            Dict: Updated user data
        """
        return self.put(f'/api/account_users/{user_id}', json_data=data)
    
    def patch_account_user(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update an account user
        
        Args:
            user_id: User ID
            data: Partial user data
            
        Returns:
            Dict: Updated user data
        """
        return self.patch(f'/api/account_users/{user_id}', json_data=data)
    
    def delete_account_user(self, user_id: int) -> Dict[str, Any]:
        """
        Delete an account user
        
        Args:
            user_id: User ID
            
        Returns:
            Dict: Deletion result
        """
        return self.delete(f'/api/account_users/{user_id}')
    
    # =============================================================================
    # PRODUCTS ENDPOINTS
    # =============================================================================
    
    def get_products(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get products from SW API
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Products data
        """
        return self.get('/api/products', query_builder=query_builder)
    
    def get_product(self, product_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific product by ID
        
        Args:
            product_id: Product ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Product data
        """
        return self.get(f'/api/products/{product_id}', query_builder=query_builder)
    
    def create_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new product
        
        Args:
            data: Product data
            
        Returns:
            Dict: Created product data
        """
        return self.post('/api/products', json_data=data)
    
    def update_product(self, product_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a product
        
        Args:
            product_id: Product ID
            data: Updated product data
            
        Returns:
            Dict: Updated product data
        """
        return self.put(f'/api/products/{product_id}', json_data=data)
    
    def patch_product(self, product_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update a product
        
        Args:
            product_id: Product ID
            data: Partial product data
            
        Returns:
            Dict: Updated product data
        """
        return self.patch(f'/api/products/{product_id}', json_data=data)
    
    def delete_product(self, product_id: int) -> Dict[str, Any]:
        """
        Delete a product
        
        Args:
            product_id: Product ID
            
        Returns:
            Dict: Deletion result
        """
        return self.delete(f'/api/products/{product_id}')
    
    # =============================================================================
    # SERVICED PRODUCTS ENDPOINTS
    # =============================================================================
    
    def get_serviced_products(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get serviced products from SW API
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Serviced products data
        """
        return self.get('/api/serviced_products', query_builder=query_builder)
    
    def get_serviced_product(self, product_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific serviced product by ID
        
        Args:
            product_id: Serviced product ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Serviced product data
        """
        return self.get(f'/api/serviced_products/{product_id}', query_builder=query_builder)
    
    def create_serviced_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new serviced product
        
        Args:
            data: Serviced product data
            
        Returns:
            Dict: Created serviced product data
        """
        return self.post('/api/serviced_products', json_data=data)
    
    def update_serviced_product(self, product_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a serviced product
        
        Args:
            product_id: Serviced product ID
            data: Updated serviced product data
            
        Returns:
            Dict: Updated serviced product data
        """
        return self.put(f'/api/serviced_products/{product_id}', json_data=data)
    
    def patch_serviced_product(self, product_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update a serviced product
        
        Args:
            product_id: Serviced product ID
            data: Partial serviced product data
            
        Returns:
            Dict: Updated serviced product data
        """
        return self.patch(f'/api/serviced_products/{product_id}', json_data=data)
    
    def delete_serviced_product(self, product_id: int) -> Dict[str, Any]:
        """
        Delete a serviced product
        
        Args:
            product_id: Serviced product ID
            
        Returns:
            Dict: Deletion result
        """
        return self.delete(f'/api/serviced_products/{product_id}')
    
    # =============================================================================
    # BASKETS ENDPOINTS
    # =============================================================================
    
    def get_baskets(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get baskets from SW API
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Baskets data
        """
        return self.get('/api/baskets', query_builder=query_builder)
    
    def get_basket(self, basket_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific basket by ID
        
        Args:
            basket_id: Basket ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Basket data
        """
        return self.get(f'/api/baskets/{basket_id}', query_builder=query_builder)
    
    def create_basket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new basket
        
        Args:
            data: Basket data
            
        Returns:
            Dict: Created basket data
        """
        return self.post('/api/baskets', json_data=data)
    
    def update_basket(self, basket_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a basket
        
        Args:
            basket_id: Basket ID
            data: Updated basket data
            
        Returns:
            Dict: Updated basket data
        """
        return self.put(f'/api/baskets/{basket_id}', json_data=data)
    
    def patch_basket(self, basket_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update a basket
        
        Args:
            basket_id: Basket ID
            data: Partial basket data
            
        Returns:
            Dict: Updated basket data
        """
        return self.patch(f'/api/baskets/{basket_id}', json_data=data)
    
    def delete_basket(self, basket_id: int) -> Dict[str, Any]:
        """
        Delete a basket
        
        Args:
            basket_id: Basket ID
            
        Returns:
            Dict: Deletion result
        """
        return self.delete(f'/api/baskets/{basket_id}')
    
    # =============================================================================
    # BASKET POSITIONS ENDPOINTS
    # =============================================================================
    
    def get_basket_positions(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get basket positions from SW API
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Basket positions data
        """
        return self.get('/api/basket_positions', query_builder=query_builder)
    
    def get_basket_position(self, position_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific basket position by ID
        
        Args:
            position_id: Basket position ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Basket position data
        """
        return self.get(f'/api/basket_positions/{position_id}', query_builder=query_builder)
    
    def create_basket_position(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new basket position
        
        Args:
            data: Basket position data
            
        Returns:
            Dict: Created basket position data
        """
        return self.post('/api/basket_positions', json_data=data)
    
    def update_basket_position(self, position_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a basket position
        
        Args:
            position_id: Basket position ID
            data: Updated basket position data
            
        Returns:
            Dict: Updated basket position data
        """
        return self.put(f'/api/basket_positions/{position_id}', json_data=data)
    
    def patch_basket_position(self, position_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update a basket position
        
        Args:
            position_id: Basket position ID
            data: Partial basket position data
            
        Returns:
            Dict: Updated basket position data
        """
        return self.patch(f'/api/basket_positions/{position_id}', json_data=data)
    
    def delete_basket_position(self, position_id: int) -> Dict[str, Any]:
        """
        Delete a basket position
        
        Args:
            position_id: Basket position ID
            
        Returns:
            Dict: Deletion result
        """
        return self.delete(f'/api/basket_positions/{position_id}')

    # =============================================================================
    # CUSTOM SERVICED PRODUCTS ENDPOINTS
    # =============================================================================
    
    def get_custom_serviced_products(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get custom serviced products from SW API
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Custom serviced products data
        """
        return self.get('/api/custom_serviced_products', query_builder=query_builder)
    
    def get_custom_serviced_product(self, product_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific custom serviced product by ID
        
        Args:
            product_id: Custom serviced product ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Custom serviced product data
        """
        return self.get(f'/api/custom_serviced_products/{product_id}', query_builder=query_builder)
    
    def create_custom_serviced_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new custom serviced product
        
        Args:
            data: Custom serviced product data
            
        Returns:
            Dict: Created custom serviced product data
        """
        return self.post('/api/custom_serviced_products', json_data=data)
    
    def update_custom_serviced_product(self, product_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a custom serviced product
        
        Args:
            product_id: Custom serviced product ID
            data: Updated custom serviced product data
            
        Returns:
            Dict: Updated custom serviced product data
        """
        return self.put(f'/api/custom_serviced_products/{product_id}', json_data=data)
    
    def patch_custom_serviced_product(self, product_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update a custom serviced product
        
        Args:
            product_id: Custom serviced product ID
            data: Partial custom serviced product data
            
        Returns:
            Dict: Updated custom serviced product data
        """
        return self.patch(f'/api/custom_serviced_products/{product_id}', json_data=data)
    
    def delete_custom_serviced_product(self, product_id: int) -> Dict[str, Any]:
        """
        Delete a custom serviced product
        
        Args:
            product_id: Custom serviced product ID
            
        Returns:
            Dict: Deletion result
        """
        return self.delete(f'/api/custom_serviced_products/{product_id}')

    # =============================================================================
    # UTILITY AND CORE ENDPOINTS
    # =============================================================================
    
    def get_me(self) -> Dict[str, Any]:
        """
        Get current user information
        
        Returns:
            Dict: Current user data
        """
        return self.get('/api/me')
    
    def get_home(self) -> Dict[str, Any]:
        """
        Get homepage/API status check
        
        Returns:
            Dict: Homepage data
        """
        return self.get('/api/')
    
    def upload_file(self, files: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload files to SW API
        
        Args:
            files: Files to upload
            
        Returns:
            Dict: Upload result
        """
        # Note: This would need special handling for file uploads
        # For now, using data parameter for form-data
        return self.post('/api/files/upload', data=files)
    
    def upload_files_from_urls(self, urls: List[str]) -> Dict[str, Any]:
        """
        Upload files from URLs
        
        Args:
            urls: List of URLs to upload from
            
        Returns:
            Dict: Upload result
        """
        return self.post('/api/files/upload/urls', json_data={'data_files_urls': urls})

    # =============================================================================
    # AUTOSELECT ENDPOINTS (for UI dropdowns/selections)
    # =============================================================================
    
    def get_account_companies_autoselect(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account companies for autoselect (dropdowns)
        
        Args:
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Account companies autoselect data
        """
        return self.get('/api/account_companies/autoselect', query_builder=query_builder)
    
    def get_account_users_autoselect(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account users for autoselect (dropdowns)
        
        Args:
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Account users autoselect data
        """
        return self.get('/api/account_users/autoselect', query_builder=query_builder)
    
    def get_products_autoselect(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get products for autoselect (dropdowns)
        
        Args:
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Products autoselect data
        """
        return self.get('/api/products/autoselect', query_builder=query_builder)
    
    def get_serviced_products_autoselect(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get serviced products for autoselect (dropdowns)
        
        Args:
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Serviced products autoselect data
        """
        return self.get('/api/serviced_products/autoselect', query_builder=query_builder)
    
    def get_baskets_autoselect(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get baskets for autoselect (dropdowns)
        
        Args:
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Baskets autoselect data
        """
        return self.get('/api/baskets/autoselect', query_builder=query_builder)
    
    def get_custom_serviced_products_autoselect(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get custom serviced products for autoselect (dropdowns)
        
        Args:
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Custom serviced products autoselect data
        """
        return self.get('/api/custom_serviced_products/autoselect', query_builder=query_builder)

    # =============================================================================
    # METADATA ENDPOINTS (for getting field information)
    # =============================================================================
    
    def get_account_companies_meta(self, field_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metadata for account companies
        
        Args:
            field_name: Optional specific field name
            
        Returns:
            Dict: Metadata for account companies
        """
        params = {'for_fieldName': field_name} if field_name else None
        return self.get('/api/account_companies/meta', params=params)
    
    def get_account_users_meta(self, field_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metadata for account users
        
        Args:
            field_name: Optional specific field name
            
        Returns:
            Dict: Metadata for account users
        """
        params = {'for_fieldName': field_name} if field_name else None
        return self.get('/api/account_users/meta', params=params)
    
    def get_products_meta(self, field_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metadata for products
        
        Args:
            field_name: Optional specific field name
            
        Returns:
            Dict: Metadata for products
        """
        params = {'for_fieldName': field_name} if field_name else None
        return self.get('/api/products/meta', params=params)
    
    def get_serviced_products_meta(self, field_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metadata for serviced products
        
        Args:
            field_name: Optional specific field name
            
        Returns:
            Dict: Metadata for serviced products
        """
        params = {'for_fieldName': field_name} if field_name else None
        return self.get('/api/serviced_products/meta', params=params)

    # =============================================================================
    # HELPER METHODS
    # =============================================================================

    def query(self) -> SWQueryBuilder:
        """
        Create a new query builder instance
        
        Returns:
            SWQueryBuilder: New query builder instance
        """
        return SWQueryBuilder()

    def patch(self, endpoint: str, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make PATCH request to SW API
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            
        Returns:
            Dict: API response data
        """
        url = self._get_url(endpoint)
        response = self.session.patch(url, data=data, json=json_data)
        return self._handle_response(response)


  

    # =============================================================================
    # SPECIALIZED ENDPOINTS (Reports, Email, PDF Generation, etc.)
    # =============================================================================
    
    def get_odbc_reports(self, company_id: int) -> Dict[str, Any]:
        """
        Get ODBC reports for a specific company
        
        Args:
            company_id: Company ID
            
        Returns:
            Dict: ODBC reports data
        """
        return self.get(f'/api/account_companies/{company_id}/odbc_reports')
    
    def get_odbc_report(self, company_id: int, report_id: int) -> Dict[str, Any]:
        """
        Get a specific ODBC report for a company
        
        Args:
            company_id: Company ID
            report_id: Report ID
            
        Returns:
            Dict: ODBC report data
        """
        return self.get(f'/api/account_companies/{company_id}/odbc_reports/{report_id}')
    
    def get_email_messages(self, company_id: int) -> Dict[str, Any]:
        """
        Get email messages for a specific company
        
        Args:
            company_id: Company ID
            
        Returns:
            Dict: Email messages data
        """
        return self.get(f'/api/account_companies/{company_id}/oemail_messages')
    
    def generate_pdf(self, module: str, item_id: int, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate PDF for a specific item
        
        Args:
            module: Module name (e.g., 'account_companies', 'account_users', 'products')
            item_id: Item ID
            data: PDF generation data
            
        Returns:
            Dict: PDF generation result
        """
        return self.post(f'/api/{module}/{item_id}/generate/pdf', json_data=data or {})
    
    # =============================================================================
    # HISTORY AND AUDIT ENDPOINTS
    # =============================================================================
    
    def get_account_company_histories(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account company histories
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Account company histories data
        """
        return self.get('/api/account_company_histories', query_builder=query_builder)
    
    def get_account_company_history(self, history_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific account company history by ID
        
        Args:
            history_id: History ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Account company history data
        """
        return self.get(f'/api/account_company_histories/{history_id}', query_builder=query_builder)
    
    def get_custom_serviced_product_histories(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get custom serviced product histories
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Custom serviced product histories data
        """
        return self.get('/api/custom_serviced_product_histories', query_builder=query_builder)
    
    def get_custom_serviced_product_history(self, history_id: int, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get a specific custom serviced product history by ID
        
        Args:
            history_id: History ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Custom serviced product history data
        """
        return self.get(f'/api/custom_serviced_product_histories/{history_id}', query_builder=query_builder)
    
    # =============================================================================
    # ATTRIBUTES AND RELATIONSHIPS ENDPOINTS
    # =============================================================================
    
    def get_account_company_attributes(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account company attributes
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Account company attributes data
        """
        return self.get('/api/account_company_attributes', query_builder=query_builder)
    
    def get_account_user_attributes(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account user attributes
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Account user attributes data
        """
        return self.get('/api/account_user_attributes', query_builder=query_builder)
    
    def get_account_company_groups(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account company groups
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Account company groups data
        """
        return self.get('/api/account_company_groups', query_builder=query_builder)
    
    def get_account_company_group_to_account_companies(self, query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get account company group to account companies relationships
        
        Args:
            query_builder: Optional query builder for filtering and pagination
            
        Returns:
            Dict: Relationship data
        """
        return self.get('/api/account_company_group_to_account_companies', query_builder=query_builder)
    
    # =============================================================================
    # BULK OPERATIONS AND ADVANCED FEATURES
    # =============================================================================
    
    def bulk_create(self, endpoint: str, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create multiple items in bulk
        
        Args:
            endpoint: API endpoint
            data_list: List of items to create
            
        Returns:
            Dict: Bulk creation result
        """
        return self.post(endpoint, json_data=data_list)
    
    def bulk_update(self, endpoint: str, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update multiple items in bulk
        
        Args:
            endpoint: API endpoint
            data_list: List of items to update
            
        Returns:
            Dict: Bulk update result
        """
        return self.patch(endpoint, json_data=data_list)
    
    def bulk_delete(self, endpoint: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete multiple items based on filters
        
        Args:
            endpoint: API endpoint
            filters: Filter criteria for deletion
            
        Returns:
            Dict: Bulk deletion result
        """
        return self.delete(endpoint, params=filters)
    
    # =============================================================================
    # CONTEXTUAL DATA ENDPOINTS
    # =============================================================================
    
    def get_data_item_for_context(self, context_module: str, context_id: int, module: str, 
                                  query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get data item for a specific context
        
        Args:
            context_module: Context module name
            context_id: Context ID
            module: Target module name
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Contextual data
        """
        endpoint = f'/api/{context_module}/{context_id}/{module}'
        return self.get(endpoint, query_builder=query_builder)
    
    def get_serviced_product_histories_for_context(self, serviced_product_id: int, 
                                                  query_builder: Optional[SWQueryBuilder] = None) -> Dict[str, Any]:
        """
        Get serviced product histories for a specific serviced product
        
        Args:
            serviced_product_id: Serviced product ID
            query_builder: Optional query builder for filtering
            
        Returns:
            Dict: Serviced product histories data
        """
        return self.get(f'/api/serviced_products/{serviced_product_id}/serviced_product_histories', 
                       query_builder=query_builder)
    
    # =============================================================================
    # SEARCH AND FILTERING HELPERS
    # =============================================================================
    
    def search_companies(self, search_term: str, limit: int = 50) -> Dict[str, Any]:
        """
        Search companies by name, code, or other fields
        
        Args:
            search_term: Search term
            limit: Maximum number of results
            
        Returns:
            Dict: Search results
        """
        query = (self.query()
                .with_relations(True)
                .fields(['id', 'name', 'code', 'address', 'phone', 'email'])
                .filter_or({
                    'name': {'hasText': search_term},
                    'code': {'hasText': search_term},
                    'address': {'hasText': search_term}
                })
                .order('name', 'asc')
                .page_limit(limit))
        
        return self.get_account_companies(query_builder=query)
    
    def search_users(self, search_term: str, limit: int = 50) -> Dict[str, Any]:
        """
        Search users by name, email, or other fields
        
        Args:
            search_term: Search term
            limit: Maximum number of results
            
        Returns:
            Dict: Search results
        """
        query = (self.query()
                .with_relations(True)
                .fields(['id', 'firstName', 'lastName', 'email', 'phone'])
                .filter_or({
                    'firstName': {'hasText': search_term},
                    'lastName': {'hasText': search_term},
                    'email': {'hasText': search_term}
                })
                .order('lastName', 'asc')
                .page_limit(limit))
        
        return self.get_account_users(query_builder=query)
    
    def search_products(self, search_term: str, limit: int = 50) -> Dict[str, Any]:
        """
        Search products by name, code, or description
        
        Args:
            search_term: Search term
            limit: Maximum number of results
            
        Returns:
            Dict: Search results
        """
        query = (self.query()
                .with_relations(True)
                .fields(['id', 'name', 'code', 'description', 'price'])
                .filter_or({
                    'name': {'hasText': search_term},
                    'code': {'hasText': search_term},
                    'description': {'hasText': search_term}
                })
                .order('name', 'asc')
                .page_limit(limit))
        
        return self.get_products(query_builder=query)
    
    def search_serviced_products(self, search_term: str, limit: int = 50) -> Dict[str, Any]:
        """
        Search serviced products by name, code, or description
        
        Args:
            search_term: Search term
            limit: Maximum number of results
            
        Returns:
            Dict: Search results
        """
        query = (self.query()
                .with_relations(True)
                .fields(['id', 'name', 'code', 'description', 'status'])
                .filter_or({
                    'name': {'hasText': search_term},
                    'code': {'hasText': search_term},
                    'description': {'hasText': search_term}
                })
                .order('name', 'asc')
                .page_limit(limit))
        
        return self.get_serviced_products(query_builder=query)
    
    # =============================================================================
    # PAGINATION HELPERS
    # =============================================================================
    
    def get_all_pages(self, endpoint_method, query_builder: Optional[SWQueryBuilder] = None, 
                      page_size: int = 100) -> List[Dict[str, Any]]:
        """
        Get all pages of data from a paginated endpoint
        
        Args:
            endpoint_method: The endpoint method to call (e.g., self.get_account_companies)
            query_builder: Optional query builder
            page_size: Number of items per page
            
        Returns:
            List: All items from all pages
        """
        all_items = []
        page = 1
        
        while True:
            query = query_builder or self.query()
            query.page_number(page).page_limit(page_size)
            
            response = endpoint_method(query_builder=query)
            
            data = response.get('data', [])
            if not data:
                break
                
            all_items.extend(data)
            
            # Check if we have more pages
            meta = response.get('meta', {})
            total_pages = meta.get('totalPages', 1)
            
            if page >= total_pages:
                break
                
            page += 1
        
        return all_items
    
    def get_companies_with_pagination(self, page: int = 1, limit: int = 20, 
                                     filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get companies with pagination and optional filters
        
        Args:
            page: Page number
            limit: Items per page
            filters: Optional filters
            
        Returns:
            Dict: Paginated companies data
        """
        query = (self.query()
                .with_relations(True)
                .page_number(page)
                .page_limit(limit)
                .order('name', 'asc'))
        
        if filters:
            for field, value in filters.items():
                if isinstance(value, dict):
                    for operator, filter_value in value.items():
                        query.filter(field, filter_value, operator)
                else:
                    query.filter(field, value)
        
        return self.get_account_companies(query_builder=query)

  # Convenience function to get a configured client
def get_sw_client() -> SWApiClient:
    """Get a configured SW API client instance"""
    return SWApiClient()