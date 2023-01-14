# coding=utf-8

# This file contains the SerienRecoder Search Screen
import threading

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from Tools.Directories import fileExists

from enigma import ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from skin import parseColor

from . import SerienRecorder
from .SerienRecorderScreenHelpers import serienRecBaseScreen, updateMenuKeys, InitSkin, skinFactor

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard


class serienRecSearchResultScreen(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, serien_name):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)

		self.displayTimer = None
		self.displayMode = 2
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.resultlist = []
		self.markers = []
		self.skin = None
		self.displayTimer_conn = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "Marker für ausgewählte Serie hinzufügen"),
			"cancel": (self.keyCancel, "Zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "Zur vorherigen Seite blättern"),
			"right": (self.keyRight, "Zur nächsten Seite blättern"),
			"up": (self.keyUp, "Eine Zeile nach oben"),
			"down": (self.keyDown, "Eine Zeile nach unten"),
			"red": (self.keyRed, "Zurück zur vorherigen Ansicht"),
			"blue": (self.keyBlue, "Suche wiederholen und ggf. Suchbegriff ändern"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext": (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"	: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"2"	: (self.changeTVDBID, "TVDB-ID ändern"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.loading = True

		self.onLayoutFinish.append(self.searchSerie)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Abbrechen")
		self['text_ok'].setText("Marker hinzufügen")
		self['text_blue'].setText("Suche wiederholen")

		self.num_bt_text[2][0] = "TVDB-ID ändern"

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25 *skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_ok'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_ok'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def getCurrentSelection(self):
		serien_name = self['menu_list'].getCurrent()[0][0]
		serien_info = self['menu_list'].getCurrent()[0][1]
		serien_alias = self['menu_list'].getCurrent()[0][2]
		serien_wlid = self['menu_list'].getCurrent()[0][3]
		serien_fsid = self['menu_list'].getCurrent()[0][4]
		return serien_name, serien_info, serien_alias, serien_wlid, serien_fsid

	def changeTVDBID(self):
		from .SerienRecorderScreenHelpers import EditTVDBID
		(serien_name, serien_info, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		editTVDBID = EditTVDBID(self, self.session, serien_name, serien_alias, serien_wlid, serien_fsid, 0)
		editTVDBID.changeTVDBID()

	def serieInfo(self):
		if self.loading or self['menu_list'].getCurrent() is None:
			return

		(serien_name, serien_info, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		from .SerienRecorderSeriesInfoScreen import serienRecShowInfo
		self.session.open(serienRecShowInfo, serien_name, serien_wlid, serien_fsid)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.searchSerie()

	def searchSerie(self, start = 0):
		print("[SerienRecorder] suche ' %s '" % self.serien_name)
		self['title'].setText("Suche nach ' %s '" % self.serien_name)
		self['title'].instance.setForegroundColor(parseColor("foreground"))
		if start == 0:
			self.resultlist = []

		searchResults = downloadSearchResults(self.serien_name, start)
		searchResults.start()
		searchResults.join()

		self.results(searchResults.getData())

	def results(self, resultlist):
		(startOffset, moreResults, searchResults) = resultlist
		self.resultlist.extend(searchResults)
		self['title'].setText("Die Suche nach ' %s ' ergab %s Treffer." % (self.serien_name, str(len(self.resultlist))))
		self['title'].instance.setForegroundColor(parseColor("foreground"))

		# deep copy list
		resultList = self.resultlist[:]

		if moreResults > 0:
			resultList.append(("", "", "", "", "", 0))
			resultList.append(("=> Weitere Ergebnisse laden?", str(moreResults), "", "-1", "", 0))
		self.chooseMenuList.setList(list(map(self.buildList, resultList)))
		self['menu_list'].moveToIndex(startOffset)
		self.loading = False
		self.getCover()

	@staticmethod
	def buildList(entry):
		(serien_name, serien_info, serien_alias, serien_wlid, serien_fsid, marker_flag) = entry

		# weitere Ergebnisse Eintrag
		if serien_wlid == "-1":
			serien_info = ""

		if marker_flag == 1:
			seriesColor = parseColor('green').argb()
		elif marker_flag == 2:
			seriesColor = parseColor('red').argb()
		else:
			seriesColor = None

		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 40, 0, 500 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, seriesColor, seriesColor),
		        (eListboxPythonMultiContent.TYPE_TEXT, 600 * skinFactor, 0, 350 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_info)
		        ]

	@staticmethod
	def createMarker(serien_wlid, serien_name, serien_info, serien_fsid):
		result = False

		from .SerienRecorderDatabase import SRDatabase
		database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
			boxID = None
		else:
			boxID = config.plugins.serienRec.BoxID.value

		if database.addMarker(str(serien_wlid), serien_name, serien_info, serien_fsid, boxID, 0):
			from .SerienRecorderLogWriter import SRLogger
			SRLogger.writeLog("Ein Serien-Marker für '%s (%s)' wurde angelegt" % (serien_name, serien_info), True)
			result = True

		return result

	def keyOK(self):
		if self.loading or self['menu_list'].getCurrent() is None:
			return

		(serien_name, serien_info, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		#print(serien_name, serien_info, serien_wlid, serien_fsid)

		if serien_wlid == "":
			return

		if serien_wlid == "-1":
			self.chooseMenuList.setList([])
			self.searchSerie(int(serien_info))
			return

		self.serien_name = ""
		if serienRecSearchResultScreen.createMarker(serien_wlid, serien_name, serien_info, serien_fsid):
			self['title'].setText("Marker '%s (%s)' wurde angelegt." % (serien_name, serien_info))
			self['title'].instance.setForegroundColor(parseColor("green"))

			from .SerienRecorder import getCover
			getCover(self, serien_name, serien_fsid, False, True)

			if config.plugins.serienRec.openMarkerScreen.value:
				self.close(serien_fsid)
		else:
			self['title'].setText("Marker '%s (%s)' ist schon vorhanden." % (serien_name, serien_info))
			self['title'].instance.setForegroundColor(parseColor("red"))

	def keyRed(self):
		self.close()

	def keyBlue(self):
		self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:", text = self.serien_name)

	def wSearch(self, serien_name):
		if serien_name:
			#print(serien_name)
			self.chooseMenuList.setList([])
			self['title'].setText("")
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			self.serien_name = serien_name
			self.resultlist = []
			self.searchSerie()

	def keyLeft(self):
		self['menu_list'].pageUp()
		self.getCover()

	def keyRight(self):
		self['menu_list'].pageDown()
		self.getCover()

	def keyDown(self):
		self['menu_list'].down()
		self.getCover()

	def keyUp(self):
		self['menu_list'].up()
		self.getCover()

	def wunschliste(self):
		serien_fsid = self['menu_list'].getCurrent()[0][4]
		super(self.__class__, self).wunschliste(serien_fsid)

	def getCover(self):
		if self.loading or self['menu_list'].getCurrent() is None:
			return

		(serien_name, serien_info, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		SerienRecorder.getCover(self, serien_name, serien_fsid)

	def __onClose(self):
		self.stopDisplayTimer()

	def keyCancel(self):
		self['title'].instance.setForegroundColor(parseColor("foreground"))
		self.close()

class downloadSearchResults(threading.Thread):
	def __init__ (self, seriesName, startOffset):
		threading.Thread.__init__(self)
		self.seriesName = seriesName
		self.startOffset = startOffset
		self.searchResults = None
	def run(self):
		from .SerienRecorderSeriesServer import SeriesServer
		self.searchResults = SeriesServer().doSearch(self.seriesName, self.startOffset)

	def getData(self):
		return self.searchResults
