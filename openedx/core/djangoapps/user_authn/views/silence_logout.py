from rest_framework.views import APIView
from django.contrib.auth import logout
from common.djangoapps.util.json_request import JsonResponse
from django.http import HttpResponseRedirect

from openedx.core.djangoapps.user_authn.cookies import delete_logged_in_cookies
from openedx.core.djangoapps.safe_sessions.middleware import mark_user_change_as_expected

class SilenceLogoutView(APIView):

    def get(self, request, *args, **kwargs):
        print("silence_logout_view > get")
        print(request)

        logout(request)
        response = HttpResponseRedirect("https://www.smefe.org/")

        delete_logged_in_cookies(response)
        mark_user_change_as_expected(response, None)

        return response