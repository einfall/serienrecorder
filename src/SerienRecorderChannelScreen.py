# coding=utf-8

# This file contains the SerienRecoder Channel Screen

from __init__ import _

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList

from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, loadPNG, RT_VALIGN_CENTER, eTimer
from skin import parseColor

from SerienRecorderHelpers import *
from SerienRecorderAboutScreen import *
from SerienRecorderScreenHelpers import *
from SerienRecorderSeriesServer import *
import SerienRecorder

class serienRecMainChannelEdit(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.serienRecChlist = []
		self.selected_sender = None
		self.skin = None
		self.displayMode = 2
		self.displayTimer = eTimer()
		self.displayTimer_conn = None
		self.chooseMenuList = None
		self.chooseMenuList_popup = None
		self.chooseMenuList_popup2 = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"       : (self.keyOK, _("Popup-Fenster zur Auswahl des STB-Channels öffnen")),
			"cancel"   : (self.keyCancel, _("zurück zur Serienplaner-Ansicht")),
			"red"	   : (self.keyRed, _("umschalten ausgewählter Sender für Timererstellung aktiviert/deaktiviert")),
			"red_long" : (self.keyRedLong, _("ausgewählten Sender aus der Channelliste endgültig löschen")),
			"green"    : (self.keyGreen, _("Sender-Zuordnung aktualisieren")),
			"menu"     : (self.channelSetup, _("Menü für Sender-Einstellungen öffnen")),
			"menu_long": (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"left"     : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right"    : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"       : (self.keyUp, _("eine Zeile nach oben")),
			"down"     : (self.keyDown, _("eine Zeile nach unten")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zum ausgewählten Sender auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zum ausgewählten Sender auf Wikipedia suchen")),
			"0"		   : (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"3"		   : (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"6"		   : (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		   : (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.modus = "list"
		self.changesMade = False

		cCursor = SerienRecorder.dbSerRec.cursor()
		cCursor.execute("SELECT * FROM Channels")
		row = cCursor.fetchone()
		if row:
			cCursor.close()
			self.onLayoutFinish.append(self.showChannels)
		else:
			cCursor.close()
			if config.plugins.serienRec.selectBouquets.value:
				self.stbChlist = STBHelpers.buildSTBChannelList(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChlist = STBHelpers.buildSTBChannelList()
			self.onLayoutFinish.append(self.readWebChannels)

		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_green'].setText(_("Aktualisieren"))
		self['text_ok'].setText(_("Sender auswählen"))

		self.num_bt_text[4][0] = buttonText_na
		if longButtonText:
			self['text_red'].setText(_("An/Aus (lang: Löschen)"))
			self.num_bt_text[4][2] = _("Setup Sender (lang: global)")
		else:
			self['text_red'].setText(_("(De)aktivieren/Löschen"))
			self.num_bt_text[4][2] = _("Setup Sender/global")

		self.displayTimer = None
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
			self.updateMenuKeys()

			self.displayTimer = eTimer()
			if isDreamboxOS:
				self.displayTimer_conn = self.displayTimer.timeout.connect(self.updateMenuKeys)
			else:
				self.displayTimer.callback.append(self.updateMenuKeys)
			self.displayTimer.start(config.plugins.serienRec.DisplayRefreshRate.value * 1000)

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25*skinFactor))
		self['list'] = self.chooseMenuList
		self['list'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(int(25*skinFactor))
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		# popup2
		self.chooseMenuList_popup2 = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup2.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup2.l.setItemHeight(int(25*skinFactor))
		self['popup_list2'] = self.chooseMenuList_popup2
		self['popup_list2'].hide()

		self['title'].setText(_("Lade Web-Channel / STB-Channels..."))

		self['Web_Channel'].setText(_("Web-Channel"))
		self['STB_Channel'].setText(_("STB-Channel"))
		self['alt_STB_Channel'].setText(_("alt. STB-Channel"))

		self['Web_Channel'].show()
		self['STB_Channel'].show()
		self['alt_STB_Channel'].show()
		self['separator'].show()

		if not showAllButtons:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def channelSetup(self):
		webSender = self['list'].getCurrent()[0][0]
		self.session.open(SerienRecorder.serienRecChannelSetup, webSender)

	def readLogFile(self):
		self.session.open(SerienRecorder.serienRecReadLog)

	def showProposalDB(self):
		self.session.open(SerienRecorder.serienRecShowSeasonBegins)

	def showConflicts(self):
		self.session.open(SerienRecorder.serienRecShowConflicts)

	def showWishlist(self):
		self.session.open(SerienRecorder.serienRecWishlist)

	def youtubeSearch(self):
		if SerienRecorder.epgTranslatorInstalled:
			check = self['list'].getCurrent()
			if check is None:
				return

			sender_name = self['list'].getCurrent()[0][0]
			from Plugins.Extensions.EPGTranslator.plugin import searchYouTube
			self.session.open(searchYouTube, sender_name)
		else:
			self.session.open(MessageBox, _("Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein.") % "EPGTranslator von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def WikipediaSearch(self):
		if SerienRecorder.WikipediaInstalled:
			check = self['list'].getCurrent()
			if check is None:
				return

			sender_name = self['list'].getCurrent()[0][0]
			from Plugins.Extensions.Wikipedia.plugin import wikiSearch
			self.session.open(wikiSearch, sender_name)
		else:
			self.session.open(MessageBox, _("Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein.") % "Wikipedia von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def showManual(self):
		if SerienRecorder.OperaBrowserInstalled:
			self.session.open(SerienRecorder.Browser, SerienRecorder.SR_OperatingManual, True)
		elif SerienRecorder.DMMBrowserInstalled:
			self.session.open(SerienRecorder.Browser, True, SerienRecorder.SR_OperatingManual)
		else:
			self.session.open(MessageBox, _("Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein.") % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)

	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, SerienRecorder.serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:
			if result[0]:
				if config.plugins.serienRec.update.value:
					SerienRecorder.serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					SerienRecorder.serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.showChannels()

	def showChannels(self):
		self.serienRecChlist = []
		cCursor = SerienRecorder.dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels ORDER BY LOWER(WebChannel)")
		for row in cCursor:
			(webSender, servicename, serviceref, altservicename, altserviceref, status) = row
			self.serienRecChlist.append((webSender, servicename, altservicename, status))

		if len(self.serienRecChlist) != 0:
			self['title'].setText(_("Sender zuordnen"))
			self.chooseMenuList.setList(map(self.buildList, self.serienRecChlist))
		else:
			print "[SerienRecorder] Fehler bei der Erstellung der SerienRecChlist.."
		cCursor.close()

	def readWebChannels(self):
		print "[SerienRecorder] call webpage.."
		self['title'].setText(_("Lade Web-Channels..."))

		#from WebChannels import WebChannels
		#WebChannels(self.createWebChannels, self.dataError).request()
		self.createWebChannels(SeriesServer().doGetWebChannels())

	def createWebChannels(self, web_chlist):
		if web_chlist:
			from difflib import SequenceMatcher
			sequenceMatcher = SequenceMatcher(" ".__eq__, "", "")

			web_chlist.sort(key=lambda x: x.lower())
			print web_chlist
			self.serienRecChlist = []
			if len(web_chlist) != 0:
				self['title'].setText(_("erstelle Channels-List..."))
				cCursor = SerienRecorder.dbSerRec.cursor()
				sql = "INSERT OR IGNORE INTO Channels (WebChannel, STBChannel, ServiceRef, Erlaubt) VALUES (?, ?, ?, ?)"
				for webSender in web_chlist:
					cCursor.execute("SELECT * FROM Channels WHERE LOWER(WebChannel)=?", (webSender.lower(),))
					row = cCursor.fetchone()
					if not row:
						found = False
						for servicename,serviceref in self.stbChlist:
							#if re.search(webSender.lower(), servicename.lower(), re.S):
							#if re.search("\A%s\Z" % webSender.lower().replace('+','\+').replace('.','\.'), servicename.lower(), re.S):
							sequenceMatcher.set_seqs(webSender.lower(), servicename.lower())
							ratio = sequenceMatcher.ratio()
							if ratio == 1:
								cCursor.execute(sql, (webSender, servicename, serviceref, 1))
								self.serienRecChlist.append((webSender, servicename, "", "1"))
								found = True
								break
						if not found:
							cCursor.execute(sql, (webSender, "", "", 0))
							self.serienRecChlist.append((webSender, "", "", "0"))
						self.changesMade = True
						global runAutocheckAtExit
						runAutocheckAtExit = True
				SerienRecorder.dbSerRec.commit()
				cCursor.close()
			else:
				print "[SerienRecorder] webChannel list leer.."

			if len(self.serienRecChlist) != 0:
				self.chooseMenuList.setList(map(self.buildList, self.serienRecChlist))
			else:
				print "[SerienRecorder] Fehler bei der Erstellung der SerienRecChlist.."

		else:
			print "[SerienRecorder] get webChannel error.."

		self['title'].setText(_("Web-Channel / STB-Channels."))

	@staticmethod
	def buildList(entry):
		(webSender, stbSender, altstbSender, status) = entry
		if int(status) == 0:
			imageStatus = "%simages/minus.png" % serienRecMainPath
		else:
			imageStatus = "%simages/plus.png" % serienRecMainPath

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 7 * skinFactor, 16 * skinFactor, 16 * skinFactor, loadPNG(imageStatus)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 0, 300 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 350 * skinFactor, 0, 250 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, stbSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 600 * skinFactor, 0, 250 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, altstbSender, parseColor('yellow').argb())
			]

	@staticmethod
	def buildList_popup(entry):
		(servicename,serviceref) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 1, 250 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, servicename)
			]

	def keyOK(self):
		global runAutocheckAtExit
		if self.modus == "list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			if config.plugins.serienRec.selectBouquets.value:
				self.stbChlist = STBHelpers.buildSTBChannelList(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChlist = STBHelpers.buildSTBChannelList()
			self.stbChlist.insert(0, ("", ""))
			self.chooseMenuList_popup.setList(map(self.buildList_popup, self.stbChlist))
			idx = 0
			cCursor = SerienRecorder.dbSerRec.cursor()
			cCursor.execute("SELECT STBChannel, alternativSTBChannel FROM Channels WHERE LOWER(WebChannel)=?", (self['list'].getCurrent()[0][0].lower(),))
			row = cCursor.fetchone()
			if row:
				(stbChannel, altstbChannel) = row
				if stbChannel:
					try:
						idx = zip(*self.stbChlist)[0].index(stbChannel)
					except:
						pass
			cCursor.close()
			self['popup_list'].moveToIndex(idx)
			self['title'].setText(_("Standard STB-Channel für %s:") % self['list'].getCurrent()[0][0])
		elif config.plugins.serienRec.selectBouquets.value:
			if self.modus == "popup_list":
				self.modus = "popup_list2"
				self['popup_list'].hide()
				self['popup_list2'].show()
				self['popup_bg'].show()
				self.stbChlist = STBHelpers.buildSTBChannelList(config.plugins.serienRec.AlternativeBouquet.value)
				self.stbChlist.insert(0, ("", ""))
				self.chooseMenuList_popup2.setList(map(self.buildList_popup, self.stbChlist))
				idx = 0
				cCursor = SerienRecorder.dbSerRec.cursor()
				cCursor.execute("SELECT STBChannel, alternativSTBChannel FROM Channels WHERE LOWER(WebChannel)=?", (self['list'].getCurrent()[0][0].lower(),))
				row = cCursor.fetchone()
				if row:
					(stbChannel, altstbChannel) = row
					if stbChannel:
						try:
							idx = zip(*self.stbChlist)[0].index(altstbChannel)
						except:
							pass
				cCursor.close()
				self['popup_list2'].moveToIndex(idx)
				self['title'].setText(_("alternativer STB-Channels für %s:") % self['list'].getCurrent()[0][0])
			else:
				self.modus = "list"
				self['popup_list'].hide()
				self['popup_list2'].hide()
				self['popup_bg'].hide()

				check = self['list'].getCurrent()
				if check is None:
					print "[SerienRecorder] Channel-List leer (list)."
					return

				check = self['popup_list'].getCurrent()
				if check is None:
					print "[SerienRecorder] Channel-List leer (popup_list)."
					return

				chlistSender = self['list'].getCurrent()[0][0]
				stbSender = self['popup_list'].getCurrent()[0][0]
				stbRef = self['popup_list'].getCurrent()[0][1]
				altstbSender = self['popup_list2'].getCurrent()[0][0]
				altstbRef = self['popup_list2'].getCurrent()[0][1]
				print "[SerienRecorder] select:", chlistSender, stbSender, stbRef, altstbSender, altstbRef
				cCursor = SerienRecorder.dbSerRec.cursor()
				sql = "UPDATE OR IGNORE Channels SET STBChannel=?, ServiceRef=?, alternativSTBChannel=?, alternativServiceRef=?, Erlaubt=? WHERE LOWER(WebChannel)=?"
				if stbSender != "" or altstbSender != "":
					cCursor.execute(sql, (stbSender, stbRef, altstbSender, altstbRef, 1, chlistSender.lower()))
				else:
					cCursor.execute(sql, (stbSender, stbRef, altstbSender, altstbRef, 0, chlistSender.lower()))
				self.changesMade = True
				runAutocheckAtExit = True
				SerienRecorder.dbSerRec.commit()
				cCursor.close()
				self['title'].setText(_("Sender zuordnen"))
				self.showChannels()
		else:
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_list2'].hide()
			self['popup_bg'].hide()

			if self['list'].getCurrent() is None:
				print "[SerienRecorder] Channel-List leer (list)."
				return

			if self['popup_list'].getCurrent() is None:
				print "[SerienRecorder] Channel-List leer (popup_list)."
				return

			chlistSender = self['list'].getCurrent()[0][0]
			stbSender = self['popup_list'].getCurrent()[0][0]
			stbRef = self['popup_list'].getCurrent()[0][1]
			print "[SerienRecorder] select:", chlistSender, stbSender, stbRef
			cCursor = SerienRecorder.dbSerRec.cursor()
			sql = "UPDATE OR IGNORE Channels SET STBChannel=?, ServiceRef=?, Erlaubt=? WHERE LOWER(WebChannel)=?"
			if stbSender != "":
				cCursor.execute(sql, (stbSender, stbRef, 1, chlistSender.lower()))
			else:
				cCursor.execute(sql, (stbSender, stbRef, 0, chlistSender.lower()))
			self.changesMade = True
			runAutocheckAtExit = True
			SerienRecorder.dbSerRec.commit()
			cCursor.close()
			self['title'].setText(_("Sender zuordnen"))
			self.showChannels()

	def keyRed(self):
		global runAutocheckAtExit
		if self['list'].getCurrent() is None:
			print "[SerienRecorder] Channel-List leer."
			return

		if self.modus == "list":
			chlistSender = self['list'].getCurrent()[0][0]
			sender_status = self['list'].getCurrent()[0][2]
			print sender_status

			cCursor = SerienRecorder.dbSerRec.cursor()
			cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (chlistSender.lower(),))
			row = cCursor.fetchone()
			if row:
				(webSender, servicename, serviceref, status) = row
				sql = "UPDATE OR IGNORE Channels SET Erlaubt=? WHERE LOWER(WebChannel)=?"
				if int(status) == 0:
					cCursor.execute(sql, (1, chlistSender.lower()))
					print "[SerienRecorder] change to:", webSender, servicename, serviceref, "1"
					self['title'].instance.setForegroundColor(parseColor("red"))
					self['title'].setText("")
					self['title'].setText(_("Sender '- %s -' wurde aktiviert.") % webSender)
				else:
					cCursor.execute(sql, (0, chlistSender.lower()))
					print "[SerienRecorder] change to:",webSender, servicename, serviceref, "0"
					self['title'].instance.setForegroundColor(parseColor("red"))
					self['title'].setText("")
					self['title'].setText(_("Sender '- %s -' wurde deaktiviert.") % webSender)
				self.changesMade = True
				runAutocheckAtExit = True
				SerienRecorder.dbSerRec.commit()

			cCursor.close()
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			self.showChannels()

	def keyGreen(self):
		self.session.openWithCallback(self.channelReset, MessageBox, _("Sender-Liste zurücksetzen ?"), MessageBox.TYPE_YESNO)

	def channelReset(self, answer):
		if answer:
			print "[SerienRecorder] channel-list reset..."

			if config.plugins.serienRec.selectBouquets.value:
				self.stbChlist = STBHelpers.buildSTBChannelList(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChlist = STBHelpers.buildSTBChannelList()
			self.readWebChannels()
		else:
			print "[SerienRecorder] channel-list ok."

	def keyRedLong(self):
		check = self['list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Serien Marker leer."
			return
		else:
			self.selected_sender = self['list'].getCurrent()[0][0]
			cCursor = SerienRecorder.dbSerRec.cursor()
			cCursor.execute("SELECT * FROM Channels WHERE LOWER(WebChannel)=?", (self.selected_sender.lower(),))
			row = cCursor.fetchone()
			if row:
				print "gefunden."
				if config.plugins.serienRec.confirmOnDelete.value:
					self.session.openWithCallback(self.channelDelete, MessageBox, _("Soll '%s' wirklich entfernt werden?") % self.selected_sender, MessageBox.TYPE_YESNO, default = False)
				else:
					self.channelDelete(True)
			cCursor.close()

	def channelDelete(self, answer):
		if not answer:
			return
		cCursor = SerienRecorder.dbSerRec.cursor()
		cCursor.execute("DELETE FROM NeuerStaffelbeginn WHERE LOWER(Sender)=?", (self.selected_sender.lower(),))
		cCursor.execute("DELETE FROM SenderAuswahl WHERE LOWER(ErlaubterSender)=?", (self.selected_sender.lower(),))
		cCursor.execute("DELETE FROM Channels WHERE LOWER(WebChannel)=?", (self.selected_sender.lower(),))
		SerienRecorder.dbSerRec.commit()
		cCursor.close()
		self.changesMade = True
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText(_("Sender '- %s -' entfernt.") % self.selected_sender)
		self.showChannels()

	def keyLeft(self):
		self[self.modus].pageUp()

	def keyRight(self):
		self[self.modus].pageDown()

	def keyDown(self):
		self[self.modus].down()

	def keyUp(self):
		self[self.modus].up()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
		elif self.modus == "popup_list2":
			self.modus = "list"
			self['popup_list2'].hide()
			self['popup_bg'].hide()
		else:
			if config.plugins.serienRec.refreshViews.value:
				self.close(self.changesMade)
			else:
				self.close(False)

	@staticmethod
	def dataError(error, url=None):
		if url:
			writeErrorLog("   serienRecMainChannelEdit(): %s\n   Url: %s" % (error, url))
		else:
			writeErrorLog("   serienRecMainChannelEdit(): %s" % error)
		print error
