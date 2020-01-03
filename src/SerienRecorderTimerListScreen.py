# coding=utf-8

# This file contains the SerienRecoder Timer-List Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList
from Components.config import config
from Tools.Directories import fileExists

from enigma import ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, loadPNG, RT_VALIGN_CENTER
from skin import parseColor
import time, re

import SerienRecorder
from SerienRecorderHelpers import PiconLoader, PicLoader, STBHelpers
from SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, skinFactor
from SerienRecorderDatabase import SRDatabase

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard


class serienRecTimerListScreen(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.skin = None
		self.session = session
		self.picload = ePicLoad()
		self.piconLoader = PiconLoader()
		self.WochenTag = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		self.channelList = STBHelpers.buildSTBChannelList()

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "Liste der erstellten Timer bearbeiten"),
			"cancel": (self.keyCancel, "zurück zur Serienplaner-Ansicht"),
			"left": (self.keyLeft, "zur vorherigen Seite blättern"),
			"right": (self.keyRight, "zur nächsten Seite blättern"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"red": (self.keyRed, "ausgewählten Timer löschen"),
			"green": (self.viewChange, "Sortierung ändern"),
			"yellow": (self.keyYellow, "umschalten alle/nur aktive Timer anzeigen"),
			"blue": (self.keyBlue, "alle noch ausstehenden Timer löschen"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext": (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"	: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"8"		: (self.cleanUp, "Timerliste bereinigen"),
			"9"		: (self.dropAllTimer, "Alle Timer aus der Datenbank löschen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			# "ok"    : self.keyOK,
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.changesMade = False
		self.filter = True

		self.onLayoutFinish.append(self.readTimer)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Timer löschen")
		if config.plugins.serienRec.recordListView.value == 0:
			self['text_green'].setText("Neueste zuerst")
		elif config.plugins.serienRec.recordListView.value == 1:
			self['text_green'].setText("Älteste zuerst")
		self['text_ok'].setText("Liste bearbeiten")
		self['text_yellow'].setText("Zeige auch alte Timer")
		self['text_blue'].setText("Lösche neue Timer")
		self.num_bt_text[3][1] = "Bereinigen"
		self.num_bt_text[4][1] = "Datenbank leeren"

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		InitSkin(self)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(50 *skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
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
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][0]
		url = self.database.getMarkerURL(serien_name)
		if url:
			serien_id = url
			if serien_id:
				from SerienRecorderSeriesInfoScreen import serienRecShowInfo
				self.session.open(serienRecShowInfo, serien_name, serien_id)

	def wunschliste(self):
		serien_name = self['menu_list'].getCurrent()[0][0]
		url = self.database.getMarkerURL(serien_name)
		serien_id = url
		super(self.__class__, self).wunschliste(serien_id)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.readTimer()

	def viewChange(self):
		if config.plugins.serienRec.recordListView.value == 1:
			config.plugins.serienRec.recordListView.value = 0
			self['text_green'].setText("Neueste zuerst")
		else:
			config.plugins.serienRec.recordListView.value = 1
			self['text_green'].setText("Älteste zuerst")
		config.plugins.serienRec.recordListView.save()
		SerienRecorder.configfile.save()
		self.readTimer()

	def readTimer(self, showTitle=True):
		current_time = int(time.time())
		deltimer = 0
		timerList = []

		timers = self.database.getAllTimer(current_time if self.filter else None)
		for timer in timers:
			(serie, staffel, episode, title, start_time, stbRef, webChannel, eit, activeTimer) = timer
			if int(start_time) < int(current_time):
				deltimer += 1
				timerList.append((serie, staffel, episode, title, start_time, stbRef, webChannel, "1", 0, bool(activeTimer)))
			else:
				timerList.append((serie, staffel, episode, title, start_time, stbRef, webChannel, "0", eit, bool(activeTimer)))

		if showTitle:
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			if self.filter:
				self['title'].setText("Timer-Liste: %s ausstehende Timer" % len(timerList))
			else:
				self['title'].setText("Timer-Liste: %s abgeschlossene und %s ausstehende Timer" % (deltimer, len(timerList ) -deltimer))

		if config.plugins.serienRec.recordListView.value == 0:
			timerList.sort(key=lambda t : t[4])
		elif config.plugins.serienRec.recordListView.value == 1:
			timerList.sort(key=lambda t : t[4])
			timerList.reverse()

		self.chooseMenuList.setList(map(self.buildList, timerList))
		if len(timerList) == 0:
			if showTitle:
				self['title'].instance.setForegroundColor(parseColor("foreground"))
				self['title'].setText("Serien Timer - 0 Serien in der Aufnahmeliste.")

		self.getCover()

	def buildList(self, entry):
		(serie, staffel, episode, title, start_time, stbRef, webChannel, foundIcon, eit, activeTimer) = entry
		xtime = time.strftime(self.WochenTag[time.localtime(int(start_time)).tm_wday ] +", %d.%m.%Y - %H:%M", time.localtime(int(start_time)))
		xtitle = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title)
		imageNone = "%simages/black.png" % SerienRecorder.serienRecMainPath

		if activeTimer:
			SerieColor = None
			channelName = STBHelpers.getChannelByRef(self.channelList, stbRef)
		else:
			SerieColor = parseColor('red').argb()
			channelName = webChannel

		foregroundColor = parseColor('foreground').argb()

		if int(foundIcon) == 0 and config.plugins.serienRec.showPicons.value != "0":
			picon = loadPNG(imageNone)
			if stbRef:
				# Get picon by reference or by name
				piconPath = self.piconLoader.getPicon(stbRef)
				if piconPath:
					self.picloader = PicLoader(80 * skinFactor, 40 * skinFactor)
					picon = self.picloader.load(piconPath)
					self.picloader.destroy()

			return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 5, 80 * skinFactor, 40 * skinFactor, picon),
					(eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 3, 250 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, channelName, SerieColor, SerieColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 29 * skinFactor, 250 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, foregroundColor, foregroundColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 350 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, SerieColor, SerieColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 350 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, re.sub("(?<= - )dump\Z", "(Manuell hinzugefügt !!)", xtitle), foregroundColor, foregroundColor)
			        ]
		else:
			return [entry,
			        (eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 3, 250 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, channelName, SerieColor, SerieColor),
			        (eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 29 * skinFactor, 250 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, foregroundColor, foregroundColor),
			        (eListboxPythonMultiContent.TYPE_TEXT, 350 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, SerieColor, SerieColor),
			        (eListboxPythonMultiContent.TYPE_TEXT, 350 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, re.sub("(?<= - )dump\Z", "(Manuell hinzugefügt !!)", xtitle), foregroundColor, foregroundColor)
			        ]

	def keyOK(self):
		self.session.open(serienRecModifyAdded, False)

	def callDeleteSelectedTimer(self, answer):
		if answer:
			serien_name = self['menu_list'].getCurrent()[0][0]
			staffel = self['menu_list'].getCurrent()[0][1]
			episode = self['menu_list'].getCurrent()[0][2]
			serien_title = self['menu_list'].getCurrent()[0][3]
			serien_time = self['menu_list'].getCurrent()[0][4]
			serien_channel = self['menu_list'].getCurrent()[0][6]
			serien_eit = self['menu_list'].getCurrent()[0][8]
			self.removeTimer(serien_name, staffel, episode, serien_title, serien_time, serien_channel, serien_eit)
		else:
			return

	def removeTimer(self, serien_name, staffel, episode, serien_title, serien_time, serien_channel, serien_eit=0):
		if config.plugins.serienRec.TimerName.value == "1":  # "<Serienname>"
			title = serien_name
		elif config.plugins.serienRec.TimerName.value == "2":  # "SnnEmm - <Episodentitel>"
			title = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), serien_title)
		elif config.plugins.serienRec.TimerName.value == "3":  # "<Serienname> - SnnEmm"
			title = "%s - S%sE%s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2))
		else:  # "<Serienname> - SnnEmm - <Episodentitel>"
			title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)

		from SerienRecorderTimer import serienRecBoxTimer
		removed = serienRecBoxTimer.removeTimerEntry(title, serien_time, serien_eit)
		if not removed:
			print "[SerienRecorder] enigma2 NOOOTTT removed"
		else:
			print "[SerienRecorder] enigma2 Timer removed."

		self.database.removeTimer(serien_name, staffel, episode, None, serien_time, serien_channel, (serien_eit if serien_eit > 0 else None))

		self.changesMade = True
		self.readTimer(False)
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Timer '- %s -' gelöscht." % serien_name)

	def keyRed(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Serien Timer leer."
			return
		else:
			serien_name = self['menu_list'].getCurrent()[0][0]
			staffel = self['menu_list'].getCurrent()[0][1]
			episode = self['menu_list'].getCurrent()[0][2]
			serien_title = self['menu_list'].getCurrent()[0][3]
			serien_time = self['menu_list'].getCurrent()[0][4]
			serien_channel = self['menu_list'].getCurrent()[0][6]
			serien_eit = self['menu_list'].getCurrent()[0][8]

			print self['menu_list'].getCurrent()[0]

			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callDeleteSelectedTimer, MessageBox, "Soll '%s - S%sE%s - %s' wirklich gelöscht werden?" %
				                              (serien_name, str(staffel).zfill(2), str(episode).zfill(2),
				                              re.sub("\Adump\Z", "(Manuell hinzugefügt !!)", serien_title)),
				                              MessageBox.TYPE_YESNO, default=False)
			else:
				self.removeTimer(serien_name, staffel, episode, serien_title, serien_time, serien_channel, serien_eit)

	def keyYellow(self):
		if self.filter:
			self['text_yellow'].setText("Zeige nur neue Timer")
			self.filter = False
		else:
			self['text_yellow'].setText("Zeige auch alte Timer")
			self.filter = True
		self.readTimer()

	def keyBlue(self):
		if config.plugins.serienRec.confirmOnDelete.value:
			self.session.openWithCallback(self.removeNewTimerFromDB, MessageBox,
			                              "Sollen wirklich alle noch ausstehenden Timer von der Box und aus der Datenbank gelöscht werden?",
			                              MessageBox.TYPE_YESNO, default=False)
		else:
			self.removeNewTimerFromDB(True)

	def removeNewTimerFromDB(self, answer):
		if answer:
			current_time = int(time.time())
			timers = self.database.getAllTimer(current_time)
			for timer in timers:
				(serie, staffel, episode, title, start_time, stbRef, webChannel, eit, activeTimer) = timer
				self.removeTimer(serie, staffel, episode, title, start_time, webChannel, eit)

			self.readTimer(False)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("Alle noch ausstehenden Timer wurden gelöscht.")
		else:
			return

	def removeOldTimerFromDB(self, answer):
		if answer:
			self.database.removeAllOldTimer()
			self.database.rebuild()

			self.readTimer(False)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("Alle alten Timer wurden gelöscht.")
		else:
			return

	def dropAllTimer(self):
		if config.plugins.serienRec.confirmOnDelete.value:
			self.session.openWithCallback(self.removeOldTimerFromDB, MessageBox,
			                              "Sollen wirklich alle alten Timer aus der Datenbank gelöscht werden?",
			                              MessageBox.TYPE_YESNO,
			                              default=False)
		else:
			self.removeOldTimerFromDB(True)

	def cleanUp(self):
		numberOfOrphanTimers = self.database.countOrphanTimers()
		self.session.openWithCallback(self.removeOrphanTimerFromDB, MessageBox,
		                              "Es wurden %d Einträge in der Timer-Liste gefunden, für die kein Serien-Marker vorhanden ist, sollen diese Einträge gelöscht werden?" % numberOfOrphanTimers,
		                              MessageBox.TYPE_YESNO,
		                              default=False)

	def removeOrphanTimerFromDB(self, answer):
		if answer:
			self.database.removeOrphanTimers()
			self.database.rebuild()
		else:
			return

	def getCover(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][0]
		serien_id = None
		url = self.database.getMarkerURL(serien_name)
		if url:
			serien_id = url
		SerienRecorder.getCover(self, serien_name, serien_id)

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
		if config.plugins.serienRec.refreshViews.value:
			self.close(self.changesMade)
		else:
			self.close(False)

class serienRecModifyAdded(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, skip=True):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "für die ausgewählte Serien neue Einträge hinzufügen"),
			"cancel": (self.keyCancel, "alle Änderungen verwerfen und zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "zur vorherigen Seite blättern"),
			"right": (self.keyRight, "zur nächsten Seite blättern"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"red": (self.keyRed, "ausgewählten Eintrag löschen"),
			"green": (self.keyGreen, "alle Änderungen speichern und zurück zur vorherigen Ansicht"),
			"yellow": (self.keyYellow, "umschalten Sortierung ein/aus"),
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

		self.delAdded = False
		self.addedlist = []
		self.addedlist_tmp = []
		self.dbData = []
		self.modus = "menu_list"
		self.aSerie = ""
		self.aStaffel = "0"
		self.aFromEpisode = 0
		self.aToEpisode = 0

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
			self['text_yellow'].setText("unsortierte Liste")
		else:
			self['text_yellow'].setText("Sortieren")
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
			self['bt_exit'].show()
			#self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
			self['text_yellow'].show()
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
			serien_id = url

		from SerienRecorderSeriesInfoScreen import serienRecShowInfo
		self.session.open(serienRecShowInfo, serien_name, serien_id)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.readAdded()

	def readAdded(self):
		self.addedlist = []
		series = []
		timers = self.database.getAllTimer(None)
		for timer in timers:
			(Serie, Staffel, Episode, title, start_time, stbRef, webChannel, eit, active) = timer
			series.append(Serie)
			zeile = "%s - S%sE%s - %s" % (Serie, str(Staffel).zfill(2), str(Episode).zfill(2), title)
			self.addedlist.append((zeile.replace(" - dump", " - %s" % "(Manuell hinzugefügt !!)"), Serie, Staffel, Episode, title, start_time, webChannel))

		self.addedlist_tmp = self.addedlist[:]
		number_of_series = len(set(series))
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Für %d Episoden aus %d Serien werden keine Timer mehr erstellt!" % (len(self.addedlist_tmp), number_of_series))

		if config.plugins.serienRec.addedListSorted.value:
			self.addedlist_tmp.sort()
		self.chooseMenuList.setList(map(self.buildList, self.addedlist_tmp))
		self.getCover()

	@staticmethod
	def buildList(entry):
		(zeile, Serie, Staffel, Episode, title, start_time, webChannel) = entry
		foregroundColor = parseColor('foreground').argb()
		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile, foregroundColor)
		        ]

	@staticmethod
	def buildList_popup(entry):
		(Serie,) = entry
		foregroundColor = parseColor('foreground').argb()
		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 560 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, foregroundColor)
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
		if self.aToEpisode == "":
			self.aToEpisode = self.aFromEpisode

		if self.aToEpisode is None: # or self.aFromEpisode is None or self.aStaffel is None:
			return
		else:
			print "[SerienRecorder] Staffel: %s" % self.aStaffel
			print "[SerienRecorder] von Episode: %s" % self.aFromEpisode
			print "[SerienRecorder] bis Episode: %s" % self.aToEpisode

			if self.aStaffel.startswith('0') and len(self.aStaffel) > 1:
				self.aStaffel = self.aStaffel[1:]

			if self.database.addToTimerList(self.aSerie, self.aFromEpisode, self.aToEpisode, self.aStaffel, "dump", int(time.time()), "", "", 0, 1):
				self.readAdded()

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
			self.aStaffel = "0"
			self.aFromEpisode = 0
			self.aToEpisode = 0
			self.session.openWithCallback(self.answerStaffel, NTIVirtualKeyBoard, title = "%s: Staffel eingeben:" % self.aSerie)

	def keyRed(self):
		check = None
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Added-File leer."
			return
		else:
			zeile = self['menu_list'].getCurrent()[0]
			(txt, serie, staffel, episode, title, start_time, webChannel) = zeile
			self.dbData.append((serie.lower(), str(staffel).lower(), episode.lower(), title.lower(), start_time, webChannel.lower()))
			self.addedlist_tmp.remove(zeile)
			self.addedlist.remove(zeile)
			self.chooseMenuList.setList(map(self.buildList, self.addedlist_tmp))
			self.delAdded = True

	def keyGreen(self):
		if self.modus == "menu_list" and self.delAdded:
			self.database.removeTimers(self.dbData)
		self.close()

	def keyYellow(self):
		if self.modus == "menu_list" and len(self.addedlist_tmp) != 0:
			if config.plugins.serienRec.addedListSorted.value:
				self.addedlist_tmp = self.addedlist[:]
				self['text_yellow'].setText("Sortieren")
				config.plugins.serienRec.addedListSorted.setValue(False)
			else:
				self.addedlist_tmp.sort()
				self['text_yellow'].setText("unsortierte Liste")
				config.plugins.serienRec.addedListSorted.setValue(True)
			config.plugins.serienRec.addedListSorted.save()
			SerienRecorder.configfile.save()

			self.chooseMenuList.setList(map(self.buildList, self.addedlist_tmp))
			self.getCover()

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
			serien_id = url

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