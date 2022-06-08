"""
ProxteraOAuth2: Proxtera OAuth2
REF 
- https://github.com/raccoongang/edx-oauth-client/blob/master/edx_oauth_client/backends/generic_oauth_client.py
- https://github.com/python-social-auth/social-core/tree/f27461df08bed02cdb8f95b828316a63751bb3a4/social_core/backends
- 
"""
import logging
import urllib
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import AuthFailed
from social_core.utils import handle_http_errors
from common.djangoapps import third_party_auth

class ProxteraOAuth2(BaseOAuth2):
    """
    Backend for Proxtera OAuth Server Authorization.
    """
    name = 'proxtera-oauth2'

    PROVIDER_URL = "https://auth.proxtera.com"
    AUTHORIZE_URL = "/oauth2/authorize"  # '/oauth2/authorize' usually is default value
    GET_TOKEN_URL = "/oauth2/token"  # '/oauth2/token' usually is default value
    ID_KEY = "user_id"  # unique marker which could be taken from the SSO response
    USER_DATA_URL = "https://authapi.proxtera.com/oauth2/userinfo"  # '/api/current-user/' some url similar to the example
    EXTRA_DATA = [
        ('user_data', 'user_data')
    ]
    AUTHORIZATION_URL = urllib.parse.urljoin(PROVIDER_URL, AUTHORIZE_URL)
    ACCESS_TOKEN_URL = urllib.parse.urljoin(PROVIDER_URL, GET_TOKEN_URL)
    DEFAULT_SCOPE = ['email']
    REDIRECT_STATE = False
    STATE_PARAMETER= False
    ACCESS_TOKEN_METHOD = 'POST'  # default method is 'GET'

    skip_email_verification = True

    def get_user_details(self, response):
        logging.warning('get_user_details')
        """
        Return user details from SSO account.
        """
        data = response.get('data')
        return {
            'username': data.get('user_id'),
            'name': data.get('fullname'),
            'fullname': data.get('fullname'),  
            'email': data.get('email') or '',
            'first_name': data.get('firstname'),
            'last_name': data.get('lastname'),
            'user_data':data
        }

    @handle_http_errors
    def do_auth(self, access_token, *args, **kwargs):
        logging.warning('do_auth')
        """
        Finish the auth process once the access_token was retrieved.
        """
        data = self.user_data(access_token)
        if data is not None and 'access_token' not in data:
            data['access_token'] = access_token
        kwargs.update({'response': data, 'backend': self})
        return self.strategy.authenticate(*args, **kwargs)

    # @handle_http_errors
    def auth_complete(self, *args, **kwargs):
        logging.warning('auth_complete')
        """
        Complete loging process, must return user instance.
        """
        state = self.validate_state()
        reqData = self.auth_complete_params(state)
        
        response = self.request_access_token(
            self.access_token_url(),
            data=reqData,
            params=None,
            headers=self.auth_headers(),
            auth=self.auth_complete_credentials(),
            method=self.ACCESS_TOKEN_METHOD
        )
        self.process_error(response)
        return self.do_auth(response['access_token'],
                            response=response,
                            *args, **kwargs)

    def user_data(self, access_token, *args, **kwargs):
        logging.warning('user_data')
        """
        Grab user profile information from SSO.
        """
        data = self.get_json(
            self.USER_DATA_URL,
            headers={'Authorization': "Bearer " + access_token},
        )
        data['access_token'] = access_token
        return data

    def get_user_id(self, details, response):
        logging.warning('get_user_id')
        """
        Return a unique ID for the current user, by default from server response.
        Without this method, 1st time reg and login will be ok 
        but 2nd or more will have error
        `Login failed - user with username xxx has no social auth backend name proxtera-oauth2
        """
        if 'data' in response:
            id_key = response['data'].get(self.ID_KEY)
        else:
            id_key = response.get('email')
        if not id_key:
            log.error("ID_KEY is not found in the User data response. SSO won't work correctly")
        return id_key
