# coding=utf-8

# This file contains the SerienRecoder Github Update Screen

from __init__ import _

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from Tools import Notifications
from Tools.Directories import fileExists

from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.ScrollLabel import ScrollLabel
from Components.config import config, configfile
from Components.ProgressBar import ProgressBar

from enigma import getDesktop, eTimer, eConsoleAppContainer
from twisted.web.client import getPage, downloadPage

import Screens.Standby
import httplib

try:
	import simplejson as json
except ImportError:
	import json

from SerienRecorderHelpers import *

class checkGitHubUpdateScreen(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	BUTTON_X = DESKTOP_WIDTH / 2
	BUTTON_Y = DESKTOP_HEIGHT - 220

	skin = """
		<screen name="SerienRecorderUpdateCheck" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20">
			<widget name="headline" position="20,20" size="600,40" foregroundColor="red" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="srlog" position="5,100" size="%d,%d" font="Regular;21" valign="top" halign="left" foregroundColor="white" transparent="1" zPosition="5"/>
			<widget name="progressslider" position="5,%d" size="%d,25" borderWidth="1" zPosition="1" backgroundColor="dark"/>
			<widget name="status" position="5,%d" size="%d,25" font="Regular;20" valign="center" halign="center" foregroundColor="#00808080" transparent="1" zPosition="6"/>
			<widget name="separator" position="%d,%d" size="%d,5" backgroundColor="#00808080" zPosition="6" />
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_ok.png" position="%d,%d" zPosition="1" size="32,32" alphatest="on" />
			<widget name="text_ok" position="%d,%d" size="%d,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_exit.png" position="%d,%d" zPosition="1" size="32,32" alphatest="on" />
			<widget name="text_exit" position="%d,%d" size="%d,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>""" % (50, 100, DESKTOP_WIDTH - 100, DESKTOP_HEIGHT - 180, "SerienRecorder Update",
						DESKTOP_WIDTH - 110, DESKTOP_HEIGHT - 405,
						BUTTON_Y - 75, DESKTOP_WIDTH - 110,
						BUTTON_Y - 50, DESKTOP_WIDTH - 110,
						5, BUTTON_Y - 20, DESKTOP_WIDTH - 110,
						BUTTON_X + 50, BUTTON_Y,
						BUTTON_X + 92, BUTTON_Y + 3, BUTTON_X - 100,
						50, BUTTON_Y,
						92, BUTTON_Y + 3, BUTTON_X - 100,
						)

	def __init__(self, session):
		self.session = session
		self.updateAvailable = False
		self.updateInfo = None
		self.updateName = None
		self.progress = 0
		self.downloadDone = False
		self.downloadURL = None
		self.downloadFileSize = 5 * 1024
		self.filePath = None

		self.progressTimer = eTimer()
		if isDreamboxOS:
			self.progressTimerConnection = self.progressTimer.timeout.connect(self.updateProgressBar)
		else:
			self.progressTimer.callback.append(self.updateProgressBar)


		Screen.__init__(self, session)

		self["actions"] = ActionMap(["SerienRecorderActions",], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
		}, -1)

		self['headline'] = Label("")
		self['srlog'] = ScrollLabel("")
		self['status'] = Label("")
		self['progressslider'] = ProgressBar()
		self['separator'] = Label("")
		self['text_ok'] = Label("Jetzt herunterladen und installieren")
		self['text_exit'] = Label("Später aktualisieren")

		conn = httplib.HTTPSConnection("api.github.com", timeout=10, port=443)
		try:
			conn.request(url="/repos/einfall/serienrecorder/releases", method="GET", headers={'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US;rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3 ( .NET CLR 3.5.30729)',})
			rawData = conn.getresponse()
			data = json.load(rawData)
			self.latestRelease = data[0]
			latestVersion = self.latestRelease['tag_name'][1:]

			remoteversion = latestVersion.lower().replace("-", ".").replace("beta", "-1").split(".")
			version = config.plugins.serienRec.showversion.value.lower().replace("-", ".").replace("beta", "-1").split(".")
			remoteversion.extend((max([len(remoteversion),len(version)])-len(remoteversion)) * '0')
			remoteversion = map(lambda x: int(x), remoteversion)
			version.extend((max([len(remoteversion),len(version)])-len(version)) * '0')
			version = map(lambda x: int(x), version)

			if remoteversion > version:
				self.updateName = self.latestRelease['name'].encode('utf-8')
				self.updateInfo = self.latestRelease['body'].encode('utf-8')
				for asset in self.latestRelease['assets']:
					updateURL = asset['browser_download_url'].encode('utf-8')
					if isDreamboxOS and updateURL.find(".deb"):
						self.downloadURL = updateURL
						self.downloadFileSize = int(asset['size'] / 1024)
					if not isDreamboxOS and updateURL.find('.ipk'):
						self.downloadURL = updateURL
						self.downloadFileSize = int(asset['size'] / 1024)

				self.onLayoutFinish.append(self.__onLayoutFinished)
			else:
				self.close()
		except:
			self.close()

	def __onLayoutFinished(self):
		self['headline'].setText("Update verfügbar: %s" % self.updateName)
		self['srlog'].setText(self.updateInfo)
		self['progressslider'].setValue(0)

	def keyLeft(self):
		self['srlog'].pageUp()

	def keyRight(self):
		self['srlog'].pageDown()

	def keyDown(self):
		self['srlog'].pageDown()

	def keyUp(self):
		self['srlog'].pageUp()

	def keyOK(self):
		self.filePath = "/tmp/%s" % self.downloadURL.split('/')[-1]
		self['status'].setText("Download wurde gestartet, bitte warten...")
		self.progress = 0
		self['progressslider'].setValue(self.progress)
		self.startProgressTimer()

		if fileExists(self.filePath):
			os.remove(self.filePath)
		downloadPage(self.downloadURL, self.filePath).addCallback(self.downloadFinished).addErrback(self.downloadError)

	def keyCancel(self):
		self.close()

	def updateProgressBar(self):
		if self.downloadDone:
			self.progress += 10
			if self.progress > 100:
				self.progress = 10
		else:
			if os.path.exists(self.filePath):
				kBbytesDownloaded = int(os.path.getsize(self.filePath) / 1024)
			else:
				kBbytesDownloaded = 0

			self.progress = int((kBbytesDownloaded / self.downloadFileSize) * 100)
			self['status'].setText("%s / %s kB (%s%%)" % (kBbytesDownloaded, self.downloadFileSize, self.progress))

		self['progressslider'].setValue(self.progress)

	def startProgressTimer(self):
		self.progressTimer.start(100)

	def stopProgressTimer(self):
		if self.progressTimer:
			self.progressTimer.stop()
			self.progressTimer = None

		if isDreamboxOS:
			self.progressTimerConnection = None

	def downloadFinished(self, data):
		self.downloadDone = True
		self.progress = 0
		self['status'].setText("")

		if fileExists(self.filePath):
			self['status'].setText("Installation wurde gestartet, bitte warten...")
			appContainer = eConsoleAppContainer()
			if isDreamboxOS:
				appContainer.stdoutAvail.connect(self['srlog'])
				appContainer.appClosed.connect(self.finishedPluginUpdate)
				appContainer.execute("apt-get update && dpkg -i %s && apt-get -f install" % str(self.filePath))
			else:
				appContainer.stdoutAvail.append(self['srlog'])
				appContainer.appClosed.append(self.finishedPluginUpdate)
				appContainer.execute("opkg update && opkg install --force-overwrite --force-depends --force-downgrade %s" % str(self.filePath))
		else:
			self.downloadError()

	def downloadError(self):
		self.stopProgressTimer()
		writeErrorLog("SerienRecorderUpdateScreen():\n   URL: %s" % self.downloadURL)
		self.session.open(MessageBox, "Der SerienRecorder Download ist fehlgeschlagen.\nDie Installation wurde abgebrochen.", MessageBox.TYPE_INFO)
		self.close()

	def finishedPluginUpdate(self, retval):
		self.stopProgressTimer()
		if fileExists(self.filePath):
			os.remove(self.filePath)
		self.session.openWithCallback(self.restartGUI, MessageBox, "Der SerienRecorder wurde erfolgreich aktualisiert!\nSoll die Box jetzt neu gestartet werden?", MessageBox.TYPE_YESNO)

	def restartGUI(self, doRestart):
		config.plugins.serienRec.showStartupInfoText.value = True
		config.plugins.serienRec.showStartupInfoText.save()
		configfile.save()

		if doRestart:
			self.session.open(Screens.Standby.TryQuitMainloop, 3)
		else:
			self.close()