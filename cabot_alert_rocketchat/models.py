import logging
from django.db import models
from cabot.cabotapp.alert import AlertPlugin, AlertPluginUserData

from os import environ as env

from django.conf import settings
from django.core.urlresolvers import reverse
from django.template import Context, Template

import requests
import json

logger = logging.getLogger(__name__)
service_status_template = "{% if service.overall_status == service.PASSING_STATUS %}Back to normal{% else %}Reporting {{ service.overall_status }} status{% endif %}: [Link]({{ scheme }}://{{ host }}{% url 'service' pk=service.id %})"
check_error_template = "{% if check.check_category == 'Jenkins check' %}{% if check.last_result.error %} {{ check.name }} ({{ check.last_result.error|safe }}) {{jenkins_api}}job/{{ check.name }}/{{ check.last_result.job_number }}/console{% else %} {{ check.name }} {{jenkins_api}}/job/{{ check.name }}/{{check.last_result.job_number}}/console {% endif %}{% else %} {{ check.name }} {% if check.last_result.error %} ({{ check.last_result.error|safe }}){% endif %}{% endif %}"
alert_template = "{% for alias in users %} @{{ alias }}{% endfor %}"


# This provides the rocketchat alias for each user. Each object corresponds to a User
class RocketchatAlert(AlertPlugin):
    name = "Rocketchat"
    author = "Objectif Libre"

    def send_alert(self, service, users, duty_officers):
        alert = True
        rocketchat_aliases = []
        users = list(users) + list(duty_officers)

        rocketchat_aliases = [u.rocketchat_alias for u in RocketchatAlertUserData.objects.filter(user__user__in=users)]

        if service.overall_status == service.WARNING_STATUS:
            alert = False  # Don't alert at all for WARNING
        if service.overall_status == service.ERROR_STATUS:
            if service.old_overall_status in (service.ERROR_STATUS, service.ERROR_STATUS):
                alert = False  # Don't alert repeatedly for ERROR
        if service.overall_status == service.PASSING_STATUS:
            color = 'green'
            if service.old_overall_status == service.WARNING_STATUS:
                alert = False  # Don't alert for recovery from WARNING status
        else:
            color = 'red'

        context = Context({
            'service': service,
            'users': rocketchat_aliases,
            'host': settings.WWW_HTTP_HOST,
            'scheme': settings.WWW_SCHEME,
            'alert': alert,
            'jenkins_api': settings.JENKINS_API,
            'color': color,
            'channel': env.get('ROCKETCHAT_CHANNEL'),
            'webhook_url': env.get('ROCKETCHAT_WEBHOOK_URL'),
            'username': env.get('ROCKETCHAT_USERNAME'),
            'collapsed_service': json.loads(env.get('ROCKETCHAT_COLLAPSED_SERVICE', 'False').lower()),
            'collapsed_checks': json.loads(env.get('ROCKETCHAT_COLLAPSED_CHECKS', 'False').lower()),
            'collapsed_alert': json.loads(env.get('ROCKETCHAT_COLLAPSED_ALERT', 'False').lower()),
        })

        ### Build message
        attachments = []
        # Status attachment
        attachments = self._status_attachment(attachments, context)
        # Check multi-part attachment
        if service.overall_status != service.PASSING_STATUS:
            attachments = self._check_error_attachment(attachments, context)
        # Alert attachment
        if alert:
            attachments = self._alert_attachment(attachments, context)
 
        self._send_rocketchat_alert(attachments, context)


    def _send_rocketchat_alert(self, attachments, context):
        payload = {}
        payload['attachments'] = attachments
        payload['text'] = '*Service "%s"*' % (context.get('service').name)
        payload['parse'] = 'none'
        payload['username'] = context.get('username')
        payload['channel'] = context.get('channel')
        
        headers = {'content-type': 'application/json'}
        try:
            resp = requests.post(context.get('webhook_url'), headers=headers, data=json.dumps(payload))
        except Exception as e:
            logger.exception('Could not submit message to RocketChat: %s' % str(e))

    def _status_attachment(self, attachments, context):
        service_status_attachement = {
            'title': 'Status',
            'text': Template(service_status_template).render(context),
            'color': context.get('color'),
            'collapsed': context.get('collapsed_service'),
        }
        attachments.append(service_status_attachement)
        return attachments

    def _check_error_attachment(self, attachments, context):
        check_error_fields = []
        for check in context.get('service').all_failing_checks():
            context.push({'check': check})
            check_error_fields.append({
                'title': 'Check failing:',
                'value': Template(check_error_template).render(context)
            })
            context.pop()
        check_error_attachement = {
            'title': 'Checks',
            'fields': check_error_fields,
            'color': context.get('color'),
            'collapsed': context.get('collapsed_checks'),
        }
        attachments.append(check_error_attachement)
        return attachments

    def _alert_attachment(self, attachments, context):
        alert_attachement = {
            'title': 'Alert',
            'text': Template(alert_template).render(context),
            'color': context.get('color'),
            'collapsed': context.get('collapsed_alert'),
        }
        attachments.append(alert_attachement)
        return attachments

class RocketchatAlertUserData(AlertPluginUserData):
    name = "Rocketchat Plugin"
    rocketchat_alias = models.CharField(max_length=50, blank=True)
