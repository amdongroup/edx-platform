(function (define) {
    'use strict';
    define(['jquery', 'jquery.cookie'], function ($) {
        var EnrollmentInterface = {

            urls: {
                baskets: '/api/commerce/v0/baskets/'
            },

            headers: {
                'X-CSRFToken': $.cookie('csrftoken')
            },

            /**
             * Enroll a user in a course, then redirect the user.
             * @param  {string} courseKey  Slash-separated course key.
             * @param  {string} redirectUrl The URL to redirect to once enrollment completes.
             */
            enroll: function (courseKey, redirectUrl, subSectionId, unitId) {
                alert('enroll')
                console.log('GGWP 5: subSectionId', subSectionId)
                console.log('GGWP 5: unitId', unitId)
                // MOD
                var data_obj = {
                    course_id: courseKey,
                    sub_section_id: subSectionId,
                    unit_id: unitId
                },
                    data = JSON.stringify(data_obj);
                console.log('GGWP 5: API CALL')
                $.ajax({
                    url: this.urls.baskets,
                    type: 'POST',
                    contentType: 'application/json; charset=utf-8',
                    data: data,
                    headers: this.headers,
                    context: this
                }).fail(function (jqXHR) {
                    console.log('GGWP 5: API CALL FAIL')
                    var responseData = JSON.parse(jqXHR.responseText);
                    if (jqXHR.status === 403 && responseData.user_message_url) {
                        // Check if we've been blocked from the course
                        // because of country access rules.
                        // If so, redirect to a page explaining to the user
                        // why they were blocked.
                        this.redirect(responseData.user_message_url);
                    } else {
                        // Otherwise, redirect the user to the next page.
                        // MOD
                        // if (redirectUrl) {
                        //     this.redirect(redirectUrl);
                        // }
                        this.redirectToDashboard()
                        // EOF MOD
                    }
                }).done(function (response) {
                    console.log('GGWP 5: API CALL DONE')
                    // If we successfully enrolled, redirect the user
                    // to the next page (usually the student dashboard or payment flow)
                    // MOD
                    console.log('GGWP 5 : RRR ', response.message)
                    if (response.message == "success") {
                        //this.redirectToSectionDetail(courseKey, chapterId, sectionId)
                        this.redirect(response.redirect_url)
                    } else {
                        this.redirectToDashboard()
                    }
                    // if (response.redirect_destination) {
                    //     this.redirect(response.redirect_destination);
                    // } else if (redirectUrl) {
                    //     this.redirect(redirectUrl);
                    // }
                    // EOF MOD
                });
            },

            // MOD
            redirectToDashboard: function () {
                console.log('GGWP 5 : redirectToDashboard')
                var url = `${window.location.origin}/dashboard`
                window.location.href = url
            },
            // EOF MOD

            /**
             * Redirect to a URL.  Mainly useful for mocking out in tests.
             * @param  {string} url The URL to redirect to.
             */
            redirect: function (url) {
                window.location.href = url;
            }
        };

        return EnrollmentInterface;
    });
}).call(this, define || RequireJS.define);
