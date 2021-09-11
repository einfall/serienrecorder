# coding=utf-8

# This file contains the SerienRecoder Cover Selector Screen
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.GUIComponent import GUIComponent

from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_VALIGN_CENTER, RT_HALIGN_LEFT, RT_HALIGN_CENTER
from enigma import getDesktop

from twisted.internet import defer

from Tools.Directories import fileExists

from .SerienRecorderHelpers import PicLoader

import os, shutil

class CoverSelectorScreen(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	DIALOG_WIDTH = 680
	DIALOG_HEIGHT = DESKTOP_HEIGHT - 180

	skin = """
			<screen name="CoverSelectorScreen" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20">
				<widget name="headline" position="10,6" size="500,26" foregroundColor="green" backgroundColor="#26181d20" transparent="1" font="Regular;19" valign="center" halign="left" />
				<widget name="list" position="5,40" size="%d,%d" scrollbarMode="showOnDemand"/>
				<widget name="footer" position="10,%d" size="500,26" foregroundColor="green" backgroundColor="#26181d20" transparent="1" font="Regular;19" valign="center" halign="left" />
			</screen>""" % (50, 100, DIALOG_WIDTH, DIALOG_HEIGHT, "SerienRecorder Coverauswahl",
	                        DIALOG_WIDTH - 10, DIALOG_HEIGHT - 70,
                            DIALOG_HEIGHT - 28
	                        )

	def __init__(self, session, serien_wlid, serien_name, serien_fsid):
		Screen.__init__(self, session)

		self._session = session
		self._serien_wlid = serien_wlid
		self._serien_name = serien_name
		self._serien_fsid = serien_fsid
		self._tempDir = '/tmp/serienrecorder/'
		self._coverList = []
		self._numberOfCovers = 0

		if os.path.exists(self._tempDir) is False:
			os.mkdir(self._tempDir)

		self['headline'] = Label("Welches Cover soll für die Serie gespeichert werden?")
		self['list'] = CoverSelectorList()
		self['footer'] = Label("Cover werden geladen...")

		self["actions"] = ActionMap(["SerienRecorderActions",], {
			"ok"    : self.keyOK,
			"green" : self.keyOK,
			"cancel": self.keyExit,
			"red"   : self.keyExit,
		}, -1)

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		self._numberOfCovers = 0

		from .SerienRecorderSeriesServer import SeriesServer
		print("[SerienRecorder] Get covers for id = " + str(self._serien_wlid))
		covers = SeriesServer().getCoverURLs(self._serien_wlid)
		if covers is not None:
			print("[SerienRecorder] Number of covers found = " + str(len(covers)))
			self._numberOfCovers = len(covers)
			ds = defer.DeferredSemaphore(tokens=5)
			downloads = [ds.run(self.download, cover).addCallback(self.buildList, cover).addErrback(self.buildList, cover) for cover in covers]
			defer.DeferredList(downloads).addErrback(self.dataError).addCallback(self.dataFinish)
		else:
			self['footer'].setText("Keine Cover gefunden!")

	def download(self, cover):
		from twisted.web import client
		from .SerienRecorderHelpers import toBinary

		path = self._tempDir + str(cover['id']) + '.jpg'
		print("[SerienRecorder] Temp cover path = " + path)
		if not fileExists(path):
			print("[SerienRecorder] Downloading cover %s => %s" % (cover['url'], path))
			return client.downloadPage(toBinary(cover['url']), path)
		else:
			return True

	def buildList(self, data, cover):
		self._coverList.append(((cover['id'], cover['rating'], cover['language'], self._tempDir + str(cover['id']) + '.jpg'),))
		self['list'].setList(self._coverList)

	def dataError(self, error):
		print("[SerienRecorder] Cover download error = ", error)
		self['footer'].setText("Fehler beim Laden der Cover!")

	def dataFinish(self, res):
		self['footer'].setText("Es wurden %d Cover gefunden" % self._numberOfCovers)

	def keyOK(self):
		from Components.config import config

		selectedRow = self['list'].getCurrent()
		if selectedRow:
			sourcePath = selectedRow[4]
			targetPath = "%s%s.jpg" % (config.plugins.serienRec.coverPath.value, self._serien_fsid)
			shutil.copy(sourcePath, targetPath)
		self.close()

	def keyExit(self):
		self.close()


class CoverSelectorList(GUIComponent, object):
	GUI_WIDGET = eListbox

	def __init__(self):
		GUIComponent.__init__(self)
		self.l = eListboxPythonMultiContent()
		self.l.setFont(0, gFont("Regular", 19))
		self.l.setItemHeight(186)
		self.l.setBuildFunc(self.buildList)

	def buildList(self, entry):
		(cover_id, rating, language, path) = entry
		res = [None]

		# First column
		x, y, w, h = (5, 5, 120, 176)
		if fileExists(path):
			picloader = PicLoader(w, h)
			image = picloader.load(path)
			res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, x, y, w, h, image))
			picloader.destroy()
		else:
			res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_CENTER | RT_VALIGN_CENTER, "Ladefehler"))

		# Second column
		x, y, w, h = (150, 5, 300, 25)
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "ID: %s" % str(cover_id)))
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y + 35, w, h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "Sprache: %s" % str(language)))
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y + 60, w, h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "Bewertung: %0.1f" % rating))
		return res

	def getCurrent(self):
		cur = self.l.getCurrentSelection()
		return cur and cur[0]

	def postWidgetCreate(self, instance):
		instance.setContent(self.l)
		self.instance.setWrapAround(True)

	def preWidgetRemove(self, instance):
		instance.setContent(None)

	def setList(self, list):
		self.l.setList(list)

	def moveToIndex(self, idx):
		self.instance.moveSelectionTo(idx)

	def getSelectionIndex(self):
		return self.l.getCurrentSelectionIndex()

	def getSelectedIndex(self):
		return self.l.getCurrentSelectionIndex()

	def selectionEnabled(self, enabled):
		if self.instance is not None:
			self.instance.setSelectionEnable(enabled)

	def pageUp(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.pageUp)

	def pageDown(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.pageDown)

	def up(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.moveUp)

	def down(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.moveDown)
