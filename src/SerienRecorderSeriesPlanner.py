# coding=utf-8

# This file contains the SerienRecoder Series Planner
import threading, os, time, datetime
from Components.config import config
from Tools.Directories import fileExists

from .SerienRecorderLogWriter import SRLogger
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorderHelpers import STBHelpers, TimeHelpers, getDirname, toStr, PY2

if PY2:
	import cPickle as pickle
else:
	import pickle

class downloadPlannerData(threading.Thread):
	def __init__ (self, daypage, webChannels):
		threading.Thread.__init__(self)
		self.daypage = daypage
		self.webChannels = webChannels
		self.plannerData = None
	def run(self):
		try:
			from .SerienRecorderSeriesServer import SeriesServer
			self.plannerData = SeriesServer().doGetPlannerData(self.daypage, self.webChannels)
		except:
			SRLogger.writeLog("Fehler beim Abrufen und Verarbeiten der Serien-Planer Daten [%s]\n" % str(self.daypage), True)

	def getData(self):
		return self.daypage, self.plannerData


class serienRecSeriesPlanner:
	def __init__(self):
		from .SerienRecorder import getDataBaseFilePath
		self.database = SRDatabase(getDataBaseFilePath())

	def updatePlannerData(self):
		webChannels = self.database.getActiveChannels()
		markers = self.database.getAllMarkers(config.plugins.serienRec.BoxID.value)

		SRLogger.writeLog("\nLaden der Serien-Planer Daten gestartet ...", True)

		downloadPlannerDataResults = []
		plannerCacheSize = 2
		for daypage in range(plannerCacheSize):
			plannerData = downloadPlannerData(int(daypage), webChannels)
			downloadPlannerDataResults.append(plannerData)
			plannerData.start()

		try:
			for plannerDataThread in downloadPlannerDataResults:
				plannerDataThread.join()
				if not plannerDataThread.getData():
					continue

				(daypage, plannerData) = plannerDataThread.getData()
				self.processPlannerData(plannerData, markers, daypage)
		except:
			SRLogger.writeLog("Fehler beim Abrufen oder Verarbeiten der Serien-Planer Daten")
		SRLogger.writeLog("... Laden der Serien-Planer Daten beendet\n", True)

	def processPlannerData(self, data, markers, daypage):
		if not data or len(data) == 0:
			pass
		daylist = [[]]

		headDate = [data["date"]]
		timers = self.database.getTimer(daypage)

		for event in data["events"]:
			aufnahme = False
			serieAdded = 0
			start_h = event["time"][:+2]
			start_m = event["time"][+3:]
			start_time = TimeHelpers.getUnixTimeWithDayOffset(start_h, start_m, daypage)

			serien_name = toStr(event["name"])
			sender = event["channel"]
			title = toStr(event["title"])
			staffel = event["season"]
			episode = event["episode"]
			serien_wlid = event["id"]
			serien_fsid = event["fs_id"]
			serien_info = event["info"]

			serienTimers = [timer for timer in timers if timer[0] == serien_fsid]
			serienTimersOnChannel = [serienTimer for serienTimer in serienTimers if
			                         serienTimer[2] == sender.lower()]
			for serienTimerOnChannel in serienTimersOnChannel:
				if (int(serienTimerOnChannel[1]) >= (int(start_time) - 300)) and (
						int(serienTimerOnChannel[1]) < (int(start_time) + 300)):
					aufnahme = True

			# 0 = no marker, 1 = active marker, 2 = deactive marker
			if serien_wlid in markers:
				serieAdded = 1 if markers[serien_wlid] else 2

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
				(dirname, dirname_serie) = getDirname(self.database, serien_name, serien_fsid, staffel)
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
			daylist[0].append((regional, paytv, neu, prime, transmissionTime, serien_name, sender, staffel,
			                   episode, title, aufnahme, serieAdded, bereits_vorhanden, serien_wlid, serien_fsid, serien_info))

		print("[SerienRecorder] Es wurden %s Serie(n) gefunden" % len(daylist[0]))

		if headDate:
			d = headDate[0].split(',')
			d.reverse()
			key = d[0].strip()
			cache = self.loadPlannerData(1)
			cache.update({key: (headDate, daylist)})
			self.writePlannerData(1, cache)

		return headDate, daylist

	@staticmethod
	def writePlannerData(plannerType, cache):
		serienRecPlannerPath = "/var/cache/serienrecorder"

		if not os.path.exists(serienRecPlannerPath):
			try:
				os.makedirs(serienRecPlannerPath)
			except:
				pass
		if os.path.isdir(serienRecPlannerPath):
			try:
				os.chmod("%s/planer_%s" % (serienRecPlannerPath, str(plannerType)), 0o666)
			except:
				pass

			f = open("%s/planer_%s" % (serienRecPlannerPath, str(plannerType)), "wb")
			try:
				p = pickle.Pickler(f)
				p.dump(cache)
			except:
				pass
			f.close()

			try:
				os.chmod("%s/planer_%s" % (serienRecPlannerPath, str(plannerType)), 0o666)
			except:
				pass

	@staticmethod
	def loadPlannerData(plannerType):
		cache = {}

		plannerFile = "/var/cache/serienrecorder/planer_%s" % str(plannerType)
		if fileExists(plannerFile):
			f = open(plannerFile, "rb")
			try:
				u = pickle.Unpickler(f)
				cache = u.load()
			except:
				pass
			f.close()

			try:
				d_now_str = time.strptime(time.strftime('%d.%m.%Y', datetime.datetime.now().timetuple()), '%d.%m.%Y')
				l = []
				for key in cache:
					if time.strptime(key, '%d.%m.%Y') < d_now_str: l.append(key)
				for key in l:
					del cache[key]
			except:
				pass

			if plannerType == 1:
				serienRecSeriesPlanner.optimizePlannerData(cache)

		return cache

	@staticmethod
	def optimizePlannerData(cache):
		if time.strftime('%H:%M', datetime.datetime.now().timetuple()) < '01:00':
			t_now = datetime.datetime.now().timetuple()
		else:
			t_now = (datetime.datetime.now() - datetime.timedelta(0, 3600)).timetuple()
		t_now_str = time.strftime('%H:%M', t_now)
		d_now_str = time.strftime('%d.%m.%Y', t_now)
		if d_now_str in cache:
			try:
				for a in cache[d_now_str][1]:
					l = []
					for b in a:
						if b[4] < t_now_str:
							l.append(b)
						else:
							break
					for b in l:
						a.remove(b)
			except:
				pass