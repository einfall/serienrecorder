# coding=utf-8

# This file contains the SerienRecoder Github Update Screen
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
import urllib
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

	def checkForUpdate(self):
		import ssl
		if ssl.OPENSSL_VERSION_NUMBER < 268439552:
			Notifications.AddPopup("Leider ist die Suche nach SerienRecorder Updates auf Ihrer Box technisch nicht möglich - bitte deaktivieren Sie die automatische Plugin-Update Funktion, in den SerienRecorder Einstellungen, um diese Meldung zu unterdrücken!", MessageBox.TYPE_INFO, timeout=0)
			return

		if hasattr(ssl, '_create_unverified_context'):
			ssl._create_default_https_context = ssl._create_unverified_context
		conn = httplib.HTTPSConnection("api.github.com", timeout=10, port=443)
		try:
			conn.request(url="/repos/einfall/serienrecorder/releases/latest", method="GET", headers={
				'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US;rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3 ( .NET CLR 3.5.30729)',})
			rawData = conn.getresponse()
			latestRelease = json.load(rawData)
			#latestRelease = data[0]
			latestVersion = latestRelease['tag_name'][1:]

			remoteversion = latestVersion.lower().replace("-", ".").replace("beta", "-1").split(".")
			version = config.plugins.serienRec.showversion.value.lower().replace("-", ".").replace("beta", "-1").split(".")
			remoteversion.extend((max([len(remoteversion), len(version)]) - len(remoteversion)) * '0')
			remoteversion = map(lambda x: int(x), remoteversion)
			version.extend((max([len(remoteversion), len(version)]) - len(version)) * '0')
			version = map(lambda x: int(x), version)

			if remoteversion > version:
				updateName = latestRelease['name'].encode('utf-8')
				updateInfo = latestRelease['body'].encode('utf-8')
				downloadURL = None
				downloadFileSize = 5 * 1024
				for asset in latestRelease['assets']:
					updateURL = asset['browser_download_url'].encode('utf-8')
					if isDreamOS() and updateURL.endswith(".deb"):
						downloadURL = updateURL
						downloadFileSize = int(asset['size'] / 1024)
						break
					if not isDreamOS() and updateURL.endswith('.ipk'):
						downloadURL = updateURL
						downloadFileSize = int(asset['size'] / 1024)
						break

				if downloadURL:
					self.session.open(checkGitHubUpdateScreen, updateName, updateInfo, downloadURL, downloadFileSize)
		except:
			Notifications.AddPopup("Unerwarteter Fehler beim Überprüfen der SerienRecorder Version", MessageBox.TYPE_INFO, timeout=3)


class checkGitHubUpdateScreen(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	BUTTON_X = DESKTOP_WIDTH / 2
	BUTTON_Y = DESKTOP_HEIGHT - 220

	skin = """
		<screen name="SerienRecorderUpdateCheck" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20">
			<widget name="headline" position="20,20" size="600,40" foregroundColor="#00ff4a3c" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="srlog" position="5,100" size="%d,%d" font="Regular;21" valign="top" halign="left" foregroundColor="#FFFFFF" transparent="1" zPosition="5"/>
			<widget name="progressslider" position="5,%d" size="%d,25" borderWidth="1" zPosition="1" backgroundColor="#00242424"/>
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

	def __init__(self, session, updateName, updateInfo, downloadURL, downloadFileSize):
		Screen.__init__(self, session)
		self.session = session
		self.updateAvailable = False
		self.updateInfo = updateInfo
		self.updateName = updateName
		self.progress = 0
		self.inProgres = False
		self.downloadDone = False
		self.downloadURL = downloadURL
		self.downloadFileSize = downloadFileSize
		self.filePath = None
		self.console = eConsoleAppContainer()

		self.progressTimer = eTimer()
		if isDreamOS():
			self.progressTimerConnection = self.progressTimer.timeout.connect(self.updateProgressBar)
		else:
			self.progressTimer.callback.append(self.updateProgressBar)

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

		self.onLayoutFinish.append(self.__onLayoutFinished)

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
		if self.inProgres:
			return
		else:
			self.filePath = "/tmp/%s" % self.downloadURL.split('/')[-1]
			self['status'].setText("Download wurde gestartet, bitte warten...")
			self.progress = 0
			self.inProgres = True
			self['progressslider'].setValue(self.progress)
			self.startProgressTimer()

			if fileExists(self.filePath):
				os.remove(self.filePath)
			downloadPage(self.downloadURL, self.filePath).addCallback(self.downloadFinished).addErrback(self.downloadError)

	def keyCancel(self):
		self.close()

	def cmdData(self, data):
		self['srlog'].setText(data)

	def updateProgressBar(self):
		if self.downloadDone:
			self.progress += 10
			if self.progress > 100:
				self.progress = 10
		else:
			if os.path.exists(self.filePath):
				kBytesDownloaded = int(os.path.getsize(self.filePath) / 1024)
			else:
				kBytesDownloaded = 0

			self.progress = int((kBytesDownloaded / self.downloadFileSize) * 100)
			self['status'].setText("%s / %s kB (%s%%)" % (kBytesDownloaded, self.downloadFileSize, self.progress))

		self['progressslider'].setValue(self.progress)

	def startProgressTimer(self):
		self.progressTimer.start(100)

	def stopProgressTimer(self):
		if self.progressTimer:
			self.progressTimer.stop()
			self.progressTimer = None

		if isDreamOS():
			self.progressTimerConnection = None

	def downloadFinished(self, result):
		self.downloadDone = True
		self.progress = 0
		self['status'].setText("")

		if fileExists(self.filePath):
			self['status'].setText("Installation wurde gestartet, bitte warten...")

			if isDreamOS():
				self.console.appClosed.connect(self.finishedPluginUpdate)
				#self.console.dataAvail.connect(self.cmdData)
				command = "apt-get update && dpkg -i %s && apt-get -f install" % str(self.filePath)
			else:
				self.console.appClosed.append(self.finishedPluginUpdate)
				#self.console.dataAvail.append(self.cmdData)
				command = "opkg update && opkg install --force-overwrite --force-depends --force-downgrade %s" % str(self.filePath)

			self.console.execute(command)
		else:
			self.downloadError("Downloaded file does not exist")

	def downloadError(self, result):
		self.stopProgressTimer()
		Notifications.AddPopup("Der Download der neuen SerienRecorder Version ist fehlgeschlagen.\nDas Update wird abgebrochen.", type=MessageBox.TYPE_INFO, timeout=10)
		self.close()

	def finishedPluginUpdate(self, retval):
		self.console.kill()
		#self.stopProgressTimer()
		self['status'].setText("")
		if fileExists(self.filePath):
			os.remove(self.filePath)
		if retval == 0:
			config.plugins.serienRec.showStartupInfoText.value = True
			config.plugins.serienRec.showStartupInfoText.save()
			configfile.save()
			self.session.openWithCallback(self.restartGUI, MessageBox, text="Der SerienRecorder wurde erfolgreich aktualisiert!\nSoll die Box jetzt neu gestartet werden?", type=MessageBox.TYPE_YESNO)
		else:
			self.session.openWithCallback(self.closeUpdate, MessageBox, text="Der SerienRecorder konnte nicht aktualisiert werden!", type=MessageBox.TYPE_ERROR)

	def restartGUI(self, doRestart):
		if doRestart:
			self.session.open(Screens.Standby.TryQuitMainloop, 3)
		self.close()
	
	def closeUpdate(self):
		self.close()