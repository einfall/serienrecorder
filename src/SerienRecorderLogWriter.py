﻿# coding=utf-8

# This file contain logger functions

from Components.config import config
from Screens.MessageBox import MessageBox
from Tools import Notifications
from Tools.Directories import fileExists

import os, shutil, datetime, time

SERIENRECORDER_LOGFILENAME = "SerienRecorder.log"
SERIENRECORDER_LONG_LOGFILENAME = "SerienRecorder_%s%s%s%s%s.log"
SERIENRECORDER_TEST_LOGFILEPATH = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/TestLogs"

class SRLogger:
	def __init__(self):
		pass

	@classmethod
	def writeLog(cls, text, forceWrite=False):
		logFile = SRLogger.getLogFilePath()
		if config.plugins.serienRec.writeLog.value or forceWrite:
			try:
				open(logFile, 'a').close()
			except (IOError, OSError):
				logFile = SRLogger.getDefaultLogFilePath()
				open(logFile, 'a').close()

			writeLogFile = open(logFile, 'a')
			try:
				writeLogFile.write('%s\n' % text)
			except Exception as e:
				print("[SerienRecorder] Error while writing to log file [%s]" % str(e))
			finally:
				writeLogFile.close()

	@classmethod
	def writeLogFilter(cls, logtype, text, forceWrite=False):
		logFile = SRLogger.getLogFilePath()
		if config.plugins.serienRec.writeLog.value or forceWrite:
			try:
				open(logFile, 'a').close()
			except (IOError, OSError):
				logFile = SRLogger.getDefaultLogFilePath()
				open(logFile, 'a').close()

			writeLogFile = open(logFile, 'a')
			try:
				if (logtype == "channels" and config.plugins.serienRec.writeLogChannels.value) or \
						(logtype == "allowedEpisodes" and config.plugins.serienRec.writeLogAllowedEpisodes.value) or \
						(logtype == "added" and config.plugins.serienRec.writeLogAdded.value) or \
						(logtype == "disk" and config.plugins.serienRec.writeLogDisk.value) or \
						(logtype == "timeRange" and config.plugins.serienRec.writeLogTimeRange.value) or \
						(logtype == "timeLimit" and config.plugins.serienRec.writeLogTimeLimit.value) or \
						(logtype == "timerDebug" and config.plugins.serienRec.writeLogTimerDebug.value):
					# write log
					writeLogFile.write('%s\n' % text)
			except Exception as e:
				print("[SerienRecorder] Error while writing to filte log [%s]" % str(e))
			finally:
				writeLogFile.close()

	@classmethod
	def writeTestLog(cls, text):
		if not fileExists(SERIENRECORDER_TEST_LOGFILEPATH):
			open(SERIENRECORDER_TEST_LOGFILEPATH, 'w').close()

		writeLogFile = open(SERIENRECORDER_TEST_LOGFILEPATH, "a")
		try:
			writeLogFile.write('%s\n' % text)
		except Exception as e:
			print("[SerienRecorder] Error while writing test log [%s]" % str(e))
		finally:
			writeLogFile.close()

	@classmethod
	def checkFileAccess(cls):
		# überprüfe ob logFile als Datei erzeugt werden kann
		logFileValid = True

		if not os.path.exists(config.plugins.serienRec.LogFilePath.value):
			try:
				os.makedirs(config.plugins.serienRec.LogFilePath.value)
			except:
				logFileValid = False

		if not logFileValid:
			try:
				logFile = SRLogger.getLogFilePath()
				open(logFile, 'a').close()
			except:
				logFileValid = False

		if not logFileValid:
			logFile = SRLogger.getDefaultLogFilePath()
			Notifications.AddPopup(
				"Log-Datei kann nicht im angegebenen Pfad (%s) erzeugt werden.\n\nEs wird '%s' verwendet!" % (
				config.plugins.serienRec.LogFilePath.value, logFile), MessageBox.TYPE_INFO, timeout=10,
				id="checkFileAccess")

	@classmethod
	def reset(cls):
		log_filepath = SRLogger.getLogFilePath()

		if not config.plugins.serienRec.longLogFileName.value:
			# logFile leeren (renamed to .old)
			if fileExists(log_filepath):
				shutil.move(log_filepath,"%s.old" % log_filepath)
		else:
			lt = datetime.datetime.now() - datetime.timedelta(days=config.plugins.serienRec.deleteLogFilesOlderThan.value)
			for filename in os.listdir(config.plugins.serienRec.LogFilePath.value):
				long_logfile_filepath = os.path.join(config.plugins.serienRec.LogFilePath.value, filename)
				try:
					if (filename.find('SerienRecorder_') == 0) and (int(os.path.getmtime(long_logfile_filepath)) < int(lt.strftime("%s"))):
						os.remove(long_logfile_filepath)
				except:
					SRLogger.writeLog("Logdatei konnte nicht gelöscht werden: %s" % long_logfile_filepath, True)

		open(log_filepath, 'w').close()

	@classmethod
	def backup(cls):
		if config.plugins.serienRec.longLogFileName.value:
			lt = time.localtime()
			log_filepath = SRLogger.getLogFilePath()
			long_log_filepath = os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_LONG_LOGFILENAME % (str(lt.tm_year), str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)))
			shutil.copy(log_filepath, long_log_filepath)

	@classmethod
	def getLogFilePath(cls):
		return os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_LOGFILENAME)

	@classmethod
	def getDefaultLogFilePath(cls):
		return os.path.join(os.path.dirname(__file__), SERIENRECORDER_LOGFILENAME)
