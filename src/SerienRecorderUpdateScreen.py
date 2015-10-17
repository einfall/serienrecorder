# coding=utf-8

# This file contains the SerienRecoder Github Update Screen

from __init__ import _

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from Tools import Notifications
from Tools.Directories import fileExists

from Components.Label import Label
from Components.config import config, configfile

from enigma import getDesktop, eTimer, eConsoleAppContainer
from twisted.web.client import getPage, downloadPage

import Screens.Standby
import httplib

try:
	import simplejson as json
except ImportError:
	import json

from SerienRecorderHelpers import *

class checkGitHubUpdate:
	def __init__(self, session):
		self.session = session
		self.response = []
		self.latestVersion = ''

	def checkForUpdate(self):
		global UpdateAvailable
		UpdateAvailable = False
		conn = httplib.HTTPSConnection("api.github.com", timeout=WebTimeout, port=443)
		try:
			conn.request(url="/repos/einfall/serienrecorder/tags", method="GET", headers={'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US;rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3 ( .NET CLR 3.5.30729)',})
			data = conn.getresponse()
		except:
			return

		self.response = json.load(data)
		latestVersion = self.response[0]['name'][1:]

		if config.plugins.serienRec.updateType.value == "0" and self.checkIfBetaVersion(latestVersion): # Stable
			latestVersion = self.searchLatestStable()

		remoteversion = latestVersion.lower().replace("-", ".").replace("beta", "-1").split(".")
		version=config.plugins.serienRec.showversion.value.lower().replace("-", ".").replace("beta", "-1").split(".")
		remoteversion.extend((max([len(remoteversion),len(version)])-len(remoteversion)) * '0')
		remoteversion=map(lambda x: int(x), remoteversion)
		version.extend((max([len(remoteversion),len(version)])-len(version)) * '0')
		version=map(lambda x: int(x), version)

		if remoteversion > version:
			UpdateAvailable = True
			self.latestVersion = latestVersion
			self.session.openWithCallback(self.startUpdate, MessageBox, _("Für das Serien Recorder Plugin ist ein Update (v%s) verfügbar!\nWollen Sie es jetzt herunterladen und installieren?") % str(latestVersion), MessageBox.TYPE_YESNO, msgBoxID="[Serien Recorder] Update available")

	@staticmethod
	def checkIfBetaVersion(foundVersion):
		isBeta = foundVersion.find("beta")
		if isBeta != -1:
			return True
		else:
			return False

	def searchLatestStable(self):
		isStable = False
		latestStabel = ""
		idx = 0

		while not isStable:
			idx += 1
			latestStabel = self.response[idx]['name'][1:]
			isBeta = self.checkIfBetaVersion(latestStabel)
			if not isBeta:
				isStable = True

		return latestStabel

	def startUpdate(self,answer):
		if answer:
			if isDreamboxOS:
				remoteUrl = "https://github.com/einfall/serienrecorder/releases/download/v%s/enigma2-plugin-extensions-serienrecorder_%s_all.deb" % (str(self.latestVersion), str(self.latestVersion))
			else:
				remoteUrl = "https://github.com/einfall/serienrecorder/releases/download/v%s/enigma2-plugin-extensions-serienrecorder_%s_all.ipk" % (str(self.latestVersion), str(self.latestVersion))

			try:
				self.session.open(SerienRecorderUpdateScreen, remoteUrl, self.latestVersion)
			except:
				Notifications.AddPopup(_("[Serien Recorder]\nDer Download ist fehlgeschlagen.\nDie Installation wurde abgebrochen."), MessageBox.TYPE_INFO, timeout=3)
		else:
			return

class SerienRecorderUpdateScreen(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	skin = """
		<screen name="SerienRecorderUpdate" position="%d,%d" size="720,320" title="%s" backgroundColor="#26181d20" flags="wfNoBorder">
			<widget name="srlog" position="5,5" size="710,310" font="Regular;18" valign="center" halign="center" foregroundColor="white" transparent="1" zPosition="5"/>
			<widget name="activityslider" position="5,280" size="710,25" borderWidth="1" transparent="1" zPosition="4"/>
			<widget name="status" position="30,280" size="660,25" font="Regular;20" valign="center" halign="center" foregroundColor="#00808080" transparent="1" zPosition="6"/>
		</screen>""" % ((DESKTOP_WIDTH - 720) / 2, (DESKTOP_HEIGHT - 320) / 2, _("Serien Recorder Update"))

	def __init__(self, session, updateurl, version):
		from Components.Slider import Slider

		self.session = session
		Screen.__init__(self, session)
		self.target = updateurl
		self.version = version
		self.file_name = "/tmp/%s" % self.target.split('/')[-1]
		self.fileSize = 5 * 1024
		self.downloadDone = False
		self.container = eConsoleAppContainer()

		self['srlog'] = Label()

		self.status = Label(_("Preparing... Please wait"))
		self['status'] = self.status
		self.activityslider = Slider(0, 100)
		self['activityslider'] = self.activityslider
		self.activity = 0
		self.activityTimer = eTimer()
		if isDreamboxOS:
			self.activityTimerConnection = self.activityTimer.timeout.connect(self.doActivityTimer)
		else:
			self.activityTimer.callback.append(self.doActivityTimer)

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def doActivityTimer(self):
		if self.downloadDone:
			self.activity += 1
			if self.activity == 101:
				self.activity = 1
		else:
			if os.path.exists(self.file_name):
				kBbytesDownloaded = int(os.path.getsize(self.file_name) / 1024)
			else:
				kBbytesDownloaded = 0

			self.activity = int(kBbytesDownloaded * 100 / self.fileSize)
			self.status.setText("%s / %s kB (%s%%)" % (kBbytesDownloaded, self.fileSize, self.activity))

		self.activityslider.setValue(self.activity)

	def startActivityTimer(self):
		self.activityTimer.start(100, False)

	def stopActivityTimer(self):
		self.activityTimer.stop()
		if self.activityTimer:
			self.activityTimer.stop()
			self.activityTimer = None

		if isDreamboxOS:
			self.activityTimerConnection = None

	def __onLayoutFinished(self):
		sl = self['srlog']
		sl.instance.setZPosition(5)

		getPage(str(self.target.replace("/download/", "/tag/").rsplit('/', 1)[0]), timeout=WebTimeout, agent=getUserAgent(), headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getFileSize).addErrback(self.downloadError)

		self['srlog'].setText(_("Download wurde gestartet, bitte warten..."))
		self.activityslider.setValue(0)
		self.startActivityTimer()

		if fileExists(self.file_name):
			os.remove(self.file_name)
		downloadPage(self.target, self.file_name).addCallback(self.downloadFinished).addErrback(self.downloadError)

	def getFileSize(self, data):
		if isDreamboxOS:
			raw = re.findall('<a href="/einfall/serienrecorder/releases/download/v.*?/enigma2-plugin-extensions-serienrecorder_.*?_all.deb".*?aria-label="(.*?)">enigma2-plugin-extensions-serienrecorder_.*?_all.deb</span>',data,re.S)
		else:
			raw = re.findall('<a href="/einfall/serienrecorder/releases/download/v.*?/enigma2-plugin-extensions-serienrecorder_.*?_all.ipk".*?aria-label="(.*?)">enigma2-plugin-extensions-serienrecorder_.*?_all.ipk</span>',data,re.S)
		if len(raw):
			self.fileSize = int(float(raw[0].replace("MB", "").strip()) * 1024.0)
		else:
			self.fileSize = 5 * 1024

	def downloadFinished(self, data):
		self.downloadDone = True
		self.activity = 0
		self.status.setText("")

		if fileExists(self.file_name):
			self['srlog'].setText(_("Starte Update, bitte warten..."))

			self.container.appClosed.append(self.finishedPluginUpdate)
			self.container.stdoutAvail.append(self.srlog)

			if isDreamboxOS:
				self.container.execute("apt-get update && dpkg -i %s && apt-get -f install" % str(self.file_name))
			else:
				self.container.execute("opkg install --force-overwrite --force-depends --force-downgrade %s" % str(self.file_name))
		else:
			self.downloadError()

	def downloadError(self):
		self.stopActivityTimer()
		writeErrorLog("   SerienRecorderUpdateScreen():\n   Url: %s" % self.target)
		self.session.open(MessageBox, _("[Serien Recorder]\nDer Download ist fehlgeschlagen.\nDie Installation wurde abgebrochen."), MessageBox.TYPE_INFO)
		self.close()

	def finishedPluginUpdate(self,retval):
		self.stopActivityTimer()
		if fileExists(self.file_name):
			os.remove(self.file_name)
		self.session.openWithCallback(self.restartGUI, MessageBox, _("Serien Recorder wurde erfolgreich aktualisiert!\nWollen Sie jetzt Enigma2 GUI neu starten?"), MessageBox.TYPE_YESNO)

	def restartGUI(self, answer):
		config.plugins.serienRec.showStartupInfoText.value = True
		config.plugins.serienRec.showStartupInfoText.save()
		configfile.save()

		if answer:
			self.session.open(Screens.Standby.TryQuitMainloop, 3)
		else:
			self.close()

	def srlog(self,str):
		self['srlog'].setText(str)