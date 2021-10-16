"""
SFFOAuth2: SFF OAuth2
"""

import urllib
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import AuthFailed
from social_core.utils import handle_http_errors
from common.djangoapps import third_party_auth

class SFFOAuth2(BaseOAuth2):  # pylint: disable=abstract-method
    """
    python-social-auth backend that doesn't actually go to any third party site
    """
    name = "sff-oauth2"
    SUCCEED = True  # You can patch this during tests in order to control whether or not login works

    PROVIDER_URL = "https://gevme.com"
    AUTHORIZE_URL = "/page/oauth"  # '/oauth2/authorize' usually is default value
    GET_TOKEN_URL = "/oauth2/v1/token"  # '/oauth2/token' usually is default value
    ID_KEY = "id"  # unique marker which could be taken from the SSO response
    USER_DATA_URL = "/oauth2/v1/userinfo"  # '/api/current-user/' some url similar to the example

    AUTHORIZATION_URL = urllib.parse.urljoin(PROVIDER_URL, AUTHORIZE_URL)
    ACCESS_TOKEN_URL = 'https://live.gevme.com/v1/livestream/integrations/oauth/authorize'
    # DEFAULT_SCOPE = settings.FEATURES.get('SCOPE')  # extend the scope of the provided permissions.
    DEFAULT_SCOPE = None
    REDIRECT_STATE = False
    STATE_PARAMETER = False
    ACCESS_TOKEN_METHOD = 'POST'  # default method is 'GET'

    skip_email_verification = True

    def setting(self, name, default=None):
        """
        Return setting value from strategy.
        """
        if third_party_auth.models.OAuth2ProviderConfig is not None:
            providers = [
                p for p in third_party_auth.provider.Registry.displayed_for_login() if p.backend_name == self.name
            ]
            if not providers:
                raise Exception("Can't fetch setting of a disabled backend.")
            provider_config = providers[0]
            try:
                return provider_config.get_setting(name)
            except KeyError:
                pass
        return super(SFFOAuth2, self).setting(name, default=default)

    def auth_params(self, state=None):
        client_id, client_secret = self.get_key_and_secret()
        params = {
            'clientId': client_id,
            'clientSecret': client_secret,
            'redirectUri': self.get_redirect_uri(state)[:-1]
        }
        return params

    def auth_complete_params(self, state=None):
        client_id, client_secret = self.get_key_and_secret()
        # # Sample Request
        # {
        #     "clientId": "9ce7a185f5c84dd5",
        #     "clientSecret": "42fb7717573f473e96af53367bae0d66aab",
        #     "redirectUri": "http://localhost:4009",
        #     "code": "xxx",
        #     "grantType": "authorization_code"
        # }
        return {
            'grantType': 'authorization_code',  # request auth code
            'code': self.data.get('authorizationCode', ''),  # server response code
            'clientId': client_id,
            'clientSecret': client_secret,
            'redirectUri': self.get_redirect_uri(state)[:-1]
        }

    def get_user_details(self, response):
        """
        Return user details from SSO account.
        """
        return {'username': response.get('id'),
                'name': response.get('name'),
                'fullname': response.get('name'),  
                'email': response.get('email') or '',
                'first_name': response.get('firstname'),
                'last_name': response.get('lastname')}

    @handle_http_errors
    def do_auth(self, access_token, *args, **kwargs):
        """
        Finish the auth process once the access_token was retrieved.
        """
        data = self.user_data(access_token, *args, **kwargs)
        if data is not None and 'access_token' not in data:
            data['access_token'] = access_token
        kwargs.update({'response': data, 'backend': self})
        return self.strategy.authenticate(*args, **kwargs)

    @handle_http_errors
    def auth_complete(self, *args, **kwargs):
        """Completes login process, must return user instance"""
        return self.do_auth('blah', response=None, *args, **kwargs)

    def user_data(self, access_token, *args, **kwargs):
        state = self.validate_state()
        reqData = self.auth_complete_params(state)
        """
        Grab user profile information from SSO.
        """
        data = self.request_access_token(
            self.access_token_url(),
            data=reqData,
            params=None,
            headers=self.auth_headers(),
            auth=self.auth_complete_credentials(),
            method=self.ACCESS_TOKEN_METHOD
        )
        return data

    def get_user_id(self, details, response):
        """
        Return a unique ID for the current user, by default from server response.
        """
        if 'data' in response:
            id_key = response['data'][0].get(self.ID_KEY)
        else:
            id_key = response.get('email')
        if not id_key:
            log.error("ID_KEY is not found in the User data response. SSO won't work correctly")
        return id_key
