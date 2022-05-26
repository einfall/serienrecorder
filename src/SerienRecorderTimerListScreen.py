# coding=utf-8

# This file contains the SerienRecoder Timer-List Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList
from Components.config import config, configfile

from enigma import ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, loadPNG, RT_VALIGN_CENTER
from skin import parseColor
import time, re, os

from .SerienRecorderHelpers import PiconLoader, PicLoader, STBHelpers
from .SerienRecorderScreenHelpers import serienRecBaseScreen, updateMenuKeys, InitSkin, skinFactor
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorderLogWriter import SRLogger
from .SerienRecorder import getDataBaseFilePath, getCover


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
		self.database = SRDatabase(getDataBaseFilePath())
		self.channelList = STBHelpers.buildSTBChannelList()
		self.lastSelectedFSID = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "Liste der erstellten Timer bearbeiten"),
			"cancel": (self.keyCancel, "Zurück zur Serienplaner-Ansicht"),
			"left": (self.keyLeft, "Zur vorherigen Seite blättern"),
			"right": (self.keyRight, "Zur nächsten Seite blättern"),
			"up": (self.keyUp, "Eine Zeile nach oben"),
			"down": (self.keyDown, "Eine Zeile nach unten"),
			"red": (self.keyRed, "Ausgewählten Timer löschen"),
			"green": (self.viewChange, "Sortierung ändern"),
			"yellow": (self.keyYellow, "Umschalten alle/nur aktive Timer anzeigen"),
			"blue": (self.keyBlue, "Alle noch ausstehenden Timer löschen"),
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

	def getCurrentSelection(self):
		if self['menu_list'].getCurrent() is None:
			return None, None, None

		serien_name = self['menu_list'].getCurrent()[0][0]
		serien_fsid = self['menu_list'].getCurrent()[0][10]
		serien_wlid = self.database.getMarkerWLID(serien_fsid)
		return serien_name, serien_wlid, serien_fsid

	def serieInfo(self):
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_name and serien_wlid:
			from .SerienRecorderSeriesInfoScreen import serienRecShowInfo
			self.session.open(serienRecShowInfo, serien_name, serien_wlid, serien_fsid)

	def wunschliste(self):
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_wlid:
			super(self.__class__, self).wunschliste(serien_fsid)

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
		configfile.save()
		self.readTimer()

	def readTimer(self, showTitle=True):
		current_time = int(time.time())
		self['title'].setText("Lade Timer-Liste...")

		def loadTimer():
			print("[SerienRecorder] loadAllTimer")
			database = SRDatabase(getDataBaseFilePath())
			return database.getAllTimer(current_time if self.filter else None)

		def onLoadTimerSuccessful(timers):
			completedTimer = 0
			timerList = []
			self['title'].instance.setForegroundColor(parseColor("foreground"))

			for timer in timers:
				(row_id, serie, staffel, episode, title, start_time, stbRef, webChannel, eit, activeTimer, serien_fsid) = timer
				if int(start_time) < int(current_time):
					completedTimer += 1
					timerList.append((serie, staffel, episode, title, start_time, stbRef, webChannel, True, 0, bool(activeTimer), serien_fsid))
				else:
					timerList.append((serie, staffel, episode, title, start_time, stbRef, webChannel, False, eit, bool(activeTimer), serien_fsid))

			if showTitle:
				if self.filter:
					self['title'].setText("Timer-Liste: %s ausstehende Timer" % len(timerList))
				else:
					self['title'].setText("Timer-Liste: %s abgeschlossene und %s ausstehende Timer" % (completedTimer, len(timerList) - completedTimer))

			if config.plugins.serienRec.recordListView.value == 0:
				timerList.sort(key=lambda t: t[4])
			elif config.plugins.serienRec.recordListView.value == 1:
				timerList.sort(key=lambda t: t[4])
				timerList.reverse()

			self.chooseMenuList.setList(list(map(self.buildList, timerList)))
			if len(timerList) == 0:
				if showTitle:
					self['title'].setText("Timer-Liste: 0 ausstehende Timer")

			self.getCover()

		import twisted.python.runtime
		if twisted.python.runtime.platform.supportsThreads():
			from twisted.internet.threads import deferToThread
			deferToThread(loadTimer).addCallback(onLoadTimerSuccessful)
		else:
			timers = loadTimer()
			onLoadTimerSuccessful(timers)

	def buildList(self, entry):
		(serie, staffel, episode, title, start_time, serviceRef, webChannel, completed, eit, activeTimer, serien_fsid) = entry
		xtime = ''
		if start_time > 0:
			xtime = time.strftime(self.WochenTag[time.localtime(int(start_time)).tm_wday ] +", %d.%m.%Y - %H:%M", time.localtime(int(start_time)))

		if start_time == 0 or title == 'dump':
			title = '(Manuell hinzugefügt !!)'
		xtitle = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title)

		imageNone = "%s/images/black.png" % os.path.dirname(__file__)

		imageTimer = imageNone

		channelName = webChannel
		if serviceRef:
			channelName = STBHelpers.getChannelByRef(self.channelList, serviceRef)
		
		if activeTimer:
			SerieColor = None
		else:
			SerieColor = parseColor("red").argb()

		foregroundColor = parseColor("foreground").argb()

		picon = loadPNG(imageNone)

		if not completed:
			imageTimer = "%s/images/timer.png" % os.path.dirname(__file__)

			if serviceRef and config.plugins.serienRec.showPicons.value != "0":
				# Get picon by reference or by name
				piconPath = self.piconLoader.getPicon(serviceRef if config.plugins.serienRec.showPicons.value == "1" else channelName)
				if piconPath:
					self.picloader = PicLoader(80 * skinFactor, 40 * skinFactor)
					picon = self.picloader.load(piconPath)
					self.picloader.destroy()

		return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 5, 80 * skinFactor, 40 * skinFactor, picon),
				(eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 3, 250 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, channelName, SerieColor, SerieColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 27 * skinFactor, 220 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, foregroundColor, foregroundColor),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 315 * skinFactor, 30 * skinFactor, 30 * skinFactor, 22 * skinFactor, loadPNG(imageTimer)),
				(eListboxPythonMultiContent.TYPE_TEXT, 350 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, SerieColor, SerieColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 350 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtitle, foregroundColor, foregroundColor)
		        ]


	def keyOK(self):
		from .SerienRecorderEditTimerListScreen import serienRecEditTimerList
		self.session.open(serienRecEditTimerList)

	def callDeleteSelectedTimer(self, answer):
		if answer:
			serien_name = self['menu_list'].getCurrent()[0][0]
			staffel = self['menu_list'].getCurrent()[0][1]
			episode = self['menu_list'].getCurrent()[0][2]
			serien_title = self['menu_list'].getCurrent()[0][3]
			serien_time = self['menu_list'].getCurrent()[0][4]
			serien_channel = self['menu_list'].getCurrent()[0][6]
			serien_eit = self['menu_list'].getCurrent()[0][8]
			serien_fsid = self['menu_list'].getCurrent()[0][10]
			self.removeTimer(self.database, serien_name, serien_fsid, staffel, episode, serien_title, serien_time, serien_channel, serien_eit)
			self.changesMade = True
			self.readTimer(False)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("Timer '- %s -' gelöscht." % serien_name)
		else:
			return

	@staticmethod
	def removeTimer(database, serien_name, serien_fsid, staffel, episode, serien_title, serien_time, serien_channel, serien_eit=0):

		markerType = database.getMarkerType(serien_fsid)
		if markerType is None:
			markerType = 1
		else:
			markerType = int(markerType)

		from .SerienRecorderTimer import serienRecTimer
		title = serienRecTimer.getTimerName(serien_name, staffel, episode, serien_title, markerType)

		from .SerienRecorderTimer import serienRecBoxTimer
		removed = serienRecBoxTimer.removeTimerEntry(title, serien_time, serien_eit)
		if not removed:
			print("[SerienRecorder] enigma2 NOOOTTT removed")
		else:
			print("[SerienRecorder] enigma2 Timer removed.")

		database.removeTimer(serien_fsid, staffel, episode, None, serien_time, serien_channel)
		seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
		SRLogger.writeLogFilter("timerDebug", "Timer gelöscht: ' %s - %s - %s '" % (serien_name, seasonEpisodeString, serien_title))

	def keyRed(self):
		if self['menu_list'].getCurrent() is None:
			print("[SerienRecorder] Angelegte Timer Tabelle leer.")
			return

		serien_name = self['menu_list'].getCurrent()[0][0]
		staffel = self['menu_list'].getCurrent()[0][1]
		episode = self['menu_list'].getCurrent()[0][2]
		serien_title = self['menu_list'].getCurrent()[0][3]
		serien_time = self['menu_list'].getCurrent()[0][4]
		serien_channel = self['menu_list'].getCurrent()[0][6]
		serien_eit = self['menu_list'].getCurrent()[0][8]
		serien_fsid = self['menu_list'].getCurrent()[0][10]

		#print(self['menu_list'].getCurrent()[0])

		if config.plugins.serienRec.confirmOnDelete.value:
			title = re.sub("\Adump\Z", "(Manuell hinzugefügt !!)", serien_title)
			title = re.sub("\Awebdump\Z", "(Manuell übers Webinterface hinzugefügt !!)", title)
			self.session.openWithCallback(self.callDeleteSelectedTimer, MessageBox, "Soll der Timer für '%s - S%sE%s - %s' wirklich gelöscht werden?" %
			                              (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title),
			                              MessageBox.TYPE_YESNO, default=False)
		else:
			self.removeTimer(self.database, serien_name, serien_fsid, staffel, episode, serien_title, serien_time, serien_channel, serien_eit)
			self.changesMade = True
			self.readTimer(False)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("Timer '- %s -' gelöscht." % serien_name)

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
			self.session.openWithCallback(self.removeRemainingTimerFromDB, MessageBox,
			                              "Sollen wirklich alle noch ausstehenden Timer von der Box und aus der Datenbank gelöscht werden?",
			                              MessageBox.TYPE_YESNO, default=False)
		else:
			self.removeRemainingTimerFromDB(True)

	def removeRemainingTimerFromDB(self, answer):
		if answer:
			current_time = int(time.time())
			timers = self.database.getAllTimer(current_time)
			for timer in timers:
				(row_id, serie, staffel, episode, title, start_time, stbRef, webChannel, eit, activeTimer, serien_fsid) = timer
				self.removeTimer(self.database, serie, serien_fsid, staffel, episode, title, start_time, webChannel, eit)

			self.changesMade = True
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
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_name and serien_wlid and serien_fsid and self.lastSelectedFSID != serien_fsid:
			getCover(self, serien_name, serien_fsid)
			# Avoid flickering while scrolling through timers of same series
			self.lastSelectedFSID = serien_fsid

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
		self.close(self.changesMade)
