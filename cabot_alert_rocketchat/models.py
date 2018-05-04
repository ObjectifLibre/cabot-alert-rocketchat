from django.db import models
from cabot.cabotapp.alert import AlertPlugin, AlertPluginUserData

from os import environ as env

from django.conf import settings
from django.core.urlresolvers import reverse
from django.template import Context, Template

import requests

rocketchat_template = "Service {{ service.name }} {% if service.overall_status == service.PASSING_STATUS %}is back to normal{% else %}reporting {{ service.overall_status }} status{% endif %}: {{ scheme }}://{{ host }}{% url 'service' pk=service.id %}. {% if service.overall_status != service.PASSING_STATUS %}Checks failing: {% for check in service.all_failing_checks %}{% if check.check_category == 'Jenkins check' %}{% if check.last_result.error %} {{ check.name }} ({{ check.last_result.error|safe }}) {{jenkins_api}}job/{{ check.name }}/{{ check.last_result.job_number }}/console{% else %} {{ check.name }} {{jenkins_api}}/job/{{ check.name }}/{{check.last_result.job_number}}/console {% endif %}{% else %} {{ check.name }} {% if check.last_result.error %} ({{ check.last_result.error|safe }}){% endif %}{% endif %}{% endfor %}{% endif %}{% if alert %}{% for alias in users %} @{{ alias }}{% endfor %}{% endif %}"

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
            color = '#008000'
            if service.old_overall_status == service.WARNING_STATUS:
                alert = False  # Don't alert for recovery from WARNING status
        else:
            color = '#800000'

        c = Context({
            'service': service,
            'users': rocketchat_aliases,
            'host': settings.WWW_HTTP_HOST,
            'scheme': settings.WWW_SCHEME,
            'alert': alert,
            'jenkins_api': settings.JENKINS_API,
        })
        message = Template(rocketchat_template).render(c)
        self._send_rocketchat_alert(message, color)

    def _send_rocketchat_alert(self, message, color):
        channel = env.get('ROCKETCHAT_CHANNEL')
        webhook_url = env.get('ROCKETCHAT_WEBHOOK_URL')
        username = env.get('ROCKETCHAT_USERNAME')

        resp = requests.post(webhook_url, data={
            'channel': channel,
            'text': message,
            'color': color,
            'alias': username
        })

class RocketchatAlertUserData(AlertPluginUserData):
    name = "Rocketchat Plugin"
    rocketchat_alias = models.CharField(max_length=50, blank=True)
