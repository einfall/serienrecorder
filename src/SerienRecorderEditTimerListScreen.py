# coding=utf-8

# This file contains the SerienRecoder Edit Timer-List Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList
from Components.config import config, configfile
from Tools.Directories import fileExists

from enigma import ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from skin import parseColor
import time, re

from .SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, skinFactor
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorder import getDataBaseFilePath, getCover

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard


class serienRecEditTimerList(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.database = SRDatabase(getDataBaseFilePath())
		self.database.beginTransaction()
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "Für die ausgewählte Serie neue Einträge hinzufügen"),
			"cancel": (self.keyCancel, "Alle Änderungen verwerfen und zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "Zur vorherigen Seite blättern"),
			"right": (self.keyRight, "Zur nächsten Seite blättern"),
			"up": (self.keyUp, "Eine Zeile nach oben"),
			"down": (self.keyDown, "Eine Zeile nach unten"),
			"red": (self.keyRed, "Ausgewählten Eintrag löschen"),
			"green": (self.keyGreen, "Alle Änderungen speichern und zurück zur vorherigen Ansicht"),
			"yellow": (self.keyYellow, "Sortierung umschalten (Chronologisch/Alphabetisch)"),
			"blue": (self.keyBlue, "Timer Einträge wiederherstellen"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"0"	: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"nextBouquet": (self.previousSeries, "Zur vorherigen Serie springen"),
			"prevBouquet": (self.nextSeries, "Zur nächsten Serie springen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.changed = False
		self.addedlist = []
		self.addedlist_tmp = []
		self.modus = "menu_list"
		self.aSerie = ""
		self.aSerieFSID = None
		self.aStaffel = "0"
		self.aFromEpisode = 0
		self.aToEpisode = 0
		self.lastSelectedFSID = None

		self.onLayoutFinish.append(self.readAdded)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Eintrag löschen")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Neuer Eintrag")
		if config.plugins.serienRec.addedListSorted.value:
			self['text_yellow'].setText("Chronologisch")
		else:
			self['text_yellow'].setText("Alphabetisch")
		self['text_blue'].setText("Wiederherstellen")
		self.num_bt_text[1][0] = buttonText_na

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25 *skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(int(25 *skinFactor))
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			#self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
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
		if self.modus == "menu_list":
			if self['menu_list'].getCurrent() is None:
				return None, None, None
			serien_name = self['menu_list'].getCurrent()[0][2]
			serien_fsid = self['menu_list'].getCurrent()[0][8]
		else:
			if self['popup_list'].getCurrent() is None:
				return None, None, None
			serien_name = self['popup_list'].getCurrent()[0][0]
			serien_fsid = self['popup_list'].getCurrent()[0][3]
		serien_wlid = self.database.getMarkerWLID(serien_fsid)
		return serien_name, serien_wlid, serien_fsid

	def serieInfo(self):
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_name and serien_wlid:
			from .SerienRecorderSeriesInfoScreen import serienRecShowInfo
			self.session.open(serienRecShowInfo, serien_name, serien_wlid, serien_fsid)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.readAdded()

	def readAdded(self):
		self.addedlist = []
		series = []

		def loadAllTimer(database):
			print("[SerienRecorder] loadAllTimer")
			return database.getAllTimer(None)

		def onLoadAllTimerSuccessful(timers):
			for timer in timers:
				(row_id, serien_name, serien_season, serien_episode, serien_title, start_time, stbRef, webChannel, eit, active, serien_fsid) = timer
				series.append(serien_name)
				text = "%s - S%sE%s - %s" % (serien_name, str(serien_season).zfill(2), str(serien_episode).zfill(2), serien_title)
				text = text.replace(" - dump", " - %s" % "(Manuell hinzugefügt !!)").replace(" - webdump", " - %s" % "(Manuell übers Webinterface hinzugefügt !!)")
				self.addedlist.append((text, row_id, serien_name, serien_season, serien_episode, serien_title, start_time, webChannel, serien_fsid))

			self.addedlist_tmp = self.addedlist[:]
			number_of_series = len(set(series))
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("Keine weiteren Timer für %d Episoden aus %d Serien" % (len(self.addedlist_tmp), number_of_series))

			if config.plugins.serienRec.addedListSorted.value:
				self.addedlist_tmp.sort(key=lambda x: (x[2].lower(), self.alphanum_key(x[3]), self.alphanum_key(x[4])))
			self.chooseMenuList.setList(list(map(self.buildList, self.addedlist_tmp)))
			self.getCover()

		def onLoadAllTimerFailed(exception):
			print("[SerienRecorder]: Laden aller Timer fehlgeschlagen: " + str(exception))

		self['title'].setText("Lade Liste aller Timer...")

		# import twisted.python.runtime
		# if twisted.python.runtime.platform.supportsThreads():
		# 	from twisted.internet.threads import deferToThread
		# 	deferToThread(loadAllTimer).addCallback(onLoadAllTimerSuccessful).addErrback(onLoadAllTimerFailed)
		# else:
		# 	allTimers = loadAllTimer()
		# 	onLoadAllTimerSuccessful(allTimers)
		
		allTimers = loadAllTimer(self.database)
		onLoadAllTimerSuccessful(allTimers)	

	@staticmethod
	def alphanum_key(s):
		return [int(text) if text.isdigit() else text for text in re.split('([0-9]+)', s)]
	
	@staticmethod
	def buildList(entry):
		(row_text, row_id, serien_name, serien_season, serien_episode, serien_title, start_time, webChannel, serien_fsid) = entry
		foregroundColor = parseColor('foreground').argb()
		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row_text, foregroundColor)
		        ]

	@staticmethod
	def buildList_popup(entry):
		(serien_name, serien_wlid, serien_info, serien_fsid) = entry
		foregroundColor = parseColor('foreground').argb()
		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 560 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s (%s)" % (serien_name, serien_info), foregroundColor)
		        ]

	def answerStaffel(self, aStaffel):
		if not aStaffel:
			return

		self.aStaffel = aStaffel.strip()
		if len(self.aStaffel) == 0:
			return

		self.session.openWithCallback(self.answerFromEpisode, NTIVirtualKeyBoard, title = "von Episode:")

	def answerFromEpisode(self, aFromEpisode):
		self.aFromEpisode = aFromEpisode
		if not self.aFromEpisode or len(self.aFromEpisode) == 0:
			return
		self.session.openWithCallback(self.answerToEpisode, NTIVirtualKeyBoard, title = "bis Episode:")

	def answerToEpisode(self, aToEpisode):
		self.aToEpisode = aToEpisode
		if len(self.aToEpisode) == 0:
			self.aToEpisode = self.aFromEpisode

		if self.aToEpisode is None: # or self.aFromEpisode is None or self.aStaffel is None:
			return

		print("[SerienRecorder] Staffel: %s" % self.aStaffel)
		print("[SerienRecorder] von Episode: %s" % self.aFromEpisode)
		print("[SerienRecorder] bis Episode: %s" % self.aToEpisode)

		if self.aStaffel.startswith('0') and len(self.aStaffel) > 1:
			self.aStaffel = self.aStaffel[1:]

		if self.database.addToTimerList(self.aSerie, self.aSerieFSID, self.aFromEpisode, self.aToEpisode, self.aStaffel, "dump", int(time.time()), "", "", 0, 1):
			self.changed = True
			self.readAdded()

	def keyOK(self):
		if self.modus == "menu_list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['menu_list'].hide()
			l = self.database.getMarkerNames()
			self.chooseMenuList_popup.setList(list(map(self.buildList_popup, l)))
			self['popup_list'].moveToIndex(0)
		else:
			self.modus = "menu_list"
			self['menu_list'].show()
			self['popup_list'].hide()
			self['popup_bg'].hide()

			if self['popup_list'].getCurrent() is None:
				print("[SerienRecorder] Marker-Liste leer.")
				return

			self.aSerie = self['popup_list'].getCurrent()[0][0]
			self.aSerieFSID = self['popup_list'].getCurrent()[0][3]
			self.aStaffel = "0"
			self.aFromEpisode = 0
			self.aToEpisode = 0
			self.session.openWithCallback(self.answerStaffel, NTIVirtualKeyBoard, title = "%s: Staffel eingeben:" % self.aSerie)

	def keyRed(self):
		if self.modus == "menu_list":
			if self['menu_list'].getCurrent() is None:
				return

			entry = self['menu_list'].getCurrent()[0]
			(txt, row_id, serien_name, serien_season, serien_episode, serien_title, start_time, webChannel, serien_fsid) = entry
			
			self.database.removeTimers([row_id])
			self.changed = True
			self.readAdded()

	def keyGreen(self):
		self.database.commitTransaction()
		self.close()

	def keyYellow(self):
		if self.modus == "menu_list" and len(self.addedlist_tmp) != 0:
			if config.plugins.serienRec.addedListSorted.value:
				self.addedlist_tmp = self.addedlist[:]
				self['text_yellow'].setText("Alphabetisch")
				config.plugins.serienRec.addedListSorted.setValue(False)
			else:
				self.addedlist_tmp.sort(key=lambda x: (x[2].lower(), self.alphanum_key(x[3]), self.alphanum_key(x[4])))
				self['text_yellow'].setText("Chronologisch")
				config.plugins.serienRec.addedListSorted.setValue(True)
			config.plugins.serienRec.addedListSorted.save()
			configfile.save()

			self.chooseMenuList.setList(list(map(self.buildList, self.addedlist_tmp)))
			self.getCover()

	def keyBlue(self):
		from .SerienRecorderUndoTimerListScreen import serienRecUndoTimerList
		self.session.open(serienRecUndoTimerList)

	def previousSeries(self):
		(selected_serien_name, selected_serien_wlid, selected_serien_fsid) = self.getCurrentSelection()
		selectedIndex = self['menu_list'].getSelectedIndex()
		for i, (txt, row_id, serie, staffel, episode, title, start_time, webChannel, serien_fsid) in reversed(list(enumerate(self.addedlist_tmp[:selectedIndex]))):
			if serien_fsid != selected_serien_fsid or i == 0:
				self['menu_list'].moveToIndex(i)
				break
		self.getCover()

	def nextSeries(self):
		(selected_serien_name, selected_serien_wlid, selected_serien_fsid) = self.getCurrentSelection()
		selectedIndex = self['menu_list'].getSelectedIndex()
		for i, (txt, row_id, serie, staffel, episode, title, start_time, webChannel, serien_fsid) in list(enumerate(self.addedlist_tmp[selectedIndex:])):
			if serien_fsid != selected_serien_fsid or selectedIndex + i == len(self.addedlist_tmp):
				self['menu_list'].moveToIndex(selectedIndex + i)
				break
		self.getCover()

	def getCover(self):
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_name and serien_fsid and self.lastSelectedFSID != serien_fsid:
			getCover(self, serien_name, serien_fsid)
			# Avoid flickering while scrolling through timers of same series
			self.lastSelectedFSID = serien_fsid

	def keyLeft(self):
		self[self.modus].pageUp()
		self.getCover()

	def keyRight(self):
		self[self.modus].pageDown()
		self.getCover()

	def keyDown(self):
		self[self.modus].down()
		self.getCover()

	def keyUp(self):
		self[self.modus].up()
		self.getCover()

	def __onClose(self):
		self.stopDisplayTimer()

	def callDeleteMsg(self, answer):
		if answer:
			self.keyGreen()
		else:
			self.database.rollbackTransaction()
			self.close()

	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "menu_list"
			self['menu_list'].show()
			self['popup_list'].hide()
			self['popup_bg'].hide()
		else:
			if self.changed:
				self.session.openWithCallback(self.callDeleteMsg, MessageBox, "Sollen die Änderungen gespeichert werden?", MessageBox.TYPE_YESNO, default = True)
				self.close()
			else:
				self.database.rollbackTransaction()
				self.close()
