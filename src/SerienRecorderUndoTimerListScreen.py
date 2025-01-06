# coding=utf-8

# This file contains the SerienRecoder Undo Timer-List Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList
from Components.config import config

from enigma import ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from skin import parseColor

from .SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, skinFactor
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorder import getDataBaseFilePath, getCover

class serienRecUndoTimerList(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.database = SRDatabase(getDataBaseFilePath())
		self.lastSelectedFSID = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "Zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "Zur vorherigen Seite blättern"),
			"right": (self.keyRight, "Zur nächsten Seite blättern"),
			"up": (self.keyUp, "Eine Zeile nach oben"),
			"down": (self.keyDown, "Eine Zeile nach unten"),
			"red": (self.keyRed, "Ausgewählten Eintrag löschen"),
			"green": (self.keyGreen, "Ausgewählten Timer wiederherstellen"),
			"yellow": (self.keyYellow, "Alle Timer des ausgewählten Tages wiederherstellen"),
			"blue": (self.keyBlue, "Alle Timer der ausgewählten Serie wiederherstellen"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"0"	: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
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

		self.undoList = []

		self.onLayoutFinish.append(self.getUndoList)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Eintrag löschen")
		self['text_green'].setText("Wiederherstellen")
		self['text_yellow'].setText("Alle des Tages")
		self['text_blue'].setText("Alle der Serie")
		self.num_bt_text[1][0] = buttonText_na
		print('[SerienRecorder] setSkinProperties')

		super(self.__class__, self).startDisplayTimer()

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setupSkin(self):
		self.skin = None
		InitSkin(self)
		print('[SerienRecorder] setupSkin')

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25 *skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_yellow'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def getCurrentSelection(self):
		if self['menu_list'].getCurrent() is None:
			return None, None, None
		created = self['menu_list'].getCurrent()[0][0]
		series_name = self['menu_list'].getCurrent()[0][3]
		series_fsid = self['menu_list'].getCurrent()[0][4]
		series_wlid = self.database.getMarkerWLID(series_fsid)
		return created, series_name, series_wlid, series_fsid

	def serieInfo(self):
		(created, series_name, series_wlid, series_fsid) = self.getCurrentSelection()
		if series_name and series_wlid:
			from .SerienRecorderSeriesInfoScreen import serienRecShowInfo
			self.session.open(serienRecShowInfo, series_name, series_wlid, series_fsid)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.getUndoList()

	def getUndoList(self):
		self.undoList = []
		print('[SerienRecorder] getUndoList')

		def loadUndoTimer():
			print("[SerienRecorder] loadUndoTimer")
			database = SRDatabase(getDataBaseFilePath())
			return database.getUndoTimer()

		def onLoadUndoTimerSuccessful(timers):
			print('[SerienRecorder] onLoadUndoTimerSuccessful')
			for timer in timers:
				(row_id, series, season, episode, title, fsid, created) = timer
				title_string = "%s - S%sE%s - %s" % (series, str(season).zfill(2), str(episode).zfill(2), title)
				self.undoList.append((created, title_string, row_id, series, fsid))

			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("%d gelöschte Timer-Einträge können wiederhergestellt werden" % len(self.undoList))

			self.chooseMenuList.setList(list(map(self.buildList, self.undoList)))
			self.getCover()

		def onLoadUndoTimerFailed(exception):
			print("[SerienRecorder] Laden der Undo Timer fehlgeschlagen: " + str(exception))

		self['title'].setText("Lade Liste der gelöschten Timer...")

		import twisted.python.runtime
		if twisted.python.runtime.platform.supportsThreads():
			from twisted.internet.threads import deferToThread
			deferToThread(loadUndoTimer).addCallback(onLoadUndoTimerSuccessful).addErrback(onLoadUndoTimerFailed)
		else:
			onLoadUndoTimerSuccessful(loadUndoTimer())

	@staticmethod
	def buildList(entry):
		(created, title_string, row_id, series_name, series_fsid) = entry
		foregroundColor = parseColor('foreground').argb()
		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 20, 0, 180 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, created, foregroundColor),
		        (eListboxPythonMultiContent.TYPE_TEXT, 220 * skinFactor, 0, 1060 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title_string, foregroundColor)
		        ]

	def keyGreen(self):
		if self['menu_list'].getCurrent() is None:
			return

		entry = self['menu_list'].getCurrent()[0]
		(created, title_string, row_id, series_name, series_fsid) = entry
		self.database.restoreUndoTimerByID(row_id)
		self.getUndoList()

	def keyYellow(self):
		if self['menu_list'].getCurrent() is None:
			return

		entry = self['menu_list'].getCurrent()[0]
		(created, title_string, row_id, series_name, series_fsid) = entry
		self.database.restoreUndoTimerByDate(created[0:10])
		self.getUndoList()

	def keyBlue(self):
		if self['menu_list'].getCurrent() is None:
			return

		entry = self['menu_list'].getCurrent()[0]
		(created, title_string, row_id, series_name, series_fsid) = entry
		self.database.restoreUndoTimerBySeries(series_fsid)
		self.getUndoList()

	def keyRed(self):
		if self['menu_list'].getCurrent() is None:
			return

		entry = self['menu_list'].getCurrent()[0]
		(created, title_string, row_id, series_name, series_fsid) = entry
		self.database.deleteUndoTimer(row_id)
		self.getUndoList()

	def getCover(self):
		if self['menu_list'].getCurrent() is None:
			return

		(created, series_name, series_wlid, series_fsid) = self.getCurrentSelection()
		self['text_yellow'].setText("Alle vom %s%s" % (created[0:6], created[8:10]))
		if series_name and series_fsid and self.lastSelectedFSID != series_fsid:
			getCover(self, series_name, series_fsid)
			# Avoid flickering while scrolling through timers of same series
			self.lastSelectedFSID = series_fsid

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

	def __onClose(self):
		self.stopDisplayTimer()

	def keyCancel(self):
		self.close()
