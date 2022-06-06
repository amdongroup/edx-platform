from rest_framework.views import APIView
from django.contrib.auth import logout
from common.djangoapps.util.json_request import JsonResponse
from django.http import HttpResponseRedirect

class SilenceLogoutView(APIView):

    def get(self, request, *args, **kwargs):
        print("silence_logout_view > get")
        print(request)

        logout(request)
        return HttpResponseRedirect("https://www.smefe.org/")