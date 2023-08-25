""" API v0 views. """


import logging

## MOD
import requests
import json

from django.http.response import HttpResponse

from urllib.parse import urljoin

from django.urls import reverse
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey # MOD
from requests.exceptions import HTTPError
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_406_NOT_ACCEPTABLE, HTTP_409_CONFLICT
from rest_framework.views import APIView

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.entitlements.models import CourseEntitlement
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.util.json_request import JsonResponse
from lms.djangoapps.courseware import courses
from openedx.core.djangoapps.commerce.utils import get_ecommerce_api_base_url, get_ecommerce_api_client
from openedx.core.djangoapps.embargo import api as embargo_api
from openedx.core.djangoapps.enrollments.api import add_enrollment
from openedx.core.djangoapps.enrollments.views import EnrollmentCrossDomainSessionAuth
from openedx.core.djangoapps.user_api.preferences.api import update_email_opt_in
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser

## MOD
from lms.djangoapps.verify_student.models import ManualVerification
from openedx.features.course_experience.url_helpers import make_learning_mfe_courseware_url, get_learning_mfe_home_url

from ...constants import Messages
from ...http import DetailResponse

log = logging.getLogger(__name__)


class BasketsView(APIView):
    """ Creates a basket with a course seat and enrolls users. """

    # LMS utilizes User.user_is_active to indicate email verification, not whether an account is active. Sigh!
    authentication_classes = (JwtAuthentication,
                              BearerAuthenticationAllowInactiveUser,
                              EnrollmentCrossDomainSessionAuth)
    permission_classes = (IsAuthenticated,)

    def _is_data_valid(self, request):
        """
        Validates the data posted to the view.

        Arguments
            request -- HTTP request

        Returns
            Tuple (data_is_valid, course_key, error_msg)
        """
        course_id = request.data.get('course_id')

        if not course_id:
            return False, None, 'Field course_id is missing.'

        try:
            course_key = CourseKey.from_string(course_id)
            courses.get_course(course_key)
        except (InvalidKeyError, ValueError) as ex:
            log.exception('Unable to locate course matching %s.', course_id)
            return False, None, str(ex)

        return True, course_key, None

    def _enroll(self, course_key, user, mode=CourseMode.DEFAULT_MODE_SLUG):
        """ Enroll the user in the course. """
        add_enrollment(user.username, str(course_key), mode)

    def _handle_marketing_opt_in(self, request, course_key, user):
        """
        Handle the marketing email opt-in flag, if it was set.

        Errors here aren't expected, but should not break the outer enrollment transaction.
        """
        email_opt_in = request.data.get('email_opt_in', None)
        if email_opt_in is not None:
            try:
                update_email_opt_in(user, course_key.org, email_opt_in)
            except Exception:  # pylint: disable=broad-except
                # log the error, return silently
                log.exception(
                    'Failed to handle marketing opt-in flag: user="%s", course="%s"', user.username, course_key
                )

    ## MOD
    def _has_user_purchased_course(self, username, enrollingCourseId):
        print("GGWP4 : _has_user_purchased_course", username, enrollingCourseId)
        purchased_courses_url = "https://sdl-api.sdl.nodma.com/api/courses/" + username
        #purchased_courses_url = "https://oxygen-proxtera-api.apixoxygen.com/api/courses/" + username
        purchased_courses = requests.get(purchased_courses_url).json()
        user_enrolled = False

        for purchased_course in purchased_courses:
            if str(enrollingCourseId) == str(purchased_course):
                user_enrolled = True
        print("GGWP4 : user_enrolled",user_enrolled)
        return user_enrolled

    def post(self, request, *args, **kwargs):  # lint-amnesty, pylint: disable=unused-argument
        """
        Attempt to enroll the user.
        """
        print("GGWP4")
        user = request.user
        ## MOD
        subSectionId = request.data.get("sub_section_id")
        unitId = request.data.get("unit_id")
        enrollment_response = {}
        ## EOF MOD

        valid, course_key, error = self._is_data_valid(request)
        ## MOD
        learning_mfe_courseware_url = ""
        if subSectionId:
            if unitId:
                learning_mfe_courseware_url = make_learning_mfe_courseware_url(course_key, UsageKey.from_string(subSectionId), UsageKey.from_string(unitId))
            else:
                learning_mfe_courseware_url = make_learning_mfe_courseware_url(course_key, UsageKey.from_string(subSectionId))
        else:
            learning_mfe_courseware_url = make_learning_mfe_courseware_url(course_key)
        ## EOF MOD


        if not valid:
            return DetailResponse(error, status=HTTP_406_NOT_ACCEPTABLE)

        embargo_response = embargo_api.get_embargo_response(request, course_key, user)

        if embargo_response:
            return embargo_response

        # Don't do anything if an enrollment already exists
        course_id = str(course_key)
        enrollment = CourseEnrollment.get_enrollment(user, course_key)
        if enrollment and enrollment.is_active:
            ## MOD
            # msg = Messages.ENROLLMENT_EXISTS.format(course_id=course_id, username=user.username)
            # return DetailResponse(msg, status=HTTP_409_CONFLICT)
            enrollment_response['message'] = 'success'
            enrollment_response['redirect_url'] = learning_mfe_courseware_url
            return HttpResponse(
                json.dumps(enrollment_response),
                content_type="application/json"
            )
            ## EOF MOD

        # Check to see if enrollment for this course is closed.
        course = courses.get_course(course_key)
        if CourseEnrollment.is_enrollment_closed(user, course):
            msg = Messages.ENROLLMENT_CLOSED.format(course_id=course_id)
            log.info('Unable to enroll user %s in closed course %s.', user.id, course_id)
            return DetailResponse(msg, status=HTTP_406_NOT_ACCEPTABLE)

        # If there is no audit or honor course mode, this most likely
        # a Prof-Ed course. Return an error so that the JS redirects
        # to track selection.
        honor_mode = CourseMode.mode_for_course(course_key, CourseMode.HONOR)
        audit_mode = CourseMode.mode_for_course(course_key, CourseMode.AUDIT)
        verified_mode = CourseMode.mode_for_course(course_key, CourseMode.VERIFIED) ## MOD

        # Check to see if the User has an entitlement and enroll them if they have one for this course
        if CourseEntitlement.check_for_existing_entitlement_and_enroll(user=user, course_run_key=course_key):
            return JsonResponse(
                {
                    'redirect_destination': reverse('courseware', args=[str(course_id)]),
                },
            )

        # Accept either honor or audit as an enrollment mode to
        # maintain backwards compatibility with existing courses
        default_enrollment_mode = audit_mode or honor_mode
        course_name = None
        course_announcement = None
        print("GGWP4 : course_key",course_key)
        print("GGWP4 : verified_mode",verified_mode)
        print("GGWP4 : honor_mode",honor_mode)
        print("GGWP4 : audit_mode",audit_mode)
        ## MOD
        if verified_mode == None:
            self._enroll(course_key, user, "audit")
            enrollment_response['mode'] = 'audit'
            enrollment_response['message'] = 'success'
            enrollment_response['redirect_url'] = learning_mfe_courseware_url
            return HttpResponse(
                json.dumps(enrollment_response),
                content_type="application/json"
            )

        elif self._has_user_purchased_course(user.username, course_key):
            self._enroll(course_key, user, "verified")
            
            isUserVerified = ManualVerification.objects.get_or_create(
                user = user,
                status = 'approved',
                defaults = {'name': user.profile.name}
            )

            print('isUserVerified')
            print(isUserVerified)

            enrollment_response['mode'] = 'verified'
            enrollment_response['message'] = 'success'
            enrollment_response['redirect_url'] = learning_mfe_courseware_url
            return HttpResponse(
                json.dumps(enrollment_response),
                content_type="application/json"
            )

        enrollment_response['message'] = 'error'
        return HttpResponse(
            json.dumps(enrollment_response),
                content_type="application/json"
        )
        
        if course is not None:
            course_name = course.display_name
            course_announcement = course.announcement
        if default_enrollment_mode:
            msg = Messages.ENROLL_DIRECTLY.format(
                username=user.username,
                course_id=course_id
            )
            if not default_enrollment_mode.sku:
                # If there are no course modes with SKUs, return a different message.
                msg = Messages.NO_SKU_ENROLLED.format(
                    enrollment_mode=default_enrollment_mode.slug,
                    course_id=course_id,
                    course_name=course_name,
                    username=user.username,
                    announcement=course_announcement
                )
            log.info(msg)
            self._enroll(course_key, user, default_enrollment_mode.slug)
            mode = CourseMode.AUDIT if audit_mode else CourseMode.HONOR  # lint-amnesty, pylint: disable=unused-variable
            self._handle_marketing_opt_in(request, course_key, user)
            return DetailResponse(msg)
        else:
            msg = Messages.NO_DEFAULT_ENROLLMENT_MODE.format(course_id=course_id)
            return DetailResponse(msg, status=HTTP_406_NOT_ACCEPTABLE)


class BasketOrderView(APIView):
    """
    Retrieve the order associated with a basket.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, *_args, **kwargs):
        """
        HTTP handler.
        """
        try:
            api_url = urljoin(f"{get_ecommerce_api_base_url()}/", f"baskets/{kwargs['basket_id']}/order/")
            response = get_ecommerce_api_client(request.user).get(api_url)
            response.raise_for_status()
            return JsonResponse(response.json())
        except HTTPError as err:
            if err.response.status_code == 404:
                return JsonResponse(status=404)
            raise
