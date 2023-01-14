# coding=utf-8

# This file contains the SerienRecoder TVDB Selector Screen
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.GUIComponent import GUIComponent
from Screens.MessageBox import MessageBox

from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_VALIGN_CENTER, RT_HALIGN_LEFT, RT_HALIGN_CENTER, RT_WRAP
from enigma import getDesktop

from twisted.internet import defer

from Tools.Directories import fileExists

from .SerienRecorderHelpers import PicLoader, toStr

import os

class TVDBSelectorScreen(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	DIALOG_WIDTH = 680
	DIALOG_HEIGHT = DESKTOP_HEIGHT - 180

	skin = """
			<screen name="TVDBSelectorScreen" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20">
				<widget name="headline" position="10,6" size="660,52" foregroundColor="green" backgroundColor="#26181d20" transparent="1" font="Regular;19" valign="center" halign="left" />
				<widget name="list" position="5,66" size="%d,%d" scrollbarMode="showOnDemand"/>
				<widget name="footer" position="10,%d" size="500,26" foregroundColor="green" backgroundColor="#26181d20" transparent="1" font="Regular;19" valign="center" halign="left" />
				<eLabel text="MENU" position="%d,%d" size="60,25" backgroundColor="#777777" valign="center" halign="center" font="Regular;18"/>
			</screen>""" % (50, 100, DIALOG_WIDTH, DIALOG_HEIGHT, "SerienRecorder TVDB ändern",
	                        DIALOG_WIDTH - 10, DIALOG_HEIGHT - 96,
                            DIALOG_HEIGHT - 28,
                            DIALOG_WIDTH - 65, DIALOG_HEIGHT - 28
	                        )

	def __init__(self, session, parent, series_id, series_name, series_alias, series_fsid, tvdb_id):
		Screen.__init__(self, session)

		self._session = session
		self._parent = parent
		self._series_name = series_name
		self._series_alias = series_alias
		self._series_id = series_id
		self._series_fsid = series_fsid
		self._tvdb_id = tvdb_id
		self._tempDir = '/tmp/serienrecorder/'
		self._searchResultList = []
		self._numberOfSearchResults = 0
		self._searchTerm = ""

		if os.path.exists(self._tempDir) is False:
			os.mkdir(self._tempDir)

		self['headline'] = Label("Welche ID soll für die Serie gespeichert werden?")
		self['list'] = TVDBIDSelectorList()
		self['footer'] = Label("Suche wird ausgeführt...")

		self["actions"] = ActionMap(["SerienRecorderActions",], {
			"ok"    : self.keyOK,
			"green" : self.keyOK,
			"cancel": self.keyExit,
			"red"   : self.keyExit,
			"menu"  : self.menu,
		}, -1)

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		self.doSearch(self._series_name)

	def doSearch(self, searchTerm):
		self._numberOfSearchResults = 0
		self._searchResultList = []
		self._searchTerm = searchTerm

		self['list'].setList(self._searchResultList)
		if self._series_alias and len(self._series_alias) > 0:
			self['headline'].setText("%s (%s)" % (self._series_name, self._series_alias))
		else:
			self['headline'].setText(self._series_name)
		from .SerienRecorderSeriesServer import SeriesServer
		print("[SerienRecorder] Search TVDB series: " + str(self._searchTerm))
		searchResults = SeriesServer().doSearchTVDBSeries(self._searchTerm)
		if searchResults is not None:
			self._numberOfSearchResults = len(searchResults)
			print("[SerienRecorder] Number of search results found = " + str(self._numberOfSearchResults))

			ds = defer.DeferredSemaphore(tokens=5)
			downloads = [ds.run(self.download, searchResult).addCallback(self.buildList, searchResult).addErrback(self.buildList, searchResult) for searchResult in searchResults]
			defer.DeferredList(downloads).addErrback(self.dataError).addCallback(self.dataFinish)
		else:
			self['footer'].setText("Keine Cover gefunden!")

	def download(self, searchResult):
		from twisted.web import client
		from .SerienRecorderHelpers import toBinary

		path = self._tempDir + str(searchResult['tvdb_id']) + '.jpg'
		print("[SerienRecorder] Temp cover path = " + path)
		if not fileExists(path):
			print("[SerienRecorder] Downloading cover %s => %s" % (searchResult['thumbnail'], path))
			return client.downloadPage(toBinary(searchResult['thumbnail']), path)
		else:
			return True

	def buildList(self, data, searchResult):
		name = searchResult['name']
		overview = searchResult['overview']
		if len(searchResult['name']) == 0:
			name = searchResult['original_name']

		if len(searchResult['overview']) == 0:
			overview = searchResult['original_overview']

		self._searchResultList.append(((searchResult['tvdb_id'], searchResult['year'], name, overview, self._tempDir + str(searchResult['tvdb_id']) + '.jpg'),))
		self['list'].setList(self._searchResultList)

	def dataError(self, error):
		print("[SerienRecorder] Cover download error = ", error)
		self['footer'].setText("Fehler beim Laden der Cover!")

	def dataFinish(self, res):
		self['footer'].setText("Es wurden %d Serien gefunden" % self._numberOfSearchResults)

		# Select row
		if self._tvdb_id:
			try:
				idx = [i[0] for i in list(*zip(*self._searchResultList))].index(str(self._tvdb_id))
				self['list'].moveToIndex(idx)
			except Exception:
				pass

	def keyOK(self):
		selectedRow = self['list'].getCurrent()
		if selectedRow:
			tvdb_id = selectedRow[0]
			self.setTVDBID(tvdb_id)

	def menu(self):
		menu_list = [("TVDB-ID eingeben", "enter_tvdb_id"), ("Cover aktualisieren", "reload_cover")]
		if self._series_alias and len(self._series_alias) > 0:
			menu_list.append(("Mit Aliasnamen suchen", "search_with_alias"))
		if " - " in self._series_name:
			menu_list.append(("Nach '%s' suchen" % self._series_name[0:self._series_name.find(" - ")], "search_substring"))

		from Screens.ChoiceBox import ChoiceBox
		self.session.openWithCallback(self.menuCallback, ChoiceBox, title=self._searchTerm, list=menu_list)

	def menuCallback(self, ret):
		ret = ret and ret[1]
		if ret:
			if ret == "enter_tvdb_id":
				self.enterTVDBID()
			if ret == "reload_cover":
				from .SerienRecorder import getCover
				getCover(self._parent, self._series_name, self._series_fsid, False, True)
				self.close()
			if ret == "search_with_alias":
				# If there are more than one alias they are separated by slashes
				# We will use the first alias only
				aliases = self._series_alias.split("/")
				searchTerm = aliases[0]
				if searchTerm == self._searchTerm:
					searchTerm = self._series_name
				self.doSearch(searchTerm)
			if ret == "search_substring":
				searchTerm = self._series_name[0:self._series_name.find(" - ")]
				self.doSearch(searchTerm)

	def enterTVDBID(self):
			tvdb_id_text = str(self._tvdb_id) if self._tvdb_id > 0 else ''
			from Screens.InputBox import InputBox
			from Components.Input import Input
			self.session.openWithCallback(self.setTVDBID, InputBox, title="TVDB-ID (zum Löschen eine 0 eingeben):",
		                              windowTitle="TVDB-ID hinzufügen/ändern", text=tvdb_id_text, type=Input.NUMBER)

	def setTVDBID(self, tvdb_id):
		if tvdb_id:
			from .SerienRecorderSeriesServer import SeriesServer
			if not SeriesServer().setTVDBID(self._series_id, tvdb_id):
				self.session.open(MessageBox, "Die TVDB-ID konnte nicht auf dem SerienServer geändert werden!", MessageBox.TYPE_ERROR, timeout=5)

			from .SerienRecorder import getCover
			getCover(self._parent, self._series_name, self._series_fsid, False, True)
		self.close()

	def keyExit(self):
		self.close()


class TVDBIDSelectorList(GUIComponent, object):
	GUI_WIDGET = eListbox

	def __init__(self):
		GUIComponent.__init__(self)
		self.l = eListboxPythonMultiContent()
		self.l.setFont(0, gFont("Regular", 19))
		self.l.setItemHeight(186)
		self.l.setBuildFunc(self.buildList)

	def buildList(self, entry):
		(tvdb_id, year, name, overview, path) = entry
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
		x, y, w, h = (150, 5, 515, 25)
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s" % str(tvdb_id)))
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y + 30, w, h, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s" % toStr(name)))
		res.append((eListboxPythonMultiContent.TYPE_TEXT, x, y + 60, w, 110, 0, RT_HALIGN_LEFT | RT_WRAP, "%s" % toStr(overview)))
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
