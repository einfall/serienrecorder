# coding=utf-8

# This file contains the SerienRecoder Wishlist Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from Tools.Directories import fileExists

from enigma import ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER

import SerienRecorder
from SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, skinFactor
from SerienRecorderDatabase import SRDatabase

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard


class serienRecWishlistScreen(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "für die ausgewählte Serien neue Einträge hinzufügen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyRed, "ausgewählten Eintrag löschen"),
			"green" : (self.keyGreen, "alle Änderungen speichern und zurück zur vorherigen Ansicht"),
			"yellow": (self.keyYellow, "umschalten Sortierung ein/aus"),
			"blue"	: (self.keyBlue, "alle Einträge aus der Liste endgültig löschen"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.delAdded = False
		self.wishlist = []
		self.wishlist_tmp = []
		self.dbData = []
		self.modus = "menu_list"
		self.aSerie = ""
		self.aStaffel = 0
		self.aFromEpisode = 0
		self.aToEpisode = 0

		self.onLayoutFinish.append(self.readWishlist)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Eintrag löschen")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Eintrag anlegen")
		if config.plugins.serienRec.wishListSorted.value:
			self['text_yellow'].setText("unsortierte Liste")
		else:
			self['text_yellow'].setText("Sortieren")
		self['text_blue'].setText("Liste leeren")
		self.num_bt_text[2][1] = buttonText_na

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

		self['title'].setText("Diese Episoden sind zur Aufnahme vorgemerkt")

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

	def serieInfo(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return
			serien_name = self['menu_list'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check is None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		serien_id = None
		url = self.database.getMarkerURL(serien_name)
		if url:
			from SerienRecorderHelpers import getSeriesIDByURL
			serien_id = getSeriesIDByURL(url)
		if serien_id:
			from SerienRecorderSeriesInfoScreen import serienRecShowInfo
			self.session.open(serienRecShowInfo, serien_name, serien_id)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.readWishlist()

	def readWishlist(self):
		self.wishlist = []
		bookmarks = self.database.getBookmarks()
		for bookmark in bookmarks:
			(Serie, Staffel, Episode, numberOfRecordings) = bookmark
			zeile = "%s S%sE%s" % (Serie, str(Staffel).zfill(2), str(Episode).zfill(2))
			self.wishlist.append((zeile, Serie, Staffel, Episode))

		self.wishlist_tmp = self.wishlist[:]
		if config.plugins.serienRec.wishListSorted.value:
			self.wishlist_tmp.sort()
		self.chooseMenuList.setList(map(self.buildList, self.wishlist_tmp))
		self.getCover()

	@staticmethod
	def buildList(entry):
		(zeile, Serie, Staffel, Episode) = entry
		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
		        ]

	@staticmethod
	def buildList_popup(entry):
		(Serie,) = entry
		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 560 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie)
		        ]

	def answerStaffel(self, aStaffel):
		self.aStaffel = aStaffel
		if self.aStaffel is None or self.aStaffel == "":
			return
		self.session.openWithCallback(self.answerFromEpisode, NTIVirtualKeyBoard, title = "von Episode:")

	def answerFromEpisode(self, aFromEpisode):
		self.aFromEpisode = aFromEpisode
		if self.aFromEpisode is None or self.aFromEpisode == "":
			return
		self.session.openWithCallback(self.answerToEpisode, NTIVirtualKeyBoard, title = "bis Episode:")

	def answerToEpisode(self, aToEpisode):
		self.aToEpisode = aToEpisode
		print "[SerienRecorder] Staffel: %s" % self.aStaffel
		print "[SerienRecorder] von Episode: %s" % self.aFromEpisode
		print "[SerienRecorder] bis Episode: %s" % self.aToEpisode

		if self.aToEpisode is None or self.aFromEpisode is None or self.aStaffel is None or self.aToEpisode == "":
			return
		else:
			self.database.addBookmark(self.aSerie, self.aFromEpisode, self.aToEpisode, self.aStaffel, int(config.plugins.serienRec.NoOfRecords.value))
			self.readWishlist()

	def keyOK(self):
		if self.modus == "menu_list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['menu_list'].hide()
			l = self.database.getMarkerNames()
			self.chooseMenuList_popup.setList(map(self.buildList_popup, l))
			self['popup_list'].moveToIndex(0)
		else:
			self.modus = "menu_list"
			self['menu_list'].show()
			self['popup_list'].hide()
			self['popup_bg'].hide()

			if self['popup_list'].getCurrent() is None:
				print "[SerienRecorder] Marker-Liste leer."
				return

			self.aSerie = self['popup_list'].getCurrent()[0][0]
			self.aStaffel = 0
			self.aFromEpisode = 0
			self.aToEpisode = 0
			self.session.openWithCallback(self.answerStaffel, NTIVirtualKeyBoard, title = "%s: Staffel eingeben:" % self.aSerie)

	def keyRed(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Merkzettel ist leer."
			return
		else:
			zeile = self['menu_list'].getCurrent()[0]
			(title, serie, staffel, episode) = zeile
			self.dbData.append((serie.lower(), str(staffel).lower(), episode.lower()))
			self.wishlist_tmp.remove(zeile)
			self.wishlist.remove(zeile)
			self.chooseMenuList.setList(map(self.buildList, self.wishlist_tmp))
			self.delAdded = True

	def keyGreen(self):
		if self.delAdded:
			self.database.removeBookmarks(self.dbData)
		self.close()

	def keyYellow(self):
		if len(self.wishlist_tmp) != 0:
			if config.plugins.serienRec.wishListSorted.value:
				self.wishlist_tmp = self.wishlist[:]
				self['text_yellow'].setText("Sortieren")
				config.plugins.serienRec.wishListSorted.setValue(False)
			else:
				self.wishlist_tmp.sort()
				self['text_yellow'].setText("unsortierte Liste")
				config.plugins.serienRec.wishListSorted.setValue(True)
			config.plugins.serienRec.wishListSorted.save()
			SerienRecorder.configfile.save()

			self.chooseMenuList.setList(map(self.buildList, self.wishlist_tmp))
			self.getCover()

	def keyBlue(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Merkzettel ist leer."
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callClearListMsg, MessageBox, "Soll die Liste wirklich geleert werden?", MessageBox.TYPE_YESNO, default = False)
			else:
				self.callClearListMsg(True)

	def callClearListMsg(self, answer):
		if answer:
			self.database.removeAllBookmarks()
			self.readWishlist()
		else:
			return

	def getCover(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return
			serien_name = self['menu_list'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check is None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		serien_id = None
		url = self.database.getMarkerURL(serien_name)
		if url:
			from SerienRecorderHelpers import getSeriesIDByURL
			serien_id = getSeriesIDByURL(url)

		SerienRecorder.getCover(self, serien_name, serien_id)

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
		self.close()

	def keyCancel(self):
		if self.delAdded:
			self.session.openWithCallback(self.callDeleteMsg, MessageBox, "Sollen die Änderungen gespeichert werden?", MessageBox.TYPE_YESNO, default = True)
		else:
			self.close()
