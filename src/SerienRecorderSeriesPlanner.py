# coding=utf-8

# This file contains the SerienRecoder Series Planner
import threading, os, time, datetime
import cPickle as pickle
from Components.config import config
from Tools.Directories import fileExists

import SerienRecorder
from SerienRecorderLogWriter import SRLogger
from SerienRecorderDatabase import SRDatabase
from SerienRecorderHelpers import STBHelpers, TimeHelpers, getDirname

class downloadPlanerData(threading.Thread):
	def __init__ (self, daypage, webChannels):
		threading.Thread.__init__(self)
		self.daypage = daypage
		self.webChannels = webChannels
		self.planerData = None
	def run(self):
		try:
			from SerienRecorderSeriesServer import SeriesServer
			self.planerData = SeriesServer().doGetPlanerData(self.daypage, self.webChannels)
		except:
			SRLogger.writeLog("Fehler beim Abrufen und Verarbeiten der SerienPlaner-Daten [%s]\n" % str(self.daypage), True)

	def getData(self):
		return self.daypage, self.planerData


class serienRecSeriesPlanner:
	def __init__(self, manuell):
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		self.manuell = manuell

	def updatePlanerData(self):

		webChannels = self.database.getActiveChannels()
		SRLogger.writeLog("\nLaden der SerienPlaner-Daten gestartet ...", True)

		markers = self.database.getAllMarkers(config.plugins.serienRec.BoxID.value)
		downloadPlanerDataResults = []
		for daypage in range(int(config.plugins.serienRec.planerCacheSize.value)):
			planerData = downloadPlanerData(int(daypage), webChannels)
			downloadPlanerDataResults.append(planerData)
			planerData.start()

		try:
			for planerDataThread in downloadPlanerDataResults:
				planerDataThread.join()
				if not planerDataThread.getData():
					continue

				(daypage, planerData) = planerDataThread.getData()
				self.processPlanerData(planerData, markers, daypage)

			self.postProcessPlanerData()
		except:
			SRLogger.writeLog("Fehler beim Abrufen oder Verarbeiten der SerienPlaner-Daten")
			SRLogger.writeLog("... Laden der SerienPlaner-Daten beendet\n", True)

	def processPlanerData(self, data, markers, daypage):
		if not data or len(data) == 0:
			pass
		daylist = [[]]

		headDate = [data["date"]]
		timers = []
		# txt = headDate[0].split(",")
		# (day, month, year) = txt[1].split(".")
		# UTCDatum = TimeHelpers.getRealUnixTime(0, 0, day, month, year)

		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value:
			timers = self.database.getTimer(daypage)

		for event in data["events"]:
			aufnahme = False
			serieAdded = 0
			start_h = event["time"][:+2]
			start_m = event["time"][+3:]
			start_time = TimeHelpers.getUnixTimeWithDayOffset(start_h, start_m, daypage)

			serien_name = event["name"].encode("utf-8")
			serien_name_lower = serien_name.lower()
			sender = event["channel"]
			title = event["title"].encode("utf-8")
			staffel = event["season"]
			episode = event["episode"]
			serien_id = event["id"]

			if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value:
				serienTimers = [timer for timer in timers if timer[0] == serien_name_lower]
				serienTimersOnChannel = [serienTimer for serienTimer in serienTimers if
				                         serienTimer[2] == sender.lower()]
				for serienTimerOnChannel in serienTimersOnChannel:
					if (int(serienTimerOnChannel[1]) >= (int(start_time) - 300)) and (
							int(serienTimerOnChannel[1]) < (int(start_time) + 300)):
						aufnahme = True

				# 0 = no marker, 1 = active marker, 2 = deactive marker
				if serien_name_lower in markers:
					serieAdded = 1 if markers[serien_name_lower] else 2

				staffel = str(staffel).zfill(2)
				episode = str(episode).zfill(2)

				##############################
				#
				# CHECK
				#
				# ueberprueft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
				#
				seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

				bereits_vorhanden = False
				if config.plugins.serienRec.sucheAufnahme.value:
					(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
					if str(episode).isdigit():
						if int(episode) == 0:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString,
							                                                 serien_name, False,
							                                                 title) > 0 and True or False
						else:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString,
							                                                 serien_name,
							                                                 False) > 0 and True or False
					else:
						bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name,
						                                                 False) > 0 and True or False

				title = "%s - %s" % (seasonEpisodeString, title)
				regional = False
				paytv = False
				neu = event["new"]
				prime = False
				transmissionTime = event["time"]
				url = ''
				daylist[0].append((regional, paytv, neu, prime, transmissionTime, url, serien_name, sender, staffel,
				                   episode, title, aufnahme, serieAdded, bereits_vorhanden, serien_id))

		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value and headDate:
			d = headDate[0].split(',')
			d.reverse()
			key = d[0].strip()
			cache = self.loadPlanerData(1)
			cache.update({key: (headDate, daylist)})

	def postProcessPlanerData(self):
		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value:
			cache = self.loadPlanerData(1)
			self.writePlanerData(1, cache)

	@staticmethod
	def writePlanerData(planerType, cache):
		if not os.path.exists("%stmp/" % SerienRecorder.serienRecMainPath):
			try:
				os.makedirs("%stmp/" % SerienRecorder.serienRecMainPath)
			except:
				pass
		if os.path.isdir("%stmp/" % SerienRecorder.serienRecMainPath):
			try:
				os.chmod("%stmp/planer_%s" % (SerienRecorder.serienRecMainPath, str(planerType)), 0o666)
			except:
				pass

			f = open("%stmp/planer_%s" % (SerienRecorder.serienRecMainPath, str(planerType)), "wb")
			try:
				p = pickle.Pickler(f, 2)
				p.dump(cache)
			except:
				pass
			f.close()

			try:
				os.chmod("%stmp/planer_%s" % (SerienRecorder.serienRecMainPath, str(planerType)), 0o666)
			except:
				pass

	@staticmethod
	def loadPlanerData(planerType):
		cache = {}
		planerFile = "%stmp/planer_%s" % (SerienRecorder.serienRecMainPath, str(planerType))
		if fileExists(planerFile):
			f = open(planerFile, "rb")
			try:
				u = pickle.Unpickler(f)
				cache = u.load()
			except:
				pass
			f.close()

			try:
				heute = time.strptime(time.strftime('%d.%m.%Y', datetime.datetime.now().timetuple()), '%d.%m.%Y')
				l = []
				for key in cache:
					if time.strptime(key, '%d.%m.%Y') < heute: l.append(key)
				for key in l:
					del cache[key]
			except:
				pass

			if planerType == 1:
				serienRecSeriesPlanner.optimizePlanerData(cache)

		return cache

	@staticmethod
	def optimizePlanerData(cache):
		if time.strftime('%H.%M', datetime.datetime.now().timetuple()) < '01.00':
			t_jetzt = datetime.datetime.now().timetuple()
		else:
			t_jetzt = (datetime.datetime.now() - datetime.timedelta(0, 3600)).timetuple()
		jetzt = time.strftime('%H.%M', t_jetzt)
		heute = time.strftime('%d.%m.%Y', t_jetzt)
		if heute in cache:
			try:
				for a in cache[heute][1]:
					l = []
					for b in a:
						if b[4] < jetzt:
							l.append(b)
						else:
							break
					for b in l:
						a.remove(b)
			except:
				pass