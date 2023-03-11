# coding=utf-8

# This file contains the SerienRecoder Series Planner
import time, datetime
import NavigationInstance

from Components.config import config
from RecordTimer import RecordTimerEntry
from Screens.MessageBox import MessageBox
from ServiceReference import ServiceReference
from Tools import Notifications

from . import SerienRecorder
from .SerienRecorderLogWriter import SRLogger
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorderHelpers import STBHelpers, TimeHelpers, getDirname

class serienRecTimer:
	def __init__(self):

		self.countTimer = 0
		self.countTimerUpdate = 0
		self.countNotActiveTimer = 0
		self.countTimerFromWishlist = 0
		self.countBoxOnlyTimer = 0
		self.messageList = []

		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		self.tempDB = None
		self.konflikt = ""
		self.enableDirectoryCreation = False
		self.channelList = STBHelpers.buildSTBChannelList()

	def setTempDB(self, database):
		self.tempDB = database

	def getCounts(self):
		return self.countTimer, self.countTimerUpdate, self.countNotActiveTimer, self.countTimerFromWishlist, self.countBoxOnlyTimer, self.messageList

	@staticmethod
	def getTimerName(series_name, series_season, series_episode, series_title, series_altname, marker_type):
		if marker_type == 1:
			timer_name = series_name
		else:
			try:
				if len(series_altname) > 0:
					series_name = series_altname
				data = {"serie": series_name, "staffel": str(series_season).zfill(2), "episode": str(series_episode).zfill(2), "titel": series_title}
				timer_name = config.plugins.serienRec.TimerName.value.strip().format(**data)
			except Exception as e:
				SRLogger.writeLog("Fehler beim Zusammensetzen des Timernamens: %s" % str(e))
				timer_name = "%s - S%sE%s - %s" % (series_name, str(series_season).zfill(2), str(series_episode).zfill(2), series_title)

		return timer_name

	@staticmethod
	def getTimerDescription(series_name, series_season, series_episode, series_title):
		try:
			data = {"serie": series_name, "staffel": str(series_season).zfill(2), "episode": str(series_episode).zfill(2), "titel": series_title}
			timer_description = config.plugins.serienRec.TimerDescription.value.strip().format(**data)
		except Exception as e:
			SRLogger.writeLog("Fehler beim Zusammensetzen der Timerbeschreibung: %s" % str(e))
			timer_description = "S%sE%s - %s" % (str(series_season).zfill(2), str(series_episode).zfill(2), series_title)

		return timer_description

	def activate(self):
		# versuche deaktivierte Timer zu aktivieren oder auf anderer Box zu erstellen
		from enigma import eEPGCache

		deactivatedTimers = self.database.getDeactivatedTimers()
		for deactivatedTimer in deactivatedTimers:
			(serien_name, serien_fsid, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = deactivatedTimer
			label_serie = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
			print("[SerienRecorder] Getting deactivated timer from database (%s)" % label_serie)
			if eit > 0:
				markerType = self.database.getMarkerType(serien_fsid)
				if markerType is None:
					# Marker type not found in database => it's a movie
					markerType = 1
				else:
					markerType = int(markerType)

				recordHandler = NavigationInstance.instance.RecordTimer
				(dirname, dirname_serie) = getDirname(self.database, serien_name, serien_fsid, staffel)
				channelName = STBHelpers.getChannelByRef(self.channelList, stbRef)
				try:
					serien_altname = self.database.getMarkerTimerName(serien_fsid)

					timerFound = False
					# suche in deaktivierten Timern
					for timer in recordHandler.processed_timers:
						if timer and timer.service_ref:
							print("[SerienRecorder] Getting deactivated timer from box (%s) [%s]" % (timer.name, str(timer.begin)))
							if (timer.begin == serien_time) and (timer.eit == eit) and (
									str(timer.service_ref).lower() == stbRef.lower()):
								# versuche deaktivierten Timer zu aktivieren
								timer_name = self.getTimerName(serien_name, staffel, episode, serien_title, serien_altname, markerType)
								SRLogger.writeLog("Versuche deaktivierten Timer zu aktivieren: ' %s ' - %s" % (serien_title, dirname))

								if STBHelpers.checkTuner(str(timer.begin), str(timer.end), str(timer.service_ref)):
									from Components.TimerSanityCheck import TimerSanityCheck
									timer.disabled = False
									timersanitycheck = TimerSanityCheck(recordHandler.timer_list, timer)
									if timersanitycheck.check():
										self.countTimerUpdate += 1
										NavigationInstance.instance.RecordTimer.timeChanged(timer)

										# Eintrag in das timer file
										self.database.activateTimer(serien_fsid, staffel, episode, serien_title,
										                            serien_time, stbRef, webChannel, eit)
										show_start = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
										SRLogger.writeLog("' %s ' - Timer wurde aktiviert → %s %s @ %s" % (
										label_serie, show_start, timer_name, channelName), True)
										timer.log(0, "[SerienRecorder] Activated timer")
										print("[SerienRecorder] Activated timer: %s" % label_serie)
									else:
										timer.disabled = True

								timerFound = True
								break

					if not timerFound:
						# suche in (manuell) aktivierten Timern
						for timer in recordHandler.timer_list:
							if timer and timer.service_ref:
								if (timer.begin == serien_time) and (timer.eit == eit) and (
										str(timer.service_ref).lower() == stbRef.lower()):
									# Eintrag in das timer file
									self.database.activateTimer(serien_fsid, staffel, episode, serien_title,
									                            serien_time, stbRef, webChannel, eit)
									timerFound = True
									break

					if not timerFound:
						# versuche deaktivierten Timer (auf anderer Box) zu erstellen
						(margin_before, margin_after) = self.database.getMargins(serien_fsid, webChannel,
						                                                         config.plugins.serienRec.margin_before.value,
						                                                         config.plugins.serienRec.margin_after.value)

						# get VPS settings for channel
						vpsSettings = self.database.getVPS(serien_fsid, webChannel)

						# get tags from marker
						tags = self.database.getTags(serien_fsid)

						# get addToDatabase for marker
						addToDatabase = self.database.getAddToDatabase(serien_fsid)

						# get autoAdjust for marker
						autoAdjust = self.database.getAutoAdjust(serien_fsid, webChannel)

						# get kind of timer for marker
						kindOfTimer = self.database.getKindOfTimer(serien_fsid, config.plugins.serienRec.kindOfTimer.value)

						epgcache = eEPGCache.getInstance()
						allevents = epgcache.lookupEvent(['IBD', (stbRef, 2, eit, -1)]) or []

						for eventid, begin, duration in allevents:
							if int(begin) == (int(serien_time) + (int(margin_before) * 60)):
								label_serie = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
								timer_name = self.getTimerName(serien_name, staffel, episode, serien_title, serien_altname, markerType)
								timer_description = self.getTimerDescription(serien_name, staffel, episode, serien_title)
								SRLogger.writeLog("Versuche deaktivierten Timer aktiv zu erstellen: ' %s ' - %s" % (serien_title, dirname))
								end_unixtime = int(begin) + int(duration)
								end_unixtime = int(end_unixtime) + (int(margin_after) * 60)
								result = serienRecBoxTimer.addTimer(stbRef, str(serien_time), str(end_unixtime),
								                                    timer_name, timer_description, eit, False, dirname, vpsSettings,
								                                    tags, autoAdjust, kindOfTimer, False, None)
								if result["result"]:
									self.countTimer += 1
									if addToDatabase:
										# Eintrag in das timer file
										self.database.activateTimer(serien_fsid, staffel, episode, serien_title,
										                            serien_time, stbRef, webChannel, eit)
									else:
										self.countBoxOnlyTimer += 1
									show_start = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
									SRLogger.writeLog("' %s ' - Timer wurde angelegt → %s %s @ %s" % (label_serie, show_start, timer_name, channelName), True)
								break

				except:
					pass

	def update(self, timer_list, eit, end_unixtime, new_episode, new_serien_title, new_serien_name, serien_fsid, serien_time, new_staffel, start_unixtime, stbRef, title, dirname, channelName, vpsSettings, markerType, updateFromEPGFailed, timerSeriesName):
		timerUpdated = False
		timerFound = False
		print("[SerienRecorder] Iterate box timers to update timer: " + title)

		for timer in timer_list:
			if timer and timer.service_ref:
				# skip all timer with false service ref
				serien_time_str = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
				timer_begin_str = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(timer.begin)))

				print("[SerienRecorder] Get box timer for update: [%s] [%s / %s] [%s (%s) / %s (%s)]" % (timer.name, str(timer.service_ref).lower(), str(stbRef).lower(), timer_begin_str, str(timer.begin), serien_time_str, str(serien_time)))
				if (str(timer.service_ref).lower() == str(stbRef).lower()) and (str(timer.begin) == str(serien_time)):
					# Timer gefunden, weil auf dem richtigen Sender und Startzeit im Timer entspricht Startzeit in SR DB
					print("[SerienRecorder] Timer found")
					timerFound = True
					# Muss der Timer aktualisiert werden?

					# Event ID
					updateEIT = False
					old_eit = timer.eit
					print("[SerienRecorder] EIT: [%s]" % str(timer.eit) + " / " + str(eit))
					if timer.eit != int(eit) and int(eit) != 0:
						timer.eit = eit
						# Respect VPS settings if eit is available now
						if SerienRecorder.VPSPluginAvailable and eit != 0:
							timer.vpsplugin_enabled = vpsSettings[0]
							timer.vpsplugin_overwrite = timer.vpsplugin_enabled and (not vpsSettings[1])

						updateEIT = True

					# Startzeit
					updateStartTime = False
					if start_unixtime is not None:
						start_unixtime_str = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
						print("[SerienRecorder] Start: [%s (%s)] / %s (%s)" % (timer_begin_str, str(timer.begin), start_unixtime_str, str(start_unixtime)))
						if start_unixtime and timer.begin != start_unixtime and abs(start_unixtime - timer.begin) > 30:
							timer.begin = start_unixtime
							timer.end = end_unixtime
							NavigationInstance.instance.RecordTimer.timeChanged(timer)
							updateStartTime = True
						else:
							# Reset start_unixtime to timer start time to keep database and timer in sync if start time changed lesser than 30 seconds
							start_unixtime = timer.begin

					# Endzeit
					updateEndTime = False
					old_endTime = timer.end
					if end_unixtime is not None:
						timer_end_str = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(end_unixtime)))
						end_unixtime_str = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(end_unixtime)))
						print("[SerienRecorder] End: [%s (%s)] / %s (%s)" % (timer_end_str, str(timer.end), end_unixtime_str, str(end_unixtime)))
						if end_unixtime and timer.end != end_unixtime and abs(end_unixtime - timer.end) > 30:
							timer.begin = start_unixtime
							timer.end = end_unixtime
							NavigationInstance.instance.RecordTimer.timeChanged(timer)
							updateEndTime = True
						else:
							# Reset start_unixtime to timer start time to keep database and timer in sync if start time changed lesser than 30 seconds
							end_unixtime = timer.end

					# Timername
					updateName = False
					old_timername = timer.name
					timer_name = self.getTimerName(new_serien_name, new_staffel, new_episode, new_serien_title, timerSeriesName, markerType)
					print("[SerienRecorder] Name: [%s]" % str(timer.name) + " / " + str(timer_name))
					if timer.name != timer_name:
						timer.name = timer_name
						updateName = True

					# Timerbeschreibung
					updateDescription = False
					old_timerdescription = timer.description
					timer_description = self.getTimerDescription(new_serien_name, new_staffel, new_episode, new_serien_title)
					print("[SerienRecorder] Description: [%s]" % str(timer.description) + " / " + str(timer_description))
					if timer.description != timer_description:
						timer.description = timer_description
						updateDescription = True

					# Directory
					updateDirectory = False
					old_dirname = timer.dirname
					print("[SerienRecorder] Directory: [%s]" % str(timer.dirname) + " / " + str(dirname))
					if timer.dirname != dirname:
						(dirname, dirname_serie) = getDirname(self.database, new_serien_name, serien_fsid, new_staffel)
						STBHelpers.createDirectory(serien_fsid, 0, dirname, dirname_serie)
						timer.dirname = dirname
						updateDirectory = True

					if updateEIT or updateStartTime or updateEndTime or updateName or updateDescription or updateDirectory:
						if not updateFromEPGFailed:
							SRLogger.writeLog("' %s ' @ %s" % (title, channelName), True)
						new_start = time.strftime("%a, %d.%m. - %H:%M", time.localtime(int(start_unixtime)))
						old_start = time.strftime("%a, %d.%m. - %H:%M", time.localtime(int(serien_time)))
						new_end = time.strftime("%a, %d.%m. - %H:%M", time.localtime(int(end_unixtime)))
						old_end = time.strftime("%a, %d.%m. - %H:%M", time.localtime(int(old_endTime)))
						if updateStartTime:
							SRLogger.writeLog("   Startzeit wurde aktualisiert von ' %s ' auf ' %s '" % (old_start, new_start), True)
							timer.log(0, "[SerienRecorder] Changed timer start from %s to %s" % (old_start, new_start))
						if updateEndTime:
							SRLogger.writeLog("   Endzeit wurde aktualisiert von ' %s ' auf ' %s '" % (old_end, new_end), True)
							timer.log(0, "[SerienRecorder] Changed timer end from %s to %s" % (old_end, new_end))
						if updateEIT:
							SRLogger.writeLog("   Event ID wurde aktualisiert von ' %s ' auf ' %s '" % (str(old_eit), str(eit)), True)
							timer.log(0, "[SerienRecorder] Changed event ID from %s to %s" % (str(old_eit), str(eit)))
						if updateName:
							SRLogger.writeLog("   Name wurde aktualisiert von ' %s ' auf ' %s '" % (old_timername, timer_name), True)
							timer.log(0, "[SerienRecorder] Changed name from %s to %s" % (old_timername, timer_name))
						if updateDescription:
							SRLogger.writeLog("   Beschreibung wurde aktualisiert von ' %s ' auf ' %s '" % (old_timerdescription, timer_description), True)
							timer.log(0, "[SerienRecorder] Changed description from %s to %s" % (old_timerdescription, timer_description))
						if updateDirectory:
							SRLogger.writeLog("   Verzeichnis wurde aktualisiert von ' %s ' auf ' %s '" % (old_dirname, dirname), True)
							timer.log(0, "[SerienRecorder] Changed directory from %s to %s" % (old_dirname, dirname))
						self.countTimerUpdate += 1
						NavigationInstance.instance.RecordTimer.saveTimer()
						self.database.updateTimerStartTime(start_unixtime, eit, new_serien_title, serien_time, stbRef)
						timerUpdated = True
					else:
						print("[SerienRecorder] No timer update needed")
						#SRLogger.writeLog("' %s ' - %s" % (title, dirname), True)
						#SRLogger.writeLog("   Timer muss nicht aktualisiert werden", True)
						timerUpdated = True
					break

		# Timer not found - maybe removed from image timer list
		if not timerFound:
			print("[SerienRecorder] Timer not found")
			if not updateFromEPGFailed:
				SRLogger.writeLog("' %s ' @ %s" % (title, channelName), True)
			SRLogger.writeLog("   Timer konnte nicht aktualisiert werden, weil er nicht gefunden werden konnte!", True)

		return timerUpdated

	def search(self, NoOfRecords):
		if NoOfRecords:
			optionalText = " (%s. Wiederholung)" % NoOfRecords
		else:
			optionalText = ""

		SRLogger.writeLog("\n---------' Erstelle Timer%s '---------\n" % optionalText, True)
		print("[SerienRecorder] Creating timers...")

		transmissions = self.tempDB.getTransmissionsOrderedByNumberOfRecordings(NoOfRecords)
		for transmission in transmissions:
			(serien_name, serien_wlid, serien_fsid, markerType, staffel, episode, title, anzahl) = transmission
			(noOfRecords, preferredChannel, useAlternativeChannel) = self.database.getPreferredMarkerChannels(serien_fsid, config.plugins.serienRec.useAlternativeChannel.value, config.plugins.serienRec.NoOfRecords.value)

			(dirname, dirname_serie) = getDirname(self.database, serien_name, serien_fsid, staffel)
			self.enableDirectoryCreation = False

			self.konflikt = ""
			TimerDone = self.doSearch(serien_fsid, staffel, episode, title, optionalText, preferredChannel)
			if not TimerDone and useAlternativeChannel:
				print("[SerienRecorder] Timer not created: Try to create timer on alternative channel")
				if preferredChannel == 1:
					usedChannel = 2
				else:
					usedChannel = 1
				TimerDone = self.doSearch(serien_fsid, staffel, episode, title, optionalText, usedChannel)

			# Setze deaktivierten Timer
			if not TimerDone:
				print("[SerienRecorder] Timer not created: Try to create deactivated timer")
				if str(episode).isdigit():
					if int(episode) == 0:
						transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_fsid, staffel, episode, title)
					else:
						transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_fsid, staffel, episode)
				else:
					transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_fsid, staffel, episode)

				for transmissionForTimer in transmissionsForTimer:
					(current_time, future_time, serien_name, serien_wlid, serien_fsid, markerType, staffel, episode, check_SeasonEpisode, title, label_serie,
					 webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, altstbChannel, altstbRef,
					 dirname, AnzahlAufnahmen, from_time, to_time,
					 vomMerkzettel, excludedWeekdays, updateFromEPG, source) = transmissionForTimer

					print("[SerienRecorder] Transmission for deactivated timer: %s" % label_serie)
					# set the lead/follow-up time
					(margin_before, margin_after) = self.database.getMargins(serien_fsid, webChannel,
					                                                         config.plugins.serienRec.margin_before.value,
					                                                         config.plugins.serienRec.margin_after.value)

					start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
					end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

					timer_start_unixtime = start_unixtime
					timer_end_unixtime = end_unixtime

					if preferredChannel == 1:
						timer_stbChannel = stbChannel
						timer_stbRef = stbRef
					else:
						timer_stbChannel = altstbChannel
						timer_stbRef = altstbRef

					if config.plugins.serienRec.selectBouquets.value and config.plugins.serienRec.preferMainBouquet.value and timer_stbChannel == "":
						timer_stbChannel = altstbChannel
						timer_stbRef = altstbRef

					##############################
					#
					# Setze deaktivierten Timer
					#
					# Ueberpruefe ob der sendetermin zwischen der fromTime und toTime liegt
					if (int(from_time) > 0) or (int(to_time) < (23 * 60) + 59):
						start_time = (time.localtime(int(timer_start_unixtime)).tm_hour * 60) + time.localtime(int(timer_start_unixtime)).tm_min
						end_time = (time.localtime(int(timer_end_unixtime)).tm_hour * 60) + time.localtime(int(timer_end_unixtime)).tm_min
						print("[SerienRecorder] Check allowed time range [%s/%s] - [%s/%s]" % (str(from_time), str(start_time), str(to_time), str(end_time)))
						if not TimeHelpers.allowedTimeRange(from_time, to_time, start_time):
							continue

					if self.doTimer(current_time, future_time, title, staffel, episode, label_serie,
					                timer_start_unixtime, timer_end_unixtime, timer_stbRef,
					                serien_name, serien_wlid, serien_fsid, markerType, webChannel, timer_stbChannel, optionalText,
					                vomMerkzettel, True):
						break

				if len(self.konflikt) > 0:
					if config.plugins.serienRec.showMessageOnConflicts.value:
						timeout = config.plugins.serienRec.showMessageTimeout.value
						if config.plugins.serienRec.showMessageTimeout.value == 0:
							timeout = -1
						self.messageList.append(("Timerkonflikte beim SerienRecorder Suchlauf:\n\n%s" % self.konflikt,
						                         MessageBox.TYPE_INFO, timeout, self.konflikt))
						Notifications.AddPopup("Timerkonflikte beim SerienRecorder Suchlauf:\n\n%s" % self.konflikt,
						                       MessageBox.TYPE_INFO, timeout=timeout, id=self.konflikt)

			##############################
			#
			# erstellt das serien verzeichnis
			if TimerDone and self.enableDirectoryCreation:
				STBHelpers.createDirectory(serien_fsid, markerType, dirname, dirname_serie)

	def doSearch(self, serien_fsid, staffel, episode, title, optionalText, usedChannel):
		print("[SerienRecorder] doSearch: %s" % serien_fsid)
		forceRecordings = []
		forceRecordings_W = []
		eventRecordings = []
		self.konflikt = ""

		TimerDone = False
		if str(episode).isdigit():
			if int(episode) == 0:
				transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_fsid, staffel, episode, title)
			else:
				transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_fsid, staffel, episode)
		else:
			transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_fsid, staffel, episode)

		self.tempDB.beginTransaction()
		for transmissionForTimer in transmissionsForTimer:
			(current_time, future_time, serien_name, serien_wlid, serien_fsid, markerType, staffel, episode, check_SeasonEpisode, title, label_serie,
			 webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, altstbChannel, altstbRef,
			 dirname, AnzahlAufnahmen, from_time, to_time, vomMerkzettel,
			 excludedWeekdays, updateFromEPG, source) = transmissionForTimer

			# set the lead/follow-up time
			(margin_before, margin_after) = self.database.getMargins(serien_fsid, webChannel,
			                                                         config.plugins.serienRec.margin_before.value,
			                                                         config.plugins.serienRec.margin_after.value)

			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

			timer_start_unixtime = start_unixtime
			timer_end_unixtime = end_unixtime

			if usedChannel == 1:
				timer_stbChannel = stbChannel
				timer_stbRef = stbRef
			else:
				timer_stbChannel = altstbChannel
				timer_stbRef = altstbRef

			if config.plugins.serienRec.selectBouquets.value and config.plugins.serienRec.preferMainBouquet.value and timer_stbChannel == "":
				timer_stbChannel = altstbChannel
				timer_stbRef = altstbRef

			# Is channel assigned
			if timer_stbChannel == "":
				SRLogger.writeLogFilter("channels", "' %s ' - Box-Sender nicht der bevorzugten Senderliste zugewiesen → ' %s '" % (label_serie, webChannel))
				# Nicht in bevorzugter Kanalliste - dann gehen wir davon aus, dass kein Timer angelegt werden soll.
				TimerDone = True
				continue

			##############################
			#
			# CHECK
			#
			# ueberprueft anhand des Seriennamen, Season, Episode, ob die serie bereits auf der HDD existiert
			#
			# check ob timer existiert
			startTimeLowBound = int(timer_start_unixtime) - (int(STBHelpers.getEPGTimeSpan()) * 60)
			startTimeHighBound = int(timer_start_unixtime) + (int(STBHelpers.getEPGTimeSpan()) * 60)

			if not (vomMerkzettel and config.plugins.serienRec.forceBookmarkRecording.value):
				if self.database.timerExists(webChannel, serien_fsid, staffel, episode, startTimeLowBound, startTimeHighBound):
					SRLogger.writeLogFilter("added", "' %s ' - Timer für diese Episode%s wurde bereits erstellt → ' %s '" % (label_serie, optionalText, check_SeasonEpisode))
					##self.removeTransmission(episode, serien_fsid, staffel, start_unixtime, stbRef, title)
					TimerDone = True
					continue

				if config.plugins.serienRec.selectBouquets.value and config.plugins.serienRec.preferMainBouquet.value:
					(primary_bouquet_active, secondary_bouquet_active) = self.database.isBouquetActive(webChannel)
					(count_manually, count_primary_bouquet, count_secondary_bouquet) = self.countEpisodeByBouquet(episode, serien_fsid, staffel, title)
					if count_manually >= AnzahlAufnahmen or (count_primary_bouquet >= AnzahlAufnahmen or (secondary_bouquet_active and count_secondary_bouquet >= AnzahlAufnahmen) or (primary_bouquet_active and count_primary_bouquet >= AnzahlAufnahmen)):
						SRLogger.writeLogFilter("added", "' %s ' - Eingestellte Anzahl Timer für diese Episode%s wurden bereits erstellt → ' %s '" % (label_serie, optionalText, check_SeasonEpisode))
						TimerDone = True
						break
				else:
					# check anzahl timer und auf hdd
					bereits_vorhanden, bereits_vorhanden_HDD = self.countEpisode(check_SeasonEpisode, dirname, episode, serien_fsid, serien_name, staffel, title)

					if bereits_vorhanden >= AnzahlAufnahmen:
						SRLogger.writeLogFilter("added", "' %s ' - Eingestellte Anzahl Timer für diese Episode%s wurden bereits erstellt → ' %s '" % (label_serie, optionalText, check_SeasonEpisode))
						TimerDone = True
						break

					if bereits_vorhanden_HDD >= AnzahlAufnahmen:
						SRLogger.writeLogFilter("disk", "' %s ' - Episode%s bereits auf HDD vorhanden → ' %s '" % (label_serie, optionalText, check_SeasonEpisode))
						TimerDone = True
						break

			# check for excluded weekdays - this can be done early, so we can skip all other checks
			# if the transmission date is on an excluded weekday
			if str(excludedWeekdays).isdigit():
				print("[SerienRecorder] - Excluded weekdays check")
				# SRLogger.writeLog("- Excluded weekdays check", True)
				transmissionDate = datetime.date.fromtimestamp((int(timer_start_unixtime)))
				weekday = transmissionDate.weekday()
				print("    Serie = %s, Datum = %s, Wochentag = %s" % (label_serie, time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime))),weekday))
				# SRLogger.writeLog("   Serie = %s, Datum = %s, Wochentag = %s" % (label_serie, time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime))), weekday), True)
				if excludedWeekdays & (1 << weekday) != 0:
					SRLogger.writeLogFilter("timeRange", "' %s ' - Wochentag auf der Ausnahmeliste → ' %s '" % (label_serie, transmissionDate.strftime('%A')))
					TimerDone = True
					continue

			if config.plugins.serienRec.splitEventTimer.value != "0" and '/' in str(episode):
				# Event-Programmierung auflösen → 01/1x02/1x03
				SRLogger.writeLogFilter("timerDebug", "Event-Programmierung gefunden: ' %s S%sE%s - %s '" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
				splitedSeasonEpisodeList, splitedTitleList, useTitles = self.splitEvent(episode, staffel, title)

				alreadyExistsCount = 0
				for idx, entry in enumerate(splitedSeasonEpisodeList):
					splitedTitle = None
					if useTitles:
						splitedTitle = splitedTitleList[idx]

					alreadyExists = False
					if config.plugins.serienRec.selectBouquets.value and config.plugins.serienRec.preferMainBouquet.value:
						(primary_bouquet_active, secondary_bouquet_active) = self.database.isBouquetActive(webChannel)
						(count_manually, count_primary_bouquet, count_secondary_bouquet) = self.countEpisodeByBouquet(entry[1], serien_fsid, entry[0], splitedTitle)
						if count_manually >= 1 or (count_primary_bouquet >= 1 or (secondary_bouquet_active and count_secondary_bouquet >= 1) or (primary_bouquet_active and count_primary_bouquet >= 1)):
							alreadyExists = True
					else:
						alreadyExists = self.database.getNumberOfTimers(serien_fsid, entry[0], entry[1], splitedTitle, False)

					if alreadyExists:
						alreadyExistsCount += 1

				if len(splitedSeasonEpisodeList) == alreadyExistsCount:
					# Alle Einzelfolgen wurden bereits aufgenommen - der Event muss nicht mehr aufgenommen werden.
					SRLogger.writeLogFilter("timerDebug", "   ' %s ' - Timer für Einzelepisoden wurden bereits erstellt → ' %s '" % (serien_name, check_SeasonEpisode))
					TimerDone = True
					continue
				elif config.plugins.serienRec.splitEventTimer.value == "2":
					# Nicht alle Einzelfolgen wurden bereits aufgenommen, es sollen aber Einzelfolgen bevorzugt werden
					SRLogger.writeLogFilter("timerDebug", "   ' %s ' - Versuche zunächst Timer für Einzelepisoden anzulegen" % serien_name)
					eventRecordings.append((title, staffel, episode, label_serie, timer_start_unixtime,
					                        timer_end_unixtime, timer_stbRef, dirname,
					                        serien_name, serien_wlid, serien_fsid, markerType, webChannel, timer_stbChannel, check_SeasonEpisode,
					                        vomMerkzettel, current_time, future_time))
					continue

			##############################
			#
			# CHECK
			#
			# Ueberpruefe ob der sendetermin zwischen der fromTime und toTime liegt und finde Wiederholungen auf dem gleichen Sender
			#
			# prepare valid time range
			if (int(from_time) > 0) or (int(to_time) < (23 * 60) + 59):
				start_time = (time.localtime(int(timer_start_unixtime)).tm_hour * 60) + time.localtime(int(timer_start_unixtime)).tm_min
				end_time = (time.localtime(int(timer_end_unixtime)).tm_hour * 60) + time.localtime(int(timer_end_unixtime)).tm_min
				print("[SerienRecorder] Check allowed time range [%s/%s] - [%s/%s]" % (str(from_time), str(start_time), str(to_time), str(end_time)))

				if not TimeHelpers.allowedTimeRange(from_time, to_time, start_time):
					timeRangeConfigured = "%s:%s - %s:%s" % (str(int(from_time) // 60).zfill(2), str(int(from_time) % 60).zfill(2), str(int(to_time) // 60).zfill(2), str(int(to_time) % 60).zfill(2))
					timeRangeTransmission = "%s:%s - %s:%s" % (str(int(start_time) // 60).zfill(2), str(int(start_time) % 60).zfill(2), str(int(end_time) // 60).zfill(2), str(int(end_time) % 60).zfill(2))
					SRLogger.writeLogFilter("timeRange", "' %s ' - Sendung (%s) nicht in Zeitspanne [%s]" % (label_serie, timeRangeTransmission, timeRangeConfigured))

					# forced recording activated?
					if not self.database.getForceRecording(serien_fsid, config.plugins.serienRec.forceRecording.value):
						continue

					# backup timer data for post-processing
					show_start = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
					SRLogger.writeLogFilter("timeRange", "' %s ' - Backup Timer → %s" % (label_serie, show_start))
					forceRecordings.append((title, staffel, episode, label_serie, timer_start_unixtime,
					                        timer_end_unixtime, timer_stbRef, dirname, serien_name, serien_wlid, serien_fsid,
					                        markerType, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel, current_time, future_time))
					continue

				##############################
				#
				# CHECK
				#
				# Ueberpruefe ob der sendetermin innerhalb der Wartezeit für Wiederholungen liegt
				#
				if self.database.getForceRecording(serien_fsid, config.plugins.serienRec.forceRecording.value):
					TimeSpan_time = int(future_time) + (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400
					if int(timer_start_unixtime) > int(TimeSpan_time):
						# backup timer data for post processing
						show_start = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
						SRLogger.writeLogFilter("timeRange", "' %s ' - Backup Timer → %s" % (label_serie, show_start))
						forceRecordings_W.append((title, staffel, episode, label_serie, timer_start_unixtime,
						                          timer_end_unixtime, timer_stbRef, dirname, serien_name, serien_wlid, serien_fsid,
						                          markerType, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel, current_time, future_time))
						continue

			##############################
			#
			# Setze Timer
			#
			print("[SerienRecorder] Try to create timer")
			if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime,
			                timer_end_unixtime, timer_stbRef, serien_name, serien_wlid, serien_fsid, markerType, webChannel,
			                timer_stbChannel, optionalText, vomMerkzettel):
				#self.removeTransmission(episode, serien_fsid, staffel, timer_start_unixtime, timer_stbRef, title)
				TimerDone = True
				break

		### end of for loop
		self.tempDB.commitTransaction()

		if not TimerDone:
			# post-processing for rerun
			for title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, dirname, serien_name, serien_wlid, serien_fsid, markerType, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel, current_time, future_time in forceRecordings_W:
				if config.plugins.serienRec.selectBouquets.value and config.plugins.serienRec.preferMainBouquet.value:
					(primary_bouquet_active, secondary_bouquet_active) = self.database.isBouquetActive(webChannel)
					(count_manually, count_primary_bouquet, count_secondary_bouquet) = self.countEpisodeByBouquet(episode, serien_fsid, staffel, title)
					if count_manually >= 1 or (count_primary_bouquet >= 1 or (secondary_bouquet_active and count_secondary_bouquet >= 1) or (primary_bouquet_active and count_primary_bouquet >= 1)):
						continue
				else:
					if self.database.getNumberOfTimers(serien_fsid, staffel, episode, title, False):
						continue
				# programmiere Timer (Wiederholung)
				print("[SerienRecorder] Try to create timer (rerun)")
				if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime,
				                timer_end_unixtime, timer_stbRef, serien_name, serien_wlid, serien_fsid, markerType, webChannel,
				                timer_stbChannel, optionalText, vomMerkzettel):
					#self.removeTransmission(episode, serien_fsid, staffel, timer_start_unixtime, timer_stbRef, title)
					TimerDone = True

		if not TimerDone:
			# post-processing for forced recordings
			for title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, dirname, serien_name, serien_wlid, serien_fsid, markerType, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel, current_time, future_time in forceRecordings:
				if config.plugins.serienRec.selectBouquets.value and config.plugins.serienRec.preferMainBouquet.value:
					(primary_bouquet_active, secondary_bouquet_active) = self.database.isBouquetActive(webChannel)
					(count_manually, count_primary_bouquet, count_secondary_bouquet) = self.countEpisodeByBouquet(episode, serien_fsid, staffel, title)
					if count_manually >= 1 or (count_primary_bouquet >= 1 or (secondary_bouquet_active and count_secondary_bouquet >= 1) or (primary_bouquet_active and count_primary_bouquet >= 1)):
						continue
				else:
					if self.database.getNumberOfTimers(serien_fsid, staffel, episode, title, False):
						continue
				show_start = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
				SRLogger.writeLogFilter("timeRange", "' %s ' - Keine Wiederholung gefunden! → %s" % (label_serie, show_start), True)
				# programmiere Timer
				print("[SerienRecorder] Try to create timer (force recording)")
				if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime,
				                timer_end_unixtime, timer_stbRef, serien_name, serien_wlid, serien_fsid, markerType, webChannel,
				                timer_stbChannel, optionalText, vomMerkzettel):
					#self.removeTransmission(episode, serien_fsid, staffel, timer_start_unixtime, timer_stbRef, title)
					TimerDone = True

		if not TimerDone:
			# post-processing event recordings
			for singleTitle, staffel, singleEpisode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, dirname, serien_name, serien_wlid, serien_fsid, markerType, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel, current_time, future_time in eventRecordings[:]:
				if self.shouldCreateEventTimer(serien_fsid, staffel, singleEpisode, singleTitle):
					show_start = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
					SRLogger.writeLogFilter("timerDebug", "   ' %s ' - Einzelepisoden nicht gefunden! → %s" % (label_serie, show_start),
					                  True)
					# programmiere Timer
					print("[SerienRecorder] Try to create timer (event)")
					if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime,
					                timer_end_unixtime, timer_stbRef, serien_name, serien_wlid, serien_fsid, markerType, webChannel,
					                timer_stbChannel, optionalText, vomMerkzettel):
						TimerDone = True

		print("[SerienRecorder] doSearch: TimerDone = [%s]" % str(TimerDone))
		return TimerDone

	def countEpisode(self, check_SeasonEpisode, dirname, episode, serien_fsid, serien_name, season, title):
		print("[SerienRecorder] countEpisode: %s (%s) S%sE%s - %s" % (serien_name, serien_fsid, str(season), str(episode), title))
		bereits_vorhanden_HDD = 0
		if str(episode).isdigit():
			if int(episode) == 0:
				bereits_vorhanden = self.database.getNumberOfTimers(serien_fsid, season, episode, title, True)
				if config.plugins.serienRec.sucheAufnahme.value:
					bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False, title)
			else:
				bereits_vorhanden = self.database.getNumberOfTimers(serien_fsid, season, episode, None, True)
				if config.plugins.serienRec.sucheAufnahme.value:
					bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False)
		else:
			bereits_vorhanden = self.database.getNumberOfTimers(serien_fsid, season, episode, None, True)
			if config.plugins.serienRec.sucheAufnahme.value:
				bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False)
		print("[SerienRecorder] countEpisode: %d/%d" % (bereits_vorhanden, bereits_vorhanden_HDD))
		return bereits_vorhanden, bereits_vorhanden_HDD

	def countEpisodeByBouquet(self, episode, serien_fsid, season, title):
		if str(episode).isdigit():
			if int(episode) == 0:
				(count_manually, count_primary_bouquet, count_secondary_bouquet) = self.database.getNumberOfTimersByBouquet(serien_fsid, season, episode, title)
			else:
				(count_manually, count_primary_bouquet, count_secondary_bouquet) = self.database.getNumberOfTimersByBouquet(serien_fsid, season, episode)
		else:
			(count_manually, count_primary_bouquet, count_secondary_bouquet) = self.database.getNumberOfTimersByBouquet(serien_fsid, season, episode)
		return count_manually, count_primary_bouquet, count_secondary_bouquet

	def removeTransmission(self, episode, serien_fsid, season, timer_start_unixtime, timer_stbRef, title):
		if str(episode).isdigit():
			if int(episode) == 0:
				self.tempDB.removeTransmission(serien_fsid, season, episode, title, timer_start_unixtime, timer_stbRef)
			else:
				self.tempDB.removeTransmission(serien_fsid, season, episode, None, timer_start_unixtime, timer_stbRef)
		else:
			self.tempDB.removeTransmission(serien_fsid, season, episode, None, timer_start_unixtime, timer_stbRef)

	def doTimer(self, current_time, future_time, title, season, episode, label_serie, start_unixtime, end_unixtime,
	            stbRef, serien_name, serien_wlid, serien_fsid, markerType, webChannel, stbChannel, optionalText='',
	            vomMerkzettel=False, tryDisabled=False):

		print("[SerienRecorder] doTimer: %s [%s]" % (label_serie, str(start_unixtime)))
		(margin_before, margin_after) = self.database.getMargins(serien_fsid, webChannel,
		                                                         config.plugins.serienRec.margin_before.value,
		                                                         config.plugins.serienRec.margin_after.value)

		epgSeriesName = self.database.getMarkerEPGName(serien_fsid)
		if len(epgSeriesName) == 0 or epgSeriesName == serien_name:
			epgSeriesName = ""

		timerSeriesName = self.database.getMarkerTimerName(serien_fsid)
		if len(timerSeriesName) == 0 or timerSeriesName == serien_name:
			timerSeriesName = ""

		# try to get eventID (eit) from epgCache
		eit = 0
		if self.database.getUpdateFromEPG(serien_fsid, config.plugins.serienRec.eventid.value):
			print("[SerienRecorder] Update data from EPG")
			eit, start_unixtime, end_unixtime = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, serien_name, epgSeriesName, stbRef)

		if eit > 0:
			# If event found in EPG we get start- and endtimes from EPG without margins → add margins
			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

		show_start = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
		show_end = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(end_unixtime)))

		if int(start_unixtime) > int(future_time):
			show_future = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(future_time)))
			SRLogger.writeLogFilter("timeLimit", "' %s ' - Timer wird evtl. später angelegt → Sendetermin: %s - Erlaubte Zeitspanne bis %s" % (label_serie, show_start, show_future))
			return True
		if int(current_time) > int(start_unixtime):
			show_current = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(current_time)))
			SRLogger.writeLogFilter("timeLimit", "' %s ' - Der Sendetermin liegt in der Vergangenheit: %s - Aktuelles Datum: %s" % (label_serie, show_start, show_current))
			return True

		# get VPS settings for channel
		vpsSettings = self.database.getVPS(serien_fsid, webChannel)

		# get tags from marker
		tags = self.database.getTags(serien_fsid)

		# get addToDatabase for marker
		addToDatabase = self.database.getAddToDatabase(serien_fsid)

		# get autoAdjust for marker
		autoAdjust = self.database.getAutoAdjust(serien_fsid, webChannel)

		# get kind of timer for marker
		kindOfTimer = self.database.getKindOfTimer(serien_fsid, config.plugins.serienRec.kindOfTimer.value)

		# install missing covers
		(dirname, dirname_serie) = getDirname(self.database, serien_name, serien_fsid, season)
		STBHelpers.createDirectory(serien_fsid, markerType, dirname, dirname_serie, True)

		# versuche timer anzulegen
		# setze strings für addtimer
		if STBHelpers.checkTuner(start_unixtime, end_unixtime, stbRef):
			timer_name = self.getTimerName(serien_name, season, episode, title, timerSeriesName, markerType)
			timer_description = self.getTimerDescription(serien_name, season, episode, title)

			result = serienRecBoxTimer.addTimer(stbRef, str(start_unixtime), str(end_unixtime), timer_name,
		                                        timer_description, eit, False, dirname, vpsSettings, tags, autoAdjust, kindOfTimer, tryDisabled, None)
			print("[SerienRecorder] addTimer result = [%s]" % str(result["result"]))

			if result["result"]:
				self.countTimer += 1
				# Eintrag in die Datenbank
				self.addTimerToDB(serien_name, serien_wlid, serien_fsid, season, episode, title, start_unixtime, stbRef, webChannel, eit, addToDatabase)
				if vomMerkzettel:
					self.countTimerFromWishlist += 1
					SRLogger.writeLog("' %s ' - Timer (vom Merkzettel) wurde angelegt%s → [%s] - [%s] %s @ %s" % (label_serie, optionalText, show_start, show_end, timer_name, stbChannel), True)
					self.database.updateBookmark(serien_fsid, season, episode)
					self.database.removeBookmark(serien_fsid, season, episode)
				else:
					SRLogger.writeLog("' %s ' - Timer wurde angelegt%s → [%s] - [%s] %s @ %s" % (label_serie, optionalText, show_start, show_end, timer_name, stbChannel), True)
					# Event-Programmierung verarbeiten
					if (config.plugins.serienRec.splitEventTimer.value == "1" or (config.plugins.serienRec.splitEventTimer.value == "2" and config.plugins.serienRec.addSingleTimersForEvent.value == "1")) and '/' in str(episode):
						splitedSeasonEpisodeList, splitedTitleList, useTitles = self.splitEvent(episode, season, title)
						for idx, entry in enumerate(splitedSeasonEpisodeList):
							splitedTitle = None
							if useTitles:
								splitedTitle = splitedTitleList[idx]
							alreadyExists = 0
							if config.plugins.serienRec.selectBouquets.value and config.plugins.serienRec.preferMainBouquet.value:
								(primary_bouquet_active, secondary_bouquet_active) = self.database.isBouquetActive(webChannel)
								(count_manually, count_primary_bouquet, count_secondary_bouquet) = self.countEpisodeByBouquet(entry[1], serien_fsid, entry[0], splitedTitle)
								if count_manually >= 1 or ((secondary_bouquet_active and count_secondary_bouquet >= 1) or (primary_bouquet_active and count_primary_bouquet >= 1)):
									alreadyExists = 1
							else:
								alreadyExists = self.database.getNumberOfTimers(serien_fsid, entry[0], entry[1], splitedTitle, False)
							if alreadyExists == 0 and addToDatabase:
								splitedTitle = "dump"
								if useTitles:
									splitedTitle = splitedTitleList[idx]

								# Nicht vorhandene Einzelfolgen als bereits aufgenommen markieren
								self.database.addToTimerList(serien_name, serien_fsid, entry[1], entry[1], entry[0], splitedTitle, int(time.time() - 10), "", "", 0, 1)
								SRLogger.writeLogFilter("timerDebug", "   Für die Einzelepisode wird kein Timer mehr erstellt: %s S%sE%s - %s" % (serien_name, str(entry[0]).zfill(2), str(entry[1]).zfill(2), splitedTitle))

				self.enableDirectoryCreation = True
				return True
			elif not tryDisabled:
				self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
				print("[SerienRecorder] ' %s ' - ACHTUNG! → %s" % (label_serie, result["message"]))
				SRLogger.writeLog("' %s ' - Timer konnte nicht angelegt werden%s → [%s] - [%s] %s @ %s" % (
				label_serie, optionalText, show_start, show_end, timer_name, stbChannel), True)
				SRLogger.writeLog("' %s ' - ACHTUNG! → %s" % (label_serie, result["message"]), True)
			else:
				#self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
				#print("[SerienRecorder] ' %s ' - ACHTUNG! → %s" % (label_serie, result["message"]))
				#SRLogger.writeLog("' %s ' - ACHTUNG! → %s" % (label_serie, result["message"]), True)
				dbMessage = result["message"].replace("In Konflikt stehende Timer vorhanden!", "").strip()

				result = serienRecBoxTimer.addTimer(stbRef, str(start_unixtime), str(end_unixtime), timer_name,
				                                    timer_description, eit, True,
				                                    dirname, vpsSettings, tags, autoAdjust, kindOfTimer, False, None)
				print("[SerienRecorder] addTimer (deactivated) result = [%s]" % str(result["result"]))
				if result["result"]:
					self.countNotActiveTimer += 1
					# Eintrag in die Datenbank
					self.addTimerToDB(serien_name, serien_wlid, serien_fsid, season, episode, title, start_unixtime, stbRef, webChannel, eit, addToDatabase, False)
					self.database.addTimerConflict(dbMessage, start_unixtime, webChannel)
					if vomMerkzettel:
						self.countTimerFromWishlist += 1
						SRLogger.writeLog(
							"' %s ' - Timer (vom Merkzettel) wurde deaktiviert angelegt%s → [%s] - [%s] %s @ %s" % (
							label_serie, optionalText, show_start, show_end, timer_name, stbChannel), True)
					else:
						SRLogger.writeLog("' %s ' - Timer wurde deaktiviert angelegt%s → [%s] - [%s] %s @ %s" % (
						label_serie, optionalText, show_start, show_end, timer_name, stbChannel), True)
					self.enableDirectoryCreation = True
					return True
				else:
					self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
					print("[SerienRecorder] ' %s ' - ACHTUNG! → %s" % (label_serie, result["message"]))
					SRLogger.writeLog("' %s ' - ACHTUNG! → %s" % (label_serie, result["message"]), True)
		else:
			print("[SerienRecorde] Tuner belegt ' %s %s '" % (label_serie, show_start))
			SRLogger.writeLog("Tuner belegt: ' %s ' %s" % (label_serie, show_start), True)
		return False

	def addTimerToDB(self, serien_name, serien_wlid, serien_fsid, staffel, episode, title, start_time, stbRef, webChannel, eit, addToDatabase, TimerAktiviert=True):
		seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
		channelName = STBHelpers.getChannelByRef(self.channelList, stbRef)
		if not addToDatabase:
			print("[SerienRecorder] Timer nur auf der Box angelegt: ' %s - %s - %s @ %s '" % (serien_name, seasonEpisodeString, title, channelName))
			SRLogger.writeLogFilter("timerDebug", "   Timer nur auf der Box angelegt: ' %s - %s - %s @ %s '" % (serien_name, seasonEpisodeString, title, channelName))
			self.countBoxOnlyTimer += 1
		else:
			#startTimeLowBound = int(start_time) - (int(STBHelpers.getEPGTimeSpan()) * 60)
			#startTimeHighBound = int(start_time) + (int(STBHelpers.getEPGTimeSpan()) * 60)

			# if self.database.timerExistsByServiceRef(serien_fsid, stbRef, startTimeLowBound, startTimeHighBound):
			# 	self.database.updateTimerEIT(serien_fsid, stbRef, eit, startTimeLowBound, startTimeHighBound, TimerAktiviert)
			# 	print("[SerienRecorder] Ein Timer für diese Serie ist zu dieser Startzeit bereits vorhanden: ' %s %s - %s '" % (serien_name, seasonEpisodeString, title))
			# 	SRLogger.writeLog("   Ein Timer für diese Serie ist zu dieser Startzeit bereits vorhanden: ' %s %s - %s '" % (serien_name, seasonEpisodeString, title))
			# else:

			self.database.addToTimerList(serien_name, serien_fsid, episode, episode, staffel, title, start_time, stbRef, webChannel, eit, TimerAktiviert)
			print("[SerienRecorder] Timer angelegt: ' %s - %s - %s @ %s '" % (serien_name, seasonEpisodeString, title, channelName))
			SRLogger.writeLogFilter("timerDebug", "   Timer angelegt: ' %s - %s - %s @ %s '" % (serien_name, seasonEpisodeString, title, channelName))


	def shouldCreateEventTimer(self, serien_fsid, season, episode, title):
		if self.database.getNumberOfTimers(serien_fsid, season, episode, title, False):
			return False

		result = True
		if config.plugins.serienRec.splitEventTimer.value != "2" and '/' in str(episode):
			# Event-Programmierung auflösen → 01/1x02/1x03
			splitedSeasonEpisodeList, splitedTitleList, useTitles = self.splitEvent(episode, season, title)

			# Möglichst die Einzelfolgen bevorzugen und Event ignorieren
			alreadyExistsCount = 0
			for idx,entry in enumerate(splitedSeasonEpisodeList):
				title = None
				if useTitles:
					title = splitedTitleList[idx]
				alreadyExists = self.database.getNumberOfTimers(serien_fsid, entry[0], entry[1], title, False)
				if alreadyExists:
					alreadyExistsCount += 1

			if alreadyExistsCount == len(splitedSeasonEpisodeList):
				result = False

		return result

	def adjustEPGtimes(self, current_time):
		print("[SerienRecorder] --------------- Refresh timer ---------------")
		SRLogger.writeLog("\n---------' Aktualisiere Timer '---------\n", True)
		recordHandler = NavigationInstance.instance.RecordTimer
		#SRLogger.writeLog("<< Suche im EPG anhand der Uhrzeit", True)

		eventsNotFound = ""
		timers = self.database.getAllTimer(current_time)
		for timer in timers:
			try:
				(row_id, serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit, active, serien_fsid) = timer
			except ValueError as e:
				continue

			channelName = STBHelpers.getChannelByRef(self.channelList, stbRef)
			title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
			serien_time_str = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
			print("[SerienRecorder] =======================================================")
			print("[SerienRecorder] Update request for timer: %s [%s (%d)] @ %s" % (title, serien_time_str, serien_time, channelName))

			if channelName is None:
				SRLogger.writeLog("' %s '" % title, True)
				SRLogger.writeLog("   Timer konnte nicht aktualisiert werden, der zugeordnete Box-Sender konnte nicht gefunden werden @ %s" % webChannel)
				continue

			markerType = self.database.getMarkerType(serien_fsid)
			if markerType is None:
				# Marker type not found in database => it's a movie
				markerType = 1
			else:
				markerType = int(markerType)

			(margin_before, margin_after) = self.database.getMargins(serien_fsid, webChannel, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)
			epg_timespan = int(STBHelpers.getEPGTimeSpan() * 60)
			# If the transmission starts before the start time set in the timer, the getTransmission query doesn't return this transmission,
			# so we use the configured EPG timespan to make sure the transmission is considered
			db_serien_time = int(serien_time) + (int(margin_before) * 60) - epg_timespan
			transmission = self.tempDB.getTransmissionForTimerUpdate(serien_fsid, staffel, episode, db_serien_time, webChannel)
			if transmission:
				(new_serien_name, serien_wlid, serien_fsid, new_staffel, new_episode, new_serien_title, new_serien_time, new_serien_endtime, updateFromEPG) = transmission
				new_serien_time_str = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(new_serien_time)))
				title = "%s - S%sE%s - %s" % (new_serien_name, str(new_staffel).zfill(2), str(new_episode).zfill(2), new_serien_title)
				print("[SerienRecorder] Get transmission from database: %s [%s (%d)]" % (title, new_serien_time_str, new_serien_time))
			else:
				print("[SerienRecorder] No transmission found for timer - maybe removed at Wunschliste")
				new_serien_name = serien_name
				new_staffel = staffel
				new_episode = episode
				new_serien_title = serien_title
				new_serien_time = 0
				new_serien_endtime = 0
				new_serien_time_str = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(new_serien_time)))

			updateFromEPG = self.database.getUpdateFromEPG(serien_fsid, config.plugins.serienRec.eventid.value)
			title = "%s - S%sE%s - %s" % (new_serien_name, str(new_staffel).zfill(2), str(new_episode).zfill(2), new_serien_title)

			(dirname, dirname_serie) = getDirname(self.database, new_serien_name, serien_fsid, new_staffel)

			if new_serien_time > 0 and new_serien_endtime > 0:
				start_unixtime = new_serien_time - (int(margin_before) * 60)
				end_unixtime = new_serien_endtime + (int(margin_after) * 60)
			else:
				start_unixtime = end_unixtime = None

			updateFromEPGFailed = False
			if updateFromEPG:
				epgSeriesName = self.database.getMarkerEPGName(serien_fsid)
				if len(epgSeriesName) == 0 or epgSeriesName == serien_name:
					epgSeriesName = ""

				# event_matches = STBHelpers.getEPGEvent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				(no_events_found, event_matches) = STBHelpers.getEPGEvent(stbRef, new_serien_name, epgSeriesName, int(serien_time)+(int(margin_before) * 60))
				new_event_matches = None
				no_new_events_found = True
				#if serien_time != new_serien_time and new_serien_time != 0:
				if no_events_found and new_serien_time != 0:
					print("[SerienRecorder] Transmission not found at [%s (%d)] => try another transmission [%s (%d)]" % (serien_time_str, serien_time, new_serien_time_str, new_serien_time))
					(no_new_events_found, new_event_matches) = STBHelpers.getEPGEvent(stbRef, new_serien_name, epgSeriesName, int(new_serien_time)+(int(margin_before) * 60))

				if no_events_found and no_new_events_found:
					print("[SerienRecorder] Failed to update timer, not enough EPG data")
					SRLogger.writeLog("' %s ' @ %s" % (title, channelName), True)
					SRLogger.writeLog("   Timer konnte nicht aus dem EPG aktualisiert werden, nicht genügend EPG Daten vorhanden @ %s" % channelName)
					updateFromEPGFailed = True
					#continue
				else:
					if new_event_matches and len(new_event_matches) > 0 and (not event_matches or (event_matches and len(event_matches) == 0)):
						# Old event not found but new one with different start time
						print("[SerienRecorder] Event could be found in EPG, but a repetition at a different time")
						SRLogger.writeLog("' %s ' @ %s" % (title, channelName), True)
						SRLogger.writeLog("   Die Sendung wurde im EPG nicht gefunden, es wurde aber eine Wiederholung zu einer anderen Zeit gefunden @ %s" % channelName)
						event_matches = new_event_matches
						updateFromEPGFailed = True

					if event_matches and len(event_matches) > 0:
						for event_entry in event_matches:
							eit = int(event_entry[0])
							start_unixtime = int(event_entry[2]) - (int(margin_before) * 60)
							end_unixtime = int(event_entry[2]) + int(event_entry[3]) + (int(margin_after) * 60)
							break
					else:
						print("[SerienRecorder] Failed to update timer, event not found in time range")
						SRLogger.writeLog("' %s ' @ %s" % (title, channelName), True)
						SRLogger.writeLog("   Timer konnte nicht aus dem EPG aktualisiert werden, die Sendung wurde im Zeitfenster nicht gefunden @ %s" % channelName)
						eventsNotFound += "%s\n" % title
						updateFromEPGFailed = True
						#continue


			print("[SerienRecorder] Try to modify enigma2 timer: %s [%d]" % (title, serien_time))
			try:
				# get VPS settings for channel
				vpsSettings = self.database.getVPS(serien_fsid, webChannel)

				# get timer series name
				timerSeriesName = self.database.getMarkerTimerName(serien_fsid)

				# update box timer
				self.update(recordHandler.timer_list + recordHandler.processed_timers, eit, end_unixtime, new_episode,
				            new_serien_title, serien_name, serien_fsid, serien_time,
				            new_staffel, start_unixtime, stbRef, title,
				            dirname, channelName, vpsSettings, markerType, updateFromEPGFailed, timerSeriesName)

			except Exception as e:
				print("[SerienRecorder] Modifying enigma2 timer failed: %s [%d] (%s)" % (title, serien_time, str(e)))
				SRLogger.writeLog("' %s ' @ %s" % (title, channelName), True)
				SRLogger.writeLog("   Timeraktualisierung fehlgeschlagen @ %s" % channelName, True)

		# Notification event not found
		if len(eventsNotFound) > 0:
			if config.plugins.serienRec.showMessageOnEventNotFound.value:
				timeout = config.plugins.serienRec.showMessageTimeout.value
				if config.plugins.serienRec.showMessageTimeout.value == 0:
					timeout = -1
				self.messageList.append(("Folgende Sendungen wurden im EPG nicht gefunden:\n\n%s" % eventsNotFound,
				                         MessageBox.TYPE_INFO, timeout, eventsNotFound))
				Notifications.AddPopup("Folgende Sendungen wurden im EPG nicht gefunden:\n\n%s" % eventsNotFound,
				                       MessageBox.TYPE_INFO, timeout=timeout, id="eventsNotFound")

	@staticmethod
	def splitEvent(episode, staffel, title):
		splitedSeasonEpisodeList = []
		if 'x' in str(episode):
			seasonEpisodeList = episode.split('/')
			for seasonEpisode in seasonEpisodeList:
				if not 'x' in seasonEpisode:
					seasonEpisode = str(staffel) + 'x' + str(seasonEpisode)
				splitedSeasonEpisodeList.append(seasonEpisode.split('x'))
		else:
			seasonEpisodeList = episode.split('/')
			for seasonEpisode in seasonEpisodeList:
				seasonEpisode = str(staffel) + 'x' + str(seasonEpisode)
				splitedSeasonEpisodeList.append(seasonEpisode.split('x'))
		useTitles = True
		splitedTitleList = title.split('/')
		if not config.plugins.serienRec.splitEventTimerCompareTitle.value or len(splitedTitleList) != len(splitedSeasonEpisodeList):
			useTitles = False
		return splitedSeasonEpisodeList, splitedTitleList, useTitles


# ---------------------------------- Timer Functions ------------------------------------------

class serienRecBoxTimer:

	def __init__(self):
		pass

	@staticmethod
	def getTimersTime():

		recordHandler = NavigationInstance.instance.RecordTimer
		timers = []

		for timer in recordHandler.timer_list:
			timers.append((timer.name, timer.begin, timer.end, timer.service_ref))
		return timers

	@staticmethod
	def getTimersList():

		recordHandler = NavigationInstance.instance.RecordTimer

		timers = []
		serienRec_chlist = STBHelpers.buildSTBChannelList()

		for timer in recordHandler.timer_list:
			if timer and timer.service_ref and timer.eit is not None:

				location = 'NULL'
				recordedfile = 'NULL'
				if timer.dirname:
					location = timer.dirname
				channel = STBHelpers.getChannelByRef(serienRec_chlist, str(timer.service_ref))
				if channel:
					# recordedfile = getRecordFilename(timer.name,timer.description,timer.begin,channel)
					recordedfile = str(timer.begin) + " - " + str(timer.service_ref) + " - " + str(timer.name)
				timers.append({
					"title": timer.name,
					"description": timer.description,
					"id_channel": 'NULL',
					"channel": channel,
					"id_genre": 'NULL',
					"begin": timer.begin,
					"end": timer.end,
					"serviceref": timer.service_ref,
					"location": location,
					"recordedfile": recordedfile,
					"tags": timer.tags,
					"eit": timer.eit
				})
		return timers

	@staticmethod
	def removeTimerEntry(serien_name, start_time, eit=0):

		recordHandler = NavigationInstance.instance.RecordTimer
		removed = False
		print("[SerienRecorder] try to remove enigma2 Timer:", serien_name, start_time)

		# entferne aktivierte Timer
		for timer in recordHandler.timer_list:
			if timer and timer.service_ref:
				if eit > 0:
					if timer.eit == eit:
						recordHandler.removeEntry(timer)
						removed = True
						break
				if str(timer.name) == serien_name and int(timer.begin) == int(start_time):
					# if str(timer.service_ref) == entry_dict['channelref']:
					recordHandler.removeEntry(timer)
					removed = True

		# entferne deaktivierte Timer
		if not removed:
			for timer in recordHandler.processed_timers:
				if timer and timer.service_ref:
					if eit > 0:
						if timer.eit == eit:
							recordHandler.removeEntry(timer)
							removed = True
							break
					if str(timer.name) == serien_name and int(timer.begin) == int(start_time):
						# if str(timer.service_ref) == entry_dict['channelref']:
						recordHandler.removeEntry(timer)
						removed = True

		return removed

	@staticmethod
	def addTimer(serviceref, begin, end, name, description, eit, disabled, dirname, vpsSettings, tags, autoAdjust, kindOfTimer, silent, logentries=None):
		recordHandler = NavigationInstance.instance.RecordTimer

		if not silent:
			if disabled:
				print("[SerienRecorder] Try to create deactivated timer: %s [%s]" % (name, dirname))
				SRLogger.writeLogFilter("timerDebug", "Versuche deaktivierten Timer anzulegen: ' %s ' - %s" % (name, dirname))
			else:
				print("[SerienRecorder] Try to create timer: %s [%s]" % (name, dirname))
				SRLogger.writeLogFilter("timerDebug", "Versuche Timer anzulegen: ' %s ' - %s" % (name, dirname))

		try:
			timer = RecordTimerEntry(ServiceReference(serviceref), int(begin), int(end), name, description, int(eit))

			# Set disabled
			print("[SerienRecorder] Setting disabled")
			timer.disabled = disabled

			# Set afterEvent
			print("[SerienRecorder] Setting afterEvent")
			timer.afterEvent = int(config.plugins.serienRec.afterEvent.value)

			# Set dirname
			print("[SerienRecorder] Setting dirname")
			timer.dirname = dirname

			# Set kind of timer
			if kindOfTimer == "1":
				# Zap
				print("[SerienRecorder] Setting justplay")
				timer.justplay = True

			if kindOfTimer == "2":
				# Zap and record
				if hasattr(timer, 'zapbeforerecord'):
					print("[SerienRecorder] Setting zapbeforerecord")
					timer.zapbeforerecord = True
				if hasattr(timer, 'always_zap'):
					print("[SerienRecorder] Setting always_zap")
					timer.always_zap = True

			if kindOfTimer == "4":
				# Remind
				if hasattr(timer, 'justremind'):
					print("[SerienRecorder] Setting justremind")
					timer.justremind = True
				else:
					print("[SerienRecorder] Setting justplay")
					timer.justplay = True


			print("[SerienRecorder] Setting repeated")
			timer.repeated = 0

			# Set autoAdjust
			print("[SerienRecorder] Setting autoAdjust")
			if hasattr(timer, 'autoadjust') and autoAdjust is not None:
				print("[SerienRecorder] Current autoAdjust for timer [%s]: %s" % (name, str(timer.autoadjust)))
				print("[SerienRecorder] autoAdjust is: %s" % str(autoAdjust))
				timer.autoadjust = autoAdjust
				print("[SerienRecorder] Set autoAdjust for timer [%s] to: %s" % (name, str(timer.autoadjust)))

			# Add tags
			print("[SerienRecorder] Getting tags")
			timerTags = timer.tags[:]
			timerTags.append('SerienRecorder')
			if len(tags) != 0:
				timerTags.extend(tags)
			print("[SerienRecorder] Setting tags")
			timer.tags = timerTags

			# If eit = 0 the VPS plugin won't work properly for this timer, so we have to disable VPS in this case.
			if SerienRecorder.VPSPluginAvailable and eit != 0:
				print("[SerienRecorder] Getting VPS")
				timer.vpsplugin_enabled = vpsSettings[0]
				timer.vpsplugin_overwrite = timer.vpsplugin_enabled and (not vpsSettings[1])

			if SerienRecorder.VPSPluginAvailable and vpsSettings[0] and eit == 0:
				print("[SerienRecorder] Failed to set VPS for timer [%s] - missing event ID" % name)
				SRLogger.writeLogFilter("timerDebug", "Event ID ist 0 - VPS kann nicht am Timer gesetzt werden: ' %s ' - %s" % (name, dirname))

			if logentries:
				print("[SerienRecorder] Getting log entries")
				timer.log_entries = logentries

			print("[SerienRecorder] Setting RecordTimerEntry to recordHandler")
			conflicts = recordHandler.record(timer)
			if conflicts:
				errors = []
				for conflict in conflicts:
					errors.append(conflict.name)

				return {
					"result": False,
					"message": "In Konflikt stehende Timer vorhanden! %s" % " / ".join(errors)
				}
			else:
				timer.log(0, "[SerienRecorder] Timer angelegt")

		except Exception as e:
			print(("[%s] <%s>" % (__name__, e)))
			return {
				"result": False,
				"message": "Timer konnte nicht angelegt werden '%s'!" % e
			}


		# Timer created successful
		return {
			"result": True,
			"message": "Timer '%s' angelegt" % name,
			"eit": eit
		}

