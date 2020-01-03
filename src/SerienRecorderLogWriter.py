# coding=utf-8

# This file contain logger functions

from Components.config import config
from Screens.MessageBox import MessageBox
from Tools import Notifications
from Tools.Directories import fileExists

import SerienRecorder
import os, shutil, datetime, time

SERIENRECORDER_LOGFILENAME = "%sSerienRecorder.log"
SERIENRECORDER_LONG_LOGFILENAME = "%sSerienRecorder_%s%s%s%s%s.log"
SERIENRECORDER_TEST_LOGFILEPATH = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/TestLogs"

class SRLogger:
	def __init__(self):
		pass

	@classmethod
	def writeLog(cls, text, forceWrite=False):
		logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value
		if config.plugins.serienRec.writeLog.value or forceWrite:
			try:
				open(logFile, 'a').close()
			except (IOError, OSError):
				logFile = SERIENRECORDER_LOGFILENAME % SerienRecorder.serienRecMainPath
				open(logFile, 'a').close()

			writeLogFile = open(logFile, 'a')
			writeLogFile.write('%s\n' % text)
			writeLogFile.close()

	@classmethod
	def writeLogFilter(cls, logtype, text, forceWrite=False):
		logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value
		if config.plugins.serienRec.writeLog.value or forceWrite:
			try:
				open(logFile, 'a').close()
			except (IOError, OSError):
				logFile = SERIENRECORDER_LOGFILENAME % SerienRecorder.serienRecMainPath
				open(logFile, 'a').close()

			writeLogFile = open(logFile, 'a')
			if (logtype is "channels" and config.plugins.serienRec.writeLogChannels.value) or \
					(logtype is "allowedEpisodes" and config.plugins.serienRec.writeLogAllowedEpisodes.value) or \
					(logtype is "added" and config.plugins.serienRec.writeLogAdded.value) or \
					(logtype is "disk" and config.plugins.serienRec.writeLogDisk.value) or \
					(logtype is "timeRange" and config.plugins.serienRec.writeLogTimeRange.value) or \
					(logtype is "timeLimit" and config.plugins.serienRec.writeLogTimeLimit.value) or \
					(logtype is "timerDebug" and config.plugins.serienRec.writeLogTimerDebug.value):
				# write log
				writeLogFile.write('%s\n' % text)

			writeLogFile.close()

	@classmethod
	def writeTestLog(cls, text):
		if not fileExists(SERIENRECORDER_TEST_LOGFILEPATH):
			open(SERIENRECORDER_TEST_LOGFILEPATH, 'w').close()

		writeLogFile = open(SERIENRECORDER_TEST_LOGFILEPATH, "a")
		writeLogFile.write('%s\n' % text)
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
				logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value
				open(logFile, 'a').close()
			except:
				logFileValid = False

		if not logFileValid:
			logFile = SERIENRECORDER_LOGFILENAME % SerienRecorder.serienRecMainPath
			Notifications.AddPopup(
				"Log-Datei kann nicht im angegebenen Pfad (%s) erzeugt werden.\n\nEs wird '%s' verwendet!" % (
				config.plugins.serienRec.LogFilePath.value, logFile), MessageBox.TYPE_INFO, timeout=10,
				id="checkFileAccess")

	@classmethod
	def reset(cls):
		logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value

		# logFile leeren (renamed to .old)
		if fileExists(logFile):
			shutil.move(logFile,"%s.old" % logFile)

		open(logFile, 'w').close()

	@classmethod
	def getLogFilePath(cls):
		return SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value