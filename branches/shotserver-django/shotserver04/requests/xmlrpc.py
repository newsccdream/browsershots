# browsershots.org - Test your web design in different browsers
# Copyright (C) 2007 Johann C. Rocholl <johann@browsershots.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston,
# MA 02111-1307, USA.

"""
XML-RPC interface for requests app.
"""

__revision__ = "$Rev$"
__date__ = "$Date$"
__author__ = "$Author$"

from xmlrpclib import Fault
from django.db import models
from shotserver04.common import serializable, get_or_fault
from shotserver04.xmlrpc import register
from shotserver04.nonces import xmlrpc as nonces
from shotserver04.factories.models import Factory
from shotserver04.browsers.models import Browser
from shotserver04.requests.models import Request
from datetime import datetime, timedelta
# import time # For test_overload.py


@serializable
def find_and_lock_request(factory, features):
    """
    Find a matching screenshot request and lock it.
    """
    # Find matching request
    now = datetime.now()
    five_minutes_ago = now - timedelta(0, 300)
    matches = Request.objects.select_related()
    matches = matches.filter(features)
    matches = matches.filter(screenshot__isnull=True)
    matches = matches.filter(request_group__expire__gt=now)
    matches = matches.filter(
        models.Q(locked__isnull=True) | models.Q(locked__lt=five_minutes_ago))
    matches = matches.order_by(
        'requests_request__request_group.submitted')
    matches = matches[:1]
    # time.sleep(0.1) # For test_overload.py
    if len(matches) == 0:
        raise Fault(0, 'No matching request.')
    request = matches[0]
    # Lock request
    request.factory = factory
    request.locked = datetime.now()
    request.save()
    return request


def add_version(filters, value, name):
    """
    Update filters to get the browser for a matching request.
    """
    if value is None:
        return
    if hasattr(value, 'id'):
        value = value.id
    if value == 2: # request for 'enabled'
        filters[name + '__gte'] = 2 # match 'enabled' or version
    else:
        filters[name] = value # specific requested version


def version_or_empty(feature):
    """Return version field, or empty string if feature is None."""
    if feature is None:
        return ''
    else:
        return feature.version


@register(dict, str, str)
def poll(http_request, factory_name, encrypted_password):
    """
    Try to find a matching screenshot request for a given factory.

    Arguments
    ~~~~~~~~~
    * factory_name string (lowercase, normally from hostname)
    * encrypted_password string (lowercase hexadecimal, length 32)

    See nonces.verify for how to encrypt your password.

    Return value
    ~~~~~~~~~~~~
    * options dict (screenshot request configuration)

    If successful, the options dict will have the following keys:

    * request int (for redirect and screenshots.upload)
    * browser string (browser name)
    * version string (browser version)
    * major int (major browser version number)
    * minor int (minor browser version number)
    * command string (browser command to run, empty for default)
    * width int (screen width in pixels)
    * height int (screen height in pixels)
    * bpp int (color depth in bits per pixel)
    * javascript string (javascript version)
    * java string (java version)
    * flash string (flash version)

    Locking
    ~~~~~~~
    The matching screenshot request is locked for five minutes. This
    is to make sure that no requests are processed by two factories at
    the same time. If your factory takes longer to process a request,
    it is possible that somebody else will lock it. In this case, your
    upload will fail.
    """
    # Verify authentication
    factory = get_or_fault(Factory, name=factory_name)
    nonces.verify(http_request, factory, encrypted_password)
    # Update last_poll timestamp
    factory.last_poll = datetime.now()
    factory.ip = http_request.META['REMOTE_ADDR']
    factory.save()
    # Get matching request
    request = find_and_lock_request(factory, factory.features_q())
    # Get matching browser
    filters = {'factory': factory,
               'browser_group': request.browser_group,
               'active': True}
    add_version(filters, request.major, 'major')
    add_version(filters, request.minor, 'minor')
    add_version(filters, request.request_group.javascript, 'javascript__id')
    add_version(filters, request.request_group.java, 'java__id')
    add_version(filters, request.request_group.flash, 'flash__id')
    try:
        browser = Browser.objects.select_related().get(**filters)
    except Browser.DoesNotExist:
        raise Fault(0, "No matching browser for selected request.")
    # Build result dict
    return {
        'request': request.id,
        'browser': browser.browser_group.name,
        'version': browser.version,
        'major': browser.major,
        'minor': browser.minor,
        'command': browser.command,
        'width': request.request_group.width or 0,
        'height': request.request_group.height or 0,
        'bpp': request.request_group.bits_per_pixel or 0,
        'javascript': version_or_empty(request.request_group.javascript),
        'java': version_or_empty(request.request_group.java),
        'flash': version_or_empty(request.request_group.flash),
        }
