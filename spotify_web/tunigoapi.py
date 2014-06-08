# -*- coding: utf-8 -*-

import time
import requests
from spotify import Logging

IMAGE_HOST = "d3rt1990lpmkn.cloudfront.net"

class Tunigo():

    def __init__(self, region = "us"):
        self.region   = region
        self.root_url = "https://api.tunigo.com/v3/space/"
        Logging.debug("Starting with Tunigo for region: "  + self.region)

    def getFeaturedPlaylists(self):
      action       = "featured-playlists"
      fixed_params = "page=0&per_page=50&suppress_response_codes=1&locale=en&product=premium&version=6.31.1&platform=web"
      date_param   = "dt=" + time.strftime("%Y-%m-%dT%H:%M:%S") #2014-05-29T02%3A01%3A00"
      region_param = "region=" + self.region
      full_url = self.root_url + action + '?' + fixed_params + '&' + date_param + '&' + region_param
      
      Logging.debug("Tunigo - getFeaturedPlaylists url: " + full_url)
      r = requests.get(full_url)
      #Logging.debug("Tunigo - getFeaturedPlaylists response: " + str(r.json()))
      Logging.debug("Tunigo - getFeaturedPlaylists response OK")

      if r.status_code != 200 or r.headers['content-type'] != 'application/json':
        return { 'items': [] }.json()
      return r.json()

    def getTopPlaylists(self):
      action       = "toplists"
      fixed_params = "page=0&per_page=50&suppress_response_codes=1&locale=en&product=premium&version=6.31.1&platform=web"
      date_param   = "dt=" + time.strftime("%Y-%m-%dT%H:%M:%S") #2014-05-29T02%3A01%3A00"
      region_param = "region=" + self.region
      full_url = self.root_url + action + '?' + fixed_params + '&' + date_param + '&' + region_param
      
      Logging.debug("Tunigo - getTopPlaylists url: " + full_url)
      r = requests.get(full_url)
      #Logging.debug("Tunigo - getTopPlaylists response: " + str(r.json()))
      Logging.debug("Tunigo - getTopPlaylists response OK")

      if r.status_code != 200 or r.headers['content-type'] != 'application/json':
        return { 'items': [] }.json()
      return r.json()

    def getNewReleases(self):
      action       = "new-releases"
      fixed_params = "page=0&per_page=50&suppress_response_codes=1&locale=en&product=premium&version=6.31.1&platform=web"
      date_param   = "dt=" + time.strftime("%Y-%m-%dT%H:%M:%S") #2014-05-29T02%3A01%3A00"
      region_param = "region=" + self.region
      full_url = self.root_url + action + '?' + fixed_params + '&' + date_param + '&' + region_param
      
      Logging.debug("Tunigo - getNewReleases url: " + full_url)
      r = requests.get(full_url)
      #Logging.debug("Tunigo - getNewReleases response: " + str(r.json()))
      Logging.debug("Tunigo - getNewReleases response OK")
      
      if r.status_code != 200 or r.headers['content-type'] != 'application/json':
        return { 'items': [] }.json()
      return r.json()


