import requests
import json
import time, datetime

from lms.djangoapps.courseware import courses
from social_django.models import UserSocialAuth

def get_grade_cutoffs(user, course_id):
    """
    Get grade cutoffs for user for a specific course
    Sample: grade_cutoffs = {'B': 0.8, 'C': 0.7, 'D': 0.6, 'A': 0.9}

    return None if GRADE_CUTOFFS key does not exists in the grading_policy

    """
    course = courses.get_course_with_access(user, 'load', course_id)
    print("get_grade_info > course")
    print(course.grading_policy.get('GRADE_CUTOFFS'))
    print(course.grading_policy)
    
    return course.grading_policy.get('GRADE_CUTOFFS')

def is_distinction(course_grade, grade_cutoffs, course_key):
    """
    Check if user's current course grade (eg. 0.6) is grater than or equal to distinction grade

    """
    if not course_has_cert_template(course_key):
      return "false"

    """
    Check if the course only have fail and pass grades
    """
    if len(grade_cutoffs) <= 1:
      return "false"

    if course_grade and grade_cutoffs and len(grade_cutoffs) > 0:
        sorted_grade_cutoffs = sorted(list(grade_cutoffs.items()), key=lambda i: i[1], reverse=True)
        if len(sorted_grade_cutoffs[0]) > 1 and course_grade >= sorted_grade_cutoffs[0][1]:
            return "true"

    return "false"

def course_has_cert_template(course_key):
  cert_config = get_cert_config_for_course(course_key)

  if cert_config:
    if cert_config.get('certDisTemplateID'):
      return True

  return False

def get_cert_config_for_course(course_key):
  candidate_courses_url = 'https://ygndev.s3.ap-southeast-1.amazonaws.com/edx/course_dev.json'
  courses_response = requests.get(candidate_courses_url)
  courses_json = courses_response.json()

  for course_obj in courses_json:
    if str(course_obj.get('course_id')) == str(course_key):
      return course_obj.get('cert_data')

  return None

def get_letter_grade(course_grade, grade_cutoffs):

    """
    return letter_grade based on user's current course grade

    """

    letter_grade = None
    if course_grade and not isinstance(course_grade, str) and grade_cutoffs and len(grade_cutoffs) > 0:
        sorted_grade_cutoffs = sorted(list(grade_cutoffs.items()), key=lambda i: i[1], reverse=True)
        for grade in sorted_grade_cutoffs:
            if len(grade) > 1 and course_grade >= grade[1]:
                letter_grade = grade[0]
                break

    return letter_grade

#generate_custom_certificate
def send_cert_to_external_service(user, cert_id, course_id, course_grade):
    headers = {'Content-Type': 'application/json', 'apikey': '06642ecb-036d-4428-85a4-56b1428ec740'}
    url = 'https://stg-cert-api.apixoxygen.com/api/v2/certs'
    #url = 'https://cert-proxtera-api.apixoxygen.com/api/v2/certs'
    #candidate_courses_url = 'https://oxygen-lms-sg.s3.ap-southeast-1.amazonaws.com/config/course_smefe.json' #live_server
    
    
    # candidate_courses_url = 'https://ygndev.s3.ap-southeast-1.amazonaws.com/edx/course_dev.json' #Dev_Server
    # courses_response = requests.get(candidate_courses_url)
    # courses_json = courses_response.json()

    participantName = ""
    communicationChannel = ""
    participantPhone = {
        "countryCode": "",
        "phoneNumber" : ""
    }

    grade_cutoffs = get_grade_cutoffs(user, course_id)
    distinction = is_distinction(course_grade, grade_cutoffs, course_id)
    cert_category = get_letter_grade(course_grade, grade_cutoffs)

    try:
        userSocialAuth = UserSocialAuth.objects.get(user=user)

        print("User Social Auth")
        print(userSocialAuth.extra_data)
        print(userSocialAuth.extra_data['user_data'])
        print(userSocialAuth.extra_data['user_data']['country_code'])
        #print(userSocialAuth.extra_data.user_data)

        if 'fullname' in userSocialAuth.extra_data['user_data']:
            participantName = userSocialAuth.extra_data['user_data']['fullname']

        if 'preferred_communication_channel' in userSocialAuth.extra_data['user_data']:
            communicationChannel = userSocialAuth.extra_data['user_data']['preferred_communication_channel']
            if communicationChannel == "sms":
                if 'country_code' in userSocialAuth.extra_data['user_data']:
                    participantPhone["countryCode"] = userSocialAuth.extra_data['user_data']['country_code']
                if 'phone_number' in userSocialAuth.extra_data['user_data']:
                    participantPhone["phoneNumber"] = userSocialAuth.extra_data['user_data']['phone_number']

    except UserSocialAuth.DoesNotExist:
        communicationChannel = "email"
        participantName = user.first_name + " " + user.last_name

    print(communicationChannel)
    print(participantPhone)

    cert_data = get_cert_config_for_course(course_id)

    if cert_config:
      #cert_data = cert_config
      cert_data['username'] = user.username
      cert_data['cert_id'] = cert_id
      cert_data['participantName'] = participantName #user.first_name + " " + user.last_name
      cert_data['participantEmail'] = user.email
      cert_data['communicationChannel'] = communicationChannel
      cert_data['participantPhone'] = participantPhone
      cert_data['isDistinction'] = distinction
      cert_data['certCategory'] = cert_category
      cert_data['issuanceDate'] = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%dT%H:%M:%S')
      print("send_cert_to_external_service > cert_data")
      print(cert_data)
      response = requests.post(url, data=json.dumps(cert_data), headers=headers)
      print('certificate generation response')
      print(vars(response))
      return response

    # for course_obj in courses_json:
    #     if str(course_obj.get('course_id')) == str(course_id):
    #         cert_data = course_obj.get('cert_data')
    #         cert_data['username'] = user.username
    #         cert_data['cert_id'] = cert_id
    #         cert_data['participantName'] = participantName #user.first_name + " " + user.last_name
    #         cert_data['participantEmail'] = user.email
    #         cert_data['communicationChannel'] = communicationChannel
    #         cert_data['participantPhone'] = participantPhone
    #         cert_data['isDistinction'] = distinction
    #         cert_data['certCategory'] = cert_category
    #         cert_data['issuanceDate'] = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%dT%H:%M:%S')
    #         print("send_cert_to_external_service > cert_data")
    #         print(cert_data)
    #         response = requests.post(url, data=json.dumps(cert_data), headers=headers)
    #         print('certificate generation response')
    #         print(vars(response))
    #         return response

    return ""