# -*- coding: utf-8 -*-
from __init__ import _

import datetime, time
import re

from twisted.web.client import getPage
from twisted.internet import defer

import socket
from urllib import urlencode
from urllib2 import urlopen, Request, URLError

from SerienRecorder import getUserAgent
#from SerienRecorder import writeTestLog


class SearchEvents(object):
	def __init__(self, serien_name, serien_id, termineCache, user_callback=None, user_errback=None):
		#self.FilterEnabled = filter_enabled
		self.serien_name = serien_name
		self.serie_url = "http://www.wunschliste.de/epg_print.pl?s=%s" % str(serien_id)
		self.termineCache = termineCache
		self.user_callback = user_callback
		self.user_errback  = user_errback

	def	request(self):
		if self.serien_name in self.termineCache:
			self.__callback(self.termineCache[self.serien_name], True)
			#writeTestLog("in cache: %s" % self.serien_name)
		else:
			#writeTestLog("not in cache: %s" % self.serien_name)
			print "[SerienRecorder] suche ' %s '" % self.serien_name
			print self.serie_url
			#getPage(self.serie_url, agent="Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0", headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.__callback).addErrback(self.__errback)
			getPage(self.serie_url, agent=getUserAgent(), headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.__callback).addErrback(self.__errback)

	def request_and_return(self):
		print "[SerienRecorder] suche dates"
		print self.serie_url
		req = Request(self.serie_url, headers={'Content-Type':'application/x-www-form-urlencoded'})
		try:
			data = urlopen(req).read()
		except URLError as e:
			self.__errback(str(e))
		except socket.timeout as e:
			self.__errback(str(e))
		return self.__callback(data)

	def __errback(self, error):
		print error
		if (self.user_errback):
			self.user_errback(error)

	def __callback(self, data, useCache=False):
		from SerienRecorder import iso8859_Decode
		sendetermine_list = []

		if useCache:
			#writeTestLog("use cache: %s" % self.serien_name)
			raw = data
		else:
			#writeTestLog("dont use cache: %s" % self.serien_name)
			#('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
			#raw = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)x(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
			raw = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>(?:\((.*?)x(.*?)\).)*<span class="titel">(.*?)</span></td></tr>', data)
			raw2 = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((?!(.*?x))(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
			raw.extend([(a,b,c,d,'0',f,g) for (a,b,c,d,e,f,g) in raw2])
			
			self.termineCache.update({self.serien_name:raw})
			
		if raw:
			def y(l):
				(day, month) = l[1].split('.')
				(start_hour, start_min) = l[2].split('.')
				now = datetime.datetime.now()
				if int(month) < now.month:
					return time.mktime((int(now.year) + 1, int(month), int(day), int(start_hour), int(start_min), 0, 0, 0, 0))		
				else:
					return time.mktime((int(now.year), int(month), int(day), int(start_hour), int(start_min), 0, 0, 0, 0))		
			raw.sort(key=y)
		
			for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
				# umlaute umwandeln
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
				title = iso8859_Decode(title)
				staffel = iso8859_Decode(staffel)

				#if self.FilterEnabled:
				#	# filter sender
				#	cSender_list = checkSender(sender)
				#	if len(cSender_list) == 0:
				#		webChannel = sender
				#		stbChannel = ""
				#		altstbChannel = ""
				#	else:
				#		(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = cSender_list[0]
                #
				#	if stbChannel == "":
				#		print "[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '" % (self.serien_name, webChannel)
				#		continue
				#		
				#	if int(status) == 0:
				#		print "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (self.serien_name, webChannel)
				#		continue
					
				sendetermine_list.append([self.serien_name, sender, datum, startzeit, endzeit, staffel, str(episode).zfill(2), title, "0"])

		if (self.user_callback):
			self.user_callback(sendetermine_list)

		return (sendetermine_list)
