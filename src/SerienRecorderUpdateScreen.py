# coding=utf-8

# This file contains the SerienRecoder Github Update Screen
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from Tools import Notifications
from Tools.Directories import fileExists

from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.config import config, configfile
from Components.ProgressBar import ProgressBar

from enigma import eListboxPythonMultiContent, gFont, getDesktop, eTimer, eConsoleAppContainer, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from skin import parseColor
from twisted.web.client import getPage, downloadPage

from .SerienRecorderHelpers import isDreamOS, toStr, toBinary, PY2, SRAPIVERSION
from .SerienRecorderScreenHelpers import skinFactor

import Screens.Standby
import os, re, ssl

try:
	import simplejson as json
except ImportError:
	import json

class checkGitHubUpdate:
	def __init__(self, session):
		self.session = session

	@staticmethod
	def getLastestReleaseData():
		if hasattr(ssl, '_create_unverified_context'):
			ssl._create_default_https_context = ssl._create_unverified_context

		if PY2:
			import httplib
		else:
			import http.client as httplib

		conn = httplib.HTTPSConnection("api.github.com", timeout=10, port=443)
		conn.request(url="/repos/einfall/serienrecorder/releases/latest", method="GET", headers={
			'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US;rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3 ( .NET CLR 3.5.30729)', })
		rawData = conn.getresponse()
		return json.load(rawData)

	###################################################################################
	# SerienRecorder Webinterface Update
	###################################################################################

	@staticmethod
	def checkForWebinterfaceUpdate():
		if ssl.OPENSSL_VERSION_NUMBER < 268439552:
			return

		latestRelease = checkGitHubUpdate.getLastestReleaseData()
		webapp_assets = []
		for asset in latestRelease['assets']:
			if asset['name'].lower().startswith('serienrecorder-webinterface'):
				name_parts = asset['name'].split('_')
				version = name_parts[1][:-4]
				version_parts = version.split('-')
				api_version = version_parts[0]
				webapp_version = version_parts[1]
				if api_version == SRAPIVERSION:
					webapp_assets.append((api_version, webapp_version, asset['browser_download_url'], int(asset['size'] / 1024)))

		return webapp_assets

	@staticmethod
	def installWebinterfaceUpdate(downloadURL):
		filePath = "/tmp/%s" % downloadURL.split('/')[-1]
		if fileExists(filePath):
			os.remove(filePath)

		import requests
		response = requests.get(downloadURL)
		if response.status_code == 200:
			with open(filePath, 'wb') as f:
				f.write(response.content)

			targetFilePath = os.path.join(os.path.dirname(__file__), "web-data")
			if fileExists(filePath):
				if os.path.exists(targetFilePath):
					import shutil
					shutil.rmtree(targetFilePath)

				import zipfile
				zip = zipfile.ZipFile(filePath)
				zip.extractall(os.path.dirname(__file__))
				os.remove(filePath)
			return True
		else:
			return False

	###################################################################################
	# SerienRecorder Update
	###################################################################################

	def checkForUpdate(self):
		if ssl.OPENSSL_VERSION_NUMBER < 268439552:
			Notifications.AddPopup("Leider ist die Suche nach SerienRecorder Updates auf dieser Box technisch nicht möglich - die automatische Plugin-Update Funktion wird deaktiviert!", MessageBox.TYPE_INFO, timeout=0)
			config.plugins.serienRec.Autoupdate.value = False
			config.plugins.serienRec.Autoupdate.save()
			configfile.save()
			return

		def checkReleases():
			latestRelease = checkGitHubUpdate.getLastestReleaseData()
			#latestRelease = data[0]
			latestVersion = latestRelease['tag_name'][1:]

			remoteversion = latestVersion.lower().replace("-", ".").replace("beta", "-1").split(".")
			version = config.plugins.serienRec.showversion.value.lower().replace("-", ".").replace("alpha", "-1").replace("beta", "-1").split(".")
			remoteversion.extend((max([len(remoteversion), len(version)]) - len(remoteversion)) * '0')
			remoteversion = [int(x) for x in remoteversion]
			version.extend((max([len(remoteversion), len(version)]) - len(version)) * '0')
			version = [int(x) for x in version]

			if remoteversion > version:
				updateName = toStr(latestRelease['name'])
				updateInfo = toStr(latestRelease['body'])
				updateDate = toStr(latestRelease['published_at'])
				downloadURL = None
				downloadFileSize = 5 * 1024
				for asset in latestRelease['assets']:
					updateURL = toStr(asset['browser_download_url'])
					if PY2:
						if isDreamOS() and updateURL.endswith(".deb"):
							downloadURL = updateURL
							downloadFileSize = int(asset['size'] / 1024)
							break
						if not isDreamOS() and updateURL.endswith('.ipk'):
							downloadURL = updateURL
							downloadFileSize = int(asset['size'] / 1024)
							break
					else:
						if isDreamOS() and updateURL.endswith(".deb3"):
							downloadURL = updateURL
							downloadFileSize = int(asset['size'] / 1024)
							break
						if not isDreamOS() and updateURL.endswith('.ipk3'):
							downloadURL = updateURL
							downloadFileSize = int(asset['size'] / 1024)
							break

				if downloadURL:
					return updateName, updateInfo, updateDate, downloadURL, downloadFileSize

			return None

		def onUpdateAvailable(result):
			if result:
				(updateName, updateInfo, updateDate, downloadURL, downloadFileSize) = result
				self.session.open(checkGitHubUpdateScreen, updateName, updateInfo, updateDate, downloadURL, downloadFileSize)

		def onUpdateCheckFailed():
			print("[SerienRecorder] Update check failed")
			self.session.open(MessageBox, "Bei der Suche nach einer neuen SerienRecorder Version ist ein Fehler aufgetreten!", MessageBox.TYPE_INFO, timeout=5)

		import twisted.python.runtime
		if twisted.python.runtime.platform.supportsThreads():
			from twisted.internet.threads import deferToThread
			deferToThread(checkReleases).addCallback(onUpdateAvailable).addErrback(onUpdateCheckFailed)
		else:
			try:
				result = checkReleases()
				onUpdateAvailable(result)
			except:
				onUpdateCheckFailed()


class checkGitHubUpdateScreen(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	BUTTON_X = DESKTOP_WIDTH / 2
	BUTTON_Y = DESKTOP_HEIGHT - 220

	skin = """
		<screen name="SerienRecorderUpdateCheck" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20">
			<widget name="headline" position="20,20" size="600,40" foregroundColor="#00ff4a3c" backgroundColor="#26181d20" transparent="1" font="Regular;26" halign="left" />
			<widget name="dateline" position="20,60" size="600,40" foregroundColor="yellow" backgroundColor="#26181d20" transparent="1" font="Regular;16" halign="left" />
			<widget name="changelog" position="5,100" size="%d,%d" foregroundColor="yellow" foregroundColorSelected="yellow" scrollbarMode="showOnDemand" selectionDisabled="1"/>
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

	def __init__(self, session, updateName, updateInfo, updateDate, downloadURL, downloadFileSize):
		Screen.__init__(self, session)
		self.session = session
		self.updateAvailable = False
		self.updateInfo = updateInfo
		self.updateName = updateName
		self.updateDate = updateDate
		self.progress = 0
		self.inProgres = False
		self.downloadDone = False
		self.downloadURL = downloadURL
		self.downloadFileSize = downloadFileSize
		self.filePath = None
		self.console = eConsoleAppContainer()
		self.progressTimer = eTimer()
		self.cmdList = []
		self.indent = False

		if isDreamOS():
			self.progressTimerConnection = self.progressTimer.timeout.connect(self.updateProgressBar)
			self.appClosed_conn = None
			self.dataAvail_conn = None
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
		self['dateline'] = Label("")

		self.changeLogList = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
		self.changeLogList.l.setFont(0, gFont('Regular', int(16 * skinFactor)))
		self.changeLogList.l.setFont(1, gFont('Regular', int(22 * skinFactor)))
		self.changeLogList.l.setFont(2, gFont('Regular', int(24 * skinFactor)))
		self.changeLogList.l.setItemHeight(int(28 * skinFactor))
		self['changelog'] = self.changeLogList

		self['status'] = Label("")
		self['progressslider'] = ProgressBar()
		self['separator'] = Label("")
		self['text_ok'] = Label("Jetzt herunterladen und installieren")
		self['text_exit'] = Label("Später aktualisieren")

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		self['headline'].setText("Update verfügbar: %s" % self.updateName)
		self['dateline'].setText("Veröffentlicht am: %s / Größe: %s kB" % (re.sub(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z", r"\3.\2.\1 um \4:\5 Uhr", self.updateDate), self.downloadFileSize))

		changelog_list = []
		for row in self.updateInfo.splitlines():
			changelog_list.append(row)
		self.changeLogList.setList(list(map(self.buildList, changelog_list)))

		self['progressslider'].setValue(0)

	def buildList(self, entry):
		(row) = entry
		DESKTOP_WIDTH = getDesktop(0).size().width()

		if len(row) == 0:
			self.indent = False

		if row.startswith('##'):
			row = row.replace('#', '')
			color = parseColor('green').argb()
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 5, 2 * skinFactor, DESKTOP_WIDTH - 105, 28 * skinFactor, 2, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row, color, color)]
		if row.startswith('**'):
			row = row.replace('*', '')
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 5, 2 * skinFactor, DESKTOP_WIDTH - 105, 28 * skinFactor, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row)]
		elif re.search('^[1-9-]', row):
			color = parseColor('foreground').argb()
			self.indent = True
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 20, 2 * skinFactor, DESKTOP_WIDTH - 90, 28 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row, color, color)]
		elif self.indent:
			color = parseColor('foreground').argb()
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 40, 2 * skinFactor, DESKTOP_WIDTH - 70, 28 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row, color, color)]
		else:
			color = parseColor('foreground').argb()
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 20, 2 * skinFactor, DESKTOP_WIDTH - 90, 28 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row, color, color)]

	def keyLeft(self):
		self['changelog'].pageUp()

	def keyRight(self):
		self['changelog'].pageDown()

	def keyDown(self):
		self['changelog'].pageDown()

	def keyUp(self):
		self['changelog'].pageUp()

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
			downloadPage(toBinary(self.downloadURL), self.filePath).addCallback(self.downloadFinished).addErrback(self.downloadError)

	def keyCancel(self):
		self.close()

	def cmdData(self, data):
		for row in toStr(data).splitlines():
			self.cmdList.append(row)
		self.changeLogList.setList(list(map(self.buildList, self.cmdList)))
		count = len(self.cmdList)
		if count != 0:
			self['changelog'].moveToIndex(int(count - 1))

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
		print("[SerienRecorder] downloadFinished")
		self.downloadDone = True
		self.progress = 0
		self['status'].setText("")

		print("[SerienRecorder] Filepath: " + self.filePath)
		if fileExists(self.filePath):
			self['status'].setText("Installation wurde gestartet, bitte warten...")

			if isDreamOS():
				self.appClosed_conn = self.console.appClosed.connect(self.finishedPluginUpdate)
				self.dataAvail_conn = self.console.dataAvail.connect(self.cmdData)
				command = "apt-get update && dpkg -i %s && apt-get -f install" % str(self.filePath)
			else:
				self.console.appClosed.append(self.finishedPluginUpdate)
				self.console.dataAvail.append(self.cmdData)
				command = "opkg update && opkg install --force-overwrite --force-depends --force-downgrade %s" % str(self.filePath)

			print("[SerienRecorder] Executing command: " + command)
			retval = self.console.execute(command)
			print("[SerienRecorder] Return: " + str(retval))
		else:
			self.downloadError()

	def downloadError(self):
		self.stopProgressTimer()
		Notifications.AddPopup("Der Download der neuen SerienRecorder Version ist fehlgeschlagen.\nDas Update wird abgebrochen.", type=MessageBox.TYPE_INFO, timeout=10)
		self.close()

	def finishedPluginUpdate(self, retval):
		print("[SerienRecorder] finishPluginUpdate [retval = " + str(retval) + "]")
		#self.console.kill()
		#self.stopProgressTimer()
		self['status'].setText("")
		if fileExists(self.filePath):
			print("[SerienRecorder] Removing file: " + self.filePath)
			os.remove(self.filePath)

		if retval == 0:
			self.session.openWithCallback(self.restartGUI, MessageBox,
			                              text="Der SerienRecorder wurde erfolgreich aktualisiert!\nSoll die Box jetzt neu gestartet werden?",
			                              type=MessageBox.TYPE_YESNO)
		else:
			self.session.openWithCallback(self.closeUpdate, MessageBox,
			                              text="Der SerienRecorder konnte nicht aktualisiert werden!",
			                              type=MessageBox.TYPE_ERROR)

	def restartGUI(self, doRestart):
		if doRestart:
			self.session.open(Screens.Standby.TryQuitMainloop, 3)
		self.close()
	
	def closeUpdate(self, retval):
		self.close()