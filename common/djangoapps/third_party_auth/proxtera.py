"""
ProxteraOAuth2: Proxtera OAuth2
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
    SUCCEED = True  # You can patch this during tests in order to control whether or not login works

    # CUSTOM_OAUTH_PARAMS = settings.CUSTOM_OAUTH_PARAMS

    # if not all(CUSTOM_OAUTH_PARAMS.values()):
        # log.error("Some of the CUSTOM_OAUTH_PARAMS are improperly configured. Custom oauth won't work correctly.")

    PROVIDER_URL = "https://devauth.proxtera.app"
    AUTHORIZE_URL = "/oauth2/authorize"  # '/oauth2/authorize' usually is default value
    GET_TOKEN_URL = "/oauth2/token"  # '/oauth2/token' usually is default value
    ID_KEY = "username"  # unique marker which could be taken from the SSO response
    USER_DATA_URL = "https://devauthapi.proxtera.app/oauth2/userinfo"  # '/api/current-user/' some url similar to the example

    AUTHORIZATION_URL = urllib.parse.urljoin(PROVIDER_URL, AUTHORIZE_URL)
    ACCESS_TOKEN_URL = urllib.parse.urljoin(PROVIDER_URL, GET_TOKEN_URL)
    # DEFAULT_SCOPE = settings.FEATURES.get('SCOPE')  # extend the scope of the provided permissions.
    DEFAULT_SCOPE = ['email']
    # REDIRECT_STATE = False
    STATE_PARAMETER = False
    RESPONSE_TYPE = 'code'
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
        return super(ProxteraOAuth2, self).setting(name, default=default)

    def auth_params(self, state=None):
        logging.warning('>>> auth_params')
        client_id, client_secret = self.get_key_and_secret()
        params = {
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': self.get_redirect_uri(state)[:-1],
            'scope': 'email',
            'response_type': 'code'
        }
        return params

    def auth_complete_params(self, state=None):
        logging.warning('>>> auth_complete_params')
        client_id, client_secret = self.get_key_and_secret()
        return {
            'grant_type': 'authorization_code',  # request auth code
            'code': self.data.get('code', ''),  # server response code
            'client_id': client_id,
            'redirect_uri': self.get_redirect_uri(state)[:-1]
        }

    def get_user_details(self, response):
        logging.warning('>>> get_user_details')
        logging.warning(response)
        """
        Return user details from SSO account.
        """
        data = response.get('data')
        return {'username': data.get('username'),
                'name': data.get('fullname'),
                'fullname': data.get('fullname'),  
                'email': data.get('email') or '',
                'first_name': data.get('firstname'),
                'last_name': data.get('lastname')}

    @handle_http_errors
    def do_auth(self, access_token, *args, **kwargs):
        logging.warning('>>> do_auth')
        """
        Finish the auth process once the access_token was retrieved.
        """
        data = self.user_data(access_token)
        if data is not None and 'access_token' not in data:
            data['access_token'] = access_token
        kwargs.update({'response': data, 'backend': self})
        return self.strategy.authenticate(*args, **kwargs)

    @handle_http_errors
    def auth_complete(self, *args, **kwargs):
        logging.warning('>>> auth_complete')
        """
        Complete loging process, must return user instance.
        """
        self.strategy.session_set('{}_state'.format(self.name), self.data.get('state'))
        next_url = '/'
        self.strategy.session.setdefault('next', next_url)
        return super(ProxteraOAuth2, self).auth_complete(*args, **kwargs)

    def user_data(self, access_token, *args, **kwargs):
        logging.warning('>>> user_data')
        """
        Grab user profile information from SSO.
        """
        data = self.get_json(
            self.USER_DATA_URL,
            params={'access_token': access_token},
        )
        data['access_token'] = access_token
        return data

    # def pipeline(self, pipeline, pipeline_index=0, *args, **kwargs):
    #     self.strategy.session.setdefault('auth_entry', 'register')
    #     return super(ProxteraOAuth2, self).pipeline(
    #         pipeline=self.PIPELINE, *args, **kwargs
    #     )

    def get_user_id(self, details, response):
        logging.warning('>>> get_user_id')
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
